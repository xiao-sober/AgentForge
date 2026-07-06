const i18n = {
  en: {
    statusLoading: "Checking local runtime...",
    apiLinks: "API links",
    workflowTabs: "AgentForge workflows",
    workspaceStatus: "Workspace status",
    inspectableDetails: "Inspectable run details",
    runtime: "Runtime",
    health: "Health",
    skills: "Skills",
    skillCount: "Skills",
    tasksets: "Tasksets",
    tasksetCount: "Tasksets",
    traces: "Traces",
    mode: "Mode",
    runMode: "Run Mode",
    agentMode: "Agent Mode",
    harnessWorkflow: "harness_workflow",
    toolCallingAgent: "tool_calling_agent",
    useProvider: "Call model",
    localModeHint: "Local deterministic mode",
    providerModeHint: "Model provider mode",
    tabChat: "Chat",
    tabGenerate: "Generate Skill",
    tabRun: "Run Skill",
    tabEvolve: "Evolve Skill",
    message: "Message",
    run: "Run",
    debug: "Debug",
    requirement: "Requirement",
    generateSkill: "Generate Skill",
    skill: "Skill",
    taskInput: "Task input",
    runSkill: "Run Skill",
    taskset: "Taskset",
    maxIterations: "Max iterations",
    minImprovement: "Min improvement",
    evolveSkill: "Evolve Skill",
    emptyResult: "Run a workflow to see results.",
    hqs: "HQS",
    response: "Response",
    system: "System",
    runSummary: "Run",
    intent: "Intent",
    plan: "Plan",
    trace: "Trace",
    warnings: "Warnings",
    artifacts: "Artifacts",
    none: "None",
    timeline: "Timeline",
    timelineEmpty: "No run yet.",
    debugJson: "Debug JSON",
    running: "Running...",
    progressTitle: "Workflow running",
    elapsed: "Elapsed",
    seconds: "s",
    longTaskHint: "Provider calls can take minutes with thinking models. Keep this tab open while AgentForge writes traces and artifacts.",
    stageSubmit: "Submit request",
    stageModelThinking: "Model thinking",
    stageValidateWrite: "Validate and write artifacts",
    stageSkillExecute: "Run selected Skill",
    stageContractTrace: "Normalize output and write trace",
    stageHqsTrace: "Score HQS and save trace",
    stageRunBaseline: "Run current Skill",
    stageRewriteCandidate: "Rewrite and test candidate",
    stageGatePersist: "Apply quality gate and persist result",
    runIdle: "No active run",
    stop: "Stop",
    traceReady: "Trace",
    noResponse: "No response.",
    generated: "Generated Skill",
    generatedBody: "Skill generated and validated.",
    runOutput: "Skill Output",
    evolveResult: "Evolution Result",
    missingSkills: "No Skills found.",
    missingTasksets: "No tasksets found.",
    providerMode: "provider",
    localMode: "local",
    drilldown: "Drilldown",
    drilldownEmpty: "Run a workflow, then inspect trace, HQS, memory, or Skill diffs.",
    memory: "Memory",
    skillDiff: "Skill Diff",
    loading: "Loading...",
    noTrace: "No trace available.",
    noDiff: "No Skill diff available for this version.",
    retrieval: "Retrieval",
    dimensions: "Dimensions",
    messageEmpty: "Message is empty.",
    requirementEmpty: "Requirement is empty.",
    taskInputEmpty: "Task input is empty.",
    localApiRunning: "Local API running",
    healthLabel: "Health",
    unavailable: "unavailable",
    offline: "offline",
    unknown: "unknown",
    status: "Status",
    runId: "Run",
    modeLabel: "Mode",
    pathLabel: "Path",
    versionLabel: "Version",
    finalSkill: "Final Skill",
    stopReason: "Stop reason",
    iterations: "Iterations",
    decision: "decision",
    candidate: "candidate",
    runDir: "Run",
    steps: "Steps",
    errors: "Errors",
    latestEpisodes: "Latest Episodes",
    semanticMemory: "Semantic Memory",
    executionState: "Execution State",
    diff: "Diff",
    type: "type",
    schema: "schema",
    completed: "completed",
    failed: "failed",
    skipped: "skipped",
    avg: "avg",
    confidence: "confidence",
    query: "query",
    episodes: "episodes",
    semantic: "semantic",
    score: "score",
    artifact: "artifact",
    artifactCount: "artifact",
    errorCount: "error",
    warning: "Warning",
    step: "step",
    transition: "transition",
    episode: "episode",
    skillSource: "source",
    toolCalls: "Tool Calls",
    modelDecision: "Model Decision",
    toolArguments: "Tool Arguments",
    validation: "Validation",
    validationErrors: "Validation Errors",
    observation: "Observation",
    parseRepair: "Parse Repair",
    repaired: "repaired",
    repairStrategy: "repair",
    finalAnswerSource: "Final answer",
    repairCount: "repairs",
    hqsGate: "HQS Gate",
    qualityRetry: "Retry"
  },
  zh: {
    statusLoading: "正在检查本地运行状态...",
    apiLinks: "API 链接",
    workflowTabs: "AgentForge 工作流",
    workspaceStatus: "工作台状态",
    inspectableDetails: "可钻取运行详情",
    runtime: "运行时",
    health: "健康",
    skills: "技能",
    skillCount: "技能",
    tasksets: "任务集",
    tasksetCount: "任务集",
    traces: "追踪",
    mode: "模式",
    runMode: "运行模式",
    useProvider: "调用大模型",
    localModeHint: "本地确定性模式",
    providerModeHint: "大模型调用模式",
    tabChat: "对话",
    tabGenerate: "生成 Skill",
    tabRun: "运行 Skill",
    tabEvolve: "演化 Skill",
    message: "消息",
    run: "运行",
    debug: "调试",
    requirement: "需求",
    generateSkill: "生成 Skill",
    skill: "Skill",
    taskInput: "任务输入",
    runSkill: "运行 Skill",
    taskset: "任务集",
    maxIterations: "最大迭代",
    minImprovement: "最小提升",
    evolveSkill: "演化 Skill",
    emptyResult: "运行一个流程后查看结果。",
    hqs: "HQS",
    response: "响应",
    system: "系统",
    runSummary: "运行摘要",
    intent: "意图",
    plan: "计划",
    trace: "追踪",
    warnings: "警告",
    artifacts: "产物",
    none: "无",
    timeline: "时间线",
    timelineEmpty: "暂无运行。",
    debugJson: "调试 JSON",
    running: "运行中...",
    progressTitle: "流程运行中",
    elapsed: "已耗时",
    seconds: "秒",
    longTaskHint: "Thinking 模型调用可能持续数分钟。请保持当前页面打开，AgentForge 会继续写入 trace 和产物。",
    stageSubmit: "提交请求",
    stageModelThinking: "模型思考",
    stageValidateWrite: "校验并写入产物",
    stageSkillExecute: "执行选中的 Skill",
    stageContractTrace: "规范输出并写入 trace",
    stageHqsTrace: "计算 HQS 并保存 trace",
    stageRunBaseline: "运行当前 Skill",
    stageRewriteCandidate: "重写并测试候选版本",
    stageGatePersist: "执行质量门禁并保存结果",
    runIdle: "暂无运行",
    stop: "停止",
    traceReady: "追踪",
    noResponse: "没有响应。",
    generated: "已生成 Skill",
    generatedBody: "Skill 已生成并通过校验。",
    runOutput: "Skill 输出",
    evolveResult: "演化结果",
    missingSkills: "没有找到 Skill。",
    missingTasksets: "没有找到任务集。",
    providerMode: "大模型",
    localMode: "本地",
    drilldown: "钻取视图",
    drilldownEmpty: "运行一个流程后，可查看追踪、HQS、记忆或 Skill diff。",
    memory: "记忆",
    skillDiff: "Skill Diff",
    loading: "加载中...",
    noTrace: "暂无追踪。",
    noDiff: "当前版本没有 Skill diff。",
    retrieval: "检索结果",
    dimensions: "维度",
    messageEmpty: "消息不能为空。",
    requirementEmpty: "需求不能为空。",
    taskInputEmpty: "任务输入不能为空。",
    localApiRunning: "本地 API 已启动",
    healthLabel: "健康状态",
    unavailable: "不可用",
    offline: "离线",
    unknown: "未知",
    status: "状态",
    runId: "运行",
    modeLabel: "模式",
    pathLabel: "路径",
    versionLabel: "版本",
    finalSkill: "最终 Skill",
    stopReason: "停止原因",
    iterations: "迭代",
    decision: "决策",
    candidate: "候选",
    runDir: "运行目录",
    steps: "步骤",
    errors: "错误",
    latestEpisodes: "最近事件",
    semanticMemory: "语义记忆",
    executionState: "执行状态",
    diff: "Diff",
    type: "类型",
    schema: "Schema",
    completed: "完成",
    failed: "失败",
    skipped: "跳过",
    avg: "均分",
    confidence: "置信度",
    query: "查询",
    episodes: "事件",
    semantic: "语义",
    score: "分数",
    artifact: "产物",
    artifactCount: "产物",
    errorCount: "错误",
    warning: "警告",
    step: "步骤",
    transition: "状态变更",
    episode: "事件",
    skillSource: "来源"
  }
};

