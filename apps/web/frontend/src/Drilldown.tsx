import { useEffect, useState } from "react";
import { getJson } from "./api";
import type { I18nKey } from "./i18n";
import type { DrilldownKey, JsonRecord, ScoreReport, WebPayload } from "./types";
import {
  chipHtml,
  dimensionHtml,
  escapeHtml,
  formatMetadataValue,
  formatScore,
  jsonBlockHtml,
  objectValue,
  schemaLabel,
  skillIdentityFromPayload,
  stringValue,
  traceLabel,
  traceStepHtml,
  traceUrlFromPath
} from "./view-model";

interface DrilldownProps {
  active: DrilldownKey;
  payload: WebPayload | null;
  t: (key: I18nKey) => string;
  onStatus: (text: string, muted: boolean) => void;
}

export function Drilldown({ active, payload, t, onStatus }: DrilldownProps) {
  const [html, setHtml] = useState(`<p>${escapeHtml(t("drilldownEmpty"))}</p>`);

  useEffect(() => {
    let cancelled = false;

    async function render() {
      if (!payload) {
        onStatus(t("runIdle"), true);
        setHtml(`<p>${escapeHtml(t("drilldownEmpty"))}</p>`);
        return;
      }

      onStatus(t("loading"), true);
      setHtml(`<p>${escapeHtml(t("loading"))}</p>`);

      try {
        const nextHtml = await renderDrilldownHtml(active, payload, t);
        if (!cancelled) {
          setHtml(nextHtml);
          onStatus(drilldownLabel(active, t), false);
        }
      } catch (error) {
        if (!cancelled) {
          setHtml(`<p class="status-error">${escapeHtml(error instanceof Error ? error.message : String(error))}</p>`);
          onStatus(t("errors"), false);
        }
      }
    }

    void render();
    return () => {
      cancelled = true;
    };
  }, [active, payload, t, onStatus]);

  return <div className="drilldown-content" dangerouslySetInnerHTML={{ __html: html }} />;
}

async function renderDrilldownHtml(
  active: DrilldownKey,
  payload: WebPayload,
  t: (key: I18nKey) => string
): Promise<string> {
  if (active === "hqs") {
    return renderHqsDrilldown(payload, t);
  }
  if (active === "memory") {
    return renderMemoryDrilldown(payload, t);
  }
  if (active === "diff") {
    return renderSkillDiffDrilldown(payload, t);
  }
  return renderTraceDrilldown(payload, t);
}

async function renderTraceDrilldown(payload: WebPayload, t: (key: I18nKey) => string): Promise<string> {
  const url = payload.trace_url || traceUrlFromPath(payload.trace_path);
  if (!url) {
    return `<p>${escapeHtml(t("noTrace"))}</p>`;
  }
  const trace = await getJson<JsonRecord>(url);
  const steps = Array.isArray(trace.steps) ? trace.steps : [];
  const artifacts = Array.isArray(trace.artifacts) ? trace.artifacts : [];
  const errors = Array.isArray(trace.errors) ? trace.errors : [];
  const traceOutput = objectValue(trace.output);
  const executionState = objectValue(traceOutput?.execution_state) || objectValue(payload.execution_state) || {};

  return [
    `<div class="drill-meta">${chipHtml(t("type"), trace.type)}${chipHtml(t("trace"), trace.trace_id)}${chipHtml(
      t("schema"),
      schemaLabel(trace)
    )}</div>`,
    renderExecutionState(executionState, t),
    `<h3>${escapeHtml(t("steps"))}</h3>`,
    steps.length ? `<ol class="drill-steps">${steps.map((step) => traceStepHtml(objectValue(step) || {}, t)).join("")}</ol>` : `<p>${escapeHtml(t("timelineEmpty"))}</p>`,
    `<h3>${escapeHtml(t("artifacts"))}</h3>`,
    artifacts.length
      ? `<ul class="drill-list">${artifacts
          .map((item) => {
            const artifact = objectValue(item) || {};
            return `<li>${escapeHtml(stringValue(artifact.type) || t("artifact"))}: ${escapeHtml(
              traceLabel(artifact.path || "")
            )}</li>`;
          })
          .join("")}</ul>`
      : `<p>${escapeHtml(t("none"))}</p>`,
    `<h3>${escapeHtml(t("errors"))}</h3>`,
    errors.length
      ? `<ul class="drill-list warning">${errors
          .map((item) => {
            const error = objectValue(item) || {};
            return `<li>${escapeHtml(stringValue(error.error_type) || t("errors"))}: ${escapeHtml(
              stringValue(error.message)
            )}</li>`;
          })
          .join("")}</ul>`
      : `<p>${escapeHtml(t("none"))}</p>`
  ].join("");
}

