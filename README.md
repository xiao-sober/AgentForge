# AgentForge

AgentForge is a local-first Agent system for building, running, evaluating, and improving reusable Markdown Skills.

It is designed for transparent local development: Skills are files, runs are inspectable directories, traces are JSON, memory is JSON/JSONL, and model providers are optional adapters configured outside the code.

## What It Does

- Generates valid versioned `SKILL.md` files from requirements.
- Runs Skills against single inputs or task sets.
- Scores outputs with deterministic HQS diagnostics.
- Reflects on weak results and writes next Skill versions without overwriting old ones.
- Exposes a local JSON chat API backed by an Agent harness.
- Tracks each chat as an `AgentRun` with step timeline, reflection, and stop reason.
- Stores three-layer local memory.
- Writes readable traces for important actions.
- Provides health, config, trace inspection, and artifact cleanup commands.

## Status

Current status: observable Harness Agent MVP with production-hardening basics.

Implemented:

- Skill generation
- Skill execution
- Skill evolution
- Agent harness run loop with local ToolRegistry
- State-driven Planner/Executor for multi-step Skill execution
- JSON Web/API MVP and local Web workbench
- Local memory with retrieval scores and match reasons
- Skill, response, and system HQS
- Skill evolution quality gate
- Trace schema validation and inspection
- Provider output normalization and fail-fast provider errors
- Artifact retention cleanup
- Sample Skill and task set

Not implemented:

- Multi-agent orchestration
- Hosted/cloud deployment
- Enterprise auth/RBAC
- Vector database dependency
- Visual workflow builder

## Install

Use Python 3.10 or newer.

```bash
uv venv .venv
uv pip install --python .venv\Scripts\python.exe -e ".[dev]"
```

Run tests:

```bash
.venv\Scripts\python.exe -m unittest discover -s tests
```

## Quick Start

Start the local API:

```bash
python -m agentforge serve --host 127.0.0.1 --port 8765
```

Send a chat message:

```bash
curl -X POST http://127.0.0.1:8765/chat ^
  -H "Content-Type: application/json" ^
  -d "{\"message\":\"Review this dashboard layout for readability.\"}"
```

Open the Web console:

```text
http://127.0.0.1:8765/
```

The console supports:

- Chat
- Generate Skill
- Run Skill
- Evolve Skill
- Model-call toggle using the default provider config
- Chinese UI by default, with English/Chinese switching
- Agent run timeline
- Trace, HQS, memory retrieval, and Skill diff drill-down views
- Artifact and warning panels
- Trace/debug JSON inspection

Check local health and config:

```bash
python -m agentforge check-config
```

Generate a Skill locally:

```bash
python -m agentforge generate-skill --local-only --input "Create a UI review Skill"
```

Run a Skill:

```bash
python -m agentforge run-skill ^
  --skill skills/ui_review_skill/v1/SKILL.md ^
  --input "Review this dashboard layout for hierarchy and readability."
```

Evolve a Skill:

```bash
python -m agentforge evolve-skill ^
  --skill skills/ui_review_skill/v1/SKILL.md ^
  --taskset tasksets/sample_ui_review_basic.json ^
  --max-iterations 1
```

Inspect a trace:

```bash
python -m agentforge inspect-trace traces\<trace-file>.json
```

Preview cleanup:

```bash
python -m agentforge cleanup-artifacts --max-traces 200 --max-runs-per-skill-version 20
```

Add `--delete` only when you want to remove old trace files and run directories.

## API

The Web/API MVP uses Python standard library HTTP and returns JSON.

```text
GET  /health
GET  /version
GET  /config
POST /chat
POST /skills/generate
POST /skills/run
POST /skills/evolve
GET  /skills
GET  /skills/<skillName>
GET  /skills/<skillName>/<version>
GET  /tasksets
GET  /memory
GET  /traces
GET  /traces/<traceFileName>
GET  /hqs
```

`POST /chat` returns:

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
- `stop_reason`
- `reinforcement`

By default, `/chat` returns a compact payload for UI use. Send `{"debug": true}` or call `/chat?debug=1` to receive the full execution payload, including the full `run` object, execution result, memory context, and per-step inputs/outputs.

`GET /skills/<skillName>/<version>` returns the Skill Markdown, metadata, and `diff.patch` text when the version has an evolution diff.

`POST /chat`, `POST /skills/generate`, `POST /skills/run`, and `POST /skills/evolve` accept `use_provider: true` when you want to call the default configured model provider.

Web/API path inputs are constrained to project-local artifact folders:

- Skills: `skills/` or `examples/skills/`
- Task sets: `tasksets/`
- Traces: `traces/`
- Provider config: `config/providers.json`

