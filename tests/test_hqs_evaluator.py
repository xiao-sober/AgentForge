import tempfile
import unittest
from pathlib import Path

from agentforge.skill_evolver.hqs_evaluator import SKILL_HQS_DIMENSIONS, evaluate_taskset, write_hqs_report
from agentforge.skill_evolver.skill_runner import TaskOutput
from agentforge.skill_evolver.task_loader import Task, TaskSet


class HQSEvaluatorTest(unittest.TestCase):
    def test_evaluates_taskset_with_structured_json_shape(self):
        taskset = TaskSet(
            name="basic",
            tasks=[
                Task(
                    task_id="task_001",
                    input="Review dashboard layout readability.",
                    expected_output=["layout issue", "recommendation"],
                    criteria=["structured report"],
                )
            ],
        )
        outputs = [
            TaskOutput(
                task_id="task_001",
                input=taskset.tasks[0].input,
                output="""# Skill Run Output

## Task

Review dashboard layout readability.

## Result

- Specific layout issue with evidence.
- Concrete recommendation and next step.

## Assumptions and Gaps

- Do not invent facts beyond the provided input.
""",
            )
        ]

        report = evaluate_taskset(taskset, outputs)

        self.assertEqual(report.dimensions, SKILL_HQS_DIMENSIONS)
        self.assertEqual(len(report.per_task), 1)
        self.assertGreater(report.average_score, 0)
        for dimension in SKILL_HQS_DIMENSIONS:
            self.assertIn(dimension, report.per_task[0].scores)
            self.assertGreaterEqual(report.per_task[0].scores[dimension], 0)
            self.assertLessEqual(report.per_task[0].scores[dimension], 5)

    def test_writes_hqs_report_json(self):
        taskset = TaskSet(name="basic", tasks=[Task(task_id="task_001", input="Run the Skill.")])
        report = evaluate_taskset(taskset, [TaskOutput(task_id="task_001", input="Run the Skill.", output="Done.")])

        with tempfile.TemporaryDirectory() as temp_dir:
            path = write_hqs_report(Path(temp_dir) / "hqs_report.json", report)

            self.assertTrue(path.exists())
            self.assertIn("average_score", path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
