import tempfile
import unittest
from pathlib import Path

from agentforge.skill_evolver.version_manager import (
    list_skill_versions,
    next_skill_path,
    next_version,
    parse_skill_version_path,
    write_next_skill_version,
)


class VersionManagerTest(unittest.TestCase):
    def test_finds_next_version_without_overwriting(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            v1 = root / "skills" / "ui_review_skill" / "v1" / "SKILL.md"
            v2 = root / "skills" / "ui_review_skill" / "v2" / "SKILL.md"
            v1.parent.mkdir(parents=True)
            v2.parent.mkdir(parents=True)
            v1.write_text(_skill_markdown("v1"), encoding="utf-8")
            v2.write_text(_skill_markdown("v2"), encoding="utf-8")

            info = parse_skill_version_path(v1)

            self.assertEqual(info.skill_slug, "ui_review_skill")
            self.assertEqual(list_skill_versions(v1.parent.parent), ["v1", "v2"])
            self.assertEqual(next_version(v1), "v3")
            self.assertEqual(next_skill_path(v1), root / "skills" / "ui_review_skill" / "v3" / "SKILL.md")

    def test_writes_next_skill_version_metadata(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            v1 = root / "skills" / "ui_review_skill" / "v1" / "SKILL.md"
            v1.parent.mkdir(parents=True)
            v1.write_text(_skill_markdown("v1"), encoding="utf-8")

            written = write_next_skill_version(v1, _skill_markdown("v2"), {"reason": "test"})

            self.assertEqual(written.version, "v2")
            self.assertTrue(written.skill_path.exists())
            self.assertTrue(written.metadata_path.exists())
            self.assertTrue(v1.exists())


def _skill_markdown(version):
    return f"""# UI Review Skill

## Purpose

Review UI.

## When to Use

When reviewing UI.

## Inputs

- input

## Outputs

- output

## Workflow

1. Review.

## Constraints

- Do not invent facts.

## Quality Criteria

- Be specific.

## Failure Modes

- Generic output.

## Examples

- Review a dashboard.

## Version Notes

- {version}: Test version.
"""


if __name__ == "__main__":
    unittest.main()
