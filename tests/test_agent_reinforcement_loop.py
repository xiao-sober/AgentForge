import json
import tempfile
import unittest
from pathlib import Path

from agentforge.agent.harness import AgentHarness


class AgentReinforcementLoopTest(unittest.TestCase):
    def test_low_hqs_with_taskset_runs_bounded_reinforcement_and_updates_memory(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_skill(root)
            taskset_path = _write_taskset(root)

            result = AgentHarness(
                project_root=root,
                response_hqs_threshold=5.1,
                reinforcement_taskset_path=taskset_path,
                reinforcement_max_iterations=1,
            ).chat("Review dashboard layout then propose concrete fixes.")

            self.assertIn(result.reinforcement["status"], {"evolved", "evaluated_no_change"})
            self.assertTrue(result.reinforcement["stable"])
            self.assertIn("evolution", result.reinforcement)
            self.assertEqual(result.reinforcement["taskset_path"], str(taskset_path))
            step_names = [step.name for step in result.run.steps]
            self.assertIn("run_reinforcement_evolution", step_names)
            self.assertIn("write_reinforcement_memory", step_names)

            semantic_path = root / "data" / "memory" / "semantic_memory.json"
            semantic = json.loads(semantic_path.read_text(encoding="utf-8"))
            record = semantic["ui_review_skill"]
            self.assertEqual(record["last_reinforcement"]["taskset_path"], str(taskset_path))
            self.assertEqual(record["last_reinforcement"]["status"], result.reinforcement["status"])
            self.assertIn("last_reinforcement", record)


def _write_taskset(root: Path) -> Path:
    taskset_path = root / "tasksets" / "reinforcement_ui_review.json"
    taskset_path.parent.mkdir(parents=True)
    taskset_path.write_text(
        json.dumps(
            {
                "name": "reinforcement_ui_review",
                "description": "Small taskset for deterministic reinforcement tests.",
                "tasks": [
                    {
                        "id": "dashboard_readability",
                        "input": "Review a dashboard with dense KPI cards, a crowded table, weak empty states, and unclear filters.",
                        "criteria": ["specific findings", "risk control", "actionable fixes"],
                    }
                ],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return taskset_path


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
2. Analyze layout and readability.

## Constraints

- Do not invent facts, UI elements, or data that are not provided.

## Quality Criteria

- Advice is specific enough to act on.

## Failure Modes

- Input is too vague to support a specific recommendation.

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