const state = {
  lang: localStorage.getItem("agentforge_lang") || "zh",
  skills: [],
  tasksets: [],
  lastPayload: null,
  activeDrilldown: "trace"
};

const el = {
  statusText: document.getElementById("statusText"),
  runtimeValue: document.getElementById("runtimeValue"),
  skillCountValue: document.getElementById("skillCountValue"),
  tasksetCountValue: document.getElementById("tasksetCountValue"),
  modeValue: document.getElementById("modeValue"),
  languageToggle: document.getElementById("languageToggle"),
  useProvider: document.getElementById("useProvider"),
  agentMode: document.getElementById("agentMode"),
  modeHint: document.getElementById("modeHint"),
  chatMessage: document.getElementById("chatMessage"),
  chatSend: document.getElementById("chatSend"),
  chatDebug: document.getElementById("chatDebug"),
  generateInput: document.getElementById("generateInput"),
  generateSend: document.getElementById("generateSend"),
  runSkill: document.getElementById("runSkill"),
  runInput: document.getElementById("runInput"),
  runSend: document.getElementById("runSend"),
  evolveSkill: document.getElementById("evolveSkill"),
  evolveTaskset: document.getElementById("evolveTaskset"),
  maxIterations: document.getElementById("maxIterations"),
  minImprovement: document.getElementById("minImprovement"),
  evolveSend: document.getElementById("evolveSend"),
  result: document.getElementById("result"),
  runRibbon: document.getElementById("runRibbon"),
  responseScore: document.getElementById("responseScore"),
  responseScoreBar: document.getElementById("responseScoreBar"),
  systemScore: document.getElementById("systemScore"),
  systemScoreBar: document.getElementById("systemScoreBar"),
  intentValue: document.getElementById("intentValue"),
  planValue: document.getElementById("planValue"),
  skillValue: document.getElementById("skillValue"),
  traceValue: document.getElementById("traceValue"),
  warnings: document.getElementById("warnings"),
  artifacts: document.getElementById("artifacts"),
  timeline: document.getElementById("timeline"),
  drilldownStatus: document.getElementById("drilldownStatus"),
  drilldownContent: document.getElementById("drilldownContent"),
  debugOutput: document.getElementById("debugOutput")
};

function t(key) {
  return (i18n[state.lang] && i18n[state.lang][key]) || i18n.en[key] || key;
}

function applyLanguage() {
  document.documentElement.lang = state.lang === "zh" ? "zh-CN" : "en";
  for (const node of document.querySelectorAll("[data-i18n]")) {
    node.textContent = t(node.dataset.i18n);
  }
  el.languageToggle.textContent = state.lang === "zh" ? "English" : "中文";
  updateModeHint();
  renderWarnings(state.lastPayload && state.lastPayload.warnings ? state.lastPayload.warnings : []);
  renderArtifacts(state.lastPayload && state.lastPayload.artifacts ? state.lastPayload.artifacts : []);
  renderTimeline(timelineForPayload(state.lastPayload));
  void renderActiveDrilldown();
}

