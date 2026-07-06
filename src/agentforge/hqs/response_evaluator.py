from __future__ import annotations

from dataclasses import dataclass
from typing import Any


RESPONSE_HQS_DIMENSIONS = [
    "Intent Satisfaction",
    "Instruction Following",
    "Completeness",
    "Specificity",
    "Safety / Risk Control",
    "Memory Usefulness",
]


@dataclass(frozen=True)
class ResponseHQSReport:
    dimensions: list[str]
    scores: dict[str, float]
    average_score: float
    rationale: dict[str, str]
    recommendation: str
    confidence: float
    calibration: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "dimensions": self.dimensions,
            "scores": self.scores,
            "average_score": self.average_score,
            "rationale": self.rationale,
            "recommendation": self.recommendation,
            "confidence": self.confidence,
            "calibration": self.calibration,
        }


def evaluate_response(
    user_input: str,
    response: str,
    memory_context: dict[str, Any] | None = None,
    intent: dict[str, Any] | None = None,
) -> ResponseHQSReport:
    response_text = response.strip()
    calibration = _calibration(user_input, response_text, memory_context)
    scores = {
        "Intent Satisfaction": _score_intent_satisfaction(user_input, response_text, intent),
        "Instruction Following": _score_instruction_following(response_text),
        "Completeness": _score_completeness(response_text),
        "Specificity": _score_specificity(user_input, response_text),
        "Safety / Risk Control": _score_safety(response_text),
        "Memory Usefulness": _score_memory_usefulness(response_text, memory_context),
    }
    average = round(sum(scores.values()) / len(scores), 2)
    rationale = {dimension: _rationale(dimension, scores[dimension]) for dimension in RESPONSE_HQS_DIMENSIONS}
    return ResponseHQSReport(
        dimensions=RESPONSE_HQS_DIMENSIONS,
        scores=scores,
        average_score=average,
        rationale=rationale,
        recommendation=_recommendation(average, scores),
        confidence=_confidence(calibration),
        calibration=calibration,
    )


def _score_intent_satisfaction(user_input: str, response: str, intent: dict[str, Any] | None) -> float:
    if not response:
        return 0.0
    score = 2.5
    if _overlap_ratio(user_input, response) >= 0.08:
        score += 1.0
    if any(word in response.lower() for word in ["result", "generated", "skill", "response", "output"]):
        score += 0.75
    if intent and str(intent.get("intent_type", "")) in response.lower():
        score += 0.25
    score -= _generic_response_penalty(response) * 0.5
    return _clamp(score)


def _score_instruction_following(response: str) -> float:
    if not response:
        return 0.0
    score = 2.5
    if "##" in response or "- " in response or "1. " in response:
        score += 1.0
    if any(word in response.lower() for word in ["trace", "hqs", "skill", "memory"]):
        score += 0.75
    if "error" not in response.lower():
        score += 0.25
    return _clamp(score)


def _score_completeness(response: str) -> float:
    if not response:
        return 0.0
    score = 2.0
    word_count = len(response.split())
    if word_count >= 35:
        score += 1.0
    if word_count >= 70:
        score += 0.75
    if response.count("## ") >= 2:
        score += 0.75
    if any(word in response.lower() for word in ["next", "artifact", "trace", "assumption"]):
        score += 0.5
    score -= _generic_response_penalty(response) * 0.35
    return _clamp(score)


def _score_specificity(user_input: str, response: str) -> float:
    if not response:
        return 0.0
    score = 1.75
    if _overlap_ratio(user_input, response) >= 0.12:
        score += 1.25
    if len(response.split()) >= 50:
        score += 0.75
    if any(word in response.lower() for word in ["because", "specific", "selected", "generated", "path"]):
        score += 0.75
    if _overlap_ratio(user_input, response) < 0.08:
        score -= 0.75
    score -= _generic_response_penalty(response)
    return _clamp(score)


