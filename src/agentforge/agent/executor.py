from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from agentforge.agent.intent_parser import Intent
from agentforge.agent.planner import AgentPlan
from agentforge.agent.skill_selector import SkillCandidate
from agentforge.common.llm_client import LLMClient
from agentforge.skill_evolver.skill_runner import SkillRunResult, run_skill
from agentforge.skill_evolver.skill_runner import run_skill_on_taskset
from agentforge.skill_evolver.task_loader import Task, TaskSet
from agentforge.skill_generator.generator import GeneratedSkill, generate_skill_from_input


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

    def to_dict(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "generated_skill_path": str(self.generated_skill.skill_path) if self.generated_skill else None,
            "selected_skill": self.selected_skill.to_dict() if self.selected_skill else None,
            "run_result": self.run_result.to_dict() if self.run_result else None,
            "output_text": self.output_text,
            "artifacts": self.artifacts,
            "errors": self.errors,
            "plan_step_results": self.plan_step_results,
        }


def execute_plan(
    plan: AgentPlan,
    intent: Intent,
    selected_skill: SkillCandidate | None,
    project_root: Path | str = ".",
    llm_client: LLMClient | None = None,
) -> ExecutionResult:
    root = Path(project_root).resolve()
    artifacts: list[dict[str, str]] = []
    errors: list[dict[str, Any]] = []
    plan_step_results: list[dict[str, Any]] = []

    if plan.action == "direct_response":
        return ExecutionResult(
            action=plan.action,
            generated_skill=None,
            selected_skill=selected_skill,
            run_result=None,
            output_text="",
            artifacts=[],
            errors=[],
            plan_step_results=[],
        )

    generated_skill = None
    skill_to_run = selected_skill

    if plan.action in {"generate_skill", "generate_and_run_skill"}:
        try:
            generated_skill = generate_skill_from_input(intent.query, project_root=root, llm_client=llm_client)
            artifacts.append({"type": "skill", "path": _relative_or_absolute(generated_skill.skill_path, root)})
            artifacts.append({"type": "trace", "path": _relative_or_absolute(generated_skill.trace_path, root)})
            skill_to_run = SkillCandidate(
                skill_slug=generated_skill.requirement.skill_slug,
                version=generated_skill.version,
                skill_path=generated_skill.skill_path,
                title=generated_skill.requirement.skill_name,
                score=5.0,
                reasons=["generated_for_request"],
            )
        except Exception as exc:
            errors.append(
                {
                    "error_type": exc.__class__.__name__,
                    "message": str(exc),
                    "user_message": "Model-backed Skill generation failed.",
                    "recoverable": llm_client is not None,
                }
            )
            if llm_client is None:
                return ExecutionResult(
                    action=plan.action,
                    generated_skill=None,
                    selected_skill=selected_skill,
                    run_result=None,
                    output_text="",
                    artifacts=artifacts,
                    errors=errors,
                    plan_step_results=plan_step_results,
                )
            try:
                generated_skill = generate_skill_from_input(intent.query, project_root=root, llm_client=None)
                artifacts.append({"type": "skill", "path": _relative_or_absolute(generated_skill.skill_path, root)})
                artifacts.append({"type": "trace", "path": _relative_or_absolute(generated_skill.trace_path, root)})
                skill_to_run = SkillCandidate(
                    skill_slug=generated_skill.requirement.skill_slug,
                    version=generated_skill.version,
                    skill_path=generated_skill.skill_path,
                    title=generated_skill.requirement.skill_name,
                    score=4.0,
                    reasons=["local_fallback_after_provider_error"],
                )
                errors.append(
                    {
                        "error_type": "ProviderFallback",
                        "message": "Used deterministic local Skill generation after provider failure.",
                        "user_message": "Provider failed, so AgentForge used local fallback generation.",
                        "recoverable": True,
                    }
                )
            except Exception as fallback_exc:
                errors.append(
                    {
                        "error_type": fallback_exc.__class__.__name__,
                        "message": str(fallback_exc),
                        "user_message": "Local fallback Skill generation also failed.",
                        "recoverable": False,
                    }
                )
                return ExecutionResult(
                    action=plan.action,
                    generated_skill=None,
                    selected_skill=selected_skill,
                    run_result=None,
                    output_text="",
                    artifacts=artifacts,
                    errors=errors,
                    plan_step_results=plan_step_results,
                )

    if plan.action == "generate_skill":
        return ExecutionResult(
            action=plan.action,
            generated_skill=generated_skill,
            selected_skill=skill_to_run,
            run_result=None,
            output_text="",
            artifacts=artifacts,
            errors=errors,
            plan_step_results=plan_step_results,
        )

    if plan.action in {"run_skill", "generate_and_run_skill"} and skill_to_run:
        try:
            run_result = _run_skill_for_plan(skill_to_run.skill_path, plan, intent.query, project_root=root, llm_client=llm_client)
            artifacts.append({"type": "run_result", "path": _relative_or_absolute(run_result.result_path, root)})
            artifacts.append({"type": "trace", "path": _relative_or_absolute(run_result.trace_path, root)})
            output_text = _execution_output_text(run_result)
            plan_step_results.extend(_plan_step_results(plan, run_result))
            return ExecutionResult(
                action=plan.action,
                generated_skill=generated_skill,
                selected_skill=skill_to_run,
                run_result=run_result,
                output_text=output_text,
                artifacts=artifacts,
                errors=errors,
                plan_step_results=plan_step_results,
            )
        except Exception as exc:
            errors.append(
                {
                    "error_type": exc.__class__.__name__,
                    "message": str(exc),
                    "user_message": "Skill execution failed.",
                    "recoverable": llm_client is not None,
                }
            )
            if llm_client is not None:
                try:
                    run_result = _run_skill_for_plan(skill_to_run.skill_path, plan, intent.query, project_root=root, llm_client=None)
                    artifacts.append({"type": "run_result", "path": _relative_or_absolute(run_result.result_path, root)})
                    artifacts.append({"type": "trace", "path": _relative_or_absolute(run_result.trace_path, root)})
                    output_text = _execution_output_text(run_result)
                    plan_step_results.extend(_plan_step_results(plan, run_result))
                    errors.append(
                        {
                            "error_type": "ProviderFallback",
                            "message": "Used deterministic local Skill execution after provider failure.",
                            "user_message": "Provider failed, so AgentForge used local fallback execution.",
                            "recoverable": True,
                        }
                    )
                    return ExecutionResult(
                        action=plan.action,
                        generated_skill=generated_skill,
                        selected_skill=skill_to_run,
                        run_result=run_result,
                        output_text=output_text,
                        artifacts=artifacts,
                        errors=errors,
                        plan_step_results=plan_step_results,
                    )
                except Exception as fallback_exc:
                    errors.append(
                        {
                            "error_type": fallback_exc.__class__.__name__,
                            "message": str(fallback_exc),
                            "user_message": "Local fallback Skill execution also failed.",
                            "recoverable": False,
                        }
                    )

    return ExecutionResult(
        action=plan.action,
        generated_skill=generated_skill,
        selected_skill=skill_to_run,
        run_result=None,
        output_text="",
        artifacts=artifacts,
        errors=errors,
        plan_step_results=plan_step_results,
    )


