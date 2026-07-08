import { useEffect, useMemo, useState } from "react";
import { getJson } from "../../api";
import type { I18nKey } from "../../i18n";
import type { JsonRecord, ToolRecord } from "../../types";

interface ToolsViewProps {
  active: boolean;
  t: (key: I18nKey) => string;
}

export function ToolsView({ active, t }: ToolsViewProps) {
  const [tools, setTools] = useState<ToolRecord[]>([]);
  const [selectedToolName, setSelectedToolName] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const selectedTool = useMemo(
    () => tools.find((tool) => tool.name === selectedToolName) || tools[0] || null,
    [selectedToolName, tools]
  );

  const loadTools = async () => {
    setLoading(true);
    setError("");
    try {
      const payload = await getJson<{ tools?: ToolRecord[] }>("/tools");
      const nextTools = payload.tools || [];
      setTools(nextTools);
      setSelectedToolName((current) => (nextTools.some((tool) => tool.name === current) ? current : nextTools[0]?.name || ""));
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (active) {
      void loadTools();
    }
  }, [active]);

  return (
    <section className={active ? "catalog-workbench active" : "catalog-workbench"}>
      <div className="runs-head">
        <div>
          <h2>{t("tools")}</h2>
          <p>{t("toolsSubtitle")}</p>
        </div>
        <button className="secondary" type="button" onClick={() => void loadTools()}>
          {loading ? t("loading") : t("refresh")}
        </button>
      </div>

      {error ? <div className="inline-error">{error}</div> : null}

      <div className="catalog-layout">
        <div className="catalog-list" aria-label={t("tools")}>
          {tools.length ? (
            tools.map((tool) => (
              <button
                className={tool.name === selectedTool?.name ? "catalog-row active" : "catalog-row"}
                key={tool.name}
                type="button"
                onClick={() => setSelectedToolName(tool.name)}
              >
                <strong>{tool.name}</strong>
                <span>{tool.kind}</span>
                <small>{tool.permission_level || "-"}</small>
              </button>
            ))
          ) : (
            <div className="runs-empty">{loading ? t("loading") : t("noTools")}</div>
          )}
        </div>

        <ToolDetail tool={selectedTool} t={t} />
      </div>
    </section>
  );
}

function ToolDetail({ tool, t }: { tool: ToolRecord | null; t: (key: I18nKey) => string }) {
  if (!tool) {
    return (
      <section className="catalog-detail">
        <p className="muted-text">{t("noTools")}</p>
      </section>
    );
  }

  return (
    <section className="catalog-detail">
      <div className="section-heading">
        <h3>{tool.name}</h3>
        <span className="badge">{tool.kind}</span>
      </div>
      <p className="muted-text">{tool.description || "-"}</p>

      <dl className="run-meta compact">
        <dt>{t("permission")}</dt>
        <dd>{tool.permission_level || "-"}</dd>
        <dt>{t("timeout")}</dt>
        <dd>{tool.timeout_seconds ? `${tool.timeout_seconds}s` : "-"}</dd>
        <dt>{t("idempotent")}</dt>
        <dd>{tool.idempotent ? t("yes") : t("no")}</dd>
        <dt>{t("sideEffects")}</dt>
        <dd>{tool.side_effects ? t("yes") : t("no")}</dd>
      </dl>

      <div className="schema-grid">
        <SchemaPanel title={t("inputSchema")} schema={recordValue(tool.input_schema)} />
        <SchemaPanel title={t("outputSchema")} schema={recordValue(tool.output_schema)} />
      </div>

      <section className="run-section nested-section">
        <div className="section-heading">
          <h3>{t("errorSpecs")}</h3>
          <span className="badge">{Array.isArray(tool.error_specs) ? tool.error_specs.length : 0}</span>
        </div>
        {Array.isArray(tool.error_specs) && tool.error_specs.length ? (
          <ul className="run-chip-list">
            {tool.error_specs.map((item, index) => {
              const spec = recordValue(item) || {};
              return (
                <li key={`${String(spec.error_type || "error")}-${index}`}>
                  <strong>{String(spec.error_type || "-")}</strong>
                  <span>{String(spec.user_message || spec.description || "-")}</span>
                </li>
              );
            })}
          </ul>
        ) : (
          <p className="muted-text">{t("none")}</p>
        )}
      </section>
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

function recordValue(value: unknown): JsonRecord | null {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return null;
  }
  return value as JsonRecord;
}
