from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from agentforge.common.llm_client import LLMClient
from agentforge.common.trace import write_trace
from agentforge.skill_generator.prompts import SKILL_GENERATION_SYSTEM_PROMPT, build_skill_generation_prompt
from agentforge.skill_generator.requirement_parser import SkillRequirement, parse_requirement
from agentforge.skill_generator.skill_schema import SkillValidationResult
from agentforge.skill_generator.skill_writer import write_skill
from agentforge.workflows import WorkflowRunner


@dataclass(frozen=True)
class GeneratedSkill:
    requirement: SkillRequirement
    skill_path: Path
    trace_path: Path
    validation_result: SkillValidationResult
    version: str
    generation_mode: str
    run_id: str | None = None


def generate_skill_from_input(
    input_text: str,
    project_root: Path | str = ".",
    llm_client: LLMClient | None = None,
) -> GeneratedSkill:
    root = Path(project_root).resolve()
    run_service = WorkflowRunner.for_task(
        root,
        workflow_id="skill_generation_workflow",
        task_type="skill_generate",
        steps=[
            "parse_requirement",
            "generate_skill_markdown_with_llm",
            "generate_skill_markdown_local",
            "write_skill",
            "validate_skill",
        ],
    )
    run_id = run_service.start_run(
        task_type="skill_generate",
        title="Generate Skill",
        input_data={"input": input_text},
    )
    steps: list[dict[str, object]] = []
    errors: list[dict[str, object]] = []
    provider_metadata = llm_client.metadata() if llm_client else None
    generation_mode = "model" if llm_client else "local"

    try:
        requirement = parse_requirement(input_text)
    except Exception as exc:
        run_service.fail_run(run_id, {"error_type": exc.__class__.__name__, "message": str(exc)})
        raise
    steps.append({"name": "parse_requirement", "status": "completed", "skill_slug": requirement.skill_slug})
    run_service.record_step(run_id, steps[-1], len(steps))
    run_service.update_run(run_id, "running", {"skill_slug": requirement.skill_slug, "skill_name": requirement.skill_name})

    generated_markdown = None
    if llm_client:
        prompt = build_skill_generation_prompt(input_text, requirement)
        try:
            generated_markdown = llm_client.complete(prompt, system_prompt=SKILL_GENERATION_SYSTEM_PROMPT)
            steps.append(
                {
                    "name": "generate_skill_markdown_with_llm",
                    "status": "completed",
                    "provider": provider_metadata,
                }
            )
            run_service.record_step(run_id, steps[-1], len(steps))
        except Exception as exc:
            error = {
                "message": "LLM Skill generation failed.",
                "error_type": exc.__class__.__name__,
                "detail": str(exc),
                "provider": provider_metadata,
            }
            errors.append(error)
            run_service.fail_run(run_id, error)
            failure_trace_path = write_trace(
                project_root=root,
                trace_type="skill_generation",
                input_data=input_text,
                output={
                    "parsed_requirement": requirement.to_dict(),
                    "generated_skill_path": None,
                    "validation_result": None,
                    "generation_mode": generation_mode,
                    "provider": provider_metadata,
                },
                steps=steps,
                artifacts=[],
                errors=errors,
                extra_fields={
                    "parsed_requirement": requirement.to_dict(),
                    "generated_skill_path": None,
                    "validation_result": None,
                    "generation_mode": generation_mode,
                    "provider": provider_metadata,
                },
            )
            run_service.record_run(
                task_type="skill_generate",
                title=f"Generate Skill: {requirement.skill_name}",
                input_data={"input": input_text},
                output_data={
                    "parsed_requirement": requirement.to_dict(),
                    "generated_skill_path": None,
                    "validation_result": None,
                    "generation_mode": generation_mode,
                    "provider": provider_metadata,
                },
                trace_path=failure_trace_path,
                status="failed",
                run_id=run_id,
                steps=steps,
                artifacts=[],
            )
            raise
    else:
        steps.append({"name": "generate_skill_markdown_local", "status": "completed"})
        run_service.record_step(run_id, steps[-1], len(steps))

    written = write_skill(requirement, project_root=root, markdown=generated_markdown)
    steps.append(
        {
            "name": "write_skill",
            "status": "completed",
            "path": str(written.skill_path),
            "version": written.version,
            "was_repaired": written.was_repaired,
        }
    )
    run_service.record_step(run_id, steps[-1], len(steps))

    validation_payload = written.validation_result.to_dict()
    steps.append({"name": "validate_skill", "status": "completed", "validation": validation_payload})
    run_service.record_step(run_id, steps[-1], len(steps))
    if not written.validation_result.valid:
        errors.append({"message": "Generated Skill failed schema validation.", "validation": validation_payload})

    generated_rel_path = _relative_or_absolute(written.skill_path, root)
    trace_output = {
        "parsed_requirement": requirement.to_dict(),
        "generated_skill_path": generated_rel_path,
        "validation_result": validation_payload,
        "generation_mode": generation_mode,
        "provider": provider_metadata,
        "was_repaired": written.was_repaired,
        "validation_before_repair": written.validation_before_repair.to_dict()
        if written.validation_before_repair
        else None,
    }
    trace_path = write_trace(
        project_root=root,
        trace_type="skill_generation",
        input_data=input_text,
        output=trace_output,
        steps=steps,
        artifacts=[{"type": "skill", "path": generated_rel_path}],
        errors=errors,
        extra_fields={
            "parsed_requirement": requirement.to_dict(),
            "generated_skill_path": generated_rel_path,
            "validation_result": validation_payload,
            "generation_mode": generation_mode,
            "provider": provider_metadata,
        },
    )
    run_id = run_service.record_run(
        task_type="skill_generate",
        title=f"Generate Skill: {requirement.skill_name}",
        input_data={"input": input_text},
        output_data=trace_output,
        trace_path=trace_path,
        status="failed" if errors else "completed",
        run_id=run_id,
        steps=steps,
        artifacts=[{"type": "skill", "path": generated_rel_path}],
    )

    return GeneratedSkill(
        requirement=requirement,
        skill_path=written.skill_path,
        trace_path=trace_path,
        validation_result=written.validation_result,
        version=written.version,
        generation_mode=generation_mode,
        run_id=run_id,
    )


def _relative_or_absolute(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return str(path)
