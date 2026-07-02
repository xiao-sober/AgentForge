from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from agentforge.agent.run import AgentRun
from agentforge.agent.tools import ToolCall, ToolRegistry, ToolResult
from agentforge.common.trace import utc_now_iso
from agentforge.memory.memory_manager import MemoryManager


TOOL_PHASES = {
    "receive_input": "received",
    "parse_intent": "parsed",
    "retrieve_memory_context": "memory_retrieved",
    "select_skill": "skill_selected",
    "build_plan": "planned",
    "execute_plan": "executing",
    "observe_execution": "observing",
    "update_semantic_memory": "memory_updated",
    "build_response": "responding",
    "evaluate_response_hqs": "evaluating",
    "hqs_gate": "quality_gated",
    "replan_response": "planned",
    "reflect": "reflecting",
    "reinforcement_check": "reinforcing",
    "save_episode_memory": "saving_memory",
}


@dataclass
class AgentRunLoopState:
    phase: str = "initialized"
    iteration: int = 0
    max_iterations: int = 2
    tool_results: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "phase": self.phase,
            "iteration": self.iteration,
            "max_iterations": self.max_iterations,
            "tool_results": self.tool_results,
        }


class AgentRunLoop:
    def __init__(
        self,
        run: AgentRun,
        registry: ToolRegistry,
        memory: MemoryManager,
        max_iterations: int = 2,
    ) -> None:
        self.run = run
        self.registry = registry
        self.memory = memory
        self.state = AgentRunLoopState(max_iterations=max_iterations)

    def execute(self, call: ToolCall) -> ToolResult:
        try:
            tool = self.registry.get(call.tool_name)
            kind = call.kind or tool.kind
        except Exception:
            tool = None
            kind = call.kind or "tool"
        step_input: dict[str, Any] = {"tool_name": call.tool_name, **call.input}
        if tool is not None:
            step_input["tool"] = tool.to_dict()
        step = self.run.add_step(
            call.step_name or call.tool_name,
            kind,
            step_input,
        )
        try:
            if tool is None:
                raise ValueError(f"Tool is not registered: {call.tool_name}")
            result = self.registry.execute(call)
        except Exception as exc:
            result = ToolResult(
                output={},
                errors=[{"error_type": exc.__class__.__name__, "message": str(exc), "recoverable": False}],
                status="failed",
            )

        step.complete(
            output=result.output,
            artifacts=result.artifacts,
            errors=result.errors,
            status=result.status,
        )
        phase = _phase_for_tool(call.tool_name)
        self.run.transition(
            phase,
            status=result.status,
            reason=call.tool_name,
            details={"step_id": step.step_id, "kind": kind},
        )
        self.state.phase = phase
        self.state.tool_results.append({"call": call.to_dict(), "result": result.to_dict()})
        self.memory.add_working_memory(
            {
                "active_run_id": self.run.run_id,
                "active_run_status": self.run.status,
                "active_run_phase": self.run.phase,
                "active_run_loop": self.state.to_dict(),
                "active_run_steps": [item.to_dict() for item in self.run.steps],
                "active_run_phase_history": self.run.phase_history,
                "last_step": step.to_dict(),
                "updated_at": utc_now_iso(),
            }
        )
        return result

    def can_iterate(self) -> bool:
        return self.state.iteration < self.state.max_iterations

    def next_iteration(self) -> int:
        self.state.iteration += 1
        return self.state.iteration


def _phase_for_tool(tool_name: str) -> str:
    return TOOL_PHASES.get(tool_name, "executing")
