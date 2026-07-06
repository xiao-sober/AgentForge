import type { I18nKey } from "./i18n";
import type { JsonRecord, ScoreReport, SkillSummary, TimelineStep, WebPayload } from "./types";

export type Translator = (key: I18nKey) => string;

export function timelineForPayload(payload: WebPayload | null): TimelineStep[] {
  if (!payload) {
    return [];
  }
  if (Array.isArray(payload.tool_call_timeline) && payload.tool_call_timeline.length) {
    return payload.tool_call_timeline;
  }
  if (Array.isArray(payload.timeline)) {
    return payload.timeline;
  }
  if (payload.run && Array.isArray(payload.run.steps)) {
    return payload.run.steps;
  }
  return [];
}

export function isToolCallTimelineStep(step: TimelineStep): boolean {
  return Boolean(
    step &&
      (step.model_decision ||
        step.decision_type ||
        step.tool_name ||
        step.validation ||
        step.observation ||
        step.observation_summary ||
        step.parse_repair ||
        step.tool_result)
  );
}

export function markdownToHtml(markdown: string): string {
  const lines = String(markdown).replaceAll("\r\n", "\n").split("\n");
  const html: string[] = [];
  let listOpen = false;

  for (const line of lines) {
    const trimmed = line.trim();
    if (!trimmed) {
      if (listOpen) {
        html.push("</ul>");
        listOpen = false;
      }
      continue;
    }
    if (trimmed.startsWith("### ")) {
      if (listOpen) {
        html.push("</ul>");
        listOpen = false;
      }
      html.push(`<h3>${inlineMarkdown(trimmed.slice(4))}</h3>`);
      continue;
    }
    if (trimmed.startsWith("## ")) {
      if (listOpen) {
        html.push("</ul>");
        listOpen = false;
      }
      html.push(`<h2>${inlineMarkdown(trimmed.slice(3))}</h2>`);
      continue;
    }
    if (trimmed.startsWith("# ")) {
      if (listOpen) {
        html.push("</ul>");
        listOpen = false;
      }
      html.push(`<h1>${inlineMarkdown(trimmed.slice(2))}</h1>`);
      continue;
    }
    if (trimmed.startsWith("- ")) {
      if (!listOpen) {
        html.push("<ul>");
        listOpen = true;
      }
      html.push(`<li>${inlineMarkdown(trimmed.slice(2))}</li>`);
      continue;
    }
    if (listOpen) {
      html.push("</ul>");
      listOpen = false;
    }
    html.push(`<p>${inlineMarkdown(trimmed)}</p>`);
  }

  if (listOpen) {
    html.push("</ul>");
  }
  return html.join("\n");
}

function inlineMarkdown(text: string): string {
  let escaped = escapeHtml(text);
  escaped = escaped.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
  escaped = escaped.replace(/`(.+?)`/g, "<code>$1</code>");
  return escaped;
}

