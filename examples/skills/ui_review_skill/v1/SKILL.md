# UI Review Skill

## Purpose

Analyze UI screenshots or page descriptions and produce structured, evidence-based improvement advice.

## When to Use

Use this Skill when the user asks to review a dashboard, admin page, product screen, workflow, screenshot, or UI description.

## Inputs

- screenshot
- page description
- user goal
- visible UI constraints

## Outputs

- issues
- reasons
- recommendations
- priority
- assumptions

## Workflow

1. Identify the provided UI context, user goal, and visible or described constraints.
2. Extract layout areas, information hierarchy, data elements, interactions, and unclear parts.
3. Analyze readability, hierarchy, workflow closure, feedback, error states, and data interpretation.
4. List concrete issues with evidence from the provided input.
5. Recommend specific improvements and assign priority when impact is clear.
6. State assumptions and missing context before making uncertain claims.

## Constraints

- Do not invent UI elements, data, or user behavior that was not provided.
- Prefer actionable recommendations over generic design advice.
- Mark uncertainty clearly when screenshot or page context is incomplete.
- Keep recommendations feasible for an MVP implementation pass.

## Quality Criteria

- Output separates findings, reasons, recommendations, and assumptions.
- Advice is specific enough for a designer or engineer to act on.
- Priority labels reflect user impact and implementation urgency.
- Risky or uncertain claims are qualified.

## Failure Modes

- The response gives generic style advice without tying it to the provided UI.
- The response invents screen elements or user flows.
- The response misses hierarchy, data readability, or workflow issues.
- Priority labels are assigned without evidence.

## Examples

- Input: "Review this admin dashboard for layout and readability." Output: list layout, hierarchy, data density, and action clarity issues with recommendations.

## Version Notes

- v1: Sample built-in Skill for first-run AgentForge chat and taskset testing.