async function renderHqsDrilldown(payload: WebPayload, t: (key: I18nKey) => string): Promise<string> {
  let hqsPayload = payload;
  if (!payload.hqs && !payload.system_hqs) {
    hqsPayload = await getJson<WebPayload>("/hqs");
  }
  const response = payload.hqs || hqsPayload.last_response_hqs;
  const system = payload.system_hqs || hqsPayload.last_system_hqs || hqsPayload.current_system_hqs;
  return [renderScoreReport(t("response"), response, t), renderScoreReport(t("system"), system, t)].join("");
}

async function renderMemoryDrilldown(payload: WebPayload, t: (key: I18nKey) => string): Promise<string> {
  const memory = await getJson<JsonRecord>("/memory");
  const payloadMemory = objectValue(payload.memory_context);
  const retrieval = objectValue(payload.memory_retrieval) || objectValue(payloadMemory?.retrieval) || null;
  const latestEpisodes = Array.isArray(memory.latest_episodes) ? memory.latest_episodes.slice(-4).reverse() : [];
  const semanticMemory = objectValue(memory.semantic_memory);
  const semanticValues = semanticMemory ? Object.values(semanticMemory).slice(0, 6) : [];

  return [
    `<div class="drill-meta">${chipHtml(t("episodes"), memory.episode_count)}${chipHtml(t("semantic"), memory.semantic_count)}</div>`,
    `<h3>${escapeHtml(t("retrieval"))}</h3>`,
    retrieval ? renderRetrievalSummary(retrieval, t) : `<p>${escapeHtml(t("none"))}</p>`,
    `<h3>${escapeHtml(t("latestEpisodes"))}</h3>`,
    latestEpisodes.length
      ? `<ul class="drill-list">${latestEpisodes
          .map((item) => {
            const episode = objectValue(item) || {};
            const intent = objectValue(episode.intent);
            return `<li><strong>${escapeHtml(stringValue(episode.episode_id) || t("episode"))}</strong><span>${escapeHtml(
              stringValue(intent?.intent_type) || stringValue(episode.user_input)
            )}</span></li>`;
          })
          .join("")}</ul>`
      : `<p>${escapeHtml(t("none"))}</p>`,
    `<h3>${escapeHtml(t("semanticMemory"))}</h3>`,
    semanticValues.length
      ? `<ul class="drill-list">${semanticValues
          .map((item) => {
            const semantic = objectValue(item) || {};
            return `<li><strong>${escapeHtml(stringValue(semantic.key) || t("memory"))}</strong><span>${escapeHtml(
              stringValue(semantic.summary) || stringValue(semantic.best_version)
            )}</span></li>`;
          })
          .join("")}</ul>`
      : `<p>${escapeHtml(t("none"))}</p>`
  ].join("");
}

async function renderSkillDiffDrilldown(payload: WebPayload, t: (key: I18nKey) => string): Promise<string> {
  const identity = skillIdentityFromPayload(payload);
  if (!identity) {
    return `<p>${escapeHtml(t("noDiff"))}</p>`;
  }
  const detail = await getJson<JsonRecord>(
    `/skills/${encodeURIComponent(identity.skill_slug)}/${encodeURIComponent(identity.version)}`
  );
  const metadata = objectValue(detail.metadata) || {};
  const diff = stringValue(detail.diff);
  return [
    `<div class="drill-meta">${chipHtml(t("skill"), detail.skill_slug)}${chipHtml(t("versionLabel"), detail.version)}${chipHtml(
      t("skillSource"),
      detail.source
    )}</div>`,
    Object.keys(metadata).length ? renderMetadataTable(metadata) : "",
    `<h3>${escapeHtml(t("diff"))}</h3>`,
    diff ? `<pre class="diff-block">${escapeHtml(diff)}</pre>` : `<p>${escapeHtml(t("noDiff"))}</p>`
  ].join("");
}

