import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from agentforge.runs import RunRepository, RunService


class RunRepositoryTest(unittest.TestCase):
    def test_sqlite_initialization_is_idempotent(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            service = RunService(root)

            first = service.ensure_initialized()
            second = service.ensure_initialized()

            self.assertEqual(first, second)
            self.assertEqual(first, root / "data" / "agentforge.db")
            self.assertTrue(first.exists())
            with closing(sqlite3.connect(first)) as connection:
                tables = {
                    row[0]
                    for row in connection.execute(
                        "SELECT name FROM sqlite_master WHERE type = 'table'"
                    ).fetchall()
                }
            self.assertIn("runs", tables)
            self.assertIn("run_steps", tables)
            self.assertIn("tool_calls", tables)
            self.assertIn("workflow_checkpoints", tables)

    def test_database_path_must_stay_under_project_root(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            root = base / "project"
            root.mkdir()

            with self.assertRaises(ValueError):
                RunRepository(root, db_path=base / "external.db")

    def test_repository_and_service_store_run_detail(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            service = RunService(root)

            run_id = service.record_run(
                task_type="skill_run",
                title="Run Skill",
                input_data={"input": "Review dashboard"},
                output_data={"result": "ok"},
                trace_path=root / "traces" / "sample.json",
                status="completed",
                run_id="run_test",
                steps=[{"name": "load_skill", "kind": "setup", "status": "completed"}],
                artifacts=[{"type": "trace", "path": "traces/sample.json"}],
                hqs_reports={"response": {"average_score": 4.2, "scores": {"Completeness": 4}}},
                tool_calls=[
                    {
                        "tool_name": "build_response",
                        "status": "completed",
                        "arguments": {},
                        "tool_result": {"status": "completed"},
                    }
                ],
            )

            self.assertEqual(run_id, "run_test")
            runs = service.repository.list_runs()
            self.assertEqual(len(runs), 1)
            self.assertEqual(runs[0].task_type, "skill_run")
            detail = service.run_detail("run_test")
            self.assertIsNotNone(detail)
            self.assertEqual(detail["run_id"], "run_test")
            self.assertEqual(detail["steps"][0]["name"], "load_skill")
            self.assertEqual(detail["artifacts"][0]["type"], "trace")
            self.assertEqual(detail["tool_calls"][0]["tool_name"], "build_response")
            self.assertEqual(detail["hqs_reports"][0]["average_score"], 4.2)
            self.assertEqual(detail["workflow_checkpoints"], [])

    def test_lifecycle_updates_keep_existing_output(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            service = RunService(root)

            run_id = service.start_run(
                task_type="agent_chat",
                title="Agent chat",
                input_data={"message": "hello"},
                run_id="run_live",
            )
            service.update_run(run_id, "running", {"phase": "received"})
            service.record_step(
                run_id,
                {
                    "step_id": "step_001",
                    "name": "receive_input",
                    "kind": "input",
                    "status": "completed",
                    "output": {"message_length": 5},
                },
                1,
            )
            service.update_run(run_id, "running")

            detail = service.run_detail(run_id)
            self.assertEqual(detail["status"], "running")
            self.assertEqual(detail["output"]["phase"], "received")
            self.assertEqual(detail["steps"][0]["step_id"], "run_live_step_001")

            service.complete_run(run_id, {"phase": "completed"})
            completed = service.run_detail(run_id)
            self.assertEqual(completed["status"], "completed")
            self.assertIsNotNone(completed["completed_at"])
            self.assertEqual(completed["output"]["phase"], "completed")

    def test_service_records_workflow_checkpoints(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            service = RunService(root)
            service.start_run(
                task_type="skill_generate",
                title="Generate Skill",
                input_data={"input": "create a skill"},
                run_id="run_workflow",
            )

            service.record_workflow_checkpoint(
                "run_workflow",
                workflow_id="skill_generation_workflow",
                step_name="parse_requirement",
                state={"status": "running", "step": "parse_requirement"},
            )

            checkpoints = service.repository.list_workflow_checkpoints("run_workflow")
            detail = service.run_detail("run_workflow")
            self.assertEqual(len(checkpoints), 1)
            self.assertEqual(checkpoints[0].workflow_id, "skill_generation_workflow")
            self.assertEqual(checkpoints[0].step_name, "parse_requirement")
            self.assertEqual(checkpoints[0].state["step"], "parse_requirement")
            self.assertEqual(detail["workflow_checkpoints"][0]["workflow_id"], "skill_generation_workflow")


if __name__ == "__main__":
    unittest.main()
