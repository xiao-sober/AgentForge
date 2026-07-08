from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from agentforge.agent.intent_parser import Intent
from agentforge.agent.skill_selector import SkillCandidate


@dataclass(frozen=True)
class StopCondition:
    name: str
    value: Any
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "value": self.value, "reason": self.reason}


@dataclass(frozen=True)
class PlanStep:
    name: str
    action: str
    status: str = "pending"
    tool_name: str | None = None
    step_id: str | None = None
    depends_on: list[str] = field(default_factory=list)
    tool_input: dict[str, Any] = field(default_factory=dict)
    expected_output: str | None = None
    required: bool = True
    max_retries: int = 0
    permission_required: str = "execute"

    def to_dict(self) -> dict[str, Any]:
        return {
            "step_id": self.step_id,
            "name": self.name,
            "action": self.action,
            "status": self.status,
            "tool_name": self.tool_name,
            "depends_on": self.depends_on,
            "tool_input": self.tool_input,
            "expected_output": self.expected_output,
            "required": self.required,
            "max_retries": self.max_retries,
            "permission_required": self.permission_required,
        }


@dataclass(frozen=True)
class AgentPlan:
    action: str
    steps: list[PlanStep]
    rationale: str
    objective: str = ""
    complexity: str = "simple"
    subtasks: list[str] = field(default_factory=list)
    stop_conditions: list[StopCondition] = field(default_factory=list)
    max_steps: int = 8

    def to_dict(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "objective": self.objective,
            "complexity": self.complexity,
            "subtasks": self.subtasks,
            "steps": [step.to_dict() for step in self.steps],
            "rationale": self.rationale,
            "stop_conditions": [condition.to_dict() for condition in self.stop_conditions],
            "max_steps": self.max_steps,
        }


