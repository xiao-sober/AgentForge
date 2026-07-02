from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agentforge.common.artifact_schema import validate_json_artifact


def inspect_trace(path_or_name: Path | str, project_root: Path | str = ".") -> dict[str, Any]:
    root = Path(project_root).resolve()
    trace_path = _resolve_trace_path(root, Path(path_or_name))
    if not trace_path.exists():
        raise ValueError(f"Trace not found: {trace_path}")

    try:
        payload = json.loads(trace_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Trace is not valid JSON: {trace_path}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"Trace must be a JSON object: {trace_path}")

    schema = validate_json_artifact(trace_path, payload)
    steps = payload.get("steps", [])
    artifacts = payload.get("artifacts", [])
    errors = payload.get("errors", [])
    return {
        "path": str(trace_path),
        "schema": schema.to_dict(),
        "embedded_schema": payload.get("schema") if isinstance(payload.get("schema"), dict) else None,
        "trace_id": payload.get("trace_id"),
        "type": payload.get("type"),
        "created_at": payload.get("created_at"),
        "step_count": len(steps) if isinstance(steps, list) else 0,
        "artifact_count": len(artifacts) if isinstance(artifacts, list) else 0,
        "error_count": len(errors) if isinstance(errors, list) else 0,
        "steps": _summarize_steps(steps),
        "artifacts": artifacts if isinstance(artifacts, list) else [],
        "errors": errors if isinstance(errors, list) else [],
        "output_keys": sorted(payload.get("output", {}).keys()) if isinstance(payload.get("output"), dict) else [],
    }


def format_trace_summary(summary: dict[str, Any]) -> str:
    lines = [
        f"Trace: {summary.get('path')}",
        f"Type: {summary.get('type')}",
        f"Created: {summary.get('created_at')}",
        f"Schema: {'valid' if summary.get('schema', {}).get('valid') else 'invalid'}",
        f"Steps: {summary.get('step_count')}",
        f"Artifacts: {summary.get('artifact_count')}",
        f"Errors: {summary.get('error_count')}",
    ]
    if summary.get("steps"):
        lines.append("")
        lines.append("Steps:")
        for step in summary["steps"]:
            lines.append(f"- {step.get('name')}: {step.get('status')}")
    if summary.get("errors"):
        lines.append("")
        lines.append("Errors:")
        for error in summary["errors"]:
            lines.append(f"- {error.get('error_type', 'Error')}: {error.get('message')}")
    if summary.get("artifacts"):
        lines.append("")
        lines.append("Artifacts:")
        for artifact in summary["artifacts"]:
            if isinstance(artifact, dict):
                lines.append(f"- {artifact.get('type', 'artifact')}: {artifact.get('path')}")
    return "\n".join(lines)


def _resolve_trace_path(root: Path, path: Path) -> Path:
    if path.is_absolute():
        return path
    if path.parent != Path("."):
        return root / path
    return root / "traces" / path


def _summarize_steps(steps: Any) -> list[dict[str, Any]]:
    if not isinstance(steps, list):
        return []
    summaries = []
    for step in steps:
        if isinstance(step, dict):
            summaries.append({"name": step.get("name"), "status": step.get("status")})
    return summaries
