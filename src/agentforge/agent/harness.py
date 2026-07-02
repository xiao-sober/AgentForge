from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from agentforge.agent.executor import ExecutionResult, execute_plan
from agentforge.agent.intent_parser import Intent, parse_intent
from agentforge.agent.planner import AgentPlan, PlanStep, build_plan
from agentforge.agent.response_builder import build_reinforcement_recommendation, build_response
from agentforge.agent.run import AgentRun, AgentRunStep
from agentforge.agent.run_loop import AgentRunLoop
from agentforge.agent.skill_selector import SkillCandidate, select_skill
from agentforge.agent.tools import AgentTool, ToolCall, ToolErrorSpec, ToolRegistry, ToolResult, ToolSchema
from agentforge.common.file_store import write_json
from agentforge.common.llm_client import LLMClient
from agentforge.common.trace import utc_now_iso, write_trace
from agentforge.hqs.response_evaluator import ResponseHQSReport, evaluate_response
from agentforge.hqs.system_evaluator import SystemHQSReport, evaluate_system
from agentforge.memory.memory_manager import MemoryManager
from agentforge.skill_evolver.evolution_loop import evolve_skill
from agentforge.skill_evolver.version_manager import parse_skill_version_path


@dataclass(frozen=True)
class AgentChatResult:
    response: str
    trace_path: Path
    hqs: ResponseHQSReport
    system_hqs: SystemHQSReport
    intent: Intent
    plan: AgentPlan
    selected_skill: SkillCandidate | None
    execution: ExecutionResult
    memory_context: dict[str, Any]
    episode: dict[str, Any]
    reinforcement: dict[str, Any]
    run: AgentRun
    reflection: dict[str, Any]
    stop_reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run.run_id,
            "response": self.response,
            "trace_path": str(self.trace_path),
            "hqs": self.hqs.to_dict(),
            "system_hqs": self.system_hqs.to_dict(),
            "intent": self.intent.to_dict(),
            "plan": self.plan.to_dict(),
            "selected_skill": self.selected_skill.to_dict() if self.selected_skill else None,
            "execution": self.execution.to_dict(),
            "memory_context": self.memory_context,
            "episode": self.episode,
            "reinforcement": self.reinforcement,
            "reflection": self.reflection,
            "stop_reason": self.stop_reason,
            "run": self.run.to_dict(),
        }


