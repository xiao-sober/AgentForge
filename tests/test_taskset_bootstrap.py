import json
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from agentforge.cli import main
from agentforge.skill_evolver.taskset_bootstrap import create_taskset_from_skill


class TasksetBootstrapTest(unittest.TestCase):
    def test_creates_ui_taskset_from_skill(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            skill_path = _write_skill(root)
            taskset_path = root / "tasksets" / "auto_ui.json"

            created = create_taskset_from_skill(skill_path, taskset_path)

            payload = json.loads(created.read_text(encoding="utf-8"))
            self.assertEqual(payload["name"], "auto_ui")
            self.assertEqual(payload["metadata"]["source_skill_slug"], "ui_review_skill")
            self.assertEqual(payload["metadata"]["status"], "starter")
            self.assertTrue(payload["metadata"]["review_required"])
            self.assertEqual(len(payload["tasks"]), 2)
            self.assertEqual(payload["tasks"][0]["id"], "dashboard_layout")

    def test_cli_auto_create_taskset_then_evolves(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            skill_path = _write_skill(root)
            taskset_path = root / "tasksets" / "generated_basic.json"

            with redirect_stdout(StringIO()):
                exit_code = main(
                    [
                        "evolve-skill",
                        "--skill",
                        str(skill_path),
                        "--taskset",
                        str(taskset_path),
                        "--project-root",
                        str(root),
                        "--max-iterations",
                        "1",
                        "--min-improvement",
                        "0",
                        "--auto-create-taskset",
                        "--json",
                    ]
                )

            self.assertEqual(exit_code, 0)
            self.assertTrue(taskset_path.exists())
            self.assertTrue((root / "skills" / "ui_review_skill" / "v2" / "SKILL.md").exists())


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
