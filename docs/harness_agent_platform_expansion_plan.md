# Harness Agent Platform Expansion Plan

## 1. 文档目的

本文档定义 AgentForge 从当前偏 Skill 操作的 MVP，扩展为业务范围更广的 Harness Agent 平台的实施计划。

当前系统已经具备：

- Skill 生成、运行、演化
- Harness workflow
- Tool-calling agent loop
- 三层 memory 的文件化雏形
- HQS 评分
- JSON trace
- FastAPI API 边界
- React Web 工作台

下一阶段的目标不是做一个泛泛的聊天机器人，而是把 AgentForge 扩展为：

```text
Local-first Harness Agent Platform
  = Task Router
  + Workflow / Run System
  + Tool Registry
  + Skill System
  + Memory Store
  + Trace / HQS / Artifact Observability
  + React Operations Workbench
```

## 2. 完成目标

### 2.1 平台目标

把 AgentForge 从：

```text
用户输入 -> Skill 生成 / Skill 运行 / Skill 演化
```

扩展为：

```text
用户任务
  -> Task Router
  -> Harness
  -> Memory Retrieval
  -> Skill Selection
  -> Tool Planning
  -> Workflow Execution
  -> Artifact Persistence
  -> HQS Evaluation
  -> Trace / Run Record
  -> User-facing Result
```

### 2.2 业务范围目标

第一阶段扩展后，AgentForge 应能支持这些非 Skill 单一场景：

- 文档分析和结构化提取
- 代码库分析和代码审查
- 本地 JSON / CSV 数据分析
- API 调试和接口检查
- Trace / run 诊断
- 报告生成
- Skill 生成、运行、演化继续作为平台内置任务类型保留

### 2.3 技术目标

- 用 SQLite 作为本地索引和状态数据库。
- 保留 JSON trace 文件作为可读审计材料。
- 所有业务任务统一进入 Run / Workflow 模型。
- 所有工具调用进入 Tool Registry，带 schema、权限、超时、trace。
- Web UI 从 Skill 控制台升级为 Agent 工作台。

## 3. SQLite 引入原则

### 3.1 不需要 MySQL

当前阶段不需要 MySQL，也不需要启动独立数据库服务。

SQLite 是嵌入式数据库，Python 标准库自带：

```python
import sqlite3
```

推荐本地数据库文件：

```text
data/agentforge.db
```

### 3.2 SQLite 负责什么

SQLite 用于查询、列表、筛选和状态恢复：

- runs
- run_steps
- artifacts
- tool_calls
- hqs_reports
- memory_episodes
- semantic_memories
- workflow_checkpoints

### 3.3 JSON trace 继续负责什么

JSON trace 不要删除。它继续作为可读、可 diff、可审计的事实记录：

```text
traces/*.json
```

原则：

```text
SQLite = 查询索引和当前状态
JSON trace = 可读审计和完整过程记录
```

### 3.4 后续扩展边界

不要一开始抽象复杂 ORM。建议先使用标准库 `sqlite3` 和小型 repository 层。

后续如果需要多人部署，再引入 storage adapter：

```text
SQLiteStorage
MySQLStorage
PostgresStorage
```

## 4. 推荐目录结构

建议在现有结构基础上增量添加：

```text
src/agentforge/
  storage/
    __init__.py
    sqlite_store.py
    migrations.py
    schema.sql

  runs/
    __init__.py
    models.py
    repository.py
    service.py

  workflows/
    __init__.py
    definition.py
    runner.py
    state.py
    checkpoint.py

  tools/
    __init__.py
    schema.py
    registry.py
    executor.py
    permissions.py
    builtin/
      __init__.py
      file_tools.py
      http_tools.py
      data_tools.py
      trace_tools.py

  tasks/
    __init__.py
    router.py
    schemas.py
    handlers/
      __init__.py
      skill_tasks.py
      document_analysis.py
      code_analysis.py
      data_analysis.py
      trace_diagnosis.py

apps/web/backend/agentforge_web_backend/
  routers/
    runs.py
    tasks.py
    tools.py
    memory.py

apps/web/frontend/src/
  features/
    runs/
    tasks/
    tools/
    memory/
```

