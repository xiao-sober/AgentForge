import tempfile
import unittest
from pathlib import Path

from agentforge.skill_generator.requirement_parser import parse_requirement
from agentforge.skill_generator.skill_writer import write_skill


class SkillWriterTest(unittest.TestCase):
    def test_writes_skill_to_v1(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            requirement = parse_requirement("帮我做一个能根据网页截图分析 UI 问题并给出优化建议的 Skill")

            written = write_skill(requirement, root)

            self.assertEqual(written.skill_path, root / "skills" / "ui_review_skill" / "v1" / "SKILL.md")
            self.assertTrue(written.skill_path.exists())
            self.assertTrue(written.validation_result.valid)
            self.assertIn(
                "No concrete Skill execution example was provided",
                written.skill_path.read_text(encoding="utf-8"),
            )

    def test_does_not_overwrite_existing_version(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            requirement = parse_requirement("帮我做一个能根据网页截图分析 UI 问题并给出优化建议的 Skill")

            first = write_skill(requirement, root)
            second = write_skill(requirement, root)

            self.assertEqual(first.version, "v1")
            self.assertEqual(second.version, "v2")
            self.assertTrue(first.skill_path.exists())
            self.assertTrue(second.skill_path.exists())


if __name__ == "__main__":
    unittest.main()
