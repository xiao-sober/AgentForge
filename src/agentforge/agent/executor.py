from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from agentforge.agent.intent_parser import Intent
from agentforge.agent.planner import AgentPlan, PlanStep
from agentforge.agent.skill_selector import SkillCandidate
from agentforge.common.llm_client import LLMClient
from agentforge.common.trace import utc_now_iso
from agentforge.skill_evolver.skill_runner import SkillRunResult, run_skill
from agentforge.skill_generator.generator import GeneratedSkill, generate_skill_from_input


COMPLETED_STEP_STATUSES = {"completed", "completed_with_warnings"}
TERMINAL_STEP_STATUSES = {*COMPLETED_STEP_STATUSES, "failed", "skipped"}


@dataclass
class PlanExecutionState:
    action: str
    status: str = "pending"
    current_step_id: str | None = None
    step_statuses: dict[str, str] = field(default_factory=dict)
    completed_steps: list[str] = field(default_factory=list)
    failed_steps: list[str] = field(default_factory=list)
    skipped_steps: list[str] = field(default_factory=list)
    transitions: list[dict[str, Any]] = field(default_factory=list)

    @classmethod
    def from_plan(cls, plan: AgentPlan) -> "PlanExecutionState":
        return cls(
            action=plan.action,
            step_statuses={
                step.step_id or step.name: step.status
                for step in plan.steps
                if step.tool_name == "execute_plan"
            },
        )

    def start(self) -> None:
        self.status = "running"
        self.transitions.append(
            {
                "created_at": utc_now_iso(),
                "event": "plan_started",
                "status": self.status,
                "action": self.action,
            }
        )

    def transition(
        self,
        step: PlanStep,
        status: str,
        reason: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        step_id = step.step_id or step.name
        previous = self.step_statuses.get(step_id, step.status)
        self.current_step_id = step_id if status == "running" else None
        self.step_statuses[step_id] = status
        if status in COMPLETED_STEP_STATUSES and step_id not in self.completed_steps:
            self.completed_steps.append(step_id)
        if status == "failed" and step_id not in self.failed_steps:
            self.failed_steps.append(step_id)
        if status == "skipped" and step_id not in self.skipped_steps:
            self.skipped_steps.append(step_id)
        self.transitions.append(
            {
                "created_at": utc_now_iso(),
                "event": "step_transition",
                "plan_step_id": step_id,
                "plan_step_name": step.name,
                "from_status": previous,
                "to_status": status,
                "reason": reason,
                "details": details or {},
            }
        )

    def finish(self, status: str, reason: str) -> None:
        self.current_step_id = None
        self.status = status
        self.transitions.append(
            {
                "created_at": utc_now_iso(),
                "event": "plan_finished",
                "status": status,
                "reason": reason,
            }
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "status": self.status,
            "current_step_id": self.current_step_id,
            "step_statuses": self.step_statuses,
            "completed_steps": self.completed_steps,
            "failed_steps": self.failed_steps,
            "skipped_steps": self.skipped_steps,
            "transitions": self.transitions,
        }


@dataclass(frozen=True)
class ExecutionResult:
    action: str
    generated_skill: GeneratedSkill | None
    selected_skill: SkillCandidate | None
    run_result: SkillRunResult | None
    output_text: str
    artifacts: list[dict[str, str]]
    errors: list[dict[str, Any]]
    plan_step_results: list[dict[str, Any]] = field(default_factory=list)
    run_results: list[SkillRunResult] = field(default_factory=list)
    execution_state: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "generated_skill_path": str(self.generated_skill.skill_path) if self.generated_skill else None,
            "selected_skill": self.selected_skill.to_dict() if self.selected_skill else None,
            "run_result": self.run_result.to_dict() if self.run_result else None,
            "run_results": [run_result.to_dict() for run_result in self.run_results],
            "output_text": self.output_text,
            "artifacts": self.artifacts,
            "errors": self.errors,
            "plan_step_results": self.plan_step_results,
            "execution_state": self.execution_state,
        }