def _run_skill_for_plan(
    skill_path: Path,
    plan: AgentPlan,
    query: str,
    project_root: Path,
    llm_client: LLMClient | None,
) -> SkillRunResult:
    subtasks = _planned_subtasks(plan, query)
    if len(subtasks) <= 1:
        return run_skill(skill_path, subtasks[0] if subtasks else query, project_root=project_root, llm_client=llm_client)
    taskset = TaskSet(
        name="agent_plan_subtasks",
        description="Planner v2 decomposed taskset for a single Agent chat run.",
        tasks=[
            Task(
                task_id=f"plan_step_{index:02d}",
                input=subtask,
                criteria=["complete the subtask", "return structured output", "avoid inventing missing context"],
                metadata={"plan_complexity": plan.complexity, "subtask_index": index},
            )
            for index, subtask in enumerate(subtasks, start=1)
        ],
    )
    return run_skill_on_taskset(skill_path, taskset, project_root=project_root, llm_client=llm_client)


def _planned_subtasks(plan: AgentPlan, query: str) -> list[str]:
    subtasks = [subtask for subtask in plan.subtasks if subtask.strip()]
    return subtasks or [query]


def _execution_output_text(run_result: SkillRunResult) -> str:
    if len(run_result.outputs) <= 1:
        return run_result.outputs[0].output if run_result.outputs else ""
    lines = ["# Multi-Step Skill Output", ""]
    for index, output in enumerate(run_result.outputs, start=1):
        lines.extend(
            [
                f"## Step {index}: {output.task_id}",
                "",
                output.output.strip(),
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def _plan_step_results(plan: AgentPlan, run_result: SkillRunResult) -> list[dict[str, Any]]:
    executable_steps = [step for step in plan.steps if step.tool_name == "execute_plan" and step.name.startswith("run_skill")]
    results: list[dict[str, Any]] = []
    for index, output in enumerate(run_result.outputs):
        step = executable_steps[index] if index < len(executable_steps) else None
        results.append(
            {
                "plan_step_id": step.step_id if step else None,
                "plan_step_name": step.name if step else None,
                "task_id": output.task_id,
                "status": "failed" if output.error else "completed",
                "output_path": str(output.output_path) if output.output_path else None,
                "error": output.error,
            }
        )
    return results


def _relative_or_absolute(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return str(path)
