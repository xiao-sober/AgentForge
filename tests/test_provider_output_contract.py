import json
import tempfile
import unittest
from pathlib import Path

from agentforge.skill_evolver.skill_runner import run_skill


class LooseProviderClient:
    def complete(self, prompt, system_prompt=None):
        return "# Provider Skill Output\n\n- provider path used"

    def metadata(self):
        return {"provider": "fake", "model": "fake"}


class ProviderOutputContractTest(unittest.TestCase):
    def test_provider_skill_run_output_is_wrapped_to_contract(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            skill_path = _write_skill(root)

            result = run_skill(
                skill_path,
                "Review a dashboard with dense KPI cards.",
                project_root=root,
                llm_client=LooseProviderClient(),
            )

            output = result.outputs[0]
            self.assertIn("# Skill Run Output", output.output)
            self.assertIn("Provider Skill Output", output.output)
            self.assertTrue(output.output_contract["valid"])
            self.assertTrue(output.output_contract["repaired"])
            self.assertEqual(output.output_contract["contract"], "skill_run_output.v1")

            payload = json.loads(result.result_path.read_text(encoding="utf-8"))
            self.assertTrue(payload["outputs"][0]["output_contract"]["repaired"])


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
