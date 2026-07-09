import type { I18nKey } from "../../i18n";
import type { ArtifactItem, Lang, SummaryState, TimelineStep, WebPayload, WarningItem } from "../../types";
import { formatScore, scoreNumber, traceLabel } from "../../view-model";
import { HqsView } from "../hqs/HqsView";
import { MemoryView } from "../memory/MemoryView";
import { TasksView } from "../tasks/TasksView";
import { ToolsView } from "../tools/ToolsView";
import { TraceViewer } from "../traces/TraceViewer";
import { collectWarnings, friendlyTimeline, taskTypeFromPayload } from "../agent/AgentPage";
import { ObservationMetricGrid, ObservationSection } from "./ObservationPrimitives";

export type ObservationPanelKey = "current" | "tasks" | "tools" | "memory" | "hqs" | "traces" | "developer";

interface ObservationDrawerProps {
  open: boolean;
  activePanel: ObservationPanelKey;
  lang: Lang;
  t: (key: I18nKey) => string;
  currentPayload: WebPayload | null;
  debugPayload: WebPayload | Record<string, never>;
  summary: SummaryState;
  onPanel: (panel: ObservationPanelKey) => void;
  onClose: () => void;
}

export function ObservationDrawer({
  open,
  activePanel,
  lang,
  t,
  currentPayload,
  debugPayload,
  summary,
  onPanel,
  onClose
}: ObservationDrawerProps) {
  const copy = (zh: string, en: string) => (lang === "zh" ? zh : en);
  const tabs: Array<{ key: ObservationPanelKey; label: string }> = [
    { key: "current", label: copy("当前运行", "Current") },
    { key: "tasks", label: t("tasks") },
    { key: "tools", label: t("tools") },
    { key: "memory", label: t("memory") },
    { key: "hqs", label: t("hqs") },
    { key: "traces", label: t("traces") },
    { key: "developer", label: copy("开发者数据", "Developer") }
  ];

  return (
    <>
      <div className={open ? "drawer-scrim open" : "drawer-scrim"} onClick={onClose} />
      <aside className={open ? "observation-drawer open" : "observation-drawer"} aria-hidden={!open} aria-label={copy("高级观察视图", "Advanced observation")}>
        <div className="drawer-head">
          <div>
            <span className="eyebrow">{copy("高级观察", "Advanced details")}</span>
            <h2>{copy("运行记录与调试详情", "Run record and debug details")}</h2>
          </div>
          <button className="secondary drawer-close" type="button" onClick={onClose}>
            {copy("关闭", "Close")}
          </button>
        </div>

        <div className="drawer-tabs" role="tablist" aria-label={copy("观察视图", "Observation views")}>
          {tabs.map((tab) => (
            <button
              aria-selected={activePanel === tab.key}
              className={activePanel === tab.key ? "drawer-tab active" : "drawer-tab"}
              key={tab.key}
              role="tab"
              type="button"
              onClick={() => onPanel(tab.key)}
            >
              {tab.label}
            </button>
          ))}
        </div>

        <div className="drawer-body">
          {activePanel === "current" ? <CurrentRunObservation lang={lang} payload={currentPayload} summary={summary} /> : null}
          {activePanel === "tasks" ? <TasksView active t={t} /> : null}
          {activePanel === "tools" ? <ToolsView active t={t} /> : null}
          {activePanel === "memory" ? <MemoryView active t={t} /> : null}
          {activePanel === "hqs" ? <HqsView active t={t} /> : null}
          {activePanel === "traces" ? <TraceViewer active t={t} /> : null}
          {activePanel === "developer" ? <DeveloperData lang={lang} payload={debugPayload} /> : null}
        </div>
      </aside>
    </>
  );
}

