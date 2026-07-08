import { useEffect, useMemo, useState } from "react";
import { getJson } from "../../api";
import type { I18nKey } from "../../i18n";
import type { HqsStatusRecord, JsonRecord, RunDetailRecord, RunRecord, ScoreReport } from "../../types";
import { formatScore } from "../../view-model";

interface HqsViewProps {
  active: boolean;
  t: (key: I18nKey) => string;
}

export function HqsView({ active, t }: HqsViewProps) {
  const [hqsStatus, setHqsStatus] = useState<HqsStatusRecord | null>(null);
  const [runs, setRuns] = useState<RunRecord[]>([]);
  const [selectedRunId, setSelectedRunId] = useState("");
  const [runDetail, setRunDetail] = useState<RunDetailRecord | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const selectedRun = useMemo(() => runs.find((run) => run.run_id === selectedRunId) || runs[0] || null, [runs, selectedRunId]);

  async function loadHqs() {
    setLoading(true);
    setError("");
    try {
      const [hqsPayload, runsPayload] = await Promise.all([
        getJson<HqsStatusRecord>("/hqs"),
        getJson<{ runs?: RunRecord[] }>("/runs?limit=100")
      ]);
      const nextRuns = runsPayload.runs || [];
      setHqsStatus(hqsPayload);
      setRuns(nextRuns);
      setSelectedRunId((current) => (current && nextRuns.some((run) => run.run_id === current) ? current : nextRuns[0]?.run_id || ""));
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : String(loadError));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (active) {
      void loadHqs();
    }
  }, [active]);

  useEffect(() => {
    let cancelled = false;
    async function loadRunDetail() {
      if (!selectedRunId) {
        setRunDetail(null);
        return;
      }
      try {
        const detail = await getJson<RunDetailRecord>(`/runs/${encodeURIComponent(selectedRunId)}`);
        if (!cancelled) {
          setRunDetail(detail);
        }
      } catch (loadError) {
        if (!cancelled) {
          setRunDetail(null);
          setError(loadError instanceof Error ? loadError.message : String(loadError));
        }
      }
    }
    if (active) {
      void loadRunDetail();
    }
    return () => {
      cancelled = true;
    };
  }, [active, selectedRunId]);

  return (
    <section className={active ? "catalog-workbench active" : "catalog-workbench"}>
      <div className="runs-head">
        <div>
          <h2>{t("hqs")}</h2>
          <p>{t("hqsSubtitle")}</p>
        </div>
        <button className="secondary" type="button" onClick={() => void loadHqs()}>
          {loading ? t("loading") : t("refresh")}
        </button>
      </div>

      {error ? <div className="inline-error">{error}</div> : null}

      <div className="catalog-layout">
        <div className="catalog-list" aria-label={t("runs")}>
          {runs.length ? (
            runs.map((run) => (
              <button
                className={run.run_id === selectedRun?.run_id ? "catalog-row active" : "catalog-row"}
                key={run.run_id}
                type="button"
                onClick={() => setSelectedRunId(run.run_id)}
              >
                <strong>{run.title || run.task_type}</strong>
                <span>{run.task_type}</span>
                <small>{run.status}</small>
              </button>
            ))
          ) : (
            <div className="runs-empty">{loading ? t("loading") : t("noRuns")}</div>
          )}
        </div>

        <section className="catalog-detail workbench-detail">
          <div className="hqs-status-grid">
            <ScoreReportPanel title={t("currentSystemHqs")} report={hqsStatus?.current_system_hqs} t={t} />
            <ScoreReportPanel title={t("lastResponseHqs")} report={hqsStatus?.last_response_hqs} t={t} />
            <ScoreReportPanel title={t("lastSystemHqs")} report={hqsStatus?.last_system_hqs} t={t} />
          </div>

          <section className="run-section nested-section">
            <div className="section-heading">
              <h3>{t("selectedRunHqs")}</h3>
              <span className="badge">{runDetail?.hqs_reports?.length || 0}</span>
            </div>
            {runDetail?.hqs_reports?.length ? (
              <div className="run-hqs-grid observation-hqs-grid">
                {runDetail.hqs_reports.map((report) => (
                  <div className="run-hqs-card detailed" key={report.hqs_id}>
                    <span>{report.scope}</span>
                    <strong>{formatScore(report.average_score)}</strong>
                    <div className="scorebar">
                      <span style={{ width: scoreWidth(report.average_score) }} />
                    </div>
                    <DimensionList report={report.report} t={t} />
                  </div>
                ))}
              </div>
            ) : (
              <p className="muted-text">{t("noHqsReports")}</p>
            )}
          </section>
        </section>
      </div>
    </section>
  );
}

function ScoreReportPanel({ title, report, t }: { title: string; report: ScoreReport | undefined; t: (key: I18nKey) => string }) {
  const score = typeof report?.average_score === "number" ? report.average_score : undefined;
  return (
    <section className="hqs-status-panel">
      <div className="section-heading">
        <h3>{title}</h3>
        <span className="badge">{formatScore(score)}</span>
      </div>
      <div className="scorebar">
        <span style={{ width: typeof score === "number" ? scoreWidth(score) : "0%" }} />
      </div>
      <DimensionList report={report} t={t} />
    </section>
  );
}

function DimensionList({ report, t }: { report: ScoreReport | undefined; t: (key: I18nKey) => string }) {
  const dimensions = scoreEntries(report);
  if (!dimensions.length) {
    return <p className="muted-text">{t("noDimensions")}</p>;
  }
  return (
    <div className="dimension-list compact">
      {dimensions.map(([name, score]) => (
        <div className="dimension" key={name}>
          <span>{name}</span>
          <strong>{formatScore(score)}</strong>
          <div className="scorebar">
            <span style={{ width: scoreWidth(score) }} />
          </div>
        </div>
      ))}
    </div>
  );
}

function scoreEntries(report: ScoreReport | undefined): Array<[string, number]> {
  const scores = recordValue(report?.scores);
  if (!scores) {
    return [];
  }
  return Object.entries(scores)
    .filter((entry): entry is [string, number] => typeof entry[1] === "number" && Number.isFinite(entry[1]))
    .slice(0, 8);
}

function scoreWidth(score: number): string {
  return `${Math.max(0, Math.min(100, (score / 5) * 100))}%`;
}

function recordValue(value: unknown): JsonRecord | null {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return null;
  }
  return value as JsonRecord;
}
