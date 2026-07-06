# AgentForge

AgentForge 是一个本地优先的 Agent Harness，用来创建、运行、评估和改进可复用的 Markdown Skill。

它面向可观察、可调试的本地 Agent 开发：

- Skill 使用 Markdown 文件保存。
- 运行结果写入本地 `runs/`。
- Trace 使用 JSON 文件保存。
- Memory 使用 JSON / JSONL 保存。
- 大模型 provider 是可选适配器，通过本地配置接入，不写死在代码里。

AgentForge 不是托管平台，也不包含云部署、RBAC、计费、插件市场或分布式任务队列。

## 核心能力

- 根据需求生成带版本的 `SKILL.md`。
- 对单条输入或任务集运行 Skill。
- 通过有限轮评估和重写演进 Skill。
- 使用确定性的 Harness workflow 运行聊天。
- 使用 Tool-Calling Agent loop 运行模型可见的工具调用流程。
- 在本地保存 working、episodic、semantic 三层 memory。
- 使用 HQS 对响应、Skill 和系统行为评分。
- 为 Skill 生成、执行、演进、聊天、memory、HQS 写入可读 trace。
- 提供本地 Web 工作台和 JSON API。

## 核心架构

```text
用户请求
  -> Agent Harness
  -> Intent parser
  -> Memory retrieval
  -> Skill selection / Skill generation
  -> Planner
  -> Executor
  -> Response builder
  -> HQS evaluation
  -> Trace and memory write
```

## 运行模式

聊天流程有两个独立开关：

- `use_provider`：是否调用 `config/providers.json` 中配置的大模型 provider。
- `agent_mode`：使用固定 Harness workflow，还是使用 Tool-Calling Agent loop。

| 运行后端 | Agent 模式 | 说明 |
| --- | --- | --- |
| 本地 | `harness_workflow` | 完全确定性的基线模式，Harness 决定每一步。 |
| Provider | `harness_workflow` | 步骤顺序仍由 Harness 决定，需要模型文本时才调用 provider。 |
| 本地 | `tool_calling_agent` | 使用带少量规则路由的脚本化 planner 跑工具调用链路，不调用外部 API。适合测试 policy、trace、memory 和 UI timeline；泛化规划能力仍应由 provider 模式验收。 |
| Provider | `tool_calling_agent` | 真实 provider 返回 JSON 工具决策，Harness 负责校验和执行。 |

更完整的模式对比见：[docs/agent_run_modes.md](docs/agent_run_modes.md)。

## Tool-Calling Agent

Tool-Calling Agent 会向 planner 暴露有限工具集：

- `retrieve_memory_context`
- `inspect_latest_trace`
- `select_skill`
- `build_plan`
- `execute_plan`
- `observe_execution`
- `build_response`
- `evaluate_response_hqs`

planner 每次只能返回一个 JSON 决策：

```json
{"type":"tool_call","tool_name":"select_skill","arguments":{}}
```

或：

```json
{"type":"final_answer","content":"..."}
```

或：

```json
{"type":"cannot_continue","reason":"...","needed_input":["..."]}
```

以下高影响动作始终由 Harness 控制，不交给模型直接执行：

- memory 写入
- HQS gate
- retry / replan
- reflection
- reinforcement
- episode persistence

当前本地 AgentForge 范围内，`docs/tool_calling_agent_goal.md` 记录的 Tool-Calling Agent 目标已经完成。

## 环境要求

- Python 3.10 或更新版本
- Windows、macOS 或 Linux
- 可选：`uv`
- 可选：用于 provider 模式的大模型 API key

本地确定性模式不需要数据库或外部服务。

## 安装

使用 `uv`：

```bash
uv venv .venv
uv pip install --python .venv\Scripts\python.exe -e ".[dev]"
```

使用标准 `pip`：

