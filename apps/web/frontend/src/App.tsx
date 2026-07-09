import { useCallback, useEffect, useState, type ReactNode } from "react";
import { apiUrl, getJson, postJson } from "./api";
import { AgentPage, collectWarnings } from "./features/agent/AgentPage";
import { ObservationDrawer, type ObservationPanelKey } from "./features/observability/ObservationDrawer";
import { RunsView } from "./features/runs/RunsView";
import { SettingsView } from "./features/settings/SettingsView";
import { SkillsView } from "./features/skills/SkillsView";
import { translate, type I18nKey } from "./i18n";
import type {
  AgentMode,
  Lang,
  ProgressState,
  RunRecord,
  SummaryState,
  TabKey,
  UploadedFileRecord,
  WebPayload
} from "./types";
import { formatSkill, objectValue, scoreNumber, stringValue, timelineForPayload } from "./view-model";

const defaultSummary: SummaryState = {
  intent: "-",
  plan: "-",
  skill: "-",
  warnings: [],
  artifacts: [],
  timeline: []
};

type PrimaryTab = Extract<TabKey, "agent" | "skills" | "settings" | "runs">;

export function App() {
  const [lang, setLang] = useState<Lang>(() => {
    const stored = localStorage.getItem("agentforge_lang");
    return stored === "en" || stored === "zh" ? stored : "zh";
  });
  const t = useCallback((key: I18nKey) => translate(lang, key), [lang]);
  const copy = useCallback((zh: string, en: string) => (lang === "zh" ? zh : en), [lang]);

  const [activeTab, setActiveTab] = useState<PrimaryTab>("agent");
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [detailsOpen, setDetailsOpen] = useState(false);
  const [activeObservationPanel, setActiveObservationPanel] = useState<ObservationPanelKey>("current");

  const [sidebarRuns, setSidebarRuns] = useState<RunRecord[]>([]);
  const [sidebarRunsLoading, setSidebarRunsLoading] = useState(false);
  const [selectedSidebarRunId, setSelectedSidebarRunId] = useState("");
  const useProvider = true;
  const [agentMode, setAgentMode] = useState<AgentMode>("harness_workflow");
  const [message, setMessage] = useState("帮我检查最近一次运行记录：哪里失败了、为什么会失败、下一步怎么修。");
  const [uploads, setUploads] = useState<UploadedFileRecord[]>([]);

  const [runningAction, setRunningAction] = useState<string | null>(null);
  const [progress, setProgress] = useState<ProgressState | null>(null);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const [lastPayload, setLastPayload] = useState<WebPayload | null>(null);
  const [debugPayload, setDebugPayload] = useState<WebPayload | Record<string, never>>({});
  const [summary, setSummary] = useState<SummaryState>(defaultSummary);
  const [error, setError] = useState("");
  const [runsRefreshKey, setRunsRefreshKey] = useState(0);

  useEffect(() => {
    document.documentElement.lang = lang === "zh" ? "zh-CN" : "en";
    localStorage.setItem("agentforge_lang", lang);
  }, [lang]);

  useEffect(() => {
    void loadSidebarRuns();
  }, [runsRefreshKey]);

  useEffect(() => {
    if (!progress) {
      return;
    }
    const update = () => setElapsedSeconds(Math.max(0, Math.floor((Date.now() - progress.startedAt) / 1000)));
    update();
    const timer = window.setInterval(update, 1000);
    return () => window.clearInterval(timer);
  }, [progress]);

  async function loadSidebarRuns() {
    setSidebarRunsLoading(true);
    try {
      const payload = await getJson<{ runs?: RunRecord[] }>("/runs?limit=40");
      const nextRuns = payload.runs || [];
      setSidebarRuns(nextRuns);
      setSelectedSidebarRunId((current) =>
        current && nextRuns.some((run) => run.run_id === current) ? current : nextRuns[0]?.run_id || ""
      );
    } catch {
      setSidebarRuns([]);
    } finally {
      setSidebarRunsLoading(false);
    }
  }

  async function runChat() {
    const trimmed = message.trim();
    if (!trimmed && !uploads.length) {
      setError(copy("请输入要执行的任务，或先上传一个文件。", "Enter a task or upload a file first."));
      return;
    }
    const messageToRun = appendUploadedFilesToMessage(
      trimmed || uploadOnlyPrompt(uploads, lang),
      uploads,
      lang
    );

    setRunningAction("chat");
    setError("");
    setProgress({ phases: phasesForMode(agentMode, copy), startedAt: Date.now() });
    try {
      const payload = await postJson<WebPayload>("/chat", {
        message: messageToRun,
        use_provider: useProvider,
        agent_mode: agentMode,
        uploads
      });
      renderChatPayload(payload);
      setUploads([]);
      setRunsRefreshKey((value) => value + 1);
      setActiveObservationPanel("current");
    } catch (chatError) {
      const messageText = chatError instanceof Error ? chatError.message : String(chatError);
      setError(errorMessageForRun(messageText, useProvider, copy));
      setDebugPayload({ status: "error", message: messageText });
    } finally {
      setProgress(null);
      setRunningAction(null);
    }
  }

  function renderChatPayload(payload: WebPayload) {
    const selectedSkill = payload.selected_skill || objectValue(objectValue(payload.execution)?.selected_skill);
    const warnings = collectWarnings(payload);
    setLastPayload(payload);
    setDebugPayload(payload);
    setError("");
    setSummary({
      responseScore: scoreNumber(payload.hqs),
      systemScore: scoreNumber(payload.system_hqs),
      intent: stringValue(payload.intent?.task_type) || stringValue(payload.intent?.type) || "-",
      plan: stringValue(payload.plan?.action) || "-",
      skill: formatSkill(selectedSkill),
      traceUrl: apiUrl(payload.trace_url),
      traceLabel: payload.trace_file || payload.trace_path,
      warnings,
      artifacts: payload.artifacts || [],
      timeline: timelineForPayload(payload)
    });
  }

  function handleLanguageToggle() {
    setLang((current) => (current === "zh" ? "en" : "zh"));
  }

  function openDetails(panel: ObservationPanelKey = "current") {
    setActiveObservationPanel(panel);
    setDetailsOpen(true);
  }

  function openRecords(runId?: string) {
    if (runId) {
      setSelectedSidebarRunId(runId);
    }
    setActiveTab("runs");
    setDetailsOpen(false);
  }

  return (
    <div className={sidebarCollapsed ? "app-shell sidebar-collapsed" : "app-shell"}>
      <AppSidebar
        activeTab={activeTab}
        collapsed={sidebarCollapsed}
        lang={lang}
        loadingRuns={sidebarRunsLoading}
        runs={sidebarRuns}
        selectedRunId={selectedSidebarRunId}
        t={t}
        copy={copy}
        onCollapse={() => setSidebarCollapsed((value) => !value)}
        onOpenRecords={openRecords}
        onRefreshRuns={() => void loadSidebarRuns()}
        onTab={(tab) => {
          setActiveTab(tab);
          setDetailsOpen(false);
        }}
      />

      <div className="app-frame">
        <header className="topbar product-topbar">
          <div className="page-heading">
            <span className="eyebrow">{copy("本地优先 · 可观察 · 可控", "Local-first · Observable · Controllable")}</span>
            <h1>{pageTitle(activeTab, t)}</h1>
          </div>

          <div className="topbar-actions">
            <button className="secondary" type="button" onClick={() => openDetails("current")}>
              {copy("高级观察", "Advanced")}
            </button>
            <button className="secondary" type="button" onClick={handleLanguageToggle}>
              {lang === "zh" ? "English" : "中文"}
            </button>
          </div>
        </header>

        <main className="app-main">
          {activeTab === "agent" ? (
            <ProgressPanel>
              <AgentPage
                lang={lang}
                t={t}
                message={message}
                agentMode={agentMode}
                running={runningAction === "chat"}
                progress={progress}
                elapsedSeconds={elapsedSeconds}
                payload={lastPayload}
                error={error}
                uploads={uploads}
                onMessage={setMessage}
                onUploads={(files) => setUploads((current) => mergeUploads(current, files))}
                onRemoveUpload={(uploadId) => setUploads((current) => current.filter((file) => file.upload_id !== uploadId))}
                onAgentMode={setAgentMode}
                onSubmit={() => void runChat()}
                onOpenDetails={() => openRecords(lastPayload?.run_id)}
              />
            </ProgressPanel>
          ) : activeTab === "skills" ? (
            <SkillsView active t={t} />
          ) : activeTab === "settings" ? (
            <SettingsView
              active
              t={t}
              agentMode={agentMode}
              onAgentMode={setAgentMode}
            />
          ) : (
            <RunsView
              active
              refreshKey={runsRefreshKey}
              selectedRunId={selectedSidebarRunId}
              t={t}
              onSelectedRunId={setSelectedSidebarRunId}
            />
          )}
        </main>
      </div>

      <ObservationDrawer
        open={detailsOpen}
        activePanel={activeObservationPanel}
        lang={lang}
        t={t}
        currentPayload={lastPayload}
        debugPayload={debugPayload}
        summary={summary}
        onPanel={setActiveObservationPanel}
        onClose={() => setDetailsOpen(false)}
      />
    </div>
  );
}