## 5. 数据模型草案

### 5.1 runs

```sql
CREATE TABLE runs (
  run_id TEXT PRIMARY KEY,
  task_type TEXT NOT NULL,
  title TEXT NOT NULL,
  status TEXT NOT NULL,
  input_json TEXT NOT NULL,
  output_json TEXT,
  trace_path TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  completed_at TEXT
);
```

状态建议：

```text
queued
running
waiting_for_user
completed
failed
cancelled
```

### 5.2 run_steps

```sql
CREATE TABLE run_steps (
  step_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  name TEXT NOT NULL,
  kind TEXT NOT NULL,
  status TEXT NOT NULL,
  input_json TEXT,
  output_json TEXT,
  error_json TEXT,
  started_at TEXT,
  completed_at TEXT,
  FOREIGN KEY (run_id) REFERENCES runs(run_id)
);
```

### 5.3 tool_calls

```sql
CREATE TABLE tool_calls (
  tool_call_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  step_id TEXT,
  tool_name TEXT NOT NULL,
  status TEXT NOT NULL,
  arguments_json TEXT NOT NULL,
  result_json TEXT,
  error_json TEXT,
  started_at TEXT NOT NULL,
  completed_at TEXT,
  FOREIGN KEY (run_id) REFERENCES runs(run_id)
);
```

### 5.4 artifacts

```sql
CREATE TABLE artifacts (
  artifact_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  type TEXT NOT NULL,
  path TEXT,
  content_type TEXT,
  metadata_json TEXT,
  created_at TEXT NOT NULL,
  FOREIGN KEY (run_id) REFERENCES runs(run_id)
);
```

### 5.5 hqs_reports

```sql
CREATE TABLE hqs_reports (
  hqs_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  scope TEXT NOT NULL,
  average_score REAL NOT NULL,
  report_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY (run_id) REFERENCES runs(run_id)
);
```

## 6. 分阶段实施计划

### Phase 1: SQLite Storage Baseline

目标：建立本地数据库和 repository 基础。

修改内容：

- 新增 `src/agentforge/storage/`
- 新增 `data/agentforge.db` 自动初始化逻辑
- 新增 schema migration 基础能力
- `.gitignore` 保持忽略 `data/`
- CLI 或启动流程中懒初始化 SQLite

关键要求：

- 不引入 MySQL
- 不引入复杂 ORM
- 测试使用临时目录里的 SQLite 文件
- 数据库损坏时给出明确错误，不静默失败

验收标准：

- 启动后能自动创建 `data/agentforge.db`
- 单测能验证 schema 初始化
- 重复初始化不会破坏已有数据

### Phase 2: Run Repository and Run Service

目标：让所有任务有统一运行记录。

修改内容：

- 新增 `src/agentforge/runs/`
- 定义 `RunRecord`、`RunStepRecord`、`ArtifactRecord`
- 提供 repository：
  - `create_run()`
  - `update_run_status()`
  - `add_run_step()`
  - `complete_run_step()`
  - `add_artifact()`
  - `list_runs()`
  - `get_run()`

需要接入：

- `AgentHarness.chat()`
- `tool_chat()`
- Skill generation
- Skill run
- Skill evolve

验收标准：

- Web chat 会写入 runs 表
- Skill generate/run/evolve 会写入 runs 表
- 原有 JSON trace 仍然生成
- 现有测试保持通过

### Phase 3: Tool Registry Formalization

目标：把工具调用从局部逻辑升级成平台能力。

修改内容：

- 新增 `src/agentforge/tools/`
- 定义 Tool schema：
  - name
  - description
  - input_schema
  - output_schema
  - permission_level
  - timeout_seconds
  - side_effects