function ensureAgentModeControl() {
  if (el.agentMode) {
    return;
  }
  const settings = document.querySelector(".settings-panel");
  if (!settings) {
    return;
  }
  const label = document.createElement("label");
  label.className = "mode-select";
  label.innerHTML = [
    `<span data-i18n="agentMode">${escapeHtml(t("agentMode"))}</span>`,
    `<select id="agentMode">`,
    `<option value="harness_workflow" data-i18n="harnessWorkflow">${escapeHtml(t("harnessWorkflow"))}</option>`,
    `<option value="tool_calling" data-i18n="toolCallingAgent">${escapeHtml(t("toolCallingAgent"))}</option>`,
    `</select>`
  ].join("");
  settings.appendChild(label);
  el.agentMode = document.getElementById("agentMode");
}

async function init() {
  ensureAgentModeControl();
  applyLanguage();
  bindEvents();
  updateModeHint();
  await Promise.all([loadHealth(), loadSkills(), loadTasksets()]);
}

function bindEvents() {
  el.languageToggle.addEventListener("click", () => {
    state.lang = state.lang === "zh" ? "en" : "zh";
    localStorage.setItem("agentforge_lang", state.lang);
    applyLanguage();
  });

  el.useProvider.addEventListener("change", updateModeHint);
  if (el.agentMode) {
    el.agentMode.addEventListener("change", updateModeHint);
  }

  for (const tab of document.querySelectorAll(".tab")) {
    tab.addEventListener("click", () => activateTab(tab.dataset.tab));
  }
  for (const tab of document.querySelectorAll(".drill-tab")) {
    tab.addEventListener("click", () => activateDrilldown(tab.dataset.drill));
  }

  el.chatSend.addEventListener("click", runChat);
  el.generateSend.addEventListener("click", generateSkill);
  el.runSend.addEventListener("click", runSkill);
  el.evolveSend.addEventListener("click", evolveSkill);

  el.chatMessage.addEventListener("keydown", (event) => {
    if ((event.ctrlKey || event.metaKey) && event.key === "Enter") {
      runChat();
    }
  });
}

function activateTab(name) {
  for (const tab of document.querySelectorAll(".tab")) {
    tab.classList.toggle("active", tab.dataset.tab === name);
  }
  for (const panel of document.querySelectorAll(".panel")) {
    panel.classList.toggle("active", panel.id === `panel-${name}`);
  }
}

function activateDrilldown(name) {
  state.activeDrilldown = name || "trace";
  for (const tab of document.querySelectorAll(".drill-tab")) {
    tab.classList.toggle("active", tab.dataset.drill === state.activeDrilldown);
  }
  void renderActiveDrilldown();
}

async function loadHealth() {
  el.statusText.textContent = t("localApiRunning");
  el.runtimeValue.textContent = "...";
  try {
    const payload = await getJson("/health");
    el.statusText.textContent = `${t("healthLabel")}: ${payload.status || t("unknown")}`;
    el.runtimeValue.textContent = payload.status || t("unknown");
    el.statusText.className = payload.status === "ok" ? "" : "status-warn";
  } catch (error) {
    el.statusText.textContent = `${t("healthLabel")}: ${t("unavailable")}`;
    el.runtimeValue.textContent = t("offline");
    el.statusText.className = "status-error";
  }
}

async function loadSkills() {
  const payload = await getJson("/skills");
  state.skills = payload.skills || [];
  el.skillCountValue.textContent = String(state.skills.length);
  populateSkillSelect(el.runSkill);
  populateSkillSelect(el.evolveSkill);
}

async function loadTasksets() {
  const payload = await getJson("/tasksets");
  state.tasksets = payload.tasksets || [];
  el.tasksetCountValue.textContent = String(state.tasksets.length);
  el.evolveTaskset.innerHTML = "";
  if (!state.tasksets.length) {
    addOption(el.evolveTaskset, "", t("missingTasksets"));
    return;
  }
  for (const taskset of state.tasksets) {
    addOption(el.evolveTaskset, taskset.relative_path, `${taskset.name} (${taskset.task_count})`);
  }
}

function populateSkillSelect(select) {
  select.innerHTML = "";
  if (!state.skills.length) {
    addOption(select, "", t("missingSkills"));
    return;
  }
  for (const skill of state.skills) {
    const title = skill.title || skill.skill_slug;
    const source = skill.source ? `/${skill.source}` : "";
    addOption(select, skill.latest_skill_path, `${title} ${skill.latest_version}${source}`);
  }
}

function addOption(select, value, label) {
  const option = document.createElement("option");
  option.value = value;
  option.textContent = label;
  select.appendChild(option);
}

async function runChat() {
  const message = el.chatMessage.value.trim();
  if (!message) {
    renderError(t("messageEmpty"));
    return;
  }
  await runAction(el.chatSend, async () => {
    const payload = await postJson("/chat", {
      message,
      debug: el.chatDebug.checked,
      ...providerPayload()
    });
    renderChatPayload(payload);
  }, {
    phases: [t("stageSubmit"), t("stageModelThinking"), t("stageSkillExecute"), t("stageHqsTrace")]
  });
}

async function generateSkill() {
  const input = el.generateInput.value.trim();
  if (!input) {
    renderError(t("requirementEmpty"));
    return;
  }
  await runAction(el.generateSend, async () => {
    const payload = await postJson("/skills/generate", {
      input,
      ...providerPayload()
    });
    renderGeneratePayload(payload);
    await loadSkills();
    selectSkillPath(el.runSkill, payload.skill_path);
    selectSkillPath(el.evolveSkill, payload.skill_path);
  }, {
    phases: [t("stageSubmit"), t("stageModelThinking"), t("stageValidateWrite")]
  });
}

