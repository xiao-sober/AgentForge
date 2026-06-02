import unittest

from agentforge.agent.tools import AgentTool, ToolCall, ToolRegistry, ToolResult, ToolSchema


class ToolSchemaTest(unittest.TestCase):
    def test_tool_input_schema_rejects_invalid_payload_before_handler_runs(self):
        calls = {"count": 0}
        registry = ToolRegistry()
        registry.register(
            AgentTool(
                name="echo",
                kind="test",
                handler=lambda payload: _echo_handler(payload, calls),
                input_schema=ToolSchema.from_types(required={"message": "string"}, allow_extra=False),
                output_schema=ToolSchema.from_types(required={"value": "string"}),
            )
        )

        result = registry.execute(ToolCall("echo", {"message": 12}))

        self.assertEqual(result.status, "failed")
        self.assertEqual(result.errors[0]["error_type"], "ToolInputValidationError")
        self.assertEqual(calls["count"], 0)

    def test_tool_output_schema_records_invalid_result(self):
        registry = ToolRegistry()
        registry.register(
            AgentTool(
                name="bad_output",
                kind="test",
                handler=lambda payload: ToolResult(output={"value": 123}),
                output_schema=ToolSchema.from_types(required={"value": "string"}),
            )
        )

        result = registry.execute(ToolCall("bad_output"))

        self.assertEqual(result.status, "failed")
        self.assertEqual(result.errors[0]["error_type"], "ToolOutputValidationError")

    def test_permission_policy_blocks_disallowed_tool(self):
        registry = ToolRegistry(allowed_permission_levels={"read"})
        registry.register(
            AgentTool(
                name="write_memory",
                kind="memory",
                handler=lambda payload: ToolResult(output={"ok": True}),
                permission_level="write",
            )
        )

        result = registry.execute(ToolCall("write_memory"))

        self.assertEqual(result.status, "failed")
        self.assertEqual(result.errors[0]["error_type"], "ToolPermissionDenied")


def _echo_handler(payload, calls):
    calls["count"] += 1
    return ToolResult(output={"value": payload["message"]})


if __name__ == "__main__":
    unittest.main()