```bash
python -m venv .venv
.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

Linux / macOS 下把 `.venv\Scripts\python.exe` 替换为 `.venv/bin/python`。

运行测试：

```bash
.venv\Scripts\python.exe -m unittest discover -s tests
```

## 本地启动

启动本地服务：

```bash
agentforge serve --host 127.0.0.1 --port 8765
```

打开 Web 工作台：

```text
http://127.0.0.1:8765/
```

检查本地配置：

```bash
agentforge check-config
```

查看包含 provider、真实 provider 测试门禁和密钥脱敏信息的 JSON 报告：

```bash
agentforge check-config --json
```

如果 shell 找不到 `agentforge` 命令，可以使用：

```bash
python -m agentforge serve --host 127.0.0.1 --port 8765
```

## 快速使用

### 本地 Harness 聊天

```bash
agentforge agent-chat ^
  --input "Review this dashboard layout for readability." ^
  --json
```

### 本地 Tool-Calling loop 冒烟测试

本地 `tool_calling_agent` 使用脚本化 planner，内置少量规则路由，可覆盖普通执行、trace inspection、memory query 和 Skill 生成类冒烟场景。它主要用于验证工具调用链路、policy、trace 和 Web timeline；更开放的自然语言规划仍应使用 provider 模式验收。

```bash
agentforge agent-chat ^
  --input "Inspect the latest trace." ^
  --agent-mode tool-calling ^
  --json
```

### Provider Tool-Calling Agent

真实 trace inspection、memory query、Skill 生成类请求应使用接入 provider 的 `tool_calling_agent` 验收：

```bash
agentforge agent-chat ^
  --input "Inspect the latest trace and summarize errors." ^
  --use-provider ^
  --agent-mode tool-calling ^
  --json
```

需要完整调试 payload 时增加 `--debug`：

```bash
agentforge agent-chat ^
  --input "What useful memory do you have about recent provider dry runs?" ^
  --use-provider ^
  --agent-mode tool-calling ^
  --json ^
  --debug
```

### 生成 Skill

```bash
agentforge generate-skill ^
  --local-only ^
  --input "Create a UI review Skill"
```

该命令会生成类似 `skills/ui_review_skill/v1/SKILL.md` 的本地 Skill。

### 运行示例 Skill

全新克隆仓库后，可直接运行的示例 Skill 位于 `examples/skills/`：

```bash
agentforge run-skill ^
  --skill examples/skills/ui_review_skill/v1/SKILL.md ^
  --input "Review this dashboard layout for hierarchy and readability."
```

### 演进 Skill

Skill 演进会写入下一个版本，建议对 `skills/` 下的生成 Skill 使用。全新克隆仓库后还没有 `skills/ui_review_skill/v1/SKILL.md`，请先运行上面的 `generate-skill` 示例；下面的命令假设已经生成了该 Skill。

```bash
agentforge evolve-skill ^
  --skill skills/ui_review_skill/v1/SKILL.md ^
  --taskset tasksets/sample_ui_review_basic.json ^
  --max-iterations 1
