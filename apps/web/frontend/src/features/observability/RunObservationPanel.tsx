import { useEffect, useMemo, useState } from "react";
import { apiUrl, getJson } from "../../api";
import { formatBeijingDateTime } from "../../datetime";
import type { I18nKey } from "../../i18n";
import type {
  JsonRecord,
  RunArtifactRecord,
  RunDetailRecord,
  RunHqsRecord,
  RunStepRecord,
  RunToolCallRecord,
  RunWorkflowCheckpointRecord,
  ScoreReport,
  TraceDetailRecord
} from "../../types";
import { formatMetadataValue, formatScore, traceLabel } from "../../view-model";
import { ObservationMetricGrid, ObservationSection } from "./ObservationPrimitives";

type CodeSeverity = "high" | "medium" | "low" | "info" | "unknown";

interface CodeAnalysisFinding {
  severity: CodeSeverity;
  source: string;
  line: number | null;
  rule: string;
  message: string;
  recommendation: string;
}

interface CodeAnalysisViewModel {
  summary: JsonRecord;
  findings: CodeAnalysisFinding[];
  limitations: string[];
  sources: JsonRecord[];
}

export function RunObservationPanel({ run, t }: { run: RunDetailRecord; t: (key: I18nKey) => string }) {
  const traceFile = run.trace_path ? traceLabel(run.trace_path) : "";
  const [trace, setTrace] = useState<TraceDetailRecord | null>(null);
  const [traceError, setTraceError] = useState("");
  const [traceLoading, setTraceLoading] = useState(false);

  useEffect(() => {
    let cancelled = false;
    async function loadTrace() {
      if (!traceFile) {
        setTrace(null);
        setTraceError("");
        return;
      }
      setTraceLoading(true);
      setTraceError("");
      try {
        const payload = await getJson<TraceDetailRecord>(`/traces/${encodeURIComponent(traceFile)}`);
        if (!cancelled) {
          setTrace(payload);
        }
      } catch (error) {
        if (!cancelled) {
          setTrace(null);
          setTraceError(error instanceof Error ? error.message : String(error));
        }
      } finally {
        if (!cancelled) {
          setTraceLoading(false);
        }
      }
    }
    void loadTrace();
    return () => {
      cancelled = true;
    };
  }, [traceFile]);

  const summary = useMemo(
    () => [
      { label: t("hqs"), value: String(run.hqs_reports?.length || 0), tone: "score" },
      { label: t("toolCalls"), value: String(run.tool_calls?.length || 0), tone: "tool" },
      { label: t("artifacts"), value: String(run.artifacts?.length || 0), tone: "artifact" },
      { label: t("trace"), value: traceFile || "-", tone: "trace" }
    ],
    [run.artifacts?.length, run.hqs_reports?.length, run.tool_calls?.length, t, traceFile]
  );

  return (
    <section className="observation-panel">
      <div className="section-heading">
        <h3>{t("observation")}</h3>
        <span className="badge">{run.status}</span>
      </div>
      <ObservationMetricGrid items={summary} />

      <RunTracePreview trace={trace} traceError={traceError} traceFile={traceFile} loading={traceLoading} t={t} />
      <RunHqs reports={run.hqs_reports || []} t={t} />
      <RunCodeAnalysis run={run} t={t} />
      <RunToolCalls toolCalls={run.tool_calls || []} t={t} />
      <RunArtifacts artifacts={run.artifacts || []} t={t} />
      <RunWorkflowCheckpoints checkpoints={run.workflow_checkpoints || []} t={t} />
      <RunSteps steps={run.steps || []} t={t} />
    </section>
  );
}

