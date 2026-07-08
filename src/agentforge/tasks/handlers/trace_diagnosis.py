from __future__ import annotations

from pathlib import Path
from typing import Any

from agentforge.common.trace_inspector import inspect_trace
from agentforge.runs.service import RunService
from agentforge.tasks.handlers.workflow_task import finalize_workflow_task_result
from agentforge.tasks.schemas import TaskRequest, TaskResult
from agentforge.workflows import WorkflowExecutionContext, WorkflowRunner, WorkflowStepResult


def handle_trace_diagnosis_task(
    request: TaskRequest,
    project_root: Path,
    llm_client: Any | None = None,
) -> TaskResult:
    del llm_client
    runner = WorkflowRunner.for_task(
        project_root,
        workflow_id="trace_diagnosis_workflow",
        task_type="trace_diagnosis",
        steps=["resolve_trace", "inspect_trace", "build_diagnosis"],
    )

    def resolve_trace(_: WorkflowExecutionContext) -> WorkflowStepResult:
        trace_path = _resolve_trace_for_request(request, project_root)
        inspected_trace = _relative_or_absolute(trace_path, project_root)
        return WorkflowStepResult(
            output={"trace_path": inspected_trace},
            state_updates={"trace_path": str(trace_path), "inspected_trace": inspected_trace},
        )

    def inspect_selected_trace(context: WorkflowExecutionContext) -> WorkflowStepResult:
        trace_path = Path(str(context.state["trace_path"]))
        summary = inspect_trace(trace_path, project_root=project_root)
        return WorkflowStepResult(
            output={
                "trace_type": summary.get("type"),
                "schema_valid": _nested_bool(summary, "schema", "valid"),
                "step_count": summary.get("step_count"),
                "error_count": summary.get("error_count"),
                "artifact_count": summary.get("artifact_count"),
            },
            state_updates={"summary": summary},
        )

    def build_diagnosis(context: WorkflowExecutionContext) -> WorkflowStepResult:
        summary = context.state["summary"]
        diagnosis = _build_diagnosis(summary)
        trace_output = {
            "diagnosis": diagnosis,
            "inspected_trace": context.state["inspected_trace"],
            "summary": summary,
        }
        artifact = {"type": "inspected_trace", "path": context.state["inspected_trace"]}
        return WorkflowStepResult(
            output=diagnosis,
            artifacts=[artifact],
            state_updates={"trace_output": trace_output, "artifacts": [artifact]},
        )

    run_id = runner.execute(
        title="Trace diagnosis",
        input_data=request.to_dict(),
        handlers={
            "resolve_trace": resolve_trace,
            "inspect_trace": inspect_selected_trace,
            "build_diagnosis": build_diagnosis,
        },
    )
    return finalize_workflow_task_result(
        runner=runner,
        run_id=run_id,
        request=request,
        project_root=project_root,
        trace_type="trace_diagnosis",
        success_state_key="trace_output",
        failure_output_key="diagnosis",
    )


def _resolve_trace_for_request(request: TaskRequest, root: Path) -> Path:
    payload = request.payload()
    run_id = payload.get("run_id")
    if isinstance(run_id, str) and run_id.strip():
        detail = RunService(root).run_detail(run_id.strip())
        if detail is None:
            raise ValueError(f"Run not found: {run_id.strip()}")
        trace_path = detail.get("trace_path")
        if not isinstance(trace_path, str) or not trace_path.strip():
            raise ValueError(f"Run has no trace_path: {run_id.strip()}")
        return _resolve_trace_path(root, Path(trace_path))

    raw_trace = payload.get("trace_path") or payload.get("trace_file")
    if isinstance(raw_trace, str) and raw_trace.strip():
        return _resolve_trace_path(root, Path(raw_trace.strip()))

    if payload.get("latest") is True:
        return _latest_trace(root)

    raise ValueError("trace_diagnosis requires input.run_id, input.trace_file, input.trace_path, or input.latest=true.")


def _resolve_trace_path(root: Path, path: Path) -> Path:
    if path.is_absolute():
        candidate = path.resolve()
    elif path.parent != Path("."):
        candidate = (root / path).resolve()
    else:
        candidate = (root / "traces" / path).resolve()
    traces_root = (root / "traces").resolve()
    if candidate != traces_root and traces_root not in candidate.parents:
        raise ValueError("Trace path must stay under traces/.")
    if not candidate.exists() or candidate.suffix.lower() != ".json":
        raise ValueError(f"Trace not found: {candidate}")
    return candidate


def _latest_trace(root: Path) -> Path:
    traces_dir = root / "traces"
    if not traces_dir.exists():
        raise ValueError("No traces directory exists.")
    traces = [
        path
        for path in sorted(traces_dir.glob("*.json"), key=lambda item: item.name, reverse=True)
        if "_memory_update" not in path.name and "_trace_diagnosis" not in path.name
    ]
    if not traces:
        raise ValueError("No trace is available for diagnosis.")
    return traces[0]


def _build_diagnosis(summary: dict[str, Any]) -> dict[str, Any]:
    schema_valid = _nested_bool(summary, "schema", "valid")
    errors = summary.get("errors") if isinstance(summary.get("errors"), list) else []
    step_count = int(summary.get("step_count") or 0)
    artifact_count = int(summary.get("artifact_count") or 0)
    error_count = int(summary.get("error_count") or len(errors))
    findings: list[dict[str, Any]] = []
    if not schema_valid:
        findings.append(
            {
                "severity": "high",
                "message": "Trace schema validation failed.",
                "recommendation": "Open the trace JSON and fix missing or malformed required trace fields.",
            }
        )
    if step_count == 0:
        findings.append(
            {
                "severity": "medium",
                "message": "Trace contains no steps.",
                "recommendation": "Ensure the workflow records each major execution step before writing the trace.",
            }
        )
    if error_count:
        findings.append(
            {
                "severity": "high",
                "message": f"Trace contains {error_count} error record(s).",
                "recommendation": "Inspect the first errors and map them back to run steps or tool calls.",
            }
        )
    if artifact_count == 0:
        findings.append(
            {
                "severity": "low",
                "message": "Trace contains no artifacts.",
                "recommendation": "For tasks that produce files or reports, record artifacts for easier inspection.",
            }
        )
    if not findings:
        findings.append(
            {
                "severity": "info",
                "message": "Trace is structurally healthy.",
                "recommendation": "Review recent steps and HQS output if behavior quality still looks low.",
            }
        )
    return {
        "trace_id": summary.get("trace_id"),
        "trace_type": summary.get("type"),
        "schema_valid": schema_valid,
        "step_count": step_count,
        "artifact_count": artifact_count,
        "error_count": error_count,
        "output_keys": summary.get("output_keys") if isinstance(summary.get("output_keys"), list) else [],
        "findings": findings,
        "recent_steps": summary.get("steps", [])[-8:] if isinstance(summary.get("steps"), list) else [],
        "errors": errors[:5],
    }


def _nested_bool(payload: dict[str, Any], key: str, nested_key: str) -> bool:
    nested = payload.get(key)
    if not isinstance(nested, dict):
        return False
    return bool(nested.get(nested_key))


def _relative_or_absolute(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return str(path)
