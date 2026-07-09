import { useEffect, useMemo, useState } from "react";
import { apiUrl, getJson } from "../../api";
import { formatBeijingDateTime, formatBeijingShort } from "../../datetime";
import type { I18nKey } from "../../i18n";
import type { RunDetailRecord, RunRecord } from "../../types";
import { traceLabel } from "../../view-model";
import { RunObservationPanel } from "../observability/RunObservationPanel";

interface RunsViewProps {
  active: boolean;
  refreshKey: number;
  selectedRunId?: string;
  t: (key: I18nKey) => string;
  onSelectedRunId?: (runId: string) => void;
}

export function RunsView({ active, refreshKey, selectedRunId: externalSelectedRunId, t, onSelectedRunId }: RunsViewProps) {
  const [runs, setRuns] = useState<RunRecord[]>([]);
  const [internalSelectedRunId, setInternalSelectedRunId] = useState("");
  const [detail, setDetail] = useState<RunDetailRecord | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const selectedRunId = externalSelectedRunId || internalSelectedRunId;

  const selectedRun = useMemo(
    () => (detail?.run_id === selectedRunId ? detail : runs.find((run) => run.run_id === selectedRunId) || null),
    [detail, runs, selectedRunId]
  );

  async function loadRuns() {
    setLoading(true);
    setError("");
    try {
      const payload = await getJson<{ runs?: RunRecord[] }>("/runs?limit=100");
      const nextRuns = payload.runs || [];
      setRuns(nextRuns);
      setInternalSelectedRunId((current) => {
        if (current && nextRuns.some((run) => run.run_id === current)) {
          return current;
        }
        const fallback = externalSelectedRunId && nextRuns.some((run) => run.run_id === externalSelectedRunId)
          ? externalSelectedRunId
          : nextRuns[0]?.run_id || "";
        if (fallback && fallback !== externalSelectedRunId) {
          onSelectedRunId?.(fallback);
        }
        return fallback;
      });
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : String(loadError));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (active) {
      void loadRuns();
    }
  }, [active, refreshKey]);

  useEffect(() => {
    if (!active) {
      return;
    }
    const timer = window.setInterval(() => {
      void loadRuns();
    }, 5000);
    return () => window.clearInterval(timer);
  }, [active]);

  useEffect(() => {
    let cancelled = false;
    async function loadDetail() {
      if (!selectedRunId) {
        setDetail(null);
        return;
      }
      try {
        const payload = await getJson<RunDetailRecord>(`/runs/${encodeURIComponent(selectedRunId)}`);
        if (!cancelled) {
          setDetail(payload);
        }
      } catch (loadError) {
        if (!cancelled) {
          setDetail(null);
          setError(loadError instanceof Error ? loadError.message : String(loadError));
        }
      }
    }
    if (active) {
      void loadDetail();
    }
    return () => {
      cancelled = true;
    };
  }, [active, selectedRunId, refreshKey, runs]);

  function selectRun(runId: string) {
    setInternalSelectedRunId(runId);
    onSelectedRunId?.(runId);
  }

  return (
    <section className={active ? "runs-workbench active" : "runs-workbench"}>
      <div className="runs-head">
        <div>
          <h2>{t("runs")}</h2>
          <p>{t("runsSubtitle")}</p>
        </div>
        <button className="secondary" type="button" onClick={() => void loadRuns()}>
          {loading ? t("loading") : t("refresh")}
        </button>
      </div>

      {error ? <p className="status-error">{error}</p> : null}

      <div className="runs-layout">
        <div className="runs-list" aria-label={t("runs")}>
          {runs.length ? (
            runs.map((run) => (
              <button
                className={run.run_id === selectedRunId ? "run-row active" : "run-row"}
                key={run.run_id}
                type="button"
                  onClick={() => selectRun(run.run_id)}
              >
                <span className={`status-dot ${run.status}`} />
                <span>
                  <strong>{run.title || run.task_type}</strong>
                  <small>
                    {run.task_type} · {formatBeijingShort(run.created_at)}
                  </small>
                </span>
                <em>{run.status}</em>
              </button>
            ))
          ) : (
            <div className="runs-empty">{loading ? t("loading") : t("noRuns")}</div>
          )}
        </div>

        <RunDetail run={selectedRun as RunDetailRecord | null} t={t} />
      </div>
    </section>
  );
}

function RunDetail({ run, t }: { run: RunDetailRecord | null; t: (key: I18nKey) => string }) {
  if (!run) {
    return (
      <article className="run-detail-surface empty">
        <p>{t("noRuns")}</p>
      </article>
    );
  }
  const traceUrl = run.trace_path ? apiUrl(`/traces/${encodeURIComponent(traceLabel(run.trace_path))}`) : undefined;
  return (
    <article className="run-detail-surface">
      <div className="run-detail-head">
        <div>
          <span className={`badge run-status ${run.status}`}>{run.status}</span>
          <h3>{run.title || run.task_type}</h3>
          <p>{run.run_id}</p>
        </div>
        {traceUrl ? <a href={traceUrl}>{t("trace")}</a> : null}
      </div>

      <dl className="run-kv">
        <dt>{t("taskType")}</dt>
        <dd>{run.task_type}</dd>
        <dt>{t("created")}</dt>
        <dd>{formatBeijingDateTime(run.created_at)}</dd>
        <dt>{t("updated")}</dt>
        <dd>{formatBeijingDateTime(run.updated_at)}</dd>
        <dt>{t("completed")}</dt>
        <dd>{formatBeijingDateTime(run.completed_at)}</dd>
      </dl>

      <RunObservationPanel run={run} t={t} />

      {run.output ? (
        <details className="run-json">
          <summary>{t("output")}</summary>
          <pre>{JSON.stringify(run.output, null, 2)}</pre>
        </details>
      ) : null}
    </article>
  );
}
