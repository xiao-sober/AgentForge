# AgentForge Developer Usage

本文档收纳 README 中不适合长期堆叠的开发、调试、CLI、API 和本地产物说明。README 只保留项目定位、快速部署和最常用入口。

## 运行模式

聊天流程有两个核心开关：

- `use_provider`：是否调用 `config/providers.json` 中配置的大模型 provider。
- `agent_mode`：使用固定 Harness workflow，还是使用 Tool-Calling Agent loop。

| 运行后端 | Agent 模式 | 说明 |
| --- | --- | --- |
| 本地 | `harness_workflow` | 完全确定性的基线模式，Harness 决定每一步。 |
| Provider | `harness_workflow` | 步骤顺序仍由 Harness 决定，需要模型文本时才调用 provider。 |
| 本地 | `tool_calling_agent` | 使用脚本化 planner 跑工具调用链路，适合测试 policy、trace、memory 和 UI timeline。 |
| Provider | `tool_calling_agent` | 真实 provider 返回 JSON 工具决策，Harness 负责校验和执行。 |

CLI 中对应参数为：

```powershell
agentforge agent-chat --input "Inspect the latest trace." --agent-mode tool-calling --json
agentforge agent-chat --input "Inspect the latest trace." --use-provider --agent-mode tool-calling --json
```

## CLI 参考

### 配置检查

```powershell
agentforge check-config
agentforge check-config --json
```

`check-config --json` 会输出健康状态、版本信息、provider 配置状态和真实 provider 测试门禁状态。

### Agent 聊天

```powershell
agentforge agent-chat `
  --input "Review this dashboard layout for readability." `
  --json
```

需要完整调试 payload 时增加 `--debug`：

```powershell
agentforge agent-chat `
  --input "What useful memory do you have about recent provider dry runs?" `
  --use-provider `
  --agent-mode tool-calling `
  --json `
  --debug
```

### 生成 Skill

```powershell
agentforge generate-skill `
  --local-only `
  --input "Create a UI review Skill"
```

生成结果通常写入 `skills/<skill_slug>/v1/SKILL.md`，并在 `traces/` 中写入生成 trace。

### 验证 Skill

```powershell
agentforge validate-skill skills/ui_review_skill/v1/SKILL.md
agentforge validate-skill skills/ui_review_skill/v1/SKILL.md --json
```

### 运行 Skill

```powershell
agentforge run-skill `
  --skill examples/skills/ui_review_skill/v1/SKILL.md `
  --input "Review this dashboard layout for hierarchy and readability."
```

### 演进 Skill

```powershell
agentforge evolve-skill `
  --skill skills/ui_review_skill/v1/SKILL.md `
  --taskset tasksets/sample_ui_review_basic.json `
  --max-iterations 1
```

可选参数包括：

- `--target-hqs`
- `--min-improvement`
- `--auto-create-taskset`
- `--use-provider`

### 查看 Trace

```powershell
agentforge inspect-trace traces\<trace-file>.json
agentforge inspect-trace traces\<trace-file>.json --json
```

### 清理旧产物

预览清理范围：

```powershell
agentforge cleanup-artifacts --max-traces 200 --max-runs-per-skill-version 20
```

执行删除：

```powershell
agentforge cleanup-artifacts --max-traces 200 --max-runs-per-skill-version 20 --delete
```

## Provider 配置

Provider 配置是可选的。没有 `config/providers.json` 时，AgentForge 使用本地确定性逻辑。

```powershell
copy config\providers.example.json config\providers.json
```

当前支持的适配器类型：

- `openai_compatible`

Provider 调用走兼容 `/chat/completions` 的 API。API key 必须放在 `config/providers.json`，或通过其中的 `api_key_env` 引用环境变量，不要写死在源码里。

真实 provider 测试默认跳过，需要显式开启：

```powershell
set AGENTFORGE_RUN_REAL_PROVIDER_TESTS=1
set AGENTFORGE_REAL_PROVIDERS=deepseek_v4_pro,dashscope
python -m unittest tests.test_real_provider_tool_calling
```

## Web 与 API

本地服务使用 FastAPI。一体模式下，`agentforge serve` 同时提供：

- React Web 工作台：`http://127.0.0.1:8765/`
- FastAPI JSON API：`http://127.0.0.1:8765/api/...`

主要路由：

```text
GET  /api/health
GET  /api/version
GET  /api/config
POST /api/chat
POST /api/skills/generate
POST /api/skills/run
POST /api/skills/evolve
POST /api/tasks
GET  /api/tasks/types
GET  /api/skills
GET  /api/skills/<skillName>
GET  /api/skills/<skillName>/<version>
GET  /api/tasksets
GET  /api/runs
GET  /api/runs/<runId>
GET  /api/runs/<runId>/steps
GET  /api/runs/<runId>/artifacts
GET  /api/runs/<runId>/tool-calls
GET  /api/tools
GET  /api/tools/<toolName>
GET  /api/memory
GET  /api/memory/episodes
GET  /api/memory/semantic
GET  /api/agent/runs/<runId>
GET  /api/agent/runs/<runId>/tool-calls
GET  /api/traces
GET  /api/traces/<traceFileName>
GET  /api/hqs
```

