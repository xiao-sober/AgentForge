from __future__ import annotations

from typing import Any

from agentforge.agent.tools import AgentTool, ToolFieldSpec, ToolRegistry, ToolSchema


_JSON_SCHEMA_TYPES = {
    "string": "string",
    "number": "number",
    "integer": "integer",
    "boolean": "boolean",
    "object": "object",
    "array": "array",
}


def agent_tool_to_model_schema(tool: AgentTool) -> dict[str, Any]:
    return {
        "name": tool.name,
        "description": tool.description,
        "kind": tool.kind,
        "permission_level": tool.permission_level,
        "idempotent": tool.idempotent,
        "input_schema": tool_schema_to_json_schema(tool.input_schema),
    }


def registry_model_schemas(
    registry: ToolRegistry,
    allowed_tool_names: set[str] | list[str] | tuple[str, ...] | None = None,
) -> list[dict[str, Any]]:
    names = (
        sorted(allowed_tool_names)
        if allowed_tool_names is not None
        else [item["name"] for item in registry.list_tools()]
    )
    return [agent_tool_to_model_schema(registry.get(name)) for name in names]


def tool_schema_to_json_schema(schema: ToolSchema) -> dict[str, Any]:
    properties: dict[str, Any] = {}
    required: list[str] = []
    for field in schema.fields:
        properties[field.name] = _field_to_json_schema(field)
        if field.required:
            required.append(field.name)

    result: dict[str, Any] = {
        "type": "object",
        "properties": properties,
        "required": required,
    }
    if not schema.allow_extra:
        result["additionalProperties"] = False
    if schema.description:
        result["description"] = schema.description
    return result


def _field_to_json_schema(field: ToolFieldSpec) -> dict[str, Any]:
    result: dict[str, Any] = {}
    json_type = _JSON_SCHEMA_TYPES.get(field.value_type)
    if json_type:
        result["type"] = json_type
    if field.description:
        result["description"] = field.description
    return result