- 实现 Tool Registry：
  - `register_tool()`
  - `get_tool()`
  - `list_tools()`
  - `schema_for_model()`
- 实现 Tool Executor：
  - schema validation
  - timeout
  - permission check
  - tool call trace
  - SQLite tool_calls 记录

第一批内置工具：

- trace inspection
- memory retrieval
- skill selection
- response build
- file read under allowed roots
- JSON data inspection

验收标准：

- tool-calling agent 使用 registry 暴露工具 schema
- 工具调用写入 `tool_calls`
- 非法工具名、非法参数、越权操作都有明确错误

### Phase 4: Workflow Runner

目标：把多步骤任务编排从 Harness 内部流程抽象为统一 workflow。

修改内容：

- 新增 `src/agentforge/workflows/`
- 定义 Workflow：
  - workflow_id
  - task_type
  - steps
  - stop_conditions
  - retry_policy
  - artifact_policy
- 实现 runner：
  - start
  - step execution
  - checkpoint
  - fail / retry
  - complete

先迁移这些流程：

- chat workflow
- skill generation workflow
- skill run workflow
- skill evolve workflow

验收标准：

- 原有业务行为不退化
- 每个 workflow step 都能在 UI 和 SQLite 中看到
- trace 中仍包含完整步骤

### Phase 5: Task Router and Non-Skill Task Types

目标：扩展业务范围，让用户任务不再只能围绕 Skill。

修改内容：

- 新增 `src/agentforge/tasks/`
- 定义任务输入：

```json
{
  "task_type": "document_analysis",
  "input": {},
  "options": {}
}
```

第一批任务类型：

- `skill_generate`
- `skill_run`
- `skill_evolve`
- `document_analysis`
- `code_analysis`
- `data_analysis`
- `trace_diagnosis`

推荐先实现 `trace_diagnosis` 或 `document_analysis`，因为最贴近当前能力，风险较低。

验收标准：

- 新 API `POST /api/tasks` 能创建任务
- `GET /api/runs` 能看到任务运行状态
- 至少一个非 Skill 任务完整可用

### Phase 6: FastAPI API Expansion

目标：为平台能力提供清晰 API。

新增路由：

```text
POST /api/tasks
GET  /api/tasks/types

GET  /api/runs
GET  /api/runs/{run_id}
GET  /api/runs/{run_id}/steps
GET  /api/runs/{run_id}/artifacts
GET  /api/runs/{run_id}/tool-calls

GET  /api/tools
GET  /api/tools/{tool_name}

GET  /api/memory/episodes
GET  /api/memory/semantic
```

保留旧路由：

```text
POST /api/chat
POST /api/skills/generate
POST /api/skills/run
POST /api/skills/evolve
```

旧路由可以内部转为 task/workflow，但外部兼容不要立即破坏。

### Phase 7: React Workbench Upgrade

目标：从 Skill 控制台升级为 Agent 运行工作台。

建议页面：

```text
Dashboard
Runs
Run Detail
Tasks
Skills
Tools
Memory
Traces
HQS
Settings
```

优先实现：

- Runs 列表
- Run detail
- Tool calls timeline
- Artifacts panel
- HQS panel
- Trace viewer

UI 原则：

- 不做营销页
- 不做大屏风
- 保持企业 AI 工作台风格
- 信息密度高但层级清楚
- 所有长任务都要有状态反馈

验收标准：

- 用户能看到当前任务在哪一步
- 用户能看到调用了什么工具
- 用户能看到失败原因
- 用户能打开产物、trace、HQS

## 7. 需要修改的核心模块

### 7.1 Python Core

预计新增：

```text
src/agentforge/storage/
src/agentforge/runs/
src/agentforge/workflows/
src/agentforge/tools/
src/agentforge/tasks/
```

预计调整：