export function escapeHtml(text: unknown): string {
  return String(text)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

export function formatScore(score: unknown): string {
  return typeof score === "number" && Number.isFinite(score) ? score.toFixed(2) : "-";
}

export function scoreNumber(report: ScoreReport | undefined): number | undefined {
  return typeof report?.average_score === "number" ? report.average_score : undefined;
}

export function formatSkill(skill: SkillSummary | JsonRecord | undefined): string {
  if (!skill) {
    return "-";
  }
  const title = stringValue(skill.title) || stringValue(skill.skill_slug) || "Skill";
  const version = stringValue(skill.version) ? ` ${stringValue(skill.version)}` : "";
  const source = stringValue(skill.source) ? ` (${stringValue(skill.source)})` : "";
  return `${title}${version}${source}`;
}

export function traceLabel(path: unknown): string {
  const normalized = String(path || "").replaceAll("\\", "/");
  return normalized.split("/").pop() || normalized;
}

export function traceUrlFromPath(path: unknown): string | undefined {
  if (!path) {
    return undefined;
  }
  return `/traces/${encodeURIComponent(traceLabel(path))}`;
}

export function skillIdentityFromPayload(payload: WebPayload): { skill_slug: string; version: string } | null {
  const selected = (payload.selected_skill || objectValue(payload.execution?.selected_skill)) as JsonRecord | undefined;
  if (selected && stringValue(selected.skill_slug) && stringValue(selected.version)) {
    return { skill_slug: stringValue(selected.skill_slug), version: stringValue(selected.version) };
  }
  if (payload.skill_slug && payload.version) {
    return { skill_slug: payload.skill_slug, version: payload.version };
  }
  const paths = [
    payload.relative_final_skill_path,
    payload.final_skill_path,
    payload.relative_skill_path,
    payload.skill_path
  ].filter(Boolean);
  for (const rawPath of paths) {
    const match = String(rawPath)
      .replaceAll("\\", "/")
      .match(/(?:^|\/)(?:skills|examples\/skills)\/([^/]+)\/([^/]+)\/SKILL\.md$/);
    if (match) {
      return { skill_slug: match[1], version: match[2] };
    }
  }
  return null;
}

export function schemaLabel(trace: JsonRecord): string {
  const schema = objectValue(trace.schema) || objectValue(trace.embedded_schema) || {};
  return stringValue(schema.name) || stringValue(schema.version) || "trace";
}

export function formatMetadataValue(value: unknown): string {
  if (Array.isArray(value)) {
    return value.map(String).join(", ");
  }
  if (value && typeof value === "object") {
    return JSON.stringify(value);
  }
  return value === undefined || value === null ? "" : String(value);
}

export function chipHtml(label: string, value: unknown): string {
  if (value === undefined || value === null || value === "") {
    return "";
  }
  return `<span class="badge">${escapeHtml(label)}: ${escapeHtml(String(value))}</span>`;
}

export function jsonBlockHtml(value: unknown): string {
  const text = typeof value === "string" ? value : JSON.stringify(value, null, 2);
  return `<pre class="json-block">${escapeHtml(text)}</pre>`;
}

export function toolCallTimelineHtml(step: TimelineStep, t: Translator): string {
  const status = step.status || t("unknown");
  const name = step.tool_name || step.name || step.decision_type || t("step");
  const decisionType = step.decision_type || stringValue(objectValue(step.model_decision)?.type);
  const badges = [
    chipHtml(t("status"), status),
    decisionType ? chipHtml(t("decision"), decisionType) : "",
    step.iteration ? chipHtml(t("iterations"), step.iteration) : "",
    repairBadgeHtml(step.parse_repair || objectValue(step.model_decision)?.parse_metadata, t)
  ].join("");
  return [
    `<div class="tool-call-head"><strong>${escapeHtml(name)}</strong><span>${badges}</span></div>`,
    `<div class="tool-call-details">`,
    detailJsonHtml(t("modelDecision"), step.model_decision),
    detailJsonHtml(t("toolArguments"), step.arguments),
    validationHtml(step, t),
    detailJsonHtml(t("observation"), step.observation_summary || step.observation),
    detailJsonHtml(t("parseRepair"), step.parse_repair || objectValue(step.model_decision)?.parse_metadata),
    `</div>`
  ].join("");
}

export function traceStepHtml(step: TimelineStep, t: Translator): string {
  if (isToolCallTimelineStep(step)) {
    return `<li class="${escapeHtml(step.status || "")} tool-call-row">${toolCallTimelineHtml(step, t)}</li>`;
  }
  const status = step.status || t("unknown");
  const name = step.name || step.step_id || t("step");
  const detail = step.kind || stringValue(step.tool_name) || stringValue(step.error_type);
  return `<li class="${escapeHtml(status)}"><strong>${escapeHtml(name)}</strong><span>${escapeHtml(
    status + (detail ? ` · ${detail}` : "")
  )}</span></li>`;
}

export function dimensionHtml(name: string, score: unknown): string {
  const numeric = typeof score === "number" ? score : Number(score || 0);
  const width = Math.max(0, Math.min(100, (numeric / 5) * 100));
  return `<div class="dimension"><span>${escapeHtml(name)}</span><strong>${escapeHtml(
    formatScore(numeric)
  )}</strong><div class="scorebar"><span style="width:${width}%"></span></div></div>`;
}

export function objectValue(value: unknown): JsonRecord | undefined {
  return value && typeof value === "object" && !Array.isArray(value) ? (value as JsonRecord) : undefined;
}

export function stringValue(value: unknown): string {
  return typeof value === "string" ? value : "";
}

function validationHtml(step: TimelineStep, t: Translator): string {
  const validation = step.validation;
  const errors = Array.isArray(step.validation_errors) ? step.validation_errors : [];
  const extraErrors = Array.isArray(step.errors) ? step.errors : [];
  if (!validation && !errors.length && !extraErrors.length) {
    return "";
  }
  const errorHtml = [...errors, ...extraErrors].length
    ? `<ul class="validation-errors">${[...errors, ...extraErrors]
        .map((error) => `<li>${escapeHtml(formatMetadataValue(error))}</li>`)
        .join("")}</ul>`
    : "";
  return [
    `<details class="tool-call-detail validation-detail" ${errors.length || extraErrors.length ? "open" : ""}>`,
    `<summary>${escapeHtml(t("validation"))}</summary>`,
    validation ? jsonBlockHtml(validation) : "",
    errorHtml,
    `</details>`
  ].join("");
}

function repairBadgeHtml(metadata: unknown, t: Translator): string {
  const item = objectValue(metadata);
  if (!item || item.repaired !== true) {
    return "";
  }
  return `<span class="badge repair-badge">${escapeHtml(t("repaired"))}: ${escapeHtml(
    stringValue(item.repair_strategy) || t("unknown")
  )}</span>`;
}

function detailJsonHtml(label: string, value: unknown): string {
  if (
    value === undefined ||
    value === null ||
    value === "" ||
    (typeof value === "object" && !Array.isArray(value) && !Object.keys(value).length)
  ) {
    return "";
  }
  return [
    `<details class="tool-call-detail">`,
    `<summary>${escapeHtml(label)}</summary>`,
    jsonBlockHtml(value),
    `</details>`
  ].join("");
}
