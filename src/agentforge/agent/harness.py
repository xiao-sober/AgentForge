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
from agentforge.agent.tool_calling import (
    ProviderModelPlanner,
    ScriptedModelPlanner,
    ToolCallPolicy,
    ToolCallingLoop,
    ToolCallingLoopResult,
    default_tool_call_policy,
    registry_model_schemas,
)
from agentforge.agent.tool_calling.model_planner import ToolCallingPlanner
from agentforge.common.file_store import write_json
from agentforge.common.llm_client import LLMClient
from agentforge.common.trace import utc_now_iso, write_trace
from agentforge.common.trace_inspector import inspect_trace
from agentforge.hqs.response_evaluator import ResponseHQSReport, evaluate_response
from agentforge.hqs.system_evaluator import SystemHQSReport, evaluate_system
from agentforge.memory.memory_manager import MemoryManager
from agentforge.skill_evolver.evolution_loop import evolve_skill
from agentforge.skill_evolver.version_manager import parse_skill_version_path
from agentforge.tools import AgentTool, ToolCall, ToolErrorSpec, ToolRegistry, ToolResult, ToolSchema
from agentforge.workflows import WorkflowRunner


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


@dataclass(frozen=True)
class AgentToolChatResult:
    response: str
    trace_path: Path
    hqs: ResponseHQSReport
    system_hqs: SystemHQSReport
    run: AgentRun
    tool_calling: ToolCallingLoopResult
    memory_context: dict[str, Any]
    episode: dict[str, Any]
    planner_metadata: dict[str, Any]
    stop_reason: str
    hqs_gate: dict[str, Any]
    quality_retry: dict[str, Any]
    final_answer_source: str
    tool_call_timeline: list[dict[str, Any]]
    parse_repair_count: int
    invalid_call_count: int
    agent_mode: str = "tool_calling_agent"

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run.run_id,
            "agent_mode": self.agent_mode,
            "response": self.response,
            "trace_path": str(self.trace_path),
            "hqs": self.hqs.to_dict(),
            "system_hqs": self.system_hqs.to_dict(),
            "tool_calling": self.tool_calling.to_dict(),
            "memory_context": self.memory_context,
            "episode": self.episode,
            "planner": self.planner_metadata,
            "stop_reason": self.stop_reason,
            "hqs_gate": self.hqs_gate,
            "quality_retry": self.quality_retry,
            "final_answer_source": self.final_answer_source,
            "tool_call_timeline": self.tool_call_timeline,
            "parse_repair_count": self.parse_repair_count,
            "invalid_call_count": self.invalid_call_count,
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
        run_service = WorkflowRunner.for_task(
            self.project_root,
            workflow_id="agent_chat_workflow",
            task_type="agent_chat",
            steps=[
                "receive_input",
                "parse_intent",
                "retrieve_memory_context",
                "select_skill",
                "build_plan",
                "execute_plan",
                "observe_execution",
                "update_semantic_memory",
                "build_response",
                "evaluate_response_hqs",
                "hqs_gate",
                "replan_response",
                "reflect",
                "reinforcement_check",
                "save_episode_memory",
            ],
        )
        run_service.start_run(
            task_type="agent_chat",
            title="Agent chat",
            input_data={"message": user_input},
            run_id=run.run_id,
            created_at=run.created_at,
        )
        errors: list[dict[str, Any]] = []
        artifacts: list[dict[str, str]] = []
        state: dict[str, Any] = {"user_input": user_input, "quality_retry_count": 0}
        loop = AgentRunLoop(run, self._build_tool_registry(state, run, errors, artifacts), self.memory, run_service=run_service)

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
        run_service.record_run(
            task_type="agent_chat",
            title="Agent chat",
            input_data={"message": user_input},
            output_data={**trace_output, "system_hqs": system_hqs.to_dict()},
            trace_path=trace_path,
            status=run.status,
            run_id=run.run_id,
            steps=[step.to_dict() for step in run.steps],
            artifacts=artifacts,
            hqs_reports={"response": response_hqs.to_dict(), "system": system_hqs.to_dict()},
            created_at=run.created_at,
        )
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

    def tool_chat(
        self,
        user_input: str,
        planner: ToolCallingPlanner | None = None,
        policy: ToolCallPolicy | None = None,
    ) -> AgentToolChatResult:
        run = AgentRun.create(user_input)
        run_service = WorkflowRunner.for_task(
            self.project_root,
            workflow_id="tool_calling_agent_workflow",
            task_type="tool_calling_agent",
            steps=[
                "receive_input",
                "parse_intent",
                "retrieve_memory_context",
                "inspect_latest_trace",
                "select_skill",
                "build_plan",
                "execute_plan",
                "observe_execution",
                "build_response",
                "evaluate_response_hqs",
                "replan_response",
            ],
        )
        run_service.start_run(
            task_type="tool_calling_agent",
            title="Tool-calling agent chat",
            input_data={"message": user_input},
            run_id=run.run_id,
            created_at=run.created_at,
        )
        errors: list[dict[str, Any]] = []
        artifacts: list[dict[str, str]] = []
        state: dict[str, Any] = {"user_input": user_input, "quality_retry_count": 0}
        registry = self._build_tool_registry(state, run, errors, artifacts)

        setup_loop = AgentRunLoop(run, registry, self.memory, run_service=run_service)
        setup_loop.execute(ToolCall("receive_input", {"message": user_input}))
        setup_loop.execute(ToolCall("parse_intent", {"message": user_input}))

        active_policy = policy or default_tool_call_policy()
        active_planner = planner or (
            ProviderModelPlanner(self.llm_client) if self.llm_client is not None else ScriptedModelPlanner.default()
        )
        available_tools = registry_model_schemas(registry, active_policy.allowed_tools)
        tool_loop = ToolCallingLoop(
            run,
            registry,
            self.memory,
            active_planner,
            active_policy,
            runtime_state=state,
            available_tools=available_tools,
            run_service=run_service,
        )
        loop_result = tool_loop.run_loop()

        trace_steps = [
            {
                "name": "harness_setup",
                "status": "completed",
                "tools": ["receive_input", "parse_intent"],
            },
            *loop_result.trace_steps,
        ]

        response = _tool_calling_response(loop_result, state)
        final_answer_source = _tool_calling_final_answer_source(loop_result, state)
        memory_context = state.get("memory_context")
        if not isinstance(memory_context, dict):
            memory_context = self.memory.retrieve_context_for_task(user_input)

        intent = state.get("intent")
        intent_payload = intent.to_dict() if isinstance(intent, Intent) else {}
        response_hqs = evaluate_response(
            user_input,
            response,
            memory_context=memory_context,
            intent=intent_payload,
        )
        state["response_hqs"] = response_hqs

        trace_steps.append(
            {
                "name": "evaluate_response_hqs",
                "status": "completed",
                "output": {"hqs": response_hqs.to_dict()},
            }
        )
        hqs_gate = _tool_calling_hqs_gate_decision(
            response_hqs,
            threshold=self.response_hqs_threshold,
            runtime_state=state,
            loop_errors=loop_result.state.errors,
            harness_errors=errors,
        )
        state["hqs_gate"] = hqs_gate
        trace_steps.append(
            {
                "name": "tool_calling_hqs_gate",
                "status": "completed",
                "output": hqs_gate,
            }
        )
        quality_retry = _tool_calling_quality_retry_record(hqs_gate, response_hqs)
        if hqs_gate.get("decision") == "retry_response":
            state["quality_retry_count"] = int(state.get("quality_retry_count") or 0) + 1
            state["response_guidance"] = hqs_gate
            retry_loop = AgentRunLoop(run, registry, self.memory, run_service=run_service)
            replan_result = retry_loop.execute(ToolCall("replan_response"))
            build_result = retry_loop.execute(ToolCall("build_response"))
            _mark_plan_tool_status(state, "build_response", build_result.status)
            if replan_result.errors:
                errors.extend(replan_result.errors)
            if build_result.errors:
                errors.extend(build_result.errors)
            trace_steps.extend(
                [
                    {
                        "name": "controlled_retry_replan_response",
                        "status": replan_result.status,
                        "tool_name": "replan_response",
                        "tool_result": replan_result.to_dict(),
                        "output": replan_result.output,
                        "errors": replan_result.errors,
                    },
                    {
                        "name": "controlled_retry_build_response",
                        "status": build_result.status,
                        "tool_name": "build_response",
                        "tool_result": build_result.to_dict(),
                        "output": build_result.output,
                        "errors": build_result.errors,
                    },
                ]
            )
            response = _tool_calling_response(loop_result, state)
            final_answer_source = _tool_calling_final_answer_source(loop_result, state)
            response_hqs = evaluate_response(
                user_input,
                response,
                memory_context=memory_context,
                intent=intent_payload,
            )
            state["response_hqs"] = response_hqs
            trace_steps.append(
                {
                    "name": "evaluate_response_hqs_after_retry",
                    "status": "completed",
                    "output": {"hqs": response_hqs.to_dict()},
                }
            )
            hqs_gate = _tool_calling_hqs_gate_decision(
                response_hqs,
                threshold=self.response_hqs_threshold,
                runtime_state=state,
                loop_errors=loop_result.state.errors,
                harness_errors=errors,
            )
            state["hqs_gate"] = hqs_gate
            trace_steps.append(
                {
                    "name": "tool_calling_hqs_gate_after_retry",
                    "status": "completed",
                    "output": hqs_gate,
                }
            )
            quality_retry.update(
                {
                    "triggered": True,
                    "retry_count": state["quality_retry_count"],
                    "retry_status": build_result.status,
                    "retry_hqs": response_hqs.to_dict(),
                    "final_decision": hqs_gate.get("decision"),
                    "stop_reason": hqs_gate.get("stop_reason"),
                }
            )
        state["quality_retry"] = quality_retry
        tool_call_timeline = _tool_call_timeline(trace_steps)
        parse_repair_count = _parse_repair_count(trace_steps)

        episode = self.memory.save_episode(
            {
                "run_id": run.run_id,
                "agent_mode": "tool_calling_agent",
                "user_input": user_input,
                "response": response,
                "intent": intent_payload,
                "plan": _maybe_to_dict(state.get("plan")),
                "selected_skill": _maybe_to_dict(state.get("selected_skill")),
                "execution": _maybe_to_dict(state.get("execution")),
                "hqs": response_hqs.to_dict(),
                "hqs_gate": hqs_gate,
                "quality_retry": quality_retry,
                "final_answer_source": final_answer_source,
                "tool_calling": loop_result.state.to_dict(),
            }
        )
        artifacts.append({"type": "episodic_memory", "path": "data/memory/episodes.jsonl"})

        stop_reason = _tool_calling_stop_reason(loop_result.state)
        run_status = "completed" if loop_result.state.status == "completed" else "failed"
        run.finish(status=run_status, stop_reason=stop_reason, reflection={"agent_mode": "tool_calling_agent"})

        trace_steps.append(
            {
                "name": "save_episode_memory",
                "status": "completed",
                "output": {"episode_id": episode["episode_id"]},
            }
        )
        trace_output = {
            "run_id": run.run_id,
            "agent_mode": "tool_calling_agent",
            "response": response,
            "response_hqs": response_hqs.to_dict(),
            "tool_calling": loop_result.state.to_dict(),
            "episode_id": episode["episode_id"],
            "stop_reason": stop_reason,
            "planner": active_planner.metadata(),
            "hqs_gate": hqs_gate,
            "quality_retry": quality_retry,
            "final_answer_source": final_answer_source,
            "tool_call_timeline": tool_call_timeline,
            "parse_repair_count": parse_repair_count,
            "invalid_call_count": loop_result.state.invalid_call_count,
        }
        trace_path = write_trace(
            project_root=self.project_root,
            trace_type="tool_calling_agent",
            input_data={"message": user_input, "run_id": run.run_id},
            output=trace_output,
            steps=trace_steps,
            artifacts=artifacts,
            errors=[*errors, *loop_result.state.errors],
            extra_fields={"run": run.to_dict(), "agent_mode": "tool_calling_agent"},
        )
        system_hqs = evaluate_system(
            {
                "response": response,
                "trace_path": str(trace_path),
                "steps": [step.to_dict() for step in run.steps],
                "errors": [*errors, *loop_result.state.errors],
                "memory_context": memory_context,
                "intent": intent_payload,
                "selected_skill": _maybe_to_dict(state.get("selected_skill")),
                "generated_skill_path": _generated_skill_path(state.get("execution")),
            }
        )
        _append_system_hqs_to_trace(trace_path, system_hqs)
        run_service.record_run(
            task_type="tool_calling_agent",
            title="Tool-calling agent chat",
            input_data={"message": user_input},
            output_data={**trace_output, "system_hqs": system_hqs.to_dict()},
            trace_path=trace_path,
            status=run.status,
            run_id=run.run_id,
            steps=[step.to_dict() for step in run.steps],
            artifacts=artifacts,
            hqs_reports={"response": response_hqs.to_dict(), "system": system_hqs.to_dict()},
            created_at=run.created_at,
        )
        self.memory.add_working_memory(
            {
                "active_run": run.to_dict(),
                "last_response_hqs": response_hqs.to_dict(),
                "last_system_hqs": system_hqs.to_dict(),
                "last_trace_path": str(trace_path),
                "last_stop_reason": stop_reason,
                "last_agent_mode": "tool_calling_agent",
                "last_hqs_gate": hqs_gate,
                "last_quality_retry": quality_retry,
            }
        )

        return AgentToolChatResult(
            response=response,
            trace_path=trace_path,
            hqs=response_hqs,
            system_hqs=system_hqs,
            run=run,
            tool_calling=loop_result,
            memory_context=memory_context,
            episode=episode,
            planner_metadata=active_planner.metadata(),
            stop_reason=stop_reason,
            hqs_gate=hqs_gate,
            quality_retry=quality_retry,
            final_answer_source=final_answer_source,
            tool_call_timeline=tool_call_timeline,
            parse_repair_count=parse_repair_count,
            invalid_call_count=loop_result.state.invalid_call_count,
        )

    def list_tools(self) -> list[dict[str, Any]]:
        return self._tool_catalog_registry().list_tools()

    def get_tool(self, name: str) -> dict[str, Any] | None:
        try:
            return self._tool_catalog_registry().get(name).to_dict()
        except ValueError:
            return None

    def _tool_catalog_registry(self) -> ToolRegistry:
        run = AgentRun.create("__tool_catalog__")
        return self._build_tool_registry({}, run, [], [])

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
                    "retrieval": memory_context.get("retrieval"),
                    "episode_preview": _compact_memory_records(memory_context.get("episodes"), "episode"),
                    "semantic_preview": _compact_memory_records(memory_context.get("semantic_memory"), "semantic"),
                }
            )

        def inspect_latest_trace(payload: dict[str, Any]) -> ToolResult:
            filename = str(payload.get("filename") or "").strip()
            latest = payload.get("latest", True)
            try:
                trace_path = _trace_path_for_inspection(self.project_root, filename if filename else None, bool(latest))
                if trace_path is None:
                    output = {
                        "found": False,
                        "message": "No trace files were found under traces/.",
                    }
                    state["trace_inspection"] = output
                    return ToolResult(output=output)
                summary = inspect_trace(trace_path.name, project_root=self.project_root)
                output = _compact_trace_inspection(summary, self.project_root)
                state["trace_inspection"] = output
                artifact = {"type": "trace_inspection", "path": output["trace_path"]}
                artifacts.append(artifact)
                return ToolResult(output=output, artifacts=[artifact])
            except Exception as exc:
                error = {
                    "error_type": exc.__class__.__name__,
                    "message": str(exc),
                    "recoverable": True,
                }
                state["trace_inspection"] = {
                    "found": False,
                    "message": str(exc),
                    "error_type": error["error_type"],
                }
                return ToolResult(output=state["trace_inspection"], errors=[error], status="failed")

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
            intent: Intent = state["intent"]
            trace_inspection = state.get("trace_inspection")
            if intent.intent_type == "query_memory":
                response = _memory_query_response(intent, state["plan"], state["memory_context"])
            elif isinstance(trace_inspection, dict):
                response = _trace_inspection_response(
                    intent,
                    state["plan"],
                    trace_inspection,
                    state["memory_context"],
                )
            else:
                response = build_response(
                    intent,
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
                output_schema=ToolSchema.from_types(
                    required={"episode_count": "integer", "semantic_count": "integer"},
                    optional={"retrieval": "object", "episode_preview": "array", "semantic_preview": "array"},
                ),
                error_specs=[ToolErrorSpec("MemoryReadError", "Memory retrieval failed.", False)],
                permission_level="read",
                idempotent=True,
            ),
            AgentTool(
                "inspect_latest_trace",
                "trace",
                inspect_latest_trace,
                "Inspect the latest trace or a named trace file under traces/.",
                input_schema=ToolSchema.from_types(
                    optional={"filename": "string", "latest": "boolean"},
                    allow_extra=False,
                ),
                output_schema=ToolSchema.from_types(
                    required={"found": "boolean"},
                    optional={
                        "trace_file": "string",
                        "trace_path": "string",
                        "trace_type": "string",
                        "step_count": "integer",
                        "error_count": "integer",
                    },
                ),
                error_specs=[ToolErrorSpec("TraceInspectionError", "Trace inspection failed.", True)],
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


def _trace_path_for_inspection(root: Path, filename: str | None, latest: bool) -> Path | None:
    traces_dir = root / "traces"
    if filename:
        if filename in {"", ".", ".."} or "/" in filename or "\\" in filename or Path(filename).name != filename:
            raise ValueError("Trace filename must be a single path segment.")
        if not filename.endswith(".json"):
            raise ValueError("Trace filename must end with .json.")
        return traces_dir / filename
    if not traces_dir.exists():
        return None
    traces = [
        path
        for path in sorted(traces_dir.glob("*.json"), key=lambda item: item.name, reverse=True)
        if "_memory_update" not in path.name
    ]
    if not traces:
        return None
    return traces[0] if latest else traces[0]


def _compact_trace_inspection(summary: dict[str, Any], root: Path) -> dict[str, Any]:
    trace_path = Path(str(summary.get("path") or ""))
    steps = summary.get("steps") if isinstance(summary.get("steps"), list) else []
    errors = summary.get("errors") if isinstance(summary.get("errors"), list) else []
    artifacts = summary.get("artifacts") if isinstance(summary.get("artifacts"), list) else []
    schema = summary.get("schema") if isinstance(summary.get("schema"), dict) else {}
    return {
        "found": True,
        "trace_file": trace_path.name,
        "trace_path": _relative_or_absolute(trace_path, root),
        "trace_type": summary.get("type"),
        "trace_id": summary.get("trace_id"),
        "created_at": summary.get("created_at"),
        "schema_valid": schema.get("valid"),
        "step_count": summary.get("step_count"),
        "artifact_count": summary.get("artifact_count"),
        "error_count": summary.get("error_count"),
        "output_keys": summary.get("output_keys") if isinstance(summary.get("output_keys"), list) else [],
        "steps": steps[-12:],
        "errors": errors[:8],
        "artifacts": artifacts[:8],
    }


def _memory_query_response(intent: Intent, plan: AgentPlan, memory_context: dict[str, Any]) -> str:
    retrieval = memory_context.get("retrieval") if isinstance(memory_context.get("retrieval"), dict) else {}
    episodes = memory_context.get("episodes") if isinstance(memory_context.get("episodes"), list) else []
    semantic = memory_context.get("semantic_memory") if isinstance(memory_context.get("semantic_memory"), list) else []
    lines = [
        "# AgentForge Response",
        "",
        "## Memory Query",
        "",
        f"- Query: {retrieval.get('query') or intent.query}",
        f"- Episode matches: {len(episodes)}",
        f"- Semantic matches: {len(semantic)}",
        f"- Plan: {plan.action}",
    ]
    if episodes:
        lines.extend(["", "## Episode Memory", ""])
        for episode in episodes[:5]:
            if isinstance(episode, dict):
                label = episode.get("episode_id") or episode.get("run_id") or "episode"
                intent_payload = episode.get("intent") if isinstance(episode.get("intent"), dict) else {}
                response = str(episode.get("response") or "").strip().replace("\n", " ")
                lines.append(f"- {label}: {intent_payload.get('intent_type') or episode.get('user_input') or 'unknown'}")
                if response:
                    lines.append(f"  {response[:220]}")
    if semantic:
        lines.extend(["", "## Semantic Memory", ""])
        for record in semantic[:5]:
            if isinstance(record, dict):
                key = record.get("key") or record.get("skill_slug") or "semantic"
                summary = record.get("summary") or record.get("best_version") or record.get("last_action") or ""
                lines.append(f"- {key}: {summary}")
    if not episodes and not semantic:
        lines.extend(["", "## Result", "", "- No matching episodic or semantic memory was found."])
    scores = retrieval.get("episode_scores") if isinstance(retrieval.get("episode_scores"), list) else []
    if scores:
        lines.extend(["", "## Retrieval Signals", ""])
        for score in scores[:5]:
            if isinstance(score, dict):
                lines.append(f"- {score.get('key')}: score {score.get('score')} ({', '.join(score.get('reasons', []))})")
    return "\n".join(lines).rstrip() + "\n"


def _trace_inspection_response(
    intent: Intent,
    plan: AgentPlan,
    trace_inspection: dict[str, Any],
    memory_context: dict[str, Any],
) -> str:
    if not trace_inspection.get("found"):
        return "\n".join(
            [
                "# AgentForge Response",
                "",
                "## Trace Inspection",
                "",
                f"- Status: not found",
                f"- Message: {trace_inspection.get('message', 'No trace was available.')}",
                "",
                "## Agent State",
                "",
                f"- Intent: {intent.intent_type}",
                f"- Plan: {plan.action}",
                _local_memory_line(memory_context),
            ]
        ).rstrip() + "\n"
    lines = [
        "# AgentForge Response",
        "",
        "## Trace Inspection",
        "",
        f"- Trace: {trace_inspection.get('trace_path')}",
        f"- Type: {trace_inspection.get('trace_type')}",
        f"- Created: {trace_inspection.get('created_at')}",
        f"- Schema valid: {trace_inspection.get('schema_valid')}",
        f"- Steps: {trace_inspection.get('step_count')}",
        f"- Artifacts: {trace_inspection.get('artifact_count')}",
        f"- Errors: {trace_inspection.get('error_count')}",
    ]
    steps = trace_inspection.get("steps") if isinstance(trace_inspection.get("steps"), list) else []
    if steps:
        lines.extend(["", "## Recent Steps", ""])
        for step in steps[-8:]:
            if isinstance(step, dict):
                lines.append(f"- {step.get('name')}: {step.get('status')}")
    errors = trace_inspection.get("errors") if isinstance(trace_inspection.get("errors"), list) else []
    if errors:
        lines.extend(["", "## Errors", ""])
        for error in errors[:5]:
            if isinstance(error, dict):
                lines.append(f"- {error.get('error_type', 'Error')}: {error.get('message', '')}")
    lines.extend(
        [
            "",
            "## Memory",
            "",
            _local_memory_line(memory_context),
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def _local_memory_line(memory_context: dict[str, Any]) -> str:
    episodes = len(memory_context.get("episodes") or [])
    semantic = len(memory_context.get("semantic_memory") or [])
    return f"- Retrieved context: {episodes} episode memories and {semantic} semantic memories."


def _compact_memory_records(records: Any, record_type: str) -> list[dict[str, Any]]:
    if not isinstance(records, list):
        return []
    compact = []
    for record in records[:5]:
        if not isinstance(record, dict):
            continue
        text = (
            record.get("response")
            or record.get("summary")
            or record.get("user_input")
            or record.get("last_action")
            or ""
        )
        compact.append(
            {
                "type": record_type,
                "key": record.get("episode_id") or record.get("key") or record.get("run_id"),
                "score": record.get("_memory_score"),
                "reasons": record.get("_memory_reasons", []),
                "summary": _truncate_words(str(text).replace("\n", " "), 60),
            }
        )
    return compact


def _truncate_words(value: str, limit: int) -> str:
    words = value.split()
    if len(words) <= limit:
        return value
    return " ".join(words[:limit]) + "..."


def _tool_calling_response(loop_result: ToolCallingLoopResult, state: dict[str, Any]) -> str:
    response = state.get("response")
    if isinstance(response, str) and response.strip():
        return response
    if loop_result.state.final_answer:
        return loop_result.state.final_answer
    if loop_result.state.status == "blocked":
        error = loop_result.state.errors[-1] if loop_result.state.errors else {}
        return str(error.get("message") or "AgentForge needs more input before it can continue.")
    return "AgentForge tool-calling agent stopped before producing a final answer."


def _tool_calling_final_answer_source(loop_result: ToolCallingLoopResult, state: dict[str, Any]) -> str:
    response = state.get("response")
    if isinstance(response, str) and response.strip():
        return "harness_response"
    if loop_result.state.final_answer:
        return "model_final_answer"
    return "model_final_answer"


def _tool_calling_hqs_gate_decision(
    response_hqs: ResponseHQSReport,
    threshold: float,
    runtime_state: dict[str, Any],
    loop_errors: list[dict[str, Any]],
    harness_errors: list[dict[str, Any]],
) -> dict[str, Any]:
    weak_dimensions = [dimension for dimension, score in response_hqs.scores.items() if score < 3.0]
    triggered = response_hqs.average_score < threshold or bool(weak_dimensions)
    retry_count = int(runtime_state.get("quality_retry_count") or 0)
    response = runtime_state.get("response")
    has_harness_response = isinstance(response, str) and bool(response.strip())
    has_blocking_error = _has_blocking_error([*harness_errors, *loop_errors])

    if not triggered:
        decision = "pass"
        stop_reason = "hqs_passed"
    elif retry_count >= 1:
        decision = "stop_low_hqs"
        stop_reason = "retry_budget_exhausted"
    elif not has_harness_response:
        decision = "stop_low_hqs"
        stop_reason = "missing_harness_response"
    elif has_blocking_error:
        decision = "stop_low_hqs"
        stop_reason = "blocking_error"
    else:
        decision = "retry_response"
        stop_reason = "below_threshold"

    return {
        "decision": decision,
        "threshold": threshold,
        "average_hqs": response_hqs.average_score,
        "weak_dimensions": weak_dimensions,
        "triggered": triggered,
        "retry_count": retry_count,
        "max_retries": 1,
        "can_retry": decision == "retry_response",
        "stop_reason": stop_reason,
        "has_harness_response": has_harness_response,
        "has_blocking_error": has_blocking_error,
    }


def _tool_calling_quality_retry_record(
    gate: dict[str, Any],
    response_hqs: ResponseHQSReport,
) -> dict[str, Any]:
    return {
        "triggered": False,
        "max_retries": 1,
        "retry_count": int(gate.get("retry_count") or 0),
        "initial_decision": gate.get("decision"),
        "initial_stop_reason": gate.get("stop_reason"),
        "initial_hqs": response_hqs.to_dict(),
        "final_decision": gate.get("decision"),
        "stop_reason": gate.get("stop_reason"),
    }


def _parse_repair_count(trace_steps: list[dict[str, Any]]) -> int:
    count = 0
    for step in trace_steps:
        decision = step.get("model_decision")
        if not isinstance(decision, dict):
            continue
        metadata = decision.get("parse_metadata")
        if isinstance(metadata, dict) and metadata.get("repaired") is True:
            count += 1
    return count


def _tool_call_timeline(trace_steps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    timeline: list[dict[str, Any]] = []
    for step in trace_steps:
        decision = step.get("model_decision")
        validation = step.get("validation")
        observation = step.get("observation")
        observation_summary = step.get("observation_summary")
        tool_result = step.get("tool_result")
        tool_name = step.get("tool_name")
        arguments: Any = None
        decision_type = None
        parse_metadata = None
        if isinstance(decision, dict):
            decision_type = decision.get("type")
            tool_name = decision.get("tool_name") or tool_name
            arguments = decision.get("arguments")
            parse_metadata = decision.get("parse_metadata")
        if not any(
            isinstance(value, dict)
            for value in [decision, validation, observation, observation_summary, tool_result]
        ) and tool_name is None:
            continue
        validation_errors = []
        if isinstance(validation, dict):
            errors = validation.get("errors")
            validation_errors = errors if isinstance(errors, list) else []
        item = {
            "name": step.get("name"),
            "iteration": step.get("iteration"),
            "status": step.get("status"),
            "decision_type": decision_type,
            "tool_name": tool_name,
            "arguments": arguments if isinstance(arguments, dict) else {},
            "model_decision": decision if isinstance(decision, dict) else None,
            "validation": validation if isinstance(validation, dict) else None,
            "validation_errors": validation_errors,
            "parse_repair": parse_metadata if isinstance(parse_metadata, dict) else None,
            "observation": observation if isinstance(observation, dict) else None,
            "observation_summary": observation_summary if isinstance(observation_summary, dict) else None,
            "tool_result": tool_result if isinstance(tool_result, dict) else None,
            "errors": step.get("errors") if isinstance(step.get("errors"), list) else [],
        }
        timeline.append(item)
    return timeline


def _tool_calling_stop_reason(state: Any) -> str:
    if state.status == "completed":
        return "final_answer"
    if state.status == "blocked":
        return "cannot_continue"
    if any(error.get("error_type") == "MaxIterationsExceeded" for error in state.errors):
        return "max_iterations"
    if any(error.get("error_type") == "InvalidCallBudgetExceeded" for error in state.errors):
        return "invalid_tool_call_budget"
    if any(error.get("error_type") == "ToolErrorBudgetExceeded" for error in state.errors):
        return "tool_error_budget"
    if any(error.get("error_type") == "RepeatedToolCall" for error in state.errors):
        return "repeated_tool_call"
    if any(error.get("error_type") == "PrematureFinalAnswer" for error in state.errors):
        return "premature_final_answer"
    return state.status


def _maybe_to_dict(value: Any) -> Any:
    if value is None:
        return None
    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        return to_dict()
    return value


def _generated_skill_path(execution: Any) -> str | None:
    generated = getattr(execution, "generated_skill", None)
    skill_path = getattr(generated, "skill_path", None)
    return str(skill_path) if skill_path else None


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
