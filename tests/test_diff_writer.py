import unittest

from agentforge.skill_evolver.diff_writer import create_unified_diff


class DiffWriterTest(unittest.TestCase):
    def test_unified_diff_headers_and_hunks_are_on_separate_lines(self):
        diff = create_unified_diff(
            "# Skill\n\nold\n",
            "# Skill\n\nnew\n",
            "skill/v1/SKILL.md",
            "skill/v2/SKILL.md",
        )

        lines = diff.splitlines()
        self.assertEqual(lines[0], "--- skill/v1/SKILL.md")
        self.assertEqual(lines[1], "+++ skill/v2/SKILL.md")
        self.assertTrue(lines[2].startswith("@@ "))
        self.assertIn("-old", lines)
        self.assertIn("+new", lines)


if __name__ == "__main__":
    unittest.main()
