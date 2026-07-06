from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from agentforge.agent.run import AgentRun
from agentforge.agent.run_loop import AgentRunLoop
from agentforge.agent.tools import ToolCall, ToolRegistry
from agentforge.agent.tool_calling.model_planner import ToolCallingPlanner
from agentforge.agent.tool_calling.parser import DecisionParseError, ToolDecision, parse_model_decision
from agentforge.agent.tool_calling.policy import ToolCallPolicy
from agentforge.memory.memory_manager import MemoryManager


@dataclass
class ToolCallingState:
    run_id: str
    user_input: str
    iteration: int
    max_iterations: int
    available_tools: list[dict[str, Any]]
    observations: list[dict[str, Any]] = field(default_factory=list)
    observation_summaries: list[dict[str, Any]] = field(default_factory=list)
    final_answer: str | None = None
    errors: list[dict[str, Any]] = field(default_factory=list)
    status: str = "running"
    invalid_call_count: int = 0
    tool_error_count: int = 0
    repeated_tool_call_count: int = 0
    last_tool_call_signature: str | None = None
    same_tool_call_count: int = 0
    last_tool_name: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "user_input": self.user_input,
            "iteration": self.iteration,
            "max_iterations": self.max_iterations,
            "available_tools": self.available_tools,
            "observations": self.observations,
            "observation_summaries": self.observation_summaries,
            "final_answer": self.final_answer,
            "errors": self.errors,
            "status": self.status,
            "invalid_call_count": self.invalid_call_count,
            "tool_error_count": self.tool_error_count,
            "repeated_tool_call_count": self.repeated_tool_call_count,
            "last_tool_call_signature": self.last_tool_call_signature,
            "same_tool_call_count": self.same_tool_call_count,
            "last_tool_name": self.last_tool_name,
        }

    def to_prompt_payload(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "user_input": self.user_input,
            "iteration": self.iteration,
            "max_iterations": self.max_iterations,
            "available_tools": self.available_tools,
            "observations": self.observation_summaries[-6:],
            "invalid_call_count": self.invalid_call_count,
            "tool_error_count": self.tool_error_count,
            "repeated_tool_call_count": self.repeated_tool_call_count,
            "same_tool_call_count": self.same_tool_call_count,
        }


@dataclass(frozen=True)
class ToolCallingLoopResult:
    state: ToolCallingState
    trace_steps: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return {"state": self.state.to_dict(), "trace_steps": self.trace_steps}


