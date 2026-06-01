import unittest

from agentforge.skill_generator.skill_schema import REQUIRED_SECTIONS, validate_skill


class SkillSchemaTest(unittest.TestCase):
    def test_validates_required_sections(self):
        markdown = "# Example Skill\n\n" + "\n\n".join(f"## {section}\n\nContent" for section in REQUIRED_SECTIONS)

        result = validate_skill(markdown)

        self.assertTrue(result.valid)
        self.assertEqual(result.missing_sections, [])

    def test_reports_missing_sections(self):
        markdown = "# Broken Skill\n\n## Purpose\n\nOnly one section."

        result = validate_skill(markdown)

        self.assertFalse(result.valid)
        self.assertIn("When to Use", result.missing_sections)
        self.assertIn("Version Notes", result.missing_sections)


if __name__ == "__main__":
    unittest.main()
