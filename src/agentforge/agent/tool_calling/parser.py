from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any


class DecisionParseError(ValueError):
    """Raised when model output is not a valid AgentForge tool decision."""


@dataclass(frozen=True)
class ToolDecision:
    type: str
    tool_name: str | None = None
    arguments: dict[str, Any] = field(default_factory=dict)
    content: str | None = None
    reason: str | None = None
    needed_input: list[str] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)
    repaired: bool = False
    repair_strategy: str = "none"
    raw_text_preview: str | None = None
    provider_repair_attempted: bool = False
    provider_repair_error: str | None = None

    @classmethod
    def tool_call(cls, tool_name: str, arguments: dict[str, Any] | None = None) -> "ToolDecision":
        return cls(type="tool_call", tool_name=tool_name, arguments=arguments or {})

    @classmethod
    def final_answer(cls, content: str) -> "ToolDecision":
        return cls(type="final_answer", content=content)

    @classmethod
    def cannot_continue(cls, reason: str, needed_input: list[str] | None = None) -> "ToolDecision":
        return cls(type="cannot_continue", reason=reason, needed_input=needed_input or [])

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"type": self.type}
        if self.tool_name is not None:
            payload["tool_name"] = self.tool_name
            payload["arguments"] = self.arguments
        if self.content is not None:
            payload["content"] = self.content
        if self.reason is not None:
            payload["reason"] = self.reason
        if self.needed_input:
            payload["needed_input"] = self.needed_input
        parse_metadata: dict[str, Any] = {
            "repaired": self.repaired,
            "repair_strategy": self.repair_strategy,
            "provider_repair_attempted": self.provider_repair_attempted,
        }
        if self.raw_text_preview is not None:
            parse_metadata["raw_text_preview"] = self.raw_text_preview
        if self.provider_repair_error is not None:
            parse_metadata["provider_repair_error"] = self.provider_repair_error
        payload["parse_metadata"] = parse_metadata
        return payload


def parse_model_decision(text: str) -> ToolDecision:
    original_text = text
    raw_text = text.strip()
    if not raw_text:
        raise DecisionParseError("Model decision is empty.")
    try:
        payload = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        payload, repaired, repair_strategy = _extract_repairable_json_object(raw_text, exc)
    else:
        repaired = False
        repair_strategy = "none"
    if not isinstance(payload, dict):
        raise DecisionParseError("Model decision must be a JSON object.")

    preview = _preview(original_text) if repaired else None
    decision_type = payload.get("type")
    if decision_type == "tool_call":
        tool_name = payload.get("tool_name")
        if not isinstance(tool_name, str) or not tool_name.strip():
            raise DecisionParseError("tool_call decision requires a non-empty string tool_name.")
        arguments = payload.get("arguments", {})
        if not isinstance(arguments, dict):
            raise DecisionParseError("tool_call decision arguments must be an object.")
        return ToolDecision(
            type="tool_call",
            tool_name=tool_name.strip(),
            arguments=arguments,
            raw=payload,
            repaired=repaired,
            repair_strategy=repair_strategy,
            raw_text_preview=preview,
        )

    if decision_type == "final_answer":
        content = payload.get("content")
        if not isinstance(content, str) or not content.strip():
            raise DecisionParseError("final_answer decision requires non-empty string content.")
        return ToolDecision(
            type="final_answer",
            content=content,
            raw=payload,
            repaired=repaired,
            repair_strategy=repair_strategy,
            raw_text_preview=preview,
        )

    if decision_type == "cannot_continue":
        reason = payload.get("reason")
        if not isinstance(reason, str) or not reason.strip():
            raise DecisionParseError("cannot_continue decision requires non-empty string reason.")
        needed_input = payload.get("needed_input", [])
        if not isinstance(needed_input, list) or not all(isinstance(item, str) for item in needed_input):
            raise DecisionParseError("cannot_continue needed_input must be a list of strings.")
        return ToolDecision(
            type="cannot_continue",
            reason=reason,
            needed_input=needed_input,
            raw=payload,
            repaired=repaired,
            repair_strategy=repair_strategy,
            raw_text_preview=preview,
        )

    raise DecisionParseError("Model decision type must be one of: tool_call, final_answer, cannot_continue.")


def _extract_repairable_json_object(text: str, original_error: json.JSONDecodeError) -> tuple[dict[str, Any], bool, str]:
    candidates: list[tuple[dict[str, Any], int, int]] = []
    for start, end in _json_object_spans(text):
        if _is_array_wrapped(text, start, end):
            continue
        snippet = text[start:end]
        try:
            payload = json.loads(snippet)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            candidates.append((payload, start, end))
    if not candidates:
        raise DecisionParseError(f"Model decision must be a JSON object: {original_error.msg}") from original_error
    if len(candidates) > 1:
        raise DecisionParseError("Model decision must contain exactly one JSON object; multiple objects were found.")
    payload, start, end = candidates[0]
    strategy = "fenced_json" if _span_inside_fence(text, start, end) else "embedded_json_object"
    return payload, True, strategy


def _json_object_spans(text: str) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    depth = 0
    start: int | None = None
    in_string = False
    escaped = False
    for index, char in enumerate(text):
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
            continue
        if char == "{":
            if depth == 0:
                start = index
            depth += 1
            continue
        if char == "}" and depth:
            depth -= 1
            if depth == 0 and start is not None:
                spans.append((start, index + 1))
                start = None
    return spans


def _span_inside_fence(text: str, start: int, end: int) -> bool:
    fence_positions = []
    search_from = 0
    while True:
        position = text.find("```", search_from)
        if position == -1:
            break
        fence_positions.append(position)
        search_from = position + 3
    for index in range(0, len(fence_positions) - 1, 2):
        content_start = fence_positions[index] + 3
        content_end = fence_positions[index + 1]
        if start >= content_start and end <= content_end:
            return True
    return False


def _is_array_wrapped(text: str, start: int, end: int) -> bool:
    left = _previous_nonspace(text, start)
    right = _next_nonspace(text, end)
    return left == "[" and right == "]"


def _previous_nonspace(text: str, before: int) -> str | None:
    for index in range(before - 1, -1, -1):
        if not text[index].isspace():
            return text[index]
    return None


def _next_nonspace(text: str, after: int) -> str | None:
    for index in range(after, len(text)):
        if not text[index].isspace():
            return text[index]
    return None


def _preview(text: str, limit: int = 500) -> str:
    normalized = " ".join(text.strip().split())
    if len(normalized) <= limit:
        return normalized
    return normalized[: limit - 3] + "..."
