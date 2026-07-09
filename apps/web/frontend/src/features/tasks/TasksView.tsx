import { useEffect, useMemo, useState } from "react";
import { getJson, postJson } from "../../api";
import { formatBeijingShort } from "../../datetime";
import type { I18nKey } from "../../i18n";
import type { JsonRecord, RunRecord, TaskTypeRecord } from "../../types";

interface TasksViewProps {
  active: boolean;
  t: (key: I18nKey) => string;
}

export function TasksView({ active, t }: TasksViewProps) {
  const [taskTypes, setTaskTypes] = useState<TaskTypeRecord[]>([]);
  const [selectedTaskType, setSelectedTaskType] = useState("");
  const [recentRuns, setRecentRuns] = useState<RunRecord[]>([]);
  const [requestJson, setRequestJson] = useState("");
  const [taskResult, setTaskResult] = useState<JsonRecord | null>(null);
  const [loading, setLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  const selectedTask = useMemo(
    () => taskTypes.find((task) => task.task_type === selectedTaskType) || taskTypes[0] || null,
    [selectedTaskType, taskTypes]
  );

  async function loadTaskTypes() {
    setLoading(true);
    setError("");
    try {
      const payload = await getJson<{ task_types?: TaskTypeRecord[] }>("/tasks/types");
      const nextTaskTypes = payload.task_types || [];
      setTaskTypes(nextTaskTypes);
      setSelectedTaskType((current) =>
        current && nextTaskTypes.some((task) => task.task_type === current) ? current : nextTaskTypes[0]?.task_type || ""
      );
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : String(loadError));
    } finally {
      setLoading(false);
    }
  }

  async function loadRecentRuns(taskType = selectedTask?.task_type || "") {
    if (!taskType) {
      setRecentRuns([]);
      return;
    }
    try {
      const payload = await getJson<{ runs?: RunRecord[] }>(`/runs?limit=20&task_type=${encodeURIComponent(taskType)}`);
      setRecentRuns(payload.runs || []);
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : String(loadError));
    }
  }

  async function submitTask() {
    if (!selectedTask) {
      return;
    }
    setSubmitting(true);
    setError("");
    try {
      const payload = JSON.parse(requestJson || "{}") as JsonRecord;
      const request = {
        ...payload,
        task_type: typeof payload.task_type === "string" && payload.task_type ? payload.task_type : selectedTask.task_type
      };
      const result = await postJson<JsonRecord>("/tasks", request);
      setTaskResult(result);
      await loadRecentRuns(selectedTask.task_type);
    } catch (submitError) {
      setError(submitError instanceof SyntaxError ? t("invalidJson") : submitError instanceof Error ? submitError.message : String(submitError));
    } finally {
      setSubmitting(false);
    }
  }

  useEffect(() => {
    if (active) {
      void loadTaskTypes();
    }
  }, [active]);

  useEffect(() => {
    if (!selectedTask) {
      return;
    }
    setRequestJson(JSON.stringify(defaultTaskRequest(selectedTask.task_type), null, 2));
    if (active) {
      void loadRecentRuns(selectedTask.task_type);
    }
  }, [active, selectedTask?.task_type]);

  return (
    <section className={active ? "catalog-workbench active" : "catalog-workbench"}>
      <div className="runs-head">
        <div>
          <h2>{t("tasks")}</h2>
          <p>{t("tasksSubtitle")}</p>
        </div>
        <button className="secondary" type="button" onClick={() => void loadTaskTypes()}>
          {loading ? t("loading") : t("refresh")}
        </button>
      </div>

      {error ? <div className="inline-error">{error}</div> : null}

      <div className="catalog-layout">
        <div className="catalog-list" aria-label={t("tasks")}>
          {taskTypes.length ? (
            taskTypes.map((task) => (
              <button
                className={task.task_type === selectedTask?.task_type ? "catalog-row active" : "catalog-row"}
                key={task.task_type}
                type="button"
                onClick={() => setSelectedTaskType(task.task_type)}
              >
                <strong>{task.title || task.task_type}</strong>
                <span>{task.task_type}</span>
                <small>{task.stable === false ? t("experimental") : t("stable")}</small>
              </button>
            ))
          ) : (
            <div className="runs-empty">{loading ? t("loading") : t("noTaskTypes")}</div>
          )}
        </div>

        <section className="catalog-detail workbench-detail">
          {selectedTask ? (
            <>
              <div className="section-heading">
                <h3>{selectedTask.title || selectedTask.task_type}</h3>
                <span className="badge">{selectedTask.task_type}</span>
              </div>
              <p className="muted-text">{selectedTask.description}</p>

              <div className="schema-grid">
                <SchemaPanel title={t("inputSchema")} schema={recordValue(selectedTask.input_schema)} />
                <SchemaPanel title={t("optionsSchema")} schema={recordValue(selectedTask.options_schema)} />
              </div>

              <section className="run-section nested-section">
                <div className="section-heading">
                  <h3>{t("requestJson")}</h3>
                  <button className="secondary" type="button" disabled={submitting} onClick={() => void submitTask()}>
                    {submitting ? t("running") : t("runTask")}
                  </button>
                </div>
                <textarea
                  className="json-editor"
                  value={requestJson}
                  spellCheck={false}
                  onChange={(event) => setRequestJson(event.target.value)}
                />
              </section>

              {taskResult ? (
                <section className="run-section nested-section">
                  <div className="section-heading">
                    <h3>{t("taskResult")}</h3>
                    <span className="badge">{String(taskResult.status || t("unknown"))}</span>
                  </div>
                  <pre className="result-json">{JSON.stringify(taskResult, null, 2)}</pre>
                </section>
              ) : null}

              <RecentRuns runs={recentRuns} t={t} />
            </>
          ) : (
            <p className="muted-text">{t("noTaskTypes")}</p>
          )}
        </section>
      </div>
    </section>
  );
}

function RecentRuns({ runs, t }: { runs: RunRecord[]; t: (key: I18nKey) => string }) {
  return (
    <section className="run-section nested-section">
      <div className="section-heading">
        <h3>{t("recentRuns")}</h3>
        <span className="badge">{runs.length}</span>
      </div>
      {runs.length ? (
        <ul className="run-chip-list">
          {runs.map((run) => (
            <li key={run.run_id}>
              <strong>{run.title || run.task_type}</strong>
              <span>
                {run.status} · {formatBeijingShort(run.created_at)}
              </span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="muted-text">{t("noRuns")}</p>
      )}
    </section>
  );
}

function SchemaPanel({ title, schema }: { title: string; schema: JsonRecord | null }) {
  return (
    <section className="schema-panel">
      <h4>{title}</h4>
      <pre>{JSON.stringify(schema || {}, null, 2)}</pre>
    </section>
  );
}

function defaultTaskRequest(taskType: string): JsonRecord {
  return {
    task_type: taskType,
    input: {},
    options: {}
  };
}

function recordValue(value: unknown): JsonRecord | null {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return null;
  }
  return value as JsonRecord;
}
