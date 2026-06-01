import json
import tempfile
import unittest
from pathlib import Path

from agentforge.skill_evolver.task_loader import load_taskset


class TaskLoaderTest(unittest.TestCase):
    def test_loads_json_taskset(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "ui_review_basic.json"
            path.write_text(
                json.dumps(
                    {
                        "name": "ui_review_basic",
                        "description": "Basic UI review cases.",
                        "tasks": [
                            {
                                "id": "dashboard_layout",
                                "input": "Review a dashboard layout for hierarchy and readability.",
                                "expected_output": ["issues", "recommendations"],
                                "criteria": ["structured report"],
                                "tag": "ui",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            taskset = load_taskset(path)

            self.assertEqual(taskset.name, "ui_review_basic")
            self.assertEqual(len(taskset.tasks), 1)
            self.assertEqual(taskset.tasks[0].task_id, "dashboard_layout")
            self.assertIn("dashboard layout", taskset.tasks[0].input)
            self.assertEqual(taskset.tasks[0].criteria, ["structured report"])
            self.assertEqual(taskset.tasks[0].metadata, {"tag": "ui"})
            self.assertEqual(taskset.metadata, {})

    def test_loads_plain_task_list(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "tasks.json"
            path.write_text(json.dumps(["Summarize the API requirement."]), encoding="utf-8")

            taskset = load_taskset(path)

            self.assertEqual(taskset.name, "tasks")
            self.assertEqual(taskset.tasks[0].task_id, "task_001")
            self.assertEqual(taskset.tasks[0].input, "Summarize the API requirement.")

    def test_rejects_duplicate_task_ids(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "tasks.json"
            path.write_text(
                json.dumps(
                    {
                        "tasks": [
                            {"id": "same", "input": "First task."},
                            {"id": "same", "input": "Second task."},
                        ]
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaises(ValueError) as context:
                load_taskset(path)

            self.assertIn("duplicate task ids", str(context.exception))


if __name__ == "__main__":
    unittest.main()