function CurrentRunObservation({
  lang,
  payload,
  summary
}: {
  lang: Lang;
  payload: WebPayload | null;
  summary: SummaryState;
}) {
  const copy = (zh: string, en: string) => (lang === "zh" ? zh : en);
  if (!payload) {
    return (
      <section className="drawer-empty">
        <h3>{copy("还没有运行记录", "No run yet")}</h3>
        <p>{copy("完成一次 Agent 运行后，这里会展示过程记录、使用能力、生成内容和质量检查。", "After an Agent run, this panel will show timeline, capabilities, artifacts, and quality checks.")}</p>
      </section>
    );
  }
  const warnings = collectWarnings(payload);
  return (
    <section className="current-observation">
      <ObservationSummary lang={lang} payload={payload} summary={summary} warnings={warnings} />
      <ObservationSection title={copy("过程记录", "Timeline")} badge={String(friendlyTimeline(payload, lang).length)}>
        <FriendlyTimeline lang={lang} payload={payload} />
      </ObservationSection>
      <ObservationSection title={copy("使用能力", "Capabilities Used")} badge={String((payload.tool_call_timeline || []).length)}>
        <CapabilityList lang={lang} steps={payload.tool_call_timeline || []} />
      </ObservationSection>
      <ObservationSection title={copy("生成内容", "Artifacts")} badge={String((payload.artifacts || []).length + (payload.trace_path ? 1 : 0))}>
        <ArtifactList lang={lang} artifacts={payload.artifacts || []} tracePath={payload.trace_path} traceUrl={payload.trace_url} />
      </ObservationSection>
      <ObservationSection title={copy("质量检查", "Quality Check")} badge={qualityBadge(payload, lang)}>
        <QualityDetails lang={lang} payload={payload} warnings={warnings} />
      </ObservationSection>
    </section>
  );
}

function ObservationSummary({
  lang,
  payload,
  summary,
  warnings
}: {
  lang: Lang;
  payload: WebPayload;
  summary: SummaryState;
  warnings: WarningItem[];
}) {
  const copy = (zh: string, en: string) => (lang === "zh" ? zh : en);
  const trace = payload.trace_path || payload.trace_file || summary.traceLabel || "";
  return (
    <ObservationMetricGrid
      dense
      items={[
        { label: copy("任务", "Task"), value: humanize(taskTypeFromPayload(payload) || summary.intent) },
        { label: copy("运行 ID", "Run ID"), value: payload.run_id || "-" },
        { label: copy("警告", "Warnings"), value: String(warnings.length), tone: warnings.length ? "warning" : "ok" },
        { label: copy("Trace", "Trace"), value: trace ? traceLabel(trace) : "-", tone: "trace" }
      ]}
    />
  );
}

function FriendlyTimeline({ lang, payload }: { lang: Lang; payload: WebPayload }) {
  const copy = (zh: string, en: string) => (lang === "zh" ? zh : en);
  const items = friendlyTimeline(payload, lang);
  if (!items.length) {
    return <p className="muted-text">{copy("暂无过程记录。", "No timeline recorded.")}</p>;
  }
  return (
    <ol className="drawer-timeline">
      {items.map((item, index) => (
        <li className={item.tone} key={`${item.title}-${index}`}>
          <span className="node-marker" />
          <div>
            <strong>{item.title}</strong>
            <small>
              {item.status}
              {item.detail ? ` · ${item.detail}` : ""}
            </small>
          </div>
        </li>
      ))}
    </ol>
  );
}

function CapabilityList({ lang, steps }: { lang: Lang; steps: TimelineStep[] }) {
  const copy = (zh: string, en: string) => (lang === "zh" ? zh : en);
  if (!steps.length) {
    return <p className="muted-text">{copy("本次运行没有记录工具调用。", "No tool calls recorded for this run.")}</p>;
  }
  return (
    <ol className="capability-list">
      {steps.slice(0, 12).map((step, index) => {
        const name = step.tool_name || step.name || step.decision_type || copy("能力调用", "Capability");
        return (
          <li className={step.status || "recorded"} key={`${name}-${index}`}>
            <div>
              <strong>{humanize(name)}</strong>
              <small>{step.status || copy("已记录", "Recorded")}</small>
            </div>
            {step.observation_summary ? <span>{formatShort(step.observation_summary)}</span> : null}
          </li>
        );
      })}
    </ol>
  );
}

