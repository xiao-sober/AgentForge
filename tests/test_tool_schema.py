import unittest
import tempfile
import time
from pathlib import Path

from agentforge.runs.service import RunService
from agentforge.tools import AgentTool, ToolCall, ToolRegistry, ToolResult, ToolSchema


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

    def test_tool_timeout_returns_standard_failed_result(self):
        registry = ToolRegistry()
        registry.register(
            AgentTool(
                name="slow_tool",
                kind="test",
                handler=lambda payload: _slow_handler(),
                timeout_seconds=0.01,
            )
        )

        result = registry.execute(ToolCall("slow_tool"))

        self.assertEqual(result.status, "failed")
        self.assertEqual(result.errors[0]["error_type"], "ToolTimeout")

    def test_registry_execute_persists_tool_call_when_run_context_is_provided(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            run_service = RunService(root)
            run_service.start_run(
                task_type="agent_chat",
                title="Agent chat",
                input_data={"message": "hello"},
                run_id="run_tool",
            )
            registry = ToolRegistry()
            registry.register(
                AgentTool(
                    name="echo",
                    kind="test",
                    handler=lambda payload: ToolResult(output={"value": payload["message"]}),
                    input_schema=ToolSchema.from_types(required={"message": "string"}, allow_extra=False),
                    output_schema=ToolSchema.from_types(required={"value": "string"}, allow_extra=False),
                )
            )

            result = registry.execute(
                ToolCall("echo", {"message": "ok"}),
                run_id="run_tool",
                step_id="run_tool_step_001",
                run_service=run_service,
            )

            tool_calls = run_service.repository.list_tool_calls("run_tool")
            self.assertEqual(result.status, "completed")
            self.assertEqual(len(tool_calls), 1)
            self.assertEqual(tool_calls[0].tool_name, "echo")
            self.assertEqual(tool_calls[0].step_id, "run_tool_step_001")
            self.assertEqual(tool_calls[0].arguments, {"message": "ok"})
            self.assertEqual(tool_calls[0].result["status"], "completed")

    def test_registry_exposes_formal_model_schema_and_compatibility_aliases(self):
        registry = ToolRegistry()
        registry.register_tool(
            AgentTool(
                name="read_file",
                kind="file",
                handler=lambda payload: ToolResult(output={"content": ""}),
                description="Read a file.",
                input_schema=ToolSchema.from_types(required={"path": "string"}, allow_extra=False),
                permission_level="read",
                idempotent=True,
                side_effects=False,
            )
        )

        schema = registry.schema_for_model({"read_file"})[0]

        self.assertEqual(registry.get_tool("read_file").name, "read_file")
        self.assertEqual(schema["name"], "read_file")
        self.assertEqual(schema["permission_level"], "read")
        self.assertTrue(schema["idempotent"])
        self.assertFalse(schema["side_effects"])
        self.assertEqual(schema["input_schema"]["properties"]["path"]["type"], "string")
        self.assertFalse(schema["input_schema"]["additionalProperties"])

    def test_tool_schema_accepts_full_json_schema(self):
        calls = {"count": 0}
        schema = {
            "type": "object",
            "required": ["config"],
            "properties": {
                "config": {
                    "type": "object",
                    "required": ["limit"],
                    "properties": {
                        "limit": {"type": "integer", "minimum": 1, "maximum": 5},
                        "mode": {"enum": ["fast", "safe"]},
                    },
                    "additionalProperties": False,
                }
            },
            "additionalProperties": False,
        }
        registry = ToolRegistry()
        registry.register(
            AgentTool(
                name="json_schema_tool",
                kind="test",
                handler=lambda payload: _counting_result(payload, calls),
                input_schema=ToolSchema.from_json_schema(schema),
                output_schema=ToolSchema.from_json_schema(
                    {
                        "type": "object",
                        "required": ["accepted"],
                        "properties": {"accepted": {"type": "boolean"}},
                        "additionalProperties": False,
                    }
                ),
            )
        )

        invalid = registry.execute(ToolCall("json_schema_tool", {"config": {"limit": 0, "extra": True}}))
        valid = registry.execute(ToolCall("json_schema_tool", {"config": {"limit": 3, "mode": "safe"}}))
        model_schema = registry.schema_for_model({"json_schema_tool"})[0]["input_schema"]

        self.assertEqual(invalid.status, "failed")
        self.assertEqual(invalid.errors[0]["error_type"], "ToolInputValidationError")
        self.assertIn("input.config.limit must be greater than or equal to 1", invalid.errors[0]["message"])
        self.assertIn("input.config.extra is not allowed", invalid.errors[0]["message"])
        self.assertEqual(valid.status, "completed")
        self.assertEqual(valid.output, {"accepted": True})
        self.assertEqual(calls["count"], 1)
        self.assertEqual(model_schema, schema)


def _echo_handler(payload, calls):
    calls["count"] += 1
    return ToolResult(output={"value": payload["message"]})


def _counting_result(payload, calls):
    calls["count"] += 1
    return ToolResult(output={"accepted": True})


def _slow_handler():
    time.sleep(0.1)
    return ToolResult(output={"ok": True})


if __name__ == "__main__":
    unittest.main()
