import tempfile
import unittest
from pathlib import Path

from agentforge.agent.run import AgentRun
from agentforge.agent.run_loop import AgentRunLoop
from agentforge.agent.tools import AgentTool, ToolCall, ToolRegistry, ToolResult
from agentforge.memory.memory_manager import MemoryManager
from agentforge.runs.service import RunService


class AgentRunLoopTest(unittest.TestCase):
    def test_executes_registered_tool_and_records_timeline(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            run = AgentRun.create("hello")
            registry = ToolRegistry()
            registry.register(
                AgentTool(
                    name="echo",
                    kind="test",
                    handler=lambda payload: ToolResult(output={"value": payload["value"]}),
                    description="Echo input.",
                )
            )
            loop = AgentRunLoop(run, registry, MemoryManager(Path(temp_dir), trace_updates=False))

            result = loop.execute(ToolCall("echo", {"value": "ok"}))

            self.assertEqual(result.output["value"], "ok")
            self.assertEqual(run.steps[0].name, "echo")
            self.assertEqual(run.steps[0].status, "completed")
            self.assertEqual(run.phase, "executing")
            self.assertTrue(any(item["reason"] == "echo" for item in run.phase_history))
            self.assertEqual(loop.state.tool_results[0]["call"]["tool_name"], "echo")

    def test_unregistered_tool_records_failed_step(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            run = AgentRun.create("hello")
            loop = AgentRunLoop(run, ToolRegistry(), MemoryManager(Path(temp_dir), trace_updates=False))

            result = loop.execute(ToolCall("missing_tool"))

            self.assertEqual(result.status, "failed")
            self.assertEqual(run.steps[0].status, "failed")
            self.assertEqual(run.steps[0].errors[0]["error_type"], "ValueError")
            self.assertEqual(run.phase_history[-1]["status"], "failed")

    def test_run_loop_persists_tool_call_with_step_id(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            run = AgentRun.create("hello")
            run_service = RunService(root)
            run_service.start_run(
                task_type="agent_chat",
                title="Agent chat",
                input_data={"message": "hello"},
                run_id=run.run_id,
                created_at=run.created_at,
            )
            registry = ToolRegistry()
            registry.register(
                AgentTool(
                    name="echo",
                    kind="test",
                    handler=lambda payload: ToolResult(output={"value": payload["value"]}),
                    description="Echo input.",
                )
            )
            loop = AgentRunLoop(
                run,
                registry,
                MemoryManager(root, trace_updates=False),
                run_service=run_service,
            )

            result = loop.execute(ToolCall("echo", {"value": "ok"}))

            tool_calls = run_service.repository.list_tool_calls(run.run_id)
            self.assertEqual(result.status, "completed")
            self.assertEqual(len(tool_calls), 1)
            self.assertEqual(tool_calls[0].tool_name, "echo")
            self.assertEqual(tool_calls[0].step_id, f"{run.run_id}_{run.steps[0].step_id}")


if __name__ == "__main__":
    unittest.main()