def build_plan(intent: Intent, selected_skill: SkillCandidate | None) -> AgentPlan:
    subtasks = _decompose_task(intent.query)
    complexity = "complex" if len(subtasks) > 1 else "simple"
    objective = _objective_for_intent(intent)
    stop_conditions = _default_stop_conditions(intent, complexity)

    if intent.intent_type == "empty":
        return AgentPlan(
            action="direct_response",
            objective="Return a clear validation error.",
            complexity="simple",
            subtasks=[],
            stop_conditions=stop_conditions,
            steps=[
                _step(
                    "respond_empty",
                    "build a clear validation error",
                    "build_response",
                    expected_output="A user-facing validation response.",
                    permission_required="write",
                )
            ],
            rationale="The input is empty.",
        )
    if intent.task_type in {"trace_diagnosis", "skill_evolve", "code_analysis", "document_analysis", "data_analysis"}:
        return AgentPlan(
            action="route_task",
            objective=objective,
            complexity="simple",
            subtasks=[intent.query],
            stop_conditions=stop_conditions,
            steps=[
                _step(
                    f"route_{intent.task_type}",
                    f"dispatch {intent.task_type} through the Task Router",
                    "execute_plan",
                    tool_input={
                        "task_type": intent.task_type,
                        "input": intent.task_input,
                        "options": intent.task_options,
                    },
                    expected_output="Task Router execution result.",
                ),
                _step(
                    "build_response",
                    "summarize task router output",
                    "build_response",
                    depends_on=["step_001"],
                    expected_output="Readable Agent response.",
                    permission_required="write",
                    step_number=2,
                ),
            ],
            rationale=f"The parsed intent maps to executable task type {intent.task_type}.",
        )
    if intent.intent_type == "generate_skill":
        return AgentPlan(
            action="generate_skill",
            objective=objective,
            complexity=complexity,
            subtasks=subtasks,
            stop_conditions=stop_conditions,
            steps=[
                _step(
                    "generate_skill",
                    "call Phase 1 local/model Skill generation",
                    "execute_plan",
                    tool_input={"requirement": intent.query},
                    expected_output="A validated versioned SKILL.md path.",
                ),
                _step(
                    "record_memory",
                    "save generated Skill metadata",
                    "update_semantic_memory",
                    depends_on=["step_001"],
                    expected_output="Semantic Skill memory updated.",
                    permission_required="write",
                    step_number=2,
                ),
            ],
            rationale="The user explicitly asked to create a Skill.",
        )
    if intent.requires_skill and selected_skill:
        execution_steps = _skill_execution_steps(subtasks or [intent.query], selected_skill, original_query=intent.query)
        return AgentPlan(
            action="run_skill",
            objective=objective,
            complexity=complexity,
            subtasks=subtasks,
            stop_conditions=stop_conditions,
            steps=execution_steps
            + [
                _step(
                    "observe_execution",
                    "inspect Skill execution results and errors",
                    "observe_execution",
                    depends_on=[execution_steps[-1].step_id or f"step_{len(execution_steps):03d}"],
                    expected_output="Execution observation summary.",
                    permission_required="read",
                    step_number=len(execution_steps) + 1,
                ),
                _step(
                    "build_response",
                    "summarize output and artifacts",
                    "build_response",
                    depends_on=[f"step_{len(execution_steps) + 1:03d}"],
                    expected_output="Readable Agent response.",
                    permission_required="write",
                    step_number=len(execution_steps) + 2,
                ),
            ],
            rationale="A matching versioned Skill is available.",
        )
    if intent.requires_skill:
        generated_steps = _skill_execution_steps(subtasks or [intent.query], None, start_index=2, original_query=intent.query)
        return AgentPlan(
            action="generate_and_run_skill",
            objective=objective,
            complexity=complexity,
            subtasks=subtasks,
            stop_conditions=stop_conditions,
            steps=[
                _step(
                    "generate_skill",
                    "create a local Skill because no match exists",
                    "execute_plan",
                    tool_input={"requirement": intent.query},
                    expected_output="A generated Skill candidate.",
                ),
                *[
                    PlanStep(
                        name=step.name,
                        action=step.action,
                        status=step.status,
                        tool_name=step.tool_name,
                        step_id=step.step_id,
                        depends_on=["step_001"] if index == 0 else step.depends_on,
                        tool_input=step.tool_input,
                        expected_output=step.expected_output,
                        required=step.required,
                        max_retries=step.max_retries,
                        permission_required=step.permission_required,
                    )
                    for index, step in enumerate(generated_steps)
                ],
                _step(
                    "record_memory",
                    "save generated Skill metadata",
                    "update_semantic_memory",
                    depends_on=[generated_steps[-1].step_id or f"step_{len(generated_steps) + 1:03d}"],
                    expected_output="Semantic Skill memory updated.",
                    permission_required="write",
                    step_number=len(generated_steps) + 2,
                ),
            ],
            rationale="The task needs a Skill and no existing match was found.",
        )
    return AgentPlan(
        action="direct_response",
        objective=objective,
        complexity=complexity,
        subtasks=subtasks,
        stop_conditions=stop_conditions,
        steps=[
            _step(
                "respond",
                "return a local AgentForge response",
                "build_response",
                tool_input={"message": intent.query},
                expected_output="Readable Agent response.",
                permission_required="write",
            )
        ],
        rationale="No Skill execution is required for this message.",
    )


def _skill_execution_steps(
    subtasks: list[str],
    selected_skill: SkillCandidate | None,
    start_index: int = 1,
    original_query: str = "",
) -> list[PlanStep]:
    original = original_query.strip() or (subtasks[0] if subtasks else "")
    if len(subtasks) <= 1:
        return [
            _step(
                "run_skill",
                "execute the selected Skill through Phase 2 runner",
                "execute_plan",
                tool_input=_skill_tool_input(
                    subtasks[0] if subtasks else "",
                    selected_skill,
                    1,
                    original_query=original,
                    subtask_count=1,
                ),
                expected_output="Skill execution output and artifacts.",
                step_number=start_index,
            )
        ]
    steps: list[PlanStep] = []
    for index, subtask in enumerate(subtasks, start=1):
        step_number = start_index + index - 1
        depends_on = [] if index == 1 else [f"step_{step_number - 1:03d}"]
        steps.append(
            _step(
                f"run_skill_subtask_{index}",
                f"execute subtask {index} through the selected Skill",
                "execute_plan",
                depends_on=depends_on,
                tool_input=_skill_tool_input(
                    subtask,
                    selected_skill,
                    index,
                    original_query=original,
                    subtask_count=len(subtasks),
                ),
                expected_output=f"Skill execution output for subtask {index}.",
                step_number=step_number,
            )
        )
    return steps