async function runSkill() {
  const skillPath = el.runSkill.value;
  const input = el.runInput.value.trim();
  if (!skillPath) {
    renderError(t("missingSkills"));
    return;
  }
  if (!input) {
    renderError(t("taskInputEmpty"));
    return;
  }
  await runAction(el.runSend, async () => {
    const payload = await postJson("/skills/run", {
      skill_path: skillPath,
      input,
      ...providerPayload()
    });
    renderRunPayload(payload);
  }, {
    phases: [t("stageSubmit"), t("stageSkillExecute"), t("stageContractTrace")]
  });
}

async function evolveSkill() {
  const skillPath = el.evolveSkill.value;
  const tasksetPath = el.evolveTaskset.value;
  if (!skillPath) {
    renderError(t("missingSkills"));
    return;
  }
  if (!tasksetPath) {
    renderError(t("missingTasksets"));
    return;
  }
  await runAction(el.evolveSend, async () => {
    const payload = await postJson("/skills/evolve", {
      skill_path: skillPath,
      taskset_path: tasksetPath,
      max_iterations: Number(el.maxIterations.value || 1),
      min_improvement: Number(el.minImprovement.value || 0.01),
      ...providerPayload()
    });
    renderEvolvePayload(payload);
    await loadSkills();
  }, {
    phases: [t("stageSubmit"), t("stageRunBaseline"), t("stageRewriteCandidate"), t("stageGatePersist")]
  });
}

async function runAction(button, action, options = {}) {
  button.disabled = true;
  const oldText = button.textContent;
  button.textContent = t("running");
  el.result.classList.remove("empty");
  const startedAt = Date.now();
  const phases = Array.isArray(options.phases) && options.phases.length ? options.phases : [t("stageSubmit")];
  const renderProgress = () => renderLongTaskProgress(phases, startedAt);
  renderRunRibbon({ status: t("running") });
  renderProgress();
  const progressTimer = window.setInterval(renderProgress, 1000);
  try {
    await action();
  } catch (error) {
    renderError(error.message || String(error));
  } finally {
    window.clearInterval(progressTimer);
    button.disabled = false;
    button.textContent = oldText;
  }
}

function renderLongTaskProgress(phases, startedAt) {
  const elapsedSeconds = Math.max(0, Math.floor((Date.now() - startedAt) / 1000));
  const activeIndex = Math.min(phases.length - 1, Math.floor(elapsedSeconds / 18));
  const steps = phases.map((phase, index) => {
    const className = index < activeIndex ? "completed" : index === activeIndex ? "running" : "pending";
    return `<li class="${className}"><span>${escapeHtml(String(index + 1))}</span><strong>${escapeHtml(phase)}</strong></li>`;
  }).join("");
  const hint = elapsedSeconds >= 20 ? `<p class="progress-hint">${escapeHtml(t("longTaskHint"))}</p>` : "";
  setResultContent(
    [
      `<div class="progress-panel">`,
      `<div class="progress-head"><strong>${escapeHtml(t("progressTitle"))}</strong><span>${escapeHtml(t("elapsed"))}: ${escapeHtml(elapsedSeconds)} ${escapeHtml(t("seconds"))}</span></div>`,
      `<ol class="progress-steps">${steps}</ol>`,
      hint,
      `</div>`
    ].join("")
  );
}

function providerPayload() {
  return {
    use_provider: el.useProvider.checked,
    agent_mode: el.agentMode ? el.agentMode.value : "harness_workflow"
  };
}

function updateModeHint() {
  const agentMode = el.agentMode && el.agentMode.value === "tool_calling" ? t("toolCallingAgent") : t("harnessWorkflow");
  const providerHint = el.useProvider.checked ? t("providerModeHint") : t("localModeHint");
  el.modeHint.textContent = `${providerHint} · ${agentMode}`;
  el.modeValue.textContent = `${el.useProvider.checked ? t("providerMode") : t("localMode")} / ${agentMode}`;
}

function renderChatPayload(payload) {
  state.lastPayload = payload;
  el.result.classList.remove("empty");
  renderRunRibbon(payload);
  setResultContent(renderMarkdown(payload.response || t("noResponse")));
  setScore(el.responseScore, payload.hqs && payload.hqs.average_score);
  setScore(el.systemScore, payload.system_hqs && payload.system_hqs.average_score);
  el.intentValue.textContent = (payload.intent && (payload.intent.type || payload.intent.intent_type)) || "-";
  el.planValue.textContent = (payload.plan && payload.plan.action) || "-";
  el.skillValue.textContent = formatSkill(payload.selected_skill || (payload.execution && payload.execution.selected_skill));
  renderTrace(payload.trace_url, payload.trace_file || payload.trace_path);
  renderWarnings(payload.warnings || []);
  renderArtifacts(payload.artifacts || []);
  renderTimeline(timelineForPayload(payload));
  setDebug(payload);
}

function renderGeneratePayload(payload) {
  state.lastPayload = payload;
  const lines = [
    `# ${t("generated")}`,
    "",
    `- ${t("generatedBody")}`,
    `- Skill: ${payload.skill_name || payload.skill_slug}`,
    `- ${t("versionLabel")}: ${payload.version}`,
    `- ${t("modeLabel")}: ${payload.generation_mode}`,
    `- ${t("pathLabel")}: ${payload.relative_skill_path || payload.skill_path}`
  ];
  el.result.classList.remove("empty");
  renderRunRibbon(payload);
  setResultContent(renderMarkdown(lines.join("\n")));
  clearScores();
  el.intentValue.textContent = "generate_skill";
  el.planValue.textContent = "generate_skill";
  el.skillValue.textContent = `${payload.skill_slug} ${payload.version}`;
  renderTrace(payload.trace_url, payload.trace_path);
  renderWarnings([]);
  renderArtifacts([{ type: "skill", path: payload.relative_skill_path || payload.skill_path }]);
  renderTimeline([]);
  setDebug(payload);
}

function renderRunPayload(payload) {
  state.lastPayload = payload;
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
  el.result.classList.remove("empty");
  renderRunRibbon(payload);
  setResultContent(renderMarkdown(lines.join("\n")));
  clearScores();
  el.intentValue.textContent = "run_skill";
  el.planValue.textContent = "run_skill";
  el.skillValue.textContent = payload.relative_skill_path || payload.skill_path || "-";
  renderTrace(payload.trace_url, payload.trace_path);
  renderWarnings([]);
  renderArtifacts([
    { type: "run", path: payload.relative_run_dir || payload.run_dir },
    { type: "trace", path: payload.trace_path }
  ]);
  renderTimeline([]);
  setDebug(payload);
}

