import { useEffect, useState } from "react";
import { getJson } from "../../api";
import type { I18nKey } from "../../i18n";
import type { AgentMode, ConfigStatusRecord, HealthStatusRecord, ProviderSummaryRecord } from "../../types";

interface SettingsViewProps {
  active: boolean;
  t: (key: I18nKey) => string;
  useProvider: boolean;
  agentMode: AgentMode;
  onUseProvider: (value: boolean) => void;
  onAgentMode: (value: AgentMode) => void;
}

export function SettingsView({
  active,
  t,
  useProvider,
  agentMode,
  onUseProvider,
  onAgentMode
}: SettingsViewProps) {
  const [health, setHealth] = useState<HealthStatusRecord | null>(null);
  const [config, setConfig] = useState<ConfigStatusRecord | null>(null);
  const [version, setVersion] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function loadSettings() {
    setLoading(true);
    setError("");
    try {
      const [healthPayload, configPayload, versionPayload] = await Promise.all([
        getJson<HealthStatusRecord>("/health"),
        getJson<ConfigStatusRecord>("/config"),
        getJson<Record<string, unknown>>("/version")
      ]);
      setHealth(healthPayload);
      setConfig(configPayload);
      setVersion(versionPayload);
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : String(loadError));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (active) {
      void loadSettings();
    }
  }, [active]);

  return (
    <section className={active ? "settings-workbench active" : "settings-workbench"}>
      <div className="runs-head">
        <div>
          <h2>{t("settings")}</h2>
          <p>{t("settingsSubtitle")}</p>
        </div>
        <button className="secondary" type="button" onClick={() => void loadSettings()}>
          {loading ? t("loading") : t("refresh")}
        </button>
      </div>

      {error ? <div className="inline-error">{error}</div> : null}

      <div className="settings-workbench-grid">
        <section className="settings-section primary-settings">
          <div className="section-heading">
            <h3>{t("runMode")}</h3>
            <span className="badge">{agentMode}</span>
          </div>
          <label className="toggle mode-toggle">
            <input checked={useProvider} type="checkbox" onChange={(event) => onUseProvider(event.target.checked)} />
            <span>{t("useProvider")}</span>
          </label>
          <label className="mode-select">
            <span>{t("agentMode")}</span>
            <select value={agentMode} onChange={(event) => onAgentMode(event.target.value as AgentMode)}>
              <option value="harness_workflow">{t("harnessWorkflow")}</option>
              <option value="tool_calling">{t("toolCallingAgent")}</option>
            </select>
          </label>
          <dl className="run-kv compact">
            <dt>{t("runtime")}</dt>
            <dd>{health?.status || "-"}</dd>
            <dt>{t("versionLabel")}</dt>
            <dd>{String(version?.version || "-")}</dd>
            <dt>{t("projectRoot")}</dt>
            <dd>{String(version?.project_root || config?.project_root || "-")}</dd>
          </dl>
        </section>

        <section className="settings-section">
          <div className="section-heading">
            <h3>{t("providerConfig")}</h3>
            <span className="badge">{config?.default_provider || "-"}</span>
          </div>
          <dl className="run-kv compact">
            <dt>{t("pathLabel")}</dt>
            <dd>{config?.provider_config_path || "-"}</dd>
            <dt>{t("status")}</dt>
            <dd>{config?.provider_config_exists ? t("available") : t("unavailable")}</dd>
            <dt>{t("selectedProvider")}</dt>
            <dd>{String(config?.selected_provider?.provider || config?.default_provider || "-")}</dd>
          </dl>
          <ProviderList providers={config?.providers || []} t={t} />
        </section>

        <section className="settings-section">
          <div className="section-heading">
            <h3>{t("directories")}</h3>
            <span className="badge">{health?.directories?.length || 0}</span>
          </div>
          <ul className="directory-list">
            {(health?.directories || []).map((directory) => (
              <li key={directory.path}>
                <strong>{directory.path}</strong>
                <span className={directory.exists && directory.writable ? "status-ok" : "status-warn"}>
                  {directory.exists ? t("available") : t("missing")} · {directory.writable ? t("writable") : t("readonly")}
                </span>
              </li>
            ))}
          </ul>
        </section>

        <section className="settings-section">
          <div className="section-heading">
            <h3>{t("apiLinks")}</h3>
            <span className="badge">API</span>
          </div>
          <div className="api-link-grid">
            {["/api/health", "/api/config", "/api/runs", "/api/tasks/types", "/api/tools", "/api/traces", "/api/hqs"].map((href) => (
              <a href={href} key={href}>
                {href}
              </a>
            ))}
          </div>
        </section>
      </div>
    </section>
  );
}

function ProviderList({ providers, t }: { providers: ProviderSummaryRecord[]; t: (key: I18nKey) => string }) {
  if (!providers.length) {
    return <p className="muted-text">{t("none")}</p>;
  }
  return (
    <div className="provider-grid">
      {providers.map((provider) => (
        <article key={provider.name || provider.model || "provider"}>
          <div>
            <strong>{provider.name || "-"}</strong>
            <span>{provider.model || "-"}</span>
          </div>
          <dl>
            <dt>{t("type")}</dt>
            <dd>{provider.type || "-"}</dd>
            <dt>{t("timeout")}</dt>
            <dd>{provider.timeout_seconds ? `${provider.timeout_seconds}s` : "-"}</dd>
            <dt>{t("apiKey")}</dt>
            <dd>{provider.has_api_key ? t("available") : t("missing")}</dd>
          </dl>
        </article>
      ))}
    </div>
  );
}