function RunTracePreview({
  trace,
  traceError,
  traceFile,
  loading,
  t
}: {
  trace: TraceDetailRecord | null;
  traceError: string;
  traceFile: string;
  loading: boolean;
  t: (key: I18nKey) => string;
}) {
  const steps = arrayValue(trace?.steps);
  const errors = arrayValue(trace?.errors);
  const artifacts = arrayValue(trace?.artifacts);
  const traceUrl = traceFile ? apiUrl(`/traces/${encodeURIComponent(traceFile)}`) : undefined;

  return (
    <ObservationSection
      action={traceUrl ? <a href={traceUrl}>{traceFile}</a> : <span className="badge muted">{t("none")}</span>}
      className="run-section observation-section"
      title={t("trace")}
    >
      {traceError ? <div className="inline-error compact">{traceError}</div> : null}
      {!traceFile ? <p className="muted-text">{t("noTrace")}</p> : null}
      {traceFile && loading ? <p className="muted-text">{t("loading")}</p> : null}
      {trace ? (
        <>
          <dl className="run-kv compact">
            <dt>{t("type")}</dt>
            <dd>{trace.type || "-"}</dd>
            <dt>{t("traceId")}</dt>
            <dd>{trace.trace_id || "-"}</dd>
            <dt>{t("created")}</dt>
            <dd>{formatBeijingDateTime(trace.created_at)}</dd>
            <dt>{t("steps")}</dt>
            <dd>{steps.length}</dd>
            <dt>{t("errors")}</dt>
            <dd>{errors.length}</dd>
            <dt>{t("artifacts")}</dt>
            <dd>{artifacts.length}</dd>
          </dl>
          {steps.length ? <TraceStepList steps={steps} t={t} /> : null}
          {errors.length ? (
            <ul className="run-chip-list error-list">
              {errors.slice(0, 5).map((error, index) => (
                <li key={`trace-error-${index}`}>
                  <strong>{t("errors")}</strong>
                  <span>{formatMetadataValue(error)}</span>
                </li>
              ))}
            </ul>
          ) : null}
          <details className="run-json compact">
            <summary>{t("rawTrace")}</summary>
            <pre>{JSON.stringify(trace, null, 2)}</pre>
          </details>
        </>
      ) : null}
    </ObservationSection>
  );
}