class AgentHarness:
    def __init__(
        self,
        project_root: Path | str = ".",
        llm_client: LLMClient | None = None,
        response_hqs_threshold: float = 3.5,
        reinforcement_taskset_path: Path | str | None = None,
        reinforcement_max_iterations: int = 1,
    ) -> None:
        self.project_root = Path(project_root).resolve()
        self.llm_client = llm_client
        self.response_hqs_threshold = response_hqs_threshold
        self.reinforcement_taskset_path = Path(reinforcement_taskset_path) if reinforcement_taskset_path else None
        if reinforcement_max_iterations < 1:
            raise ValueError("reinforcement_max_iterations must be at least 1.")
        self.reinforcement_max_iterations = reinforcement_max_iterations
        self.memory = MemoryManager(self.project_root)

    def chat(self, user_input: str) -> AgentChatResult:
        run = AgentRun.create(user_input)
        errors: list[dict[str, Any]] = []
        artifacts: list[dict[str, str]] = []
        state: dict[str, Any] = {"user_input": user_input, "quality_retry_count": 0}
        loop = AgentRunLoop(run, self._build_tool_registry(state, run, errors, artifacts), self.memory)

        loop.execute(ToolCall("receive_input", {"message": user_input}))
        loop.execute(ToolCall("parse_intent", {"message": user_input}))
        loop.execute(ToolCall("retrieve_memory_context", {"query": user_input}))
        loop.execute(ToolCall("select_skill"))
        loop.execute(ToolCall("build_plan"))
        loop.execute(ToolCall("execute_plan"))
        observe_result = loop.execute(ToolCall("observe_execution"))
        _mark_plan_tool_status(state, "observe_execution", observe_result.status)
        if state["execution"].selected_skill:
            semantic_result = loop.execute(ToolCall("update_semantic_memory"))
            _mark_plan_tool_status(state, "update_semantic_memory", semantic_result.status)
        response_result = loop.execute(ToolCall("build_response"))
        _mark_plan_tool_status(state, "build_response", response_result.status)
        loop.execute(ToolCall("evaluate_response_hqs"))
        gate = loop.execute(ToolCall("hqs_gate")).output
        if gate.get("decision") == "retry_response" and loop.can_iterate():
            loop.next_iteration()
            state["response_guidance"] = gate
            loop.execute(ToolCall("replan_response"))
            response_result = loop.execute(ToolCall("build_response"))
            _mark_plan_tool_status(state, "build_response", response_result.status)
            loop.execute(ToolCall("evaluate_response_hqs"))
            loop.execute(ToolCall("hqs_gate"))
        loop.execute(ToolCall("reflect"))
        loop.execute(ToolCall("reinforcement_check"))
        loop.execute(ToolCall("save_episode_memory"))

        intent: Intent = state["intent"]
        memory_context: dict[str, Any] = state["memory_context"]
        selected_skill: SkillCandidate | None = state.get("selected_skill")
        plan: AgentPlan = state["plan"]
        execution = state["execution"]
        response: str = state["response"]
        response_hqs: ResponseHQSReport = state["response_hqs"]
        reflection: dict[str, Any] = state["reflection"]
        reinforcement: dict[str, Any] = state["reinforcement"]
        episode: dict[str, Any] = state["episode"]

        stop_reason = _stop_reason(execution.errors, reflection, reinforcement)
        run.finish(
            status="failed" if _has_blocking_error(execution.errors) else "completed",
            stop_reason=stop_reason,
            reflection=reflection,
        )

        trace_output = {
            "run_id": run.run_id,
            "response": response,
            "response_hqs": response_hqs.to_dict(),
            "execution_state": execution.execution_state,
            "plan_step_results": execution.plan_step_results,
            "episode_id": episode["episode_id"],
            "reflection": reflection,
            "reinforcement": reinforcement,
            "stop_reason": stop_reason,
        }
        trace_path = write_trace(
            project_root=self.project_root,
            trace_type="agent_chat",
            input_data={"message": user_input, "run_id": run.run_id},
            output=trace_output,
            steps=[step.to_dict() for step in run.steps],
            artifacts=artifacts,
            errors=errors,
            extra_fields={"run": run.to_dict()},
        )

        system_hqs = evaluate_system(
            {
                "response": response,
                "trace_path": str(trace_path),
                "steps": [step.to_dict() for step in run.steps],
                "errors": errors,
                "memory_context": memory_context,
                "intent": intent.to_dict(),
                "selected_skill": execution.selected_skill.to_dict() if execution.selected_skill else None,
                "generated_skill_path": str(execution.generated_skill.skill_path) if execution.generated_skill else None,
            }
        )
        _append_system_hqs_to_trace(trace_path, system_hqs)
        self.memory.add_working_memory(
            {
                "active_run": run.to_dict(),
                "last_response_hqs": response_hqs.to_dict(),
                "last_system_hqs": system_hqs.to_dict(),
                "last_trace_path": str(trace_path),
                "last_stop_reason": stop_reason,
            }
        )

        return AgentChatResult(
            response=response,
            trace_path=trace_path,
            hqs=response_hqs,
            system_hqs=system_hqs,
            intent=intent,
            plan=plan,
            selected_skill=selected_skill,
            execution=execution,
            memory_context=memory_context,
            episode=episode,
            reinforcement=reinforcement,
            run=run,
            reflection=reflection,
            stop_reason=stop_reason,
        )

    def _build_tool_registry(
        self,
        state: dict[str, Any],
        run: AgentRun,
        errors: list[dict[str, Any]],
        artifacts: list[dict[str, str]],
    ) -> ToolRegistry:
        registry = ToolRegistry()

        def receive_input(payload: dict[str, Any]) -> ToolResult:
            self.memory.add_working_memory(
                {
                    "active_run_id": run.run_id,
                    "last_user_input": str(payload.get("message", "")),
                    "active_at": utc_now_iso(),
                }
            )
            return ToolResult(output={"message_length": len(str(payload.get("message", "")))})

        def parse_input_intent(_: dict[str, Any]) -> ToolResult:
            intent = parse_intent(str(state["user_input"]))
            state["intent"] = intent
            self.memory.add_working_memory({"active_intent": intent.to_dict(), "active_run_id": run.run_id})
            return ToolResult(output={"intent": intent.to_dict()})

        def retrieve_memory(_: dict[str, Any]) -> ToolResult:
            memory_context = self.memory.retrieve_context_for_task(str(state["user_input"]))
            state["memory_context"] = memory_context
            return ToolResult(
                output={
                    "episode_count": len(memory_context.get("episodes", [])),
                    "semantic_count": len(memory_context.get("semantic_memory", [])),
                }
            )

        def choose_skill(_: dict[str, Any]) -> ToolResult:
            selected_skill = select_skill(state["intent"], self.project_root)
            state["selected_skill"] = selected_skill
            return ToolResult(output={"selected_skill": selected_skill.to_dict() if selected_skill else None})

        def plan_next_actions(_: dict[str, Any]) -> ToolResult:
            plan = build_plan(state["intent"], state.get("selected_skill"))
            state["plan"] = plan
            return ToolResult(output={"plan": plan.to_dict()})

        def run_execution_plan(_: dict[str, Any]) -> ToolResult:
            execution = execute_plan(
                state["plan"],
                state["intent"],
                state.get("selected_skill"),
                project_root=self.project_root,
                llm_client=self.llm_client,
            )
            errors.extend(execution.errors)
            artifacts.extend(execution.artifacts)
            state["execution"] = execution
            state["plan"] = _plan_with_status(state["plan"], "pending", execution.plan_step_results)
            return ToolResult(
                output={"execution": execution.to_dict()},
                artifacts=execution.artifacts,
                errors=execution.errors,
                status="failed" if _has_blocking_error(execution.errors) else "completed",
            )

        def observe(_: dict[str, Any]) -> ToolResult:
            observation = _observe_execution(state["execution"])
            state["observation"] = observation
            return ToolResult(output=observation, status="failed" if observation["blocking_error_count"] else "completed")

        def update_semantic(_: dict[str, Any]) -> ToolResult:
            execution: ExecutionResult = state["execution"]
            if not execution.selected_skill:
                return ToolResult(output={"updated": False}, status="skipped")
            self._record_skill_semantic_memory(execution.selected_skill, execution)
            artifact = {"type": "semantic_memory", "path": "data/memory/semantic_memory.json"}
            artifacts.append(artifact)
            return ToolResult(output={"updated": True, "path": artifact["path"]}, artifacts=[artifact])

        def build_agent_response(_: dict[str, Any]) -> ToolResult:
            response = build_response(
                state["intent"],
                state["plan"],
                state["execution"],
                state["memory_context"],
                project_root=self.project_root,
            )
            if state.get("response_guidance"):
                response = _append_quality_guidance(response, state["response_guidance"])
            state["response"] = response
            return ToolResult(output={"response_preview": response[:500], "response_length": len(response)})

        def score_response(_: dict[str, Any]) -> ToolResult:
            response_hqs = evaluate_response(
                str(state["user_input"]),
                state["response"],
                memory_context=state["memory_context"],
                intent=state["intent"].to_dict(),
            )
            state["response_hqs"] = response_hqs
            return ToolResult(output={"hqs": response_hqs.to_dict()})

        def hqs_gate(_: dict[str, Any]) -> ToolResult:
            response_hqs: ResponseHQSReport = state["response_hqs"]
            weak_dimensions = [dimension for dimension, score in response_hqs.scores.items() if score < 3.0]
            triggered = response_hqs.average_score < self.response_hqs_threshold or bool(weak_dimensions)
            can_retry = triggered and state["quality_retry_count"] < 1 and not _has_blocking_error(errors)
            decision = "retry_response" if can_retry else ("recommend_reflection" if triggered else "pass")
            if can_retry:
                state["quality_retry_count"] += 1
            output = {
                "decision": decision,
                "threshold": self.response_hqs_threshold,
                "average_hqs": response_hqs.average_score,
                "weak_dimensions": weak_dimensions,
                "retry_count": state["quality_retry_count"],
            }
            state["hqs_gate"] = output
            return ToolResult(output=output, status="completed" if decision == "pass" else "completed")

        def replan_response(_: dict[str, Any]) -> ToolResult:
            guidance = state.get("response_guidance") or {}
            output = {
                "reason": "response_quality_gate",
                "decision": guidance.get("decision"),
                "weak_dimensions": guidance.get("weak_dimensions", []),
                "next_tool": "build_response",
            }
            state["replan"] = output
            return ToolResult(output=output)

        def reflect(_: dict[str, Any]) -> ToolResult:
            reflection = _build_reflection(state["response_hqs"], state["execution"], self.response_hqs_threshold)
            state["reflection"] = reflection
            return ToolResult(output=reflection, status="completed" if reflection["triggered"] else "skipped")

        def check_reinforcement(_: dict[str, Any]) -> ToolResult:
            reinforcement = build_reinforcement_recommendation(
                state["response_hqs"].to_dict(),
                state["execution"],
                self.response_hqs_threshold,
                taskset_path=self._resolved_reinforcement_taskset_path(),
            )
            if reinforcement["triggered"]:
                self._maybe_reinforce_skill(reinforcement, state["execution"], errors, artifacts, run)
            state["reinforcement"] = reinforcement
            return ToolResult(output={"reinforcement": reinforcement})

        def save_episode(_: dict[str, Any]) -> ToolResult:
            execution: ExecutionResult = state["execution"]
            episode = self.memory.save_episode(
                {
                    "run_id": run.run_id,
                    "user_input": state["user_input"],
                    "response": state["response"],
                    "intent": state["intent"].to_dict(),
                    "plan": state["plan"].to_dict(),
                    "selected_skill": execution.selected_skill.to_dict() if execution.selected_skill else None,
                    "hqs": state["response_hqs"].to_dict(),
                    "hqs_gate": state.get("hqs_gate"),
                    "reflection": state["reflection"],
                    "reinforcement": state["reinforcement"],
                }
            )
            state["episode"] = episode
            return ToolResult(output={"episode_id": episode["episode_id"]})

        for tool in [
            AgentTool(
                "receive_input",
                "input",
                receive_input,
                "Receive user input.",
                input_schema=ToolSchema.from_types(required={"message": "string"}, allow_extra=False),
                output_schema=ToolSchema.from_types(required={"message_length": "integer"}),
                error_specs=[ToolErrorSpec("ToolInputValidationError", "Invalid user input payload.", False)],
                permission_level="write",
                idempotent=False,
            ),
            AgentTool(
                "parse_intent",
                "reasoning",
                parse_input_intent,
                "Parse user intent.",
                input_schema=ToolSchema.from_types(required={"message": "string"}, allow_extra=True),
                output_schema=ToolSchema.from_types(required={"intent": "object"}),
                permission_level="read",
                idempotent=True,
            ),
            AgentTool(
                "retrieve_memory_context",
                "memory",
                retrieve_memory,
                "Retrieve working, episodic, and semantic memory.",
                input_schema=ToolSchema.from_types(optional={"query": "string"}, allow_extra=False),
                output_schema=ToolSchema.from_types(required={"episode_count": "integer", "semantic_count": "integer"}),
                error_specs=[ToolErrorSpec("MemoryReadError", "Memory retrieval failed.", False)],
                permission_level="read",
                idempotent=True,
            ),
            AgentTool(
                "select_skill",
                "skill_selection",
                choose_skill,
                "Select the best available Skill.",
                input_schema=ToolSchema.from_types(allow_extra=False),
                output_schema=ToolSchema.from_types(required={"selected_skill": "any"}),
                permission_level="read",
                idempotent=True,
            ),
            AgentTool(
                "build_plan",
                "planning",
                plan_next_actions,
                "Build a structured Agent plan.",
                input_schema=ToolSchema.from_types(allow_extra=False),
                output_schema=ToolSchema.from_types(required={"plan": "object"}),
                permission_level="read",
                idempotent=True,
            ),
            AgentTool(
                "execute_plan",
                "execution",
                run_execution_plan,
                "Execute the current plan.",
                input_schema=ToolSchema.from_types(allow_extra=False),
                output_schema=ToolSchema.from_types(required={"execution": "object"}),
                error_specs=[
                    ToolErrorSpec("LLMProviderError", "Provider execution failed.", False),
                    ToolErrorSpec("SkillExecutionError", "Skill execution failed.", False),
                ],
                permission_level="execute",
                idempotent=False,
                timeout_seconds=120,
            ),
            AgentTool(
                "observe_execution",
                "observation",
                observe,
                "Observe execution output and errors.",
                input_schema=ToolSchema.from_types(allow_extra=False),
                output_schema=ToolSchema.from_types(required={"action": "string", "has_output": "boolean"}),
                permission_level="read",
                idempotent=True,
            ),
            AgentTool(
                "update_semantic_memory",
                "memory",
                update_semantic,
                "Update Skill semantic memory.",
                input_schema=ToolSchema.from_types(allow_extra=False),
                output_schema=ToolSchema.from_types(required={"updated": "boolean"}, optional={"path": "string"}),
                error_specs=[ToolErrorSpec("MemoryWriteError", "Semantic memory update failed.", False)],
                permission_level="write",
                idempotent=False,
            ),
            AgentTool(
                "build_response",
                "response",
                build_agent_response,
                "Build the user-facing response.",
                input_schema=ToolSchema.from_types(allow_extra=False),
                output_schema=ToolSchema.from_types(required={"response_preview": "string", "response_length": "integer"}),
                permission_level="write",
                idempotent=False,
            ),
            AgentTool(
                "evaluate_response_hqs",
                "evaluation",
                score_response,
                "Evaluate response HQS.",
                input_schema=ToolSchema.from_types(allow_extra=False),
                output_schema=ToolSchema.from_types(required={"hqs": "object"}),
                permission_level="read",
                idempotent=True,
            ),
            AgentTool(
                "hqs_gate",
                "control",
                hqs_gate,
                "Gate the response on HQS.",
                input_schema=ToolSchema.from_types(allow_extra=False),
                output_schema=ToolSchema.from_types(
                    required={
                        "decision": "string",
                        "threshold": "number",
                        "average_hqs": "number",
                        "weak_dimensions": "array",
                        "retry_count": "integer",
                    }
                ),
                permission_level="control",
                idempotent=False,
            ),
            AgentTool(
                "replan_response",
                "planning",
                replan_response,
                "Replan response construction after HQS gate.",
                input_schema=ToolSchema.from_types(allow_extra=False),
                output_schema=ToolSchema.from_types(required={"reason": "string", "next_tool": "string"}),
                permission_level="control",
                idempotent=False,
            ),
            AgentTool(
                "reflect",
                "reflection",
                reflect,
                "Reflect on weak response quality.",
                input_schema=ToolSchema.from_types(allow_extra=False),
                output_schema=ToolSchema.from_types(required={"triggered": "boolean", "recommendation": "string"}),
                permission_level="read",
                idempotent=True,
            ),
            AgentTool(
                "reinforcement_check",
                "control",
                check_reinforcement,
                "Check autonomous reinforcement conditions.",
                input_schema=ToolSchema.from_types(allow_extra=False),
                output_schema=ToolSchema.from_types(required={"reinforcement": "object"}),
                error_specs=[
                    ToolErrorSpec("MissingTaskset", "Reinforcement requires an explicit taskset.", False),
                    ToolErrorSpec("SkillEvolutionError", "Skill reinforcement evolution failed.", False),
                ],
                permission_level="admin",
                idempotent=False,
                timeout_seconds=180,
            ),
            AgentTool(
                "save_episode_memory",
                "memory",
                save_episode,
                "Save episodic memory.",
                input_schema=ToolSchema.from_types(allow_extra=False),
                output_schema=ToolSchema.from_types(required={"episode_id": "string"}),
                error_specs=[ToolErrorSpec("MemoryWriteError", "Episode memory update failed.", False)],
                permission_level="write",
                idempotent=False,
            ),
        ]:
            registry.register(tool)
        return registry

    def _complete_step(
        self,
        step: AgentRunStep,
        run: AgentRun,
        output: Any = None,
        artifacts: list[dict[str, Any]] | None = None,
        errors: list[dict[str, Any]] | None = None,
        status: str = "completed",
    ) -> None:
        step.complete(output=output, artifacts=artifacts, errors=errors, status=status)
        run.transition(
            _manual_step_phase(step.kind),
            status=status,
            reason=step.name,
            details={"step_id": step.step_id, "kind": step.kind},
        )
        self.memory.add_working_memory(
            {
                "active_run_id": run.run_id,
                "active_run_status": run.status,
                "active_run_phase": run.phase,
                "active_run_steps": [item.to_dict() for item in run.steps],
                "active_run_phase_history": run.phase_history,
                "last_step": step.to_dict(),
                "updated_at": utc_now_iso(),
            }
        )

    def _record_skill_semantic_memory(self, skill: SkillCandidate, execution: ExecutionResult) -> None:
        self.memory.upsert_semantic_memory(
            skill.skill_slug,
            {
                "summary": skill.title,
                "best_version": skill.version,
                "skill_path": str(skill.skill_path),
                "tags": _tags_for_skill(skill.skill_slug),
                "last_action": execution.action,
                "strengths": ["selected by deterministic local matcher"],
                "known_weaknesses": [],
            },
        )

    def _maybe_reinforce_skill(
        self,
        recommendation: dict[str, Any],
        execution: ExecutionResult,
        errors: list[dict[str, Any]],
        artifacts: list[dict[str, str]],
        run: AgentRun,
    ) -> None:
        taskset_path = self._resolved_reinforcement_taskset_path()
        if not taskset_path:
            return
        if not taskset_path.exists():
            recommendation["status"] = "blocked_missing_taskset"
            recommendation["recommendation"] = "Reinforcement was not run because the explicit task set does not exist."
            return
        if not execution.selected_skill:
            recommendation["status"] = "blocked_no_skill"
            recommendation["recommendation"] = "Reinforcement was not run because no Skill was selected or generated."
            return
        try:
            evolution = evolve_skill(
                execution.selected_skill.skill_path,
                taskset_path,
                project_root=self.project_root,
                max_iterations=self.reinforcement_max_iterations,
            )
            final_changed = evolution.final_skill_path.resolve() != execution.selected_skill.skill_path.resolve()
            accepted_versions = [
                iteration.rewritten_skill.version
                for iteration in evolution.iterations
                if iteration.rewritten_skill is not None
            ]
            recommendation.update(
                {
                    "status": "evolved" if final_changed else "evaluated_no_change",
                    "stable": _reinforcement_stable(evolution.to_dict()),
                    "evolution": evolution.to_dict(),
                    "final_skill_path": str(evolution.final_skill_path),
                    "accepted_versions": accepted_versions,
                    "stop_reason": evolution.stop_reason,
                }
            )
            artifact = {"type": "skill_evolution_trace", "path": _relative_or_absolute(evolution.trace_path, self.project_root)}
            artifacts.append(artifact)
            self._complete_step(
                run.add_step("run_reinforcement_evolution", "reinforcement", {"skill_path": str(execution.selected_skill.skill_path)}),
                run,
                output={
                    "trace_path": str(evolution.trace_path),
                    "stop_reason": evolution.stop_reason,
                    "status": recommendation["status"],
                    "accepted_versions": accepted_versions,
                },
                artifacts=[artifact],
            )
            memory_record = self._record_reinforcement_memory(execution.selected_skill, recommendation)
            recommendation["memory_update"] = {
                "path": "data/memory/semantic_memory.json",
                "key": execution.selected_skill.skill_slug,
                "best_version": memory_record.get("best_version"),
            }
            self._complete_step(
                run.add_step(
                    "write_reinforcement_memory",
                    "memory",
                    {
                        "skill_slug": execution.selected_skill.skill_slug,
                        "status": recommendation["status"],
                        "taskset_path": str(taskset_path),
                    },
                ),
                run,
                output=recommendation["memory_update"],
                artifacts=[{"type": "semantic_memory", "path": "data/memory/semantic_memory.json"}],
            )
        except Exception as exc:
            recommendation["status"] = "evolution_failed"
            recommendation["recommendation"] = "Reinforcement evolution failed and was recorded in the agent trace."
            errors.append({"error_type": exc.__class__.__name__, "message": str(exc)})

    def _resolved_reinforcement_taskset_path(self) -> Path | None:
        if self.reinforcement_taskset_path is None:
            return None
        if self.reinforcement_taskset_path.is_absolute():
            return self.reinforcement_taskset_path
        return self.project_root / self.reinforcement_taskset_path

    def _record_reinforcement_memory(
        self,
        skill: SkillCandidate,
        recommendation: dict[str, Any],
    ) -> dict[str, Any]:
        final_skill_path = Path(str(recommendation.get("final_skill_path") or skill.skill_path)).resolve()
        try:
            final_info = parse_skill_version_path(final_skill_path)
            final_version = final_info.version
        except Exception:
            final_version = skill.version
        best_version = final_version if recommendation.get("status") == "evolved" else skill.version
        weak_dimensions = [
            str(dimension)
            for dimension in recommendation.get("weak_dimensions", [])
            if str(dimension).strip()
        ]
        record = {
            "summary": skill.title,
            "best_version": best_version,
            "skill_path": str(final_skill_path if recommendation.get("status") == "evolved" else skill.skill_path),
            "tags": _tags_for_skill(skill.skill_slug),
            "last_action": "reinforcement",
            "strengths": _reinforcement_strengths(recommendation),
            "known_weaknesses": weak_dimensions,
            "last_reinforcement": {
                "status": recommendation.get("status"),
                "stable": recommendation.get("stable"),
                "taskset_path": recommendation.get("taskset_path"),
                "threshold": recommendation.get("threshold"),
                "average_hqs": recommendation.get("response_hqs", {}).get("average_score"),
                "weak_dimensions": weak_dimensions,
                "final_skill_path": recommendation.get("final_skill_path"),
                "accepted_versions": recommendation.get("accepted_versions", []),
                "stop_reason": recommendation.get("stop_reason"),
            },
        }
        return self.memory.upsert_semantic_memory(skill.skill_slug, record)


