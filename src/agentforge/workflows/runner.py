from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Mapping

from agentforge.runs.service import RunService
from agentforge.workflows.checkpoint import WorkflowCheckpointStore
from agentforge.workflows.definition import WorkflowDefinition, WorkflowStepDefinition
from agentforge.workflows.state import WorkflowRunState, WorkflowStepState


@dataclass
class WorkflowExecutionContext:
    run_id: str
    workflow_id: str
    task_type: str
    step: WorkflowStepDefinition
    step_index: int
    attempt: int
    input_data: dict[str, Any]
    state: dict[str, Any]
    project_root: Path
    run_service: RunService


@dataclass
class WorkflowStepResult:
    status: str = "completed"
    output: dict[str, Any] = field(default_factory=dict)
    artifacts: list[dict[str, Any]] = field(default_factory=list)
    hqs_reports: dict[str, dict[str, Any]] = field(default_factory=dict)
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    errors: list[dict[str, Any]] = field(default_factory=list)
    state_updates: dict[str, Any] = field(default_factory=dict)
    stop: bool = False


WorkflowStepHandler = Callable[[WorkflowExecutionContext], WorkflowStepResult | dict[str, Any] | None]


class WorkflowRunner:
    def __init__(
        self,
        definition: WorkflowDefinition,
        project_root: Path | str = ".",
        run_service: RunService | None = None,
    ) -> None:
        self.definition = definition
        self.project_root = Path(project_root).resolve()
        self.run_service = run_service or RunService(self.project_root)
        self.checkpoints = WorkflowCheckpointStore(self.run_service)
        self.state: WorkflowRunState | None = None

    @classmethod
    def for_task(
        cls,
        project_root: Path | str,
        workflow_id: str,
        task_type: str,
        steps: list[str] | tuple[str, ...] | None = None,
        stop_conditions: dict[str, Any] | None = None,
        retry_policy: dict[str, Any] | None = None,
        artifact_policy: dict[str, Any] | None = None,
    ) -> "WorkflowRunner":
        return cls(
            WorkflowDefinition.from_step_names(
                workflow_id=workflow_id,
                task_type=task_type,
                step_names=steps,
                stop_conditions=stop_conditions,
                retry_policy=retry_policy,
                artifact_policy=artifact_policy,
            ),
            project_root=project_root,
        )

    @property
    def repository(self) -> Any:
        return self.run_service.repository

    def ensure_initialized(self) -> Path:
        return self.run_service.ensure_initialized()

    def execute(
        self,
        title: str,
        input_data: dict[str, Any],
        handlers: Mapping[str, WorkflowStepHandler],
        run_id: str | None = None,
        created_at: str | None = None,
    ) -> str:
        resolved_run_id = self.start_run(
            task_type=self.definition.task_type,
            title=title,
            input_data=input_data,
            run_id=run_id,
            created_at=created_at,
        )
        shared_state: dict[str, Any] = {}
        step_outputs: list[dict[str, Any]] = []
        artifact_index = 1
        tool_call_index = 1

        for step_index, step in enumerate(self.definition.steps, start=1):
            handler = handlers.get(step.name)
            if handler is None:
                result = WorkflowStepResult(
                    status="failed",
                    errors=[
                        {
                            "error_type": "WorkflowStepHandlerMissing",
                            "message": f"Workflow step has no handler: {step.name}",
                            "step": step.name,
                        }
                    ],
                )
                self._record_execution_result(
                    resolved_run_id,
                    step,
                    step_index,
                    1,
                    input_data,
                    shared_state,
                    result,
                )
                step_outputs.append({"name": step.name, "status": result.status, "output": result.output})
                self.fail_run(
                    resolved_run_id,
                    result.errors,
                    {"state": shared_state, "failed_step": step.name, "steps": step_outputs},
                )
                return resolved_run_id

            max_attempts = self._max_attempts_for_step(step)
            final_result: WorkflowStepResult | None = None
            for attempt in range(1, max_attempts + 1):
                context = WorkflowExecutionContext(
                    run_id=resolved_run_id,
                    workflow_id=self.definition.workflow_id,
                    task_type=self.definition.task_type,
                    step=step,
                    step_index=step_index,
                    attempt=attempt,
                    input_data=input_data,
                    state=shared_state,
                    project_root=self.project_root,
                    run_service=self.run_service,
                )
                try:
                    final_result = self._normalize_step_result(handler(context))
                except Exception as exc:  # noqa: BLE001
                    final_result = WorkflowStepResult(
                        status="failed",
                        errors=[
                            {
                                "error_type": exc.__class__.__name__,
                                "message": str(exc),
                                "step": step.name,
                                "attempt": attempt,
                            }
                        ],
                    )

                if final_result.state_updates:
                    shared_state.update(final_result.state_updates)

                self._record_execution_result(
                    resolved_run_id,
                    step,
                    step_index,
                    attempt,
                    input_data,
                    shared_state,
                    final_result,
                )
                for artifact in final_result.artifacts:
                    self.record_artifact(resolved_run_id, artifact, artifact_index)
                    artifact_index += 1
                for scope, report in final_result.hqs_reports.items():
                    self.record_hqs(resolved_run_id, scope, report)
                for tool_call in final_result.tool_calls:
                    self.record_tool_call(resolved_run_id, tool_call, tool_call_index)
                    tool_call_index += 1

                if final_result.status in {"completed", "skipped"}:
                    break

            if final_result is None:
                final_result = WorkflowStepResult(status="completed")
            step_outputs.append(
                {
                    "name": step.name,
                    "status": final_result.status,
                    "output": final_result.output,
                    "errors": final_result.errors,
                }
            )

            if final_result.status not in {"completed", "skipped"}:
                self.fail_run(
                    resolved_run_id,
                    final_result.errors
                    or [
                        {
                            "error_type": "WorkflowStepFailed",
                            "message": f"Workflow step failed: {step.name}",
                            "step": step.name,
                        }
                    ],
                    {"state": shared_state, "failed_step": step.name, "steps": step_outputs},
                )
                return resolved_run_id

            if final_result.stop:
                self.complete_run(
                    resolved_run_id,
                    {"state": shared_state, "stopped_at": step.name, "steps": step_outputs},
                )
                return resolved_run_id

        self.complete_run(resolved_run_id, {"state": shared_state, "steps": step_outputs})
        return resolved_run_id

    def start_run(
        self,
        task_type: str,
        title: str,
        input_data: dict[str, Any],
        run_id: str | None = None,
        created_at: str | None = None,
        status: str = "running",
    ) -> str:
        resolved_run_id = self.run_service.start_run(
            task_type=task_type,
            title=title,
            input_data=input_data,
            run_id=run_id,
            created_at=created_at,
            status=status,
        )
        self.state = WorkflowRunState(
            run_id=resolved_run_id,
            workflow_id=self.definition.workflow_id,
            task_type=task_type,
            status=status,
            started_at=created_at or "",
            metadata={
                "workflow": self.definition.to_dict(),
                "title": title,
                "input": input_data,
            },
        )
        if not self.state.started_at:
            run = self.run_service.repository.get_run(resolved_run_id)
            self.state.started_at = run.created_at if run else self.state.started_at
        self._checkpoint("start")
        return resolved_run_id

    def update_run(
        self,
        run_id: str,
        status: str,
        output_data: dict[str, Any] | None = None,
        trace_path: Path | str | None = None,
        completed: bool = False,
    ) -> None:
        self.run_service.update_run(
            run_id=run_id,
            status=status,
            output_data=self._with_workflow_output(output_data),
            trace_path=trace_path,
            completed=completed,
        )
        self._update_state(run_id, status=status, metadata={"output": output_data or {}})
        if completed:
            self._finish_state(status)
        self._checkpoint("update_run")

    def complete_run(
        self,
        run_id: str,
        output_data: dict[str, Any] | None = None,
        trace_path: Path | str | None = None,
        status: str = "completed",
    ) -> None:
        self.run_service.complete_run(
            run_id=run_id,
            output_data=self._with_workflow_output(output_data),
            trace_path=trace_path,
            status=status,
        )
        self._update_state(run_id, status=status, metadata={"output": output_data or {}})
        self._finish_state(status)
        self._checkpoint("complete")

    def fail_run(
        self,
        run_id: str,
        error: Any,
        output_data: dict[str, Any] | None = None,
        trace_path: Path | str | None = None,
    ) -> None:
        self.run_service.fail_run(
            run_id=run_id,
            error=error,
            output_data=self._with_workflow_output(output_data),
            trace_path=trace_path,
        )
        self._update_state(run_id, status="failed", metadata={"error": error})
        self._finish_state("failed")
        self._checkpoint("fail")

    def record_run(
        self,
        task_type: str,
        title: str,
        input_data: dict[str, Any],
        output_data: dict[str, Any] | None = None,
        trace_path: Path | str | None = None,
        status: str = "completed",
        run_id: str | None = None,
        steps: list[dict[str, Any]] | None = None,
        artifacts: list[dict[str, Any]] | None = None,
        hqs_reports: dict[str, dict[str, Any]] | None = None,
        tool_calls: list[dict[str, Any]] | None = None,
        created_at: str | None = None,
    ) -> str:
        resolved_run_id = self.run_service.record_run(
            task_type=task_type,
            title=title,
            input_data=input_data,
            output_data=self._with_workflow_output(output_data),
            trace_path=trace_path,
            status=status,
            run_id=run_id,
            steps=steps,
            artifacts=artifacts,
            hqs_reports=hqs_reports,
            tool_calls=tool_calls,
            created_at=created_at,
        )
        self._update_state(resolved_run_id, status=status, metadata={"output": output_data or {}})
        if status in {"completed", "failed", "cancelled"}:
            self._finish_state(status)
        self._checkpoint("record_run")
        return resolved_run_id

    def record_step(self, run_id: str, step: dict[str, Any], index: int) -> None:
        step_name = str(step.get("name") or step.get("tool_name") or f"step_{index}")
        step_def = self.definition.step_for(step_name)
        step_payload = {**step}
        if "kind" not in step_payload and step_def is not None:
            step_payload["kind"] = step_def.kind
        if "workflow" not in step_payload:
            step_payload["workflow"] = {
                "workflow_id": self.definition.workflow_id,
                "task_type": self.definition.task_type,
            }
        self.run_service.record_step(run_id, step_payload, index)
        attempt = step_payload.get("attempt")
        if not isinstance(attempt, int) or attempt < 1:
            attempt = 1
        state_step = WorkflowStepState(
            name=step_name,
            kind=str(step_payload.get("kind") or "workflow_step"),
            status=str(step_payload.get("status") or "completed"),
            attempt=attempt,
            input=step_payload.get("input"),
            output=step_payload.get("output") if "output" in step_payload else step_payload,
            error=step_payload.get("errors") or step_payload.get("error"),
        )
        state_step.complete(
            status=str(step_payload.get("status") or "completed"),
            output=step_payload.get("output") if "output" in step_payload else step_payload,
            error=step_payload.get("errors") or step_payload.get("error"),
        )
        self._ensure_state(run_id)
        if self.state is not None:
            self.state.add_step(state_step)
        self._checkpoint(step_name)

    def record_artifact(self, run_id: str, artifact: dict[str, Any], index: int) -> None:
        self.run_service.record_artifact(run_id, artifact, index)

    def record_hqs(self, run_id: str, scope: str, report: dict[str, Any]) -> None:
        self.run_service.record_hqs(run_id, scope, report)

    def record_tool_call(self, run_id: str, tool_call: dict[str, Any], index: int) -> None:
        self.run_service.record_tool_call(run_id, tool_call, index)

    def record_tool_call_event(
        self,
        run_id: str,
        tool_name: str,
        status: str,
        arguments: dict[str, Any],
        step_id: str | None = None,
        result: dict[str, Any] | None = None,
        errors: Any | None = None,
        started_at: str | None = None,
        completed_at: str | None = None,
        tool_call_id: str | None = None,
    ) -> None:
        self.run_service.record_tool_call_event(
            run_id=run_id,
            tool_name=tool_name,
            status=status,
            arguments=arguments,
            step_id=step_id,
            result=result,
            errors=errors,
            started_at=started_at,
            completed_at=completed_at,
            tool_call_id=tool_call_id,
        )

    def record_workflow_checkpoint(
        self,
        run_id: str,
        workflow_id: str,
        state: dict[str, Any],
        step_name: str | None = None,
        checkpoint_id: str | None = None,
        created_at: str | None = None,
    ) -> None:
        self.run_service.record_workflow_checkpoint(
            run_id=run_id,
            workflow_id=workflow_id,
            state=state,
            step_name=step_name,
            checkpoint_id=checkpoint_id,
            created_at=created_at,
        )

    def run_detail(self, run_id: str) -> dict[str, Any] | None:
        return self.run_service.run_detail(run_id)

    def _ensure_state(self, run_id: str) -> None:
        if self.state is not None:
            return
        run = self.run_service.repository.get_run(run_id)
        self.state = WorkflowRunState(
            run_id=run_id,
            workflow_id=self.definition.workflow_id,
            task_type=self.definition.task_type,
            status=run.status if run else "running",
            started_at=run.created_at if run else "",
            metadata={"workflow": self.definition.to_dict()},
        )

    def _update_state(self, run_id: str, status: str, metadata: dict[str, Any] | None = None) -> None:
        self._ensure_state(run_id)
        if self.state is None:
            return
        self.state.status = status
        if metadata:
            self.state.metadata.update(metadata)

    def _finish_state(self, status: str) -> None:
        if self.state is not None:
            self.state.finish(status)

    def _checkpoint(self, step_name: str | None) -> None:
        if self.state is None:
            return
        self.checkpoints.save(
            run_id=self.state.run_id,
            workflow_id=self.definition.workflow_id,
            step_name=step_name,
            state=self.state.to_dict(),
        )

    def _with_workflow_output(self, output_data: dict[str, Any] | None) -> dict[str, Any] | None:
        if output_data is None:
            return None
        payload = {**(output_data or {})}
        payload.setdefault("workflow", self.definition.to_dict())
        return payload

    def _record_execution_result(
        self,
        run_id: str,
        step: WorkflowStepDefinition,
        step_index: int,
        attempt: int,
        input_data: dict[str, Any],
        shared_state: dict[str, Any],
        result: WorkflowStepResult,
    ) -> None:
        self.record_step(
            run_id,
            {
                "step_id": f"step_{step_index:03d}_attempt_{attempt:02d}",
                "name": step.name,
                "kind": step.kind,
                "status": result.status,
                "attempt": attempt,
                "input": {
                    "workflow_input": input_data,
                    "state": shared_state,
                    "attempt": attempt,
                },
                "output": result.output,
                "errors": result.errors,
                "workflow": {
                    "workflow_id": self.definition.workflow_id,
                    "task_type": self.definition.task_type,
                },
            },
            step_index,
        )

    def _normalize_step_result(self, raw_result: WorkflowStepResult | dict[str, Any] | None) -> WorkflowStepResult:
        if isinstance(raw_result, WorkflowStepResult):
            return raw_result
        if raw_result is None:
            return WorkflowStepResult()
        if not isinstance(raw_result, dict):
            return WorkflowStepResult(output={"value": raw_result})

        output = raw_result.get("output")
        if output is None:
            output = {
                key: value
                for key, value in raw_result.items()
                if key
                not in {
                    "status",
                    "artifacts",
                    "hqs_reports",
                    "tool_calls",
                    "errors",
                    "state_updates",
                    "stop",
                }
            }
        if not isinstance(output, dict):
            output = {"value": output}

        artifacts = raw_result.get("artifacts")
        hqs_reports = raw_result.get("hqs_reports")
        tool_calls = raw_result.get("tool_calls")
        errors = raw_result.get("errors")
        state_updates = raw_result.get("state_updates")
        return WorkflowStepResult(
            status=str(raw_result.get("status") or "completed"),
            output=output,
            artifacts=artifacts if isinstance(artifacts, list) else [],
            hqs_reports=hqs_reports if isinstance(hqs_reports, dict) else {},
            tool_calls=tool_calls if isinstance(tool_calls, list) else [],
            errors=errors if isinstance(errors, list) else [],
            state_updates=state_updates if isinstance(state_updates, dict) else {},
            stop=bool(raw_result.get("stop")),
        )

    def _max_attempts_for_step(self, step: WorkflowStepDefinition) -> int:
        policy = {**self.definition.retry_policy, **getattr(step, "retry_policy", {})}
        raw_max_attempts = policy.get("max_attempts") or policy.get("attempts")
        if isinstance(raw_max_attempts, int) and raw_max_attempts > 0:
            return raw_max_attempts
        raw_max_retries = policy.get("max_retries")
        if isinstance(raw_max_retries, int) and raw_max_retries >= 0:
            return raw_max_retries + 1
        return 1
