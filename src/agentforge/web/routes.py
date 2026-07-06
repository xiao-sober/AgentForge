from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

from agentforge.agent.harness import AgentHarness
from agentforge.agent.skill_selector import list_available_skills
from agentforge.common.diagnostics import build_config_report, build_health_report, build_version_report
from agentforge.common.llm_client import LLMProviderError
from agentforge.hqs.system_evaluator import evaluate_system
from agentforge.memory.memory_manager import MemoryManager
from agentforge.providers import ProviderConfigError, create_llm_client, load_provider_config
from agentforge.skill_evolver.evolution_loop import evolve_skill
from agentforge.skill_evolver.skill_runner import run_skill
from agentforge.skill_evolver.task_loader import load_taskset
from agentforge.skill_generator.generator import generate_skill_from_input


@dataclass(frozen=True)
class WebResponse:
    status: int
    payload: dict[str, Any]
    headers: dict[str, str] | None = None
    body_text: str | None = None

    def body(self) -> bytes:
        if self.body_text is not None:
            return self.body_text.encode("utf-8")
        return json.dumps(self.payload, ensure_ascii=False, indent=2).encode("utf-8")


@dataclass(frozen=True)
class ProviderClientSelection:
    client: Any | None
    warnings: list[dict[str, str]]


def handle_request(
    method: str,
    raw_path: str,
    body: bytes | str | None = None,
    project_root: Path | str = ".",
    harness: AgentHarness | None = None,
) -> WebResponse:
    root = Path(project_root).resolve()
    parsed = urlparse(raw_path)
    path_parts = [unquote(part) for part in parsed.path.strip("/").split("/") if part]
    method = method.upper()

    try:
        if method == "GET" and not path_parts:
            return _index(root)
        if method == "GET" and len(path_parts) == 2 and path_parts[0] == "static":
            return _static_asset(path_parts[1])
        if method == "GET" and path_parts == ["health"]:
            return _json(200, build_health_report(root))
        if method == "GET" and path_parts == ["version"]:
            return _json(200, build_version_report(root))
        if method == "GET" and path_parts == ["config"]:
            return _json(200, build_config_report(root))
        if method == "POST" and path_parts == ["chat"]:
            return _chat(body, root, harness, query=parse_qs(parsed.query))
        if method == "POST" and path_parts == ["skills", "generate"]:
            return _generate_skill(body, root)
        if method == "POST" and path_parts == ["skills", "run"]:
            return _run_skill(body, root)
        if method == "POST" and path_parts == ["skills", "evolve"]:
            return _evolve_skill(body, root)
        if method == "GET" and path_parts == ["skills"]:
            return _skills(root)
        if method == "GET" and path_parts == ["tasksets"]:
            return _tasksets(root)
        if method == "GET" and len(path_parts) == 2 and path_parts[0] == "skills":
            return _skill_detail(root, path_parts[1])
        if method == "GET" and len(path_parts) == 3 and path_parts[0] == "skills":
            return _skill_version(root, path_parts[1], path_parts[2])
        if method == "GET" and path_parts == ["memory"]:
            return _memory(root)
        if method == "GET" and len(path_parts) == 3 and path_parts[:2] == ["agent", "runs"]:
            return _agent_run_detail(root, path_parts[2])
        if method == "GET" and len(path_parts) == 4 and path_parts[:2] == ["agent", "runs"] and path_parts[3] == "tool-calls":
            return _agent_run_tool_calls(root, path_parts[2])
        if method == "GET" and path_parts == ["traces"]:
            return _traces(root)
        if method == "GET" and len(path_parts) == 2 and path_parts[0] == "traces":
            return _trace_detail(root, path_parts[1])
        if method == "GET" and path_parts == ["hqs"]:
            return _hqs(root)
    except ValueError as exc:
        return _json(400, {"error": str(exc)})
    except (ProviderConfigError, LLMProviderError) as exc:
        return _json(502, {"error": str(exc)})
    except OSError as exc:
        return _json(500, {"error": f"Filesystem error: {exc}"})

    return _json(404, {"error": "Route not found.", "path": parsed.path})


