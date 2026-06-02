const i18n = {
  en: {
    statusLoading: "Checking local runtime...",
    health: "Health",
    skills: "Skills",
    tasksets: "Tasksets",
    traces: "Traces",
    runMode: "Run Mode",
    runModeHelp: "Use local deterministic mode or call the default configured model provider.",
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
    none: "None",
    timeline: "Timeline",
    timelineEmpty: "No run yet.",
    debugJson: "Debug JSON",
    running: "Running...",
    noResponse: "No response.",
    generated: "Generated Skill",
    generatedBody: "Skill generated and validated.",
    runOutput: "Skill Output",
    evolveResult: "Evolution Result",
    missingSkills: "No Skills found.",
    missingTasksets: "No tasksets found.",
    providerMode: "provider",
    localMode: "local"
  },
  zh: {
    statusLoading: "正在检查本地运行状态...",
    health: "健康",
    skills: "技能",
    tasksets: "任务集",
    traces: "追踪",
    runMode: "运行模式",
    runModeHelp: "使用本地确定性模式，或调用默认配置的大模型 Provider。",
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
    trace: "Trace",
    warnings: "警告",
    none: "无",
    timeline: "Timeline",
    timelineEmpty: "暂无运行。",
    debugJson: "调试 JSON",
    running: "运行中...",
    noResponse: "没有响应。",
    generated: "已生成 Skill",
    generatedBody: "Skill 已生成并通过校验。",
    runOutput: "Skill 输出",
    evolveResult: "演化结果",
    missingSkills: "没有找到 Skill。",
    missingTasksets: "没有找到任务集。",
    providerMode: "大模型",
    localMode: "本地"
  }
};

const state = {
  lang: localStorage.getItem("agentforge_lang") || "en",
  skills: [],
  tasksets: [],
  lastPayload: null
};

const el = {
  statusText: document.getElementById("statusText"),
  languageToggle: document.getElementById("languageToggle"),
  useProvider: document.getElementById("useProvider"),
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
  responseScore: document.getElementById("responseScore"),
  systemScore: document.getElementById("systemScore"),
  intentValue: document.getElementById("intentValue"),
  planValue: document.getElementById("planValue"),
  skillValue: document.getElementById("skillValue"),
  traceValue: document.getElementById("traceValue"),
  warnings: document.getElementById("warnings"),
  timeline: document.getElementById("timeline"),
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
  renderTimeline(state.lastPayload && state.lastPayload.timeline ? state.lastPayload.timeline : []);
}

