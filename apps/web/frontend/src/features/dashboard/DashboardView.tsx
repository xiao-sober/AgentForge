import { useEffect, useMemo, useState } from "react";
import { getJson } from "../../api";
import { formatBeijingDateTime, formatBeijingShort } from "../../datetime";
import type { I18nKey } from "../../i18n";
import type {
  HqsStatusRecord,
  MemoryEpisodeRecord,
  RunDetailRecord,
  RunRecord,
  SemanticMemoryRecord,
  SkillSummary,
  TabKey,
  TaskTypeRecord,
  ToolRecord,
  TraceSummaryRecord
} from "../../types";
import { formatScore, scoreNumber, traceLabel } from "../../view-model";

interface DashboardViewProps {
  active: boolean;
  t: (key: I18nKey) => string;
  onNavigate: (tab: TabKey) => void;
}

export function DashboardView({ active, t, onNavigate }: DashboardViewProps) {
  const [healthStatus, setHealthStatus] = useState("-");
  const [runs, setRuns] = useState<RunRecord[]>([]);
  const [latestRunDetail, setLatestRunDetail] = useState<RunDetailRecord | null>(null);
  const [taskTypes, setTaskTypes] = useState<TaskTypeRecord[]>([]);
  const [tools, setTools] = useState<ToolRecord[]>([]);
  const [skills, setSkills] = useState<SkillSummary[]>([]);
  const [episodes, setEpisodes] = useState<MemoryEpisodeRecord[]>([]);
  const [semanticMemory, setSemanticMemory] = useState<SemanticMemoryRecord[]>([]);
  const [traces, setTraces] = useState<TraceSummaryRecord[]>([]);
  const [hqsStatus, setHqsStatus] = useState<HqsStatusRecord | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const latestRun = runs[0] || null;
  const completedRuns = runs.filter((run) => run.status === "completed").length;
  const failedRuns = runs.filter((run) => run.status === "failed").length;
  const activeCheckpoint = useMemo(() => {
    const checkpoints = latestRunDetail?.workflow_checkpoints || [];
    const checkpoint = checkpoints[checkpoints.length - 1];
    if (!checkpoint) {
      return null;
    }
    const state = checkpoint.state || {};
    return {
      name: checkpoint.step_name || checkpoint.workflow_id,
      status: typeof state.status === "string" ? state.status : latestRunDetail?.status || "-",
      currentStep: typeof state.current_step === "string" ? state.current_step : checkpoint.step_name || "-",
      createdAt: checkpoint.created_at
    };
  }, [latestRunDetail]);

  async function loadDashboard() {
    setLoading(true);
    setError("");
    try {
      const [health, runPayload, taskPayload, skillPayload, toolPayload, episodePayload, semanticPayload, tracePayload, hqsPayload] =
        await Promise.all([
          getJson<{ status?: string }>("/health"),
          getJson<{ runs?: RunRecord[] }>("/runs?limit=8"),
          getJson<{ task_types?: TaskTypeRecord[] }>("/tasks/types"),
          getJson<{ skills?: SkillSummary[] }>("/skills"),
          getJson<{ tools?: ToolRecord[] }>("/tools"),
          getJson<{ episodes?: MemoryEpisodeRecord[] }>("/memory/episodes?limit=4"),
          getJson<{ semantic_memory?: SemanticMemoryRecord[] }>("/memory/semantic?limit=4"),
          getJson<{ traces?: TraceSummaryRecord[] }>("/traces"),
          getJson<HqsStatusRecord>("/hqs")
        ]);
      const nextRuns = runPayload.runs || [];
      setHealthStatus(health.status || "-");
      setRuns(nextRuns);
      setTaskTypes(taskPayload.task_types || []);
      setSkills(skillPayload.skills || []);
      setTools(toolPayload.tools || []);
      setEpisodes(episodePayload.episodes || []);
      setSemanticMemory(semanticPayload.semantic_memory || []);
      setTraces(tracePayload.traces || []);
      setHqsStatus(hqsPayload);
      if (nextRuns[0]) {
        const detail = await getJson<RunDetailRecord>(`/runs/${encodeURIComponent(nextRuns[0].run_id)}`);
        setLatestRunDetail(detail);
      } else {
        setLatestRunDetail(null);
      }
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : String(loadError));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (active) {
      void loadDashboard();
    }
  }, [active]);

  return (
    <section className={active ? "dashboard-workbench active" : "dashboard-workbench"}>
      <div className="dashboard-hero">
        <div>
          <span className="eyebrow">{t("dashboard")}</span>
          <h2>{t("dashboardTitle")}</h2>
          <p>{t("dashboardSubtitle")}</p>
        </div>
        <div className="dashboard-actions">
          <button type="button" onClick={() => onNavigate("chat")}>
            {t("newChat")}
          </button>
          <button className="secondary" type="button" onClick={() => void loadDashboard()}>
            {loading ? t("loading") : t("refresh")}
          </button>
        </div>
      </div>

      {error ? <div className="inline-error compact">{error}</div> : null}

      <div className="dashboard-kpi-grid">
        <KpiCard label={t("health")} value={healthStatus} tone={healthStatus === "ok" ? "success" : "warn"} />
        <KpiCard label={t("runs")} value={String(runs.length)} detail={`${completedRuns} ${t("completed")} · ${failedRuns} ${t("failed")}`} />
        <KpiCard label={t("tools")} value={String(tools.length)} detail={`${taskTypes.length} ${t("tasks")}`} />
        <KpiCard label={t("hqs")} value={formatScore(scoreNumber(hqsStatus?.current_system_hqs))} detail={t("currentSystemHqs")} />
      </div>

      <div className="dashboard-grid">
        <section className="dashboard-card current-run-card">
          <div className="section-heading">
            <h3>{t("currentRun")}</h3>
            <button className="secondary" type="button" onClick={() => onNavigate("runs")}>
              {t("openRuns")}
            </button>
          </div>
          {latestRun ? (
            <>
              <div className="current-run-head">
                <span className={`status-dot ${latestRun.status}`} />
                <div>
                  <strong>{latestRun.title || latestRun.task_type}</strong>
                  <small>{latestRun.run_id}</small>
                </div>
                <em>{latestRun.status}</em>
              </div>
              <dl className="run-kv compact dashboard-kv">
                <dt>{t("taskType")}</dt>
                <dd>{latestRun.task_type}</dd>
                <dt>{t("trace")}</dt>
                <dd>{latestRun.trace_path ? traceLabel(latestRun.trace_path) : "-"}</dd>
                <dt>{t("created")}</dt>
                <dd>{formatBeijingDateTime(latestRun.created_at)}</dd>
                <dt>{t("toolCalls")}</dt>
                <dd>{latestRunDetail?.tool_calls?.length || 0}</dd>
                <dt>{t("artifacts")}</dt>
                <dd>{latestRunDetail?.artifacts?.length || 0}</dd>
                <dt>{t("hqs")}</dt>
                <dd>{latestRunDetail?.hqs_reports?.length || 0}</dd>
              </dl>
              {activeCheckpoint ? (
                <div className="checkpoint-callout">
                  <span className={`status-dot ${activeCheckpoint.status}`} />
                  <div>
                    <strong>{activeCheckpoint.name}</strong>
                    <small>
                      {t("currentStep")}: {activeCheckpoint.currentStep}
                    </small>
                    <time>{formatBeijingDateTime(activeCheckpoint.createdAt)}</time>
                  </div>
                </div>
              ) : (
                <p className="muted-text">{t("noCheckpoint")}</p>
              )}
            </>
          ) : (
            <p className="muted-text">{t("noRuns")}</p>
          )}
        </section>

        <section className="dashboard-card">
          <div className="section-heading">
            <h3>{t("recentRuns")}</h3>
            <button className="secondary" type="button" onClick={() => onNavigate("runs")}>
              {t("open")}
            </button>
          </div>
          <MiniRunList runs={runs} t={t} />
        </section>

        <section className="dashboard-card">
          <div className="section-heading">
            <h3>{t("traceViewer")}</h3>
            <button className="secondary" type="button" onClick={() => onNavigate("traces")}>
              {t("open")}
            </button>
          </div>
          <ul className="run-chip-list">
            {traces.slice(0, 5).map((trace) => (
              <li key={trace.filename}>
                <strong>{trace.type || t("trace")}</strong>
                <span>{trace.filename}</span>
              </li>
            ))}
            {!traces.length ? <li>{t("noTraces")}</li> : null}
          </ul>
        </section>

        <section className="dashboard-card">
          <div className="section-heading">
            <h3>{t("memory")}</h3>
            <button className="secondary" type="button" onClick={() => onNavigate("memory")}>
              {t("open")}
            </button>
          </div>
          <div className="dashboard-memory-grid">
            <MemoryMiniList title={t("latestEpisodes")} items={episodes.map((item) => item.user_input || item.episode_id || t("episode"))} />
            <MemoryMiniList title={t("semanticMemory")} items={semanticMemory.map((item) => item.key || item.summary || t("semantic"))} />
          </div>
        </section>

        <section className="dashboard-card dashboard-card-wide">
          <div className="section-heading">
            <h3>{t("platformSurface")}</h3>
            <span className="badge">{t("phase7CompleteSurface")}</span>
          </div>
          <div className="surface-grid">
            <SurfaceButton label={t("tasks")} count={taskTypes.length} onClick={() => onNavigate("tasks")} />
            <SurfaceButton label={t("skills")} count={skills.length} onClick={() => onNavigate("skills")} />
            <SurfaceButton label={t("tools")} count={tools.length} onClick={() => onNavigate("tools")} />
            <SurfaceButton label={t("hqs")} value={formatScore(scoreNumber(hqsStatus?.current_system_hqs))} onClick={() => onNavigate("hqs")} />
            <SurfaceButton label={t("settings")} value={healthStatus} onClick={() => onNavigate("settings")} />
          </div>
        </section>
      </div>
    </section>
  );
}

