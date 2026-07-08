from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from agentforge.common.schema import validate_json_schema


@dataclass(frozen=True)
class TaskRequest:
    task_type: str
    input: dict[str, Any] = field(default_factory=dict)
    options: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "TaskRequest":
        task_type = payload.get("task_type")
        if not isinstance(task_type, str) or not task_type.strip():
            raise ValueError("Task request requires a non-empty JSON string field: task_type.")
        task_input = payload.get("input", {})
        if not isinstance(task_input, dict):
            raise ValueError("Task request field 'input' must be an object when provided.")
        options = payload.get("options", {})
        if not isinstance(options, dict):
            raise ValueError("Task request field 'options' must be an object when provided.")
        return cls(task_type=task_type.strip(), input=task_input, options=options)

    def payload(self) -> dict[str, Any]:
        return {**self.options, **self.input}

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_type": self.task_type,
            "input": self.input,
            "options": self.options,
        }


@dataclass(frozen=True)
class TaskTypeSpec:
    task_type: str
    title: str
    description: str
    input_schema: dict[str, Any] = field(default_factory=dict)
    options_schema: dict[str, Any] = field(default_factory=dict)
    stable: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_type": self.task_type,
            "title": self.title,
            "description": self.description,
            "input_schema": self.input_schema,
            "options_schema": self.options_schema,
            "stable": self.stable,
        }

    def validate_request(self, request: TaskRequest) -> list[str]:
        errors: list[str] = []
        errors.extend(validate_schema(self.input_schema, request.input, "input"))
        if self.options_schema:
            option_errors = validate_schema(self.options_schema, request.options, "options")
            if option_errors:
                # The existing TaskRequest contract merges input/options for handlers.
                # Keep that compatibility while still making validation explicit.
                payload_errors = validate_schema(self.options_schema, request.payload(), "payload")
                errors.extend(option_errors if payload_errors else [])
        return errors


@dataclass(frozen=True)
class TaskResult:
    task_type: str
    status: str
    run_id: str | None
    output: dict[str, Any]
    trace_path: Path | None = None
    artifacts: list[dict[str, Any]] = field(default_factory=list)
    errors: list[dict[str, Any]] = field(default_factory=list)
    raw_result: Any | None = field(default=None, repr=False, compare=False)

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_type": self.task_type,
            "status": self.status,
            "run_id": self.run_id,
            "output": self.output,
            "trace_path": str(self.trace_path) if self.trace_path else None,
            "artifacts": self.artifacts,
            "errors": self.errors,
        }


def validate_schema(schema: dict[str, Any], value: Any, label: str) -> list[str]:
    return validate_json_schema(schema, value, label)
