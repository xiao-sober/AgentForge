from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


SYSTEM_HQS_DIMENSIONS = [
    "Tool Reliability",
    "Memory Retrieval Quality",
    "Skill Selection Accuracy",
    "Trace Completeness",
    "Recovery Ability",
    "User Experience",
]


@dataclass(frozen=True)
class SystemHQSReport:
    dimensions: list[str]
    scores: dict[str, float]
    average_score: float
    rationale: dict[str, str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "dimensions": self.dimensions,
            "scores": self.scores,
            "average_score": self.average_score,
            "rationale": self.rationale,
        }


def evaluate_system(state: dict[str, Any]) -> SystemHQSReport:
    scores = {
        "Tool Reliability": _score_tool_reliability(state),
        "Memory Retrieval Quality": _score_memory_retrieval(state),
        "Skill Selection Accuracy": _score_skill_selection(state),
        "Trace Completeness": _score_trace_completeness(state),
        "Recovery Ability": _score_recovery(state),
        "User Experience": _score_user_experience(state),
    }
    average = round(sum(scores.values()) / len(scores), 2)
    rationale = {dimension: _rationale(dimension, scores[dimension]) for dimension in SYSTEM_HQS_DIMENSIONS}
    return SystemHQSReport(
        dimensions=SYSTEM_HQS_DIMENSIONS,
        scores=scores,
        average_score=average,
        rationale=rationale,
    )


def _score_tool_reliability(state: dict[str, Any]) -> float:
    errors = state.get("errors") or []
    if not errors:
        return 4.5
    if state.get("response"):
        return 3.0
    return 1.0


def _score_memory_retrieval(state: dict[str, Any]) -> float:
    context = state.get("memory_context") or {}
    score = 3.0
    if context.get("working_memory") is not None:
        score += 0.5
    if context.get("episodes"):
        score += 0.5
    if context.get("semantic_memory"):
        score += 0.5
    return _clamp(score)


def _score_skill_selection(state: dict[str, Any]) -> float:
    intent = state.get("intent") or {}
    requires_skill = bool(intent.get("requires_skill"))
    selected_skill = state.get("selected_skill")
    generated_skill = state.get("generated_skill_path")
    if requires_skill and (selected_skill or generated_skill):
        return 4.5
    if not requires_skill and not selected_skill:
        return 4.0
    if selected_skill:
        return 3.5
    return 2.0


def _score_trace_completeness(state: dict[str, Any]) -> float:
    trace_path = state.get("trace_path")
    if trace_path and Path(str(trace_path)).exists():
        return 4.5
    steps = state.get("steps") or []
    if steps:
        return 3.5
    return 1.0


def _score_recovery(state: dict[str, Any]) -> float:
    errors = state.get("errors") or []
    if not errors:
        return 4.0
    if state.get("response") and state.get("trace_path"):
        return 3.5
    return 1.5


def _score_user_experience(state: dict[str, Any]) -> float:
    response = str(state.get("response") or "")
    if not response:
        return 0.0
    score = 3.0
    if "Trace" in response or "trace" in response:
        score += 0.5
    if "HQS" in response or "hqs" in response:
        score += 0.5
    if len(response.split()) >= 30:
        score += 0.5
    return _clamp(score)


def _clamp(score: float) -> float:
    return round(max(0.0, min(5.0, score)), 2)


def _rationale(dimension: str, score: float) -> str:
    if score >= 4.0:
        return f"{dimension} is healthy for the local AgentForge runtime."
    if score >= 3.0:
        return f"{dimension} is usable but should be watched."
    if score > 0:
        return f"{dimension} needs improvement."
    return f"{dimension} is unavailable."
