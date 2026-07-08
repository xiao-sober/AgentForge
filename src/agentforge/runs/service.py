from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import uuid4

from agentforge.common.trace import utc_now_iso
from agentforge.runs.repository import RunRepository


COMPLETED_STATUSES = {"completed", "failed", "cancelled"}


class RunService:
    def __init__(self, project_root: Path | str = ".", db_path: Path | str | None = None) -> None:
        self.project_root = Path(project_root).resolve()
        self.repository = RunRepository(project_root=self.project_root, db_path=db_path)

    def ensure_initialized(self) -> Path:
        return self.repository.initialize()

    def start_run(
        self,
        task_type: str,
        title: str,
        input_data: dict[str, Any],
        run_id: str | None = None,
        created_at: str | None = None,
        status: str = "running",
    ) -> str:
        resolved_run_id = run_id or f"run_{uuid4().hex}"
        now = created_at or utc_now_iso()
        self.repository.upsert_run(
            run_id=resolved_run_id,
            task_type=task_type,
            title=title,
            status=status,
            input_data=input_data,
            output_data=None,
            trace_path=None,
            created_at=now,
            updated_at=now,
            completed_at=None,
        )
        return resolved_run_id

    def update_run(
        self,
        run_id: str,
        status: str,
        output_data: dict[str, Any] | None = None,
        trace_path: Path | str | None = None,
        completed: bool = False,
    ) -> None:
        self.repository.update_run_status(
            run_id=run_id,
            status=status,
            output_data=output_data,
            trace_path=_relative_or_absolute(Path(trace_path), self.project_root) if trace_path else None,
            completed_at=utc_now_iso() if completed else None,
        )

    def complete_run(
        self,
        run_id: str,
        output_data: dict[str, Any] | None = None,
        trace_path: Path | str | None = None,
        status: str = "completed",
    ) -> None:
        self.update_run(run_id, status=status, output_data=output_data, trace_path=trace_path, completed=True)

    def fail_run(
        self,
        run_id: str,
        error: Any,
        output_data: dict[str, Any] | None = None,
        trace_path: Path | str | None = None,
    ) -> None:
        payload = {**(output_data or {}), "error": error}
        self.update_run(run_id, status="failed", output_data=payload, trace_path=trace_path, completed=True)

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
        now = utc_now_iso()
        resolved_run_id = run_id or f"run_{uuid4().hex}"
        self.repository.upsert_run(
            run_id=resolved_run_id,
            task_type=task_type,
            title=title,
            status=status,
            input_data=input_data,
            output_data=output_data,
            trace_path=_relative_or_absolute(Path(trace_path), self.project_root) if trace_path else None,
            created_at=created_at or now,
            updated_at=now,
            completed_at=now if status in COMPLETED_STATUSES else None,
        )

        for index, step in enumerate(steps or [], start=1):
            self.record_step(resolved_run_id, step, index)
        for index, artifact in enumerate(artifacts or [], start=1):
            self.record_artifact(resolved_run_id, artifact, index)
        for scope, report in (hqs_reports or {}).items():
            self.record_hqs(resolved_run_id, scope, report)
        for index, tool_call in enumerate(tool_calls or [], start=1):
            self.record_tool_call(resolved_run_id, tool_call, index)
        return resolved_run_id

    def record_step(self, run_id: str, step: dict[str, Any], index: int) -> None:
        raw_step_id = str(step.get("step_id") or f"step_{index:03d}")
        step_id = raw_step_id if raw_step_id.startswith(f"{run_id}_") else f"{run_id}_{raw_step_id}"
        errors = step.get("errors")
        if errors is None and step.get("error"):
            errors = step.get("error")
        self.repository.add_run_step(
            step_id=step_id,
            run_id=run_id,
            name=str(step.get("name") or step.get("tool_name") or f"step_{index}"),
            kind=str(step.get("kind") or step.get("phase") or "step"),
            status=str(step.get("status") or "completed"),
            input_data=step.get("input"),
            output_data=step.get("output") if "output" in step else step,
            error_data=errors,
            started_at=_optional_string(step.get("started_at")),
            completed_at=_optional_string(step.get("completed_at")),
        )

    def record_artifact(self, run_id: str, artifact: dict[str, Any], index: int) -> None:
        self.repository.add_artifact(
            artifact_id=str(artifact.get("artifact_id") or f"{run_id}_artifact_{index:03d}"),
            run_id=run_id,
            artifact_type=str(artifact.get("type") or "artifact"),
            path=_optional_string(artifact.get("path") or artifact.get("relative_path")),
            content_type=_optional_string(artifact.get("content_type")),
            metadata={key: value for key, value in artifact.items() if key not in {"artifact_id", "type", "path", "relative_path", "content_type"}},
        )

    def record_hqs(self, run_id: str, scope: str, report: dict[str, Any]) -> None:
        average = report.get("average_score")
        if not isinstance(average, (int, float)):
            return
        self.repository.add_hqs_report(
            hqs_id=f"{run_id}_{scope}_hqs",
            run_id=run_id,
            scope=scope,
            average_score=float(average),
            report=report,
        )

    def record_tool_call(self, run_id: str, tool_call: dict[str, Any], index: int) -> None:
        tool_name = tool_call.get("tool_name") or tool_call.get("name")
        if not tool_name:
            return
        self.repository.add_tool_call(
            tool_call_id=str(tool_call.get("tool_call_id") or f"{run_id}_tool_{index:03d}"),
            run_id=run_id,
            step_id=_optional_string(tool_call.get("step_id")),
            tool_name=str(tool_name),
            status=str(tool_call.get("status") or "completed"),
            arguments=tool_call.get("arguments") if isinstance(tool_call.get("arguments"), dict) else {},
            result=tool_call.get("tool_result") if isinstance(tool_call.get("tool_result"), dict) else None,
            error=tool_call.get("errors"),
            started_at=_optional_string(tool_call.get("started_at")),
            completed_at=_optional_string(tool_call.get("completed_at")),
        )

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
        self.repository.add_tool_call(
            tool_call_id=tool_call_id or f"{run_id}_tool_{uuid4().hex[:12]}",
            run_id=run_id,
            step_id=step_id,
            tool_name=tool_name,
            status=status,
            arguments=arguments,
            result=result,
            error=errors,
            started_at=started_at,
            completed_at=completed_at,
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
        self.repository.add_workflow_checkpoint(
            checkpoint_id=checkpoint_id or f"{run_id}_checkpoint_{uuid4().hex[:12]}",
            run_id=run_id,
            workflow_id=workflow_id,
            step_name=step_name,
            state=state,
            created_at=created_at,
        )

    def run_detail(self, run_id: str) -> dict[str, Any] | None:
        run = self.repository.get_run(run_id)
        if run is None:
            return None
        return {
            **run.to_dict(),
            "steps": [step.to_dict() for step in self.repository.list_run_steps(run_id)],
            "artifacts": [artifact.to_dict() for artifact in self.repository.list_artifacts(run_id)],
            "tool_calls": [tool_call.to_dict() for tool_call in self.repository.list_tool_calls(run_id)],
            "hqs_reports": [hqs.to_dict() for hqs in self.repository.list_hqs_reports(run_id)],
            "workflow_checkpoints": [
                checkpoint.to_dict() for checkpoint in self.repository.list_workflow_checkpoints(run_id)
            ],
        }


def _optional_string(value: Any) -> str | None:
    return str(value) if isinstance(value, str) and value else None


def _relative_or_absolute(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root).as_posix()
    except ValueError:
        return str(path)
