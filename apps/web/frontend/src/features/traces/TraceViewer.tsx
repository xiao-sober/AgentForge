import { useEffect, useMemo, useState } from "react";
import { getJson, postJson } from "../../api";
import type { I18nKey } from "../../i18n";
import type { JsonRecord, TraceDetailRecord, TraceSummaryRecord } from "../../types";
import { formatMetadataValue } from "../../view-model";

interface TraceViewerProps {
  active: boolean;
  t: (key: I18nKey) => string;
}

export function TraceViewer({ active, t }: TraceViewerProps) {
  const [traces, setTraces] = useState<TraceSummaryRecord[]>([]);
  const [selectedTraceFile, setSelectedTraceFile] = useState("");
  const [traceDetail, setTraceDetail] = useState<TraceDetailRecord | null>(null);
  const [diagnosis, setDiagnosis] = useState<JsonRecord | null>(null);
  const [loading, setLoading] = useState(false);
  const [diagnosing, setDiagnosing] = useState(false);
  const [error, setError] = useState("");

  const selectedTrace = useMemo(
    () => traces.find((trace) => trace.filename === selectedTraceFile) || traces[0] || null,
    [selectedTraceFile, traces]
  );

  async function loadTraces() {
    setLoading(true);
    setError("");
    try {
      const payload = await getJson<{ traces?: TraceSummaryRecord[] }>("/traces");
      const nextTraces = payload.traces || [];
      setTraces(nextTraces);
      setSelectedTraceFile((current) =>
        current && nextTraces.some((trace) => trace.filename === current) ? current : nextTraces[0]?.filename || ""
      );
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : String(loadError));
    } finally {
      setLoading(false);
    }
  }

  async function diagnoseTrace() {
    if (!selectedTrace) {
      return;
    }
    setDiagnosing(true);
    setError("");
    try {
      const result = await postJson<JsonRecord>("/tasks", {
        task_type: "trace_diagnosis",
        input: { trace_file: selectedTrace.filename }
      });
      setDiagnosis(result);
    } catch (diagnosisError) {
      setError(diagnosisError instanceof Error ? diagnosisError.message : String(diagnosisError));
    } finally {
      setDiagnosing(false);
    }
  }

  useEffect(() => {
    if (active) {
      void loadTraces();
    }
  }, [active]);

  useEffect(() => {
    let cancelled = false;
    async function loadTraceDetail() {
      if (!selectedTraceFile) {
        setTraceDetail(null);
        setDiagnosis(null);
        return;
      }
      try {
        const payload = await getJson<TraceDetailRecord>(`/traces/${encodeURIComponent(selectedTraceFile)}`);
        if (!cancelled) {
          setTraceDetail(payload);
          setDiagnosis(null);
        }
      } catch (loadError) {
        if (!cancelled) {
          setTraceDetail(null);
          setError(loadError instanceof Error ? loadError.message : String(loadError));
        }
      }
    }
    if (active) {
      void loadTraceDetail();
    }
    return () => {
      cancelled = true;
    };
  }, [active, selectedTraceFile]);

  return (
    <section className={active ? "catalog-workbench active" : "catalog-workbench"}>
      <div className="runs-head">
        <div>
          <h2>{t("traceViewer")}</h2>
          <p>{t("traceViewerSubtitle")}</p>
        </div>
        <button className="secondary" type="button" onClick={() => void loadTraces()}>
          {loading ? t("loading") : t("refresh")}
        </button>
      </div>

      {error ? <div className="inline-error">{error}</div> : null}

      <div className="catalog-layout">
        <div className="catalog-list" aria-label={t("traceViewer")}>
          {traces.length ? (
            traces.map((trace) => (
              <button
                className={trace.filename === selectedTrace?.filename ? "catalog-row active" : "catalog-row"}
                key={trace.filename}
                type="button"
                onClick={() => setSelectedTraceFile(trace.filename)}
              >
                <strong>{trace.filename}</strong>
                <span>{trace.type || trace.error || t("unknown")}</span>
                <small>{trace.created_at || "-"}</small>
              </button>
            ))
          ) : (
            <div className="runs-empty">{loading ? t("loading") : t("noTraces")}</div>
          )}
        </div>

        <section className="catalog-detail workbench-detail">
          {selectedTrace ? (
            <>
              <div className="section-heading">
                <h3>{selectedTrace.filename}</h3>
                <button className="secondary" type="button" disabled={diagnosing} onClick={() => void diagnoseTrace()}>
                  {diagnosing ? t("running") : t("diagnoseTrace")}
                </button>
              </div>
              <TraceMetadata trace={selectedTrace} detail={traceDetail} t={t} />
              <TraceStructure trace={traceDetail} t={t} />
              {diagnosis ? (
                <section className="run-section nested-section">
                  <div className="section-heading">
                    <h3>{t("diagnosis")}</h3>
                    <span className="badge">{String(diagnosis.status || t("unknown"))}</span>
                  </div>
                  <pre className="result-json">{JSON.stringify(diagnosis, null, 2)}</pre>
                </section>
              ) : null}
              {traceDetail ? (
                <details className="run-json">
                  <summary>{t("rawTrace")}</summary>
                  <pre>{JSON.stringify(traceDetail, null, 2)}</pre>
                </details>
              ) : null}
            </>
          ) : (
            <p className="muted-text">{t("noTraces")}</p>
          )}
        </section>
      </div>
    </section>
  );
}