function AppSidebar({
  activeTab,
  collapsed,
  copy,
  lang,
  loadingRuns,
  runs,
  selectedRunId,
  t,
  onCollapse,
  onOpenRecords,
  onRefreshRuns,
  onTab
}: {
  activeTab: PrimaryTab;
  collapsed: boolean;
  copy: (zh: string, en: string) => string;
  lang: Lang;
  loadingRuns: boolean;
  runs: RunRecord[];
  selectedRunId: string;
  t: (key: I18nKey) => string;
  onCollapse: () => void;
  onOpenRecords: (runId?: string) => void;
  onRefreshRuns: () => void;
  onTab: (tab: PrimaryTab) => void;
}) {
  const navItems: Array<{ key: PrimaryTab; label: string; short: string }> = [
    { key: "agent", label: "Agent", short: "A" },
    { key: "skills", label: t("skills"), short: lang === "zh" ? "技" : "S" },
    { key: "settings", label: t("settings"), short: lang === "zh" ? "设" : "C" }
  ];

  return (
    <aside className={collapsed ? "app-sidebar collapsed" : "app-sidebar"} aria-label={copy("工作台侧边栏", "Workbench sidebar")}>
      <div className="sidebar-brand">
        <div className="brand-mark" aria-hidden="true">
          AF
        </div>
        <div className="sidebar-brand-text">
          <strong>AgentForge</strong>
        </div>
        <button className="sidebar-collapse" type="button" onClick={onCollapse} aria-label={collapsed ? copy("展开侧边栏", "Expand sidebar") : copy("收起侧边栏", "Collapse sidebar")}>
          {collapsed ? "›" : "‹"}
        </button>
      </div>

      <nav className="sidebar-nav" aria-label={copy("页面切换", "Page navigation")}>
        {navItems.map((item) => (
          <button
            className={activeTab === item.key ? "sidebar-nav-item active" : "sidebar-nav-item"}
            key={item.key}
            type="button"
            onClick={() => onTab(item.key)}
            title={item.label}
          >
            <span className="sidebar-nav-icon">{item.short}</span>
            <span className="sidebar-label">{item.label}</span>
          </button>
        ))}
      </nav>

      <section className="sidebar-runs" aria-label={copy("最近运行", "Recent runs")}>
        <div className="sidebar-section-head">
          <span>{copy("任务运行记录", "Run history")}</span>
          <button type="button" onClick={onRefreshRuns} title={t("refresh")}>
            {loadingRuns ? "..." : "↻"}
          </button>
        </div>
        <div className="sidebar-run-list">
          {runs.length ? (
            runs.map((run) => (
              <button
                className={run.run_id === selectedRunId ? "sidebar-run active" : "sidebar-run"}
                key={run.run_id}
                type="button"
                title={`${formatSidebarRunTitle(run, lang)} · ${runTypeLabel(run.task_type, lang)}`}
                onClick={() => onOpenRecords(run.run_id)}
              >
                <span className={`status-dot ${run.status}`} />
                <span>
                  <strong>{formatSidebarRunTitle(run, lang)}</strong>
                  <small>{runTypeLabel(run.task_type, lang)}</small>
                </span>
              </button>
            ))
          ) : (
            <div className="sidebar-empty">{loadingRuns ? t("loading") : t("noRuns")}</div>
          )}
        </div>
      </section>
    </aside>
  );
}

