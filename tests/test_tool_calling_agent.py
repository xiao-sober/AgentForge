import json
import tempfile
import unittest
from pathlib import Path

from agentforge.agent.harness import AgentHarness
from agentforge.agent.tool_calling import (
    DecisionParseError,
    ProviderModelPlanner,
    ScriptedModelPlanner,
    ToolCallPolicy,
    ToolDecision,
    default_tool_call_policy,
    parse_model_decision,
    registry_model_schemas,
)
from agentforge.agent.tools import AgentTool, ToolRegistry, ToolResult, ToolSchema


class ToolCallingAgentTest(unittest.TestCase):
    def test_schema_adapter_outputs_model_readable_json_schema(self):
        registry = ToolRegistry()
        registry.register(
            AgentTool(
                name="echo",
                kind="test",
                handler=lambda payload: ToolResult(output={"value": payload["message"]}),
                description="Echo a message.",
                input_schema=ToolSchema.from_types(required={"message": "string"}, allow_extra=False),
                permission_level="read",
                idempotent=True,
            )
        )

        schema = registry_model_schemas(registry, {"echo"})[0]

        self.assertEqual(schema["name"], "echo")
        self.assertEqual(schema["permission_level"], "read")
        self.assertEqual(schema["input_schema"]["properties"]["message"]["type"], "string")
        self.assertEqual(schema["input_schema"]["required"], ["message"])
        self.assertFalse(schema["input_schema"]["additionalProperties"])

    def test_parser_accepts_supported_decisions_and_rejects_invalid_json(self):
        tool_call = parse_model_decision('{"type":"tool_call","tool_name":"select_skill","arguments":{}}')
        final = parse_model_decision('{"type":"final_answer","content":"done"}')
        blocked = parse_model_decision(
            '{"type":"cannot_continue","reason":"missing","needed_input":["screenshot"]}'
        )

        self.assertEqual(tool_call.tool_name, "select_skill")
        self.assertEqual(final.content, "done")
        self.assertEqual(blocked.needed_input, ["screenshot"])
        with self.assertRaises(DecisionParseError):
            parse_model_decision("not json")

    def test_parser_repairs_fenced_json_and_embedded_single_object(self):
        fenced = parse_model_decision(
            '```json\n{"type":"tool_call","tool_name":"select_skill","arguments":{}}\n```'
        )
        embedded = parse_model_decision(
            'Next decision:\n{"type":"final_answer","content":"done"}\nNo more text.'
        )

        self.assertTrue(fenced.repaired)
        self.assertEqual(fenced.repair_strategy, "fenced_json")
        self.assertEqual(fenced.to_dict()["parse_metadata"]["repair_strategy"], "fenced_json")
        self.assertIn("raw_text_preview", fenced.to_dict()["parse_metadata"])
        self.assertTrue(embedded.repaired)
        self.assertEqual(embedded.repair_strategy, "embedded_json_object")
        self.assertEqual(embedded.content, "done")

    def test_parser_rejects_arrays_and_multiple_json_objects(self):
        with self.assertRaises(DecisionParseError):
            parse_model_decision('[{"type":"final_answer","content":"done"}]')
        with self.assertRaises(DecisionParseError):
            parse_model_decision(
                '{"type":"final_answer","content":"one"}\n{"type":"final_answer","content":"two"}'
            )

    def test_provider_model_planner_parses_provider_json_decisions(self):
        client = FakeProviderClient(
            [
                '{"type":"tool_call","tool_name":"select_skill","arguments":{}}',
                '{"type":"final_answer","content":"done"}',
                '{"type":"cannot_continue","reason":"missing input","needed_input":["screenshot"]}',
            ]
        )
        planner = ProviderModelPlanner(client)
        state = _PromptState()

        tool_call = planner.decide(state)
        final = planner.decide(state)
        blocked = planner.decide(state)

        self.assertEqual(tool_call.tool_name, "select_skill")
        self.assertEqual(final.content, "done")
        self.assertEqual(blocked.reason, "missing input")
        self.assertEqual(blocked.needed_input, ["screenshot"])
        self.assertEqual(client.call_count, 3)
        self.assertIn("Tool-Calling Planner", client.system_prompts[0])
        self.assertIn("available_tools", client.prompts[0])
        self.assertIn("After build_response", client.prompts[0])

    def test_provider_model_planner_rejects_invalid_json(self):
        planner = ProviderModelPlanner(FakeProviderClient(["not json"]))

        with self.assertRaises(DecisionParseError):
            planner.decide(_PromptState())

    def test_provider_model_planner_preserves_repair_metadata(self):
        planner = ProviderModelPlanner(
            FakeProviderClient(['```json\n{"type":"tool_call","tool_name":"select_skill","arguments":{}}\n```'])
        )

        decision = planner.decide(_PromptState())

        self.assertTrue(decision.repaired)
        self.assertEqual(decision.repair_strategy, "fenced_json")

    def test_provider_model_planner_retries_once_with_repair_prompt(self):
        client = FakeProviderClient(["not json", '{"type":"tool_call","tool_name":"select_skill","arguments":{}}'])
        planner = ProviderModelPlanner(client)

        decision = planner.decide(_PromptState())

        self.assertEqual(decision.tool_name, "select_skill")
        self.assertTrue(decision.provider_repair_attempted)
        self.assertIn("JSON object", client.system_prompts[1])
        self.assertIn("Invalid output to repair", client.prompts[1])
        self.assertTrue(decision.to_dict()["parse_metadata"]["provider_repair_attempted"])

    def test_policy_rejects_unknown_tool_write_tool_and_missing_state(self):
        registry = ToolRegistry()
        registry.register(
            AgentTool(
                name="build_response",
                kind="response",
                handler=lambda payload: ToolResult(output={}),
                permission_level="write",
                input_schema=ToolSchema.from_types(allow_extra=False),
            )
        )
        policy = ToolCallPolicy(
            allowed_tools={"build_response"},
            allowed_write_tools=set(),
            state_requirements={"build_response": {"execution"}},
        )

        unknown = policy.validate(ToolDecision.tool_call("missing_tool"), registry, runtime_state={})
        rejected = policy.validate(ToolDecision.tool_call("build_response"), registry, runtime_state={})

        self.assertFalse(unknown.valid)
        self.assertIn("Tool is not allowed", unknown.errors[0])
        self.assertFalse(rejected.valid)
        self.assertTrue(any("write permission" in error for error in rejected.errors))
        self.assertTrue(any("missing prerequisite state" in error for error in rejected.errors))

    def test_harness_tool_chat_runs_scripted_tool_loop_and_writes_trace(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_skill(root)

            result = AgentHarness(project_root=root).tool_chat("Review dashboard layout readability.")

            self.assertEqual(result.agent_mode, "tool_calling_agent")
            self.assertEqual(result.stop_reason, "final_answer")
            self.assertIn("AgentForge Response", result.response)
            self.assertTrue(result.trace_path.exists())
            self.assertEqual(result.tool_calling.state.status, "completed")
            self.assertEqual(result.tool_calling.state.iteration, 8)
            tool_names = [item["tool_name"] for item in result.tool_calling.state.observations]
            self.assertIn("select_skill", tool_names)
            self.assertIn("execute_plan", tool_names)
            trace = json.loads(result.trace_path.read_text(encoding="utf-8"))
            self.assertEqual(trace["type"], "tool_calling_agent")
            self.assertEqual(trace["output"]["agent_mode"], "tool_calling_agent")
            self.assertTrue(trace["schema"]["valid"])

    def test_harness_tool_chat_stops_after_repeated_invalid_calls(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            planner = ScriptedModelPlanner(
                [
                    ToolDecision.tool_call("save_episode_memory", {}),
                    ToolDecision.tool_call("save_episode_memory", {}),
                ]
            )
            policy = default_tool_call_policy()

            result = AgentHarness(project_root=root).tool_chat("hello", planner=planner, policy=policy)

            self.assertEqual(result.stop_reason, "invalid_tool_call_budget")
            self.assertEqual(result.tool_calling.state.status, "failed")
            self.assertEqual(result.tool_calling.state.invalid_call_count, 2)

    def test_harness_tool_chat_stops_on_repeated_same_tool_call(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            planner = ScriptedModelPlanner(
                [
                    ToolDecision.tool_call("retrieve_memory_context", {}),
                    ToolDecision.tool_call("retrieve_memory_context", {}),
                ]
            )
            policy = _policy_with(max_repeated_tool_calls=1)

            result = AgentHarness(project_root=root).tool_chat("hello", planner=planner, policy=policy)

            self.assertEqual(result.stop_reason, "repeated_tool_call")
            self.assertEqual(result.tool_calling.state.status, "failed")
            self.assertEqual(result.tool_calling.state.repeated_tool_call_count, 2)
            self.assertTrue(any(error["error_type"] == "RepeatedToolCall" for error in result.tool_calling.state.errors))
            trace = json.loads(result.trace_path.read_text(encoding="utf-8"))
            repeated_step = trace["steps"][2]
            self.assertEqual(repeated_step["errors"][0]["error_type"], "RepeatedToolCall")

    def test_harness_tool_chat_stops_on_repeated_same_tool_with_different_arguments(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            planner = ScriptedModelPlanner(
                [
                    ToolDecision.tool_call("retrieve_memory_context", {"query": "dashboard UI review"}),
                    ToolDecision.tool_call("retrieve_memory_context", {"query": "dashboard review skill"}),
                    ToolDecision.tool_call("retrieve_memory_context", {"query": "UI dashboard prior skill"}),
                ]
            )
            policy = _policy_with(max_same_tool_calls=2)

            result = AgentHarness(project_root=root).tool_chat("hello", planner=planner, policy=policy)

            self.assertEqual(result.stop_reason, "repeated_tool_call")
            self.assertEqual(result.tool_calling.state.status, "failed")
            self.assertEqual(result.tool_calling.state.same_tool_call_count, 3)
            error = next(error for error in result.tool_calling.state.errors if error["error_type"] == "RepeatedToolCall")
            self.assertEqual(error["scope"], "same_tool")
            self.assertEqual(error["threshold"], 2)
            self.assertIn("recovery_hint", result.tool_calling.state.observation_summaries[-1]["policy_rejection"])

    def test_policy_rejection_adds_recovery_observation_for_next_turn(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            planner = ScriptedModelPlanner(
                [
                    ToolDecision.tool_call("retrieve_memory_context", {}),
                    ToolDecision.tool_call("select_skill", {}),
                    ToolDecision.tool_call("build_response", {}),
                    ToolDecision.tool_call("build_plan", {}),
                    ToolDecision.tool_call("execute_plan", {}),
                    ToolDecision.tool_call("build_response", {}),
                    ToolDecision.final_answer("done"),
                ]
            )

            result = AgentHarness(project_root=root).tool_chat("Review dashboard layout.", planner=planner)

            self.assertEqual(result.stop_reason, "final_answer")
            policy_summaries = [
                item
                for item in result.tool_calling.state.observation_summaries
                if item.get("policy_rejection")
            ]
            self.assertTrue(policy_summaries)
            hint = policy_summaries[0]["policy_rejection"]["recovery_hint"]
            self.assertIn("Call build_plan first", hint)
            self.assertIn("execute_plan", hint)
            trace = json.loads(result.trace_path.read_text(encoding="utf-8"))
            rejected_step = next(step for step in trace["steps"] if step.get("errors"))
            self.assertEqual(rejected_step["errors"][0]["error_type"], "ToolCallPolicyViolation")
            self.assertIn("recovery_hint", rejected_step["observation_summary"]["policy_rejection"])

    def test_harness_tool_chat_records_premature_final_answer_before_build_response(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            planner = ScriptedModelPlanner(
                [
                    ToolDecision.final_answer("too early"),
                    ToolDecision.final_answer("still too early"),
                ]
            )

            result = AgentHarness(project_root=root).tool_chat("hello", planner=planner)

            self.assertEqual(result.stop_reason, "invalid_tool_call_budget")
            self.assertEqual(result.tool_calling.state.status, "failed")
            self.assertTrue(any(error["error_type"] == "PrematureFinalAnswer" for error in result.tool_calling.state.errors))
            trace = json.loads(result.trace_path.read_text(encoding="utf-8"))
            self.assertEqual(trace["steps"][1]["errors"][0]["error_type"], "PrematureFinalAnswer")

    def test_harness_tool_chat_with_provider_invalid_json_stops_at_invalid_budget(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            client = FakeProviderClient(["not json", "not json"])

            result = AgentHarness(project_root=root, llm_client=client).tool_chat("hello")

            self.assertEqual(result.stop_reason, "invalid_tool_call_budget")
            self.assertEqual(result.tool_calling.state.status, "failed")
            self.assertEqual(result.tool_calling.state.invalid_call_count, 2)
            self.assertTrue(any(error["error_type"] == "DecisionParseError" for error in result.tool_calling.state.errors))

    def test_harness_tool_chat_with_provider_unknown_tool_stops_at_invalid_budget(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            client = FakeProviderClient(
                [
                    '{"type":"tool_call","tool_name":"save_episode_memory","arguments":{}}',
                    '{"type":"tool_call","tool_name":"save_episode_memory","arguments":{}}',
                ]
            )

            result = AgentHarness(project_root=root, llm_client=client).tool_chat("hello")

            self.assertEqual(result.stop_reason, "invalid_tool_call_budget")
            self.assertEqual(result.tool_calling.state.status, "failed")
            self.assertTrue(
                any(
                    error["error_type"] == "ToolCallPolicyViolation" and "Tool is not allowed" in error["message"]
                    for error in result.tool_calling.state.errors
                )
            )

    def test_harness_tool_chat_with_provider_cannot_continue_blocks_cleanly(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            client = FakeProviderClient(
                ['{"type":"cannot_continue","reason":"Need a screenshot.","needed_input":["screenshot"]}']
            )

            result = AgentHarness(project_root=root, llm_client=client).tool_chat("Review this UI.")

            self.assertEqual(result.stop_reason, "cannot_continue")
            self.assertEqual(result.tool_calling.state.status, "blocked")
            self.assertIn("Need a screenshot", result.response)
            self.assertTrue(any(error["error_type"] == "CannotContinue" for error in result.tool_calling.state.errors))

    def test_harness_tool_chat_can_inspect_latest_trace(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_trace(root, "20260703T000000Z_agent_chat.json")
            planner = ScriptedModelPlanner(
                [
                    ToolDecision.tool_call("retrieve_memory_context", {}),
                    ToolDecision.tool_call("inspect_latest_trace", {}),
                    ToolDecision.tool_call("build_plan", {}),
                    ToolDecision.tool_call("execute_plan", {}),
                    ToolDecision.tool_call("build_response", {}),
                    ToolDecision.final_answer("done"),
                ]
            )

            result = AgentHarness(project_root=root).tool_chat("Inspect the latest trace.", planner=planner)

            self.assertEqual(result.stop_reason, "final_answer")
            self.assertIn("Trace Inspection", result.response)
            self.assertIn("20260703T000000Z_agent_chat.json", result.response)
            tool_names = [item["tool_name"] for item in result.tool_calling.state.observations]
            self.assertIn("inspect_latest_trace", tool_names)
            trace_summary = next(
                item["output"]["trace_inspection"]
                for item in result.tool_calling.state.observation_summaries
                if item["tool_name"] == "inspect_latest_trace"
            )
            self.assertTrue(trace_summary["found"])

    def test_harness_tool_chat_answers_memory_query_from_retrieval(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            harness = AgentHarness(project_root=root)
            harness.memory.save_episode(
                {
                    "run_id": "run_provider_dry_run",
                    "user_input": "provider dry run",
                    "response": "DeepSeek and DashScope completed tool-calling dry runs.",
                    "intent": {"intent_type": "agent_validation"},
                }
            )
            planner = ScriptedModelPlanner(
                [
                    ToolDecision.tool_call("retrieve_memory_context", {}),
                    ToolDecision.tool_call("build_plan", {}),
                    ToolDecision.tool_call("execute_plan", {}),
                    ToolDecision.tool_call("build_response", {}),
                    ToolDecision.final_answer("done"),
                ]
            )

            result = harness.tool_chat(
                "What memory do you have about provider dry run?",
                planner=planner,
            )

            self.assertEqual(result.stop_reason, "final_answer")
            self.assertIn("Memory Query", result.response)
            self.assertIn("DeepSeek and DashScope", result.response)
            memory_summary = result.tool_calling.state.observation_summaries[0]["output"]
            self.assertIn("memory_preview", memory_summary)
            self.assertTrue(memory_summary["memory_preview"]["episodes"])

    def test_harness_tool_chat_trace_records_provider_repair_metadata(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            client = FakeProviderClient(
                [
                    '```json\n{"type":"tool_call","tool_name":"retrieve_memory_context","arguments":{}}\n```',
                    '{"type":"tool_call","tool_name":"select_skill","arguments":{}}',
                    '{"type":"tool_call","tool_name":"build_plan","arguments":{}}',
                    '{"type":"tool_call","tool_name":"execute_plan","arguments":{}}',
                    '{"type":"tool_call","tool_name":"build_response","arguments":{}}',
                    '{"type":"final_answer","content":"done"}',
                ]
            )

            result = AgentHarness(project_root=root, llm_client=client).tool_chat("hello")

            self.assertEqual(result.stop_reason, "final_answer")
            trace = json.loads(result.trace_path.read_text(encoding="utf-8"))
            first_decision = trace["steps"][1]["model_decision"]
            self.assertTrue(first_decision["parse_metadata"]["repaired"])
            self.assertEqual(first_decision["parse_metadata"]["repair_strategy"], "fenced_json")

    def test_harness_tool_chat_prefers_harness_response_after_provider_rewrites_final_answer(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_skill(root)
            client = RoutingProviderClient(
                planner_outputs=[
                    '{"type":"tool_call","tool_name":"retrieve_memory_context","arguments":{}}',
                    '{"type":"tool_call","tool_name":"select_skill","arguments":{}}',
                    '{"type":"tool_call","tool_name":"build_plan","arguments":{}}',
                    '{"type":"tool_call","tool_name":"execute_plan","arguments":{}}',
                    '{"type":"tool_call","tool_name":"observe_execution","arguments":{}}',
                    '{"type":"tool_call","tool_name":"build_response","arguments":{}}',
                    '{"type":"final_answer","content":"# Free Rewrite\\n\\nThis should not be returned."}',
                ],
                skill_output="# Skill Run Output\n\n## Task\n\nReview dashboard.\n\n## Applied Skill\n\nUI Review Skill\n\n## Result\n\nHarness skill result marker.\n\n## Assumptions and Gaps\n\n- None.\n",
            )

            result = AgentHarness(project_root=root, llm_client=client).tool_chat(
                "Review dashboard layout readability."
            )

            self.assertEqual(result.stop_reason, "final_answer")
            self.assertIn("AgentForge Response", result.response)
            self.assertIn("Harness skill result marker", result.response)
            self.assertNotIn("Free Rewrite", result.response)
            self.assertEqual(result.tool_calling.state.final_answer, "# Free Rewrite\n\nThis should not be returned.")
            self.assertTrue(result.tool_calling.state.observation_summaries)
            prompt_payload = result.tool_calling.state.to_prompt_payload()
            self.assertIn("observations", prompt_payload)
            self.assertNotIn("tool_result", prompt_payload["observations"][0])
            self.assertIn("output", prompt_payload["observations"][0])

    def test_tool_calling_hqs_gate_retries_response_once_without_reinforcement(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_skill(root)

            result = AgentHarness(project_root=root, response_hqs_threshold=5.1).tool_chat(
                "Review dashboard layout readability."
            )

            self.assertTrue(result.quality_retry["triggered"])
            self.assertEqual(result.quality_retry["retry_count"], 1)
            self.assertEqual(result.quality_retry["final_decision"], "stop_low_hqs")
            self.assertEqual(result.hqs_gate["stop_reason"], "retry_budget_exhausted")
            self.assertEqual(result.final_answer_source, "harness_response")
            self.assertTrue(any(item["tool_name"] == "build_response" for item in result.tool_call_timeline))
            trace = json.loads(result.trace_path.read_text(encoding="utf-8"))
            step_names = [step["name"] for step in trace["steps"]]
            self.assertEqual(step_names.count("controlled_retry_build_response"), 1)
            self.assertIn("tool_calling_hqs_gate", step_names)
            self.assertIn("tool_calling_hqs_gate_after_retry", step_names)
            self.assertNotIn("reinforcement", trace["output"])


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


def _write_trace(root: Path, filename: str) -> Path:
    trace_path = root / "traces" / filename
    trace_path.parent.mkdir(parents=True)
    trace_path.write_text(
        json.dumps(
            {
                "trace_id": "trace_test",
                "type": "agent_chat",
                "created_at": "2026-07-03T00:00:00Z",
                "input": {"message": "hello"},
                "steps": [{"name": "receive_input", "status": "completed"}],
                "output": {"run_id": "run_test"},
                "artifacts": [],
                "errors": [],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return trace_path


def _policy_with(**overrides):
    base = default_tool_call_policy()
    values = {
        "allowed_tools": base.allowed_tools,
        "max_iterations": base.max_iterations,
        "max_invalid_calls": base.max_invalid_calls,
        "max_tool_errors": base.max_tool_errors,
        "max_repeated_tool_calls": base.max_repeated_tool_calls,
        "max_same_tool_calls": base.max_same_tool_calls,
        "same_tool_call_guard_tools": base.same_tool_call_guard_tools,
        "allow_write_tools": base.allow_write_tools,
        "allow_admin_tools": base.allow_admin_tools,
        "allowed_write_tools": base.allowed_write_tools,
        "state_requirements": base.state_requirements,
    }
    values.update(overrides)
    return ToolCallPolicy(**values)


class FakeProviderClient:
    def __init__(self, outputs):
        self.outputs = list(outputs)
        self.call_count = 0
        self.prompts = []
        self.system_prompts = []

    def complete(self, prompt, system_prompt=None):
        self.prompts.append(prompt)
        self.system_prompts.append(system_prompt or "")
        output = self.outputs[min(self.call_count, len(self.outputs) - 1)]
        self.call_count += 1
        return output

    def metadata(self):
        return {"provider": "fake", "model": "fake-tool-planner"}


class RoutingProviderClient:
    def __init__(self, planner_outputs, skill_output):
        self.planner_outputs = list(planner_outputs)
        self.skill_output = skill_output
        self.planner_call_count = 0
        self.skill_call_count = 0
        self.prompts = []
        self.system_prompts = []

    def complete(self, prompt, system_prompt=None):
        self.prompts.append(prompt)
        self.system_prompts.append(system_prompt or "")
        if "Tool-Calling Planner" in (system_prompt or ""):
            output = self.planner_outputs[min(self.planner_call_count, len(self.planner_outputs) - 1)]
            self.planner_call_count += 1
            return output
        self.skill_call_count += 1
        return self.skill_output

    def metadata(self):
        return {"provider": "fake", "model": "fake-routing-provider"}


class _PromptState:
    def to_prompt_payload(self):
        return {
            "user_input": "Review dashboard layout.",
            "available_tools": [{"name": "select_skill", "input_schema": {"type": "object"}}],
            "observations": [],
        }


if __name__ == "__main__":
    unittest.main()
