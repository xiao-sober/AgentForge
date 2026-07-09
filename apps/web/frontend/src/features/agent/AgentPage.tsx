import { useRef, useState, type ChangeEvent, type KeyboardEvent } from "react";
import type { I18nKey } from "../../i18n";
import type {
  AgentMode,
  ArtifactItem,
  Lang,
  ProgressState,
  TimelineStep,
  UploadedFileRecord,
  WebPayload,
  WarningItem
} from "../../types";
import {
  escapeHtml,
  formatScore,
  markdownToHtml,
  objectValue,
  scoreNumber,
  stringValue,
  timelineForPayload,
  traceLabel
} from "../../view-model";
import { apiUrl, uploadFiles } from "../../api";

interface AgentPageProps {
  lang: Lang;
  t: (key: I18nKey) => string;
  message: string;
  agentMode: AgentMode;
  running: boolean;
  progress: ProgressState | null;
  elapsedSeconds: number;
  payload: WebPayload | null;
  error: string;
  uploads: UploadedFileRecord[];
  onMessage: (value: string) => void;
  onUploads: (files: UploadedFileRecord[]) => void;
  onRemoveUpload: (uploadId: string) => void;
  onAgentMode: (value: AgentMode) => void;
  onSubmit: () => void;
  onOpenDetails: () => void;
}

interface QuickTask {
  labelZh: string;
  labelEn: string;
  promptZh: string;
  promptEn: string;
}

const quickTasks: QuickTask[] = [
  {
    labelZh: "诊断运行记录",
    labelEn: "Diagnose run",
    promptZh: "帮我检查最近一次运行记录：哪里失败了、为什么会失败、下一步怎么修。",
    promptEn: "Help me inspect the latest run record: where it failed, why it likely failed, and what to fix next."
  },
  {
    labelZh: "分析代码",
    labelEn: "Analyze code",
    promptZh: "帮我快速检查当前项目代码，指出最值得优先修的 3 个问题，并给出对应文件和修改建议。",
    promptEn: "Review the current project code and highlight the top 3 issues to fix first, with files and concrete suggestions."
  },
  {
    labelZh: "分析文档",
    labelEn: "Analyze docs",
    promptZh: "帮我阅读项目文档，告诉我当前说明是否清楚、缺了什么、哪些地方容易让用户误解。",
    promptEn: "Read the project docs and tell me what is clear, what is missing, and what could confuse users."
  },
  {
    labelZh: "分析数据",
    labelEn: "Analyze data",
    promptZh: "帮我分析项目里的数据文件，先说明有哪些字段和异常，再给出适合继续看的图表或结论方向。",
    promptEn: "Analyze the project data files. Summarize fields and anomalies first, then suggest useful charts or next conclusions."
  },
  {
    labelZh: "生成 Skill",
    labelEn: "Generate Skill",
    promptZh: "帮我把下面这个需求整理成一个可复用的 Skill，包含使用场景、输入输出、步骤和质量标准：",
    promptEn: "Turn the following requirement into a reusable Skill with usage conditions, inputs, outputs, workflow, and quality criteria:"
  },
  {
    labelZh: "进化 Skill",
    labelEn: "Evolve Skill",
    promptZh: "帮我根据最近的运行结果改进相关 Skill，说明要改哪里、为什么改、预期能提升什么。",
    promptEn: "Improve the relevant Skill based on recent run results. Explain what to change, why, and what should improve."
  }
];

const uploadAccept = [
  ".png",
  ".jpg",
  ".jpeg",
  ".gif",
  ".webp",
  ".bmp",
  ".svg",
  ".py",
  ".js",
  ".jsx",
  ".ts",
  ".tsx",
  ".css",
  ".scss",
  ".html",
  ".htm",
  ".sql",
  ".yaml",
  ".yml",
  ".toml",
  ".xml",
  ".txt",
  ".md",
  ".markdown",
  ".rst",
  ".adoc",
  ".pdf",
  ".doc",
  ".docx",
  ".rtf",
  ".csv",
  ".tsv",
  ".json",
  ".jsonl",
  ".ndjson",
  ".xls",
  ".xlsx",
  ".ppt",
  ".pptx"
].join(",");

