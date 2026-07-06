import { useCallback, useEffect, useMemo, useState } from "react";
import { apiUrl, getJson, postJson } from "./api";
import { Drilldown } from "./Drilldown";
import { translate, type I18nKey } from "./i18n";
import type {
  AgentMode,
  ArtifactItem,
  DrilldownKey,
  Lang,
  ProgressState,
  SkillSummary,
  SummaryState,
  TabKey,
  TasksetSummary,
  TimelineStep,
  WebPayload
} from "./types";
import {
  escapeHtml,
  formatScore,
  formatSkill,
  isToolCallTimelineStep,
  markdownToHtml,
  objectValue,
  scoreNumber,
  stringValue,
  timelineForPayload,
  toolCallTimelineHtml,
  traceLabel
} from "./view-model";

const defaultSummary: SummaryState = {
  intent: "-",
  plan: "-",
  skill: "-",
  warnings: [],
  artifacts: [],
  timeline: []
};

export function App() {
  const [lang, setLang] = useState<Lang>(() => {
    const stored = localStorage.getItem("agentforge_lang");
    return stored === "en" || stored === "zh" ? stored : "zh";
  });
  const t = useCallback((key: I18nKey) => translate(lang, key), [lang]);

  const [activeTab, setActiveTab] = useState<TabKey>("chat");
  const [activeDrilldown, setActiveDrilldown] = useState<DrilldownKey>("trace");
  const [drilldownStatus, setDrilldownStatus] = useState({ text: t("runIdle"), muted: true });
  const [statusText, setStatusText] = useState(t("statusLoading"));
  const [statusClass, setStatusClass] = useState("");
  const [runtimeValue, setRuntimeValue] = useState("-");
  const [skills, setSkills] = useState<SkillSummary[]>([]);
  const [tasksets, setTasksets] = useState<TasksetSummary[]>([]);
  const [useProvider, setUseProvider] = useState(false);
  const [agentMode, setAgentMode] = useState<AgentMode>("harness_workflow");
  const [chatMessage, setChatMessage] = useState("评审这个后台仪表盘布局的可读性，并给出具体优化建议。");
  const [chatDebug, setChatDebug] = useState(false);
  const [generateInput, setGenerateInput] = useState("生成一个用于后台仪表盘和管理页面的 UI 评审 Skill。");
  const [runInput, setRunInput] = useState("评审一个指标密集、标签对比度偏低、操作按钮不清晰的后台仪表盘。");
  const [runSkillPath, setRunSkillPath] = useState("");
  const [evolveSkillPath, setEvolveSkillPath] = useState("");
  const [evolveTasksetPath, setEvolveTasksetPath] = useState("");
  const [maxIterations, setMaxIterations] = useState(1);
  const [minImprovement, setMinImprovement] = useState(0.01);
  const [runningAction, setRunningAction] = useState<string | null>(null);
  const [progress, setProgress] = useState<ProgressState | null>(null);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const [resultHtml, setResultHtml] = useState(`<p>${escapeHtml(t("emptyResult"))}</p>`);
  const [resultEmpty, setResultEmpty] = useState(true);
  const [ribbonPayload, setRibbonPayload] = useState<WebPayload>({});
  const [summary, setSummary] = useState<SummaryState>(defaultSummary);
  const [lastPayload, setLastPayload] = useState<WebPayload | null>(null);
  const [debugPayload, setDebugPayload] = useState<WebPayload | Record<string, never>>({});

  const modeHint = useMemo(() => {
    const agentLabel = agentMode === "tool_calling" ? t("toolCallingAgent") : t("harnessWorkflow");
    const providerHint = useProvider ? t("providerModeHint") : t("localModeHint");
    return `${providerHint} · ${agentLabel}`;
  }, [agentMode, t, useProvider]);

  const modeValue = useMemo(() => {
    const agentLabel = agentMode === "tool_calling" ? t("toolCallingAgent") : t("harnessWorkflow");
    return `${useProvider ? t("providerMode") : t("localMode")} / ${agentLabel}`;
  }, [agentMode, t, useProvider]);

  useEffect(() => {
    document.documentElement.lang = lang === "zh" ? "zh-CN" : "en";
    localStorage.setItem("agentforge_lang", lang);
    if (!lastPayload) {
      setDrilldownStatus({ text: t("runIdle"), muted: true });
    }
  }, [lang, lastPayload, t]);

  useEffect(() => {
    void loadHealth();
    void loadSkills();
    void loadTasksets();
  }, []);

  useEffect(() => {
    if (!progress) {
      return;
    }
    const update = () => setElapsedSeconds(Math.max(0, Math.floor((Date.now() - progress.startedAt) / 1000)));
    update();
    const timer = window.setInterval(update, 1000);
    return () => window.clearInterval(timer);
  }, [progress]);

  useEffect(() => {
    if (!runSkillPath && skills.length) {
      setRunSkillPath(skills[0].latest_skill_path || "");
    }
    if (!evolveSkillPath && skills.length) {
      setEvolveSkillPath(skills[0].latest_skill_path || "");
    }
  }, [evolveSkillPath, runSkillPath, skills]);

  useEffect(() => {
    if (!evolveTasksetPath && tasksets.length) {
      setEvolveTasksetPath(tasksets[0].relative_path || "");
    }
  }, [evolveTasksetPath, tasksets]);

  async function loadHealth() {
    setStatusText(t("localApiRunning"));
    setRuntimeValue("...");
    try {
      const payload = await getJson<{ status?: string }>("/health");
      const status = payload.status || t("unknown");
      setStatusText(`${t("healthLabel")}: ${status}`);
      setRuntimeValue(status);
      setStatusClass(status === "ok" ? "" : "status-warn");
    } catch {
      setStatusText(`${t("healthLabel")}: ${t("unavailable")}`);
      setRuntimeValue(t("offline"));
      setStatusClass("status-error");
    }
  }

  async function loadSkills(): Promise<SkillSummary[]> {
    const payload = await getJson<{ skills?: SkillSummary[] }>("/skills");
    const nextSkills = payload.skills || [];
    setSkills(nextSkills);
    return nextSkills;
  }

  async function loadTasksets(): Promise<TasksetSummary[]> {
    const payload = await getJson<{ tasksets?: TasksetSummary[] }>("/tasksets");
    const nextTasksets = payload.tasksets || [];
    setTasksets(nextTasksets);
    return nextTasksets;
  }

  function providerPayload() {
    return {
      use_provider: useProvider,
      agent_mode: agentMode
    };
  }

  async function runAction(actionKey: string, phases: string[], action: () => Promise<void>) {
    setRunningAction(actionKey);
    setResultEmpty(false);
    setRibbonPayload({ status: t("running") });
    setProgress({ phases, startedAt: Date.now() });
    try {
      await action();
    } catch (error) {
      renderError(error instanceof Error ? error.message : String(error));
    } finally {
      setProgress(null);
      setRunningAction(null);
    }
  }

  async function runChat() {
    const message = chatMessage.trim();
    if (!message) {
      renderError(t("messageEmpty"));
      return;
    }
    await runAction("chat", [t("stageSubmit"), t("stageModelThinking"), t("stageSkillExecute"), t("stageHqsTrace")], async () => {
      const payload = await postJson<WebPayload>("/chat", {
        message,
        debug: chatDebug,
        ...providerPayload()
      });
      renderChatPayload(payload);
    });
  }

  async function generateSkill() {
    const input = generateInput.trim();
    if (!input) {
      renderError(t("requirementEmpty"));
      return;
    }
    await runAction("generate", [t("stageSubmit"), t("stageModelThinking"), t("stageValidateWrite")], async () => {
      const payload = await postJson<WebPayload>("/skills/generate", {
        input,
        ...providerPayload()
      });
      renderGeneratePayload(payload);
      const nextSkills = await loadSkills();
      const selected = selectSkillPath(nextSkills, payload.skill_path);
      if (selected) {
        setRunSkillPath(selected);
        setEvolveSkillPath(selected);
      }
    });
  }

  async function runSkill() {
    const input = runInput.trim();
    if (!runSkillPath) {
      renderError(t("missingSkills"));
      return;
    }
    if (!input) {
      renderError(t("taskInputEmpty"));
      return;
    }
    await runAction("run", [t("stageSubmit"), t("stageSkillExecute"), t("stageContractTrace")], async () => {
      const payload = await postJson<WebPayload>("/skills/run", {
        skill_path: runSkillPath,
        input,
        ...providerPayload()
      });
      renderRunPayload(payload);
    });
  }

  async function evolveSkill() {
    if (!evolveSkillPath) {
      renderError(t("missingSkills"));
      return;
    }
    if (!evolveTasksetPath) {
      renderError(t("missingTasksets"));
      return;
    }
    await runAction(
      "evolve",
      [t("stageSubmit"), t("stageRunBaseline"), t("stageRewriteCandidate"), t("stageGatePersist")],
      async () => {
        const payload = await postJson<WebPayload>("/skills/evolve", {
          skill_path: evolveSkillPath,
          taskset_path: evolveTasksetPath,
          max_iterations: maxIterations,
          min_improvement: minImprovement,
          ...providerPayload()
        });
        renderEvolvePayload(payload);
        await loadSkills();
      }
    );
  }

  function renderChatPayload(payload: WebPayload) {
    const selectedSkill = payload.selected_skill || objectValue(objectValue(payload.execution)?.selected_skill);
    setLastPayload(payload);
    setRibbonPayload(payload);
    setResultEmpty(false);
    setResultHtml(markdownToHtml(payload.response || t("noResponse")));
    setSummary({
      responseScore: scoreNumber(payload.hqs),
      systemScore: scoreNumber(payload.system_hqs),
      intent: stringValue(payload.intent?.type) || stringValue(payload.intent?.intent_type) || "-",
      plan: stringValue(payload.plan?.action) || "-",
      skill: formatSkill(selectedSkill),
      traceUrl: apiUrl(payload.trace_url),
      traceLabel: payload.trace_file || payload.trace_path,
      warnings: payload.warnings || [],
      artifacts: payload.artifacts || [],
      timeline: timelineForPayload(payload)
    });
    setDebugPayload(payload);
  }

  function renderGeneratePayload(payload: WebPayload) {
    const lines = [
      `# ${t("generated")}`,
      "",
      `- ${t("generatedBody")}`,
      `- Skill: ${payload.skill_name || payload.skill_slug}`,
      `- ${t("versionLabel")}: ${payload.version}`,
      `- ${t("modeLabel")}: ${payload.generation_mode}`,
      `- ${t("pathLabel")}: ${payload.relative_skill_path || payload.skill_path}`
    ];
    setLastPayload(payload);
    setRibbonPayload(payload);
    setResultEmpty(false);
    setResultHtml(markdownToHtml(lines.join("\n")));
    setSummary({
      intent: "generate_skill",
      plan: "generate_skill",
      skill: `${payload.skill_slug || "Skill"} ${payload.version || ""}`.trim(),
      traceUrl: apiUrl(payload.trace_url),
      traceLabel: payload.trace_path,
      warnings: payload.warnings || [],
      artifacts: [{ type: "skill", path: payload.relative_skill_path || payload.skill_path }],
      timeline: []
    });
    setDebugPayload(payload);
  }

  function renderRunPayload(payload: WebPayload) {
    const lines = [
      `# ${t("runOutput")}`,
      "",
      payload.output || t("noResponse"),
      "",
      `## ${t("artifacts")}`,
      "",
      `- ${t("modeLabel")}: ${payload.mode}`,
      `- ${t("runDir")}: ${payload.relative_run_dir || payload.run_dir}`
    ];
    setLastPayload(payload);
    setRibbonPayload(payload);
    setResultEmpty(false);
    setResultHtml(markdownToHtml(lines.join("\n")));
    setSummary({
      intent: "run_skill",
      plan: "run_skill",
      skill: payload.relative_skill_path || payload.skill_path || "-",
      traceUrl: apiUrl(payload.trace_url),
      traceLabel: payload.trace_path,
      warnings: payload.warnings || [],
      artifacts: [
        { type: "run", path: payload.relative_run_dir || payload.run_dir },
        { type: "trace", path: payload.trace_path }
      ],
      timeline: []
    });
    setDebugPayload(payload);
  }

  function renderEvolvePayload(payload: WebPayload) {
    const lines = [
      `# ${t("evolveResult")}`,
      "",
      `- ${t("stopReason")}: ${payload.stop_reason}`,
      `- ${t("finalSkill")}: ${payload.relative_final_skill_path || payload.final_skill_path}`,
      `- ${t("iterations")}: ${payload.iterations ? payload.iterations.length : 0}`,
      "",
      `## ${t("iterations")}`,
      ""
    ];
    for (const item of payload.iterations || []) {
      lines.push(
        `- #${item.iteration}: HQS ${item.average_hqs}, ${t("decision")} ${item.decision}` +
          (item.candidate_average_hqs !== null ? `, ${t("candidate")} ${item.candidate_average_hqs}` : "")
      );
    }
    setLastPayload(payload);
    setRibbonPayload(payload);
    setResultEmpty(false);
    setResultHtml(markdownToHtml(lines.join("\n")));
    setSummary({
      intent: "evolve_skill",
      plan: "evolve_skill",
      skill: payload.relative_final_skill_path || payload.final_skill_path || "-",
      traceUrl: apiUrl(payload.trace_url),
      traceLabel: payload.trace_path,
      warnings: payload.warnings || [],
      artifacts: [
        { type: "skill", path: payload.relative_final_skill_path || payload.final_skill_path },
        { type: "trace", path: payload.trace_path }
      ],
      timeline: []
    });
    setDebugPayload(payload);
  }

  function renderError(message: string) {
    setResultEmpty(false);
    setRibbonPayload({ status: "error" });
    setResultHtml(`<p class="status-error">${escapeHtml(message)}</p>`);
  }

  function handleLanguageToggle() {
    setLang((current) => (current === "zh" ? "en" : "zh"));
  }

  function handleChatKeyDown(event: React.KeyboardEvent<HTMLTextAreaElement>) {
    if ((event.ctrlKey || event.metaKey) && event.key === "Enter") {
      void runChat();
    }
  }

  return (
    <>
      <header className="topbar">
        <div className="brand-lockup">
          <div className="brand-mark" aria-hidden="true">
            AF
          </div>
          <div>
            <h1>AgentForge</h1>
            <p id="statusText" className={statusClass}>
              {statusText}
            </p>
          </div>
        </div>
        <nav className="navlinks" aria-label={t("apiLinks")}>
          <a href="/health">{t("health")}</a>
          <a href="/skills">{t("skills")}</a>
          <a href="/tasksets">{t("tasksets")}</a>
          <a href="/traces">{t("traces")}</a>
          <button className="secondary" type="button" onClick={handleLanguageToggle}>
            {lang === "zh" ? "English" : "中文"}
          </button>
        </nav>
      </header>

      <main className="layout">
        <section className="workspace">
          <section className="status-strip" aria-label={t("workspaceStatus")}>
            <StatusTile primary label={t("runtime")} value={runtimeValue} />
            <StatusTile label={t("skillCount")} value={String(skills.length)} />
            <StatusTile label={t("tasksetCount")} value={String(tasksets.length)} />
            <StatusTile label={t("mode")} value={modeValue} />
          </section>

          <section className="settings-panel">
            <div>
              <h2>{t("runMode")}</h2>
              <p className="mode-hint">{modeHint}</p>
            </div>
            <label className="toggle mode-toggle">
              <input checked={useProvider} type="checkbox" onChange={(event) => setUseProvider(event.target.checked)} />
              <span>{t("useProvider")}</span>
            </label>
            <label className="mode-select">
              <span>{t("agentMode")}</span>
              <select value={agentMode} onChange={(event) => setAgentMode(event.target.value as AgentMode)}>
                <option value="harness_workflow">{t("harnessWorkflow")}</option>
                <option value="tool_calling">{t("toolCallingAgent")}</option>
              </select>
            </label>
          </section>

          <div className="tabs" role="tablist" aria-label={t("workflowTabs")}>
            <TabButton active={activeTab === "chat"} label={t("tabChat")} onClick={() => setActiveTab("chat")} />
            <TabButton active={activeTab === "generate"} label={t("tabGenerate")} onClick={() => setActiveTab("generate")} />
            <TabButton active={activeTab === "run"} label={t("tabRun")} onClick={() => setActiveTab("run")} />
            <TabButton active={activeTab === "evolve"} label={t("tabEvolve")} onClick={() => setActiveTab("evolve")} />
          </div>

          <WorkflowPanels
            activeTab={activeTab}
            t={t}
            skills={skills}
            tasksets={tasksets}
            runningAction={runningAction}
            chatMessage={chatMessage}
            chatDebug={chatDebug}
            generateInput={generateInput}
            runInput={runInput}
            runSkillPath={runSkillPath}
            evolveSkillPath={evolveSkillPath}
            evolveTasksetPath={evolveTasksetPath}
            maxIterations={maxIterations}
            minImprovement={minImprovement}
            onChatMessage={setChatMessage}
            onChatDebug={setChatDebug}
            onGenerateInput={setGenerateInput}
            onRunInput={setRunInput}
            onRunSkillPath={setRunSkillPath}
            onEvolveSkillPath={setEvolveSkillPath}
            onEvolveTasksetPath={setEvolveTasksetPath}
            onMaxIterations={setMaxIterations}
            onMinImprovement={setMinImprovement}
            onChatKeyDown={handleChatKeyDown}
            onRunChat={() => void runChat()}
            onGenerateSkill={() => void generateSkill()}
            onRunSkill={() => void runSkill()}
            onEvolveSkill={() => void evolveSkill()}
          />

          <ResultPanel
            empty={resultEmpty}
            progress={progress}
            elapsedSeconds={elapsedSeconds}
            resultHtml={resultHtml}
            ribbonPayload={ribbonPayload}
            t={t}
          />
        </section>

        <aside className="sidepanel">
          <MetricPanel summary={summary} t={t} />
          <RunSummary summary={summary} t={t} />
          <ListPanel title={t("warnings")} emptyText={t("none")} items={summary.warnings.map((item) => item.message || item.type || t("warning"))} />
          <ListPanel title={t("artifacts")} emptyText={t("none")} compact items={artifactLabels(summary.artifacts, t)} />
          <TimelinePanel steps={summary.timeline} t={t} />
          <section className="meta-panel drilldown-panel">
            <div className="section-heading">
              <h2>{t("drilldown")}</h2>
              <span className={drilldownStatus.muted ? "badge muted" : "badge"}>{drilldownStatus.text}</span>
            </div>
            <div className="drill-tabs" role="tablist" aria-label={t("inspectableDetails")}>
              <DrillTab active={activeDrilldown === "trace"} label={t("trace")} onClick={() => setActiveDrilldown("trace")} />
              <DrillTab active={activeDrilldown === "hqs"} label={t("hqs")} onClick={() => setActiveDrilldown("hqs")} />
              <DrillTab active={activeDrilldown === "memory"} label={t("memory")} onClick={() => setActiveDrilldown("memory")} />
              <DrillTab active={activeDrilldown === "diff"} label={t("skillDiff")} onClick={() => setActiveDrilldown("diff")} />
            </div>
            <Drilldown
              active={activeDrilldown}
              payload={lastPayload}
              t={t}
              onStatus={(text, muted) => setDrilldownStatus({ text, muted })}
            />
          </section>
        </aside>
      </main>

      <section className="debug-panel">
        <details>
          <summary>{t("debugJson")}</summary>
          <pre>{JSON.stringify(debugPayload, null, 2)}</pre>
        </details>
      </section>
    </>
  );
}