def _chat(
    body: bytes | str | None,
    root: Path,
    harness: AgentHarness | None,
    query: dict[str, list[str]] | None = None,
) -> WebResponse:
    payload = _decode_json_body(body)
    message = payload.get("message")
    if not isinstance(message, str) or not message.strip():
        raise ValueError("POST /chat requires a non-empty JSON string field: message.")
    provider_selection = _optional_llm_client(payload, root)
    active_harness = harness or AgentHarness(project_root=root, llm_client=provider_selection.client)
    agent_mode = _agent_mode(payload, query or {})
    if agent_mode == "tool_calling":
        result = active_harness.tool_chat(message)
        response_payload = _debug_tool_chat_payload(result) if _wants_debug(payload, query or {}) else _compact_tool_chat_payload(result)
        return _json(200, _with_provider_warnings(response_payload, provider_selection.warnings))
    if agent_mode != "harness_workflow":
        raise ValueError("agent_mode must be either harness_workflow or tool_calling.")
    result = active_harness.chat(message)
    if _wants_debug(payload, query or {}):
        response_payload = _debug_chat_payload(result)
        if provider_selection.warnings:
            response_payload["provider_warnings"] = provider_selection.warnings
        return _json(200, _with_provider_warnings(response_payload, provider_selection.warnings))
    return _json(200, _with_provider_warnings(_compact_chat_payload(result), provider_selection.warnings))


def _generate_skill(body: bytes | str | None, root: Path) -> WebResponse:
    payload = _decode_json_body(body)
    input_text = _required_string(payload, "input")
    provider_selection = _optional_llm_client(payload, root)
    result = generate_skill_from_input(input_text, project_root=root, llm_client=provider_selection.client)
    response = {
        "skill_slug": result.requirement.skill_slug,
        "skill_name": result.requirement.skill_name,
        "version": result.version,
        "skill_path": str(result.skill_path),
        "relative_skill_path": _relative_or_absolute(result.skill_path, root),
        "trace_path": str(result.trace_path),
        "trace_url": _trace_url(result.trace_path),
        "valid": result.validation_result.valid,
        "missing_sections": result.validation_result.missing_sections,
        "generation_mode": result.generation_mode,
        "warnings": provider_selection.warnings,
    }
    return _json(200, response)


def _run_skill(body: bytes | str | None, root: Path) -> WebResponse:
    payload = _decode_json_body(body)
    input_text = _required_string(payload, "input")
    skill_path = _resolve_skill_path(payload, root)
    provider_selection = _optional_llm_client(payload, root)
    result = run_skill(skill_path, input_text, project_root=root, llm_client=provider_selection.client)
    output = result.outputs[0].output if result.outputs else ""
    response = {
        "skill_path": str(result.skill_path),
        "relative_skill_path": _relative_or_absolute(result.skill_path, root),
        "run_dir": str(result.run_dir),
        "relative_run_dir": _relative_or_absolute(result.run_dir, root),
        "result_path": str(result.result_path),
        "trace_path": str(result.trace_path),
        "trace_url": _trace_url(result.trace_path),
        "mode": result.mode,
        "output": output,
        "outputs": [item.to_dict() for item in result.outputs],
        "warnings": provider_selection.warnings,
    }
    return _json(200, response)


def _evolve_skill(body: bytes | str | None, root: Path) -> WebResponse:
    payload = _decode_json_body(body)
    skill_path = _resolve_skill_path(payload, root)
    taskset_path = _resolve_taskset_path(payload, root)
    max_iterations = int(payload.get("max_iterations", 1))
    target_hqs = float(payload.get("target_hqs", 5.0))
    min_improvement = float(payload.get("min_improvement", 0.01))
    provider_selection = _optional_llm_client(payload, root)
    result = evolve_skill(
        skill_path,
        taskset_path,
        project_root=root,
        max_iterations=max_iterations,
        target_hqs=target_hqs,
        min_improvement=min_improvement,
        llm_client=provider_selection.client,
    )
    iterations = []
    for iteration in result.iterations:
        iterations.append(
            {
                "iteration": iteration.iteration,
                "skill_path": str(iteration.skill_path),
                "average_hqs": iteration.hqs_report.average_score,
                "candidate_average_hqs": iteration.candidate_hqs_report.average_score
                if iteration.candidate_hqs_report
                else None,
                "candidate_improvement": iteration.candidate_improvement,
                "decision": iteration.decision,
                "quality_gate": iteration.quality_gate,
                "rewritten_skill_path": str(iteration.rewritten_skill.skill_path) if iteration.rewritten_skill else None,
                "run_dir": str(iteration.run_result.run_dir),
            }
        )
    response = {
        "taskset": result.taskset.to_dict(),
        "final_skill_path": str(result.final_skill_path),
        "relative_final_skill_path": _relative_or_absolute(result.final_skill_path, root),
        "trace_path": str(result.trace_path),
        "trace_url": _trace_url(result.trace_path),
        "stop_reason": result.stop_reason,
        "iterations": iterations,
        "warnings": provider_selection.warnings,
    }
    return _json(200, response)