Provider overrides are CLI-only. The Web/API uses the default provider config and falls back to local mode when provider setup or provider calls fail.

`GET /config` redacts secrets and does not return API keys.

## CLI Commands

```text
agentforge generate-skill
agentforge validate-skill
agentforge run-skill
agentforge evolve-skill
agentforge serve
agentforge check-config
agentforge inspect-trace
agentforge cleanup-artifacts
```

Use `--help` on any command for arguments.

## Model Providers

Provider config is optional. Without it, AgentForge uses deterministic local generation and execution.

Create local provider config:

```bash
copy config\providers.example.json config\providers.json
```

`config/providers.json` is ignored by git and must not be committed.

Provider calls go through adapters. The current adapter is `openai_compatible`, which expects a `/chat/completions` API.

Example shape:

```json
{
  "default_provider": "dashscope",
  "providers": {
    "dashscope": {
      "type": "openai_compatible",
      "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
      "api_key": "your-api-key",
      "model": "qwen3.7-plus",
      "timeout_seconds": 180,
      "temperature": 0.2,
      "max_tokens": 2500
    }
  }
}
```

If a provider is explicitly enabled and the model call times out or fails, AgentForge stops that provider-backed action and records the failure. It does not silently switch to deterministic local execution. Use `--local-only` or omit `--use-provider` when you intentionally want deterministic local behavior.

When `thinking_mode.enabled` is true and `timeout_seconds` is omitted, AgentForge defaults the provider timeout to 180 seconds. Non-thinking providers still default to 60 seconds.

Provider-backed Skill runs must satisfy the AgentForge output contract:

```md
# Skill Run Output

## Task

## Applied Skill

## Result

## Assumptions and Gaps
```

When provider output is non-empty but does not match the contract, AgentForge wraps it in the required structure without discarding the raw content. The output contract report is stored with each task output.

## Core Concepts

**Skill**

A reusable Markdown instruction file saved as:

```text
skills/<skill_slug>/<version>/SKILL.md
```

Every Skill version is preserved. New versions are written as `v1`, `v2`, `v3`, and so on.

**Trace**

A JSON record of important system activity, saved under `traces/`.

Trace types include:

- `skill_generation`
- `skill_execution`
- `skill_evaluation`
- `skill_evolution`
- `agent_chat`
- `memory_update`

**Agent Run**

Each `/chat` request creates an `AgentRun` with:

- `run_id`
- step timeline
- registered tool calls
- phase history
- response-level HQS
- HQS gate decision
- reflection recommendation
- stop reason

Typical steps include intent parsing, memory retrieval, Skill selection, planning, execution, observation, response building, HQS evaluation, HQS gate, reflection, reinforcement check, memory save, and trace write.

The harness uses a local `ToolRegistry` and `AgentRunLoop` to execute steps. Each registered tool declares input schema, output schema, known error types, permission level, idempotency, and optional timeout metadata. Tool inputs and outputs are validated before they are recorded in the run timeline.

**Planner and Executor**

Planner v2 decomposes complex Skill tasks into ordered subtasks with:

- stable `step_id`
- `depends_on`
- `tool_input`
- expected output metadata
- required/optional step flags
- max retry metadata
- stop conditions

The Executor is state-driven. It advances executable plan steps from `pending` to `running`, then to `completed`, `completed_with_warnings`, `failed`, or `skipped`. Dependency failures propagate to dependent steps as `skipped`. Provider-backed failures are blocking errors; local deterministic mode remains available only when selected intentionally. Multi-step Skill tasks are run as separate Skill executions, so the final execution result can contain both the compatibility `run_result` and the full `run_results` list.

Execution state is exposed as:

- `execution_state.status`
- `execution_state.step_statuses`
- `execution_state.completed_steps`
- `execution_state.failed_steps`
- `execution_state.skipped_steps`
- `execution_state.transitions`

The `agent_chat` trace also records the execution state and plan step results for inspection.

If the response HQS gate is triggered, the loop records a `replan_response` step, rebuilds the response once, evaluates HQS again, then moves to reflection or reinforcement. Reinforcement only runs when an explicit task set is configured. It is bounded by `max_iterations`, writes a Skill evolution trace, rejects regressions through the existing HQS gate, and writes the reinforcement result back to semantic memory.

Skill evolution also applies a candidate quality gate. A rewritten Skill can be rejected when it regresses average HQS, fails minimum improvement, worsens a task score, or regresses critical dimensions such as task completion, instruction following, output structure, or risk control.

**HQS**

Health and Quality Score. Scores use `0-5` dimensions and average them.

