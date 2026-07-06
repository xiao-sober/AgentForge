from __future__ import annotations

import json
from dataclasses import dataclass, field, replace
from typing import Any, Protocol

from agentforge.agent.tool_calling.parser import DecisionParseError, ToolDecision, parse_model_decision
from agentforge.agent.tool_calling.prompts import (
    TOOL_CALLING_REPAIR_SYSTEM_PROMPT,
    TOOL_CALLING_SYSTEM_PROMPT,
    build_decision_repair_prompt,
    build_tool_calling_prompt,
)
from agentforge.common.llm_client import LLMClient


class ToolCallingPlanner(Protocol):
    def decide(self, state: Any, runtime_state: dict[str, Any] | None = None) -> ToolDecision | str:
        """Return the next structured tool-calling decision."""

    def metadata(self) -> dict[str, Any]:
        """Return non-secret planner metadata."""


@dataclass
class ProviderModelPlanner:
    llm_client: LLMClient
    max_repair_attempts: int = 1

    def decide(self, state: Any, runtime_state: dict[str, Any] | None = None) -> ToolDecision:
        payload = state.to_prompt_payload()
        raw = self.llm_client.complete(
            build_tool_calling_prompt(payload),
            system_prompt=TOOL_CALLING_SYSTEM_PROMPT,
        )
        try:
            return parse_model_decision(raw)
        except DecisionParseError as exc:
            if self.max_repair_attempts < 1:
                raise
            repair_raw = self.llm_client.complete(
                build_decision_repair_prompt(raw, str(exc), payload),
                system_prompt=TOOL_CALLING_REPAIR_SYSTEM_PROMPT,
            )
            decision = parse_model_decision(repair_raw)
            return replace(
                decision,
                provider_repair_attempted=True,
                provider_repair_error=str(exc),
            )

    def metadata(self) -> dict[str, Any]:
        metadata = self.llm_client.metadata()
        return {"planner": "provider", "provider": metadata}


@dataclass
class ScriptedModelPlanner:
    decisions: list[ToolDecision | dict[str, Any] | str] = field(default_factory=list)
    index: int = 0
    auto_route: bool = False
    route: str = "custom"

    @classmethod
    def default(cls) -> "ScriptedModelPlanner":
        return cls(auto_route=True, route="auto")

    def decide(self, state: Any, runtime_state: dict[str, Any] | None = None) -> ToolDecision:
        if self.auto_route and self.index == 0 and not self.decisions:
            self.route = _scripted_route_name(state, runtime_state)
            self.decisions = _scripted_route_decisions(self.route)
        if self.index < len(self.decisions):
            decision = self.decisions[self.index]
            self.index += 1
            return _coerce_decision(decision)
        response = ""
        if runtime_state and isinstance(runtime_state.get("response"), str):
            response = str(runtime_state["response"])
        return ToolDecision.final_answer(response or "AgentForge tool-calling run completed.")

    def metadata(self) -> dict[str, Any]:
        return {
            "planner": "scripted",
            "route": self.route,
            "auto_route": self.auto_route,
            "remaining_decisions": max(0, len(self.decisions) - self.index),
        }


def _coerce_decision(value: ToolDecision | dict[str, Any] | str) -> ToolDecision:
    if isinstance(value, ToolDecision):
        return value
    if isinstance(value, dict):
        return parse_model_decision(json.dumps(value, ensure_ascii=False))
    return parse_model_decision(value)


def _scripted_route_name(state: Any, runtime_state: dict[str, Any] | None) -> str:
    intent_type = ""
    if runtime_state and runtime_state.get("intent") is not None:
        intent = runtime_state["intent"]
        intent_type = str(getattr(intent, "intent_type", "") or "")
    user_input = str(getattr(state, "user_input", "") or "")
    lowered = user_input.lower()

    if intent_type == "inspect_traces" or "trace" in lowered or "日志" in user_input or "轨迹" in user_input:
        return "trace_inspection"
    if intent_type == "query_memory" or "memory" in lowered or "memories" in lowered or "记忆" in user_input:
        return "memory_query"
    if intent_type == "generate_skill":
        return "skill_generation"
    if intent_type in {"chat", "inspect_skills", "empty"}:
        return "direct_response"
    return "skill_execution"


def _scripted_route_decisions(route: str) -> list[ToolDecision]:
    if route == "trace_inspection":
        return [
            ToolDecision.tool_call("retrieve_memory_context", {}),
            ToolDecision.tool_call("inspect_latest_trace", {}),
            ToolDecision.tool_call("build_plan", {}),
            ToolDecision.tool_call("execute_plan", {}),
            ToolDecision.tool_call("build_response", {}),
            ToolDecision.tool_call("evaluate_response_hqs", {}),
        ]
    if route == "memory_query":
        return [
            ToolDecision.tool_call("retrieve_memory_context", {}),
            ToolDecision.tool_call("build_plan", {}),
            ToolDecision.tool_call("execute_plan", {}),
            ToolDecision.tool_call("build_response", {}),
            ToolDecision.tool_call("evaluate_response_hqs", {}),
        ]
    if route == "skill_generation":
        return [
            ToolDecision.tool_call("retrieve_memory_context", {}),
            ToolDecision.tool_call("build_plan", {}),
            ToolDecision.tool_call("execute_plan", {}),
            ToolDecision.tool_call("observe_execution", {}),
            ToolDecision.tool_call("build_response", {}),
            ToolDecision.tool_call("evaluate_response_hqs", {}),
        ]
    if route == "direct_response":
        return [
            ToolDecision.tool_call("retrieve_memory_context", {}),
            ToolDecision.tool_call("build_plan", {}),
            ToolDecision.tool_call("execute_plan", {}),
            ToolDecision.tool_call("build_response", {}),
            ToolDecision.tool_call("evaluate_response_hqs", {}),
        ]
    return [
        ToolDecision.tool_call("retrieve_memory_context", {}),
        ToolDecision.tool_call("select_skill", {}),
        ToolDecision.tool_call("build_plan", {}),
        ToolDecision.tool_call("execute_plan", {}),
        ToolDecision.tool_call("observe_execution", {}),
        ToolDecision.tool_call("build_response", {}),
        ToolDecision.tool_call("evaluate_response_hqs", {}),
    ]