function renderEvolvePayload(payload) {
  state.lastPayload = payload;
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
  el.result.classList.remove("empty");
  renderRunRibbon(payload);
  setResultContent(renderMarkdown(lines.join("\n")));
  clearScores();
  el.intentValue.textContent = "evolve_skill";
  el.planValue.textContent = "evolve_skill";
  el.skillValue.textContent = payload.relative_final_skill_path || payload.final_skill_path || "-";
  renderTrace(payload.trace_url, payload.trace_path);
  renderWarnings([]);
  renderArtifacts([
    { type: "skill", path: payload.relative_final_skill_path || payload.final_skill_path },
    { type: "trace", path: payload.trace_path }
  ]);
  renderTimeline([]);
  setDebug(payload);
}

function setResultContent(html) {
  el.result.innerHTML = "";
  el.result.appendChild(el.runRibbon);
  el.result.insertAdjacentHTML("beforeend", html);
}

function renderRunRibbon(payload) {
  const chips = [];
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
    chips.push([t("status"), payload.status]);
  }
  el.runRibbon.className = chips.length ? "run-ribbon" : "run-ribbon muted";
  el.runRibbon.innerHTML = chips.length
    ? chips.map(([label, value]) => `<span class="ribbon-chip">${escapeHtml(label)}: ${escapeHtml(value)}</span>`).join("")
    : `<span>${escapeHtml(t("runIdle"))}</span>`;
}

function renderTrace(url, label) {
  if (!url) {
    el.traceValue.textContent = "-";
    return;
  }
  el.traceValue.innerHTML = "";
  const link = document.createElement("a");
  link.href = url;
  link.textContent = traceLabel(label || url);
  el.traceValue.appendChild(link);
}

function renderWarnings(warnings) {
  el.warnings.innerHTML = "";
  if (!warnings.length) {
    const item = document.createElement("li");
    item.textContent = t("none");
    el.warnings.appendChild(item);
    return;
  }
  for (const warning of warnings) {
    const item = document.createElement("li");
    item.textContent = warning.message || warning.type || t("warning");
    el.warnings.appendChild(item);
  }
}

function renderArtifacts(artifacts) {
  el.artifacts.innerHTML = "";
  if (!artifacts.length) {
    const item = document.createElement("li");
    item.textContent = t("none");
    el.artifacts.appendChild(item);
    return;
  }
  for (const artifact of artifacts.slice(0, 8)) {
    const item = document.createElement("li");
    const type = artifact.type || t("artifact");
    const path = artifact.path || artifact.relative_path || "";
    item.textContent = path ? `${type}: ${traceLabel(path)}` : type;
    el.artifacts.appendChild(item);
  }
}

function timelineForPayload(payload) {
  if (!payload) {
    return [];
  }
  if (Array.isArray(payload.tool_call_timeline) && payload.tool_call_timeline.length) {
    return payload.tool_call_timeline;
  }
  if (Array.isArray(payload.timeline)) {
    return payload.timeline;
  }
  if (payload.run && Array.isArray(payload.run.steps)) {
    return payload.run.steps;
  }
  return [];
}

function renderTimeline(steps) {
  el.timeline.innerHTML = "";
  if (!steps.length) {
    const item = document.createElement("li");
    item.textContent = t("timelineEmpty");
    el.timeline.appendChild(item);
    return;
  }
  for (const step of steps) {
    const item = document.createElement("li");
    item.className = step.status || "";
    if (isToolCallTimelineStep(step)) {
      item.classList.add("tool-call-row");
      item.innerHTML = toolCallTimelineHtml(step);
      el.timeline.appendChild(item);
      continue;
    }
    const name = step.name || t("step");
    const kind = step.kind ? ` · ${step.kind}` : "";
    const counts = [];
    if (step.artifact_count) {
      counts.push(`${step.artifact_count} ${t("artifactCount")}`);
    }
    if (step.error_count) {
      counts.push(`${step.error_count} ${t("errorCount")}`);
    }
    const suffix = counts.length ? ` · ${counts.join(", ")}` : "";
    item.innerHTML = `<div><strong>${escapeHtml(name)}</strong><span>${escapeHtml((step.status || t("unknown")) + kind + suffix)}</span></div>`;
    el.timeline.appendChild(item);
  }
}

async function renderActiveDrilldown() {
  if (!el.drilldownContent) {
    return;
  }
  for (const tab of document.querySelectorAll(".drill-tab")) {
    tab.classList.toggle("active", tab.dataset.drill === state.activeDrilldown);
  }
  if (!state.lastPayload) {
    setDrilldownStatus(t("runIdle"), true);
    el.drilldownContent.innerHTML = `<p>${escapeHtml(t("drilldownEmpty"))}</p>`;
    return;
  }
  setDrilldownStatus(t("loading"), true);
  el.drilldownContent.innerHTML = `<p>${escapeHtml(t("loading"))}</p>`;
  try {
    let html = "";
    if (state.activeDrilldown === "hqs") {
      html = await renderHqsDrilldown(state.lastPayload);
    } else if (state.activeDrilldown === "memory") {
      html = await renderMemoryDrilldown(state.lastPayload);
    } else if (state.activeDrilldown === "diff") {
      html = await renderSkillDiffDrilldown(state.lastPayload);
    } else {
      html = await renderTraceDrilldown(state.lastPayload);
    }
    el.drilldownContent.innerHTML = html;
    setDrilldownStatus(drilldownLabel(state.activeDrilldown), false);
  } catch (error) {
    el.drilldownContent.innerHTML = `<p class="status-error">${escapeHtml(error.message || String(error))}</p>`;
    setDrilldownStatus(t("errors"), false);
  }
}

