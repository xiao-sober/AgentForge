import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agentforge.memory.memory_manager import MemoryManager
from agentforge.web.routes import handle_request


class ProviderLLMClient:
    def complete(self, prompt, system_prompt=None):
        return "# Provider Skill Output\n\n- provider path used"

    def metadata(self):
        return {"provider": "fake", "model": "fake"}


class FailingProviderLLMClient:
    def complete(self, prompt, system_prompt=None):
        from agentforge.common.llm_client import LLMProviderError

        raise LLMProviderError("provider unavailable")

    def metadata(self):
        return {"provider": "fake", "model": "fake"}


class WebRoutesTest(unittest.TestCase):
    def test_chat_and_inspection_routes_return_json(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_skill(root)
            _write_frontend_dist(root)

            index = handle_request("GET", "/", project_root=root)
            self.assertEqual(index.status, 200)
            self.assertIn("text/html", index.headers["Content-Type"])
            self.assertIn("AgentForge", index.body().decode("utf-8"))

            chat = handle_request(
                "POST",
                "/chat",
                body=json.dumps({"message": "Review dashboard layout readability."}),
                project_root=root,
            )
            self.assertEqual(chat.status, 200)
            self.assertIn("response", chat.payload)
            self.assertIn("trace_path", chat.payload)
            self.assertIn("trace_url", chat.payload)
            self.assertIn("execution_state", chat.payload)
            self.assertIn("plan_step_results", chat.payload)
            self.assertIn("memory_retrieval", chat.payload)
            self.assertTrue(chat.payload["run_id"].startswith("run_"))
            self.assertEqual(chat.payload["stop_reason"], "completed")
            self.assertIn("triggered", chat.payload["reflection"])
            self.assertTrue(any(step["name"] == "observe_execution" for step in chat.payload["timeline"]))
            self.assertTrue(any(step["name"] == "reflect" for step in chat.payload["timeline"]))
            self.assertNotIn("execution", chat.payload)
            self.assertIn("match_score", chat.payload["selected_skill"])

            debug_chat = handle_request(
                "POST",
                "/chat?debug=1",
                body=json.dumps({"message": "Review dashboard layout readability."}),
                project_root=root,
            )
            self.assertEqual(debug_chat.status, 200)
            self.assertIn("execution", debug_chat.payload)
            self.assertIn("run", debug_chat.payload)
            self.assertTrue(debug_chat.payload["run"]["run_id"].startswith("run_"))
            self.assertIn("trace_url", debug_chat.payload)
            self.assertIn("execution_state", debug_chat.payload)
            self.assertIn("plan_step_results", debug_chat.payload)
            self.assertIn("memory_retrieval", debug_chat.payload)
            self.assertTrue(debug_chat.payload["trace_url"].startswith("/traces/"))

            health = handle_request("GET", "/health", project_root=root)
            self.assertEqual(health.status, 200)
            self.assertEqual(health.payload["status"], "ok")

            version = handle_request("GET", "/version", project_root=root)
            self.assertEqual(version.status, 200)
            self.assertIn("version", version.payload)

            config = handle_request("GET", "/config", project_root=root)
            self.assertEqual(config.status, 200)
            self.assertEqual(config.payload["status"], "local_only")

            skills = handle_request("GET", "/skills", project_root=root)
            self.assertEqual(skills.status, 200)
            self.assertEqual(skills.payload["skills"][0]["skill_slug"], "ui_review_skill")

            skill = handle_request("GET", "/skills/ui_review_skill", project_root=root)
            self.assertEqual(skill.status, 200)

            diff_path = root / "skills" / "ui_review_skill" / "v1" / "diff.patch"
            diff_path.write_text("--- old\n+++ new\n", encoding="utf-8")
            skill_version = handle_request("GET", "/skills/ui_review_skill/v1", project_root=root)
            self.assertEqual(skill_version.status, 200)
            self.assertIn("## Purpose", skill_version.payload["markdown"])
            self.assertIn("+++ new", skill_version.payload["diff"])

            memory = handle_request("GET", "/memory", project_root=root)
            self.assertEqual(memory.status, 200)
            self.assertGreaterEqual(memory.payload["episode_count"], 1)

            traces = handle_request("GET", "/traces", project_root=root)
            self.assertEqual(traces.status, 200)
            self.assertTrue(any(trace["type"] == "agent_chat" for trace in traces.payload["traces"]))

            hqs = handle_request("GET", "/hqs", project_root=root)
            self.assertEqual(hqs.status, 200)
            self.assertIsNotNone(hqs.payload["last_response_hqs"])

            runs = handle_request("GET", "/runs", project_root=root)
            self.assertEqual(runs.status, 200)
            self.assertTrue(any(run["run_id"] == chat.payload["run_id"] for run in runs.payload["runs"]))

            run_detail = handle_request("GET", f"/runs/{chat.payload['run_id']}", project_root=root)
            self.assertEqual(run_detail.status, 200)
            self.assertEqual(run_detail.payload["task_type"], "agent_chat")
            self.assertTrue(run_detail.payload["steps"])

    def test_trace_detail_rejects_path_traversal(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_path = root / "config" / "providers.json"
            config_path.parent.mkdir(parents=True)
            config_path.write_text('{"default_provider":"x","providers":{}}', encoding="utf-8")

            response = handle_request("GET", "/traces/..%2Fconfig%2Fproviders.json", project_root=root)

            self.assertEqual(response.status, 400)
            self.assertIn("single path segment", response.payload["error"])

    def test_trace_listing_marks_invalid_json_without_failing(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            trace_path = root / "traces" / "bad.json"
            trace_path.parent.mkdir(parents=True)
            trace_path.write_text("{", encoding="utf-8")

            response = handle_request("GET", "/traces", project_root=root)

            self.assertEqual(response.status, 200)
            self.assertEqual(response.payload["traces"][0]["filename"], "bad.json")
            self.assertIn("error", response.payload["traces"][0])

    def test_phase_6_tools_routes_return_tool_catalog(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)

            tools = handle_request("GET", "/tools", project_root=root)
            self.assertEqual(tools.status, 200)
            tool_names = {tool["name"] for tool in tools.payload["tools"]}
            self.assertIn("parse_intent", tool_names)
            self.assertIn("execute_plan", tool_names)
            self.assertEqual(tools.payload["count"], len(tools.payload["tools"]))

            detail = handle_request("GET", "/tools/execute_plan", project_root=root)
            self.assertEqual(detail.status, 200)
            self.assertEqual(detail.payload["name"], "execute_plan")
            self.assertEqual(detail.payload["permission_level"], "execute")
            self.assertIn("input_schema", detail.payload)
            self.assertIn("output_schema", detail.payload)

            missing = handle_request("GET", "/tools/not_registered", project_root=root)
            self.assertEqual(missing.status, 404)

    def test_phase_6_memory_routes_return_episodes_and_semantic_memory(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            memory = MemoryManager(root, trace_updates=False)
            episode = memory.save_episode({"user_input": "Review dashboard layout.", "response": "Done."})
            memory.save_episode({"user_input": "Trace diagnosis run.", "response": "Trace ok."})
            memory.upsert_semantic_memory("ui_review_skill", {"summary": "UI review helper", "tags": ["ui"]})

            episodes = handle_request("GET", "/memory/episodes?limit=1", project_root=root)
            self.assertEqual(episodes.status, 200)
            self.assertEqual(episodes.payload["count"], 1)
            self.assertEqual(episodes.payload["total_count"], 2)

            searched = handle_request("GET", "/memory/episodes?q=dashboard", project_root=root)
            self.assertEqual(searched.status, 200)
            self.assertEqual(searched.payload["episodes"][0]["episode_id"], episode["episode_id"])
            self.assertGreater(searched.payload["episodes"][0]["_memory_score"], 0)

            semantic = handle_request("GET", "/memory/semantic?q=ui", project_root=root)
            self.assertEqual(semantic.status, 200)
            self.assertEqual(semantic.payload["semantic_memory"][0]["key"], "ui_review_skill")
            self.assertEqual(semantic.payload["total_count"], 1)

    def test_run_skill_rejects_external_skill_path(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            root = base / "project"
            external = base / "external" / "ui_review_skill" / "v1" / "SKILL.md"
            root.mkdir()
            _write_skill_at(external)

            response = handle_request(
                "POST",
                "/skills/run",
                body=json.dumps({"skill_path": str(external), "input": "Review dashboard layout."}),
                project_root=root,
            )

            self.assertEqual(response.status, 400)
            self.assertIn("Skill path must stay", response.payload["error"])

    def test_sample_skill_detail_routes_are_available_without_local_skill(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_skill_at(root / "examples" / "skills" / "ui_review_skill" / "v1" / "SKILL.md")

            detail = handle_request("GET", "/skills/ui_review_skill", project_root=root)
            version = handle_request("GET", "/skills/ui_review_skill/v1", project_root=root)

            self.assertEqual(detail.status, 200)
            self.assertEqual(detail.payload["source"], "sample")
            self.assertEqual(version.status, 200)
            self.assertEqual(version.payload["source"], "sample")

    def test_chat_uses_default_provider_when_enabled(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_skill(root)
            _write_provider_config(root)

            with patch("agentforge.web.routes.create_llm_client", return_value=ProviderLLMClient()):
                chat = handle_request(
                    "POST",
                    "/chat",
                    body=json.dumps({"message": "Review dashboard layout readability.", "use_provider": True}),
                    project_root=root,
                )

            self.assertEqual(chat.status, 200)
            self.assertIn("Provider Skill Output", chat.payload["response"])

    def test_chat_supports_tool_calling_agent_mode(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_skill(root)

            chat = handle_request(
                "POST",
                "/chat",
                body=json.dumps({"message": "Review dashboard layout readability.", "agent_mode": "tool_calling"}),
                project_root=root,
            )

            self.assertEqual(chat.status, 200)
            self.assertEqual(chat.payload["agent_mode"], "tool_calling_agent")
            self.assertEqual(chat.payload["tool_calling"]["status"], "completed")
            self.assertTrue(chat.payload["trace_url"].startswith("/traces/"))
            self.assertTrue(any(step["name"] == "execute_plan" for step in chat.payload["timeline"]))
            self.assertIn("tool_call_timeline", chat.payload)
            self.assertEqual(chat.payload["parse_repair_count"], 0)
            self.assertEqual(chat.payload["invalid_call_count"], 0)
            self.assertEqual(chat.payload["final_answer_source"], "harness_response")
            self.assertIn("hqs_gate", chat.payload)
            self.assertIn("quality_retry", chat.payload)
            self.assertTrue(any(item["tool_name"] == "build_response" for item in chat.payload["tool_call_timeline"]))

            run_detail = handle_request("GET", f"/agent/runs/{chat.payload['run_id']}", project_root=root)
            self.assertEqual(run_detail.status, 200)
            self.assertEqual(run_detail.payload["run_id"], chat.payload["run_id"])
            self.assertEqual(run_detail.payload["agent_mode"], "tool_calling_agent")
            self.assertTrue(run_detail.payload["tool_call_timeline"])

            tool_calls = handle_request(
                "GET",
                f"/agent/runs/{chat.payload['run_id']}/tool-calls",
                project_root=root,
            )
            self.assertEqual(tool_calls.status, 200)
            self.assertEqual(tool_calls.payload["run_id"], chat.payload["run_id"])
            self.assertEqual(tool_calls.payload["final_answer_source"], "harness_response")
            self.assertTrue(any(item["tool_name"] == "build_response" for item in tool_calls.payload["tool_call_timeline"]))

    def test_chat_surfaces_provider_task_failure_without_fallback(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_skill(root)
            _write_provider_config(root)

            with patch("agentforge.web.routes.create_llm_client", return_value=FailingProviderLLMClient()):
                chat = handle_request(
                    "POST",
                    "/chat",
                    body=json.dumps({"message": "Review dashboard layout readability.", "use_provider": True}),
                    project_root=root,
                )

            self.assertEqual(chat.status, 200)
            self.assertEqual(chat.payload["execution_state"]["status"], "failed")
            self.assertEqual(chat.payload["plan_step_results"][0]["status"], "failed")
            self.assertEqual(chat.payload["warnings"], [])
            self.assertEqual(chat.payload["stop_reason"], "blocking_error")
            self.assertIn("could not complete", chat.payload["response"])

    def test_generate_skill_returns_error_when_provider_fails(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_provider_config(root)

            with patch("agentforge.web.routes.create_llm_client", return_value=FailingProviderLLMClient()):
                generated = handle_request(
                    "POST",
                    "/skills/generate",
                    body=json.dumps({"input": "Create a UI review Skill", "use_provider": True}),
                    project_root=root,
                )

            self.assertEqual(generated.status, 502)
            self.assertIn("provider unavailable", generated.payload["error"])

    def test_skill_workflow_routes_generate_run_and_evolve(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_skill(root)
            taskset_path = _write_taskset(root)

            tasksets = handle_request("GET", "/tasksets", project_root=root)
            self.assertEqual(tasksets.status, 200)
            self.assertEqual(tasksets.payload["tasksets"][0]["relative_path"], "tasksets/sample.json")

            generated = handle_request(
                "POST",
                "/skills/generate",
                body=json.dumps({"input": "Create a UI review Skill"}),
                project_root=root,
            )
            self.assertEqual(generated.status, 200)
            self.assertTrue(generated.payload["valid"])
            self.assertIn("skill_path", generated.payload)
            self.assertTrue(generated.payload["run_id"].startswith("run_"))
            generated_run = handle_request("GET", f"/runs/{generated.payload['run_id']}", project_root=root)
            self.assertEqual(generated_run.payload["task_type"], "skill_generate")

            run = handle_request(
                "POST",
                "/skills/run",
                body=json.dumps(
                    {
                        "skill_path": str(root / "skills" / "ui_review_skill" / "v1" / "SKILL.md"),
                        "input": "Review a dashboard with dense charts and low-contrast labels.",
                    }
                ),
                project_root=root,
            )
            self.assertEqual(run.status, 200)
            self.assertEqual(run.payload["mode"], "local")
            self.assertIn("Skill Run Output", run.payload["output"])
            self.assertTrue(run.payload["run_id"].startswith("run_"))
            skill_run = handle_request("GET", f"/runs/{run.payload['run_id']}", project_root=root)
            self.assertEqual(skill_run.payload["task_type"], "skill_run")

            evolved = handle_request(
                "POST",
                "/skills/evolve",
                body=json.dumps(
                    {
                        "skill_path": str(root / "skills" / "ui_review_skill" / "v1" / "SKILL.md"),
                        "taskset_path": str(taskset_path),
                        "max_iterations": 1,
                        "min_improvement": 0,
                    }
                ),
                project_root=root,
            )
            self.assertEqual(evolved.status, 200)
            self.assertIn("final_skill_path", evolved.payload)
            self.assertEqual(len(evolved.payload["iterations"]), 1)
            self.assertIn("quality_gate", evolved.payload["iterations"][0])
            self.assertTrue(evolved.payload["run_id"].startswith("run_"))
            evolve_run = handle_request("GET", f"/runs/{evolved.payload['run_id']}", project_root=root)
            self.assertEqual(evolve_run.payload["task_type"], "skill_evolve")

    def test_task_routes_expose_types_and_run_trace_diagnosis(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            chat = handle_request(
                "POST",
                "/chat",
                body=json.dumps({"message": "Review dashboard layout readability."}),
                project_root=root,
            )
            task_types = handle_request("GET", "/tasks/types", project_root=root)
            self.assertEqual(task_types.status, 200)
            self.assertTrue(any(item["task_type"] == "trace_diagnosis" for item in task_types.payload["task_types"]))

            task = handle_request(
                "POST",
                "/tasks",
                body=json.dumps(
                    {
                        "task_type": "trace_diagnosis",
                        "input": {"run_id": chat.payload["run_id"]},
                    }
                ),
                project_root=root,
            )

            self.assertEqual(task.status, 200)
            self.assertEqual(task.payload["task_type"], "trace_diagnosis")
            self.assertEqual(task.payload["status"], "completed")
            self.assertIn("trace_url", task.payload)
            self.assertEqual(task.payload["output"]["diagnosis"]["trace_type"], "agent_chat")
            runs = handle_request("GET", "/runs?task_type=trace_diagnosis", project_root=root)
            self.assertTrue(any(run["run_id"] == task.payload["run_id"] for run in runs.payload["runs"]))
            detail = handle_request("GET", f"/runs/{task.payload['run_id']}", project_root=root)
            self.assertTrue(detail.payload["workflow_checkpoints"])

    def test_chat_routes_trace_diagnosis_task(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            handle_request(
                "POST",
                "/chat",
                body=json.dumps({"message": "hello"}),
                project_root=root,
            )

            response = handle_request(
                "POST",
                "/chat",
                body=json.dumps({"message": "Inspect the latest trace."}),
                project_root=root,
            )

            self.assertEqual(response.status, 200)
            self.assertEqual(response.payload["intent"]["task_type"], "trace_diagnosis")
            self.assertEqual(response.payload["plan"]["action"], "route_task")
            self.assertEqual(response.payload["task_result"]["task_type"], "trace_diagnosis")
            self.assertEqual(response.payload["task_result"]["status"], "completed")

    def test_chat_routes_code_analysis_task(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)

            response = handle_request(
                "POST",
                "/chat",
                body=json.dumps(
                    {
                        "message": (
                            "Analyze this Python function.\n"
                            "```python\n"
                            "def run(value):\n"
                            "    return eval(value)\n"
                            "```\n"
                        )
                    }
                ),
                project_root=root,
            )

            self.assertEqual(response.status, 200)
            self.assertEqual(response.payload["intent"]["task_type"], "code_analysis")
            self.assertEqual(response.payload["plan"]["action"], "route_task")
            self.assertEqual(response.payload["task_result"]["task_type"], "code_analysis")
            self.assertEqual(response.payload["task_result"]["status"], "completed")
            self.assertIn("Code Analysis", response.payload["response"])

    def test_chat_routes_document_analysis_task(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)

            response = handle_request(
                "POST",
                "/chat",
                body=json.dumps(
                    {
                        "message": (
                            "Analyze this document.\n"
                            "# Release Notes\n\n"
                            "TODO: fill in details.\n\n"
                            "## Scope\n"
                            "This document describes rollout scope."
                        )
                    }
                ),
                project_root=root,
            )

            self.assertEqual(response.status, 200)
            self.assertEqual(response.payload["intent"]["task_type"], "document_analysis")
            self.assertEqual(response.payload["plan"]["action"], "route_task")
            self.assertEqual(response.payload["task_result"]["task_type"], "document_analysis")
            self.assertEqual(response.payload["task_result"]["status"], "completed")
            self.assertIn("Document Analysis", response.payload["response"])

    def test_chat_routes_data_analysis_task(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)

            response = handle_request(
                "POST",
                "/chat",
                body=json.dumps(
                    {
                        "message": (
                            "Analyze this CSV dataset.\n"
                            "```csv\n"
                            "name,score\n"
                            "Ada,10\n"
                            "Bob,\n"
                            "```\n"
                        )
                    }
                ),
                project_root=root,
            )

            self.assertEqual(response.status, 200)
            self.assertEqual(response.payload["intent"]["task_type"], "data_analysis")
            self.assertEqual(response.payload["plan"]["action"], "route_task")
            self.assertEqual(response.payload["task_result"]["task_type"], "data_analysis")
            self.assertEqual(response.payload["task_result"]["status"], "completed")
            self.assertIn("Data Analysis", response.payload["response"])

    def test_tool_calling_chat_compact_payload_exposes_task_result(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)

            response = handle_request(
                "POST",
                "/chat",
                body=json.dumps(
                    {
                        "agent_mode": "tool_calling",
                        "message": (
                            "Analyze this Python function.\n"
                            "```python\n"
                            "def run(value):\n"
                            "    return eval(value)\n"
                            "```\n"
                        ),
                    }
                ),
                project_root=root,
            )

            self.assertEqual(response.status, 200)
            self.assertEqual(response.payload["intent"]["task_type"], "code_analysis")
            self.assertEqual(response.payload["task_result"]["task_type"], "code_analysis")
            self.assertEqual(response.payload["task_result"]["status"], "completed")

    def test_chat_rejects_missing_message(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            response = handle_request("POST", "/chat", body="{}", project_root=Path(temp_dir))

            self.assertEqual(response.status, 400)
            self.assertIn("message", response.payload["error"])


def _write_skill(root: Path) -> Path:
    skill_path = root / "skills" / "ui_review_skill" / "v1" / "SKILL.md"
    return _write_skill_at(skill_path)


def _write_frontend_dist(root: Path) -> Path:
    dist = root / "apps" / "web" / "frontend" / "dist"
    dist.mkdir(parents=True)
    (dist / "index.html").write_text(
        '<!doctype html><html lang="zh-CN"><body><h1>AgentForge</h1><script type="module" src="/app.js"></script></body></html>',
        encoding="utf-8",
    )
    (dist / "app.js").write_text("console.log('AgentForge');", encoding="utf-8")
    return dist


def _write_skill_at(skill_path: Path) -> Path:
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


def _write_provider_config(root: Path) -> Path:
    config_path = root / "config" / "providers.json"
    config_path.parent.mkdir(parents=True)
    config_path.write_text(
        json.dumps(
            {
                "default_provider": "fake",
                "providers": {
                    "fake": {
                        "type": "openai_compatible",
                        "base_url": "https://example.invalid/v1",
                        "api_key": "test-key",
                        "model": "fake-model",
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    return config_path


def _write_taskset(root: Path) -> Path:
    taskset_path = root / "tasksets" / "sample.json"
    taskset_path.parent.mkdir(parents=True)
    taskset_path.write_text(
        json.dumps(
            {
                "name": "sample",
                "tasks": [
                    {
                        "id": "dashboard",
                        "input": "Review a dashboard with dense charts and low-contrast labels.",
                        "expected_output": ["issues", "recommendations"],
                        "criteria": ["structured report"],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    return taskset_path


if __name__ == "__main__":
    unittest.main()