def _score_safety(response: str) -> float:
    if not response:
        return 0.0
    lowered = response.lower()
    score = 3.0
    if any(word in lowered for word in ["assumption", "unclear", "local", "deterministic", "fallback"]):
        score += 0.75
    if any(word in lowered for word in ["trace", "recorded", "provided input", "not invent"]):
        score += 0.75
    if any(word in lowered for word in ["guaranteed", "definitely", "always"]) and "provided" not in lowered:
        score -= 0.75
    return _clamp(score)


def _score_memory_usefulness(response: str, memory_context: dict[str, Any] | None) -> float:
    if memory_context is None:
        return 3.0
    has_context = bool(memory_context.get("episodes")) or bool(memory_context.get("semantic_memory"))
    if not has_context:
        return 3.25
    score = 3.0
    if any(word in response.lower() for word in ["memory", "previous", "context", "selected"]):
        score += 1.0
    if memory_context.get("working_memory"):
        score += 0.25
    return _clamp(score)


def _overlap_ratio(source: str, target: str) -> float:
    source_tokens = set(_tokens(source))
    if not source_tokens:
        return 0.0
    target_tokens = set(_tokens(target))
    return len(source_tokens & target_tokens) / len(source_tokens)


def _calibration(user_input: str, response: str, memory_context: dict[str, Any] | None) -> dict[str, Any]:
    source_tokens = set(_tokens(user_input))
    response_tokens = set(_tokens(response))
    matched = sorted(source_tokens & response_tokens)
    generic_penalty = _generic_response_penalty(response)
    return {
        "evidence_overlap_ratio": _overlap_ratio(user_input, response),
        "matched_input_tokens": matched[:20],
        "generic_penalty": generic_penalty,
        "has_memory_context": bool(memory_context and (memory_context.get("episodes") or memory_context.get("semantic_memory"))),
    }


def _confidence(calibration: dict[str, Any]) -> float:
    overlap = float(calibration.get("evidence_overlap_ratio", 0.0) or 0.0)
    penalty = float(calibration.get("generic_penalty", 0.0) or 0.0)
    score = 0.45 + min(0.35, overlap) - min(0.25, penalty * 0.12)
    if calibration.get("has_memory_context"):
        score += 0.05
    return round(max(0.0, min(1.0, score)), 2)


def _generic_response_penalty(response: str) -> float:
    lowered = response.lower()
    generic_phrases = [
        "follow the skill workflow",
        "return a structured",
        "structured task output",
        "specific enough to act on",
        "actionable output",
        "recommended approach",
        "local deterministic run",
        "completed the local agent loop",
    ]
    hits = sum(1 for phrase in generic_phrases if phrase in lowered)
    if hits == 0:
        return 0.0
    return round(min(1.25, hits * 0.35), 2)


def _tokens(text: str) -> list[str]:
    normalized = "".join(char.lower() if char.isalnum() else " " for char in text)
    stopwords = {
        "the",
        "and",
        "for",
        "with",
        "this",
        "that",
        "from",
        "into",
        "about",
        "please",
        "should",
        "would",
        "could",
    }
    return [token for token in normalized.split() if len(token) >= 3 and token not in stopwords]


def _clamp(score: float) -> float:
    return round(max(0.0, min(5.0, score)), 2)


def _rationale(dimension: str, score: float) -> str:
    if score >= 4.5:
        return f"{dimension} is strong for the local evidence."
    if score >= 3.0:
        return f"{dimension} is acceptable for the local Agent loop."
    if score > 0:
        return f"{dimension} is weak and should trigger reinforcement review."
    return f"{dimension} could not be evaluated because the response was empty."


def _recommendation(average: float, scores: dict[str, float]) -> str:
    weak = [dimension for dimension, score in scores.items() if score < 3.0]
    if average >= 4.0:
        return "No reinforcement needed."
    if weak:
        return "Reinforce response quality for: " + ", ".join(weak) + "."
    return "Review the response and selected Skill before autonomous rewriting."