def _tags_for_skill(skill_slug: str) -> list[str]:
    return [token for token in skill_slug.split("_") if token and token != "skill"]


def _plan_status(errors: list[dict[str, Any]]) -> str:
    return "failed" if _has_blocking_error(errors) else "completed"


def _mark_plan_tool_status(state: dict[str, Any], tool_name: str, status: str) -> None:
    plan = state.get("plan")
    if not isinstance(plan, AgentPlan):
        return
    state["plan"] = _plan_with_tool_status(plan, tool_name, status)


def _plan_with_tool_status(plan: AgentPlan, tool_name: str, status: str) -> AgentPlan:
    return AgentPlan(
        action=plan.action,
        steps=[
            PlanStep(
                step.name,
                step.action,
                status=status if step.tool_name == tool_name else step.status,
                tool_name=step.tool_name,
                step_id=step.step_id,
                depends_on=step.depends_on,
                tool_input=step.tool_input,
                expected_output=step.expected_output,
                required=step.required,
                max_retries=step.max_retries,
                permission_required=step.permission_required,
            )
            for step in plan.steps
        ],
        rationale=plan.rationale,
        objective=plan.objective,
        complexity=plan.complexity,
        subtasks=plan.subtasks,
        stop_conditions=plan.stop_conditions,
        max_steps=plan.max_steps,
    )


