import json
import tempfile
import unittest
from pathlib import Path

from agentforge.agent.harness import AgentHarness
from agentforge.common.trace import write_trace


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
            self.assertEqual(result.run.phase, "completed")
            self.assertIn("phase_history", result.run.to_dict())
            self.assertTrue(any(item["phase"] == "planned" for item in result.run.phase_history))
            self.assertTrue(any(item["phase"] == "executing" for item in result.run.phase_history))
            plan_steps = result.plan.to_dict()["steps"]
            self.assertTrue(plan_steps)
            self.assertTrue(all(step["status"] == "completed" for step in plan_steps))
            self.assertGreater(result.hqs.average_score, 0)
            self.assertTrue((root / "data" / "memory" / "episodes.jsonl").exists())

            trace = json.loads(result.trace_path.read_text(encoding="utf-8"))
            self.assertEqual(trace["type"], "agent_chat")
            self.assertEqual(trace["run"]["run_id"], result.run.run_id)
            self.assertEqual(trace["run"]["phase"], "completed")
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

    def test_provider_generation_failure_stops_without_local_fallback(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)

            result = AgentHarness(project_root=root, llm_client=FailingLLMClient()).chat("Please generate Skill for UI review.")

            self.assertIn("could not complete", result.response)
            self.assertIsNone(result.execution.generated_skill)
            self.assertEqual(result.execution.execution_state["status"], "failed")
            self.assertTrue(any(error.get("error_type") == "RuntimeError" for error in result.execution.errors))
            self.assertEqual(result.stop_reason, "blocking_error")

    def test_generate_and_run_updates_each_plan_step_status(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)

            result = AgentHarness(project_root=root).chat(
                "Review dashboard layout then summarize accessibility risks then propose concrete fixes."
            )

            self.assertEqual(result.plan.action, "generate_and_run_skill")
            plan_steps = result.plan.to_dict()["steps"]
            self.assertGreaterEqual(len(result.execution.plan_step_results), 4)
            self.assertEqual(result.execution.execution_state["status"], "completed")
            self.assertGreaterEqual(len(result.execution.run_results), 3)
            self.assertTrue(all(step["status"] == "completed" for step in plan_steps))
            self.assertEqual(plan_steps[0]["name"], "generate_skill")
            self.assertEqual(plan_steps[0]["status"], "completed")
            self.assertTrue(any(step["name"].startswith("run_skill_subtask") for step in plan_steps))

    def test_chat_routes_trace_diagnosis_through_task_router(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_trace(
                project_root=root,
                trace_type="agent_chat",
                input_data={"message": "hello"},
                output={"response": "ok"},
                steps=[{"name": "receive_input", "status": "completed"}],
                artifacts=[],
                errors=[],
            )

            result = AgentHarness(project_root=root).chat("Inspect the latest trace.")

            self.assertEqual(result.intent.task_type, "trace_diagnosis")
            self.assertEqual(result.plan.action, "route_task")
            self.assertIsNotNone(result.execution.task_result)
            self.assertEqual(result.execution.task_result.task_type, "trace_diagnosis")
            self.assertEqual(result.execution.task_result.status, "completed")
            self.assertIn("Task Router", result.response)
            self.assertIn("Trace Diagnosis", result.response)

    def test_chat_routes_code_analysis_through_task_router(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)

            result = AgentHarness(project_root=root).chat(
                "Analyze this Python function for edge cases.\n```python\ndef run(value):\n    return eval(value)\n```"
            )

            self.assertEqual(result.intent.intent_type, "reserved_task")
            self.assertEqual(result.intent.task_type, "code_analysis")
            self.assertEqual(result.plan.action, "route_task")
            self.assertIsNotNone(result.execution.task_result)
            self.assertEqual(result.execution.task_result.task_type, "code_analysis")
            self.assertEqual(result.execution.task_result.status, "completed")
            self.assertIn("Code Analysis", result.response)
            self.assertIn("python_eval_exec", str(result.execution.task_result.output["analysis"]["findings"]))


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