AgentForge currently supports:

- Skill-level HQS
- Response-level HQS
- System-level HQS

Response HQS includes calibration, confidence, memory usefulness, and generic-output penalties. System HQS scores tool reliability, memory retrieval quality, Skill selection accuracy, trace completeness, recovery ability, and user experience.

**Memory**

Local three-layer memory:

```text
data/memory/
  working_memory.json
  episodes.jsonl
  semantic_memory.json
```

`data/` is ignored by git.

Retrieval returns ranked episodic and semantic memories with:

- `_memory_rank`
- `_memory_score`
- `_memory_reasons`
- `_memory_matched_tokens`

`retrieve_context_for_task()` also returns a compact `retrieval` summary used by traces and the Web workbench.

## Web Workbench

The local Web workbench is served from the standard-library HTTP server and uses static HTML/CSS/JS.

Main panels:

- Chat
- Generate Skill
- Run Skill
- Evolve Skill

Inspection panels:

- HQS score bars and dimensions
- Run metadata
- Warnings
- Artifacts
- Timeline
- Drill-down tabs for Trace, HQS, Memory, and Skill Diff

The Trace drill-down fetches the latest trace JSON and shows trace type, schema, execution state, trace steps, artifacts, and errors. The HQS drill-down shows response and system dimensions. The Memory drill-down shows retrieval scores, reasons, recent episodes, and semantic memory. The Skill Diff drill-down reads the current Skill version and displays `diff.patch` when present.

## Skill Format

Every valid Skill must contain:

```md
# <Skill Name>

## Purpose

## When to Use

## Inputs

## Outputs

## Workflow

## Constraints

## Quality Criteria

## Failure Modes

## Examples

## Version Notes
```

## Task Set Format

JSON task sets use this shape:

```json
{
  "name": "sample_ui_review_basic",
  "description": "Sample UI review tasks.",
  "tasks": [
    {
      "id": "dashboard_readability",
      "input": "Review an admin dashboard with dense metrics.",
      "expected_output": ["issues", "reasons", "recommendations"],
      "criteria": ["structured report", "specific recommendations"]
    }
  ]
}
```

YAML task sets are supported only when `PyYAML` is installed. JSON is the default MVP format.

## Samples

Committed samples:

```text
examples/skills/ui_review_skill/v1/SKILL.md
tasksets/sample_ui_review_basic.json
```

The Skill selector scans both `skills/` and `examples/skills/`. Local Skills win over sample Skills when both match.

## Runtime Artifacts

AgentForge writes local artifacts to:

```text
skills/
runs/
traces/
data/memory/
```

Git ignores generated runtime artifacts except committed placeholders and explicit samples.

Do not commit:

- `config/providers.json`
- generated `skills/*`
- generated `runs/*`
- generated `traces/*`
- `data/*`

Artifact cleanup only targets old trace JSON files and run directories. It never deletes Skills, task sets, provider config, or memory.

## JSON Validation

JSON artifacts pass lightweight schema checks before writing. The validator checks required keys and JSON-safe values for:

- traces
- run results
- task sets
- HQS reports
- rewrite metadata
- candidate decisions
- memory JSON

This is intentionally small and dependency-free.

Trace validation checks supported trace types, required top-level fields, step records, artifact records, and error records. Traces embed schema metadata so inspection tools and the Web workbench can display the schema version used at write time.

## Project Layout

```text
src/agentforge/
  cli.py
  common/
    artifact_schema.py
    artifacts.py
    diagnostics.py
    file_store.py
    llm_client.py
    trace.py
    trace_inspector.py
  skill_generator/
    generator.py
    prompts.py
    requirement_parser.py
    skill_schema.py
    skill_writer.py
  skill_evolver/
    task_loader.py
    skill_runner.py
    hqs_evaluator.py
    reflector.py
    rewriter.py
    version_manager.py
    diff_writer.py
    evolution_loop.py
  agent/
    harness.py
    run.py
    intent_parser.py
    planner.py
    executor.py
    response_builder.py
    skill_selector.py
  memory/
    memory_manager.py
    stores.py
  hqs/
    response_evaluator.py
    system_evaluator.py
  web/
    app.py
    routes.py
    static/

examples/
tasksets/
runs/
skills/
traces/
tests/
```

## Development Notes

- Keep the system local-first.
- Preserve existing Skill versions.
- Keep generated artifacts readable.
- Route model calls through provider config.
- Prefer deterministic local behavior before opaque model behavior.
- Record important steps in traces.
- Keep Web/API, Skill generation, Skill evolution, memory, HQS, and Agent harness modular.
