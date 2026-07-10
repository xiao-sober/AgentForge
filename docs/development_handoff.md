# AgentForge Development Handoff

## Last Updated

- Date: 2026-07-10
- Updated By: Codex
- Current Focus: Multi-Agent autonomous platform goal documentation, runtime governance design, project-level agent rule alignment, and README restructuring

## Current Phase

Documentation and architecture target definition.

The project goal has been expanded from a conservative Agent Harness target into a mature Multi-Agent Autonomous Platform target. The current implementation work has not started for these new modules yet; this handoff records the documentation baseline for the next development phase.

## Completed

- Renamed the long-term target document from `docs/autonomous_agent_platform_goal.md` to `docs/multi_agent_autonomous_platform_goal.md`.
- Updated `README.md` to point to the new target document path.
- Added mature Multi-Agent platform goals, including runtime, goal management, task graph, planning, multi-agent roles, governance, rollback, memory, evaluation, and Web operations center.
- Added framework direction: AgentForge-owned runtime with LangGraph-style state graph, plus optional adapters for external frameworks.
- Added Context Engineering and Compression as a first-class platform capability.
- Added Context Inspector as a Web workbench page target.
- Added this development handoff mechanism.
- Added Knowledge Layer planning with local-first hybrid retrieval.
- Selected `qwen3-vl-embedding` as the target embedding model through a provider adapter.
- Added Knowledge Base Web page, Knowledge API, Knowledge CLI, data directory, tests, risks, and phased delivery plan.
- Added File Source Management planning for project files, uploaded files, and explicit read-only external mounts.
- Recorded the current implementation limitation: uploaded files are copied under `data/uploads`, while direct project-external absolute paths are rejected by analysis handlers.
- Added Files / Sources Web page, Files API, files CLI, data directories, tests, risks, and Phase 8 acceptance criteria.
- Added `docs/runtime_governance_and_source_design.md` as the detailed design entry for sandbox, secrets, model router, file sources, artifact lifecycle, locks, policy, approval, and audit.
- Optimized the two architecture documents after review: clarified Memory vs Knowledge boundaries, moved governance primitives earlier, added prompt snapshot privacy defaults, added multimodal ingestion rules, added prompt/policy/AgentSpec versioning, and added retrieval evaluation.
- Updated `.gitignore` so only `docs/development_handoff.md`, `docs/runtime_governance_and_source_design.md`, and `docs/multi_agent_autonomous_platform_goal.md` remain trackable under `docs/`.
- Removed older tracked docs files from the Git index with `git rm --cached`; local copies remain in the workspace and are now ignored.
- Rewrote `AGENTS.md` from the first-version Skill-only roadmap into a stable project rulebook that points agents to the current handoff, platform goal, and runtime governance documents.
- Refactored `README.md` into a concise, formal project entry focused on positioning, quick start, provider setup, common commands, local artifacts, and documentation navigation.
- Added `docs/developer_usage.md` for detailed CLI, API, Web workbench, Task Router, provider testing, project structure, and validation guidance.
- Updated `.gitignore` so `docs/developer_usage.md` remains trackable together with the active architecture and handoff documents.

## In Progress

- No active code implementation is in progress from this documentation task.

## Next Recommended Steps

1. Start Phase 1: Runtime consolidation.
2. Define `src/agentforge/runtime/state.py` with typed Agent state.
3. Define graph/node/edge/checkpoint contracts before changing existing harness behavior.
4. Map existing `AgentHarness`, `AgentRunLoop`, `ToolCallingLoop`, and `WorkflowRunner` responsibilities into the new runtime design.
5. Keep old behavior passing while introducing the runtime layer.
6. After Memory 2.0, implement Knowledge Layer before Context Engineering so context assembly has a reliable retrieval source.
7. Before expanding analysis tools, introduce `FileSourceResolver` and structured `SourceRef` so `/chat`, Task Router, Knowledge Layer, and ContextManager share one source model.
8. Read `docs/runtime_governance_and_source_design.md` before implementing file source, sandbox, provider routing, secret handling, or concurrent multi-agent execution.

## Key Files Changed

- `README.md`
- `AGENTS.md`
- `.gitignore`
- `docs/developer_usage.md`
- `docs/multi_agent_autonomous_platform_goal.md`
- `docs/development_handoff.md`

## Validation

