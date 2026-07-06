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

    @classmethod
    def default(cls) -> "ScriptedModelPlanner":
        return cls(
            decisions=[
                ToolDecision.tool_call("retrieve_memory_context", {}),
                ToolDecision.tool_call("select_skill", {}),
                ToolDecision.tool_call("build_plan", {}),
                ToolDecision.tool_call("execute_plan", {}),
                ToolDecision.tool_call("observe_execution", {}),
                ToolDecision.tool_call("build_response", {}),
                ToolDecision.tool_call("evaluate_response_hqs", {}),
            ]
        )

    def decide(self, state: Any, runtime_state: dict[str, Any] | None = None) -> ToolDecision:
        if self.index < len(self.decisions):
            decision = self.decisions[self.index]
            self.index += 1
            return _coerce_decision(decision)
        response = ""
        if runtime_state and isinstance(runtime_state.get("response"), str):
            response = str(runtime_state["response"])
        return ToolDecision.final_answer(response or "AgentForge tool-calling run completed.")

    def metadata(self) -> dict[str, Any]:
        return {"planner": "scripted", "remaining_decisions": max(0, len(self.decisions) - self.index)}


def _coerce_decision(value: ToolDecision | dict[str, Any] | str) -> ToolDecision:
    if isinstance(value, ToolDecision):
        return value
    if isinstance(value, dict):
        return parse_model_decision(json.dumps(value, ensure_ascii=False))
    return parse_model_decision(value)
