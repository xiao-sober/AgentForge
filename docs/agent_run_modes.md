# Agent Run Modes: Local vs Provider, Harness Workflow vs Tool-Calling Agent

This document explains the four runtime combinations used by AgentForge chat:

- Runtime backend: local deterministic mode or configured model provider mode.
- Agent mode: `harness_workflow` or `tool_calling_agent`.

The important distinction is:

- `use_provider` controls whether model-backed operations can call the configured LLM provider.
- `agent_mode` controls who decides the next Agent step: fixed Harness workflow or model-planned tool calls.

## Quick Matrix

| Runtime | Agent mode | Who chooses next step | Model role | Trace type | Best for |
| --- | --- | --- | --- | --- | --- |
| Local | `harness_workflow` | Harness fixed workflow | None, deterministic local logic | `agent_chat` | Baseline tests, offline development, deterministic debugging |
| Provider | `harness_workflow` | Harness fixed workflow | Provider may generate/run/rewrite Skill content when a step needs model text | `agent_chat` | Stable production-like workflow with model-backed content |
| Local | `tool_calling_agent` | Scripted local planner | None; fake/scripted planner emits tool decisions | `tool_calling_agent` | Testing tool-call policy, trace, UI timeline, and Harness controls without API calls |
| Provider | `tool_calling_agent` | Provider planner proposes tool calls | Provider returns JSON decisions; Harness validates and executes tools | `tool_calling_agent` | Real tool-calling Agent behavior under Harness safety controls |

## Two Independent Switches

### `use_provider`

`use_provider: false` means local deterministic execution. No external model call is required.

`use_provider: true` means AgentForge creates the default configured provider client from `config/providers.json`. Secrets must stay in config or environment references and must not be hardcoded.

### `agent_mode`

`agent_mode: "harness_workflow"` uses the deterministic Harness sequence:

```text
receive_input
-> parse_intent
-> retrieve_memory_context
-> select_skill
-> build_plan
-> execute_plan
-> observe_execution
-> update_semantic_memory
-> build_response
-> evaluate_response_hqs
-> hqs_gate
-> reflect
-> reinforcement_check
-> save_episode_memory
```

`agent_mode: "tool_calling"` or `tool_calling_agent` uses a tool-call loop:

```text
Harness setup
-> expose allowed tool schemas
-> planner returns one JSON decision
-> Harness validates policy/schema/state
-> Harness executes tool
-> observation is summarized
-> planner chooses next tool or final_answer
-> Harness evaluates HQS
-> optional one controlled response retry
-> Harness saves memory and trace
```

## Mode Details

### 1. Local + `harness_workflow`

This is the most deterministic mode.

Properties:

- No external provider is required.
- The Harness decides every step in a fixed order.
- Skill generation and Skill execution use local deterministic fallbacks where possible.
- Trace type is `agent_chat`.
- HQS, memory, trace writing, and reinforcement checks still run through Harness logic.

Use this when:

- You want a stable baseline.
- You are debugging intent parsing, plan construction, memory, HQS, or trace shape.
- You need tests that should not depend on provider availability.

Example API:

```json
{
  "message": "Review dashboard layout readability.",
  "use_provider": false,
  "agent_mode": "harness_workflow"
}
```

Example CLI:

```bash
agentforge agent-chat --input "Review dashboard layout readability." --json
```

### 2. Provider + `harness_workflow`

This keeps the same fixed Harness workflow, but model-backed steps can call the provider.

Properties:

- The Harness still decides step order.
- The provider does not choose tools.
- Provider may be used inside Skill generation, Skill execution, or rewrite flows.
- Trace type is `agent_chat`.
- This mode is more stable than provider tool-calling because the model only supplies content, not control flow.

Use this when:

- You want model quality for generated or executed Skill output.
- You still want predictable orchestration.
- You are comparing provider output quality without testing model-planned tool calls.

Example API:

```json
{
  "message": "Generate a Skill for API response contract review.",
  "use_provider": true,
  "agent_mode": "harness_workflow"
}
```

Example CLI:

```bash
agentforge agent-chat --input "Generate a Skill for API response contract review." --use-provider --json
```

### 3. Local + `tool_calling_agent`

This mode exercises the tool-calling architecture without calling a real model.

Properties:

- AgentForge uses a scripted local planner.
- The scripted planner emits deterministic tool decisions.
- Harness policy, state prerequisites, tool execution, observation summaries, final answer handling, and trace timeline are still exercised.
- Trace type is `tool_calling_agent`.
- `final_answer_source` is normally `harness_response` after `build_response` runs.

