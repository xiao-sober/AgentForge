# AGENTS.md

## Project: AgentForge

AgentForge is a local-first, observable, modular Agent system for Web chat scenarios. Its core loop is:

```text
Requirement
  -> Generate Skill
  -> Run Skill
  -> Evaluate with HQS
  -> Reflect
  -> Rewrite Skill
  -> Version and Remember
  -> Use in Agent
```

The goal is not to build a generic chatbot. The project should evolve toward a controllable Agent platform with:

- Web chat entry
- Agent harness and core execution loop
- reusable versioned Skills
- three-layer memory
- autonomous Skill generation
- autonomous Skill reinforcement
- HQS diagnostics
- readable traces for all important steps

Keep the MVP simple, local, transparent, and easy to debug.

---

## Core Concepts

- **Harness**: runtime container for receiving user input, creating traces, loading memory, selecting or generating Skills, executing steps, running diagnostics, and saving results.
- **Agent**: the task understanding, planning, execution, reflection, and reinforcement subject.
- **Skill**: a reusable `SKILL.md` containing purpose, usage conditions, workflow, constraints, quality criteria, and examples.
- **Memory**: three-layer memory made of working memory, episodic memory, and semantic / Skill memory.
- **Self-generation**: generating Skills from user conversations or requirements.
- **Self-reinforcement**: improving Skills based on task results, HQS scores, and reflection.
- **HQS**: Health & Quality Score, used to diagnose response, Skill, and system quality.

---

## Development Principles

Follow these rules throughout the project:

1. **Local-first**: the system must run locally. External APIs are optional integrations, not core requirements.
2. **Observable**: important steps must produce inspectable traces.
3. **File-based where practical**: Skills must be Markdown files. Traces, memory, and runs should use JSON, JSONL, SQLite, or other readable local formats.
4. **Modular**: Web UI, Skill generation, Skill evolution, memory, HQS, and Agent harness must remain separated.
5. **MVP-first**: implement the smallest working version before adding advanced behavior.
6. **Version-safe**: never overwrite previous Skill versions. Always create `v1`, `v2`, `v3`, etc.
7. **Deterministic before complex**: prefer simple local logic before adding opaque model behavior.
8. **Trace failures**: user-facing errors should be understandable, and internal errors should be recorded in traces.
9. **Provider-configured models**: model calls should go through provider adapters and local JSON config, not hardcoded API keys or platform-specific logic.

Avoid hidden global state, silent failures, hardcoded absolute paths, large enterprise abstractions, and mixing UI logic with core Agent logic.

---

## Roadmap

Implement the project in three phases.

### Phase 1: Generate `SKILL.md`

Build the ability to transform a one-line requirement or multi-turn conversation into a valid, reusable Skill file.

Required behavior:

- parse requirement into a normalized structure
- generate compliant Markdown through a configured model provider, with deterministic local generation available for tests and offline development
- validate required Skill sections
- save to `skills/<skill_slug>/v1/SKILL.md`
- save a generation trace under `traces/`
- expose CLI command:

```bash
agentforge generate-skill --input "帮我生成一个 UI 分析 Skill"
```

Model provider configuration should live in `config/providers.json`, created from `config/providers.example.json`. Real API keys must not be committed.

Do not implement autonomous reflection, Skill evolution, full Web chat, memory, or HQS automation in this phase.

### Phase 2: Evolve Skills

Build a Skill improvement loop using task sets.

Required behavior:

- load a Skill version
- load JSON or YAML task sets
- run the Skill against each task
- save outputs under `runs/<skill_slug>/<version>/<timestamp>/`
- evaluate outputs with HQS
- generate a reflection report
- rewrite the Skill into the next version
- save metadata, diff, and evolution trace
- expose CLI command:

```bash
agentforge evolve-skill --skill skills/ui_review_skill/v1/SKILL.md --taskset tasksets/ui_review_basic.json --max-iterations 3
```

Stop conditions should include max iterations, target HQS, minimum improvement, or user stop.

### Phase 3: Full Agent System

Integrate the complete system.

Required behavior:

- Web chat MVP
- Agent harness
- intent parsing
- planner and executor
- response builder
- Skill selection and generation
- three-layer memory
- response-level, Skill-level, and system-level HQS
- autonomous reinforcement when HQS is low
- trace viewer or trace inspection path

MVP routes:

```text
/chat
/skills
/skills/:skillName
/skills/:skillName/:version
/memory
/traces
/hqs
```

---

## Recommended Build Order

Follow this order unless there is a clear reason to change it:

1. project skeleton, base config, README, and CLI entry
2. uv virtual environment and editable install
3. Skill schema validation
4. requirement parser
5. provider-configured model client
6. Skill writer
7. Phase 1 CLI and traces
8. task set loader
9. Skill runner
10. HQS evaluator
11. reflector
12. Skill rewriter
13. version manager
14. Phase 2 CLI
15. memory manager
16. Agent harness
17. Web chat MVP
18. autonomous reinforcement