def _index(root: Path) -> WebResponse:
    return WebResponse(
        status=200,
        payload={},
        headers={"Content-Type": "text/html; charset=utf-8"},
        body_text=_read_static_text("index.html"),
    )


def _static_asset(filename: str) -> WebResponse:
    allowed = {
        "app.css": "text/css; charset=utf-8",
        "app.js": "application/javascript; charset=utf-8",
    }
    if filename not in allowed:
        return _json(404, {"error": f"Static asset not found: {filename}"})
    return WebResponse(status=200, payload={}, headers={"Content-Type": allowed[filename]}, body_text=_read_static_text(filename))


def _skills(root: Path) -> WebResponse:
    return _json(200, {"skills": list_available_skills(root)})


def _tasksets(root: Path) -> WebResponse:
    tasksets = []
    taskset_root = root / "tasksets"
    if taskset_root.exists():
        for path in sorted(taskset_root.glob("*")):
            if path.suffix.lower() not in {".json", ".yaml", ".yml"}:
                continue
            try:
                taskset = load_taskset(path)
                tasksets.append(
                    {
                        "name": taskset.name,
                        "description": taskset.description,
                        "path": str(path),
                        "relative_path": _relative_or_absolute(path, root),
                        "task_count": len(taskset.tasks),
                        "format": path.suffix.lower().lstrip("."),
                    }
                )
            except ValueError as exc:
                tasksets.append(
                    {
                        "name": path.stem,
                        "path": str(path),
                        "relative_path": _relative_or_absolute(path, root),
                        "task_count": 0,
                        "format": path.suffix.lower().lstrip("."),
                        "error": str(exc),
                    }
                )
    return _json(200, {"tasksets": tasksets})


def _skill_detail(root: Path, skill_name: str) -> WebResponse:
    skill_name = _safe_path_segment(skill_name, "Skill name")
    skills = [skill for skill in list_available_skills(root) if skill["skill_slug"] == skill_name]
    if not skills:
        return _json(404, {"error": f"Skill has no readable versions: {skill_name}"})
    return _json(200, skills[0])


def _skill_version(root: Path, skill_name: str, version: str) -> WebResponse:
    skill_name = _safe_path_segment(skill_name, "Skill name")
    version = _safe_path_segment(version, "Skill version")
    skill_path = _find_skill_version_path(root, skill_name, version)
    if not skill_path.exists():
        return _json(404, {"error": f"Skill version not found: {skill_name}/{version}"})
    metadata_path = skill_path.parent / "metadata.json"
    metadata = _read_json(metadata_path) if metadata_path.exists() else None
    diff_text = _read_skill_diff(skill_path, metadata, root)
    return _json(
        200,
        {
            "skill_slug": skill_name,
            "version": version,
            "skill_path": str(skill_path),
            "source": "sample" if "examples" in skill_path.parts else "local",
            "markdown": skill_path.read_text(encoding="utf-8"),
            "metadata": metadata,
            "diff": diff_text,
        },
    )


def _find_skill_version_path(root: Path, skill_name: str, version: str) -> Path:
    for base in [root / "skills", root / "examples" / "skills"]:
        skill_path = base / skill_name / version / "SKILL.md"
        if skill_path.exists():
            return skill_path
    return root / "skills" / skill_name / version / "SKILL.md"


def _read_skill_diff(skill_path: Path, metadata: dict[str, Any] | None, root: Path) -> str | None:
    candidates = [skill_path.parent / "diff.patch"]
    if isinstance(metadata, dict) and isinstance(metadata.get("diff_path"), str):
        try:
            candidates.append(
                _resolve_under_roots(
                    root,
                    Path(str(metadata["diff_path"])),
                    [root / "skills", root / "examples" / "skills"],
                    "Diff path must stay under skills/ or examples/skills/.",
                )
            )
        except ValueError:
            pass
    for candidate in candidates:
        if candidate.exists() and candidate.is_file():
            return candidate.read_text(encoding="utf-8")
    return None


