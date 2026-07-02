import tempfile
import unittest
from pathlib import Path

from agentforge.agent.run import AgentRun
from agentforge.agent.run_loop import AgentRunLoop
from agentforge.agent.tools import AgentTool, ToolCall, ToolRegistry, ToolResult
from agentforge.memory.memory_manager import MemoryManager


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


if __name__ == "__main__":
    unittest.main()
