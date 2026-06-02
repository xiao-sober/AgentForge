from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


ToolHandler = Callable[[dict[str, Any]], "ToolResult"]
TOOL_PERMISSION_LEVELS = {"read", "write", "execute", "control", "admin"}
TOOL_VALUE_TYPES = {"string", "number", "integer", "boolean", "object", "array", "any"}


@dataclass(frozen=True)
class ToolFieldSpec:
    name: str
    value_type: str = "any"
    required: bool = True
    description: str = ""

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("Tool field name cannot be empty.")
        if self.value_type not in TOOL_VALUE_TYPES:
            raise ValueError(f"Unsupported Tool field type: {self.value_type}")

    def validate(self, payload: dict[str, Any], location: str) -> list[str]:
        if self.name not in payload:
            return [f"{location}.{self.name} is required"] if self.required else []
        value = payload[self.name]
        if self.value_type == "any" or _matches_type(value, self.value_type):
            return []
        return [f"{location}.{self.name} must be {self.value_type}"]

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "value_type": self.value_type,
            "required": self.required,
            "description": self.description,
        }


@dataclass(frozen=True)
class ToolSchema:
    fields: list[ToolFieldSpec] = field(default_factory=list)
    allow_extra: bool = True
    description: str = ""

    @classmethod
    def from_types(
        cls,
        required: dict[str, str] | None = None,
        optional: dict[str, str] | None = None,
        allow_extra: bool = True,
        description: str = "",
    ) -> "ToolSchema":
        fields = [
            ToolFieldSpec(name=name, value_type=value_type, required=True)
            for name, value_type in (required or {}).items()
        ]
        fields.extend(
            ToolFieldSpec(name=name, value_type=value_type, required=False)
            for name, value_type in (optional or {}).items()
        )
        return cls(fields=fields, allow_extra=allow_extra, description=description)

    def validate(self, payload: dict[str, Any], location: str) -> list[str]:
        if not isinstance(payload, dict):
            return [f"{location} must be an object"]
        errors: list[str] = []
        known_fields = {field.name for field in self.fields}
        for field_spec in self.fields:
            errors.extend(field_spec.validate(payload, location))
        if not self.allow_extra:
            for key in sorted(set(payload) - known_fields):
                errors.append(f"{location}.{key} is not allowed")
        return errors

    def to_dict(self) -> dict[str, Any]:
        return {
            "fields": [field_spec.to_dict() for field_spec in self.fields],
            "allow_extra": self.allow_extra,
            "description": self.description,
        }


@dataclass(frozen=True)
class ToolErrorSpec:
    error_type: str
    user_message: str
    recoverable: bool
    description: str = ""

    def __post_init__(self) -> None:
        if not self.error_type.strip():
            raise ValueError("Tool error type cannot be empty.")

    def to_dict(self) -> dict[str, Any]:
        return {
            "error_type": self.error_type,
            "user_message": self.user_message,
            "recoverable": self.recoverable,
            "description": self.description,
        }


@dataclass(frozen=True)
class ToolCall:
    tool_name: str
    input: dict[str, Any] = field(default_factory=dict)
    step_name: str | None = None
    kind: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "tool_name": self.tool_name,
            "input": self.input,
            "step_name": self.step_name,
            "kind": self.kind,
        }


@dataclass(frozen=True)
class ToolResult:
    output: dict[str, Any] = field(default_factory=dict)
    artifacts: list[dict[str, Any]] = field(default_factory=list)
    errors: list[dict[str, Any]] = field(default_factory=list)
    status: str = "completed"

    def to_dict(self) -> dict[str, Any]:
        return {
            "output": self.output,
            "artifacts": self.artifacts,
            "errors": self.errors,
            "status": self.status,
        }