function TraceMetadata({
  trace,
  detail,
  t
}: {
  trace: TraceSummaryRecord;
  detail: TraceDetailRecord | null;
  t: (key: I18nKey) => string;
}) {
  const steps = Array.isArray(detail?.steps) ? detail.steps.length : 0;
  const errors = Array.isArray(detail?.errors) ? detail.errors.length : 0;
  const artifacts = Array.isArray(detail?.artifacts) ? detail.artifacts.length : 0;
  return (
    <dl className="run-kv compact">
      <dt>{t("type")}</dt>
      <dd>{detail?.type || trace.type || "-"}</dd>
      <dt>{t("traceId")}</dt>
      <dd>{detail?.trace_id || trace.trace_id || "-"}</dd>
      <dt>{t("created")}</dt>
      <dd>{detail?.created_at || trace.created_at || "-"}</dd>
      <dt>{t("steps")}</dt>
      <dd>{steps}</dd>
      <dt>{t("errors")}</dt>
      <dd>{errors}</dd>
      <dt>{t("artifacts")}</dt>
      <dd>{artifacts}</dd>
    </dl>
  );
}

function TraceStructure({ trace, t }: { trace: TraceDetailRecord | null; t: (key: I18nKey) => string }) {
  if (!trace) {
    return <p className="muted-text">{t("loading")}</p>;
  }
  const steps = Array.isArray(trace.steps) ? trace.steps : [];
  const errors = Array.isArray(trace.errors) ? trace.errors : [];
  const artifacts = Array.isArray(trace.artifacts) ? trace.artifacts : [];
  return (
    <>
      <section className="run-section nested-section">
        <div className="section-heading">
          <h3>{t("steps")}</h3>
          <span className="badge">{steps.length}</span>
        </div>
        {steps.length ? (
          <ol className="run-step-list trace-step-list">
            {steps.slice(0, 16).map((item, index) => {
              const step = recordValue(item) || {};
              const status = stringField(step, "status") || t("unknown");
              const name = stringField(step, "name") || stringField(step, "step_id") || `${t("step")} ${index + 1}`;
              const kind = stringField(step, "kind") || stringField(step, "type");
              return (
                <li className={status} key={`${name}-${index}`}>
                  <span className={`status-dot ${status}`} />
                  <div>
                    <strong>{name}</strong>
                    <small>
                      {status}
                      {kind ? ` · ${kind}` : ""}
                    </small>
                  </div>
                </li>
              );
            })}
          </ol>
        ) : (
          <p className="muted-text">{t("timelineEmpty")}</p>
        )}
      </section>

      <section className="run-section nested-section">
        <div className="section-heading">
          <h3>{t("errors")}</h3>
          <span className="badge">{errors.length}</span>
        </div>
        {errors.length ? (
          <ul className="run-chip-list error-list">
            {errors.map((error, index) => (
              <li key={`error-${index}`}>
                <strong>{t("errors")}</strong>
                <span>{formatMetadataValue(error)}</span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="muted-text">{t("none")}</p>
        )}
      </section>

      <section className="run-section nested-section">
        <div className="section-heading">
          <h3>{t("artifacts")}</h3>
          <span className="badge">{artifacts.length}</span>
        </div>
        {artifacts.length ? (
          <ul className="run-chip-list">
            {artifacts.map((artifact, index) => {
              const record = recordValue(artifact) || {};
              return (
                <li key={`artifact-${index}`}>
                  <strong>{stringField(record, "type") || t("artifact")}</strong>
                  <span>{stringField(record, "path") || stringField(record, "relative_path") || formatMetadataValue(artifact)}</span>
                </li>
              );
            })}
          </ul>
        ) : (
          <p className="muted-text">{t("none")}</p>
        )}
      </section>
    </>
  );
}

function recordValue(value: unknown): JsonRecord | null {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return null;
  }
  return value as JsonRecord;
}

function stringField(record: JsonRecord, key: string): string {
  const value = record[key];
  return typeof value === "string" ? value : "";
}