function ArtifactList({
  lang,
  artifacts,
  tracePath,
  traceUrl
}: {
  lang: Lang;
  artifacts: ArtifactItem[];
  tracePath?: string;
  traceUrl?: string;
}) {
  const copy = (zh: string, en: string) => (lang === "zh" ? zh : en);
  const items = [...artifacts];
  if (tracePath) {
    items.push({ type: "trace", path: tracePath });
  }
  if (!items.length) {
    return <p className="muted-text">{copy("暂无生成内容。", "No artifacts recorded.")}</p>;
  }
  return (
    <ul className="drawer-artifacts">
      {items.slice(0, 10).map((artifact, index) => {
        const path = artifact.relative_path || artifact.path || "";
        const isTrace = artifact.type === "trace" || path === tracePath;
        const href = isTrace && path ? traceUrl || `/api/traces/${encodeURIComponent(traceLabel(path))}` : "";
        return (
          <li key={`${artifact.type}-${path}-${index}`}>
            <span>{artifact.type || copy("结果", "Result")}</span>
            {href ? <a href={href}>{traceLabel(path)}</a> : <strong>{path || copy("内联内容", "Inline content")}</strong>}
          </li>
        );
      })}
    </ul>
  );
}

function QualityDetails({ lang, payload, warnings }: { lang: Lang; payload: WebPayload; warnings: WarningItem[] }) {
  const copy = (zh: string, en: string) => (lang === "zh" ? zh : en);
  return (
    <div className="quality-detail-grid">
      <div className="run-hqs-card detailed">
        <span>{copy("回答质量", "Response quality")}</span>
        <strong>{formatScore(scoreNumber(payload.hqs))}</strong>
        <ScoreBar score={scoreNumber(payload.hqs)} />
      </div>
      <div className="run-hqs-card detailed">
        <span>{copy("系统质量", "System quality")}</span>
        <strong>{formatScore(scoreNumber(payload.system_hqs))}</strong>
        <ScoreBar score={scoreNumber(payload.system_hqs)} />
      </div>
      <div className={warnings.length ? "quality-warning-list active" : "quality-warning-list"}>
        <strong>{copy("复核提示", "Review notes")}</strong>
        {warnings.length ? (
          <ul>
            {warnings.slice(0, 6).map((warning, index) => (
              <li key={`${warning.type || "warning"}-${index}`}>{warning.message || warning.type}</li>
            ))}
          </ul>
        ) : (
          <p>{copy("暂无明显警告。", "No visible warnings.")}</p>
        )}
      </div>
    </div>
  );
}

function ScoreBar({ score }: { score?: number }) {
  const width = typeof score === "number" ? `${Math.max(0, Math.min(100, (score / 5) * 100))}%` : "0%";
  return (
    <div className="scorebar">
      <span style={{ width }} />
    </div>
  );
}

function DeveloperData({ lang, payload }: { lang: Lang; payload: WebPayload | Record<string, never> }) {
  const copy = (zh: string, en: string) => (lang === "zh" ? zh : en);
  return (
    <section className="developer-data">
      <div className="section-heading">
        <h3>{copy("Raw JSON", "Raw JSON")}</h3>
        <span className="badge">{copy("高级", "Advanced")}</span>
      </div>
      <p className="muted-text">{copy("这一区域保留给调试和复盘，主界面不会直接展示原始数据。", "This area is for debugging and review; the main view does not expose raw data.")}</p>
      <pre className="json-block">{JSON.stringify(payload, null, 2)}</pre>
    </section>
  );
}

function qualityBadge(payload: WebPayload, lang: Lang): string {
  const copy = (zh: string, en: string) => (lang === "zh" ? zh : en);
  const scores = [scoreNumber(payload.hqs), scoreNumber(payload.system_hqs)].filter(
    (score): score is number => typeof score === "number"
  );
  if (!scores.length) {
    return copy("待检查", "Pending");
  }
  const average = scores.reduce((sum, score) => sum + score, 0) / scores.length;
  if (average >= 4) {
    return copy("通过", "Passed");
  }
  if (average >= 3) {
    return copy("需复核", "Review");
  }
  return copy("低分", "Low");
}

function humanize(value: unknown): string {
  return String(value || "-")
    .replaceAll("_", " ")
    .replaceAll("-", " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function formatShort(value: unknown): string {
  if (typeof value === "string") {
    return value;
  }
  if (Array.isArray(value)) {
    return value.slice(0, 3).map(formatShort).join(", ");
  }
  if (value && typeof value === "object") {
    return JSON.stringify(value);
  }
  return value === undefined || value === null ? "" : String(value);
}
