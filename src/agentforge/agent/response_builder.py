from __future__ import annotations

from pathlib import Path
from typing import Any

from agentforge.agent.executor import ExecutionResult
from agentforge.agent.intent_parser import Intent
from agentforge.agent.planner import AgentPlan


def build_response(
    intent: Intent,
    plan: AgentPlan,
    execution: ExecutionResult,
    memory_context: dict[str, Any],
    project_root: Path | str = ".",
) -> str:
    root = Path(project_root).resolve()
    if intent.intent_type == "empty":
        return "AgentForge needs a non-empty message before it can run the Agent loop."

    blocking_errors = [error for error in execution.errors if not error.get("recoverable")]
    if blocking_errors and not execution.run_result and not execution.generated_skill:
        return _error_response(intent, plan, execution)

    if plan.action == "reserved_task" and intent.task_type:
        return "\n".join(
            [
                "# AgentForge Response",
                "",
                "## Task Router",
                "",
                f"- Selected task type: {intent.task_type}",
                "- Status: reserved",
                "- This task family is recognized by chat intent routing but does not have an executable handler yet.",
                "",
                "## Next Step",
                "",
                "- Add a Task Router handler before using this task type for execution.",
            ]
        ).rstrip() + "\n"

    if plan.action == "route_task" and execution.task_result:
        return _task_result_response(intent, plan, execution, root)

    if plan.action == "generate_skill" and execution.generated_skill:
        skill_path = _relative_or_absolute(execution.generated_skill.skill_path, root)
        trace_path = _relative_or_absolute(execution.generated_skill.trace_path, root)
        return "\n".join(
            [
                "# AgentForge Response",
                "",
                "## Result",
                "",
                f"- Generated Skill: {skill_path}",
                f"- Skill version: {execution.generated_skill.version}",
                f"- Generation mode: {execution.generated_skill.generation_mode}",
                f"- Trace: {trace_path}",
                *_warning_lines(execution),
                "",
                "## Memory",
                "",
                _memory_line(memory_context),
            ]
        ).rstrip() + "\n"

    if execution.run_result:
        skill_path = _relative_or_absolute(execution.run_result.skill_path, root)
        run_count = len(execution.run_results) if execution.run_results else 1
        run_lines = _run_artifact_lines(execution, root)
        return "\n".join(
            [
                "# AgentForge Response",
                "",
                "## Result",
                "",
                execution.output_text.strip(),
                "",
                "## Agent Artifacts",
                "",
                f"- Selected Skill: {skill_path}",
                f"- Skill runs: {run_count}",
                *run_lines,
                f"- Execution mode: {execution.run_result.mode}",
                *_warning_lines(execution),
                "",
                "## Memory",
                "",
                _memory_line(memory_context),
                "",
                "## Assumptions",
                "",
                "- AgentForge uses local file memory and deterministic execution unless a provider is configured.",
            ]
        ).rstrip() + "\n"

    return "\n".join(
        [
            "# AgentForge Response",
            "",
            "## Result",
            "",
            "AgentForge received the message and completed the local Agent loop. No Skill execution was required.",
            "",
            "## Agent State",
            "",
            f"- Intent: {intent.intent_type}",
            f"- Plan: {plan.action}",
            "- Trace and memory will record this interaction for later inspection.",
        ]
    ).rstrip() + "\n"


