import tempfile
import unittest
from pathlib import Path

from agentforge.agent.intent_parser import parse_intent
from agentforge.agent.skill_selector import select_skill
from agentforge.memory.memory_manager import MemoryManager


class SkillSelectorTest(unittest.TestCase):
    def test_semantic_best_version_can_select_non_latest_skill(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_skill(root / "skills" / "ui_review_skill" / "v1" / "SKILL.md", version_note="v1")
            _write_skill(root / "skills" / "ui_review_skill" / "v2" / "SKILL.md", version_note="v2")
            MemoryManager(root, trace_updates=False).upsert_semantic_memory(
                "ui_review_skill",
                {"summary": "UI Review Skill", "best_version": "v1", "tags": ["ui", "review", "dashboard"]},
            )

            candidate = select_skill(parse_intent("Review dashboard layout readability."), project_root=root)

            self.assertIsNotNone(candidate)
            self.assertEqual(candidate.version, "v1")

    def test_api_hint_selects_api_skill_over_ui_skill(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_skill(root / "skills" / "ui_review_skill" / "v1" / "SKILL.md", version_note="v1")
            _write_api_skill(root / "skills" / "api_design_skill" / "v2" / "SKILL.md")

            candidate = select_skill(
                parse_intent("Analyze API JSON output for quality score fields and warnings."),
                project_root=root,
            )

            self.assertIsNotNone(candidate)
            self.assertEqual(candidate.skill_slug, "api_design_skill")
            self.assertEqual(candidate.version, "v2")


def _write_skill(skill_path: Path, version_note: str) -> Path:
    skill_path.parent.mkdir(parents=True)
    skill_path.write_text(
        f"""# UI Review Skill

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

- {version_note}: Test Skill.
""",
        encoding="utf-8",
    )
    return skill_path


def _write_api_skill(skill_path: Path) -> Path:
    skill_path.parent.mkdir(parents=True)
    skill_path.write_text(
        """# API Design Skill

## Purpose

Review API contracts, JSON responses, schema fields, quality score payloads, and actionable error messages.

## When to Use

Use for API response review, endpoint design, trace link fields, HQS payloads, and memory retrieval summaries.

## Inputs

- API endpoint description
- JSON response
- schema fields

## Outputs

- missing fields
- contract risks
- response structure recommendations

## Workflow

1. Identify required response fields.
2. Check field names, types, and error shapes.
3. Review quality score and memory retrieval summaries.
4. Return concrete contract fixes.

## Constraints

- Do not invent fields that are not required by the task.
- Prefer explicit field names and JSON-safe examples.

## Quality Criteria

- Findings are tied to supplied API fields.
- Recommendations are actionable.

## Failure Modes

- Input lacks response fields.
- Output gives generic API advice.

## Examples

- Review an API JSON response with hqs and warnings.

## Version Notes

- v2: Test API Skill.
""",
        encoding="utf-8",
    )
    return skill_path


if __name__ == "__main__":
    unittest.main()