Use this when:

- You are developing the tool-call loop.
- You want to test Web timeline rendering.
- You need deterministic coverage for policy failures, repeated calls, premature final answers, HQS gate, or trace shape.

Example API:

```json
{
  "message": "Inspect the latest trace.",
  "use_provider": false,
  "agent_mode": "tool_calling"
}
```

Example CLI:

```bash
agentforge agent-chat --input "Inspect the latest trace." --agent-mode tool-calling --json
```

### 4. Provider + `tool_calling_agent`

This is the real Tool-Calling Agent mode.

Properties:

- The provider receives the allowed tool schemas and compact observations.
- The provider must return exactly one JSON decision:
  - `tool_call`
  - `final_answer`
  - `cannot_continue`
- AgentForge parses the decision and may do one bounded JSON repair retry if provider output is not valid JSON.
- Harness validates tool name, argument schema, permission level, prerequisite state, repeated calls, invalid-call budget, and tool-error budget.
- Harness executes tools and owns all high-impact operations.
- Trace type is `tool_calling_agent`.
- The final returned user response prefers the Harness `build_response` output. The model `final_answer` is treated as a completion signal when `state["response"]` exists.

Use this when:

- You want the model to choose the next Agent tool.
- You are validating real provider JSON stability.
- You need inspectable tool-call timelines and observations.
- You are testing trace inspection or memory query behavior through provider-planned tool calls.

Example API:

```json
{
  "message": "What useful memory do you have about recent tool-calling provider dry runs?",
  "use_provider": true,
  "agent_mode": "tool_calling"
}
```

Example CLI:

```bash
agentforge agent-chat \
  --input "What useful memory do you have about recent tool-calling provider dry runs?" \
  --use-provider \
  --agent-mode tool-calling \
  --json
```

Use `--debug` when you need full internals:

```bash
agentforge agent-chat \
  --input "Inspect the latest trace." \
  --use-provider \
  --agent-mode tool-calling \
  --json \
  --debug
```

## Model-Callable vs Harness-Only Tools

In `tool_calling_agent`, the model sees only a bounded tool set.

Model-callable tools:

- `retrieve_memory_context`
- `inspect_latest_trace`
- `select_skill`
- `build_plan`
- `execute_plan`
- `observe_execution`
- `build_response`
- `evaluate_response_hqs`

Harness-only tools:

- `receive_input`
- `update_semantic_memory`
- `hqs_gate`
- `replan_response`
- `reflect`
- `reinforcement_check`
- `save_episode_memory`

Reason:

- Memory writes, HQS gates, retries, reflection, reinforcement, and episode persistence affect system state. They stay Harness-controlled.

## Response and Trace Differences

### `harness_workflow`

Compact `/chat` payload includes:

- `run_id`
- `response`
- `trace_path`
- `trace_url`
- `hqs`
- `system_hqs`
- `intent`
- `plan`
- `execution_state`
- `plan_step_results`
- `memory_retrieval`
- `selected_skill`
- `artifacts`
- `timeline`
- `reflection`
- `reinforcement`
- `stop_reason`

### `tool_calling_agent`

Compact `/chat` payload also includes:

- `agent_mode`
- `tool_call_timeline`
- `parse_repair_count`
- `invalid_call_count`
- `final_answer_source`
- `hqs_gate`
- `quality_retry`
- `tool_calling`

`final_answer_source` values:

- `harness_response`: `build_response` produced the user-facing response. This is the normal successful path.
- `model_final_answer`: no Harness response existed, so the model final answer or fallback stop message was used.

## Safety and Stop Conditions

`tool_calling_agent` has additional controls:

- Max iterations.
- Invalid decision budget.
- Tool error budget.
- Repeated identical tool-call detector.
- Same-tool guard for repeated memory retrieval.
- Premature `final_answer` guard before `build_response`.
- One controlled HQS retry after final answer if quality is low.
- Provider JSON repair retry limited to one repair prompt.

`harness_workflow` is safer by construction because the model does not choose tools or control flow.

## Practical Recommendation

Use this order when debugging:

1. Local + `harness_workflow` for baseline behavior.
2. Provider + `harness_workflow` for model content quality.
3. Local + `tool_calling_agent` for tool-call policy and UI timeline.
4. Provider + `tool_calling_agent` for real autonomous tool planning validation.

For day-to-day development, keep local deterministic modes green first. Use provider-backed `tool_calling_agent` as an acceptance test, not as the only debugging path.
