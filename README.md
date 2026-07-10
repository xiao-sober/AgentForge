# AgentForge

AgentForge 是一个本地优先、可观察、可治理的 Agent 平台项目。

它从可复用的 Markdown Skill、Agent Harness、Tool-Calling Loop、HQS 评估和本地运行痕迹出发，逐步演进为成熟的多 Agent 自主平台。项目当前重点不是做一个普通聊天机器人，而是建设一套可以被检查、调试、治理和持续改进的 Agent 运行系统。

## 核心特性

- **本地优先**：默认使用本地确定性逻辑运行，外部大模型 provider 是可选能力。
- **可观察运行**：Skill 生成、执行、演进、聊天、工具调用、HQS 和 memory 都会沉淀 trace / run artifact。
- **Skill 资产化**：Skill 使用 Markdown 保存，并按版本演进，避免覆盖历史版本。
- **Agent Harness**：支持固定 workflow 与 tool-calling 两类运行模式。
- **Web 工作台**：提供聊天、Skill 操作、run timeline、trace、memory、HQS 等本地可视化入口。
- **平台化目标**：长期方向是多 Agent 协作、自主规划、知识库、上下文工程和运行时治理。

## 环境要求

- Python 3.10 或更新版本
- Node.js 20 或更新版本，包含 `npm`
- Windows、macOS 或 Linux
- 可选：`uv`
- 可选：用于 provider 模式的大模型 API key

AgentForge 会自动初始化本地 SQLite 文件 `data/agentforge.db`，不需要额外安装 MySQL、PostgreSQL 或独立数据库服务。

## 快速开始

### 1. 安装 Python 依赖

使用 `uv`：

```powershell
uv venv .venv
uv pip install --python .venv\Scripts\python.exe -e ".[dev]"
```

使用标准 `pip`：

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

Linux / macOS 下将 `.venv\Scripts\python.exe` 替换为 `.venv/bin/python`。

### 2. 安装并构建前端

```powershell
npm run web:install
npm run web:build
```

### 3. 启动本地服务

```powershell
agentforge serve --host 127.0.0.1 --port 8765
```

打开 Web 工作台：

```text
http://127.0.0.1:8765/
```

如果 shell 找不到 `agentforge` 命令，可以使用：

```powershell
.venv\Scripts\python.exe -m agentforge serve --host 127.0.0.1 --port 8765
```

### 4. 前端开发模式

需要调试 React 页面时，保留 FastAPI 后端并启动 Vite：

```powershell
agentforge serve --host 127.0.0.1 --port 8765
npm run web:dev
```

开发模式打开：

```text
http://127.0.0.1:5173/
```

## 常用命令

检查本地配置：

```powershell
agentforge check-config
agentforge check-config --json
```

本地 Agent 聊天：

```powershell
agentforge agent-chat --input "Review this dashboard layout for readability." --json
```

Tool-Calling 模式：

```powershell
agentforge agent-chat --input "Inspect the latest trace." --agent-mode tool-calling --json
```

生成 Skill：

```powershell
agentforge generate-skill --local-only --input "Create a UI review Skill"
```

运行示例 Skill：

```powershell
agentforge run-skill `
  --skill examples/skills/ui_review_skill/v1/SKILL.md `
  --input "Review this dashboard layout for hierarchy and readability."
```

演进 Skill：

```powershell
agentforge evolve-skill `
  --skill skills/ui_review_skill/v1/SKILL.md `
  --taskset tasksets/sample_ui_review_basic.json `
  --max-iterations 1
```

更多 CLI、API、Web、测试和本地产物说明见 [docs/developer_usage.md](docs/developer_usage.md)。

## Provider 配置

Provider 是可选能力。没有 `config/providers.json` 时，AgentForge 使用本地确定性逻辑。

复制示例配置：

```powershell
copy config\providers.example.json config\providers.json
```

配置示例：

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

`config/providers.json` 已被 Git 忽略。API key 应通过本地配置或环境变量引用，不能写入源码。

## 本地产物

AgentForge 会在项目根目录写入本地产物：

```text
skills/                 生成的版本化 Skills
runs/                   Skill 执行和 Agent 运行输出
traces/                 JSON traces
data/memory/            working、episodic、semantic memory
data/agentforge.db      SQLite 运行索引和查询状态
config/providers.json   本地 provider 配置，已 git-ignore
apps/web/frontend/dist/ 前端构建产物，已 git-ignore
```

这些目录默认用于本地开发和调试，不应提交包含私密信息的运行产物。

## 文档导航

- [开发与使用指南](docs/developer_usage.md)
- [当前开发交接](docs/development_handoff.md)
- [多 Agent 自主平台目标](docs/multi_agent_autonomous_platform_goal.md)
- [运行时治理与文件源设计](docs/runtime_governance_and_source_design.md)

## 开发检查

常用检查命令：

```powershell
npm run web:typecheck
npm run web:build
python -m unittest discover -s tests
```

文档或配置变更至少运行：

```powershell
git diff --check
```