function KpiCard({ label, value, detail, tone }: { label: string; value: string; detail?: string; tone?: "success" | "warn" }) {
  return (
    <div className={tone ? `dashboard-kpi ${tone}` : "dashboard-kpi"}>
      <span>{label}</span>
      <strong>{value}</strong>
      {detail ? <small>{detail}</small> : null}
    </div>
  );
}

function MiniRunList({ runs, t }: { runs: RunRecord[]; t: (key: I18nKey) => string }) {
  if (!runs.length) {
    return <p className="muted-text">{t("noRuns")}</p>;
  }
  return (
    <ol className="run-mini-list">
      {runs.slice(0, 6).map((run) => (
        <li className={run.status} key={run.run_id}>
          <span className={`status-dot ${run.status}`} />
          <div>
            <strong>{run.title || run.task_type}</strong>
            <small>
              {run.task_type} · {formatBeijingShort(run.created_at)}
            </small>
          </div>
          <em>{run.status}</em>
        </li>
      ))}
    </ol>
  );
}

function MemoryMiniList({ title, items }: { title: string; items: string[] }) {
  return (
    <div className="memory-mini-list">
      <strong>{title}</strong>
      <ul>
        {items.length ? items.slice(0, 4).map((item) => <li key={item}>{item}</li>) : <li>-</li>}
      </ul>
    </div>
  );
}

function SurfaceButton({
  label,
  count,
  value,
  muted = false,
  onClick
}: {
  label: string;
  count?: number;
  value?: string;
  muted?: boolean;
  onClick: () => void;
}) {
  return (
    <button className={muted ? "surface-button muted" : "surface-button"} type="button" onClick={onClick}>
      <span>{label}</span>
      <strong>{value || String(count ?? "-")}</strong>
    </button>
  );
}