class ToolCallingLoop:
    def __init__(
        self,
        run: AgentRun,
        registry: ToolRegistry,
        memory: MemoryManager,
        planner: ToolCallingPlanner,
        policy: ToolCallPolicy,
        runtime_state: dict[str, Any],
        available_tools: list[dict[str, Any]],
    ) -> None:
        self.run = run
        self.registry = registry
        self.memory = memory
        self.planner = planner
        self.policy = policy
        self.runtime_state = runtime_state
        self.state = ToolCallingState(
            run_id=run.run_id,
            user_input=str(runtime_state.get("user_input", "")),
            iteration=0,
            max_iterations=policy.max_iterations,
            available_tools=available_tools,
        )
        self.agent_loop = AgentRunLoop(run, registry, memory, max_iterations=policy.max_iterations)
        self.trace_steps: list[dict[str, Any]] = []

    def run_loop(self) -> ToolCallingLoopResult:
        while self.state.iteration < self.policy.max_iterations and self.state.status == "running":
            self.state.iteration += 1
            step = {
                "name": f"tool_call_iteration_{self.state.iteration}",
                "status": "running",
                "iteration": self.state.iteration,
            }
            try:
                decision = self._next_decision()
            except Exception as exc:
                self._record_invalid_decision(step, exc)
                continue

            step["model_decision"] = decision.to_dict()
            validation = self.policy.validate(decision, self.registry, runtime_state=self.runtime_state)
            step["validation"] = validation.to_dict()
            if not validation.valid:
                self._record_policy_rejection(step, validation.errors)
                continue

            if decision.type == "final_answer":
                if self._is_premature_final_answer():
                    self._record_premature_final_answer(step, decision)
                    continue
                self.state.final_answer = decision.content or ""
                self.state.status = "completed"
                step["status"] = "completed"
                self.trace_steps.append(step)
                break

            if decision.type == "cannot_continue":
                self.state.status = "blocked"
                self.state.errors.append(
                    {
                        "error_type": "CannotContinue",
                        "message": decision.reason or "Model reported it cannot continue.",
                        "needed_input": decision.needed_input,
                        "recoverable": True,
                    }
                )
                step["status"] = "blocked"
                self.trace_steps.append(step)
                break

            if self._is_repeated_tool_call(decision):
                self._record_repeated_tool_call(step, decision)
                break
            if self._is_same_tool_loop(decision):
                self._record_repeated_tool_call(step, decision, same_tool=True)
                break

            result = self.agent_loop.execute(ToolCall(decision.tool_name or "", decision.arguments))
            observation = {
                "iteration": self.state.iteration,
                "tool_name": decision.tool_name,
                "tool_result": result.to_dict(),
            }
            observation_summary = _summarize_observation(observation)
            self.state.observations.append(observation)
            self.state.observation_summaries.append(observation_summary)
            step["tool_result"] = result.to_dict()
            step["observation"] = observation
            step["observation_summary"] = observation_summary
            step["status"] = result.status
            self.trace_steps.append(step)
            if result.status == "failed":
                self.state.tool_error_count += 1
                self.state.errors.extend(result.errors)
                if self.state.tool_error_count >= self.policy.max_tool_errors:
                    self.state.status = "failed"
                    self.state.errors.append(
                        {
                            "error_type": "ToolErrorBudgetExceeded",
                            "message": "Tool error budget was exceeded.",
                            "recoverable": False,
                        }
                    )

        if self.state.status == "running":
            self.state.status = "stopped"
            self.state.errors.append(
                {
                    "error_type": "MaxIterationsExceeded",
                    "message": "Tool-calling loop reached max_iterations before a final answer.",
                    "recoverable": False,
                }
            )
        return ToolCallingLoopResult(state=self.state, trace_steps=self.trace_steps)

    def _next_decision(self) -> ToolDecision:
        decision = self.planner.decide(self.state, runtime_state=self.runtime_state)
        if isinstance(decision, ToolDecision):
            return decision
        return parse_model_decision(str(decision))

    def _is_premature_final_answer(self) -> bool:
        response = self.runtime_state.get("response")
        return not isinstance(response, str) or not response.strip()

    def _is_repeated_tool_call(self, decision: ToolDecision) -> bool:
        signature = _tool_call_signature(decision)
        if signature == self.state.last_tool_call_signature:
            self.state.repeated_tool_call_count += 1
        else:
            self.state.last_tool_call_signature = signature
            self.state.repeated_tool_call_count = 1
        return self.state.repeated_tool_call_count > self.policy.max_repeated_tool_calls

    def _is_same_tool_loop(self, decision: ToolDecision) -> bool:
        tool_name = decision.tool_name or ""
        if tool_name == self.state.last_tool_name:
            self.state.same_tool_call_count += 1
        else:
            self.state.last_tool_name = tool_name
            self.state.same_tool_call_count = 1
        if tool_name not in self.policy.same_tool_call_guard_tools:
            return False
        return self.state.same_tool_call_count > self.policy.max_same_tool_calls

    def _record_invalid_decision(self, step: dict[str, Any], exc: Exception) -> None:
        self.state.invalid_call_count += 1
        error_type = exc.__class__.__name__ if not isinstance(exc, DecisionParseError) else "DecisionParseError"
        error = {
            "error_type": error_type,
            "message": str(exc),
            "recoverable": True,
        }
        self.state.errors.append(error)
        step["status"] = "failed"
        step["validation"] = {"valid": False, "errors": [str(exc)]}
        step["errors"] = [error]
        self.trace_steps.append(step)
        if self.state.invalid_call_count >= self.policy.max_invalid_calls:
            self.state.status = "failed"
            self.state.errors.append(
                {
                    "error_type": "InvalidCallBudgetExceeded",
                    "message": "Invalid model decision budget was exceeded.",
                    "recoverable": False,
                }
            )

    def _record_premature_final_answer(self, step: dict[str, Any], decision: ToolDecision) -> None:
        self.state.invalid_call_count += 1
        error = {
            "error_type": "PrematureFinalAnswer",
            "message": "Model returned final_answer before build_response produced a Harness response.",
            "recoverable": True,
        }
        self.state.errors.append(error)
        step["status"] = "failed"
        step["errors"] = [error]
        step["premature_final_answer"] = decision.to_dict()
        self.trace_steps.append(step)
        if self.state.invalid_call_count >= self.policy.max_invalid_calls:
            self.state.status = "failed"
            self.state.errors.append(
                {
                    "error_type": "InvalidCallBudgetExceeded",
                    "message": "Invalid model decision budget was exceeded.",
                    "recoverable": False,
                }
            )

    def _record_repeated_tool_call(
        self,
        step: dict[str, Any],
        decision: ToolDecision,
        same_tool: bool = False,
    ) -> None:
        error = {
            "error_type": "RepeatedToolCall",
            "message": (
                f"Tool call repeated more than "
                f"{self.policy.max_same_tool_calls if same_tool else self.policy.max_repeated_tool_calls} times: "
                f"{decision.tool_name}"
            ),
            "tool_name": decision.tool_name,
            "arguments": decision.arguments,
            "repeat_count": self.state.same_tool_call_count if same_tool else self.state.repeated_tool_call_count,
            "threshold": self.policy.max_same_tool_calls if same_tool else self.policy.max_repeated_tool_calls,
            "scope": "same_tool" if same_tool else "same_tool_and_arguments",
            "recoverable": False,
        }
        self.state.status = "failed"
        self.state.errors.append(error)
        step["status"] = "failed"
        step["errors"] = [error]
        recovery = _recovery_observation(
            iteration=self.state.iteration,
            error=error,
            decision=decision,
            policy_errors=[error["message"]],
        )
        self.state.observation_summaries.append(recovery)
        step["observation_summary"] = recovery
        self.trace_steps.append(step)

    def _record_policy_rejection(self, step: dict[str, Any], errors: list[str]) -> None:
        self.state.invalid_call_count += 1
        error = {
            "error_type": "ToolCallPolicyViolation",
            "message": "; ".join(errors),
            "recoverable": True,
        }
        self.state.errors.append(error)
        step["status"] = "failed"
        step["errors"] = [error]
        decision = _decision_from_step(step)
        recovery = _recovery_observation(
            iteration=self.state.iteration,
            error=error,
            decision=decision,
            policy_errors=errors,
        )
        self.state.observation_summaries.append(recovery)
        step["observation_summary"] = recovery
        self.trace_steps.append(step)
        if self.state.invalid_call_count >= self.policy.max_invalid_calls:
            self.state.status = "failed"
            self.state.errors.append(
                {
                    "error_type": "InvalidCallBudgetExceeded",
                    "message": "Invalid model decision budget was exceeded.",
                    "recoverable": False,
                }
            )