```text
src/agentforge/agent/harness.py
src/agentforge/agent/tool_calling/loop.py
src/agentforge/agent/tools.py
src/agentforge/memory/memory_manager.py
src/agentforge/common/trace.py
src/agentforge/skill_generator/generator.py
src/agentforge/skill_evolver/evolution_loop.py
src/agentforge/web/routes.py
```

### 7.2 FastAPI Backend

预计新增：

```text
apps/web/backend/agentforge_web_backend/routers/
```

预计调整：

```text
apps/web/backend/agentforge_web_backend/main.py
apps/web/backend/agentforge_web_backend/legacy_bridge.py
```

### 7.3 React Frontend

预计新增：

```text
apps/web/frontend/src/features/runs/
apps/web/frontend/src/features/tasks/
apps/web/frontend/src/features/tools/
apps/web/frontend/src/features/memory/
```

预计调整：

```text
apps/web/frontend/src/App.tsx
apps/web/frontend/src/api.ts
apps/web/frontend/src/types.ts
apps/web/frontend/src/view-model.ts
apps/web/frontend/src/i18n.ts
apps/web/frontend/src/styles.css
```

## 8. 测试计划

### 8.1 SQLite

- schema 初始化
- 重复 migration
- 临时数据库读写
- 数据库文件不存在时自动创建
- 数据库路径越界保护

### 8.2 Runs

- create/list/get run
- step 状态流转
- artifact 写入
- failed run 记录错误
- trace_path 和 run_id 对齐

### 8.3 Tools

- tool registry 注册和查询
- schema validation
- permission check
- timeout
- tool_call 记录
- 非法参数返回可解释错误

### 8.4 Workflows

- chat workflow
- skill generation workflow
- skill run workflow
- skill evolve workflow
- 非 Skill task workflow

### 8.5 API

- `/api/tasks`
- `/api/runs`
- `/api/tools`
- legacy routes backward compatibility

### 8.6 Frontend

- TypeScript typecheck
- Vite build
- Runs 页面渲染
- Run detail 页面状态展示
- 工具调用 timeline 展示
- 空状态和错误状态

## 9. 风险和控制策略

### 9.1 范围膨胀

风险：平台化容易失控，变成什么都想做。

控制：

- 每次只新增一个任务类型
- Skill 相关能力保持兼容
- 不引入复杂权限系统和用户系统

### 9.2 数据源重复

风险：SQLite 和 JSON trace 同时存在，容易不一致。

控制：

- Run 状态以 SQLite 为查询入口
- 完整过程以 JSON trace 为审计入口
- 每个 run 记录 `trace_path`
- 写入失败必须显式记录错误

### 9.3 Tool 权限风险

风险：工具越多，副作用越大。

控制：

- 工具默认只读
- 写文件、shell、网络调用必须显式标记
- 高风险工具先不做，或需要人工确认
- 所有工具调用写入 trace 和 SQLite

### 9.4 UI 复杂度

风险：工作台页面很容易堆成复杂大面板。

控制：

- 优先 Runs / Run Detail
- 再做 Tools / Memory
- 保持页面层组合组件，不堆大量样式
- 长任务必须有状态反馈

## 10. 推荐第一轮实现范围

第一轮不要试图完成整个 Agent 平台。建议只做：

```text
SQLite baseline
Run repository
Run service
FastAPI /api/runs
React Runs list + Run detail
现有 chat / skill workflows 写入 runs
```

第一轮完成后，项目会从“只有 trace 文件可查”升级为：

```text
所有重要任务都有 run_id
所有 run 可以列表查询
每个 run 能看到状态、步骤、产物、trace、HQS
```

这一步是后续 Tool Registry、Workflow Runner、更多业务任务的基础。

## 11. 第一轮验收清单