def _memory(root: Path) -> WebResponse:
    return _json(200, MemoryManager(root, trace_updates=False).summary())


def _traces(root: Path) -> WebResponse:
    traces_dir = root / "traces"
    traces: list[dict[str, Any]] = []
    if traces_dir.exists():
        for path in sorted(traces_dir.glob("*.json"), reverse=True):
            try:
                payload = _read_json(path)
                traces.append(
                    {
                        "filename": path.name,
                        "path": str(path),
                        "type": payload.get("type"),
                        "created_at": payload.get("created_at"),
                        "trace_id": payload.get("trace_id"),
                    }
                )
            except ValueError as exc:
                traces.append({"filename": path.name, "path": str(path), "error": str(exc)})
    return _json(200, {"traces": traces})


def _trace_detail(root: Path, filename: str) -> WebResponse:
    filename = _safe_filename(filename, ".json", "Trace filename")
    trace_path = _resolve_under_roots(root, Path("traces") / filename, [root / "traces"], "Trace path must stay under traces/.")
    if not trace_path.exists() or trace_path.suffix != ".json":
        return _json(404, {"error": f"Trace not found: {filename}"})
    return _json(200, _read_json(trace_path))


def _agent_run_detail(root: Path, run_id: str) -> WebResponse:
    trace = _find_agent_run_trace(root, run_id)
    if trace is None:
        return _json(404, {"error": f"Agent run not found: {run_id}"})
    path, payload = trace
    output = payload.get("output") if isinstance(payload.get("output"), dict) else {}
    return _json(
        200,
        {
            "run_id": run_id,
            "agent_mode": output.get("agent_mode") or payload.get("agent_mode") or payload.get("type"),
            "trace_file": path.name,
            "trace_path": str(path),
            "trace_url": _trace_url(path),
            "type": payload.get("type"),
            "created_at": payload.get("created_at"),
            "output": output,
            "run": payload.get("run"),
            "hqs": output.get("response_hqs"),
            "system_hqs": output.get("system_hqs") or payload.get("system_hqs"),
            "stop_reason": output.get("stop_reason"),
            "tool_call_timeline": _tool_call_timeline_from_trace(payload),
        },
    )


def _agent_run_tool_calls(root: Path, run_id: str) -> WebResponse:
    trace = _find_agent_run_trace(root, run_id)
    if trace is None:
        return _json(404, {"error": f"Agent run not found: {run_id}"})
    path, payload = trace
    output = payload.get("output") if isinstance(payload.get("output"), dict) else {}
    timeline = _tool_call_timeline_from_trace(payload)
    return _json(
        200,
        {
            "run_id": run_id,
            "trace_file": path.name,
            "trace_url": _trace_url(path),
            "tool_call_timeline": timeline,
            "tool_call_count": len(timeline),
            "parse_repair_count": output.get("parse_repair_count", _parse_repair_count_from_timeline(timeline)),
            "invalid_call_count": output.get("invalid_call_count"),
            "final_answer_source": output.get("final_answer_source"),
        },
    )


def _hqs(root: Path) -> WebResponse:
    memory = MemoryManager(root, trace_updates=False)
    working = memory.get_working_memory()
    trace_path = working.get("last_trace_path")
    system = evaluate_system(
        {
            "response": "",
            "trace_path": trace_path,
            "steps": [],
            "errors": [],
            "memory_context": memory.retrieve_context_for_task("hqs"),
            "intent": {},
            "selected_skill": None,
        }
    )
    return _json(
        200,
        {
            "last_response_hqs": working.get("last_response_hqs"),
            "last_system_hqs": working.get("last_system_hqs"),
            "current_system_hqs": system.to_dict(),
        },
    )


def _decode_json_body(body: bytes | str | None) -> dict[str, Any]:
    if body is None:
        return {}
    text = body.decode("utf-8") if isinstance(body, bytes) else body
    if not text.strip():
        return {}
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError("Request body must be valid JSON.") from exc
    if not isinstance(payload, dict):
        raise ValueError("Request body must be a JSON object.")
    return payload


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"JSON file is invalid: {path}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"JSON file must contain an object: {path}")
    return payload


def _json(status: int, payload: dict[str, Any]) -> WebResponse:
    return WebResponse(status=status, payload=payload, headers={"Content-Type": "application/json; charset=utf-8"})


