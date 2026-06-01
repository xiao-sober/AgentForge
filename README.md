# AgentForge

AgentForge is a local-first self-improving Agent system with Skill generation, versioned artifacts, traceable execution, hierarchical memory, and HQS diagnostics.

This repository has completed **Phase 1** and now includes the **Phase 2 MVP**: running versioned Skills on task sets, scoring outputs with HQS, reflecting on results, and rewriting the next Skill version.

## Core Concepts

- **Skill**: a reusable Markdown instruction file saved under `skills/<skill_slug>/<version>/SKILL.md`.
- **Trace**: a JSON record of an important run, saved under `traces/`.
- **HQS**: Health & Quality Score. Phase 2 includes deterministic Skill-level scoring.
- **Memory**: three-layer Agent memory. Full memory arrives in Phase 3.

## Installation

Use Python 3.10 or newer.

Create the project virtual environment with `uv`:

```bash
uv venv .venv
```

Install the project and test tooling into that virtual environment:

```bash
uv pip install --python .venv\Scripts\python.exe -e ".[dev]"
```

Activate the environment if you want to run commands directly:

```bash
.venv\Scripts\activate
```

The core runtime uses the Python standard library. JSON task sets need no extra packages; YAML task sets require optional `PyYAML` if you choose to use them. `pytest` is installed for development tests.

## Model Providers

Phase 1 supports model-backed Skill generation through provider adapters. The first adapter is `openai_compatible`, which works with platforms that expose `/chat/completions`.

Create a local provider config from the example:

```bash
copy config\providers.example.json config\providers.json
```

Then edit `config/providers.json`:

```json
{
  "default_provider": "dashscope",
  "providers": {
    "dashscope": {
      "type": "openai_compatible",
      "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
      "api_key": "your-api-key",
      "model": "qwen3.6-plus",
      "timeout_seconds": 60,
      "temperature": 0.2,
      "max_tokens": 2500,
      "thinking_mode": {
        "enabled": false,
        "provider": "qwen"
      }
    }
  }
}
```

You can add other platforms by adding more entries under `providers` and changing `default_provider` or passing `--provider`.

Enable Qwen thinking mode for complex Skill generation tasks:

```json
"thinking_mode": {
  "enabled": true,
  "provider": "qwen",
  "thinking_budget": 500,
  "preserve_thinking": true
}
```

For Qwen OpenAI-compatible chat completions, AgentForge sends `enable_thinking` and optional Qwen thinking parameters in the request body.

## Quick Start

Generate a Skill with the configured model:

```bash
python -m agentforge generate-skill --input "帮我做一个能根据网页截图分析 UI 问题并给出优化建议的 Skill"
```

Use a specific provider or model:

```bash
python -m agentforge generate-skill --provider dashscope --model qwen3.6-plus --input "帮我做一个 UI 分析 Skill"
```

For offline development and tests, skip the model call:

```bash
python -m agentforge generate-skill --local-only --input "帮我做一个能根据网页截图分析 UI 问题并给出优化建议的 Skill"
```

Expected artifacts:

```text
skills/ui_review_skill/v1/SKILL.md
traces/<timestamp>_skill_generation.json
```

Validate an existing Skill:

```bash
agentforge validate-skill skills/ui_review_skill/v1/SKILL.md
```

Run a Skill against one input with deterministic local execution:

```bash
python -m agentforge run-skill --skill skills/ui_review_skill/v1/SKILL.md --input "Review this dashboard layout for hierarchy and readability."
```

Use a configured provider for Skill execution:

```bash
python -m agentforge run-skill --use-provider --provider dashscope --skill skills/ui_review_skill/v1/SKILL.md --input "Review this dashboard layout."
```

Evolve a Skill against a task set:

```bash
python -m agentforge evolve-skill --skill skills/ui_review_skill/v1/SKILL.md --taskset tasksets/ui_review_basic.json --max-iterations 3
```

Create a starter task set automatically when the target JSON file does not exist:

```bash
python -m agentforge evolve-skill --auto-create-taskset --skill skills/ui_review_skill/v1/SKILL.md --taskset tasksets/ui_review_basic.json --max-iterations 1
```

By default, Phase 2 execution and rewriting use deterministic local logic. Pass `--use-provider` to route execution and rewriting through the configured provider adapter.

Evolution uses a stability gate before accepting a new version. AgentForge first proposes a candidate Skill under the run directory, runs that candidate on the same task set, scores it with HQS, and only writes `skills/<skill_slug>/vN/SKILL.md` when the candidate does not regress and improves by at least `--min-improvement` (`0.01` by default). Use `--min-improvement 0` if you explicitly want to accept equal-scoring rewrites.

## Skill File Format

Every generated Skill must include:

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

Phase 2 can read JSON task sets:

```json
{
  "name": "ui_review_basic",
  "description": "Basic UI review cases.",
  "tasks": [
    {
      "id": "dashboard_layout",
      "input": "Review dashboard layout, visual hierarchy, and data readability.",
      "expected_output": ["issues", "reasons", "recommendations"],
      "criteria": ["structured report", "specific suggestions"]
    }
  ]
}
```

`--auto-create-taskset` can bootstrap a starter JSON task set from the Skill, but it is intended as a convenience baseline. Review and edit generated task sets before treating them as stable benchmarks.

## Phase 2 Artifacts

Skill runs are saved under:

```text
runs/<skill_slug>/<version>/<timestamp>/
```

Each run stores:

- `taskset.json`
- `skill_snapshot.md`
- `outputs/<task_id>.md`
- `run_result.json`
- `hqs_report.json` during evolution
- `reflection.md` during evolution
- `candidate/SKILL.md` and `candidate/decision.json` during evolution when a rewrite is proposed

Each rewrite creates the next version without overwriting prior versions:

```text
skills/<skill_slug>/v2/SKILL.md
skills/<skill_slug>/v2/metadata.json
skills/<skill_slug>/v2/diff.patch
```

## HQS Scoring

The Phase 2 deterministic evaluator scores each task output on `0-5` dimensions:

- Task Completion
- Instruction Following
- Output Structure
- Specificity
- Robustness
- Risk / Hallucination Control

The final HQS is the average of those dimensions across the task set.

## Trace Format

Skill generation traces include:

```json
{
  "trace_id": "string",
  "type": "skill_generation",
  "created_at": "ISO timestamp",
  "input": "source requirement",
  "steps": [],
  "output": {
    "parsed_requirement": {},
    "generated_skill_path": "skills/<skill_slug>/v1/SKILL.md",
    "validation_result": {}
  },
  "artifacts": [],
  "errors": []
}
```

For Phase 1 compatibility, the trace also exposes `parsed_requirement`, `generated_skill_path`, and `validation_result` at the top level.

Phase 2 writes additional traces:

- `skill_execution`
- `skill_evaluation`
- `skill_evolution`

## Directory Structure

```text
src/agentforge/
  cli.py
  common/
    file_store.py
    llm_client.py
    trace.py
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
tasksets/
runs/
skills/
traces/
tests/
```

## Development Roadmap

1. **Phase 1**: generate and validate `SKILL.md` from requirements.
2. **Phase 2**: run Skills on task sets, score with HQS, reflect, and rewrite new versions.
3. **Phase 3**: integrate Web chat, Agent harness, memory, diagnostics, and autonomous reinforcement.

## Tests

Run the current test suite:

```bash
.venv\Scripts\python.exe -m unittest discover -s tests
```

If `pytest` is installed:

```bash
.venv\Scripts\pytest.exe
```