- [x] 启动项目自动创建 `data/agentforge.db`
- [x] `agentforge serve` 不需要任何外部数据库
- [x] `POST /api/chat` 写入 runs 表
- [x] `POST /api/skills/generate` 写入 runs 表
- [x] `POST /api/skills/run` 写入 runs 表
- [x] `POST /api/skills/evolve` 写入 runs 表
- [x] `GET /api/runs` 返回 run 列表
- [x] `GET /api/runs/{run_id}` 返回 run 详情
- [x] React UI 可以查看 Runs
- [x] React UI 可以打开 Run Detail
- [x] JSON trace 仍然按原规则生成
- [x] `python -m unittest discover -s tests` 通过
- [x] `npm run web:typecheck` 通过
- [x] `npm run web:build` 通过

## 12. 当前实现状态

截至 2026-07-08，本文档定义的第一轮平台化目标已经进入硬化完成状态：

- Phase 1 SQLite Storage Baseline：已实现 `src/agentforge/storage/`、schema migration、临时目录测试和本地 `data/agentforge.db` 自动初始化。
- Phase 2 Run Repository and Run Service：已实现 `src/agentforge/runs/`，chat、tool-calling、Skill generate/run/evolve、Task Router 任务均会写入 runs。
- Phase 3 Tool Registry Formalization：已实现 `src/agentforge/tools/`，统一处理 schema validation、permission、timeout、tool_calls 持久化，并支持原生 JSON Schema。
- Phase 4 Workflow Runner：已实现 `src/agentforge/workflows/`、workflow checkpoints、retry、step handler execution。`trace_diagnosis`、`code_analysis`、`document_analysis`、`data_analysis` 已迁入 `WorkflowRunner.execute()`。
- Phase 5 Task Router and Non-Skill Task Types：已实现 `skill_generate`、`skill_run`、`skill_evolve`、`trace_diagnosis`、`code_analysis`、`document_analysis`、`data_analysis`，并接入聊天 intent 路由。
- Phase 6 FastAPI API Expansion：已实现 `/api/tasks`、`/api/runs`、`/api/tools`、`/api/memory/episodes`、`/api/memory/semantic`、`/api/traces`、`/api/hqs`，保留 legacy routes。
- Phase 7 React Workbench Upgrade：已实现 Dashboard、Runs、Tasks、Skills、Tools、Memory、Trace Viewer、HQS、Settings，以及 Runs Detail 的 trace/tool calls/artifacts/HQS 观察视图。

硬化阶段已补齐：

- 本地真实服务 E2E smoke，覆盖前端入口、chat intent、Task Router、Runs、Trace、Memory、HQS、Tools。
- 共享 JSON Schema 校验器，Task Router 和 ToolSchema 均走同一套校验逻辑。
- 非 Skill 任务执行编排统一，避免继续在 handler 中手写 `record_step()` / `record_run()`。
- Runs UI 对 workflow checkpoints、code_analysis findings、tool calls、artifacts、HQS 的统一观察展示。

仍建议作为后续深度重构处理的事项：

- Skill generation / Skill run / Skill evolve 内部仍保留稳定的子系统循环和手动 run step 记录；它们已经写入 runs、trace 和 artifacts，不再阻塞当前平台化目标，但未来可以按同一 `WorkflowRunner.execute()` 模式逐步重构。
- Chat harness 当前以 `AgentRunLoop` + Tool Registry 为执行核心，并写入 WorkflowRunner/RunService；未来若要完全消除双层 loop，可将 AgentRunLoop 包装为 workflow step handler。

## 13. 结论

引入 SQLite 后，AgentForge 不需要依赖 MySQL，也不需要牺牲 local-first 定位。

正确的演进路径是：

```text
Skill Platform
  -> Run-observable Agent Harness
  -> Tool-registered Agent Platform
  -> Workflow-driven Multi-task Platform
```

下一步最值得先做的是：

```text
SQLite + Runs + Run Detail UI
```

它会直接提升平台可观察性，并为更广泛的业务任务扩展打基础。