def _plan_with_status(
    plan: AgentPlan,
    status: str,
    step_results: list[dict[str, Any]] | None = None,
) -> AgentPlan:
    result_by_step_id = {
        str(result.get("plan_step_id")): str(result.get("status"))
        for result in (step_results or [])
        if result.get("plan_step_id")
    }
    return AgentPlan(
        action=plan.action,
        steps=[
            PlanStep(
                step.name,
                step.action,
                status=result_by_step_id.get(str(step.step_id), step.status if step.status != "pending" else status),
                tool_name=step.tool_name,
                step_id=step.step_id,
                depends_on=step.depends_on,
                tool_input=step.tool_input,
                expected_output=step.expected_output,
                required=step.required,
                max_retries=step.max_retries,
                permission_required=step.permission_required,
            )
            for step in plan.steps
        ],
        rationale=plan.rationale,
        objective=plan.objective,
        complexity=plan.complexity,
        subtasks=plan.subtasks,
        stop_conditions=plan.stop_conditions,
        max_steps=plan.max_steps,
    )


def _has_blocking_error(errors: list[dict[str, Any]]) -> bool:
    return any(not error.get("recoverable") for error in errors)


def _observe_execution(execution: ExecutionResult) -> dict[str, Any]:
    return {
        "action": execution.action,
        "has_output": bool(execution.output_text.strip()),
        "selected_skill": execution.selected_skill.to_dict() if execution.selected_skill else None,
        "generated_skill_path": str(execution.generated_skill.skill_path) if execution.generated_skill else None,
        "artifact_count": len(execution.artifacts),
        "recoverable_error_count": len([error for error in execution.errors if error.get("recoverable")]),
        "blocking_error_count": len([error for error in execution.errors if not error.get("recoverable")]),
    }


