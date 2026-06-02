import tempfile
import unittest
from pathlib import Path

from agentforge.memory.memory_manager import MemoryManager


class MemoryManagerTest(unittest.TestCase):
    def test_writes_and_retrieves_three_memory_layers(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            memory = MemoryManager(root, trace_updates=False)

            working = memory.add_working_memory({"active_skill": "ui_review_skill"})
            episode = memory.save_episode({"user_input": "Review dashboard layout.", "response": "Done."})
            semantic = memory.upsert_semantic_memory(
                "ui_review_skill",
                {"summary": "UI Review Skill", "tags": ["ui", "review"]},
            )

            self.assertEqual(working["active_skill"], "ui_review_skill")
            self.assertTrue(episode["episode_id"].startswith("episode_"))
            self.assertEqual(semantic["best_version"] if "best_version" in semantic else None, None)
            self.assertTrue(memory.paths.working.exists())
            self.assertTrue(memory.paths.episodes.exists())
            self.assertTrue(memory.paths.semantic.exists())

            self.assertEqual(memory.search_episodes("dashboard")[0]["user_input"], "Review dashboard layout.")
            self.assertEqual(memory.search_semantic_memory("ui")[0]["key"], "ui_review_skill")

            context = memory.retrieve_context_for_task("Review UI dashboard.")
            self.assertIn("working_memory", context)
            self.assertEqual(len(context["episodes"]), 1)
            self.assertEqual(len(context["semantic_memory"]), 1)


if __name__ == "__main__":
    unittest.main()
