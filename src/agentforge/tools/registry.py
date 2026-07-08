from __future__ import annotations

from typing import Any

from agentforge.runs.service import RunService
from agentforge.tools.executor import ToolExecutor
from agentforge.tools.permissions import validate_permission_levels
from agentforge.tools.schema import AgentTool, ToolCall, ToolResult, ToolSchema


class ToolRegistry:
    def __init__(
        self,
        allowed_permission_levels: set[str] | None = None,
        executor: ToolExecutor | None = None,
    ) -> None:
        validate_permission_levels(allowed_permission_levels)
        self._tools: dict[str, AgentTool] = {}
        self.allowed_permission_levels = allowed_permission_levels
        self.executor = executor or ToolExecutor()

    def register(self, tool: AgentTool) -> None:
        if not tool.name.strip():
            raise ValueError("Tool name cannot be empty.")
        if tool.name in self._tools:
            raise ValueError(f"Tool already registered: {tool.name}")
        self._tools[tool.name] = tool

    def register_tool(self, tool: AgentTool) -> None:
        self.register(tool)

    def get(self, name: str) -> AgentTool:
        try:
            return self._tools[name]
        except KeyError as exc:
            raise ValueError(f"Tool is not registered: {name}") from exc

    def get_tool(self, name: str) -> AgentTool:
        return self.get(name)

    def execute(
        self,
        call: ToolCall,
        run_id: str | None = None,
        step_id: str | None = None,
        run_service: RunService | None = None,
    ) -> ToolResult:
        return self.executor.execute(
            tool=self.get(call.tool_name),
            call=call,
            allowed_permission_levels=self.allowed_permission_levels,
            run_id=run_id,
            step_id=step_id,
            run_service=run_service,
        )

    def list_tools(self) -> list[dict[str, Any]]:
        return [tool.to_dict() for tool in sorted(self._tools.values(), key=lambda item: item.name)]

    def schema_for_model(
        self,
        allowed_tool_names: set[str] | list[str] | tuple[str, ...] | None = None,
    ) -> list[dict[str, Any]]:
        names = (
            sorted(allowed_tool_names)
            if allowed_tool_names is not None
            else [item["name"] for item in self.list_tools()]
        )
        return [_agent_tool_to_model_schema(self.get(name)) for name in names]


def _agent_tool_to_model_schema(tool: AgentTool) -> dict[str, Any]:
    return {
        "name": tool.name,
        "description": tool.description,
        "kind": tool.kind,
        "permission_level": tool.permission_level,
        "idempotent": tool.idempotent,
        "side_effects": tool.side_effects,
        "input_schema": _tool_schema_to_json_schema(tool.input_schema),
    }


def _tool_schema_to_json_schema(schema: ToolSchema) -> dict[str, Any]:
    return schema.to_json_schema()