class PlanExecutor:
    def __init__(
        self,
        plan: AgentPlan,
        intent: Intent,
        selected_skill: SkillCandidate | None,
        project_root: Path | str = ".",
        llm_client: LLMClient | None = None,
    ) -> None:
        self.plan = plan
        self.intent = intent
        self.root = Path(project_root).resolve()
        self.llm_client = llm_client
        self.generated_skill: GeneratedSkill | None = None
        self.skill_to_run = selected_skill
        self.artifacts: list[dict[str, str]] = []
        self.errors: list[dict[str, Any]] = []
        self.plan_step_results: list[dict[str, Any]] = []
        self.run_results: list[SkillRunResult] = []
        self.state = PlanExecutionState.from_plan(plan)

    def execute(self) -> ExecutionResult:
        if self.plan.action == "direct_response":
            self.state.finish("skipped", "direct_response_has_no_execution_steps")
            return self._result(output_text="")

        self.state.start()
        executable_steps = [step for step in self.plan.steps if step.tool_name == "execute_plan"]
        executed_count = 0
        while executed_count < max(self.plan.max_steps, len(executable_steps)):
            changed = self._skip_steps_with_failed_dependencies(executable_steps)
            ready = self._ready_steps(executable_steps)
            if not ready:
                if not changed:
                    break
                continue

            step = ready[0]
            self._execute_step(step)
            executed_count += 1

            if self._required_step_failed(step):
                self._skip_steps_with_failed_dependencies(executable_steps)
                break

        finish_status, reason = self._finish_status(executable_steps)
        self.state.finish(finish_status, reason)
        return self._result(output_text=_execution_output_text(self.run_results))

    def _execute_step(self, step: PlanStep) -> None:
        self.state.transition(step, "running", "dependencies_satisfied", {"depends_on": step.depends_on})
        if step.name == "generate_skill":
            self._execute_generate_skill(step)
            return
        if step.name.startswith("run_skill"):
            self._execute_run_skill_step(step)
            return
        self._record_step_result(step, "skipped", error=f"Unsupported execute_plan step: {step.name}")
        self.state.transition(step, "skipped", "unsupported_execute_plan_step")

    def _execute_generate_skill(self, step: PlanStep) -> None:
        try:
            generated = generate_skill_from_input(self.intent.query, project_root=self.root, llm_client=self.llm_client)
            self._record_generated_skill(generated, score=5.0, reasons=["generated_for_request"])
            self._record_step_result(
                step,
                "completed",
                artifact_path=_relative_or_absolute(generated.skill_path, self.root),
            )
            self.state.transition(step, "completed", "skill_generated", {"version": generated.version})
            return
        except Exception as exc:
            self.errors.append(
                {
                    "error_type": exc.__class__.__name__,
                    "message": str(exc),
                    "user_message": "Model-backed Skill generation failed.",
                    "recoverable": False,
                }
            )
            self._record_step_result(step, "failed", error=str(exc))
            self.state.transition(step, "failed", "skill_generation_failed", {"error": str(exc)})

    def _execute_run_skill_step(self, step: PlanStep) -> None:
        if not self.skill_to_run:
            error = "No Skill was available to execute."
            self._record_step_result(step, "failed", task_id=_step_task_id(step), error=error)
            self.state.transition(step, "failed", "missing_skill", {"error": error})
            return

        input_text = str(step.tool_input.get("subtask") or self.intent.query).strip()
        try:
            run_result = run_skill(
                self.skill_to_run.skill_path,
                input_text,
                project_root=self.root,
                llm_client=self.llm_client,
            )
            step_status = self._record_run_result(step, run_result)
            self.state.transition(
                step,
                step_status,
                "skill_step_completed_with_warnings" if step_status == "completed_with_warnings" else "skill_step_completed",
                {"task_id": _step_task_id(step)},
            )
            return
        except Exception as exc:
            self.errors.append(
                {
                    "error_type": exc.__class__.__name__,
                    "message": str(exc),
                    "user_message": "Skill execution failed.",
                    "recoverable": False,
                    "plan_step_id": step.step_id,
                }
            )
            self._record_step_result(step, "failed", task_id=_step_task_id(step), error=str(exc))
            self.state.transition(step, "failed", "skill_step_failed", {"error": str(exc)})

    def _record_generated_skill(self, generated: GeneratedSkill, score: float, reasons: list[str]) -> None:
        self.generated_skill = generated
        self.skill_to_run = SkillCandidate(
            skill_slug=generated.requirement.skill_slug,
            version=generated.version,
            skill_path=generated.skill_path,
            title=generated.requirement.skill_name,
            score=score,
            reasons=reasons,
        )
        self.artifacts.append({"type": "skill", "path": _relative_or_absolute(generated.skill_path, self.root)})
        self.artifacts.append({"type": "trace", "path": _relative_or_absolute(generated.trace_path, self.root)})

    def _record_run_result(self, step: PlanStep, run_result: SkillRunResult, note: str | None = None) -> str:
        self.run_results.append(run_result)
        self.artifacts.append({"type": "run_result", "path": _relative_or_absolute(run_result.result_path, self.root)})
        self.artifacts.append({"type": "trace", "path": _relative_or_absolute(run_result.trace_path, self.root)})
        output = run_result.outputs[0] if run_result.outputs else None
        step_status = _run_result_step_status(run_result)
        output_error = output.error if output else None
        if output_error:
            self.errors.append(_task_output_error(step, run_result, output_error))
        self._record_step_result(
            step,
            step_status,
            task_id=_step_task_id(step),
            artifact_path=str(output.output_path) if output and output.output_path else None,
            error=output_error,
            note=note,
        )
        return step_status

    def _record_step_result(
        self,
        step: PlanStep,
        status: str,
        task_id: Any = None,
        artifact_path: str | None = None,
        error: str | None = None,
        note: str | None = None,
    ) -> None:
        self.plan_step_results.append(
            {
                "plan_step_id": step.step_id,
                "plan_step_name": step.name,
                "task_id": task_id,
                "status": status,
                "output_path": artifact_path,
                "error": error,
                "note": note,
            }
        )

    def _ready_steps(self, executable_steps: list[PlanStep]) -> list[PlanStep]:
        ready = []
        for step in executable_steps:
            if self.state.step_statuses.get(step.step_id or step.name) != "pending":
                continue
            if self._dependencies_completed(step):
                ready.append(step)
        return ready

    def _dependencies_completed(self, step: PlanStep) -> bool:
        return all(self.state.step_statuses.get(dep) in COMPLETED_STEP_STATUSES for dep in step.depends_on)

    def _skip_steps_with_failed_dependencies(self, executable_steps: list[PlanStep]) -> bool:
        changed = False
        for step in executable_steps:
            step_id = step.step_id or step.name
            if self.state.step_statuses.get(step_id) != "pending":
                continue
            blocking_deps = [
                dep
                for dep in step.depends_on
                if self.state.step_statuses.get(dep) in {"failed", "skipped"}
            ]
            if not blocking_deps:
                continue
            self._record_step_result(
                step,
                "skipped",
                task_id=_step_task_id(step),
                error=f"Skipped because dependencies did not complete: {', '.join(blocking_deps)}",
            )
            self.state.transition(step, "skipped", "dependency_not_completed", {"blocking_dependencies": blocking_deps})
            changed = True
        return changed

    def _required_step_failed(self, step: PlanStep) -> bool:
        step_id = step.step_id or step.name
        return step.required and self.state.step_statuses.get(step_id) in {"failed", "skipped"}

    def _finish_status(self, executable_steps: list[PlanStep]) -> tuple[str, str]:
        required_failed = [
            step.step_id or step.name
            for step in executable_steps
            if step.required and self.state.step_statuses.get(step.step_id or step.name) in {"failed", "skipped"}
        ]
        if required_failed:
            return "failed", "required_step_failed"
        pending = [
            step.step_id or step.name
            for step in executable_steps
            if self.state.step_statuses.get(step.step_id or step.name) not in TERMINAL_STEP_STATUSES
        ]
        if pending:
            return "blocked", "no_ready_step"
        if any(self.state.step_statuses.get(step.step_id or step.name) == "completed_with_warnings" for step in executable_steps):
            return "completed_with_warnings", "all_executable_steps_completed_with_warnings"
        return "completed", "all_executable_steps_completed"

    def _result(self, output_text: str) -> ExecutionResult:
        return ExecutionResult(
            action=self.plan.action,
            generated_skill=self.generated_skill,
            selected_skill=self.skill_to_run,
            run_result=self.run_results[0] if self.run_results else None,
            run_results=self.run_results,
            output_text=output_text,
            artifacts=self.artifacts,
            errors=self.errors,
            plan_step_results=self.plan_step_results,
            execution_state=self.state.to_dict(),
        )


