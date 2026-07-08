import tempfile
import unittest
from pathlib import Path

from agentforge.workflows import WorkflowRunner, WorkflowStepResult


class WorkflowRunnerTest(unittest.TestCase):
    def test_runner_records_steps_and_checkpoints(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            runner = WorkflowRunner.for_task(
                root,
                workflow_id="skill_generation_workflow",
                task_type="skill_generate",
                steps=["parse_requirement", "write_skill"],
            )

            run_id = runner.start_run(
                task_type="skill_generate",
                title="Generate Skill",
                input_data={"input": "create a skill"},
                run_id="run_workflow",
            )
            runner.record_step(
                run_id,
                {"name": "parse_requirement", "status": "completed", "output": {"skill_slug": "demo"}},
                1,
            )
            runner.update_run(run_id, "running", {"phase": "parsed"})
            runner.record_run(
                task_type="skill_generate",
                title="Generate Skill",
                input_data={"input": "create a skill"},
                output_data={"result": "ok"},
                status="completed",
                run_id=run_id,
            )

            detail = runner.run_detail(run_id)
            checkpoints = detail["workflow_checkpoints"]
            self.assertEqual(detail["status"], "completed")
            self.assertEqual(detail["steps"][0]["name"], "parse_requirement")
            self.assertEqual(detail["steps"][0]["kind"], "workflow_step")
            self.assertEqual(detail["output"]["workflow"]["workflow_id"], "skill_generation_workflow")
            self.assertGreaterEqual(len(checkpoints), 4)
            self.assertEqual(checkpoints[0]["step_name"], "start")
            self.assertTrue(any(item["step_name"] == "parse_requirement" for item in checkpoints))
            self.assertEqual(checkpoints[-1]["state"]["status"], "completed")

    def test_update_without_output_preserves_previous_output(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            runner = WorkflowRunner.for_task(root, "agent_chat_workflow", "agent_chat")
            run_id = runner.start_run(
                task_type="agent_chat",
                title="Agent chat",
                input_data={"message": "hello"},
                run_id="run_keep_output",
            )

            runner.update_run(run_id, "running", {"phase": "received"})
            runner.update_run(run_id, "running")

            detail = runner.run_detail(run_id)
            self.assertEqual(detail["output"]["phase"], "received")

    def test_execute_runs_step_handlers_and_records_observability(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            runner = WorkflowRunner.for_task(
                root,
                workflow_id="hardening_workflow",
                task_type="code_analysis",
                steps=["resolve_sources", "analyze_sources"],
            )

            def resolve_sources(context):
                self.assertEqual(context.step_index, 1)
                return WorkflowStepResult(
                    output={"source_count": 1},
                    artifacts=[{"type": "code_source", "path": "src/sample.py"}],
                    state_updates={"sources": ["src/sample.py"]},
                )

            def analyze_sources(context):
                self.assertEqual(context.state["sources"], ["src/sample.py"])
                return {
                    "output": {"finding_count": 0},
                    "hqs_reports": {"system": {"average_score": 4.5, "dimensions": {}}},
                    "tool_calls": [
                        {
                            "tool_name": "static_analyzer",
                            "status": "completed",
                            "arguments": {"path": "src/sample.py"},
                            "tool_result": {"ok": True},
                        }
                    ],
                    "state_updates": {"finding_count": 0},
                }

            run_id = runner.execute(
                title="Code analysis",
                input_data={"path": "src/sample.py"},
                handlers={
                    "resolve_sources": resolve_sources,
                    "analyze_sources": analyze_sources,
                },
                run_id="run_execute",
            )

            detail = runner.run_detail(run_id)
            self.assertEqual(detail["status"], "completed")
            self.assertEqual([step["name"] for step in detail["steps"]], ["resolve_sources", "analyze_sources"])
            self.assertEqual(detail["output"]["state"]["sources"], ["src/sample.py"])
            self.assertEqual(detail["output"]["state"]["finding_count"], 0)
            self.assertEqual(detail["artifacts"][0]["type"], "code_source")
            self.assertEqual(detail["hqs_reports"][0]["scope"], "system")
            self.assertEqual(detail["tool_calls"][0]["tool_name"], "static_analyzer")
            self.assertTrue(any(item["step_name"] == "complete" for item in detail["workflow_checkpoints"]))

    def test_execute_fails_when_step_handler_is_missing(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            runner = WorkflowRunner.for_task(
                root,
                workflow_id="missing_handler_workflow",
                task_type="trace_diagnosis",
                steps=["inspect_trace"],
            )

            run_id = runner.execute(
                title="Trace diagnosis",
                input_data={"latest": True},
                handlers={},
                run_id="run_missing_handler",
            )

            detail = runner.run_detail(run_id)
            self.assertEqual(detail["status"], "failed")
            self.assertEqual(detail["steps"][0]["status"], "failed")
            self.assertEqual(detail["output"]["failed_step"], "inspect_trace")
            self.assertEqual(detail["output"]["error"][0]["error_type"], "WorkflowStepHandlerMissing")

    def test_execute_retries_failed_step_before_completing(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            attempts = {"count": 0}
            runner = WorkflowRunner.for_task(
                root,
                workflow_id="retry_workflow",
                task_type="data_analysis",
                steps=["profile_data"],
                retry_policy={"max_attempts": 2},
            )

            def profile_data(context):
                attempts["count"] += 1
                if context.attempt == 1:
                    raise RuntimeError("temporary failure")
                return WorkflowStepResult(output={"attempt": context.attempt})

            run_id = runner.execute(
                title="Data analysis",
                input_data={"input": "a,b\n1,2\n"},
                handlers={"profile_data": profile_data},
                run_id="run_retry",
            )

            detail = runner.run_detail(run_id)
            self.assertEqual(detail["status"], "completed")
            self.assertEqual(attempts["count"], 2)
            self.assertEqual([step["status"] for step in detail["steps"]], ["failed", "completed"])
            self.assertEqual(detail["steps"][1]["output"]["attempt"], 2)


if __name__ == "__main__":
    unittest.main()