def build_reinforcement_recommendation(
    response_hqs: dict[str, Any],
    execution: ExecutionResult,
    threshold: float,
    taskset_path: Path | None = None,
) -> dict[str, Any]:
    scores = response_hqs.get("scores") if isinstance(response_hqs.get("scores"), dict) else {}
    weak_dimensions = [dimension for dimension, score in scores.items() if isinstance(score, (int, float)) and score < 3.0]
    average_score = float(response_hqs.get("average_score", 0.0) or 0.0)
    triggered = average_score < threshold or bool(weak_dimensions)
    recommendation = {
        "triggered": triggered,
        "threshold": threshold,
        "response_hqs": response_hqs,
        "weak_dimensions": weak_dimensions,
        "status": "not_needed",
        "recommendation": "No reinforcement needed.",
        "taskset_path": str(taskset_path) if taskset_path else None,
        "requires_explicit_taskset": True,
    }
    if not recommendation["triggered"]:
        return recommendation

    recommendation["status"] = "ready_with_taskset" if taskset_path else "recommended"
    if taskset_path:
        recommendation["recommendation"] = (
            "Response HQS is below threshold. Run bounded Skill reinforcement with the explicit task set."
        )
    else:
        recommendation["recommendation"] = (
            "Response HQS is below threshold. Record this episode, review weak dimensions, "
            "and run evolve-skill only with an explicit task set and max iteration limit."
        )
    selected_skill = execution.selected_skill.to_dict() if execution.selected_skill else None
    recommendation["selected_skill"] = selected_skill
    return recommendation


def _error_response(intent: Intent, plan: AgentPlan, execution: ExecutionResult) -> str:
    first_error = execution.errors[0]
    return "\n".join(
        [
            "# AgentForge Response",
            "",
            "## Result",
            "",
            "AgentForge could not complete the requested Agent action.",
            "",
            "## Error",
            "",
            f"- Type: {first_error.get('error_type', 'Error')}",
            f"- Message: {first_error.get('user_message') or first_error.get('message', 'Unknown error')}",
            "",
            "## Agent State",
            "",
            f"- Intent: {intent.intent_type}",
            f"- Plan: {plan.action}",
            "- Details were written to the agent_chat trace.",
        ]
    ).rstrip() + "\n"


def _task_result_response(intent: Intent, plan: AgentPlan, execution: ExecutionResult, root: Path) -> str:
    task_result = execution.task_result
    if task_result is None:
        return _error_response(intent, plan, execution)
    trace_line = None
    if task_result.trace_path:
        trace_line = f"- Task trace: {_relative_or_absolute(task_result.trace_path, root)}"
    lines = [
        "# AgentForge Response",
        "",
        "## Task Router",
        "",
        f"- Selected task type: {task_result.task_type}",
        f"- Status: {task_result.status}",
        f"- Task run: {task_result.run_id}",
    ]
    if trace_line:
        lines.append(trace_line)
    if task_result.output:
        lines.extend(["", "## Result", "", execution.output_text.strip() or f"Task Router completed {task_result.task_type}."])
    if task_result.artifacts:
        lines.extend(["", "## Artifacts", ""])
        for artifact in task_result.artifacts[:5]:
            if isinstance(artifact, dict):
                lines.append(f"- {artifact.get('type')}: {artifact.get('path')}")
    return "\n".join(lines).rstrip() + "\n"


def _warning_lines(execution: ExecutionResult) -> list[str]:
    recoverable = [error for error in execution.errors if error.get("recoverable")]
    if not recoverable:
        return []
    lines = ["", "## Warnings", ""]
    for error in recoverable[:3]:
        lines.append(f"- {error.get('user_message') or error.get('message')}")
    return lines


def _memory_line(memory_context: dict[str, Any]) -> str:
    episodes = len(memory_context.get("episodes") or [])
    semantic = len(memory_context.get("semantic_memory") or [])
    return f"- Retrieved context: {episodes} episode memories and {semantic} semantic memories."


def _run_artifact_lines(execution: ExecutionResult, root: Path) -> list[str]:
    run_results = execution.run_results or ([execution.run_result] if execution.run_result else [])
    if len(run_results) <= 1:
        run_result = run_results[0]
        return [
            f"- Run directory: {_relative_or_absolute(run_result.run_dir, root)}",
            f"- Execution trace: {_relative_or_absolute(run_result.trace_path, root)}",
        ]
    return [
        f"- Run {index}: {_relative_or_absolute(run_result.run_dir, root)}"
        for index, run_result in enumerate(run_results, start=1)
    ]


def _relative_or_absolute(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return str(path)
