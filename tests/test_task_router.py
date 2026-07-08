import tempfile
import unittest
from pathlib import Path

from agentforge.common.trace import write_trace
from agentforge.runs.service import RunService
from agentforge.tasks import TaskRequest, list_task_types, route_task


class TaskRouterTest(unittest.TestCase):
    def test_lists_executable_task_types(self):
        task_types = {item["task_type"]: item for item in list_task_types()}

        self.assertIn("skill_generate", task_types)
        self.assertIn("trace_diagnosis", task_types)
        self.assertIn("code_analysis", task_types)
        self.assertTrue(task_types["code_analysis"]["stable"])
        self.assertIn("document_analysis", task_types)
        self.assertTrue(task_types["document_analysis"]["stable"])
        self.assertIn("data_analysis", task_types)
        self.assertTrue(task_types["data_analysis"]["stable"])

    def test_trace_diagnosis_task_creates_run_trace_and_checkpoints(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source_trace = write_trace(
                project_root=root,
                trace_type="agent_chat",
                input_data={"message": "hello"},
                output={"response": "ok"},
                steps=[{"name": "receive_input", "status": "completed"}],
                artifacts=[],
                errors=[],
            )

            result = route_task(
                TaskRequest(
                    task_type="trace_diagnosis",
                    input={"trace_file": source_trace.name},
                ),
                project_root=root,
            )

            self.assertEqual(result.status, "completed")
            self.assertEqual(result.output["diagnosis"]["trace_type"], "agent_chat")
            self.assertTrue(result.output["diagnosis"]["schema_valid"])
            self.assertTrue(result.run_id.startswith("run_"))
            self.assertTrue(result.trace_path.exists())
            detail = RunService(root).run_detail(result.run_id)
            self.assertEqual(detail["task_type"], "trace_diagnosis")
            self.assertTrue(detail["steps"])
            self.assertTrue(detail["workflow_checkpoints"])

    def test_trace_diagnosis_can_resolve_trace_from_run_id(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source_trace = write_trace(
                project_root=root,
                trace_type="agent_chat",
                input_data={"message": "hello"},
                output={"response": "ok"},
                steps=[{"name": "receive_input", "status": "completed"}],
                artifacts=[],
                errors=[],
            )
            service = RunService(root)
            service.record_run(
                task_type="agent_chat",
                title="Agent chat",
                input_data={"message": "hello"},
                output_data={"response": "ok"},
                trace_path=source_trace,
                status="completed",
                run_id="run_source",
            )

            result = route_task(
                TaskRequest(
                    task_type="trace_diagnosis",
                    input={"run_id": "run_source"},
                ),
                project_root=root,
            )

            self.assertEqual(result.status, "completed")
            self.assertEqual(result.output["inspected_trace"], f"traces/{source_trace.name}")

    def test_code_analysis_analyzes_inline_python_and_records_run(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            code = """def run(value):
    try:
        return eval(value)
    except Exception:
        return None
"""

            result = route_task(
                TaskRequest(
                    task_type="code_analysis",
                    input={"input": f"```python\n{code}```"},
                ),
                project_root=root,
            )

            self.assertEqual(result.status, "completed")
            self.assertEqual(result.task_type, "code_analysis")
            self.assertTrue(result.trace_path.exists())
            analysis = result.output["analysis"]
            self.assertEqual(analysis["summary"]["source_count"], 1)
            self.assertGreaterEqual(analysis["summary"]["high_count"], 1)
            rules = {finding["rule"] for finding in analysis["findings"]}
            self.assertIn("python_eval_exec", rules)
            self.assertIn("broad_exception_handler", rules)
            detail = RunService(root).run_detail(result.run_id)
            self.assertEqual(detail["task_type"], "code_analysis")
            self.assertTrue(detail["workflow_checkpoints"])
            self.assertEqual(detail["steps"][0]["input"]["attempt"], 1)
            self.assertIn("workflow_input", detail["steps"][0]["input"])

    def test_code_analysis_can_read_project_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            sample = root / "src" / "sample.py"
            sample.parent.mkdir(parents=True)
            sample.write_text("password = 'secret'\n", encoding="utf-8")

            result = route_task(
                TaskRequest(task_type="code_analysis", input={"path": "src/sample.py"}),
                project_root=root,
            )

            self.assertEqual(result.status, "completed")
            self.assertEqual(result.output["sources"][0]["path"], "src/sample.py")
            self.assertTrue(any(finding["rule"] == "secret_keyword_assignment" for finding in result.output["analysis"]["findings"]))

    def test_document_analysis_analyzes_markdown_and_records_run(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            markdown = """# Release Notes

TODO: fill this in before publishing.

## Scope

This document explains the release scope and rollout plan.
"""

            result = route_task(
                TaskRequest(task_type="document_analysis", input={"input": markdown}),
                project_root=root,
            )

            self.assertEqual(result.status, "completed")
            self.assertEqual(result.output["analysis"]["summary"]["document_count"], 1)
            self.assertGreaterEqual(result.output["analysis"]["summary"]["heading_count"], 2)
            rules = {finding["rule"] for finding in result.output["analysis"]["findings"]}
            self.assertIn("placeholder_text", rules)
            detail = RunService(root).run_detail(result.run_id)
            self.assertEqual(detail["task_type"], "document_analysis")
            self.assertTrue(detail["workflow_checkpoints"])
            self.assertEqual(detail["steps"][0]["input"]["attempt"], 1)
            self.assertIn("workflow_input", detail["steps"][0]["input"])

    def test_data_analysis_profiles_inline_csv_and_records_run(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            csv_text = "name,score,active\nAda,10,true\nBob,,false\n"

            result = route_task(
                TaskRequest(task_type="data_analysis", input={"input": csv_text}),
                project_root=root,
            )

            self.assertEqual(result.status, "completed")
            summary = result.output["analysis"]["summary"]
            self.assertEqual(summary["source_count"], 1)
            self.assertEqual(summary["row_count"], 2)
            self.assertEqual(summary["column_count"], 3)
            self.assertEqual(summary["missing_value_count"], 1)
            rules = {finding["rule"] for finding in result.output["analysis"]["findings"]}
            self.assertIn("missing_values", rules)
            detail = RunService(root).run_detail(result.run_id)
            self.assertEqual(detail["task_type"], "data_analysis")
            self.assertTrue(detail["workflow_checkpoints"])
            self.assertEqual(detail["steps"][0]["input"]["attempt"], 1)
            self.assertIn("workflow_input", detail["steps"][0]["input"])

    def test_schema_validation_rejects_invalid_input_shape(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaisesRegex(ValueError, "input.paths must be array"):
                route_task(
                    TaskRequest(task_type="code_analysis", input={"paths": "src/sample.py"}),
                    project_root=Path(temp_dir),
                )

    def test_schema_validation_rejects_nested_items_and_enums(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            with self.assertRaisesRegex(ValueError, r"input.paths\[0\] must be string"):
                route_task(
                    TaskRequest(task_type="document_analysis", input={"paths": [123]}),
                    project_root=root,
                )
            with self.assertRaisesRegex(ValueError, "input.format must be one of"):
                route_task(
                    TaskRequest(task_type="data_analysis", input={"input": "a,b\n1,2\n", "format": "xlsx"}),
                    project_root=root,
                )

    def test_unsupported_task_type_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaises(ValueError):
                route_task(TaskRequest(task_type="unknown_task"), project_root=Path(temp_dir))


if __name__ == "__main__":
    unittest.main()