聊天请求示例：

```powershell
curl -X POST http://127.0.0.1:8765/api/chat `
  -H "Content-Type: application/json" `
  -d "{\"message\":\"Review dashboard layout readability.\",\"agent_mode\":\"tool_calling\",\"use_provider\":false}"
```

`POST /api/chat` 默认值：

```json
{
  "agent_mode": "harness_workflow",
  "use_provider": false
}
```

需要完整 payload 时传入：

```json
{"debug": true}
```

`GET /api/config` 会隐藏密钥，不返回 API key 明文。

## Task Router

统一任务入口可用于 Workflow Runner 和 Task Router 共用的任务执行。

诊断最新 trace：

```powershell
curl -X POST http://127.0.0.1:8765/api/tasks `
  -H "Content-Type: application/json" `
  -d "{\"task_type\":\"trace_diagnosis\",\"input\":{\"latest\":true}}"
```

分析项目内代码文件：

```powershell
curl -X POST http://127.0.0.1:8765/api/tasks `
  -H "Content-Type: application/json" `
  -d "{\"task_type\":\"code_analysis\",\"input\":{\"path\":\"src/agentforge/agent/intent_parser.py\"}}"
```

查看当前任务类型：

```powershell
curl http://127.0.0.1:8765/api/tasks/types
```

当前可执行任务类型包括：

- `skill_generate`
- `skill_run`
- `skill_evolve`
- `trace_diagnosis`
- `code_analysis`
- `document_analysis`
- `data_analysis`

也可以直接通过聊天触发任务路由：

```powershell
curl -X POST http://127.0.0.1:8765/api/chat `
  -H "Content-Type: application/json" `
  -d "{\"message\":\"Inspect the latest trace.\"}"
```

## Web 工作台

Web 工作台支持：

- Chat
- Skill 生成
- Skill 执行
- Skill 演进
- 本地 / provider 模式切换
- `harness_workflow` / `tool_calling_agent` 模式选择
- run timeline
- SQLite-backed Runs 列表和 Run Detail
- tool-call timeline
- trace、HQS、memory、Skill diff 下钻
- debug JSON 查看
- 中文和英文 UI 切换

前端源码位于 `apps/web/frontend/`，使用 React + TypeScript + Vite。FastAPI backend 位于 `apps/web/backend/`，只负责 HTTP/API 边界，核心 Agent、Skill、HQS、memory 逻辑仍在 `src/agentforge/`。

常用前端命令：

```powershell
npm run web:install
npm run web:dev
npm run web:typecheck
npm run web:build
```

这些根目录脚本会转发到 `apps/web/frontend/`。

## 本地产物

AgentForge 会在项目根目录写入这些本地产物：

```text
skills/                 生成的版本化 Skills
runs/                   Skill 执行输出
traces/                 JSON traces
data/memory/            working、episodic、semantic memory
data/agentforge.db      SQLite 运行索引和查询状态
config/providers.json   本地 provider 配置，已 git-ignore
apps/web/frontend/dist/ 前端构建产物，已 git-ignore
```

重要 trace 类型：

- `skill_generation`
- `skill_execution`
- `skill_evaluation`
- `skill_evolution`
- `agent_chat`
- `tool_calling_agent`
- `memory_update`
- `hqs_diagnosis`

## 项目结构

```text
apps/web/
  backend/              FastAPI API 层，调用 src/agentforge 核心能力
  frontend/             React + TypeScript + Vite 工作台

src/agentforge/
  agent/                Harness、planner、agent run loop、tool-calling loop
  common/               trace、diagnostics、cleanup、文件工具
  hqs/                  response / system HQS evaluator
  memory/               本地三层 memory
  providers/            provider 配置和适配器
  runs/                 SQLite run / step / artifact / tool call 查询服务
  skill_generator/      需求解析和 Skill 生成
  skill_evolver/        task set、runner、evaluator、rewriter、versioning
  storage/              SQLite 初始化和 migration
  tasks/                统一任务路由和任务 handlers
  tools/                Tool schema、registry、executor、permission
  workflows/            Workflow definition、runner、checkpoint
  web/                  旧 HTTP 兼容层，保留给现有测试和调用方

docs/                   设计说明、开发指南和交接文档
examples/               示例 Skills
tasksets/               任务集 JSON
tests/                  单元测试和集成测试
```

## 开发检查

交付前优先运行：

```powershell
npm run web:typecheck
npm run web:build
python -m unittest discover -s tests
```

文档或配置变更至少运行：

```powershell
git diff --check
```

## Windows UTF-8

Windows PowerShell 处理中文文本、JSON 或 Markdown 时建议使用 UTF-8：

```powershell
chcp 65001
$OutputEncoding = [Console]::OutputEncoding = [Text.UTF8Encoding]::new()
$env:PYTHONUTF8 = "1"
```
