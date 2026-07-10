# AGENTS.md

## Project: AgentForge

AgentForge is evolving into a local-first, observable, governable, multi-agent autonomous platform.

This file is the stable project rulebook for AI coding agents working in this repository. It should stay short and operational. Detailed roadmap, runtime design, and handoff state live in `docs/`.

## Required Reading

Before substantial work, read these files in order:

1. `docs/development_handoff.md`
2. `docs/multi_agent_autonomous_platform_goal.md`
3. `docs/runtime_governance_and_source_design.md`
4. `README.md`
5. Source files and tests around the module being changed

If these files conflict, prefer the newest handoff and target documents unless the user explicitly gives a newer instruction.

## Current Source Of Truth

- Long-term platform target: `docs/multi_agent_autonomous_platform_goal.md`
- Runtime, governance, source, and policy design: `docs/runtime_governance_and_source_design.md`
- Current progress and next-step state: `docs/development_handoff.md`
- Usage and repository overview: `README.md`

`AGENTS.md` should not duplicate the full roadmap. The old Skill-only Phase 1/2/3 roadmap is historical and must not be treated as the current project scope.

## Core Direction

The project target includes:

- Agent runtime with typed state, graph execution, checkpoints, and resumability
- Goal/task graph with autonomous planning, execution, review, reflection, and retry
- Multi-agent roles such as supervisor, planner, executor, reviewer, critic, memory, and knowledge agents
- File Source Management with `SourceRef` and a shared resolver for project files, uploads, imports, and explicit external mounts
- Separate Memory, Knowledge, and Context systems
- Governance for approval, budget, audit, rollback, resource locks, and risk control
- Provider-based model routing, secret references, execution profiles, and observable artifacts
- Skill generation and Skill evolution as platform assets, not the entire platform

## Development Principles

Follow these principles throughout the repository:

1. Keep the system local-first. External APIs are optional integrations and must be replaceable.
2. Make important steps observable through traces, artifacts, logs, or audit events.
3. Prefer readable local formats such as Markdown, JSON, JSONL, SQLite, and explicit metadata files.
4. Keep Web UI, runtime, tools, memory, knowledge, context, HQS, and Skill systems modular.
5. Add autonomy only after the underlying operation is typed, traceable, and governable.
6. Route model calls through provider/model adapters. Do not hardcode API keys or provider-specific logic in business code.
7. Preserve user changes. Do not revert unrelated work.
8. Prefer small typed modules, explicit paths, clear errors, and behavior-focused tests.
9. Avoid hidden global state, silent failures, hardcoded absolute paths, and mixing UI logic with core Agent logic.

## Handoff Rule

Every completed, paused, or blocked development task must update `docs/development_handoff.md`.

The handoff should record:

- current phase or focus
- completed work
- in-progress or incomplete work
- next recommended steps
- key files changed
- validation run or explicitly not run
- important decisions, risks, and open questions

If the handoff is not updated, the development task is not complete.

## File And Source Policy

Do not make broad project-external file access by simply allowing arbitrary absolute paths.

Use or introduce structured source handling:

- `project`: files under the repository root
- `uploaded`: files copied into the project-owned upload area
- `imported`: files intentionally imported into project-owned storage
- `external_mount`: explicitly configured read-only external locations

Project files and external files should be represented through `SourceRef`-style metadata and resolved through one shared file source layer. External mounts are read-only by default and must be explicit. System assets such as Skills, tasksets, traces, provider config, memory, knowledge indexes, and run artifacts should stay under project-owned directories.

Private code, private documents, secrets, and sensitive source text must not be sent to external model or embedding APIs unless policy/configuration explicitly allows it.

## Agent Runtime Policy

New autonomous or multi-agent behavior must be:

- stateful and resumable
- traceable and auditable
- bounded by model/tool budget
- governed by permission and risk policy
- safe around concurrent writes
- able to preserve citations and artifact references

Tool calls should have schema, timeout, risk level, permission behavior, artifacts, and audit records. High-risk operations need approval and a rollback or change-record strategy. Multi-agent writes to shared files, Skills, memory, knowledge indexes, artifacts, or budget state need resource locks or explicit rejection.

## Skill Rules

Skills are versioned Markdown assets. Never overwrite previous Skill versions.

Every generated or evolved Skill must be validated before it is treated as usable. Required sections are:

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

## Trace, Artifact, Memory, And Knowledge Rules

Major runs must produce trace or run records. Important tool calls, model calls, errors, generated files, decisions, and user approvals should be inspectable.

Keep these systems separate:

- Memory stores experience, preferences, corrections, episodes, and retrieval references.
- Knowledge stores indexed project facts, documents, code summaries, Skill docs, artifact summaries, and multimodal assets with citations.
- Context controls what each model call sees, including compression, selection, redaction, and prompt snapshots.

Vector indexing belongs to the Knowledge Layer. Memory can reference knowledge chunks, episodes, and artifacts but should not become an unstructured vector dump. Prompt snapshots are disabled or redacted by default unless the relevant policy allows storage.

## Testing Expectations

Tests should verify behavior rather than implementation details.

- Runtime, governance, source, memory, knowledge, context, and multi-agent changes should include focused unit or integration tests.
- Web UI changes should run relevant lint/typecheck/build commands and visual checks when practical.
- Docs-only changes should at least run `git diff --check` on changed Markdown/config files.
- If validation cannot be run, record that explicitly in the handoff and final response.

## Implementation Notes For Coding Agents

- Use project patterns before adding new abstractions.
- Keep prompts, policies, AgentSpecs, rubrics, and model routing config in dedicated versionable files or modules.
- Keep generated artifacts readable and inspectable.
- Preserve previous Skill versions and run artifacts.
- Do not hardcode secrets, API keys, provider names, or machine-specific absolute paths.
- Do not remove path/security checks without replacing them with the source governance model.
- Read the current handoff before starting and update it before finishing.