def _required_string(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Request requires a non-empty JSON string field: {key}.")
    return value.strip()


def _optional_llm_client(payload: dict[str, Any], root: Path) -> ProviderClientSelection:
    warnings: list[dict[str, str]] = []
    if payload.get("use_provider") is not True:
        return ProviderClientSelection(client=None, warnings=warnings)

    ignored = [key for key in ("provider_config", "provider", "model") if key in payload]
    if ignored:
        warnings.append(
            _provider_warning(
                "ProviderOverrideIgnored",
                "Web API model calls use the default provider config only; provider override fields were ignored.",
            )
        )
    config_path = _resolve_under_roots(
        root,
        Path("config") / "providers.json",
        [root / "config"],
        "Provider config path must stay under config/.",
    )
    try:
        config = load_provider_config(config_path)
        return ProviderClientSelection(client=create_llm_client(config), warnings=warnings)
    except ProviderConfigError as exc:
        raise ProviderConfigError(f"Provider config failed: {exc}") from exc


def _resolve_skill_path(payload: dict[str, Any], root: Path) -> Path:
    raw_path = payload.get("skill_path")
    if isinstance(raw_path, str) and raw_path.strip():
        return _resolve_under_roots(
            root,
            Path(raw_path.strip()),
            [root / "skills", root / "examples" / "skills"],
            "Skill path must stay under skills/ or examples/skills/.",
        )

    skill_slug = _safe_path_segment(_required_string(payload, "skill_slug"), "Skill slug")
    version = payload.get("version")
    if isinstance(version, str) and version.strip():
        safe_version = _safe_path_segment(version.strip(), "Skill version")
        skill_path = root / "skills" / skill_slug / safe_version / "SKILL.md"
        if skill_path.exists():
            return skill_path
        sample_path = root / "examples" / "skills" / skill_slug / safe_version / "SKILL.md"
        if sample_path.exists():
            return sample_path
        raise ValueError(f"Skill version not found: {skill_slug}/{safe_version}")

    for skill in list_available_skills(root):
        if skill.get("skill_slug") == skill_slug:
            return Path(str(skill["latest_skill_path"]))
    raise ValueError(f"Skill not found: {skill_slug}")


def _resolve_taskset_path(payload: dict[str, Any], root: Path) -> Path:
    return _resolve_under_roots(
        root,
        Path(_required_string(payload, "taskset_path")),
        [root / "tasksets"],
        "Task set path must stay under tasksets/.",
    )


def _resolve_under_roots(root: Path, path: Path, allowed_roots: list[Path], message: str) -> Path:
    candidate = path if path.is_absolute() else root / path
    resolved = candidate.resolve()
    for allowed_root in allowed_roots:
        resolved_allowed = allowed_root.resolve()
        if resolved == resolved_allowed or resolved_allowed in resolved.parents:
            return resolved
    raise ValueError(message)


def _compact_chat_payload(result: Any) -> dict[str, Any]:
    execution = result.execution
    selected = execution.selected_skill or result.selected_skill
    return {
        "run_id": result.run.run_id,
        "response": result.response,
        "trace_path": str(result.trace_path),
        "hqs": result.hqs.to_dict(),
        "system_hqs": result.system_hqs.to_dict(),
        "intent": {
            "type": result.intent.intent_type,
            "confidence": result.intent.confidence,
            "requires_skill": result.intent.requires_skill,
        },
        "plan": {
            "action": result.plan.action,
            "steps": _completed_plan_steps(result.plan.to_dict().get("steps", [])),
        },
        "selected_skill": _compact_skill(selected),
        "reinforcement": result.reinforcement,
        "reflection": result.reflection,
        "stop_reason": result.stop_reason,
        "debug_url_hint": "POST /chat with {\"debug\": true} or use /chat?debug=1 for full payload.",
        **_chat_observable_fields(result),
    }


def _debug_chat_payload(result: Any) -> dict[str, Any]:
    payload = result.to_dict()
    payload.update(_chat_observable_fields(result))
    return payload


def _chat_observable_fields(result: Any) -> dict[str, Any]:
    execution = result.execution
    trace_file = Path(result.trace_path).name
    return {
        "trace_file": trace_file,
        "trace_url": _trace_url(result.trace_path),
        "execution_state": execution.execution_state,
        "plan_step_results": execution.plan_step_results,
        "memory_retrieval": result.memory_context.get("retrieval") if isinstance(result.memory_context, dict) else None,
        "artifacts": execution.artifacts,
        "warnings": [
            {
                "type": error.get("error_type"),
                "message": error.get("user_message") or error.get("message"),
            }
            for error in execution.errors
            if error.get("recoverable")
        ],
        "timeline": _compact_timeline(result.run.to_dict().get("steps", [])),
    }


def _completed_plan_steps(steps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return steps


def _compact_skill(skill: Any) -> dict[str, Any] | None:
    if not skill:
        return None
    return {
        "skill_slug": skill.skill_slug,
        "version": skill.version,
        "title": skill.title,
        "source": skill.source,
        "match_score": skill.score,
        "reasons": skill.reasons,
        "skill_path": str(skill.skill_path),
    }


def _compact_timeline(steps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    timeline = []
    for step in steps:
        timeline.append(
            {
                "step_id": step.get("step_id"),
                "name": step.get("name"),
                "kind": step.get("kind"),
                "status": step.get("status"),
                "started_at": step.get("started_at"),
                "completed_at": step.get("completed_at"),
                "artifact_count": len(step.get("artifacts", [])) if isinstance(step.get("artifacts"), list) else 0,
                "error_count": len(step.get("errors", [])) if isinstance(step.get("errors"), list) else 0,
            }
        )
    return timeline


def _find_agent_run_trace(root: Path, run_id: str) -> tuple[Path, dict[str, Any]] | None:
    run_id = _safe_path_segment(run_id, "Run id")
    traces_dir = root / "traces"
    if not traces_dir.exists():
        return None
    for path in sorted(traces_dir.glob("*.json"), reverse=True):
        try:
            payload = _read_json(path)
        except ValueError:
            continue
        if _trace_matches_run_id(payload, run_id):
            return path, payload
    return None


def _trace_matches_run_id(payload: dict[str, Any], run_id: str) -> bool:
    output = payload.get("output") if isinstance(payload.get("output"), dict) else {}
    run = payload.get("run") if isinstance(payload.get("run"), dict) else {}
    return run_id in {
        str(output.get("run_id") or ""),
        str(run.get("run_id") or ""),
    }


def _tool_call_timeline_from_trace(payload: dict[str, Any]) -> list[dict[str, Any]]:
    output = payload.get("output") if isinstance(payload.get("output"), dict) else {}
    existing = output.get("tool_call_timeline")
    if isinstance(existing, list):
        return [item for item in existing if isinstance(item, dict)]
    steps = payload.get("steps") if isinstance(payload.get("steps"), list) else []
    timeline = []
    for step in steps:
        if not isinstance(step, dict):
            continue
        item = _tool_call_item_from_step(step)
        if item is not None:
            timeline.append(item)
    return timeline


def _tool_call_item_from_step(step: dict[str, Any]) -> dict[str, Any] | None:
    decision = step.get("model_decision")
    validation = step.get("validation")
    observation = step.get("observation")
    observation_summary = step.get("observation_summary")
    tool_result = step.get("tool_result")
    tool_name = step.get("tool_name")
    arguments: Any = {}
    decision_type = None
    parse_repair = None
    if isinstance(decision, dict):
        decision_type = decision.get("type")
        tool_name = decision.get("tool_name") or tool_name
        arguments = decision.get("arguments") if isinstance(decision.get("arguments"), dict) else {}
        parse_repair = decision.get("parse_metadata") if isinstance(decision.get("parse_metadata"), dict) else None
    if not any(
        isinstance(value, dict)
        for value in [decision, validation, observation, observation_summary, tool_result]
    ) and tool_name is None:
        return None
    validation_errors = []
    if isinstance(validation, dict) and isinstance(validation.get("errors"), list):
        validation_errors = validation["errors"]
    return {
        "name": step.get("name"),
        "iteration": step.get("iteration"),
        "status": step.get("status"),
        "decision_type": decision_type,
        "tool_name": tool_name,
        "arguments": arguments,
        "model_decision": decision if isinstance(decision, dict) else None,
        "validation": validation if isinstance(validation, dict) else None,
        "validation_errors": validation_errors,
        "parse_repair": parse_repair,
        "observation": observation if isinstance(observation, dict) else None,
        "observation_summary": observation_summary if isinstance(observation_summary, dict) else None,
        "tool_result": tool_result if isinstance(tool_result, dict) else None,
        "errors": step.get("errors") if isinstance(step.get("errors"), list) else [],
    }


def _parse_repair_count_from_timeline(timeline: list[dict[str, Any]]) -> int:
    count = 0
    for item in timeline:
        metadata = item.get("parse_repair")
        if isinstance(metadata, dict) and metadata.get("repaired") is True:
            count += 1
    return count


def _wants_debug(payload: dict[str, Any], query: dict[str, list[str]]) -> bool:
    if payload.get("debug") is True or payload.get("include_debug") is True:
        return True
    values = query.get("debug", []) + query.get("include_debug", [])
    return any(value.lower() in {"1", "true", "yes"} for value in values)


def _agent_mode(payload: dict[str, Any], query: dict[str, list[str]]) -> str:
    raw = payload.get("agent_mode")
    if not isinstance(raw, str):
        values = query.get("agent_mode", [])
        raw = values[0] if values else "harness_workflow"
    normalized = raw.strip().lower().replace("-", "_")
    if normalized in {"", "harness", "harness_workflow"}:
        return "harness_workflow"
    if normalized in {"tool_calling", "tool_calling_agent"}:
        return "tool_calling"
    return normalized


def _compact_tool_chat_payload(result: Any) -> dict[str, Any]:
    state = result.tool_calling.state
    return {
        "run_id": result.run.run_id,
        "agent_mode": result.agent_mode,
        "response": result.response,
        "trace_path": str(result.trace_path),
        "trace_file": Path(result.trace_path).name,
        "trace_url": _trace_url(result.trace_path),
        "hqs": result.hqs.to_dict(),
        "system_hqs": result.system_hqs.to_dict(),
        "tool_call_timeline": result.tool_call_timeline,
        "parse_repair_count": result.parse_repair_count,
        "invalid_call_count": result.invalid_call_count,
        "final_answer_source": result.final_answer_source,
        "hqs_gate": result.hqs_gate,
        "quality_retry": result.quality_retry,
        "tool_calling": {
            "status": state.status,
            "iteration": state.iteration,
            "max_iterations": state.max_iterations,
            "invalid_call_count": state.invalid_call_count,
            "tool_error_count": state.tool_error_count,
            "repeated_tool_call_count": state.repeated_tool_call_count,
            "observations": state.observations,
            "observation_summaries": state.observation_summaries,
            "errors": state.errors,
        },
        "planner": result.planner_metadata,
        "timeline": _compact_timeline(result.run.to_dict().get("steps", [])),
        "memory_retrieval": result.memory_context.get("retrieval") if isinstance(result.memory_context, dict) else None,
        "stop_reason": result.stop_reason,
        "debug_url_hint": "POST /chat with {\"debug\": true, \"agent_mode\": \"tool_calling\"} for full payload.",
    }


def _debug_tool_chat_payload(result: Any) -> dict[str, Any]:
    payload = result.to_dict()
    payload["trace_file"] = Path(result.trace_path).name
    payload["trace_url"] = _trace_url(result.trace_path)
    payload["timeline"] = _compact_timeline(result.run.to_dict().get("steps", []))
    payload["memory_retrieval"] = result.memory_context.get("retrieval") if isinstance(result.memory_context, dict) else None
    payload["tool_call_timeline"] = result.tool_call_timeline
    payload["parse_repair_count"] = result.parse_repair_count
    payload["invalid_call_count"] = result.invalid_call_count
    payload["final_answer_source"] = result.final_answer_source
    return payload


def _with_provider_warnings(payload: dict[str, Any], warnings: list[dict[str, str]]) -> dict[str, Any]:
    if not warnings:
        return payload
    existing = payload.get("warnings")
    payload["warnings"] = [*(existing if isinstance(existing, list) else []), *warnings]
    return payload


def _provider_warning(warning_type: str, message: str) -> dict[str, str]:
    return {"type": warning_type, "message": message}


def _safe_filename(value: str, suffix: str, label: str) -> str:
    filename = _safe_path_segment(value, label)
    if not filename.endswith(suffix):
        raise ValueError(f"{label} must end with {suffix}.")
    return filename


def _safe_path_segment(value: str, label: str) -> str:
    if value in {"", ".", ".."} or "/" in value or "\\" in value or Path(value).name != value:
        raise ValueError(f"{label} must be a single path segment.")
    return value


def _read_static_text(filename: str) -> str:
    path = Path(__file__).parent / "static" / filename
    return path.read_text(encoding="utf-8")


def _trace_url(trace_path: Path) -> str:
    return f"/traces/{trace_path.name}"


def _relative_or_absolute(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return str(path)