async function renderTraceDrilldown(payload) {
  const url = payload.trace_url || traceUrlFromPath(payload.trace_path);
  if (!url) {
    return `<p>${escapeHtml(t("noTrace"))}</p>`;
  }
  const trace = await getJson(url);
  const steps = Array.isArray(trace.steps) ? trace.steps : [];
  const artifacts = Array.isArray(trace.artifacts) ? trace.artifacts : [];
  const errors = Array.isArray(trace.errors) ? trace.errors : [];
  const executionState = (trace.output && trace.output.execution_state) || payload.execution_state || {};
  return [
    `<div class="drill-meta">${chipHtml(t("type"), trace.type)}${chipHtml(t("trace"), trace.trace_id)}${chipHtml(t("schema"), schemaLabel(trace))}</div>`,
    renderExecutionState(executionState),
    `<h3>${escapeHtml(t("steps"))}</h3>`,
    steps.length ? `<ol class="drill-steps">${steps.map(traceStepHtml).join("")}</ol>` : `<p>${escapeHtml(t("timelineEmpty"))}</p>`,
    `<h3>${escapeHtml(t("artifacts"))}</h3>`,
    artifacts.length ? `<ul class="drill-list">${artifacts.map((item) => `<li>${escapeHtml(item.type || t("artifact"))}: ${escapeHtml(traceLabel(item.path || ""))}</li>`).join("")}</ul>` : `<p>${escapeHtml(t("none"))}</p>`,
    `<h3>${escapeHtml(t("errors"))}</h3>`,
    errors.length ? `<ul class="drill-list warning">${errors.map((item) => `<li>${escapeHtml(item.error_type || t("errors"))}: ${escapeHtml(item.message || "")}</li>`).join("")}</ul>` : `<p>${escapeHtml(t("none"))}</p>`
  ].join("");
}

async function renderHqsDrilldown(payload) {
  let hqsPayload = payload;
  if (!payload.hqs && !payload.system_hqs) {
    hqsPayload = await getJson("/hqs");
  }
  const response = payload.hqs || hqsPayload.last_response_hqs;
  const system = payload.system_hqs || hqsPayload.last_system_hqs || hqsPayload.current_system_hqs;
  return [
    renderScoreReport(t("response"), response),
    renderScoreReport(t("system"), system)
  ].join("");
}

async function renderMemoryDrilldown(payload) {
  const memory = await getJson("/memory");
  const retrieval = payload.memory_retrieval || (payload.memory_context && payload.memory_context.retrieval) || null;
  const latestEpisodes = Array.isArray(memory.latest_episodes) ? memory.latest_episodes.slice(-4).reverse() : [];
  const semanticValues = memory.semantic_memory && typeof memory.semantic_memory === "object"
    ? Object.values(memory.semantic_memory).slice(0, 6)
    : [];
  return [
    `<div class="drill-meta">${chipHtml(t("episodes"), memory.episode_count)}${chipHtml(t("semantic"), memory.semantic_count)}</div>`,
    `<h3>${escapeHtml(t("retrieval"))}</h3>`,
    retrieval ? renderRetrievalSummary(retrieval) : `<p>${escapeHtml(t("none"))}</p>`,
    `<h3>${escapeHtml(t("latestEpisodes"))}</h3>`,
    latestEpisodes.length
      ? `<ul class="drill-list">${latestEpisodes.map((item) => `<li><strong>${escapeHtml(item.episode_id || t("episode"))}</strong><span>${escapeHtml(item.intent && item.intent.intent_type || item.user_input || "")}</span></li>`).join("")}</ul>`
      : `<p>${escapeHtml(t("none"))}</p>`,
    `<h3>${escapeHtml(t("semanticMemory"))}</h3>`,
    semanticValues.length
      ? `<ul class="drill-list">${semanticValues.map((item) => `<li><strong>${escapeHtml(item.key || t("memory"))}</strong><span>${escapeHtml(item.summary || item.best_version || "")}</span></li>`).join("")}</ul>`
      : `<p>${escapeHtml(t("none"))}</p>`
  ].join("");
}

async function renderSkillDiffDrilldown(payload) {
  const identity = skillIdentityFromPayload(payload);
  if (!identity) {
    return `<p>${escapeHtml(t("noDiff"))}</p>`;
  }
  const detail = await getJson(`/skills/${encodeURIComponent(identity.skill_slug)}/${encodeURIComponent(identity.version)}`);
  const metadata = detail.metadata || {};
  const diff = detail.diff || "";
  return [
    `<div class="drill-meta">${chipHtml(t("skill"), detail.skill_slug)}${chipHtml(t("versionLabel"), detail.version)}${chipHtml(t("skillSource"), detail.source)}</div>`,
    metadata && Object.keys(metadata).length ? renderMetadataTable(metadata) : "",
    `<h3>${escapeHtml(t("diff"))}</h3>`,
    diff ? `<pre class="diff-block">${escapeHtml(diff)}</pre>` : `<p>${escapeHtml(t("noDiff"))}</p>`
  ].join("");
}

function renderExecutionState(executionState) {
  if (!executionState || !executionState.status) {
    return "";
  }
  const transitions = Array.isArray(executionState.transitions) ? executionState.transitions : [];
  return [
    `<h3>${escapeHtml(t("executionState"))}</h3>`,
    `<div class="drill-meta">${chipHtml(t("status"), executionState.status)}${chipHtml(t("completed"), (executionState.completed_steps || []).length)}${chipHtml(t("failed"), (executionState.failed_steps || []).length)}${chipHtml(t("skipped"), (executionState.skipped_steps || []).length)}</div>`,
    transitions.length
      ? `<ol class="drill-steps compact">${transitions.slice(-8).map((transition) => `<li class="${escapeHtml(transition.to_status || transition.status || "")}"><strong>${escapeHtml(transition.plan_step_name || transition.event || t("transition"))}</strong><span>${escapeHtml(transition.reason || transition.to_status || transition.status || "")}</span></li>`).join("")}</ol>`
      : ""
  ].join("");
}