```

### 查看 Trace

```bash
agentforge inspect-trace traces\<trace-file>.json
```

### 清理旧产物

预览清理范围：

```bash
agentforge cleanup-artifacts --max-traces 200 --max-runs-per-skill-version 20
```

执行删除：

```bash
agentforge cleanup-artifacts --max-traces 200 --max-runs-per-skill-version 20 --delete
```

## 大模型 Provider 配置

Provider 配置是可选的。没有 `config/providers.json` 时，AgentForge 使用本地确定性逻辑。

从示例文件创建本地配置：

```bash
copy config\providers.example.json config\providers.json
```

`config/providers.json` 已被 `.gitignore` 忽略。

配置结构示例：

```json
{
  "default_provider": "deepseek_v4_pro",
  "providers": {
    "deepseek_v4_pro": {
      "type": "openai_compatible",
      "base_url": "https://api.deepseek.com",
      "api_key_env": "DEEPSEEK_API_KEY",
      "model": "deepseek-v4-pro",
      "timeout_seconds": 300,
      "temperature": 0.2,
      "max_tokens": 8192
    }
  }
}
```

当前支持的适配器类型：

- `openai_compatible`

Provider 调用走兼容 `/chat/completions` 的 API。API key 必须放在 `config/providers.json`，或通过其中的 `api_key_env` 引用环境变量，不要写死在源码里。

## Web / API

本地服务使用 Python 标准库 HTTP server，返回 JSON。

主要路由：

```text
GET  /health
GET  /version
GET  /config
POST /chat
POST /skills/generate
POST /skills/run
POST /skills/evolve
GET  /skills
GET  /skills/<skillName>
GET  /skills/<skillName>/<version>
GET  /tasksets
GET  /memory
GET  /agent/runs/<runId>
GET  /agent/runs/<runId>/tool-calls
GET  /traces
GET  /traces/<traceFileName>
GET  /hqs
```

示例请求：

```bash
curl -X POST http://127.0.0.1:8765/chat ^
  -H "Content-Type: application/json" ^
  -d "{\"message\":\"Review dashboard layout readability.\",\"agent_mode\":\"tool_calling\",\"use_provider\":false}"
```

`POST /chat` 默认值：

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

Tool-calling 的精简 payload 会额外包含：

- `tool_call_timeline`
- `parse_repair_count`
- `invalid_call_count`
- `final_answer_source`
- `hqs_gate`
- `quality_retry`

`GET /config` 会隐藏密钥，不返回 API key 明文。

## Web 工作台

Web 工作台支持：

- Chat
- Skill 生成
- Skill 执行
- Skill 演进
- 本地 / provider 模式切换
- `harness_workflow` / `tool_calling_agent` 模式选择
- run timeline
- tool-call timeline
- trace、HQS、memory、Skill diff 下钻
- debug JSON 查看
- 中文和英文 UI 切换

## 本地产物

AgentForge 会在项目根目录写入这些本地产物：

```text
skills/                 生成的版本化 Skills
runs/                   Skill 执行输出
traces/                 JSON traces
data/memory/            working、episodic、semantic memory
config/providers.json   本地 provider 配置，已 git-ignore
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
src/agentforge/
  agent/                Harness、planner、executor、tools、tool-calling loop
  common/               trace、diagnostics、cleanup、文件工具
  hqs/                  response / system HQS evaluator
  memory/               本地三层 memory
  providers/            provider 配置和适配器
  skill_generator/      需求解析和 Skill 生成
  skill_evolver/        task set、runner、evaluator、rewriter、versioning
  web/                  本地 HTTP server 和静态工作台

docs/                   设计说明和运行模式文档
examples/               示例 Skills
tasksets/               任务集 JSON
tests/                  单元测试和集成测试
```

## 开发检查

交付前运行完整测试：

```bash
python -m unittest discover -s tests
```

真实 provider 测试默认跳过，需要显式开启：

```bash
set AGENTFORGE_RUN_REAL_PROVIDER_TESTS=1
set AGENTFORGE_REAL_PROVIDERS=deepseek_v4_pro,dashscope
python -m unittest tests.test_real_provider_tool_calling
```

`agentforge check-config --json` 会在 `config.real_provider_tests` 中显示真实 provider 测试当前是 `enabled` 还是 `skipped_by_default`，并列出请求的 provider 是否存在于本地配置中。

常用文档：

- [docs/agent_run_modes.md](docs/agent_run_modes.md)
- [docs/tool_calling_agent_goal.md](docs/tool_calling_agent_goal.md)
- [docs/autonomous_agent_platform_goal.md](docs/autonomous_agent_platform_goal.md)

Windows PowerShell 处理中文文本、JSON 或 Markdown 时建议使用 UTF-8：

```powershell
chcp 65001
$OutputEncoding = [Console]::OutputEncoding = [Text.UTF8Encoding]::new()
$env:PYTHONUTF8 = "1"
```