- `git diff --check -- docs/multi_agent_autonomous_platform_goal.md` passed after the Context Engineering update.
- `git diff --check -- docs/multi_agent_autonomous_platform_goal.md docs/development_handoff.md README.md` passed after the Knowledge Layer update.
- `git diff --check -- docs/multi_agent_autonomous_platform_goal.md docs/development_handoff.md README.md` passed after the File Source Management update.
- `git diff --check -- README.md docs/multi_agent_autonomous_platform_goal.md docs/development_handoff.md docs/runtime_governance_and_source_design.md` passed after adding the runtime governance design document.
- `git diff --check -- docs/multi_agent_autonomous_platform_goal.md docs/runtime_governance_and_source_design.md docs/development_handoff.md README.md` passed after the architecture consistency optimization.
- `git diff --check -- AGENTS.md docs/development_handoff.md .gitignore README.md docs/multi_agent_autonomous_platform_goal.md docs/runtime_governance_and_source_design.md` passed after the `AGENTS.md` rulebook update.
- `git diff --check -- README.md docs/developer_usage.md docs/development_handoff.md .gitignore` passed after the README restructuring.
- `.gitignore` now ignores `docs/*` and explicitly unignores the three active architecture/handoff docs.
- `AGENTS.md` now treats `docs/development_handoff.md`, `docs/multi_agent_autonomous_platform_goal.md`, and `docs/runtime_governance_and_source_design.md` as the current source of truth.
- `README.md` now delegates detailed developer usage to `docs/developer_usage.md`.
- No code tests were run because this change is documentation-only.

## Not Yet Validated

- Full documentation link validation.
- Full repository test suite.

## Important Decisions

- AgentForge should not use CrewAI, AutoGen, LangChain, or Semantic Kernel as the core runtime.
- AgentForge should own its platform runtime and adopt a LangGraph-style state graph abstraction.
- External Agent frameworks may be supported through adapters, not by replacing AgentForge's core data model.
- Memory and Context are separate systems: Memory stores long-term knowledge; Context controls what each model call sees.
- Knowledge Base is separate from Memory: it stores indexed project facts, documents, code summaries, Skill docs, trace/artifact summaries, and multimodal assets with citations.
- Knowledge retrieval should be hybrid: SQLite FTS/BM25 + `qwen3-vl-embedding` vectors + metadata filters + citations.
- Private code and private documents must not be sent to external embedding APIs unless explicitly enabled by configuration.
- File handling should support three source types: `project`, `uploaded`, and `external_mount`.
- Direct arbitrary external absolute paths should remain rejected unless they come from upload/import, configured external mount, or one-time approval.
- `/chat` should consume structured `uploads` as source refs instead of relying only on file paths appended to natural-language messages.
- Runtime governance should include execution profiles, SecretRef redaction, ModelRouter, artifact retention, and resource locks before enabling broad autonomous execution.
- Memory should store experience and retrieval references; vector indexing belongs to the Knowledge Layer.
- Prompt snapshots are disabled by default and should normally be prompt manifests or redacted snapshots.
- Prompt, policy, AgentSpec, rubric, and model routing config changes must be versioned and referenced by runs.
- Knowledge retrieval needs event records, feedback, and evaluation metrics such as recall@k, citation accuracy, and stale retrieval rate.
- `AGENTS.md` is now a stable rulebook and navigation entry, not the full roadmap. Detailed targets belong in the two architecture documents.
- `README.md` should remain a concise project entry; detailed command/API/development material should move to dedicated docs files.
- Every future stage or long development task should update this handoff document before finishing.

## Risks And Open Questions

- The target platform is large; runtime consolidation should happen before multi-agent expansion.
- Context compression must preserve source citations to avoid losing critical facts.
- Governance, approval, budget, and rollback should be introduced before high-risk autonomous execution.
- The exact runtime graph API still needs design before implementation.
- `qwen3-vl-embedding` integration should go through a replaceable provider adapter and cache embeddings locally by content hash.
- Knowledge indexing must avoid stale vectors and preserve source citations.
- External file support can become a security risk if implemented by simply removing project-root path checks.
- File source events need audit/trace coverage before external mount support is enabled by default.
- Multi-agent parallel execution needs resource locks before Agents write shared files, Skills, memory, artifacts, or provider budget state.

## Read First Next Time

1. `docs/development_handoff.md`
2. `docs/multi_agent_autonomous_platform_goal.md`
3. `docs/runtime_governance_and_source_design.md`
4. `docs/agent_framework_file_analysis.md`
5. `README.md`
6. `src/agentforge/agent/harness.py`
7. `src/agentforge/agent/run_loop.py`
8. `src/agentforge/agent/tool_calling.py`
9. `src/agentforge/workflow/runner.py`