function StatusTile({ label, value, primary = false }: { label: string; value: string; primary?: boolean }) {
  return (
    <div className={primary ? "status-tile primary" : "status-tile"}>
      <span className="tile-label">{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function TabButton({ active, label, onClick }: { active: boolean; label: string; onClick: () => void }) {
  return (
    <button className={active ? "tab active" : "tab"} type="button" onClick={onClick}>
      {label}
    </button>
  );
}

interface WorkflowPanelsProps {
  activeTab: TabKey;
  t: (key: I18nKey) => string;
  skills: SkillSummary[];
  tasksets: TasksetSummary[];
  runningAction: string | null;
  chatMessage: string;
  chatDebug: boolean;
  generateInput: string;
  runInput: string;
  runSkillPath: string;
  evolveSkillPath: string;
  evolveTasksetPath: string;
  maxIterations: number;
  minImprovement: number;
  onChatMessage: (value: string) => void;
  onChatDebug: (value: boolean) => void;
  onGenerateInput: (value: string) => void;
  onRunInput: (value: string) => void;
  onRunSkillPath: (value: string) => void;
  onEvolveSkillPath: (value: string) => void;
  onEvolveTasksetPath: (value: string) => void;
  onMaxIterations: (value: number) => void;
  onMinImprovement: (value: number) => void;
  onChatKeyDown: (event: React.KeyboardEvent<HTMLTextAreaElement>) => void;
  onRunChat: () => void;
  onGenerateSkill: () => void;
  onRunSkill: () => void;
  onEvolveSkill: () => void;
}

function WorkflowPanels(props: WorkflowPanelsProps) {
  const { activeTab, t, skills, tasksets, runningAction } = props;

  return (
    <>
      <section className={activeTab === "chat" ? "panel active" : "panel"}>
        <label htmlFor="chatMessage">{t("message")}</label>
        <textarea
          id="chatMessage"
          value={props.chatMessage}
          onChange={(event) => props.onChatMessage(event.target.value)}
          onKeyDown={props.onChatKeyDown}
        />
        <div className="toolbar">
          <button disabled={runningAction === "chat"} type="button" onClick={props.onRunChat}>
            {runningAction === "chat" ? t("running") : t("run")}
          </button>
          <label className="toggle">
            <input checked={props.chatDebug} type="checkbox" onChange={(event) => props.onChatDebug(event.target.checked)} />
            <span>{t("debug")}</span>
          </label>
        </div>
      </section>

      <section className={activeTab === "generate" ? "panel active" : "panel"}>
        <label htmlFor="generateInput">{t("requirement")}</label>
        <textarea
          id="generateInput"
          value={props.generateInput}
          onChange={(event) => props.onGenerateInput(event.target.value)}
        />
        <div className="toolbar">
          <button disabled={runningAction === "generate"} type="button" onClick={props.onGenerateSkill}>
            {runningAction === "generate" ? t("running") : t("generateSkill")}
          </button>
        </div>
      </section>

      <section className={activeTab === "run" ? "panel active" : "panel"}>
        <div className="field-grid">
          <label>
            <span>{t("skill")}</span>
            <select value={props.runSkillPath} onChange={(event) => props.onRunSkillPath(event.target.value)}>
              <SkillOptions skills={skills} emptyLabel={t("missingSkills")} />
            </select>
          </label>
        </div>
        <label htmlFor="runInput">{t("taskInput")}</label>
        <textarea id="runInput" value={props.runInput} onChange={(event) => props.onRunInput(event.target.value)} />
        <div className="toolbar">
          <button disabled={runningAction === "run"} type="button" onClick={props.onRunSkill}>
            {runningAction === "run" ? t("running") : t("runSkill")}
          </button>
        </div>
      </section>

      <section className={activeTab === "evolve" ? "panel active" : "panel"}>
        <div className="field-grid two">
          <label>
            <span>{t("skill")}</span>
            <select value={props.evolveSkillPath} onChange={(event) => props.onEvolveSkillPath(event.target.value)}>
              <SkillOptions skills={skills} emptyLabel={t("missingSkills")} />
            </select>
          </label>
          <label>
            <span>{t("taskset")}</span>
            <select value={props.evolveTasksetPath} onChange={(event) => props.onEvolveTasksetPath(event.target.value)}>
              {tasksets.length ? (
                tasksets.map((taskset) => (
                  <option key={taskset.relative_path || taskset.path || taskset.name} value={taskset.relative_path || ""}>
                    {taskset.name} ({taskset.task_count || 0})
                  </option>
                ))
              ) : (
                <option value="">{t("missingTasksets")}</option>
              )}
            </select>
          </label>
          <label>
            <span>{t("maxIterations")}</span>
            <input
              min={1}
              max={10}
              type="number"
              value={props.maxIterations}
              onChange={(event) => props.onMaxIterations(Number(event.target.value || 1))}
            />
          </label>
          <label>
            <span>{t("minImprovement")}</span>
            <input
              step={0.01}
              type="number"
              value={props.minImprovement}
              onChange={(event) => props.onMinImprovement(Number(event.target.value || 0.01))}
            />
          </label>
        </div>
        <div className="toolbar">
          <button disabled={runningAction === "evolve"} type="button" onClick={props.onEvolveSkill}>
            {runningAction === "evolve" ? t("running") : t("evolveSkill")}
          </button>
        </div>
      </section>
    </>
  );
}

function SkillOptions({ skills, emptyLabel }: { skills: SkillSummary[]; emptyLabel: string }) {
  if (!skills.length) {
    return <option value="">{emptyLabel}</option>;
  }
  return (
    <>
      {skills.map((skill) => {
        const value = skill.latest_skill_path || skill.skill_path || "";
        const title = skill.title || skill.skill_slug;
        const source = skill.source ? `/${skill.source}` : "";
        return (
          <option key={value || skill.skill_slug} value={value}>
            {title} {skill.latest_version || skill.version || ""}
            {source}
          </option>
        );
      })}
    </>
  );
}

function ResultPanel({
  empty,
  progress,
  elapsedSeconds,
  resultHtml,
  ribbonPayload,
  t
}: {
  empty: boolean;
  progress: ProgressState | null;
  elapsedSeconds: number;
  resultHtml: string;
  ribbonPayload: WebPayload;
  t: (key: I18nKey) => string;
}) {
  return (
    <section className={empty ? "result empty" : "result"}>
      <RunRibbon payload={ribbonPayload} t={t} />
      {progress ? (
        <ProgressPanel progress={progress} elapsedSeconds={elapsedSeconds} t={t} />
      ) : (
        <div className="result-body" dangerouslySetInnerHTML={{ __html: resultHtml }} />
      )}
    </section>
  );
}

function RunRibbon({ payload, t }: { payload: WebPayload; t: (key: I18nKey) => string }) {
  const chips: Array<[string, string | number]> = [];
  if (payload.run_id) {
    chips.push([t("runId"), payload.run_id]);
  }
  if (payload.agent_mode) {
    chips.push([t("agentMode"), payload.agent_mode]);
  }
  if (payload.final_answer_source) {
    chips.push([t("finalAnswerSource"), payload.final_answer_source]);
  }
  if (payload.stop_reason) {
    chips.push([t("stop"), payload.stop_reason]);
  }
  if (typeof payload.parse_repair_count === "number" && payload.parse_repair_count > 0) {
    chips.push([t("repairCount"), payload.parse_repair_count]);
  }
  if (payload.trace_file || payload.trace_path) {
    chips.push([t("traceReady"), traceLabel(payload.trace_file || payload.trace_path)]);
  }
  if (payload.status) {
    chips.push([t("status"), String(payload.status)]);
  }

  return (
    <div className={chips.length ? "run-ribbon" : "run-ribbon muted"}>
      {chips.length ? (
        chips.map(([label, value]) => (
          <span className="ribbon-chip" key={`${label}:${value}`}>
            {label}: {value}
          </span>
        ))
      ) : (
        <span>{t("runIdle")}</span>
      )}
    </div>
  );
}

function ProgressPanel({
  progress,
  elapsedSeconds,
  t
}: {
  progress: ProgressState;
  elapsedSeconds: number;
  t: (key: I18nKey) => string;
}) {
  const activeIndex = Math.min(progress.phases.length - 1, Math.floor(elapsedSeconds / 18));
  return (
    <div className="progress-panel">
      <div className="progress-head">
        <strong>{t("progressTitle")}</strong>
        <span>
          {t("elapsed")}: {elapsedSeconds} {t("seconds")}
        </span>
      </div>
      <ol className="progress-steps">
        {progress.phases.map((phase, index) => {
          const className = index < activeIndex ? "completed" : index === activeIndex ? "running" : "pending";
          return (
            <li className={className} key={phase}>
              <span>{index + 1}</span>
              <strong>{phase}</strong>
            </li>
          );
        })}
      </ol>
      {elapsedSeconds >= 20 ? <p className="progress-hint">{t("longTaskHint")}</p> : null}
    </div>
  );
}

function MetricPanel({ summary, t }: { summary: SummaryState; t: (key: I18nKey) => string }) {
  return (
    <section className="metric-panel">
      <h2>{t("hqs")}</h2>
      <ScoreLine label={t("response")} score={summary.responseScore} />
      <ScoreLine label={t("system")} score={summary.systemScore} />
    </section>
  );
}

function ScoreLine({ label, score }: { label: string; score?: number }) {
  const width = typeof score === "number" ? `${Math.max(0, Math.min(100, (score / 5) * 100))}%` : "0%";
  return (
    <>
      <div className="scoreline">
        <span className="score">{formatScore(score)}</span>
        <span>{label}</span>
      </div>
      <div className="scorebar">
        <span style={{ width }} />
      </div>
    </>
  );
}

function RunSummary({ summary, t }: { summary: SummaryState; t: (key: I18nKey) => string }) {
  return (
    <section className="meta-panel">
      <h2>{t("runSummary")}</h2>
      <dl>
        <dt>{t("intent")}</dt>
        <dd>{summary.intent}</dd>
        <dt>{t("plan")}</dt>
        <dd>{summary.plan}</dd>
        <dt>{t("skill")}</dt>
        <dd>{summary.skill}</dd>
        <dt>{t("trace")}</dt>
        <dd>{summary.traceUrl ? <a href={summary.traceUrl}>{traceLabel(summary.traceLabel || summary.traceUrl)}</a> : "-"}</dd>
      </dl>
    </section>
  );
}

function ListPanel({
  title,
  items,
  emptyText,
  compact = false
}: {
  title: string;
  items: string[];
  emptyText: string;
  compact?: boolean;
}) {
  return (
    <section className="meta-panel">
      <h2>{title}</h2>
      <ul className={compact ? "list compact" : "list"}>
        {items.length ? items.slice(0, 8).map((item) => <li key={item}>{item}</li>) : <li>{emptyText}</li>}
      </ul>
    </section>
  );
}

function TimelinePanel({ steps, t }: { steps: TimelineStep[]; t: (key: I18nKey) => string }) {
  return (
    <section className="meta-panel">
      <h2>{t("timeline")}</h2>
      <ol className="timeline">
        {steps.length ? (
          steps.map((step, index) => <TimelineItem key={`${step.name || step.tool_name || "step"}-${index}`} step={step} t={t} />)
        ) : (
          <li>{t("timelineEmpty")}</li>
        )}
      </ol>
    </section>
  );
}

function TimelineItem({ step, t }: { step: TimelineStep; t: (key: I18nKey) => string }) {
  if (isToolCallTimelineStep(step)) {
    return (
      <li
        className={`${step.status || ""} tool-call-row`}
        dangerouslySetInnerHTML={{ __html: toolCallTimelineHtml(step, t) }}
      />
    );
  }
  const name = step.name || t("step");
  const kind = step.kind ? ` · ${step.kind}` : "";
  const counts: string[] = [];
  if (step.artifact_count) {
    counts.push(`${step.artifact_count} ${t("artifactCount")}`);
  }
  if (step.error_count) {
    counts.push(`${step.error_count} ${t("errorCount")}`);
  }
  const suffix = counts.length ? ` · ${counts.join(", ")}` : "";
  return (
    <li className={step.status || ""}>
      <div>
        <strong>{name}</strong>
        <span>
          {step.status || t("unknown")}
          {kind}
          {suffix}
        </span>
      </div>
    </li>
  );
}

function DrillTab({ active, label, onClick }: { active: boolean; label: string; onClick: () => void }) {
  return (
    <button className={active ? "drill-tab active" : "drill-tab"} type="button" onClick={onClick}>
      {label}
    </button>
  );
}

function artifactLabels(artifacts: ArtifactItem[], t: (key: I18nKey) => string): string[] {
  return artifacts.slice(0, 8).map((artifact) => {
    const type = artifact.type || t("artifact");
    const path = artifact.path || artifact.relative_path || "";
    return path ? `${type}: ${traceLabel(path)}` : type;
  });
}

function selectSkillPath(skills: SkillSummary[], path: string | undefined): string {
  if (!path) {
    return "";
  }
  const normalized = path.replaceAll("\\", "/");
  for (const skill of skills) {
    const candidate = skill.latest_skill_path || skill.skill_path || "";
    if (candidate === path || candidate.replaceAll("\\", "/") === normalized) {
      return candidate;
    }
  }
  return "";
}
