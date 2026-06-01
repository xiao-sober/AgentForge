# AgentForge

AgentForge is a local-first self-improving Agent system with Skill generation, versioned artifacts, traceable execution, hierarchical memory, and HQS diagnostics.

This repository is currently implementing **Phase 1**: generating a compliant `SKILL.md` from a one-line requirement or a multi-turn conversation.

## Core Concepts

- **Skill**: a reusable Markdown instruction file saved under `skills/<skill_slug>/<version>/SKILL.md`.
- **Trace**: a JSON record of an important run, saved under `traces/`.
- **HQS**: Health & Quality Score. Full scoring arrives in Phase 2.
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

The Phase 1 runtime code only uses the Python standard library. `pytest` is installed for development tests.

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

`config/providers.json` is ignored by git so real API keys do not get committed.

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