export function AgentPage({
  lang,
  t,
  message,
  agentMode,
  running,
  progress,
  elapsedSeconds,
  payload,
  error,
  uploads,
  onMessage,
  onUploads,
  onRemoveUpload,
  onAgentMode,
  onSubmit,
  onOpenDetails
}: AgentPageProps) {
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState("");

  function copy(zh: string, en: string) {
    return lang === "zh" ? zh : en;
  }

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if ((event.ctrlKey || event.metaKey) && event.key === "Enter") {
      event.preventDefault();
      onSubmit();
    }
  }

  async function handleUploadChange(event: ChangeEvent<HTMLInputElement>) {
    const selected = Array.from(event.target.files || []);
    event.target.value = "";
    if (!selected.length) {
      return;
    }

    setUploading(true);
    setUploadError("");
    try {
      const payload = await uploadFiles(selected);
      onUploads(payload.uploads);
      if (shouldReplaceComposerText(message)) {
        onMessage(uploadPromptFor([...uploads, ...payload.uploads], lang));
      }
    } catch (uploadIssue) {
      const text = uploadIssue instanceof Error ? uploadIssue.message : String(uploadIssue);
      setUploadError(text);
    } finally {
      setUploading(false);
    }
  }

  return (
    <section className="agent-page agent-chat-page" aria-labelledby="agent-title">
      <div className="agent-context-bar">
        <div className="agent-context-copy">
          <span className="eyebrow">{copy("对话式 Agent 工作台", "Conversational Agent workspace")}</span>
          <h2 id="agent-title">AgentForge</h2>
          <p>
            {copy(
              "把任务直接交给 AgentForge。结果、证据和质量检查会留在中间窗口，历史运行在左侧切换。",
              "Give AgentForge a task directly. Results, evidence, and quality checks stay in the center while run history is available on the left."
            )}
          </p>
        </div>
        <ModeSelector lang={lang} mode={agentMode} onMode={onAgentMode} />
      </div>

      <div className="agent-conversation-window">
        {progress ? (
          <RunProgress lang={lang} progress={progress} elapsedSeconds={elapsedSeconds} />
        ) : (
          <AgentResult lang={lang} payload={payload} error={error} onOpenDetails={onOpenDetails} />
        )}
      </div>

      <section className="agent-composer-dock" aria-label={copy("Agent 任务输入", "Agent task input")}>
        <div className="composer-bubbles" aria-label={copy("快捷任务", "Quick tasks")}>
          {quickTasks.map((task) => (
            <button
              className="quick-chip"
              key={task.labelEn}
              type="button"
              onClick={() => onMessage(copy(task.promptZh, task.promptEn))}
            >
              {copy(task.labelZh, task.labelEn)}
            </button>
          ))}
          <input
            ref={fileInputRef}
            className="upload-input"
            type="file"
            multiple
            accept={uploadAccept}
            onChange={handleUploadChange}
          />
          <button
            className="quick-chip upload-quick-action"
            disabled={running || uploading}
            type="button"
            onClick={() => fileInputRef.current?.click()}
          >
            {uploading ? copy("上传中", "Uploading") : copy("上传文件", "Upload files")}
          </button>
        </div>

        {uploadError || uploads.length ? (
          <div className="upload-toolbar">
            {uploadError ? <span className="upload-error">{uploadError}</span> : null}
            {uploads.length ? (
              <div className="upload-strip" aria-label={copy("已上传文件", "Uploaded files")}>
                {uploads.map((file) => (
                  <article className={`upload-chip ${file.kind}`} key={file.upload_id}>
                    {file.kind === "image" ? (
                      <img className="upload-thumb" src={apiUrl(file.url)} alt="" />
                    ) : (
                      <span className="upload-kind">{uploadKindLabel(file.kind)}</span>
                    )}
                    <span>
                      <strong>{file.original_name}</strong>
                      <small>{uploadMeta(file, lang)}</small>
                    </span>
                    <button
                      type="button"
                      aria-label={copy(`移除 ${file.original_name}`, `Remove ${file.original_name}`)}
                      onClick={() => onRemoveUpload(file.upload_id)}
                    >
                      ×
                    </button>
                  </article>
                ))}
              </div>
            ) : null}
          </div>
        ) : null}

        <div className="composer-input-row">
          <textarea
            aria-label={copy("任务内容", "Task message")}
            className="agent-input"
            disabled={running}
            value={message}
            onChange={(event) => onMessage(event.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={copy("输入任务，Ctrl/⌘ + Enter 运行。", "Enter a task. Press Ctrl/⌘ + Enter to run.")}
          />
          <div className="composer-actions">
            <button className="primary-action" disabled={running || (!message.trim() && !uploads.length)} type="button" onClick={onSubmit}>
              {running ? copy("运行中", "Running") : copy("运行", "Run")}
            </button>
          </div>
        </div>
      </section>
    </section>
  );
}

function shouldReplaceComposerText(value: string): boolean {
  const trimmed = value.trim();
  return (
    !trimmed ||
    trimmed.includes("最近一次运行记录") ||
    trimmed.includes("latest run record") ||
    trimmed.includes("Analyze the uploaded") ||
    trimmed.includes("请分析我上传")
  );
}

function uploadPromptFor(files: UploadedFileRecord[], lang: Lang): string {
  const kinds = new Set(files.map((file) => file.kind));
  if (kinds.has("data")) {
    return lang === "zh"
      ? "帮我分析上传的数据文件，先说明字段、样本量和异常，再给出可继续追问的结论方向。"
      : "Analyze the uploaded data file. Start with fields, sample size, and anomalies, then suggest useful follow-up questions.";
  }
  if (kinds.has("code")) {
    return lang === "zh"
      ? "帮我检查上传的代码文件，指出最值得优先处理的问题，并给出具体修改建议。"
      : "Review the uploaded code file, identify the highest-priority issues, and give concrete fixes.";
  }
  if (kinds.has("document")) {
    return lang === "zh"
      ? "帮我阅读上传的文档，概括核心内容，并指出不清楚、缺失或容易误解的地方。"
      : "Read the uploaded document, summarize the core content, and flag unclear, missing, or confusing parts.";
  }
  if (kinds.has("image")) {
    return lang === "zh"
      ? "帮我根据上传的图片文件做初步分析，并说明还需要补充哪些背景信息。"
      : "Analyze the uploaded image file and note what extra context would help.";
  }
  return lang === "zh" ? "帮我分析上传的文件。" : "Analyze the uploaded file.";
}

function uploadMeta(file: UploadedFileRecord, lang: Lang): string {
  const taskText = file.supported_tasks.length
    ? file.supported_tasks.map((task) => task.replace("_", " ")).join(", ")
    : lang === "zh"
      ? "已保存"
      : "saved";
  return `${file.kind} · ${formatBytes(file.size_bytes)} · ${taskText}`;
}

function uploadKindLabel(kind: string): string {
  if (kind === "data") return "DATA";
  if (kind === "code") return "</>";
  if (kind === "document") return "DOC";
  if (kind === "image") return "IMG";
  return "FILE";
}

function formatBytes(bytes: number): string {
  if (!Number.isFinite(bytes) || bytes <= 0) {
    return "0 B";
  }
  const units = ["B", "KB", "MB", "GB"];
  let value = bytes;
  let index = 0;
  while (value >= 1024 && index < units.length - 1) {
    value /= 1024;
    index += 1;
  }
  return `${value >= 10 || index === 0 ? value.toFixed(0) : value.toFixed(1)} ${units[index]}`;
}

function ModeSelector({
  lang,
  mode,
  onMode
}: {
  lang: Lang;
  mode: AgentMode;
  onMode: (value: AgentMode) => void;
}) {
  const copy = (zh: string, en: string) => (lang === "zh" ? zh : en);
  const modes: Array<{
    value: AgentMode;
    label: string;
    summary: string;
    detail: string;
  }> = [
    {
      value: "harness_workflow",
      label: copy("工作流模式", "Workflow Mode"),
      summary: copy("更稳、更可复现", "Stable and repeatable"),
      detail: copy(
        "适合分析代码、诊断运行记录、分析文档、检查数据、生成或改进 Skill。",
        "Best for code analysis, trace diagnosis, document/data analysis, and Skill generation or evolution."
      )
    },
    {
      value: "tool_calling",
      label: copy("自主Agent", "Autonomous Agent"),
      summary: copy("更灵活、更探索", "Flexible and exploratory"),
      detail: copy(
        "模型会根据上下文决定下一步使用什么能力，建议在需要时打开详细记录查看过程。",
        "The model decides which capability to use next. Open details when you need to audit the process."
      )
    }
  ];

  return (
    <section className="mode-panel" aria-label={copy("运行方式", "Execution mode")}>
      <div className="segmented-control" role="tablist" aria-label={copy("选择运行方式", "Choose execution mode")}>
        {modes.map((item) => (
          <button
            aria-selected={mode === item.value}
            className={mode === item.value ? "segment active" : "segment"}
            key={item.value}
            role="tab"
            type="button"
            onClick={() => onMode(item.value)}
          >
            {item.label}
          </button>
        ))}
      </div>
      <div className="mode-explain-grid">
        {modes.map((item) => (
          <article className={mode === item.value ? "mode-card active" : "mode-card"} key={item.value}>
            <div>
              <strong>{item.label}</strong>
              <span>{item.summary}</span>
            </div>
            <p>{item.detail}</p>
          </article>
        ))}
      </div>
    </section>
  );
}

function RunProgress({
  lang,
  progress,
  elapsedSeconds
}: {
  lang: Lang;
  progress: ProgressState;
  elapsedSeconds: number;
}) {
  const copy = (zh: string, en: string) => (lang === "zh" ? zh : en);
  const activeIndex = Math.min(progress.phases.length - 1, Math.floor(elapsedSeconds / 6));
  return (
    <section className="agent-run-panel" aria-live="polite">
      <div className="run-panel-head">
        <div>
          <h3>{copy("Agent 正在处理", "Agent is working")}</h3>
          <p>{copy("阶段状态会持续更新；详细工具调用保存在运行记录里。", "Stage status updates here; detailed tool calls are kept in the run record.")}</p>
        </div>
        <span className="badge">
          {elapsedSeconds}s
        </span>
      </div>
      <ol className="agent-progress-timeline">
        {progress.phases.map((phase, index) => {
          const className = index < activeIndex ? "completed" : index === activeIndex ? "running" : "pending";
          return (
            <li className={className} key={phase}>
              <span className="node-marker" />
              <div>
                <strong>{phase}</strong>
                <small>{statusCopy(className, lang)}</small>
              </div>
            </li>
          );
        })}
      </ol>
    </section>
  );
}

function AgentResult({
  lang,
  payload,
  error,
  onOpenDetails
}: {
  lang: Lang;
  payload: WebPayload | null;
  error: string;
  onOpenDetails: () => void;
}) {
  const copy = (zh: string, en: string) => (lang === "zh" ? zh : en);
  if (error) {
    return (
      <section className="agent-result-panel error-state" role="alert">
        <div className="result-heading">
          <div>
            <span className="eyebrow danger">{copy("需要处理", "Needs attention")}</span>
            <h3>{copy("这次运行没有完成", "This run did not complete")}</h3>
          </div>
          <button className="secondary action-button" type="button" onClick={onOpenDetails}>
            {copy("查看调试数据", "View debug data")}
          </button>
        </div>
        <p>{error}</p>
        <div className="recovery-grid">
          <span>{copy("可尝试重试当前任务。", "Retry the current task.")}</span>
          <span>{copy("如果是模型配置问题，切换本地模式。", "If this is provider configuration, switch to local mode.")}</span>
          <span>{copy("打开运行记录检查具体阶段。", "Open the run record to inspect the stage.")}</span>
        </div>
      </section>
    );
  }

  if (!payload) {
    return (
      <section className="agent-result-panel empty-state">
        <div>
          <span className="eyebrow">{copy("等待任务", "Ready")}</span>
          <h3>{copy("输入一个任务后，结果会显示在这里。", "Enter a task and the result will appear here.")}</h3>
          <p>{copy("主界面只显示可读结论；原始 JSON 和详细工具调用放在高级详情里。", "The main view shows readable conclusions; raw JSON and detailed tool calls stay in advanced details.")}</p>
        </div>
      </section>
    );
  }

  const response = payload.response || copy("没有返回自然语言回答。", "No natural-language response was returned.");
  const warnings = collectWarnings(payload);
  const hqsScore = scoreNumber(payload.hqs);
  const systemScore = scoreNumber(payload.system_hqs);

  return (
    <section className="agent-result-panel">
      <div className="result-heading">
        <div>
          <span className="eyebrow">{copy("当前结果", "Current result")}</span>
          <h3>{resultTitle(payload, lang)}</h3>
        </div>
        <button className="secondary action-button" type="button" onClick={onOpenDetails}>
          {copy("查看运行记录", "View run record")}
        </button>
      </div>

      <RunEvidenceStrip lang={lang} payload={payload} responseScore={hqsScore} systemScore={systemScore} />

      <div className="assistant-answer" dangerouslySetInnerHTML={{ __html: markdownToHtml(response) }} />

      <TaskResultCard lang={lang} payload={payload} />

      <ArtifactSummary lang={lang} artifacts={payload.artifacts || []} tracePath={payload.trace_path} traceUrl={payload.trace_url} />

      <QualitySummary lang={lang} responseScore={hqsScore} systemScore={systemScore} warnings={warnings} />
    </section>
  );
}

function RunEvidenceStrip({
  lang,
  payload,
  responseScore,
  systemScore
}: {
  lang: Lang;
  payload: WebPayload;
  responseScore?: number;
  systemScore?: number;
}) {
  const copy = (zh: string, en: string) => (lang === "zh" ? zh : en);
  const taskType = taskTypeFromPayload(payload) || copy("通用任务", "General task");
  return (
    <div className="run-evidence-strip">
      <EvidenceItem label={copy("任务类型", "Task type")} value={humanizeIdentifier(taskType)} />
      <EvidenceItem label={copy("运行 ID", "Run ID")} value={payload.run_id || "-"} />
      <EvidenceItem label={copy("运行方式", "Execution mode")} value={modeLabel(payload.agent_mode || "", lang)} />
      <EvidenceItem label={copy("质量检查", "Quality")} value={qualityLabel(responseScore, systemScore, lang)} />
    </div>
  );
}

function EvidenceItem({ label, value }: { label: string; value: string }) {
  return (
    <div className="evidence-item">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function TaskResultCard({ lang, payload }: { lang: Lang; payload: WebPayload }) {
  const copy = (zh: string, en: string) => (lang === "zh" ? zh : en);
  const taskType = taskTypeFromPayload(payload);
  const taskResult = objectValue(payload.task_result);
  const output = objectValue(taskResult?.output);
  const analysis = objectValue(output?.analysis);

  if (taskType === "code_analysis" || taskType === "document_analysis" || taskType === "data_analysis") {
    const summary = objectValue(analysis?.summary) || objectValue(output?.summary) || {};
    const findings = Array.isArray(analysis?.findings) ? analysis.findings : [];
    return (
      <section className={`task-result-card ${taskType}`}>
        <div className="task-card-head">
          <div>
            <span className="eyebrow">{taskTypeLabel(taskType, lang)}</span>
            <h4>{copy("结构化任务结果", "Structured task result")}</h4>
          </div>
          <span className="badge">{taskResult?.status ? String(taskResult.status) : copy("已生成", "Ready")}</span>
        </div>
        <MetricGrid metrics={analysisMetrics(taskType, summary, lang)} />
        {findings.length ? <FindingPreview lang={lang} findings={findings} /> : null}
      </section>
    );
  }

  if (taskType === "trace_diagnosis") {
    const diagnosis = objectValue(output?.diagnosis) || output || {};
    return (
      <section className="task-result-card trace-diagnosis">
        <div className="task-card-head">
          <div>
            <span className="eyebrow">{copy("Trace 诊断", "Trace diagnosis")}</span>
            <h4>{copy("关键异常与修复方向", "Key failure and repair direction")}</h4>
          </div>
          <span className="badge">{taskResult?.status ? String(taskResult.status) : copy("已生成", "Ready")}</span>
        </div>
        <dl className="task-kv">
          {Object.entries(diagnosis)
            .slice(0, 6)
            .map(([key, value]) => (
              <FragmentLike key={key} name={humanizeIdentifier(key)} value={formatValue(value)} />
            ))}
        </dl>
      </section>
    );
  }

  if (taskType?.startsWith("skill") || payload.skill_path || payload.final_skill_path || payload.selected_skill) {
    return <SkillAssetCard lang={lang} payload={payload} />;
  }

  return null;
}

function SkillAssetCard({ lang, payload }: { lang: Lang; payload: WebPayload }) {
  const copy = (zh: string, en: string) => (lang === "zh" ? zh : en);
  const selected = payload.selected_skill;
  const name = payload.skill_name || selected?.title || selected?.skill_slug || copy("可复用能力", "Reusable capability");
  const version = payload.version || selected?.version || selected?.latest_version || "-";
  const path = payload.relative_final_skill_path || payload.final_skill_path || payload.relative_skill_path || payload.skill_path || selected?.latest_skill_path || "";

  return (
    <section className="task-result-card skill-asset">
      <div className="task-card-head">
        <div>
          <span className="eyebrow">{copy("Skill 能力资产", "Skill capability asset")}</span>
          <h4>{name}</h4>
        </div>
        <span className="badge">{version}</span>
      </div>
      <dl className="task-kv">
        <FragmentLike name={copy("用途", "Purpose")} value={copy("记录为可复用的 Agent 工作方式。", "Stored as a reusable Agent working pattern.")} />
        <FragmentLike name={copy("复用场景", "Reuse")} value={copy("后续相似任务可自动选择或继续优化。", "Similar future tasks can select or improve it.")} />
        <FragmentLike name={copy("路径", "Path")} value={path || "-"} />
      </dl>
    </section>
  );
}

function FragmentLike({ name, value }: { name: string; value: string }) {
  return (
    <>
      <dt>{name}</dt>
      <dd>{value}</dd>
    </>
  );
}

function MetricGrid({ metrics }: { metrics: Array<{ label: string; value: string; tone?: string }> }) {
  return (
    <div className="task-metric-grid">
      {metrics.map((metric) => (
        <div className={metric.tone ? `task-metric ${metric.tone}` : "task-metric"} key={metric.label}>
          <span>{metric.label}</span>
          <strong>{metric.value}</strong>
        </div>
      ))}
    </div>
  );
}

function FindingPreview({ lang, findings }: { lang: Lang; findings: unknown[] }) {
  const copy = (zh: string, en: string) => (lang === "zh" ? zh : en);
  return (
    <div className="finding-preview">
      <strong>{copy("主要发现", "Key findings")}</strong>
      <ul>
        {findings.slice(0, 4).map((item, index) => {
          const finding = objectValue(item) || {};
          const severity = stringValue(finding.severity) || "info";
          const message = stringValue(finding.message) || stringValue(finding.rule) || formatValue(item);
          const source = stringValue(finding.source);
          return (
            <li className={severity} key={`${message}-${index}`}>
              <span>{severity}</span>
              <div>
                <strong>{message}</strong>
                {source ? <small>{source}</small> : null}
              </div>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

function ArtifactSummary({
  lang,
  artifacts,
  tracePath,
  traceUrl
}: {
  lang: Lang;
  artifacts: ArtifactItem[];
  tracePath?: string;
  traceUrl?: string;
}) {
  const copy = (zh: string, en: string) => (lang === "zh" ? zh : en);
  const items = [...artifacts];
  if (tracePath && !items.some((item) => item.path === tracePath || item.relative_path === tracePath)) {
    items.push({ type: "trace", path: tracePath });
  }
  if (!items.length) {
    return null;
  }
  return (
    <section className="artifact-summary">
      <div className="task-card-head">
        <div>
          <span className="eyebrow">{copy("生成内容", "Generated content")}</span>
          <h4>{copy("结果与运行记录", "Results and run records")}</h4>
        </div>
        <span className="badge">{items.length}</span>
      </div>
      <ul>
        {items.slice(0, 6).map((artifact, index) => {
          const path = artifact.relative_path || artifact.path || "";
          const isTrace = artifact.type === "trace" || path === tracePath;
          const href = isTrace ? apiUrl(traceUrl || `/traces/${encodeURIComponent(traceLabel(path))}`) : undefined;
          return (
            <li key={`${artifact.type || "artifact"}-${path}-${index}`}>
              <span>{artifact.type || copy("结果", "Result")}</span>
              {href ? <a href={href}>{traceLabel(path)}</a> : <strong>{path || copy("内联结果", "Inline result")}</strong>}
            </li>
          );
        })}
      </ul>
    </section>
  );
}

function QualitySummary({
  lang,
  responseScore,
  systemScore,
  warnings
}: {
  lang: Lang;
  responseScore?: number;
  systemScore?: number;
  warnings: WarningItem[];
}) {
  const copy = (zh: string, en: string) => (lang === "zh" ? zh : en);
  return (
    <section className="quality-summary">
      <div className="quality-card">
        <span>{copy("回答质量检查", "Response quality")}</span>
        <strong>{formatScore(responseScore)}</strong>
        <small>{qualityLabel(responseScore, undefined, lang)}</small>
      </div>
      <div className="quality-card">
        <span>{copy("系统质量检查", "System quality")}</span>
        <strong>{formatScore(systemScore)}</strong>
        <small>{qualityLabel(systemScore, undefined, lang)}</small>
      </div>
      <div className={warnings.length ? "quality-card warning" : "quality-card"}>
        <span>{copy("需复核", "Review needed")}</span>
        <strong>{warnings.length}</strong>
        <small>{warnings.length ? warnings[0]?.message || warnings[0]?.type || "-" : copy("暂无明显警告", "No visible warnings")}</small>
      </div>
    </section>
  );
}

export function friendlyTimeline(payload: WebPayload | null, lang: Lang): Array<{ title: string; status: string; tone: string; detail: string }> {
  return timelineForPayload(payload).map((step) => ({
    title: friendlyStepName(step, lang),
    status: statusCopy(step.status || "unknown", lang),
    tone: statusTone(step.status),
    detail: stepDetail(step, lang)
  }));
}

export function collectWarnings(payload: WebPayload | null): WarningItem[] {
  if (!payload) {
    return [];
  }
  return [...(payload.warnings || []), ...(payload.provider_warnings || [])];
}

export function taskTypeFromPayload(payload: WebPayload): string {
  const taskResult = objectValue(payload.task_result);
  return (
    stringValue(payload.intent?.task_type) ||
    stringValue(payload.intent?.type) ||
    stringValue(taskResult?.task_type) ||
    stringValue(payload.agent_mode)
  );
}

function resultTitle(payload: WebPayload, lang: Lang): string {
  const copy = (zh: string, en: string) => (lang === "zh" ? zh : en);
  const taskType = taskTypeFromPayload(payload);
  if (taskType === "code_analysis") return copy("代码分析结果", "Code analysis result");
  if (taskType === "trace_diagnosis") return copy("运行诊断结果", "Run diagnosis result");
  if (taskType === "document_analysis") return copy("文档分析结果", "Document analysis result");
  if (taskType === "data_analysis") return copy("数据分析结果", "Data analysis result");
  if (taskType?.startsWith("skill")) return copy("Skill 能力结果", "Skill capability result");
  return copy("Agent 回答", "Agent response");
}

function taskTypeLabel(taskType: string, lang: Lang): string {
  const copy = (zh: string, en: string) => (lang === "zh" ? zh : en);
  if (taskType === "code_analysis") return copy("代码分析", "Code analysis");
  if (taskType === "document_analysis") return copy("文档分析", "Document analysis");
  if (taskType === "data_analysis") return copy("数据分析", "Data analysis");
  return humanizeIdentifier(taskType);
}

function analysisMetrics(taskType: string, summary: Record<string, unknown>, lang: Lang) {
  const copy = (zh: string, en: string) => (lang === "zh" ? zh : en);
  if (taskType === "code_analysis") {
    return [
      { label: copy("文件", "Sources"), value: numberField(summary, "source_count") },
      { label: copy("行数", "Lines"), value: numberField(summary, "line_count") },
      { label: copy("高风险", "High"), value: numberField(summary, "high_count"), tone: "high" },
      { label: copy("中风险", "Medium"), value: numberField(summary, "medium_count"), tone: "medium" },
      { label: copy("发现", "Findings"), value: numberField(summary, "finding_count") }
    ];
  }
  if (taskType === "document_analysis") {
    return [
      { label: copy("文档", "Documents"), value: numberField(summary, "document_count") },
      { label: copy("词数", "Words"), value: numberField(summary, "word_count") },
      { label: copy("发现", "Findings"), value: numberField(summary, "finding_count") }
    ];
  }
  return [
    { label: copy("数据源", "Sources"), value: numberField(summary, "source_count") },
    { label: copy("行", "Rows"), value: numberField(summary, "row_count") },
    { label: copy("列", "Columns"), value: numberField(summary, "column_count") },
    { label: copy("发现", "Findings"), value: numberField(summary, "finding_count") }
  ];
}

function numberField(record: Record<string, unknown>, key: string): string {
  const value = record[key];
  return typeof value === "number" && Number.isFinite(value) ? String(value) : "0";
}

function friendlyStepName(step: TimelineStep, lang: Lang): string {
  const copy = (zh: string, en: string) => (lang === "zh" ? zh : en);
  const name = step.tool_name || step.name || step.step_id || "";
  const map: Record<string, string> = {
    retrieve_memory_context: copy("检索相关记忆", "Retrieve relevant memory"),
    inspect_latest_trace: copy("读取最近运行记录", "Inspect latest run record"),
    select_skill: copy("选择可复用能力", "Select reusable capability"),
    build_plan: copy("制定执行计划", "Build execution plan"),
    execute_plan: copy("执行任务流程", "Execute task workflow"),
    observe_execution: copy("整理执行证据", "Collect execution evidence"),
    build_response: copy("整理最终回答", "Build final answer"),
    evaluate_response_hqs: copy("检查回答质量", "Evaluate response quality"),
    resolve_sources: copy("准备资料", "Prepare sources"),
    analyze_sources: copy("执行分析", "Run analysis"),
    build_report: copy("生成报告", "Build report")
  };
  return map[name] || humanizeIdentifier(name || copy("处理步骤", "Processing step"));
}

function stepDetail(step: TimelineStep, lang: Lang): string {
  const copy = (zh: string, en: string) => (lang === "zh" ? zh : en);
  const parts: string[] = [];
  if (step.kind) parts.push(String(step.kind));
  if (step.artifact_count) parts.push(`${step.artifact_count} ${copy("个结果", "artifacts")}`);
  if (step.error_count) parts.push(`${step.error_count} ${copy("个错误", "errors")}`);
  if (step.decision_type) parts.push(humanizeIdentifier(String(step.decision_type)));
  return parts.join(" · ") || copy("已记录到本次运行中", "Recorded in this run");
}

function humanizeIdentifier(value: string): string {
  return String(value || "-")
    .replaceAll("_", " ")
    .replaceAll("-", " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function statusCopy(status: string, lang: Lang): string {
  const copy = (zh: string, en: string) => (lang === "zh" ? zh : en);
  if (status === "completed") return copy("已完成", "Completed");
  if (status === "running") return copy("进行中", "Running");
  if (status === "failed") return copy("失败", "Failed");
  if (status === "completed_with_warnings") return copy("完成，需复核", "Completed with review");
  if (status === "skipped") return copy("已跳过", "Skipped");
  if (status === "pending") return copy("等待中", "Pending");
  return copy("已记录", "Recorded");
}

function statusTone(status: string | undefined): string {
  if (status === "completed") return "completed";
  if (status === "running") return "running";
  if (status === "failed") return "failed";
  if (status === "completed_with_warnings" || status === "skipped") return "warning";
  return "pending";
}

function modeLabel(mode: string, lang: Lang): string {
  const copy = (zh: string, en: string) => (lang === "zh" ? zh : en);
  if (mode.includes("tool")) return copy("自主Agent", "Autonomous Agent");
  return copy("工作流模式", "Workflow Mode");
}

function qualityLabel(responseScore: number | undefined, systemScore: number | undefined, lang: Lang): string {
  const copy = (zh: string, en: string) => (lang === "zh" ? zh : en);
  const scores = [responseScore, systemScore].filter((value): value is number => typeof value === "number");
  if (!scores.length) return copy("待检查", "Pending");
  const average = scores.reduce((sum, value) => sum + value, 0) / scores.length;
  if (average >= 4) return copy("质量检查通过", "Quality passed");
  if (average >= 3) return copy("建议人工复核", "Review recommended");
  return copy("需要复核", "Needs review");
}

function formatValue(value: unknown): string {
  if (typeof value === "string") {
    return value;
  }
  if (typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  if (Array.isArray(value)) {
    return value.map(formatValue).join(", ");
  }
  if (value && typeof value === "object") {
    return escapeHtml(JSON.stringify(value));
  }
  return "-";
}