def execute_plan(
    plan: AgentPlan,
    intent: Intent,
    selected_skill: SkillCandidate | None,
    project_root: Path | str = ".",
    llm_client: LLMClient | None = None,
) -> ExecutionResult:
    return PlanExecutor(
        plan,
        intent,
        selected_skill,
        project_root=project_root,
        llm_client=llm_client,
    ).execute()


def _execution_output_text(run_results: list[SkillRunResult]) -> str:
    outputs = []
    for run_result in run_results:
        outputs.extend(run_result.outputs)
    if not outputs:
        return ""
    if len(outputs) == 1:
        return outputs[0].output
    lines = ["# Multi-Step Skill Output", ""]
    for index, output in enumerate(outputs, start=1):
        lines.extend(
            [
                f"## Step {index}: {output.task_id}",
                "",
                output.output.strip(),
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def _step_task_id(step: PlanStep) -> Any:
    return step.tool_input.get("subtask_index") or step.tool_input.get("task_id") or step.name


def _run_result_step_status(run_result: SkillRunResult) -> str:
    if not any(output.error for output in run_result.outputs):
        return "completed"
    return "completed_with_warnings" if run_result.mode == "model" else "failed"


def _task_output_error(step: PlanStep, run_result: SkillRunResult, message: str) -> dict[str, Any]:
    return {
        "error_type": "SkillTaskOutputError",
        "message": message,
        "user_message": "Skill task produced an error; fallback output was recorded.",
        "recoverable": False,
        "plan_step_id": step.step_id,
        "plan_step_name": step.name,
        "task_id": _step_task_id(step),
        "run_result_path": str(run_result.result_path),
        "trace_path": str(run_result.trace_path),
    }


def _relative_or_absolute(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return str(path)