def _tool_call_signature(decision: ToolDecision) -> str:
    return json.dumps(
        {"tool_name": decision.tool_name, "arguments": decision.arguments},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _decision_from_step(step: dict[str, Any]) -> ToolDecision | None:
    decision = step.get("model_decision")
    if not isinstance(decision, dict):
        return None
    if decision.get("type") != "tool_call":
        return None
    return ToolDecision.tool_call(str(decision.get("tool_name") or ""), decision.get("arguments") or {})


def _recovery_observation(
    iteration: int,
    error: dict[str, Any],
    decision: ToolDecision | None,
    policy_errors: list[str],
) -> dict[str, Any]:
    tool_name = decision.tool_name if isinstance(decision, ToolDecision) else None
    return {
        "iteration": iteration,
        "tool_name": tool_name,
        "status": "failed",
        "policy_rejection": {
            "error_type": error.get("error_type"),
            "message": error.get("message"),
            "policy_errors": policy_errors,
            "recovery_hint": _recovery_hint(tool_name, policy_errors),
        },
        "error_count": 1,
        "errors": _compact_errors([error]),
    }


def _recovery_hint(tool_name: str | None, policy_errors: list[str]) -> str:
    joined = " ".join(policy_errors)
    if tool_name == "build_response" and "missing prerequisite state" in joined:
        return (
            "Do not call build_response yet. Call build_plan first, then execute_plan, "
            "then observe_execution if useful, then build_response."
        )
    if "Tool is not allowed" in joined:
        return "Choose exactly one tool from available_tools, or return cannot_continue."
    if "RepeatedToolCall" in joined or "repeated" in joined.lower():
        return "Stop repeating the same read tool. Move to build_plan or select_skill based on the latest observation."
    return "Choose a valid next tool that satisfies prerequisite state, or return cannot_continue."


def _summarize_observation(observation: dict[str, Any]) -> dict[str, Any]:
    result = observation.get("tool_result") if isinstance(observation.get("tool_result"), dict) else {}
    output = result.get("output") if isinstance(result.get("output"), dict) else {}
    errors = result.get("errors") if isinstance(result.get("errors"), list) else []
    artifacts = result.get("artifacts") if isinstance(result.get("artifacts"), list) else []
    return {
        "iteration": observation.get("iteration"),
        "tool_name": observation.get("tool_name"),
        "status": result.get("status"),
        "output": _summarize_output(output),
        "artifact_count": len(artifacts),
        "artifacts": _compact_artifacts(artifacts),
        "error_count": len(errors),
        "errors": _compact_errors(errors),
    }


def _summarize_output(output: dict[str, Any]) -> dict[str, Any]:
    summary: dict[str, Any] = {"keys": sorted(output.keys())}
    if "episode_count" in output or "semantic_count" in output:
        retrieval = output.get("retrieval") if isinstance(output.get("retrieval"), dict) else {}
        summary["memory_counts"] = {
            "episode_count": output.get("episode_count"),
            "semantic_count": output.get("semantic_count"),
        }
        summary["memory_preview"] = {
            "query": retrieval.get("query"),
            "episode_scores": retrieval.get("episode_scores", [])[:5] if isinstance(retrieval.get("episode_scores"), list) else [],
            "semantic_scores": retrieval.get("semantic_scores", [])[:5] if isinstance(retrieval.get("semantic_scores"), list) else [],
            "episodes": output.get("episode_preview", [])[:5] if isinstance(output.get("episode_preview"), list) else [],
            "semantic": output.get("semantic_preview", [])[:5] if isinstance(output.get("semantic_preview"), list) else [],
        }
    if "found" in output and ("trace_file" in output or "trace_type" in output or "message" in output):
        summary["trace_inspection"] = {
            "found": output.get("found"),
            "trace_file": output.get("trace_file"),
            "trace_type": output.get("trace_type"),
            "schema_valid": output.get("schema_valid"),
            "step_count": output.get("step_count"),
            "artifact_count": output.get("artifact_count"),
            "error_count": output.get("error_count"),
            "message": output.get("message"),
            "recent_steps": output.get("steps", [])[-5:] if isinstance(output.get("steps"), list) else [],
            "errors": output.get("errors", [])[:3] if isinstance(output.get("errors"), list) else [],
        }
    if "selected_skill" in output:
        summary["selected_skill"] = _compact_skill(output.get("selected_skill"))
    if "plan" in output:
        plan = output.get("plan") if isinstance(output.get("plan"), dict) else {}
        summary["plan"] = {
            "action": plan.get("action"),
            "complexity": plan.get("complexity"),
            "step_count": len(plan.get("steps", [])) if isinstance(plan.get("steps"), list) else 0,
            "steps": [
                {
                    "name": step.get("name"),
                    "tool_name": step.get("tool_name"),
                    "status": step.get("status"),
                }
                for step in (plan.get("steps", []) if isinstance(plan.get("steps"), list) else [])[:8]
                if isinstance(step, dict)
            ],
        }
    if "execution" in output:
        execution = output.get("execution") if isinstance(output.get("execution"), dict) else {}
        summary["execution"] = {
            "action": execution.get("action"),
            "selected_skill": _compact_skill(execution.get("selected_skill")),
            "generated_skill_path": execution.get("generated_skill_path"),
            "run_result_path": _nested_path(execution.get("run_result"), "result_path"),
            "run_result_count": len(execution.get("run_results", [])) if isinstance(execution.get("run_results"), list) else 0,
            "artifact_count": len(execution.get("artifacts", [])) if isinstance(execution.get("artifacts"), list) else 0,
            "error_count": len(execution.get("errors", [])) if isinstance(execution.get("errors"), list) else 0,
            "execution_status": _nested_path(execution.get("execution_state"), "status"),
        }
    if "action" in output and "has_output" in output:
        summary["execution_observation"] = {
            "action": output.get("action"),
            "has_output": output.get("has_output"),
            "selected_skill": _compact_skill(output.get("selected_skill")),
            "generated_skill_path": output.get("generated_skill_path"),
            "artifact_count": output.get("artifact_count"),
            "recoverable_error_count": output.get("recoverable_error_count"),
            "blocking_error_count": output.get("blocking_error_count"),
        }
    if "response_preview" in output:
        summary["response"] = {
            "response_length": output.get("response_length"),
            "response_preview": _truncate(str(output.get("response_preview") or ""), 1200),
        }
    if "hqs" in output:
        hqs = output.get("hqs") if isinstance(output.get("hqs"), dict) else {}
        summary["hqs"] = {
            "average_score": hqs.get("average_score"),
            "scores": hqs.get("scores"),
            "recommendation": hqs.get("recommendation"),
        }
    return summary


def _compact_skill(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    return {
        "skill_slug": value.get("skill_slug"),
        "version": value.get("version"),
        "title": value.get("title"),
        "source": value.get("source"),
        "score": value.get("score"),
    }


def _compact_artifacts(artifacts: list[Any]) -> list[dict[str, Any]]:
    compact = []
    for artifact in artifacts[:5]:
        if isinstance(artifact, dict):
            compact.append({"type": artifact.get("type"), "path": artifact.get("path")})
    return compact


def _compact_errors(errors: list[Any]) -> list[dict[str, Any]]:
    compact = []
    for error in errors[:5]:
        if isinstance(error, dict):
            compact.append(
                {
                    "error_type": error.get("error_type"),
                    "message": _truncate(str(error.get("message") or error.get("user_message") or ""), 300),
                    "recoverable": error.get("recoverable"),
                }
            )
    return compact


def _nested_path(value: Any, key: str) -> Any:
    if isinstance(value, dict):
        return value.get(key)
    return None


def _truncate(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    return value[: limit - 3] + "..."
