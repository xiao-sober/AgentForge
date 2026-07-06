from __future__ import annotations

from agentforge.skill_evolver.hqs_evaluator import HQSReport
from agentforge.skill_evolver.task_loader import TaskSet


def build_reflection_report(taskset: TaskSet, hqs_report: HQSReport) -> str:
    dimension_averages = _dimension_averages(hqs_report)
    weak_dimensions = [dimension for dimension, score in dimension_averages.items() if score < 4.0]
    strongest_dimensions = [dimension for dimension, score in dimension_averages.items() if score >= 4.0]

    lines = [
        "# Skill Reflection Report",
        "",
        "## Summary",
        "",
        f"- Task set: {taskset.name}",
        f"- Task count: {len(taskset.tasks)}",
        f"- Average HQS: {hqs_report.average_score:.2f}",
        "",
        "## Dimension Averages",
        "",
    ]
    for dimension, score in dimension_averages.items():
        lines.append(f"- {dimension}: {score:.2f}")

    lines.extend(["", "## Strengths", ""])
    if strongest_dimensions:
        for dimension in strongest_dimensions:
            lines.append(f"- {dimension} met the local AgentForge threshold.")
    else:
        lines.append("- No dimension reached the local AgentForge strength threshold.")

    lines.extend(["", "## Weaknesses", ""])
    if weak_dimensions:
        for dimension in weak_dimensions:
            lines.append(f"- {dimension} should be reinforced in the next Skill version.")
    else:
        lines.append("- No weak dimensions were detected by the deterministic evaluator.")

    lines.extend(["", "## Rewrite Guidance", ""])
    if weak_dimensions:
        lines.append("- Add clearer workflow steps for low-scoring dimensions.")
        lines.append("- Make expected output structure explicit enough to evaluate consistently.")
        lines.append("- Preserve uncertainty handling and hallucination controls.")
    else:
        lines.append("- Keep the current structure and add version notes documenting the evaluation.")

    lines.extend(["", "## Per-Task Notes", ""])
    for evaluation in hqs_report.per_task:
        lines.append(f"- {evaluation.task_id}: HQS {evaluation.average:.2f}")

    return "\n".join(lines).rstrip() + "\n"


def _dimension_averages(hqs_report: HQSReport) -> dict[str, float]:
    totals = {dimension: 0.0 for dimension in hqs_report.dimensions}
    if not hqs_report.per_task:
        return totals
    for evaluation in hqs_report.per_task:
        for dimension in hqs_report.dimensions:
            totals[dimension] += evaluation.scores.get(dimension, 0.0)
    return {dimension: round(total / len(hqs_report.per_task), 2) for dimension, total in totals.items()}