def _build_reflection(
    response_hqs: ResponseHQSReport,
    execution: ExecutionResult,
    threshold: float,
) -> dict[str, Any]:
    weak_dimensions = [dimension for dimension, score in response_hqs.scores.items() if score < 3.0]
    triggered = response_hqs.average_score < threshold or bool(weak_dimensions)
    if triggered:
        next_actions = [
            "Review weak HQS dimensions before returning the next response.",
            "Use an explicit task set before evolving a selected Skill.",
            "Preserve trace and episode memory for audit.",
        ]
        if execution.selected_skill:
            next_actions.append(f"Candidate Skill for reinforcement: {execution.selected_skill.skill_slug}/{execution.selected_skill.version}.")
        recommendation = "Reflection required before autonomous reinforcement."
    else:
        next_actions = ["Stop the run after saving trace and episode memory."]
        recommendation = "No reflection action required."

    return {
        "triggered": triggered,
        "threshold": threshold,
        "average_hqs": response_hqs.average_score,
        "weak_dimensions": weak_dimensions,
        "recommendation": recommendation,
        "next_actions": next_actions,
    }


def _stop_reason(
    errors: list[dict[str, Any]],
    reflection: dict[str, Any],
    reinforcement: dict[str, Any],
) -> str:
    if _has_blocking_error(errors):
        return "blocking_error"
    if reinforcement.get("status") == "evolved":
        return "reinforcement_evolved"
    if reinforcement.get("status") == "evaluated_no_change":
        return "reinforcement_evaluated_no_change"
    if reflection.get("triggered"):
        return "reflection_recommended"
    return "completed"