def _skill_tool_input(
    subtask: str,
    selected_skill: SkillCandidate | None,
    index: int,
    original_query: str,
    subtask_count: int,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "subtask": subtask,
        "subtask_index": index,
        "subtask_count": subtask_count,
        "original_query": original_query,
        "skill_input": _skill_input_for_subtask(original_query, subtask, index, subtask_count),
    }
    if selected_skill:
        payload.update(
            {
                "skill_slug": selected_skill.skill_slug,
                "version": selected_skill.version,
                "skill_path": str(selected_skill.skill_path),
            }
        )
    return payload


def _skill_input_for_subtask(original_query: str, subtask: str, index: int, subtask_count: int) -> str:
    original = " ".join(original_query.strip().split())
    focus = " ".join(subtask.strip().split())
    if subtask_count <= 1 or not focus or focus == original:
        return original
    return "\n\n".join(
        [
            "原始完整用户请求：",
            original,
            f"当前执行焦点（第 {index}/{subtask_count} 步）：",
            focus,
            "执行要求：",
            "请在处理当前执行焦点时保留原始完整请求中的全部上下文、约束、端点、字段和输出要求。"
            "不要仅基于当前焦点片段判断信息不足；只有原始完整请求也缺失必要信息时，才请求补充。",
        ]
    )


def _step(
    name: str,
    action: str,
    tool_name: str | None,
    depends_on: list[str] | None = None,
    tool_input: dict[str, Any] | None = None,
    expected_output: str | None = None,
    permission_required: str = "execute",
    step_number: int = 1,
) -> PlanStep:
    return PlanStep(
        name=name,
        action=action,
        tool_name=tool_name,
        step_id=f"step_{step_number:03d}",
        depends_on=depends_on or [],
        tool_input=tool_input or {},
        expected_output=expected_output,
        permission_required=permission_required,
    )


def _objective_for_intent(intent: Intent) -> str:
    if intent.intent_type == "empty":
        return "Validate the empty input."
    if intent.task_type == "trace_diagnosis":
        return "Diagnose a local trace through the Task Router."
    if intent.task_type == "skill_evolve":
        return "Route Skill evolution through the Task Router."
    if intent.task_type == "code_analysis":
        return "Analyze code through the Task Router."
    if intent.task_type == "document_analysis":
        return "Analyze documents through the Task Router."
    if intent.task_type == "data_analysis":
        return "Analyze data through the Task Router."
    if intent.intent_type == "generate_skill":
        return "Generate a reusable versioned Skill from the user's requirement."
    if intent.requires_skill:
        return "Use the best available Skill to produce a structured task result."
    return "Answer the message through the local Agent loop."


def _default_stop_conditions(intent: Intent, complexity: str) -> list[StopCondition]:
    max_steps = 12 if complexity == "complex" else 8
    conditions = [
        StopCondition("max_steps", max_steps, "Bound the local AgentForge plan."),
        StopCondition("blocking_error", True, "Stop when a non-recoverable tool or execution error occurs."),
        StopCondition("response_hqs_gate", "single_retry", "Rebuild the response once before reflection or reinforcement."),
    ]
    if intent.requires_skill:
        conditions.append(
            StopCondition("skill_execution_complete", True, "Stop Skill execution after all planned subtasks are evaluated.")
        )
    return conditions


def _decompose_task(query: str, limit: int = 6) -> list[str]:
    normalized = " ".join(query.strip().split())
    if not normalized:
        return []

    numbered = _numbered_parts(query)
    if len(numbered) > 1:
        return numbered[:limit]

    replaced = normalized
    for connector in _complex_connectors():
        replaced = re.sub(connector, " || ", replaced, flags=re.IGNORECASE)
    parts = [_clean_part(part) for part in replaced.split("||")]
    parts = [part for part in parts if part]
    if len(parts) <= 1:
        return [normalized]
    return parts[:limit]


def _numbered_parts(query: str) -> list[str]:
    parts = re.split(r"(?:^|\n)\s*(?:\d+[\).]|[-*])\s+", query.strip())
    cleaned = [_clean_part(part) for part in parts if _clean_part(part)]
    return cleaned


def _complex_connectors() -> list[str]:
    return [
        r"\s+and\s+then\s+",
        r"\s+then\s+",
        r"\s+after\s+that\s+",
        r"\s+next\s+",
        r"\s*\u7136\u540e\s*",
        r"\s*\u63a5\u7740\s*",
    ]


def _clean_part(value: str) -> str:
    return value.strip(" \t\r\n-:;,")