function NavButton({ active, label, onClick }: { active: boolean; label: string; onClick: () => void }) {
  return (
    <button className={active ? "top-nav active" : "top-nav"} type="button" onClick={onClick}>
      {label}
    </button>
  );
}

function ProgressPanel({ children }: { children: ReactNode }) {
  return <>{children}</>;
}

function pageTitle(activeTab: PrimaryTab, t: (key: I18nKey) => string): string {
  if (activeTab === "skills") return t("skills");
  if (activeTab === "settings") return t("settings");
  if (activeTab === "runs") return t("runs");
  return "Agent";
}

function formatSidebarRunTitle(run: RunRecord, lang: Lang): string {
  const title = run.title?.trim();
  return title || runTypeLabel(run.task_type, lang);
}

function runTypeLabel(taskType: string, lang: Lang): string {
  const labels: Record<string, { zh: string; en: string }> = {
    agent_chat: { zh: "Agent 对话", en: "Agent chat" },
    code_analysis: { zh: "代码分析", en: "Code analysis" },
    data_analysis: { zh: "数据分析", en: "Data analysis" },
    doc_analysis: { zh: "文档分析", en: "Document analysis" },
    hqs_diagnosis: { zh: "质量诊断", en: "Quality diagnosis" },
    memory_update: { zh: "记忆更新", en: "Memory update" },
    skill_generate: { zh: "生成 Skill", en: "Generate Skill" },
    skill_run: { zh: "运行 Skill", en: "Run Skill" },
    skill_evolution: { zh: "进化 Skill", en: "Evolve Skill" },
    tool_calling_agent: { zh: "自主 Agent", en: "Autonomous Agent" },
    trace_diagnosis: { zh: "运行诊断", en: "Run diagnosis" }
  };
  const label = labels[taskType];
  if (label) {
    return lang === "zh" ? label.zh : label.en;
  }
  return taskType.replace(/_/g, " ");
}