def _reinforcement_stable(evolution: dict[str, Any]) -> bool:
    iterations = evolution.get("iterations") or []
    for iteration in iterations:
        decision = str(iteration.get("decision", ""))
        if "rejected_regression" in decision:
            return False
    return True


def _reinforcement_strengths(recommendation: dict[str, Any]) -> list[str]:
    if recommendation.get("status") == "evolved":
        return ["reinforced with explicit taskset", "candidate accepted by deterministic HQS gate"]
    if recommendation.get("status") == "evaluated_no_change":
        return ["evaluated against explicit reinforcement taskset", "no regressing version was accepted"]
    return ["selected by deterministic local matcher"]


def _append_system_hqs_to_trace(trace_path: Path, system_hqs: SystemHQSReport) -> None:
    payload = json.loads(trace_path.read_text(encoding="utf-8"))
    output = payload.get("output")
    if isinstance(output, dict):
        output["system_hqs"] = system_hqs.to_dict()
    payload["system_hqs"] = system_hqs.to_dict()
    write_json(trace_path, payload)


def _append_quality_guidance(response: str, guidance: dict[str, Any]) -> str:
    weak_dimensions = guidance.get("weak_dimensions") or []
    weak_text = ", ".join(str(item) for item in weak_dimensions) if weak_dimensions else "overall score below threshold"
    addition = "\n".join(
        [
            "",
            "## Quality Gate",
            "",
            f"- Decision: {guidance.get('decision', 'retry_response')}",
            f"- Trigger: {weak_text}",
            "- Response was rebuilt once before reflection or reinforcement was considered.",
        ]
    )
    return response.rstrip() + "\n" + addition + "\n"


def _relative_or_absolute(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return str(path)


def _manual_step_phase(kind: str) -> str:
    if kind == "reinforcement":
        return "reinforcing"
    if kind == "memory":
        return "memory_updated"
    return "executing"