function renderScoreReport(title, report) {
  if (!report) {
    return `<h3>${escapeHtml(title)}</h3><p>${escapeHtml(t("none"))}</p>`;
  }
  const scores = report.scores && typeof report.scores === "object" ? report.scores : {};
  return [
    `<h3>${escapeHtml(title)}</h3>`,
    `<div class="drill-meta">${chipHtml(t("avg"), formatScore(report.average_score))}${chipHtml(t("confidence"), formatScore(report.confidence))}</div>`,
    `<div class="dimension-list">${Object.entries(scores).map(([name, score]) => dimensionHtml(name, score)).join("")}</div>`
  ].join("");
}

function renderRetrievalSummary(retrieval) {
  const episodeScores = Array.isArray(retrieval.episode_scores) ? retrieval.episode_scores : [];
  const semanticScores = Array.isArray(retrieval.semantic_scores) ? retrieval.semantic_scores : [];
  return [
    `<div class="drill-meta">${chipHtml(t("query"), retrieval.query)}${chipHtml(t("episodes"), retrieval.episode_count)}${chipHtml(t("semantic"), retrieval.semantic_count)}</div>`,
    retrievalRows(t("episodes"), episodeScores),
    retrievalRows(t("semantic"), semanticScores)
  ].join("");
}

function retrievalRows(title, rows) {
  if (!rows.length) {
    return `<h4>${escapeHtml(title)}</h4><p>${escapeHtml(t("none"))}</p>`;
  }
  return [
    `<h4>${escapeHtml(title)}</h4>`,
    `<ul class="drill-list">${rows.map((row) => `<li><strong>#${escapeHtml(row.rank || "-")} ${escapeHtml(row.key || t("memory"))}</strong><span>${escapeHtml(t("score"))} ${escapeHtml(row.score || 0)} · ${(row.reasons || []).map(escapeHtml).join(", ")}</span></li>`).join("")}</ul>`
  ].join("");
}

function renderMetadataTable(metadata) {
  const rows = Object.entries(metadata)
    .filter(([key]) => ["previous_version", "new_version", "hqs_average", "candidate_improvement", "decision", "created_at", "diff_path"].includes(key))
    .map(([key, value]) => `<dt>${escapeHtml(key)}</dt><dd>${escapeHtml(formatMetadataValue(value))}</dd>`)
    .join("");
  return rows ? `<dl class="drill-kv">${rows}</dl>` : "";
}

function isToolCallTimelineStep(step) {
  return Boolean(
    step &&
    (
      step.model_decision ||
      step.decision_type ||
      step.tool_name ||
      step.validation ||
      step.observation ||
      step.observation_summary ||
      step.parse_repair ||
      step.tool_result
    )
  );
}

function toolCallTimelineHtml(step) {
  const status = step.status || t("unknown");
  const name = step.tool_name || step.name || step.decision_type || t("step");
  const decisionType = step.decision_type || (step.model_decision && step.model_decision.type) || "";
  const badges = [
    chipHtml(t("status"), status),
    decisionType ? chipHtml(t("decision"), decisionType) : "",
    step.iteration ? chipHtml(t("iterations"), step.iteration) : "",
    repairBadgeHtml(step.parse_repair || (step.model_decision && step.model_decision.parse_metadata)),
  ].join("");
  return [
    `<div class="tool-call-head"><strong>${escapeHtml(name)}</strong><span>${badges}</span></div>`,
    `<div class="tool-call-details">`,
    detailJsonHtml(t("modelDecision"), step.model_decision),
    detailJsonHtml(t("toolArguments"), step.arguments),
    validationHtml(step),
    detailJsonHtml(t("observation"), step.observation_summary || step.observation),
    detailJsonHtml(t("parseRepair"), step.parse_repair || (step.model_decision && step.model_decision.parse_metadata)),
    `</div>`
  ].join("");
}

function validationHtml(step) {
  const validation = step.validation;
  const errors = Array.isArray(step.validation_errors) ? step.validation_errors : [];
  if (!validation && !errors.length && !(Array.isArray(step.errors) && step.errors.length)) {
    return "";
  }
  const extraErrors = Array.isArray(step.errors) ? step.errors : [];
  const errorHtml = [...errors, ...extraErrors].length
    ? `<ul class="validation-errors">${[...errors, ...extraErrors].map((error) => `<li>${escapeHtml(formatMetadataValue(error))}</li>`).join("")}</ul>`
    : "";
  return [
    `<details class="tool-call-detail validation-detail" ${errors.length || extraErrors.length ? "open" : ""}>`,
    `<summary>${escapeHtml(t("validation"))}</summary>`,
    validation ? jsonBlockHtml(validation) : "",
    errorHtml,
    `</details>`
  ].join("");
}

function repairBadgeHtml(metadata) {
  if (!metadata || metadata.repaired !== true) {
    return "";
  }
  return `<span class="badge repair-badge">${escapeHtml(t("repaired"))}: ${escapeHtml(metadata.repair_strategy || t("unknown"))}</span>`;
}

function detailJsonHtml(label, value) {
  if (value === undefined || value === null || value === "" || (typeof value === "object" && !Object.keys(value).length)) {
    return "";
  }
  return [
    `<details class="tool-call-detail">`,
    `<summary>${escapeHtml(label)}</summary>`,
    jsonBlockHtml(value),
    `</details>`
  ].join("");
}

function jsonBlockHtml(value) {
  const text = typeof value === "string" ? value : JSON.stringify(value, null, 2);
  return `<pre class="json-block">${escapeHtml(text)}</pre>`;
}

function traceStepHtml(step) {
  if (isToolCallTimelineStep(step)) {
    return `<li class="${escapeHtml(step.status || "")} tool-call-row">${toolCallTimelineHtml(step)}</li>`;
  }
  const status = step.status || t("unknown");
  const name = step.name || step.step_id || t("step");
  const detail = step.kind || step.tool_name || step.error_type || "";
  return `<li class="${escapeHtml(status)}"><strong>${escapeHtml(name)}</strong><span>${escapeHtml(status + (detail ? ` · ${detail}` : ""))}</span></li>`;
}

