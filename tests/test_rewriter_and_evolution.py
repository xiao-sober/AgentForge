import json
import tempfile
import unittest
from pathlib import Path

from agentforge.skill_evolver.evolution_loop import evolve_skill
from agentforge.skill_evolver.hqs_evaluator import HQSReport, evaluate_output
from agentforge.skill_evolver.reflector import build_reflection_report
from agentforge.skill_evolver.rewriter import rewrite_skill
from agentforge.skill_evolver.task_loader import Task, TaskSet
from agentforge.skill_generator.skill_schema import validate_skill


class RewriterAndEvolutionTest(unittest.TestCase):
    def test_rewriter_creates_valid_next_version(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            skill_path = _write_skill(root)
            taskset = TaskSet(name="basic", tasks=[Task(task_id="task_001", input="Review dashboard readability.")])
            evaluation = evaluate_output(taskset.tasks[0], "Short output.")
            report = HQSReport(
                dimensions=list(evaluation.scores.keys()),
                average_score=evaluation.average,
                per_task=[evaluation],
            )
            reflection = build_reflection_report(taskset, report)

            rewritten = rewrite_skill(skill_path, reflection, report)

            self.assertEqual(rewritten.version, "v2")
            self.assertTrue(rewritten.skill_path.exists())
            self.assertTrue(rewritten.metadata_path.exists())
            self.assertTrue(rewritten.diff_path.exists())
            self.assertTrue(validate_skill(rewritten.skill_path.read_text(encoding="utf-8")).valid)
            self.assertTrue(skill_path.exists())

    def test_evolution_loop_writes_run_evaluation_reflection_and_next_version(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            skill_path = _write_skill(root)
            taskset_path = root / "tasksets" / "ui_review_basic.json"
            taskset_path.parent.mkdir(parents=True)
            taskset_path.write_text(
                json.dumps(
                    {
                        "name": "ui_review_basic",
                        "tasks": [
                            {
                                "id": "dashboard_layout",
                                "input": "Review dashboard layout, visual hierarchy, and data readability.",
                                "expected_output": ["issues", "reasons", "recommendations"],
                                "criteria": ["structured report", "specific suggestions"],
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            result = evolve_skill(skill_path, taskset_path, project_root=root, max_iterations=1, min_improvement=0.0)

            self.assertEqual(result.stop_reason, "max_iterations")
            self.assertEqual(len(result.iterations), 1)
            iteration = result.iterations[0]
            self.assertTrue(iteration.run_result.result_path.exists())
            self.assertTrue(iteration.hqs_report_path.exists())
            self.assertTrue(iteration.reflection_path.exists())
            self.assertEqual(iteration.decision, "accepted")
            self.assertIsNotNone(iteration.candidate_hqs_report)
            self.assertIsNotNone(iteration.rewritten_skill)
            self.assertTrue(iteration.rewritten_skill.skill_path.exists())
            self.assertEqual(iteration.rewritten_skill.version, "v2")
            self.assertTrue(result.trace_path.exists())
            self.assertTrue((root / "traces").exists())

    def test_evolution_rejects_candidate_without_minimum_improvement_by_default(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            skill_path = _write_skill(root)
            taskset_path = root / "tasksets" / "ui_review_basic.json"
            taskset_path.parent.mkdir(parents=True)
            taskset_path.write_text(
                json.dumps(
                    {
                        "name": "ui_review_basic",
                        "tasks": [
                            {
                                "id": "dashboard_layout",
                                "input": "Review dashboard layout, visual hierarchy, and data readability.",
                                "expected_output": ["issues", "reasons", "recommendations"],
                                "criteria": ["structured report", "specific suggestions"],
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            result = evolve_skill(skill_path, taskset_path, project_root=root, max_iterations=1)

            self.assertEqual(result.stop_reason, "minimum_improvement_not_met")
            self.assertEqual(result.final_skill_path, skill_path.resolve())
            iteration = result.iterations[0]
            self.assertEqual(iteration.decision, "rejected_minimum_improvement_not_met")
            self.assertIsNone(iteration.rewritten_skill)
            self.assertIsNotNone(iteration.candidate_path)
            self.assertTrue(iteration.candidate_path.exists())
            self.assertFalse((root / "skills" / "ui_review_skill" / "v2" / "SKILL.md").exists())


def _write_skill(root: Path) -> Path:
    skill_path = root / "skills" / "ui_review_skill" / "v1" / "SKILL.md"
    skill_path.parent.mkdir(parents=True)
    skill_path.write_text(
        """# UI Review Skill

## Purpose

Analyze UI screenshots or page descriptions and produce structured improvement advice.

## When to Use

Use for dashboard and admin page UI review.

## Inputs

- screenshot
- page context

## Outputs

- issues
- reasons
- optimization suggestions
- structured report

## Workflow

1. Identify the available input.
2. Extract visible UI areas and data elements.
3. Analyze layout, hierarchy, interactions, and data readability.
4. List issues with reasons and suggestions.

## Constraints

- Do not invent facts, UI elements, or data that are not provided.
- Prefer concrete guidance over generic advice.

## Quality Criteria

- Output follows the requested structure.
- Advice is specific enough to act on.

## Failure Modes

- Input is too vague to support a specific recommendation.
- Output ignores the required structure.

## Examples

- Analyze a dashboard screenshot.

## Version Notes

- v1: Initial test Skill.
""",
        encoding="utf-8",
    )
    return skill_path


if __name__ == "__main__":
    unittest.main()