async function init() {
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

  for (const tab of document.querySelectorAll(".tab")) {
    tab.addEventListener("click", () => activateTab(tab.dataset.tab));
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

async function loadHealth() {
  el.statusText.textContent = state.lang === "zh" ? "本地 API 已启动" : "Local API running";
  try {
    const payload = await getJson("/health");
    el.statusText.textContent = `Health: ${payload.status || "unknown"}`;
    el.statusText.className = payload.status === "ok" ? "" : "status-warn";
  } catch (error) {
    el.statusText.textContent = "Health: unavailable";
    el.statusText.className = "status-error";
  }
}

async function loadSkills() {
  const payload = await getJson("/skills");
  state.skills = payload.skills || [];
  populateSkillSelect(el.runSkill);
  populateSkillSelect(el.evolveSkill);
}

async function loadTasksets() {
  const payload = await getJson("/tasksets");
  state.tasksets = payload.tasksets || [];
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
    renderError("Message is empty.");
    return;
  }
  await runAction(el.chatSend, async () => {
    const payload = await postJson("/chat", {
      message,
      debug: el.chatDebug.checked,
      ...providerPayload()
    });
    renderChatPayload(payload);
  });
}

async function generateSkill() {
  const input = el.generateInput.value.trim();
  if (!input) {
    renderError("Requirement is empty.");
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
    renderError("Task input is empty.");
    return;
  }
  await runAction(el.runSend, async () => {
    const payload = await postJson("/skills/run", {
      skill_path: skillPath,
      input,
      ...providerPayload()
    });
    renderRunPayload(payload);
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
  });
}

async function runAction(button, action) {
  button.disabled = true;
  const oldText = button.textContent;
  button.textContent = t("running");
  el.result.classList.remove("empty");
  el.result.innerHTML = `<p>${escapeHtml(t("running"))}</p>`;
  try {
    await action();
  } catch (error) {
    renderError(error.message || String(error));
  } finally {
    button.disabled = false;
    button.textContent = oldText;
  }
}

function providerPayload() {
  return {
    use_provider: el.useProvider.checked
  };
}

function updateModeHint() {
  el.modeHint.textContent = el.useProvider.checked ? t("providerModeHint") : t("localModeHint");
}

function renderChatPayload(payload) {
  state.lastPayload = payload;
  el.result.classList.remove("empty");
  el.result.innerHTML = renderMarkdown(payload.response || t("noResponse"));
  setScore(el.responseScore, payload.hqs && payload.hqs.average_score);
  setScore(el.systemScore, payload.system_hqs && payload.system_hqs.average_score);
  el.intentValue.textContent = (payload.intent && (payload.intent.type || payload.intent.intent_type)) || "-";
  el.planValue.textContent = (payload.plan && payload.plan.action) || "-";
  el.skillValue.textContent = formatSkill(payload.selected_skill || (payload.execution && payload.execution.selected_skill));
  renderTrace(payload.trace_url, payload.trace_file || payload.trace_path);
  renderWarnings(payload.warnings || []);
  renderTimeline(payload.timeline || (payload.run && payload.run.steps) || []);
  setDebug(payload);
}

function renderGeneratePayload(payload) {
  state.lastPayload = payload;
  const lines = [
    `# ${t("generated")}`,
    "",
    `- ${t("generatedBody")}`,
    `- Skill: ${payload.skill_name || payload.skill_slug}`,
    `- Version: ${payload.version}`,
    `- Mode: ${payload.generation_mode}`,
    `- Path: ${payload.relative_skill_path || payload.skill_path}`
  ];
  el.result.classList.remove("empty");
  el.result.innerHTML = renderMarkdown(lines.join("\n"));
  clearScores();
  el.intentValue.textContent = "generate_skill";
  el.planValue.textContent = "generate_skill";
  el.skillValue.textContent = `${payload.skill_slug} ${payload.version}`;
  renderTrace(payload.trace_url, payload.trace_path);
  renderWarnings([]);
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
    "## Artifacts",
    "",
    `- Mode: ${payload.mode}`,
    `- Run: ${payload.relative_run_dir || payload.run_dir}`
  ];
  el.result.classList.remove("empty");
  el.result.innerHTML = renderMarkdown(lines.join("\n"));
  clearScores();
  el.intentValue.textContent = "run_skill";
  el.planValue.textContent = "run_skill";
  el.skillValue.textContent = payload.relative_skill_path || payload.skill_path || "-";
  renderTrace(payload.trace_url, payload.trace_path);
  renderWarnings([]);
  renderTimeline([]);
  setDebug(payload);
}

function renderEvolvePayload(payload) {
  state.lastPayload = payload;
  const lines = [
    `# ${t("evolveResult")}`,
    "",
    `- Stop reason: ${payload.stop_reason}`,
    `- Final Skill: ${payload.relative_final_skill_path || payload.final_skill_path}`,
    `- Iterations: ${payload.iterations ? payload.iterations.length : 0}`,
    "",
    "## Iterations",
    ""
  ];
  for (const item of payload.iterations || []) {
    lines.push(
      `- #${item.iteration}: HQS ${item.average_hqs}, decision ${item.decision}` +
      (item.candidate_average_hqs !== null ? `, candidate ${item.candidate_average_hqs}` : "")
    );
  }
  el.result.classList.remove("empty");
  el.result.innerHTML = renderMarkdown(lines.join("\n"));
  clearScores();
  el.intentValue.textContent = "evolve_skill";
  el.planValue.textContent = "evolve_skill";
  el.skillValue.textContent = payload.relative_final_skill_path || payload.final_skill_path || "-";
  renderTrace(payload.trace_url, payload.trace_path);
  renderWarnings([]);
  renderTimeline([]);
  setDebug(payload);
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
    item.textContent = warning.message || warning.type || "Warning";
    el.warnings.appendChild(item);
  }
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
    const name = step.name || "step";
    const kind = step.kind ? ` · ${step.kind}` : "";
    const counts = [];
    if (step.artifact_count) {
      counts.push(`${step.artifact_count} artifact`);
    }
    if (step.error_count) {
      counts.push(`${step.error_count} error`);
    }
    const suffix = counts.length ? ` · ${counts.join(", ")}` : "";
    item.innerHTML = `<div><strong>${escapeHtml(name)}</strong><span>${escapeHtml((step.status || "unknown") + kind + suffix)}</span></div>`;
    el.timeline.appendChild(item);
  }
}

function renderError(message) {
  el.result.classList.remove("empty");
  el.result.innerHTML = `<p class="status-error">${escapeHtml(message)}</p>`;
}

function setScore(element, score) {
  element.textContent = typeof score === "number" ? score.toFixed(2) : "-";
}

function clearScores() {
  el.responseScore.textContent = "-";
  el.systemScore.textContent = "-";
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
