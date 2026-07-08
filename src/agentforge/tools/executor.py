from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, TimeoutError
from typing import Any

from agentforge.common.trace import utc_now_iso
from agentforge.runs.service import RunService
from agentforge.tools.permissions import permission_allowed
from agentforge.tools.schema import AgentTool, ToolCall, ToolResult


class ToolExecutor:
    def execute(
        self,
        tool: AgentTool,
        call: ToolCall,
        allowed_permission_levels: set[str] | None = None,
        run_id: str | None = None,
        step_id: str | None = None,
        run_service: RunService | None = None,
    ) -> ToolResult:
        started_at = utc_now_iso()
        result = self._execute(
            tool=tool,
            call=call,
            allowed_permission_levels=allowed_permission_levels,
        )
        completed_at = utc_now_iso()
        self._persist_tool_call(
            run_service=run_service,
            run_id=run_id,
            step_id=step_id,
            tool=tool,
            call=call,
            result=result,
            started_at=started_at,
            completed_at=completed_at,
        )
        return result

    def _execute(
        self,
        tool: AgentTool,
        call: ToolCall,
        allowed_permission_levels: set[str] | None,
    ) -> ToolResult:
        if not permission_allowed(tool.permission_level, allowed_permission_levels):
            return ToolResult(
                errors=[
                    _tool_error(
                        "ToolPermissionDenied",
                        f"Tool '{tool.name}' requires '{tool.permission_level}' permission.",
                        recoverable=False,
                    )
                ],
                status="failed",
            )

        input_errors = tool.input_schema.validate(call.input, "input")
        if input_errors:
            return ToolResult(
                errors=[
                    _tool_error(
                        "ToolInputValidationError",
                        "; ".join(input_errors),
                        recoverable=False,
                    )
                ],
                status="failed",
            )

        result = self._call_handler(tool, call)
        if not isinstance(result, ToolResult):
            return ToolResult(
                errors=[
                    _tool_error(
                        "ToolResultValidationError",
                        f"Tool '{tool.name}' returned {type(result).__name__}, expected ToolResult.",
                        recoverable=False,
                    )
                ],
                status="failed",
            )

        output_errors = tool.output_schema.validate(result.output, "output")
        if output_errors:
            errors = [
                *result.errors,
                _tool_error(
                    "ToolOutputValidationError",
                    "; ".join(output_errors),
                    recoverable=False,
                ),
            ]
            return ToolResult(
                output=result.output,
                artifacts=result.artifacts,
                errors=errors,
                status="failed",
            )
        return result

    def _call_handler(self, tool: AgentTool, call: ToolCall) -> ToolResult | Any:
        if tool.timeout_seconds is None:
            try:
                return tool.handler(call.input)
            except Exception as exc:
                return _exception_result(exc)

        executor = ThreadPoolExecutor(max_workers=1)
        future = executor.submit(tool.handler, call.input)
        try:
            return future.result(timeout=tool.timeout_seconds)
        except TimeoutError:
            future.cancel()
            return ToolResult(
                errors=[
                    _tool_error(
                        "ToolTimeout",
                        f"Tool '{tool.name}' exceeded timeout of {tool.timeout_seconds} seconds.",
                        recoverable=True,
                    )
                ],
                status="failed",
            )
        except Exception as exc:
            return _exception_result(exc)
        finally:
            executor.shutdown(wait=False, cancel_futures=True)

    def _persist_tool_call(
        self,
        run_service: RunService | None,
        run_id: str | None,
        step_id: str | None,
        tool: AgentTool,
        call: ToolCall,
        result: ToolResult,
        started_at: str,
        completed_at: str,
    ) -> None:
        if run_service is None or not run_id:
            return
        run_service.record_tool_call_event(
            run_id=run_id,
            tool_name=tool.name,
            status=result.status,
            arguments=call.input,
            step_id=step_id,
            result=result.to_dict(),
            errors=result.errors,
            started_at=started_at,
            completed_at=completed_at,
        )


def _exception_result(exc: Exception) -> ToolResult:
    return ToolResult(
        errors=[
            _tool_error(
                exc.__class__.__name__,
                str(exc),
                recoverable=False,
            )
        ],
        status="failed",
    )


def _tool_error(error_type: str, message: str, recoverable: bool) -> dict[str, Any]:
    return {
        "error_type": error_type,
        "message": message,
        "user_message": message,
        "recoverable": recoverable,
    }