@dataclass(frozen=True)
class AgentTool:
    name: str
    kind: str
    handler: ToolHandler
    description: str = ""
    input_schema: ToolSchema = field(default_factory=ToolSchema)
    output_schema: ToolSchema = field(default_factory=ToolSchema)
    error_specs: list[ToolErrorSpec] = field(default_factory=list)
    permission_level: str = "execute"
    idempotent: bool = False
    timeout_seconds: float | None = None

    def __post_init__(self) -> None:
        if self.permission_level not in TOOL_PERMISSION_LEVELS:
            raise ValueError(f"Unsupported Tool permission level: {self.permission_level}")
        if self.timeout_seconds is not None and self.timeout_seconds <= 0:
            raise ValueError("Tool timeout_seconds must be positive when provided.")

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "kind": self.kind,
            "description": self.description,
            "input_schema": self.input_schema.to_dict(),
            "output_schema": self.output_schema.to_dict(),
            "error_specs": [error.to_dict() for error in self.error_specs],
            "permission_level": self.permission_level,
            "idempotent": self.idempotent,
            "timeout_seconds": self.timeout_seconds,
        }


class ToolRegistry:
    def __init__(self, allowed_permission_levels: set[str] | None = None) -> None:
        unknown = (allowed_permission_levels or set()) - TOOL_PERMISSION_LEVELS
        if unknown:
            raise ValueError(f"Unsupported Tool permission level: {', '.join(sorted(unknown))}")
        self._tools: dict[str, AgentTool] = {}
        self.allowed_permission_levels = allowed_permission_levels

    def register(self, tool: AgentTool) -> None:
        if not tool.name.strip():
            raise ValueError("Tool name cannot be empty.")
        if tool.name in self._tools:
            raise ValueError(f"Tool already registered: {tool.name}")
        self._tools[tool.name] = tool

    def get(self, name: str) -> AgentTool:
        try:
            return self._tools[name]
        except KeyError as exc:
            raise ValueError(f"Tool is not registered: {name}") from exc

    def execute(self, call: ToolCall) -> ToolResult:
        tool = self.get(call.tool_name)
        if self.allowed_permission_levels is not None and tool.permission_level not in self.allowed_permission_levels:
            return ToolResult(
                errors=[
                    _validation_error(
                        "ToolPermissionDenied",
                        f"Tool '{tool.name}' requires '{tool.permission_level}' permission.",
                        recoverable=False,
                    )
                ],
                status="failed",
            )
        input_errors = tool.input_schema.validate(call.input, "input")
        if input_errors:
            return ToolResult(
                errors=[
                    _validation_error(
                        "ToolInputValidationError",
                        "; ".join(input_errors),
                        recoverable=False,
                    )
                ],
                status="failed",
            )

        result = tool.handler(call.input)
        if not isinstance(result, ToolResult):
            return ToolResult(
                errors=[
                    _validation_error(
                        "ToolResultValidationError",
                        f"Tool '{tool.name}' returned {type(result).__name__}, expected ToolResult.",
                        recoverable=False,
                    )
                ],
                status="failed",
            )

        output_errors = tool.output_schema.validate(result.output, "output")
        if output_errors:
            errors = [
                *result.errors,
                _validation_error(
                    "ToolOutputValidationError",
                    "; ".join(output_errors),
                    recoverable=False,
                ),
            ]
            return ToolResult(
                output=result.output,
                artifacts=result.artifacts,
                errors=errors,
                status="failed",
            )
        return result

    def list_tools(self) -> list[dict[str, Any]]:
        return [tool.to_dict() for tool in sorted(self._tools.values(), key=lambda item: item.name)]


def _matches_type(value: Any, value_type: str) -> bool:
    if value_type == "string":
        return isinstance(value, str)
    if value_type == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if value_type == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if value_type == "boolean":
        return isinstance(value, bool)
    if value_type == "object":
        return isinstance(value, dict)
    if value_type == "array":
        return isinstance(value, list)
    return True


def _validation_error(error_type: str, message: str, recoverable: bool) -> dict[str, Any]:
    return {
        "error_type": error_type,
        "message": message,
        "user_message": message,
        "recoverable": recoverable,
    }
