from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from agentforge.common.artifact_schema import validate_json_artifact
from agentforge.common.file_store import write_json


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def trace_timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")


def write_trace(
    project_root: Path,
    trace_type: str,
    input_data: Any,
    output: dict[str, Any],
    steps: list[dict[str, Any]] | None = None,
    artifacts: list[dict[str, Any]] | None = None,
    errors: list[dict[str, Any]] | None = None,
    extra_fields: dict[str, Any] | None = None,
) -> Path:
    trace_id = f"trace_{uuid4().hex}"
    trace_path = project_root / "traces" / f"{trace_timestamp()}_{trace_type}.json"
    payload: dict[str, Any] = {
        "trace_id": trace_id,
        "type": trace_type,
        "created_at": utc_now_iso(),
        "input": input_data,
        "steps": steps or [],
        "output": output,
        "artifacts": artifacts or [],
        "errors": errors or [],
    }
    if extra_fields:
        payload.update(extra_fields)
    payload["schema"] = validate_json_artifact(trace_path, payload).to_dict()

    return write_json(trace_path, payload)
