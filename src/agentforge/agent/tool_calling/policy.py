from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from agentforge.agent.tool_calling.parser import ToolDecision
from agentforge.tools import ToolRegistry


MODEL_CALLABLE_TOOL_NAMES = {
    "retrieve_memory_context",
    "inspect_latest_trace",
    "select_skill",
    "build_plan",
    "execute_plan",
    "observe_execution",
    "build_response",
    "evaluate_response_hqs",
}

DEFAULT_TOOL_STATE_REQUIREMENTS = {
    "retrieve_memory_context": {"intent"},
    "inspect_latest_trace": {"intent"},
    "select_skill": {"intent"},
    "build_plan": {"intent"},
    "execute_plan": {"intent", "plan"},
    "observe_execution": {"execution"},
    "build_response": {"intent", "plan", "execution", "memory_context"},
    "evaluate_response_hqs": {"intent", "response", "memory_context"},
}


@dataclass(frozen=True)
class PolicyValidationResult:
    valid: bool
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {"valid": self.valid, "errors": self.errors}


@dataclass(frozen=True)
class ToolCallPolicy:
    allowed_tools: set[str] = field(default_factory=set)
    max_iterations: int = 8
    max_invalid_calls: int = 2
    max_tool_errors: int = 2
    max_repeated_tool_calls: int = 2
    max_same_tool_calls: int = 2
    same_tool_call_guard_tools: set[str] = field(default_factory=set)
    allow_write_tools: bool = False
    allow_admin_tools: bool = False
    allowed_write_tools: set[str] = field(default_factory=set)
    state_requirements: dict[str, set[str]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.max_iterations < 1:
            raise ValueError("max_iterations must be at least 1.")
        if self.max_invalid_calls < 1:
            raise ValueError("max_invalid_calls must be at least 1.")
        if self.max_tool_errors < 1:
            raise ValueError("max_tool_errors must be at least 1.")
        if self.max_repeated_tool_calls < 1:
            raise ValueError("max_repeated_tool_calls must be at least 1.")
        if self.max_same_tool_calls < 1:
            raise ValueError("max_same_tool_calls must be at least 1.")

    def validate(
        self,
        decision: ToolDecision,
        registry: ToolRegistry,
        runtime_state: dict[str, Any] | None = None,
    ) -> PolicyValidationResult:
        if decision.type in {"final_answer", "cannot_continue"}:
            return PolicyValidationResult(valid=True)
        if decision.type != "tool_call":
            return PolicyValidationResult(valid=False, errors=[f"Unsupported decision type: {decision.type}"])

        errors: list[str] = []
        tool_name = decision.tool_name or ""
        if tool_name not in self.allowed_tools:
            errors.append(f"Tool is not allowed: {tool_name}")
            return PolicyValidationResult(valid=False, errors=errors)

        try:
            tool = registry.get(tool_name)
        except ValueError as exc:
            return PolicyValidationResult(valid=False, errors=[str(exc)])

        if tool.permission_level == "write" and not self.allow_write_tools and tool.name not in self.allowed_write_tools:
            errors.append(f"Tool '{tool.name}' requires write permission.")
        if tool.permission_level == "admin" and not self.allow_admin_tools:
            errors.append(f"Tool '{tool.name}' requires admin permission.")

        runtime_state = runtime_state or {}
        missing_state = [
            key
            for key in sorted(self.state_requirements.get(tool.name, set()))
            if key not in runtime_state or runtime_state.get(key) is None
        ]
        if missing_state:
            errors.append(f"Tool '{tool.name}' is missing prerequisite state: {', '.join(missing_state)}")

        schema_errors = tool.input_schema.validate(decision.arguments, "arguments")
        errors.extend(schema_errors)
        return PolicyValidationResult(valid=not errors, errors=errors)


def default_tool_call_policy() -> ToolCallPolicy:
    return ToolCallPolicy(
        allowed_tools=set(MODEL_CALLABLE_TOOL_NAMES),
        max_iterations=8,
        max_invalid_calls=2,
        max_tool_errors=2,
        max_repeated_tool_calls=2,
        max_same_tool_calls=2,
        same_tool_call_guard_tools={"retrieve_memory_context"},
        allow_write_tools=False,
        allow_admin_tools=False,
        allowed_write_tools={"build_response"},
        state_requirements={key: set(value) for key, value in DEFAULT_TOOL_STATE_REQUIREMENTS.items()},
    )