function dimensionHtml(name, score) {
  const numeric = typeof score === "number" ? score : Number(score || 0);
  const width = Math.max(0, Math.min(100, (numeric / 5) * 100));
  return `<div class="dimension"><span>${escapeHtml(name)}</span><strong>${escapeHtml(formatScore(numeric))}</strong><div class="scorebar"><span style="width:${width}%"></span></div></div>`;
}

function chipHtml(label, value) {
  if (value === undefined || value === null || value === "") {
    return "";
  }
  return `<span class="badge">${escapeHtml(label)}: ${escapeHtml(String(value))}</span>`;
}

function setDrilldownStatus(text, muted) {
  if (!el.drilldownStatus) {
    return;
  }
  el.drilldownStatus.textContent = text;
  el.drilldownStatus.className = muted ? "badge muted" : "badge";
}

function drilldownLabel(name) {
  if (name === "hqs") {
    return t("hqs");
  }
  if (name === "memory") {
    return t("memory");
  }
  if (name === "diff") {
    return t("skillDiff");
  }
  return t("trace");
}

function schemaLabel(trace) {
  const schema = trace.schema || trace.embedded_schema || {};
  return schema.name || schema.version || "trace";
}

function traceUrlFromPath(path) {
  if (!path) {
    return null;
  }
  return `/traces/${encodeURIComponent(traceLabel(path))}`;
}

function skillIdentityFromPayload(payload) {
  const selected = payload.selected_skill || (payload.execution && payload.execution.selected_skill);
  if (selected && selected.skill_slug && selected.version) {
    return { skill_slug: selected.skill_slug, version: selected.version };
  }
  if (payload.skill_slug && payload.version) {
    return { skill_slug: payload.skill_slug, version: payload.version };
  }
  const paths = [
    payload.relative_final_skill_path,
    payload.final_skill_path,
    payload.relative_skill_path,
    payload.skill_path
  ].filter(Boolean);
  for (const path of paths) {
    const match = String(path).replaceAll("\\", "/").match(/(?:^|\/)(?:skills|examples\/skills)\/([^/]+)\/([^/]+)\/SKILL\.md$/);
    if (match) {
      return { skill_slug: match[1], version: match[2] };
    }
  }
  return null;
}

function formatScore(score) {
  return typeof score === "number" && Number.isFinite(score) ? score.toFixed(2) : "-";
}

function formatMetadataValue(value) {
  if (Array.isArray(value)) {
    return value.join(", ");
  }
  if (value && typeof value === "object") {
    return JSON.stringify(value);
  }
  return value === undefined || value === null ? "" : String(value);
}

function renderError(message) {
  el.result.classList.remove("empty");
  renderRunRibbon({ status: "error" });
  setResultContent(`<p class="status-error">${escapeHtml(message)}</p>`);
}

function setScore(element, score) {
  element.textContent = typeof score === "number" ? score.toFixed(2) : "-";
  const bar = element === el.responseScore ? el.responseScoreBar : el.systemScoreBar;
  if (bar) {
    bar.style.width = typeof score === "number" ? `${Math.max(0, Math.min(100, (score / 5) * 100))}%` : "0%";
  }
}

function clearScores() {
  el.responseScore.textContent = "-";
  el.systemScore.textContent = "-";
  el.responseScoreBar.style.width = "0%";
  el.systemScoreBar.style.width = "0%";
}

function formatSkill(skill) {
  if (!skill) {
    return "-";
  }
  const title = skill.title || skill.skill_slug || "Skill";
  const version = skill.version ? ` ${skill.version}` : "";
  const source = skill.source ? ` (${skill.source})` : "";
  return `${title}${version}${source}`;
}

function traceLabel(path) {
  const normalized = String(path).replaceAll("\\", "/");
  return normalized.split("/").pop() || path;
}

function setDebug(payload) {
  el.debugOutput.textContent = JSON.stringify(payload, null, 2);
  void renderActiveDrilldown();
}

function selectSkillPath(select, path) {
  if (!path) {
    return;
  }
  for (const option of select.options) {
    if (option.value === path || option.value.replaceAll("\\", "/") === String(path).replaceAll("\\", "/")) {
      select.value = option.value;
      return;
    }
  }
}

async function getJson(url) {
  const response = await fetch(url);
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.error || `GET ${url} failed`);
  }
  return payload;
}

async function postJson(url, payload) {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.error || `POST ${url} failed`);
  }
  return data;
}

function renderMarkdown(markdown) {
  const lines = String(markdown).replaceAll("\r\n", "\n").split("\n");
  const html = [];
  let listOpen = false;

  for (const line of lines) {
    const trimmed = line.trim();
    if (!trimmed) {
      if (listOpen) {
        html.push("</ul>");
        listOpen = false;
      }
      continue;
    }
    if (trimmed.startsWith("### ")) {
      if (listOpen) {
        html.push("</ul>");
        listOpen = false;
      }
      html.push(`<h3>${inlineMarkdown(trimmed.slice(4))}</h3>`);
      continue;
    }
    if (trimmed.startsWith("## ")) {
      if (listOpen) {
        html.push("</ul>");
        listOpen = false;
      }
      html.push(`<h2>${inlineMarkdown(trimmed.slice(3))}</h2>`);
      continue;
    }
    if (trimmed.startsWith("# ")) {
      if (listOpen) {
        html.push("</ul>");
        listOpen = false;
      }
      html.push(`<h1>${inlineMarkdown(trimmed.slice(2))}</h1>`);
      continue;
    }
    if (trimmed.startsWith("- ")) {
      if (!listOpen) {
        html.push("<ul>");
        listOpen = true;
      }
      html.push(`<li>${inlineMarkdown(trimmed.slice(2))}</li>`);
      continue;
    }
    if (listOpen) {
      html.push("</ul>");
      listOpen = false;
    }
    html.push(`<p>${inlineMarkdown(trimmed)}</p>`);
  }

  if (listOpen) {
    html.push("</ul>");
  }
  return html.join("\n");
}

function inlineMarkdown(text) {
  let escaped = escapeHtml(text);
  escaped = escaped.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
  escaped = escaped.replace(/`(.+?)`/g, "<code>$1</code>");
  return escaped;
}

function escapeHtml(text) {
  return String(text)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

init();
