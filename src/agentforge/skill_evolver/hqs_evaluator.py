from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from agentforge.common.file_store import write_json
from agentforge.skill_evolver.skill_runner import SkillRunResult, TaskOutput
from agentforge.skill_evolver.task_loader import Task, TaskSet


SKILL_HQS_DIMENSIONS = [
    "Task Completion",
    "Instruction Following",
    "Output Structure",
    "Specificity",
    "Robustness",
    "Risk / Hallucination Control",
]


@dataclass(frozen=True)
class HQSEvaluation:
    task_id: str
    scores: dict[str, float]
    average: float
    rationale: dict[str, str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "scores": self.scores,
            "average": self.average,
            "rationale": self.rationale,
        }


@dataclass(frozen=True)
class HQSReport:
    dimensions: list[str]
    average_score: float
    per_task: list[HQSEvaluation]

    def to_dict(self) -> dict[str, Any]:
        return {
            "dimensions": self.dimensions,
            "average_score": self.average_score,
            "per_task": [evaluation.to_dict() for evaluation in self.per_task],
        }


def evaluate_output(task: Task, output: str) -> HQSEvaluation:
    output_text = output.strip()
    scores = {
        "Task Completion": _score_task_completion(task, output_text),
        "Instruction Following": _score_instruction_following(task, output_text),
        "Output Structure": _score_output_structure(output_text),
        "Specificity": _score_specificity(task, output_text),
        "Robustness": _score_robustness(output_text),
        "Risk / Hallucination Control": _score_risk_control(output_text),
    }
    rationale = {dimension: _rationale(dimension, scores[dimension]) for dimension in SKILL_HQS_DIMENSIONS}
    average = round(sum(scores.values()) / len(scores), 2)
    return HQSEvaluation(task_id=task.task_id, scores=scores, average=average, rationale=rationale)


def evaluate_taskset(taskset: TaskSet, run_result: SkillRunResult | list[TaskOutput]) -> HQSReport:
    outputs = run_result.outputs if isinstance(run_result, SkillRunResult) else run_result
    output_by_id = {output.task_id: output.output for output in outputs}
    evaluations = [evaluate_output(task, output_by_id.get(task.task_id, "")) for task in taskset.tasks]
    average = round(sum(evaluation.average for evaluation in evaluations) / len(evaluations), 2)
    return HQSReport(dimensions=SKILL_HQS_DIMENSIONS, average_score=average, per_task=evaluations)


def write_hqs_report(path: Path, report: HQSReport) -> Path:
    return write_json(path, report.to_dict())


def _score_task_completion(task: Task, output: str) -> float:
    if not output:
        return 0.0
    score = 2.5
    if _overlap_ratio(task.input, output) >= 0.12:
        score += 1.0
    if task.expected_output is None:
        score += 0.5
    elif _overlap_ratio(_stringify_expected(task.expected_output), output) >= 0.15:
        score += 1.0
    if any(word in output.lower() for word in ["result", "output", "recommend", "action", "next step"]):
        score += 0.5
    return _clamp(score)


def _score_instruction_following(task: Task, output: str) -> float:
    if not output:
        return 0.0
    score = 2.5
    if "##" in output or "- " in output or "1." in output:
        score += 1.0
    criteria = task.criteria or []
    if not criteria:
        score += 0.5
    elif any(_overlap_ratio(criterion, output) >= 0.2 for criterion in criteria):
        score += 1.0
    if any(word in output.lower() for word in ["workflow", "constraint", "quality", "assumption"]):
        score += 0.75
    return _clamp(score)


def _score_output_structure(output: str) -> float:
    if not output:
        return 0.0
    score = 1.5
    if output.startswith("#"):
        score += 1.0
    if output.count("## ") >= 3:
        score += 1.5
    if "\n- " in output or "\n1. " in output:
        score += 0.75
    if len(output.splitlines()) >= 8:
        score += 0.25
    return _clamp(score)


def _score_specificity(task: Task, output: str) -> float:
    if not output:
        return 0.0
    word_count = len(output.split())
    score = 1.5
    if word_count >= 40:
        score += 1.0
    if word_count >= 80:
        score += 0.75
    if _overlap_ratio(task.input, output) >= 0.1:
        score += 1.0
    if any(word in output.lower() for word in ["concrete", "specific", "because", "why", "evidence"]):
        score += 0.5
    return _clamp(score)


def _score_robustness(output: str) -> float:
    if not output:
        return 0.0
    lowered = output.lower()
    score = 2.5
    if any(word in lowered for word in ["assumption", "gap", "missing", "unclear", "fallback"]):
        score += 1.0
    if any(word in lowered for word in ["constraint", "failure", "risk"]):
        score += 0.75
    if "do not invent" in lowered or "does not call a model" in lowered:
        score += 0.5
    return _clamp(score)


def _score_risk_control(output: str) -> float:
    if not output:
        return 0.0
    lowered = output.lower()
    score = 3.0
    if any(word in lowered for word in ["assumption", "uncertainty", "unclear", "provided input", "do not invent"]):
        score += 1.0
    if any(word in lowered for word in ["must be", "definitely", "always", "guaranteed"]) and "provided" not in lowered:
        score -= 0.75
    if "hallucination" in lowered or "invent" in lowered:
        score += 0.5
    return _clamp(score)


def _overlap_ratio(source: str, target: str) -> float:
    source_tokens = set(_tokens(source))
    if not source_tokens:
        return 0.0
    target_tokens = set(_tokens(target))
    return len(source_tokens & target_tokens) / len(source_tokens)


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


def _stringify_expected(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return " ".join(_stringify_expected(item) for item in value)
    if isinstance(value, dict):
        return " ".join(f"{key} {_stringify_expected(item)}" for key, item in value.items())
    return str(value)


def _clamp(score: float) -> float:
    return round(max(0.0, min(5.0, score)), 2)


def _rationale(dimension: str, score: float) -> str:
    if score >= 4.5:
        return f"{dimension} is strong for the available local evidence."
    if score >= 3.0:
        return f"{dimension} is acceptable but can be made more specific."
    if score > 0:
        return f"{dimension} is weak and should be improved in the next Skill version."
    return f"{dimension} could not be evaluated because the output was empty."