function phasesForMode(agentMode: AgentMode, copy: (zh: string, en: string) => string): string[] {
  if (agentMode === "tool_calling") {
    return [
      copy("模型决定下一步", "Model chooses next step"),
      copy("检查工具请求", "Validate tool request"),
      copy("执行能力", "Execute capability"),
      copy("整理最终回答", "Compose final answer"),
      copy("保存运行记录", "Save run record")
    ];
  }
  return [
    copy("理解需求", "Understand request"),
    copy("匹配任务与资料", "Match task and context"),
    copy("按流程执行", "Run workflow"),
    copy("检查质量", "Check quality"),
    copy("保存运行记录", "Save run record")
  ];
}

function mergeUploads(current: UploadedFileRecord[], incoming: UploadedFileRecord[]): UploadedFileRecord[] {
  const seen = new Set(current.map((file) => file.upload_id));
  return [...current, ...incoming.filter((file) => !seen.has(file.upload_id))];
}

function uploadOnlyPrompt(uploads: UploadedFileRecord[], lang: Lang): string {
  const kinds = new Set(uploads.map((file) => file.kind));
  if (kinds.has("data")) {
    return lang === "zh" ? "请分析我上传的数据文件。" : "Analyze the uploaded data file.";
  }
  if (kinds.has("code")) {
    return lang === "zh" ? "请检查我上传的代码文件。" : "Review the uploaded code file.";
  }
  if (kinds.has("document")) {
    return lang === "zh" ? "请阅读并分析我上传的文档。" : "Read and analyze the uploaded document.";
  }
  if (kinds.has("image")) {
    return lang === "zh" ? "请根据我上传的图片文件和文件名做初步分析。" : "Analyze the uploaded image file and filename.";
  }
  return lang === "zh" ? "请分析我上传的文件。" : "Analyze the uploaded file.";
}

function appendUploadedFilesToMessage(message: string, uploads: UploadedFileRecord[], lang: Lang): string {
  if (!uploads.length) {
    return message;
  }
  const heading = lang === "zh" ? "上传文件：" : "Uploaded files:";
  const lines = uploads.map((file) => `- ${file.original_name}: ${file.relative_path}`);
  return `${message}\n\n${heading}\n${lines.join("\n")}`;
}

function errorMessageForRun(raw: string, useProvider: boolean, copy: (zh: string, en: string) => string): string {
  if (useProvider && /provider|api key|config|timeout/i.test(raw)) {
    return `${copy("模型调用阶段失败。", "The model call stage failed.")}${raw} ${copy(
      "你可以重试，或切换本地模式后继续。",
      "You can retry, or switch to local mode and continue."
    )}`;
  }
  return `${copy("运行阶段失败。", "The run failed.")}${raw}`;
}
