import json
import tempfile
import unittest
from pathlib import Path

from agentforge.agent.harness import AgentHarness


class FailingLLMClient:
    def complete(self, prompt, system_prompt=None):
        raise RuntimeError("provider unavailable")

    def metadata(self):
        return {"provider": "fake", "model": "fake"}


class AgentHarnessTest(unittest.TestCase):
    def test_chat_runs_selected_skill_and_writes_trace_and_memory(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_skill(root)

            result = AgentHarness(project_root=root).chat("Review dashboard layout readability.")

            self.assertIn("AgentForge Response", result.response)
            self.assertTrue(result.trace_path.exists())
            self.assertTrue(result.run.run_id.startswith("run_"))
            self.assertEqual(result.stop_reason, "completed")
            self.assertIn("triggered", result.reflection)
            self.assertTrue(any(step.name == "observe_execution" for step in result.run.steps))
            self.assertTrue(any(step.name == "reflect" for step in result.run.steps))
            self.assertEqual(result.intent.intent_type, "run_skill")
            self.assertIsNotNone(result.execution.run_result)
            self.assertIsNotNone(result.execution.selected_skill)
            self.assertGreater(result.hqs.average_score, 0)
            self.assertTrue((root / "data" / "memory" / "episodes.jsonl").exists())

            trace = json.loads(result.trace_path.read_text(encoding="utf-8"))
            self.assertEqual(trace["type"], "agent_chat")
            self.assertEqual(trace["run"]["run_id"], result.run.run_id)
            self.assertEqual(trace["output"]["episode_id"], result.episode["episode_id"])
            self.assertIn("system_hqs", trace["output"])
            self.assertIn("system_hqs", trace)

    def test_low_hqs_records_reinforcement_recommendation_without_taskset(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_skill(root)

            result = AgentHarness(project_root=root, response_hqs_threshold=5.1).chat("Review dashboard layout.")

            self.assertTrue(result.reinforcement["triggered"])
            self.assertEqual(result.reinforcement["status"], "recommended")
            step_names = [step.name for step in result.run.steps]
            self.assertIn("hqs_gate", step_names)
            self.assertIn("replan_response", step_names)
            self.assertIn("Quality Gate", result.response)

    def test_provider_generation_failure_falls_back_to_local_generation(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)

            result = AgentHarness(project_root=root, llm_client=FailingLLMClient()).chat("Please generate Skill for UI review.")

            self.assertIn("Generated Skill", result.response)
            self.assertIsNotNone(result.execution.generated_skill)
            self.assertTrue(any(error.get("error_type") == "ProviderFallback" for error in result.execution.errors))
            self.assertIn("Provider failed", result.response)


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