function TraceStepList({ steps, t }: { steps: unknown[]; t: (key: I18nKey) => string }) {
  return (
    <ol className="run-step-list trace-step-list">
      {steps.slice(0, 8).map((item, index) => {
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
  );
}

function RunHqs({ reports, t }: { reports: RunHqsRecord[]; t: (key: I18nKey) => string }) {
  return (
    <ObservationSection badge={String(reports.length)} className="run-section observation-section" title={t("hqs")}>
      {reports.length ? (
        <div className="run-hqs-grid observation-hqs-grid">
          {reports.map((report) => (
            <HqsReportCard key={report.hqs_id} report={report} t={t} />
          ))}
        </div>
      ) : (
        <p className="muted-text">{t("noHqsReports")}</p>
      )}
    </ObservationSection>
  );
}

function HqsReportCard({ report, t }: { report: RunHqsRecord; t: (key: I18nKey) => string }) {
  const dimensions = scoreEntries(report.report);
  return (
    <div className="run-hqs-card detailed">
      <span>{report.scope}</span>
      <strong>{formatScore(report.average_score)}</strong>
      <div className="scorebar">
        <span style={{ width: scoreWidth(report.average_score) }} />
      </div>
      {dimensions.length ? (
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
      ) : (
        <small>{t("noDimensions")}</small>
      )}
    </div>
  );
}

function RunCodeAnalysis({ run, t }: { run: RunDetailRecord; t: (key: I18nKey) => string }) {
  const analysis = codeAnalysisViewModel(run);
  if (!analysis) {
    return null;
  }
  const groupedFindings = groupFindingsBySeverity(analysis.findings);
  const summary = analysis.summary;
  const findingCount = numericField(summary, "finding_count");
  const sourceCount = numericField(summary, "source_count");
  const lineCount = numericField(summary, "line_count");

  return (
    <ObservationSection
      badge={String(findingCount)}
      className="run-section code-analysis-panel observation-section"
      title={t("codeAnalysis")}
    >

      <div className="code-analysis-summary">
        <Metric label={t("sources")} value={String(sourceCount)} />
        <Metric label={t("lines")} value={String(lineCount)} />
        <Metric label={t("high")} value={String(numericField(summary, "high_count"))} tone="high" />
        <Metric label={t("medium")} value={String(numericField(summary, "medium_count"))} tone="medium" />
        <Metric label={t("low")} value={String(numericField(summary, "low_count"))} tone="low" />
      </div>

      {analysis.sources.length ? (
        <ul className="code-source-list" aria-label={t("sources")}>
          {analysis.sources.slice(0, 6).map((source, index) => (
            <li key={`${stringField(source, "path") || stringField(source, "name") || "source"}-${index}`}>
              <strong>{stringField(source, "path") || stringField(source, "name") || t("source")}</strong>
              <span>
                {stringField(source, "language") || t("unknown")} · {numericField(source, "line_count")} {t("lines")}
              </span>
            </li>
          ))}
        </ul>
      ) : null}

      {analysis.findings.length ? (
        <div className="finding-groups">
          {groupedFindings.map((group) => (
            <section className={`finding-group ${group.severity}`} key={group.severity}>
              <div className="finding-group-head">
                <h4>{severityLabel(group.severity, t)}</h4>
                <span className={`badge severity ${group.severity}`}>{group.items.length}</span>
              </div>
              <ul className="finding-list">
                {group.items.map((finding, index) => (
                  <li key={`${finding.rule}-${finding.source}-${finding.line ?? "n"}-${index}`}>
                    <div className="finding-title">
                      <strong>{finding.message || finding.rule}</strong>
                      <span>{finding.rule}</span>
                    </div>
                    <dl className="finding-meta">
                      <dt>{t("source")}</dt>
                      <dd>
                        {finding.source || "-"}
                        {finding.line ? `:${finding.line}` : ""}
                      </dd>
                      <dt>{t("recommendation")}</dt>
                      <dd>{finding.recommendation || "-"}</dd>
                    </dl>
                  </li>
                ))}
              </ul>
            </section>
          ))}
        </div>
      ) : (
        <p className="muted-text">{t("noFindings")}</p>
      )}

      {analysis.limitations.length ? (
        <div className="code-limitations">
          <strong>{t("limitations")}</strong>
          <ul>
            {analysis.limitations.map((item, index) => (
              <li key={`${item}-${index}`}>{item}</li>
            ))}
          </ul>
        </div>
      ) : null}
    </ObservationSection>
  );
}

function Metric({ label, value, tone }: { label: string; value: string; tone?: CodeSeverity }) {
  return (
    <div className={tone ? `code-metric ${tone}` : "code-metric"}>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function RunToolCalls({ toolCalls, t }: { toolCalls: RunToolCallRecord[]; t: (key: I18nKey) => string }) {
  return (
    <ObservationSection badge={String(toolCalls.length)} className="run-section observation-section" title={t("toolCalls")}>
      {toolCalls.length ? (
        <ol className="tool-call-list">
          {toolCalls.map((call) => (
            <li className={call.status} key={call.tool_call_id}>
              <div className="tool-call-row-head">
                <span className={`status-dot ${call.status}`} />
                <strong>{call.tool_name}</strong>
                <em>{call.status}</em>
              </div>
              <small>
                {formatBeijingDateTime(call.started_at)}
                {call.completed_at ? ` · ${formatBeijingDateTime(call.completed_at)}` : ""}
              </small>
              <div className="tool-call-details">
                <DetailJson title={t("toolArguments")} value={call.arguments} />
                <DetailJson title={t("observation")} value={call.result} />
                <DetailJson title={t("errors")} value={call.error} open={Boolean(call.error)} />
              </div>
            </li>
          ))}
        </ol>
      ) : (
        <p className="muted-text">{t("none")}</p>
      )}
    </ObservationSection>
  );
}

function RunArtifacts({ artifacts, t }: { artifacts: RunArtifactRecord[]; t: (key: I18nKey) => string }) {
  return (
    <ObservationSection badge={String(artifacts.length)} className="run-section observation-section" title={t("artifacts")}>
      {artifacts.length ? (
        <ul className="artifact-list">
          {artifacts.map((artifact) => (
            <li key={artifact.artifact_id}>
              <div>
                <strong>{artifact.type}</strong>
                <span>{artifact.path || "-"}</span>
              </div>
              <small>{artifact.content_type || formatBeijingDateTime(artifact.created_at)}</small>
              <DetailJson title={t("schema")} value={artifact.metadata} />
            </li>
          ))}
        </ul>
      ) : (
        <p className="muted-text">{t("none")}</p>
      )}
    </ObservationSection>
  );
}

function RunWorkflowCheckpoints({
  checkpoints,
  t
}: {
  checkpoints: RunWorkflowCheckpointRecord[];
  t: (key: I18nKey) => string;
}) {
  const compactCheckpoints = checkpoints.slice(-12);
  return (
    <ObservationSection
      badge={String(checkpoints.length)}
      className="run-section observation-section"
      title={t("workflowCheckpoints")}
    >
      {compactCheckpoints.length ? (
        <ol className="run-checkpoint-list">
          {compactCheckpoints.map((checkpoint) => {
            const state = checkpoint.state || {};
            const status = typeof state.status === "string" ? state.status : "running";
            const currentStep = typeof state.current_step === "string" ? state.current_step : checkpoint.step_name || "-";
            return (
              <li className={status} key={checkpoint.checkpoint_id}>
                <span className={`status-dot ${status}`} />
                <div>
                  <strong>{checkpoint.step_name || checkpoint.workflow_id}</strong>
                  <small>
                    {checkpoint.workflow_id} · {status}
                  </small>
                  <span className="checkpoint-meta">
                    {t("currentStep")}: {currentStep}
                  </span>
                  <time>{formatBeijingDateTime(checkpoint.created_at)}</time>
                </div>
              </li>
            );
          })}
        </ol>
      ) : (
        <p className="muted-text">{t("none")}</p>
      )}
      {checkpoints.length > compactCheckpoints.length ? (
        <p className="muted-text">
          {checkpoints.length - compactCheckpoints.length} {t("earlierCheckpointsHidden")}
        </p>
      ) : null}
    </ObservationSection>
  );
}

function RunSteps({ steps, t }: { steps: RunStepRecord[]; t: (key: I18nKey) => string }) {
  return (
    <ObservationSection badge={String(steps.length)} className="run-section observation-section" title={t("steps")}>
      <ol className="run-step-list">
        {steps.length ? (
          steps.map((step) => (
            <li className={step.status} key={step.step_id}>
              <span className={`status-dot ${step.status}`} />
              <div>
                <strong>{step.name}</strong>
                <small>
                  {step.kind} · {step.status}
                </small>
              </div>
            </li>
          ))
        ) : (
          <li>{t("timelineEmpty")}</li>
        )}
      </ol>
    </ObservationSection>
  );
}

function DetailJson({ title, value, open = false }: { title: string; value: unknown; open?: boolean }) {
  if (isEmptyValue(value)) {
    return null;
  }
  return (
    <details className="tool-call-detail" open={open}>
      <summary>{title}</summary>
      <pre className="json-block">{typeof value === "string" ? value : JSON.stringify(value, null, 2)}</pre>
    </details>
  );
}

function codeAnalysisViewModel(run: RunDetailRecord): CodeAnalysisViewModel | null {
  if (run.task_type !== "code_analysis") {
    return null;
  }
  const output = recordValue(run.output);
  if (!output) {
    return null;
  }
  const analysis = recordValue(output.analysis);
  if (!analysis) {
    return null;
  }
  const summary = recordValue(analysis.summary) || {};
  const rawFindings = arrayValue(analysis.findings);
  const findings = rawFindings.map(normalizeFinding).filter((finding): finding is CodeAnalysisFinding => finding !== null);
  const limitations = arrayValue(analysis.limitations)
    .map((item) => (typeof item === "string" ? item : ""))
    .filter(Boolean);
  const sources = arrayValue(analysis.sources || output.sources)
    .map(recordValue)
    .filter((source): source is JsonRecord => source !== null);
  return { summary, findings, limitations, sources };
}

function normalizeFinding(value: unknown): CodeAnalysisFinding | null {
  const finding = recordValue(value);
  if (!finding) {
    return null;
  }
  return {
    severity: normalizeSeverity(stringField(finding, "severity")),
    source: stringField(finding, "source"),
    line: nullableNumberField(finding, "line"),
    rule: stringField(finding, "rule"),
    message: stringField(finding, "message"),
    recommendation: stringField(finding, "recommendation")
  };
}

function groupFindingsBySeverity(findings: CodeAnalysisFinding[]) {
  const order: CodeSeverity[] = ["high", "medium", "low", "info", "unknown"];
  return order
    .map((severity) => ({
      severity,
      items: findings.filter((finding) => finding.severity === severity)
    }))
    .filter((group) => group.items.length > 0);
}

function severityLabel(severity: CodeSeverity, t: (key: I18nKey) => string): string {
  if (severity === "high") {
    return t("high");
  }
  if (severity === "medium") {
    return t("medium");
  }
  if (severity === "low") {
    return t("low");
  }
  if (severity === "info") {
    return t("info");
  }
  return t("unknown");
}

function normalizeSeverity(value: string): CodeSeverity {
  const normalized = value.toLowerCase();
  if (normalized === "high" || normalized === "medium" || normalized === "low" || normalized === "info") {
    return normalized;
  }
  return "unknown";
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

function arrayValue(value: unknown): unknown[] {
  return Array.isArray(value) ? value : [];
}

function stringField(record: JsonRecord, key: string): string {
  const value = record[key];
  return typeof value === "string" ? value : "";
}

function numericField(record: JsonRecord, key: string): number {
  const value = record[key];
  return typeof value === "number" && Number.isFinite(value) ? value : 0;
}

function nullableNumberField(record: JsonRecord, key: string): number | null {
  const value = record[key];
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function isEmptyValue(value: unknown): boolean {
  if (value === undefined || value === null || value === "") {
    return true;
  }
  return typeof value === "object" && !Array.isArray(value) && Object.keys(value).length === 0;
}
