from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


class ArtifactValidationError(ValueError):
    """Raised when a JSON artifact does not match the local MVP schema."""


@dataclass(frozen=True)
class ArtifactSchemaResult:
    artifact_type: str
    valid: bool
    errors: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifact_type": self.artifact_type,
            "valid": self.valid,
            "errors": self.errors,
        }


def validate_json_artifact(path: Path | str, payload: dict[str, Any]) -> ArtifactSchemaResult:
    artifact_path = Path(path)
    errors: list[str] = []
    artifact_type = infer_artifact_type(artifact_path, payload)

    if not isinstance(payload, dict):
        errors.append("payload must be a JSON object")
    else:
        _validate_json_values(payload, "$", errors)
        if artifact_type == "trace":
            _require_keys(payload, ["trace_id", "type", "created_at", "input", "steps", "output", "artifacts", "errors"], errors)
            _require_type(payload, "trace_id", str, errors)
            _require_type(payload, "type", str, errors)
            _require_type(payload, "created_at", str, errors)
            _require_type(payload, "steps", list, errors)
            _require_type(payload, "output", dict, errors)
            _require_type(payload, "artifacts", list, errors)
            _require_type(payload, "errors", list, errors)
        elif artifact_type == "run_result":
            _require_keys(payload, ["skill", "taskset", "mode", "outputs"], errors)
            _require_type(payload, "skill", dict, errors)
            _require_type(payload, "taskset", dict, errors)
            _require_type(payload, "mode", str, errors)
            _require_type(payload, "outputs", list, errors)
        elif artifact_type == "taskset":
            _require_keys(payload, ["name", "tasks"], errors)
            _require_type(payload, "name", str, errors)
            _require_type(payload, "tasks", list, errors)
        elif artifact_type == "hqs_report":
            _require_keys(payload, ["dimensions", "average_score", "per_task"], errors)
            _require_type(payload, "dimensions", list, errors)
            _require_number(payload, "average_score", errors)
            _require_type(payload, "per_task", list, errors)
        elif artifact_type == "skill_metadata":
            _require_keys(payload, ["skill_slug", "previous_version", "new_version", "created_at"], errors)
            _require_type(payload, "skill_slug", str, errors)
            _require_type(payload, "previous_version", str, errors)
            _require_type(payload, "new_version", str, errors)
            _require_type(payload, "created_at", str, errors)
        elif artifact_type == "candidate_decision":
            _require_keys(payload, ["candidate", "current_hqs", "candidate_hqs", "candidate_improvement"], errors)
            _require_type(payload, "candidate", dict, errors)
            _require_number(payload, "current_hqs", errors)
            _require_number(payload, "candidate_hqs", errors)
            _require_number(payload, "candidate_improvement", errors)
        elif artifact_type == "working_memory":
            _require_type(payload, "updated_at", str, errors, required=False)
        elif artifact_type == "semantic_memory":
            for key, value in payload.items():
                if not isinstance(value, dict):
                    errors.append(f"semantic memory entry '{key}' must be an object")

    return ArtifactSchemaResult(artifact_type=artifact_type, valid=not errors, errors=errors)


def assert_valid_json_artifact(path: Path | str, payload: dict[str, Any]) -> None:
    result = validate_json_artifact(path, payload)
    if not result.valid:
        joined = "; ".join(result.errors)
        raise ArtifactValidationError(f"Invalid {result.artifact_type} JSON artifact at {path}: {joined}")


def infer_artifact_type(path: Path, payload: dict[str, Any]) -> str:
    name = path.name
    parts = set(path.parts)
    if "traces" in parts or {"trace_id", "type", "created_at", "steps", "output"}.issubset(payload):
        return "trace"
    if name == "run_result.json":
        return "run_result"
    if name == "taskset.json":
        return "taskset"
    if name == "hqs_report.json" or {"dimensions", "average_score", "per_task"}.issubset(payload):
        return "hqs_report"
    if name == "metadata.json" and {"skill_slug", "previous_version", "new_version"}.issubset(payload):
        return "skill_metadata"
    if name == "decision.json":
        return "candidate_decision"
    if name == "working_memory.json":
        return "working_memory"
    if name == "semantic_memory.json":
        return "semantic_memory"
    return "json_object"


def _require_keys(payload: dict[str, Any], keys: list[str], errors: list[str]) -> None:
    for key in keys:
        if key not in payload:
            errors.append(f"missing required key: {key}")


def _require_type(
    payload: dict[str, Any],
    key: str,
    expected_type: type,
    errors: list[str],
    required: bool = True,
) -> None:
    if key not in payload:
        if required:
            errors.append(f"missing required key: {key}")
        return
    if not isinstance(payload[key], expected_type):
        errors.append(f"key '{key}' must be {expected_type.__name__}")


def _require_number(payload: dict[str, Any], key: str, errors: list[str]) -> None:
    if key not in payload:
        errors.append(f"missing required key: {key}")
        return
    if not isinstance(payload[key], (int, float)) or isinstance(payload[key], bool):
        errors.append(f"key '{key}' must be a number")


def _validate_json_values(value: Any, path: str, errors: list[str]) -> None:
    if value is None or isinstance(value, (str, int, float, bool)):
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            _validate_json_values(item, f"{path}[{index}]", errors)
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                errors.append(f"{path} contains a non-string object key")
                continue
            _validate_json_values(item, f"{path}.{key}", errors)
        return
    errors.append(f"{path} contains non-JSON value type {type(value).__name__}")