function renderExecutionState(executionState: JsonRecord, t: (key: I18nKey) => string): string {
  if (!executionState.status) {
    return "";
  }
  const transitions = Array.isArray(executionState.transitions) ? executionState.transitions : [];
  const completed = Array.isArray(executionState.completed_steps) ? executionState.completed_steps.length : 0;
  const failed = Array.isArray(executionState.failed_steps) ? executionState.failed_steps.length : 0;
  const skipped = Array.isArray(executionState.skipped_steps) ? executionState.skipped_steps.length : 0;
  return [
    `<h3>${escapeHtml(t("executionState"))}</h3>`,
    `<div class="drill-meta">${chipHtml(t("status"), executionState.status)}${chipHtml(t("completed"), completed)}${chipHtml(
      t("failed"),
      failed
    )}${chipHtml(t("skipped"), skipped)}</div>`,
    transitions.length
      ? `<ol class="drill-steps compact">${transitions
          .slice(-8)
          .map((item) => {
            const transition = objectValue(item) || {};
            const status = stringValue(transition.to_status) || stringValue(transition.status);
            return `<li class="${escapeHtml(status)}"><strong>${escapeHtml(
              stringValue(transition.plan_step_name) || stringValue(transition.event) || t("transition")
            )}</strong><span>${escapeHtml(stringValue(transition.reason) || status)}</span></li>`;
          })
          .join("")}</ol>`
      : ""
  ].join("");
}

function renderScoreReport(title: string, report: ScoreReport | undefined, t: (key: I18nKey) => string): string {
  if (!report) {
    return `<h3>${escapeHtml(title)}</h3><p>${escapeHtml(t("none"))}</p>`;
  }
  const scores = report.scores && typeof report.scores === "object" ? report.scores : {};
  return [
    `<h3>${escapeHtml(title)}</h3>`,
    `<div class="drill-meta">${chipHtml(t("avg"), formatScore(report.average_score))}${chipHtml(
      t("confidence"),
      formatScore(report.confidence)
    )}</div>`,
    `<div class="dimension-list">${Object.entries(scores)
      .map(([name, score]) => dimensionHtml(name, score))
      .join("")}</div>`
  ].join("");
}

function renderRetrievalSummary(retrieval: JsonRecord, t: (key: I18nKey) => string): string {
  const episodeScores = Array.isArray(retrieval.episode_scores) ? retrieval.episode_scores : [];
  const semanticScores = Array.isArray(retrieval.semantic_scores) ? retrieval.semantic_scores : [];
  return [
    `<div class="drill-meta">${chipHtml(t("query"), retrieval.query)}${chipHtml(t("episodes"), retrieval.episode_count)}${chipHtml(
      t("semantic"),
      retrieval.semantic_count
    )}</div>`,
    retrievalRows(t("episodes"), episodeScores, t),
    retrievalRows(t("semantic"), semanticScores, t)
  ].join("");
}

function retrievalRows(title: string, rows: unknown[], t: (key: I18nKey) => string): string {
  if (!rows.length) {
    return `<h4>${escapeHtml(title)}</h4><p>${escapeHtml(t("none"))}</p>`;
  }
  return [
    `<h4>${escapeHtml(title)}</h4>`,
    `<ul class="drill-list">${rows
      .map((item) => {
        const row = objectValue(item) || {};
        const reasons = Array.isArray(row.reasons) ? row.reasons.map(escapeHtml).join(", ") : "";
        return `<li><strong>#${escapeHtml(row.rank || "-")} ${escapeHtml(
          stringValue(row.key) || t("memory")
        )}</strong><span>${escapeHtml(t("score"))} ${escapeHtml(row.score || 0)} · ${reasons}</span></li>`;
      })
      .join("")}</ul>`
  ].join("");
}

function renderMetadataTable(metadata: JsonRecord): string {
  const rows = Object.entries(metadata)
    .filter(([key]) =>
      ["previous_version", "new_version", "hqs_average", "candidate_improvement", "decision", "created_at", "diff_path"].includes(
        key
      )
    )
    .map(([key, value]) => `<dt>${escapeHtml(key)}</dt><dd>${escapeHtml(formatMetadataValue(value))}</dd>`)
    .join("");
  return rows ? `<dl class="drill-kv">${rows}</dl>` : "";
}

function drilldownLabel(name: DrilldownKey, t: (key: I18nKey) => string): string {
  if (name === "hqs") {
    return t("hqs");
  }
  if (name === "memory") {
    return t("memory");
  }
  if (name === "diff") {
    return t("skillDiff");
  }
  return t("trace");
}