---

## Required Skill Format

Every generated Skill must contain these sections:

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

Generated Skills must be validated before being treated as usable.

---

## Suggested Structure

Prefer Python for the initial MVP unless the repository already chooses TypeScript.

```text
agentforge/
  src/
    skill_generator/
      __init__.py
      requirement_parser.py
      skill_schema.py
      skill_writer.py
      prompts.py
    skill_evolver/
      __init__.py
      task_loader.py
      skill_runner.py
      hqs_evaluator.py
      reflector.py
      rewriter.py
      version_manager.py
      diff_writer.py
    common/
      llm_client.py
      file_store.py
      trace.py
  skills/
    .gitkeep
  tasksets/
    .gitkeep
  runs/
  traces/
    .gitkeep
  tests/
  README.md
  AGENTS.md
```

Phase 3 may add:

```text
apps/web/frontend/
apps/web/backend/
src/agent/
src/memory/
src/hqs/
```

---

## Trace Requirements

Every major run must create a trace.

Trace types:

```text
skill_generation
skill_execution
skill_evaluation
skill_evolution
agent_chat
memory_update
hqs_diagnosis
```

Minimum trace fields:

```json
{
  "trace_id": "string",
  "type": "string",
  "created_at": "ISO timestamp",
  "input": {},
  "steps": [],
  "output": {},
  "artifacts": [],
  "errors": []
}
```

---

## HQS Rubrics

HQS means Health & Quality Score.

Skill-level HQS dimensions:

- Task Completion
- Instruction Following
- Output Structure
- Specificity
- Robustness
- Risk / Hallucination Control

Response-level HQS dimensions:

- Intent Satisfaction
- Instruction Following
- Completeness
- Specificity
- Safety / Risk Control
- Memory Usefulness

System-level HQS dimensions:

- Tool Reliability
- Memory Retrieval Quality
- Skill Selection Accuracy
- Trace Completeness
- Recovery Ability
- User Experience

Each dimension uses a `0-5` score. Average the dimensions for the final HQS.

---

## Memory Design

Implement three memory layers:

- **Working Memory**: current run state, recent messages, active Skill, current plan, intermediate results.
- **Episodic Memory**: previous runs, conversations, generated Skills, execution results, HQS reports, reflections, and user corrections.
- **Semantic / Skill Memory**: long-term Skill summaries, best versions, tags, reusable patterns, known strengths, and known weaknesses.

The memory manager should provide:

```text
add_working_memory()
get_working_memory()
save_episode()
search_episodes()
upsert_semantic_memory()
search_semantic_memory()
retrieve_context_for_task()
```

---

## Testing Requirements

Tests should verify behavior, not implementation details.

Phase 1 tests:

- requirement parsing
- Skill schema validation
- Skill writing
- generation flow and trace creation

Phase 2 tests:

- task loading
- Skill running
- HQS scoring
- reflection generation
- rewriting
- version management
- evolution loop

Phase 3 tests:

- Agent harness
- memory manager
- Skill selection
- HQS diagnostics
- chat flow

---

## Non-goals for Early MVP

Do not implement these before the core loop works:

- multi-agent collaboration
- plugin marketplace
- enterprise RBAC
- distributed task queue
- cloud deployment platform
- complicated vector database dependency
- visual workflow builder
- mobile app
- billing system

---

## Documentation

Update `README.md` after each phase. It should include:

- what AgentForge is
- core concepts
- installation
- quick start
- generating a Skill
- evolving a Skill
- running the Agent
- directory structure
- Skill format
- task set format
- HQS scoring format
- trace format
- memory structure
- roadmap

---

## Commit Plan

Suggested commit sequence:

```text
chore: initialize AgentForge project structure
feat: add skill schema validation
feat: add requirement parser
feat: generate SKILL.md from requirement
feat: add skill generation trace
feat: add taskset loader
feat: run skill on taskset
feat: add HQS evaluator
feat: add skill reflection report
feat: add skill rewriter and version manager
feat: add skill evolution CLI
feat: add three-layer memory manager
feat: add agent harness
feat: add web chat MVP
feat: connect HQS to autonomous reinforcement
docs: update README and examples
```

---

## Implementation Notes for AI Coding Agents

When working on this repository:

1. Preserve previous Skill versions.
2. Validate generated Skills before saving them as usable.
3. Save traces for generation, execution, evaluation, and evolution.
4. Keep generated artifacts readable and inspectable.
5. Put prompts in dedicated files or modules.
6. Load API keys from `config/providers.json` or environment references inside that JSON; never hardcode secrets.
7. Prefer small functions, typed structures, explicit paths, and simple errors.
8. Implement the smallest working version first when requirements are uncertain.
9. Keep the core loop working before improving UI polish.
