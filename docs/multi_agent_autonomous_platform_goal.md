# AgentForge 成熟多 Agent 自主平台目标文档

## 1. 文档目的

本文档定义 AgentForge 下一阶段以及长期阶段的完整目标：从当前的 Agent Harness / Tool-Calling Harness，演进为一个成熟、可扩展、可观察、可治理的 Multi-Agent Autonomous Platform。

本文档不是保守的“只做最小自治循环”说明，而是明确把成熟 Agent 项目应具备的能力全部纳入目标范围：

- 单 Agent 状态图运行时
- 多 Agent 角色协作
- 长期目标管理
- 自主任务拆解、规划、调度和再规划
- 工具生态和工具权限治理
- 人工审批、预算、审计、回滚
- 多层记忆和知识检索
- Skill 资产生成、演化和复用
- HQS / evaluator / critic / test-driven verification
- Web 工作台、CLI、API 和可观察运行系统

实现仍然分阶段推进，但最终目标必须对齐成熟 Agent 平台，而不是停留在脚本化 workflow 或单轮 tool-calling demo。

## 2. 当前项目定位与差距

AgentForge 当前已经具备一个 Agent 项目的核心骨架：

- `AgentHarness`：固定 Harness workflow 和 tool-calling workflow。
- `ToolRegistry`：工具 schema、权限、timeout、执行和持久化。
- `Task Router`：统一任务类型和 handler。
- `WorkflowRunner` / `RunService`：run、step、artifact、tool call、HQS、checkpoint。
- `Skill` 系统：生成、运行、评估、反思、重写、版本化。
- `MemoryManager`：working、episodic、semantic 三层本地 memory。
- `HQS`：response、skill、system 三层质量评分。
- `Trace`：每次重要运行都有 JSON trace。
- `React Workbench`：可观察 run、task、tool、memory、trace、HQS。

但它还不是成熟完整 Agent 平台。主要差距：

| 能力 | 当前状态 | 成熟目标 |
| --- | --- | --- |
| Agent runtime | `AgentRunLoop`、`ToolCallingLoop`、`WorkflowRunner` 并存 | 统一 typed state graph runtime |
| 自主规划 | 有规则 planner 和 provider tool-call decision | 支持长期目标、任务图、动态再规划、依赖调度 |
| 多 Agent | 基本未实现 | 支持 supervisor、planner、executor、reviewer、memory、skill、toolsmith 等角色协作 |
| 工具生态 | 以内置 Agent 工具和本地分析工具为主 | 扩展到文件、shell、git、HTTP、浏览器、测试、代码编辑、数据、文档、外部系统 |
| 权限治理 | 有 tool permission 基础 | 完整 policy、approval、risk、budget、sandbox、audit |
| 长期自治 | 目标文档有，核心模块未落地 | Goal store、task graph、scheduler、autonomous loop、resume/pause/cancel |
| 记忆 | JSON/JSONL + token overlap | 增加向量检索、摘要、重要性、遗忘、知识图谱或实体记忆 |
| 评估 | HQS 已有 | 多 evaluator、critic agent、test execution、rubric 数据集、人类反馈 |
| 回滚 | 目标中提及 | 变更记录、inverse patch、git revert、memory tombstone、Skill version pointer |
| 协作协议 | 无明确 agent handoff protocol | typed message、blackboard、handoff、debate、consensus、arbitration |
| UI | 工作台已有 | 增加 Goals、Agents、Task Graph、Approvals、Audit、Rollback、Live run graph |

## 3. 成熟 AgentForge 的定义

成熟 AgentForge 应该是：

> 一个本地优先、可观察、可治理、支持多 Agent 协作和长期自主任务推进的 Agent 平台。用户可以给出长期目标，系统可以拆解任务、选择合适 Agent 团队、调用工具、验证结果、记录全过程、在需要时请求审批，并支持暂停、恢复、回滚和持续学习。

目标形态：

```text
User Goal / Request
  -> Goal Manager
  -> Supervisor Agent
  -> Task Graph Planner
  -> Agent Team Formation
  -> Tool / Skill / Memory Context
  -> Parallel or Sequential Execution
  -> Observation and Artifact Capture
  -> Critic / HQS / Test Verification
  -> Replan / Retry / Escalate / Approve
  -> Persist Memory / Skill / Audit / Trace
  -> User-facing Result and Next Actions
```

成熟系统必须同时具备三类能力：

1. **能力执行**：真的能完成代码、文档、数据、Skill、诊断、报告等任务。
2. **自治推进**：能围绕长期目标跨 run、跨会话继续推进。
3. **治理可控**：所有工具调用、写操作、模型调用、审批、失败和回滚都可追踪、可解释、可中止。

## 4. 目标成熟度等级

AgentForge 的成熟度目标按 6 个等级推进。

```text
L0 Script Runner
  单次命令、无统一状态、无记忆、无审计。

L1 Agent Harness
  固定流程，能 parse intent、plan、execute、respond、trace。

L2 Tool-Calling Agent
  模型能在受控工具集中选择下一步，Harness 校验执行。

L3 Autonomous Single-Agent Platform
  有 goal、task graph、scheduler、approval、budget、rollback、长期 memory。

L4 Multi-Agent Collaborative Platform
  有 Agent registry、role、handoff、blackboard、supervisor、critic、parallel execution。

L5 Mature Autonomous Multi-Agent Platform
  支持长期自治、复杂项目推进、工具生态、强治理、实时 UI、可恢复执行、持续学习。
```

当前项目大致处于 `L1.8 - L2.3`：

- Harness 和 tool-calling 已有。
- Runs、trace、HQS、Skill 资产较强。
- 但 goal/task graph/autonomy/multi-agent 还未系统落地。

目标是推进到 `L5`。

## 5. 总体设计原则

### 5.1 不推倒重来

保留 AgentForge 已经形成的差异化资产：

- Skill 版本化系统
- HQS 体系
- JSON trace
- SQLite run index
- React observability workbench
- local-first 文件化产物
- provider-configured 模型适配

下一阶段不是重写所有能力，而是把这些能力纳入更成熟的 agent runtime。

### 5.2 引入成熟运行时思想

当前自研 loop 不应无限膨胀。成熟目标需要吸收现有 Agent 框架的核心思想：

- state graph
- typed state
- checkpoint
- resumable execution
- conditional edge
- human-in-the-loop
- tool schema
- agent handoff
- supervisor-worker
- evaluator/critic loop

可以评估和借鉴 LangGraph、AutoGen、CrewAI、Semantic Kernel 等框架的模式。是否直接引入依赖应由项目阶段决定，但 AgentForge 自身的 runtime contract 必须向成熟 Agent graph 对齐。

### 5.3 Agent 框架选型：自研 Runtime + LangGraph 风格状态图

AgentForge 的目标不是简单套一个现成 Agent 框架，而是形成自己的 Agent runtime contract，再按需吸收成熟框架能力。

推荐选型：

| 层级 | 选型 | 原因 |
| --- | --- | --- |
| 核心运行时 | AgentForge 自研 runtime | 保留本项目的 Skill、HQS、trace、run、memory、local-first、可治理能力 |
| 执行模型 | LangGraph 风格 state graph | 适合多步骤、多分支、可恢复、可 checkpoint、human-in-the-loop 的 Agent 流程 |
| 多 Agent 编排 | 自研 Supervisor / Blackboard / Handoff 协议 | 多 Agent 需要和本项目的权限、预算、审计、rollback、Skill 体系深度结合 |
| LLM / Tool 适配 | provider adapter + tool schema | 避免绑定单一模型平台，继续沿用 provider-configured 方向 |
| 外部框架接入 | adapter/plugin，而不是 core dependency | 可以接入 LangGraph、AutoGen、CrewAI、Semantic Kernel 的能力，但不让它们控制核心数据模型 |

因此，目标文档中的 Agent 不应理解为“用 CrewAI 实现”或“用 AutoGen 实现”，而应理解为：

```text
AgentForge Runtime
  -> LangGraph-style StateGraph abstraction
  -> Agent roles and handoff protocol
  -> Tool / Skill / Memory / HQS / Trace integration
  -> Optional framework adapters
```

原因：

- LangGraph 的状态图思想最适合 AgentForge 的长期目标：checkpoint、resume、conditional edge、human approval、graph visualization。
- CrewAI 更偏角色团队和任务分派，适合借鉴 role/task/crew 概念，但不适合作为底层运行时唯一核心。
- AutoGen 更偏多智能体对话协作，适合借鉴 group chat、speaker selection、agent handoff，但需要额外治理层。
- Semantic Kernel 更适合插件、函数、planner、enterprise integration，可以作为工具和插件生态参考。
- LangChain 可作为工具/模型生态参考，但不建议让核心 runtime 直接退化成 chain 拼接。

最终建议是：**AgentForge 自己做平台内核，LangGraph 化 runtime，兼容外部 Agent 框架，而不是被某个外部框架吞掉。**

实现上可以分三步：

1. 先在 `src/agentforge/runtime/` 中建立自己的 typed state graph、node、edge、checkpoint、event。
2. 再把现有 `AgentHarness`、`ToolCallingLoop`、`WorkflowRunner` 收敛为 runtime node。
3. 最后在 `src/agentforge/integrations/` 或 `src/agentforge/adapters/` 中提供 LangGraph / AutoGen / CrewAI 等可选适配层。

### 5.4 多 Agent 不是群聊

多 Agent 协作不应做成无边界角色聊天。成熟系统里的多 Agent 必须有：

- 明确角色
- 明确输入输出契约
- 明确可用工具
- 明确权限等级
- 明确预算
- 明确 handoff 协议
- 明确评价标准
- 明确停止条件

### 5.5 自主不等于失控

成熟 AgentForge 要实现强自治，但所有自治行为必须可治理：

- 模型可以建议计划，Harness 最终写状态。
- Agent 可以请求高风险工具，但 policy/approval 决定能否执行。
- Agent 可以生成修改，但 change log/rollback 负责追踪和撤销。
- Agent 可以长期推进目标，但 budget/scheduler/stop condition 控制边界。

## 6. 核心能力目标

### 6.1 统一 Agent Runtime

需要把当前分散的运行结构收敛为统一 runtime：

```text
AgentRuntime
  -> StateGraph
  -> Node
  -> Edge
  -> ToolCall
  -> Observation
  -> Checkpoint
  -> Event
```

目标：

- 用 typed state 表达 run 内所有核心字段。
- 用 graph node 表达 parse、plan、tool call、observe、evaluate、respond、memory update。
- 支持条件分支：成功、失败、低 HQS、需要审批、需要用户输入。
- 支持 retry、replan、pause、resume、cancel。
- 支持 checkpoint 后恢复。
- 支持运行事件流，供 Web UI 实时展示。

需要收敛的现有结构：

- `AgentRunLoop`
- `ToolCallingLoop`
- `WorkflowRunner`
- `PlanExecutor`

最终理想结构：

```text
AgentRuntime executes AgentGraph
  AgentGraph nodes call ToolRegistry / TaskRouter / SkillSystem / Memory / HQS
  RunService records every node, tool, artifact, checkpoint
```

### 6.2 长期目标管理

系统需要支持用户创建长期目标：

```text
把 AgentForge 演进为成熟多 Agent 自主平台，分阶段实现 runtime、goal、multi-agent、approval、rollback、web 工作台。
```

Goal 必须支持：

- create
- update
- pause
- resume
- cancel
- complete
- archive
- search
- show status
- show task graph
- show audit trail

Goal 状态：

```text
draft
active
planning
running
waiting_for_approval
waiting_for_user
paused
blocked
completed
failed
cancelled
archived
```

Goal schema 示例：

```json
{
  "goal_id": "goal_...",
  "title": "Build mature multi-agent AgentForge",
  "objective": "...",
  "status": "active",
  "owner": "local_user",
  "created_at": "...",
  "updated_at": "...",
  "success_criteria": [],
  "constraints": [],
  "budgets": {},
  "active_task_graph_id": "graph_...",
  "active_run_id": "run_...",
  "memory_scope": "goal_..."
}
```

### 6.3 自主任务图

长期目标必须拆解成任务图，而不是普通列表。

```text
Goal
  -> Milestone
  -> Task
  -> Subtask
  -> Step
  -> Tool call
```

任务图能力：

- DAG dependencies
- priority
- status
- assigned agent
- estimated cost
- risk level
- required approvals
- artifacts
- evaluation criteria
- retry policy
- rollback policy

任务状态：

```text
pending
ready
scheduled
running
waiting_for_tool
waiting_for_approval
waiting_for_user
reviewing
completed
failed
blocked
skipped
cancelled
rolled_back
```

TaskNode 示例：

```json
{
  "task_id": "task_...",
  "goal_id": "goal_...",
  "title": "Introduce typed AgentState",
  "description": "...",
  "status": "ready",
  "depends_on": [],
  "assigned_agent": "planner_agent",
  "risk_level": "medium",
  "expected_artifacts": ["design_doc", "code_patch", "tests"],
  "acceptance_criteria": [],
  "attempt_count": 0,
  "max_attempts": 3
}
```

### 6.4 自主规划与再规划

成熟系统需要规划器和再规划器。

Planner 负责：

- 从 goal 生成 milestone。
- 从 milestone 生成 task graph。
- 估算任务风险、预算、依赖。
- 选择需要的 Agent 团队。
- 指定验收标准。

Replanner 负责：

- 根据失败、低 HQS、测试失败、用户反馈调整任务图。
- 替换 agent。
- 拆小任务。
- 降低风险。
- 请求用户输入。
- 标记 blocked。

计划不是一次性产物，而是持续维护的执行对象。

### 6.5 Multi-Agent 协作

成熟 AgentForge 必须支持多 Agent。

#### 6.5.1 Agent Registry

每个 Agent 都应被注册为可配置角色：

```json
{
  "agent_id": "planner_agent",
  "name": "Planner Agent",
  "role": "planner",
  "description": "Decomposes goals into task graphs.",
  "model_policy": {},
  "allowed_tools": [],
  "memory_scopes": ["goal", "semantic"],
  "permission_level": "read",
  "input_schema": {},
  "output_schema": {},
  "quality_rubric": {}
}
```

#### 6.5.2 核心 Agent 角色

第一批成熟多 Agent 角色：

- **Supervisor Agent**：总控，分配任务，决定是否继续、暂停、升级审批。
- **Planner Agent**：把目标拆成任务图，维护计划。
- **Research Agent**：检索项目文档、trace、memory、代码上下文和外部资料。
- **Executor Agent**：调用工具执行任务，生成 artifact。
- **Code Agent**：代码阅读、修改、重构和测试。
- **Reviewer Agent**：代码审查、输出审查、风险检查。
- **HQS / Critic Agent**：使用 HQS、rubric、测试结果评估质量。
- **Skill Architect Agent**：生成、选择、演化 Skill。
- **Memory Curator Agent**：整理长期记忆、总结、去重、过期和知识化。
- **Toolsmith Agent**：提出和生成新工具 schema、测试工具。
- **Security / Policy Agent**：评估风险、权限、敏感信息和高危操作。
- **Report Agent**：生成面向用户的报告和执行摘要。

#### 6.5.3 协作模式

需要支持多种协作协议：

```text
Supervisor -> Worker
Planner -> Executor -> Reviewer
Research -> Planner
Executor -> Critic -> Replan
Debate / Compare
Consensus
Handoff
Parallel map-reduce
Blackboard collaboration
```

最小多 Agent 闭环：

```text
Supervisor
  -> Planner creates task graph
  -> Research gathers context
  -> Executor performs task
  -> Reviewer checks output
  -> Critic scores HQS
  -> Supervisor decides accept / retry / replan / ask approval
```

### 6.6 Blackboard 与消息协议

多 Agent 不能只靠函数调用传字典。需要统一通信协议。

#### AgentMessage

```json
{
  "message_id": "msg_...",
  "run_id": "run_...",
  "goal_id": "goal_...",
  "task_id": "task_...",
  "from_agent": "planner_agent",
  "to_agent": "executor_agent",
  "message_type": "task_assignment",
  "content": {},
  "artifacts": [],
  "created_at": "..."
}
```

#### Blackboard

Blackboard 是多 Agent 共享工作区：

- goal summary
- current task graph
- decisions
- observations
- open questions
- artifacts
- warnings
- approvals
- evaluation results
- final report draft

所有 Agent 读写 Blackboard 都必须写 audit event。

### 6.7 工具生态

成熟 AgentForge 需要更完整的工具生态。工具应按风险分层。

#### 只读工具

- project file read
- directory listing
- grep/search
- trace read
- run read
- memory read
- skill read
- config read with secret redaction

#### 写入工具

- file patch
- Skill write
- memory write
- report write
- task graph update
- config draft write

#### 执行工具

- test runner
- lint/typecheck/build
- safe shell command
- Python/Node script runner
- workflow execution

#### 网络工具

- HTTP fetch
- API client
- package docs lookup
- browser automation

#### Git 工具

- status
- diff
- stage
- commit
- branch
- push
- PR creation

#### 高风险工具

- delete / move
- recursive file operations
- credential-related operations
- external paid API batch calls
- git push / release
- shell with write/destructive impact

所有工具必须声明：

- schema
- permission level
- side effects
- risk level
- timeout
- approval requirement
- rollback strategy
- artifact output

#### 文件来源治理

成熟 AgentForge 应支持项目内文件和项目外文件，但不能简单放开任意绝对路径。文件处理应统一进入 File Source Management。

当前实现的合理部分：

- Web 上传会把用户选择的外部文件复制到 `data/uploads/`，再以项目内文件处理。
- `code_analysis`、`document_analysis`、`data_analysis` 当前都要求路径留在 `project_root` 下。
- 这种实现安全，适合作为 MVP。

当前实现的不足：

- `/chat` 请求虽然接收 `uploads` 字段，但当前后端主要依赖前端把上传路径拼进自然语言 message。
- 上传文件没有作为结构化 `source_ref` 进入 Agent runtime、Task Router、Trace 和 Context。
- 项目外绝对路径目前会被拒绝，不能表达“用户显式授权的外部目录”。

成熟目标应区分三类文件来源：

| source_type | 含义 | 默认权限 | 典型路径 |
| --- | --- | --- | --- |
| `project` | 项目内文件 | read，按工具策略写入 | `src/...`、`docs/...` |
| `uploaded` | 用户上传后复制进项目的数据 | read | `data/uploads/...` |
| `external_mount` | 用户显式授权的项目外目录或文件 | read-only 默认 | `D:/datasets/...`、`C:/Users/.../Documents/...` |

外部文件目标：

- 支持通过 Web 上传导入外部文件。
- 支持通过配置或 UI 显式挂载项目外目录。
- 支持 Task Router 使用结构化 `source_refs`，而不是只从自然语言中猜路径。
- 支持 Agent、Task、Knowledge、Context 统一引用同一套 source records。
- 支持 source citation，能追溯原始文件、导入副本、hash、读取时间和授权策略。
- 支持外部文件进入 Knowledge Layer 前做隐私策略检查。

SourceRef 示例：

```json
{
  "source_id": "src_...",
  "source_type": "external_mount",
  "original_path": "D:/datasets/sales.csv",
  "resolved_path": "D:/datasets/sales.csv",
  "display_name": "sales.csv",
  "content_hash": "sha256:...",
  "access_mode": "read_only",
  "allowed_tasks": ["data_analysis", "knowledge_index"],
  "policy": {
    "allow_read": true,
    "allow_write": false,
    "allow_embedding": false
  }
}
```

File source 约束：

- 默认拒绝任意项目外绝对路径。
- 项目外路径必须来自用户上传、显式 mount、或一次性 approval。
- 外部来源默认 read-only。
- 文件读取必须限制大小、数量、后缀、排除目录和跟随 symlink 策略。
- 写入、删除、移动外部文件必须默认禁止，除非未来有明确治理和回滚能力。
- 所有外部文件读取、索引、embedding、复制、删除都要写 trace 和 audit。
- Skill、taskset、trace、provider config 等系统资产仍应限制在项目内专用目录，不应通过 external_mount 任意加载。

### 6.8 审批系统

成熟系统必须有 human-in-the-loop。

ApprovalRequest 示例：

```json
{
  "approval_id": "approval_...",
  "goal_id": "goal_...",
  "run_id": "run_...",
  "task_id": "task_...",
  "requested_by": "executor_agent",
  "action_type": "file_patch",
  "risk_level": "medium",
  "summary": "Modify Agent runtime state model.",
  "impact": [],
  "arguments": {},
  "status": "pending",
  "expires_at": null
}
```

审批动作：

- approve
- deny
- request_changes
- approve_once
- approve_for_goal
- approve_for_session
- expire

审批策略：

```json
{
  "policy_id": "default_local_policy",
  "auto_approve": ["read"],
  "require_confirmation": ["write", "execute", "network", "model_spend", "git_stage", "git_commit"],
  "deny_by_default": ["destructive", "admin", "credential_access"],
  "per_goal_overrides": {}
}
```

版本化治理对象：

- system prompt
- Agent role prompt
- AgentSpec
- planner prompt
- reviewer / critic rubric
- model routing policy
- file source policy
- approval policy
- memory write policy
- retrieval/chunking policy

这些对象会直接改变 Agent 行为，必须保存版本、hash、created_at、created_by、active pointer 和变更原因。每次 run 应记录实际使用的 prompt/policy/AgentSpec 版本，便于回溯“为什么这次 Agent 行为和上次不同”。

### 6.9 预算系统

预算不仅是 token 数，还包括工具、时间、风险和变更。

预算类型：

- max wall-clock time
- max iterations
- max model calls
- max tokens
- max provider cost
- max tool calls
- max write operations
- max file changes
- max test runs
- max network calls
- max consecutive failures
- max approval waits

预算耗尽时，系统必须：

- stop
- save checkpoint
- write audit event
- summarize progress
- ask user to extend budget or reduce scope

### 6.10 审计日志

Audit log 必须覆盖所有关键事件：

- goal created / updated / paused / resumed / completed
- task graph created / revised
- task scheduled / started / completed / failed
- agent assigned / handoff
- model called
- tool requested / approved / denied / executed
- file changed
- memory updated
- Skill generated / evolved
- HQS evaluated
- budget consumed
- rollback recorded / executed

AuditEvent 示例：

```json
{
  "audit_id": "audit_...",
  "created_at": "...",
  "actor_type": "agent",
  "actor_id": "executor_agent",
  "event_type": "tool_call_executed",
  "goal_id": "goal_...",
  "run_id": "run_...",
  "task_id": "task_...",
  "risk_level": "medium",
  "summary": "...",
  "details": {},
  "trace_id": "trace_...",
  "approval_id": null
}
```

### 6.11 回滚系统

成熟系统必须记录变更并尽量可回滚。

变更类型：

- file patch
- file create
- file delete
- Skill version create
- memory write
- config change
- database row change
- git operation
- generated artifact

ChangeRecord 示例：

```json
{
  "change_id": "change_...",
  "goal_id": "goal_...",
  "run_id": "run_...",
  "task_id": "task_...",
  "type": "file_patch",
  "target": "src/agentforge/agent/state.py",
  "before_hash": "...",
  "after_hash": "...",
  "patch_path": "data/autonomy/rollback/change_....patch",
  "rollback_available": true,
  "rollback_status": "not_applied"
}
```

回滚策略：

- 文件修改：保存 patch 和 inverse patch。
- 文件创建：可删除或 tombstone。
- 文件删除：保存 snapshot。
- Skill：不删除旧版本，通过 active/best version 指针回退。
- Memory：append-only，使用 superseded/tombstone。
- Git：优先依赖 commit/revert。

### 6.12 记忆和知识系统

当前 memory 是良好 MVP，但成熟平台需要更强记忆。

Memory 层级：

- working memory：当前 run 状态。
- episodic memory：运行经历、任务结果、用户反馈。
- semantic memory：Skill、偏好、知识摘要。
- goal memory：长期目标上下文。
- agent memory：每个 Agent 的角色经验和弱点。
- tool memory：工具成功/失败模式。
- project memory：项目结构、约定、模块关系。
- retrieval references：指向 Knowledge Layer 检索结果、source citation 和相关 artifact。
- knowledge graph：实体、文件、模块、Skill、任务关系。

Memory 操作：

- add
- retrieve
- summarize
- consolidate
- decay
- pin
- supersede
- delete/tombstone
- cite source

Memory 写入必须可审计，不允许模型静默污染长期记忆。

### 6.13 知识库与混合检索

成熟 AgentForge 需要引入 Knowledge Layer。它和 Memory 不同：

- Memory 记录 Agent 经验、用户偏好、历史任务结果和反思。
- Knowledge Base 记录稳定事实、项目资料、代码结构、文档、Skill、trace/artifact 摘要和可引用知识。
- ContextManager 从 Memory、Knowledge Base、Trace、Artifact、State 中检索、排序、压缩，再组装当前模型调用的 context。

目标形态：

```text
Docs / Code / Skills / Traces / Artifacts / Handoff
  -> Knowledge Indexer
  -> Chunker
  -> Embedding Provider
  -> Local Hybrid Knowledge Store
  -> Retriever / Reranker / Citation
  -> ContextManager
```

知识库第一目标是 local-first hybrid retrieval：

- 原文保存在本地文件、JSONL 或 SQLite 中。
- SQLite FTS5 / BM25 负责关键词和精确标识符检索。
- 向量检索负责语义相似度检索。
- Metadata filter 负责按来源、时间、模块、scope、可信度过滤。
- Citation 负责让进入 context 的知识可以追溯来源。
- Reranker 后续可选接入，提高召回结果排序质量。

AgentForge 计划使用 `qwen3-vl-embedding` 作为首选 embedding 模型。该模型来自 Qwen / DashScope 生态，适合构建多模态知识库：

- 支持文本、图片、截图、视频和混合模态输入。
- 适合文档检索、代码资料检索、截图/视觉文档检索、跨模态检索。
- 支持 fused embedding，用于把文本、图片、视频等内容融合成一个可检索向量。
- 支持自定义向量维度，维度越高通常保留更多语义信息，但存储和检索成本更高。
- 多模态 embedding 调用应通过 DashScope SDK 或直接 API；不要假设 OpenAI compatible API 能覆盖所有多模态能力。

多模态 ingestion 要求：

- 图片、截图、视频、PDF 页面等二进制资料必须先进入 File Source Management，生成 `SourceRef`。
- 图片需要保存 hash、尺寸、MIME、缩略图引用和隐私级别。
- 视频需要限制大小和时长，按策略抽帧；抽帧结果作为派生 source refs。
- OCR、caption、视觉摘要可以作为派生 text chunks，但必须引用原始 source。
- 私有多模态资料进入外部 embedding API 前必须经过 policy。
- 任何二进制原文不应直接塞入 context，只能以摘要、引用或受控 preview 进入。

推荐默认配置：

```json
{
  "knowledge": {
    "enabled": true,
    "retrieval_mode": "hybrid",
    "embedding_provider": "dashscope",
    "embedding_model": "qwen3-vl-embedding",
    "embedding_dimensions": 1024,
    "enable_multimodal": true,
    "enable_fusion": true,
    "allow_external_embedding_for_private_code": false,
    "cache_embeddings": true
  }
}
```

配置原则：

- `qwen3-vl-embedding` 是默认目标模型，但必须通过 provider adapter 抽象，后续可替换。
- 私有代码、私有文档是否允许发送到外部 embedding API，必须由配置显式开启。
- 每个 chunk 需要保存 `source_path`、`source_type`、`line_range`、`content_hash`、`indexed_at`、`updated_at`、`embedding_model`、`embedding_dimensions`。
- embedding 结果必须本地缓存，内容 hash 未变化时不重复调用 API。
- 不允许只有向量，没有原文和 citation。
- 检索结果进入 context 前必须经过 ContextManager 预算和来源审查。

检索质量评估要求：

- Knowledge Layer 必须记录 retrieval query、召回 chunks、ranking score、citation、staleness 和进入 context 的最终片段。
- 需要支持 retrieval evaluation dataset，用于评估 recall@k、citation accuracy、stale retrieval rate 和 source coverage。
- 用户纠错、Reviewer/Critic 发现的错误引用，应能回写为 retrieval feedback。
- embedding model、chunking strategy、reranker、metadata filter 的版本变化必须可追踪，避免检索质量变化无法回溯。

知识库应索引：

- `README.md`
- `AGENTS.md`
- `docs/*.md`
- `skills/**/SKILL.md`
- tasksets、HQS rubric、trace 摘要、artifact 摘要
- `docs/development_handoff.md`
- 项目文件树、模块摘要、代码符号摘要
- 架构决策、用户长期偏好、重要约束
- UI 截图、视觉文档、图表、报告等多模态资料

KnowledgeRecord 示例：

```json
{
  "document_id": "doc_...",
  "source_path": "docs/multi_agent_autonomous_platform_goal.md",
  "source_type": "markdown",
  "title": "AgentForge mature multi-agent platform goal",
  "content_hash": "sha256:...",
  "indexed_at": "2026-07-09T00:00:00Z",
  "metadata": {
    "scope": "project",
    "trust_level": "high",
    "language": "zh-CN"
  }
}
```

KnowledgeChunk 示例：

```json
{
  "chunk_id": "chunk_...",
  "document_id": "doc_...",
  "text": "...",
  "source_path": "docs/multi_agent_autonomous_platform_goal.md",
  "line_start": 724,
  "line_end": 848,
  "content_hash": "sha256:...",
  "embedding_provider": "dashscope",
  "embedding_model": "qwen3-vl-embedding",
  "embedding_dimensions": 1024,
  "vector_ref": "data/knowledge/embeddings/chunk_....bin",
  "citations": [
    {
      "type": "file",
      "path": "docs/multi_agent_autonomous_platform_goal.md",
      "line_start": 724,
      "line_end": 848
    }
  ]
}
```

参考资料：

- Alibaba Cloud Model Studio Embedding 文档：https://www.alibabacloud.com/help/en/model-studio/embedding
- Qwen3-VL-Embedding-8B model card：https://huggingface.co/Qwen/Qwen3-VL-Embedding-8B

### 6.14 上下文工程与压缩

成熟自主 Agent 必须把 `context`、`memory`、`state`、`trace`、`artifact` 分开治理，不能把 memory 简单当成更长的 prompt。

核心定义：

| 概念 | 职责 | 生命周期 | 是否直接进入模型窗口 |
| --- | --- | --- | --- |
| Context | 当前一次模型调用实际看到的输入 | 单次 model call 或当前 step | 是 |
| Context Compression | 把长对话、长 trace、长工具输出压缩成摘要、状态或引用 | 当前 run 为主，可持久保存 | 压缩结果会进入 |
| Memory | 跨 step、run、session 保存和检索的长期知识 | 长期 | 不一定，只有被召回片段进入 |
| State | 当前任务图、Agent 状态、预算、审批、checkpoint | run / goal 生命周期 | 部分进入 |
| Trace / Artifact | 原始事实、日志、diff、测试输出、文件产物 | 长期 | 通常只进入摘要和引用 |

目标组件：

```text
ContextManager
  -> ContextRetriever
  -> ContextBudgeter
  -> ContextCompressor
  -> ContextAssembler
  -> ContextAuditor
```

ContextManager 职责：

- 根据当前 goal、task、agent、tool、budget 组装模型输入。
- 从 memory、trace、artifact、blackboard、run state 中检索候选信息。
- 按相关性、时效性、风险等级和来源可信度排序。
- 控制 token budget，区分 system instruction、policy、task state、retrieved memory、tool schema、artifact summary。
- 对长上下文做压缩，并保存 compression record。
- 为每个 context 片段保留 source citation，能够追溯到 memory id、trace id、artifact path、message id 或 file path。
- 记录每次模型调用的 context manifest，但不强制保存完整敏感 prompt。

ContextCompression 要求：

- 不删除原始事实，只生成摘要、状态快照或引用。
- 对代码 diff、测试失败、错误日志、审批理由等高风险信息，必须保留原始 artifact。
- 摘要必须记录来源范围和压缩策略。
- 压缩结果必须能被后续 Agent 复用，也能被 reviewer/critic 检查。
- 过期或低可信 memory 进入 context 时要标记 warning。

多 Agent context 要求：

- 每个 Agent 有独立 role context、tool context、memory scope 和权限说明。
- Supervisor 能看到全局 task graph、blackboard 和关键 agent summaries。
- Executor 不应自动继承所有私有 memory，除非 handoff 明确传递。
- Reviewer/Critic 必须能看到执行产物、验证证据和关键决策来源。
- Handoff 时生成 handoff context package，包含任务状态、已知事实、待验证假设、阻塞点和产物引用。

ContextRecord 示例：

```json
{
  "context_id": "ctx_...",
  "run_id": "run_...",
  "task_id": "task_...",
  "agent_id": "planner_agent",
  "model_call_id": "model_...",
  "token_budget": 12000,
  "estimated_tokens": 8400,
  "sections": [
    {
      "name": "goal_state",
      "tokens": 900,
      "sources": ["goal_..."]
    },
    {
      "name": "retrieved_memory",
      "tokens": 1800,
      "sources": ["mem_...", "episode_..."]
    }
  ],
  "compression_records": ["cmp_..."],
  "warnings": ["stale_memory_included"]
}
```

ContextCompressionRecord 示例：

```json
{
  "compression_id": "cmp_...",
  "source_type": "trace",
  "source_refs": ["trace_...", "artifact://runs/.../test_output.txt"],
  "strategy": "structured_summary_with_citations",
  "before_tokens": 18000,
  "after_tokens": 2200,
  "summary_ref": "data/context/compressions/cmp_....md",
  "loss_risk": "medium"
}
```

### 6.15 Skill 资产系统升级

Skill 是 AgentForge 的核心特色，成熟阶段应升级为能力资产市场。

目标：

- Skill registry
- Skill metadata
- Skill tags
- Skill dependency
- Skill quality history
- Skill tasksets
- Skill benchmark
- Skill selection by semantic memory + vector search
- Skill evolution policy
- Skill deprecation
- Skill promotion to stable
- Skill rollback to previous best version

Skill 不只是 Markdown 文件，而是 Agent 团队可复用的长期能力。

### 6.16 评估与验证体系

成熟 Agent 项目不能只靠模型自信输出。需要多层验证：

- deterministic checks
- HQS
- rubric evaluator
- Critic Agent
- Reviewer Agent
- test runner
- lint/typecheck/build
- schema validation
- artifact validation
- user feedback
- regression benchmark

对于代码任务，完成定义必须包含：

- 修改范围清楚。
- 相关测试通过。
- 没有破坏现有行为。
- 有 trace、run、artifact、audit。
- 高风险操作有审批记录。

### 6.17 失败恢复

失败恢复是成熟度核心。

失败分类：

- model_output_invalid
- tool_schema_error
- tool_permission_denied
- tool_timeout
- provider_error
- test_failed
- hqs_low
- task_blocked
- dependency_failed
- budget_exceeded
- approval_denied
- rollback_failed

恢复动作：

- retry
- repair
- replan
- assign different agent
- ask user
- request approval
- reduce scope
- run diagnostics
- rollback
- mark blocked
- mark failed

RecoveryRecord 示例：

```json
{
  "failure_id": "failure_...",
  "error_type": "test_failed",
  "recoverable": true,
  "selected_strategy": "replan",
  "attempted_actions": [],
  "result": "running",
  "next_task_id": "task_..."
}
```

## 7. 推荐架构

建议新增和调整模块如下。

### 7.1 Runtime

```text
src/agentforge/runtime/
  __init__.py
  state.py
  graph.py
  node.py
  edge.py
  events.py
  checkpoint.py
  executor.py
  resumable.py
  streaming.py
```

职责：

- 统一 Agent run 状态图。
- 支持 checkpoint/resume。
- 发出 event stream。
- 统一 node execution、retry、error handling。
- 替代或包装当前 `AgentRunLoop`、`ToolCallingLoop`、`WorkflowRunner` 的重叠职责。

### 7.2 Multi-Agent

```text
src/agentforge/multi_agent/
  __init__.py
  agent.py
  registry.py
  team.py
  supervisor.py
  handoff.py
  blackboard.py
  message.py
  collaboration.py
  consensus.py
  roles.py
```

职责：

- 定义 Agent role 和 contract。
- 注册 Agent。
- 组建 Agent team。
- 管理 handoff 和 blackboard。
- 支持 supervisor-worker、debate、review、parallel map-reduce。

### 7.3 Autonomy

```text
src/agentforge/autonomy/
  __init__.py
  goals.py
  goal_store.py
  task_graph.py
  planner.py
  replanner.py
  scheduler.py
  autonomous_loop.py
  stop_conditions.py
  recovery.py
```

职责：

- Goal lifecycle。
- Task graph lifecycle。
- Scheduler。
- Autonomous loop。
- Failure recovery。
- Pause/resume/cancel。

### 7.4 Governance

```text
src/agentforge/governance/
  __init__.py
  policy.py
  risk.py
  approval.py
  budget.py
  audit_log.py
  rollback.py
  change_log.py
  sandbox.py
```

职责：

- 风险评估。
- 权限策略。
- 人工审批。
- 预算消费。
- 审计日志。
- 变更记录和回滚。
- 工具 sandbox 策略。

### 7.5 Memory 2.0

```text
src/agentforge/memory/
  memory_manager.py
  stores.py
  vector_store.py
  summarizer.py
  consolidation.py
  knowledge_graph.py
  retrieval.py
  policies.py
```

职责：

- 保留三层 memory。
- 增加向量检索和摘要。
- 支持 goal/agent/tool/project memory scope。
- 支持 memory policy、重要性、过期和引用。

### 7.6 Knowledge Layer

```text
src/agentforge/knowledge/
  __init__.py
  indexer.py
  chunker.py
  embedding.py
  providers.py
  store.py
  fts_store.py
  vector_store.py
  retriever.py
  reranker.py
  citations.py
  freshness.py
  policies.py
```

职责：

- 索引 docs、skills、handoff、trace/artifact 摘要、代码结构和多模态资料。
- 调用 provider adapter 生成 embedding，默认目标模型为 `qwen3-vl-embedding`。
- 维护本地原文、chunk、metadata、FTS 索引和向量索引。
- 支持 hybrid retrieval：FTS/BM25 + vector + metadata filter。
- 为检索结果生成 source citation。
- 对私有代码和外部 embedding API 调用执行 policy 检查。
- 向 ContextManager 输出带来源、分数、风险和 freshness 的候选知识片段。

### 7.7 Context Engineering

```text
src/agentforge/context/
  __init__.py
  manager.py
  retriever.py
  budgeter.py
  compressor.py
  assembler.py
  auditor.py
  citations.py
  records.py
```

职责：

- 组装每次 model call 的 context。
- 管理 context token budget。
- 从 memory、state、trace、artifact、blackboard 中检索候选内容。
- 压缩长上下文并保留来源引用。
- 记录 context manifest、compression record 和 stale/risk warning。
- 支持多 Agent handoff context package。

### 7.8 File Source Management

```text
src/agentforge/files/
  __init__.py
  source_ref.py
  resolver.py
  access_policy.py
  ingestion.py
  mounts.py
  scanners.py
  citations.py
  audit.py
```

职责：

- 统一解析项目内路径、上传文件和显式授权的项目外路径。
- 提供 `SourceRef`、`FileSourceResolver`、`ExternalMountRegistry`。
- 管理 uploaded/imported/external_mount 的来源、hash、权限和生命周期。
- 为 Task Router、Knowledge Layer、ContextManager、Tool Ecosystem 提供统一文件引用。
- 替代 `code_analysis`、`document_analysis`、`data_analysis` 中重复的 `_resolve_under_project` 逻辑。
- 让 `/chat` 结构化消费 `uploads` 字段，而不是只依赖 message 中的路径文本。
- 记录所有外部文件读取、导入、索引和 embedding 行为。

### 7.9 Tool Ecosystem

```text
src/agentforge/tools/
  builtin/
    file_tools.py
    patch_tools.py
    shell_tools.py
    git_tools.py
    test_tools.py
    http_tools.py
    browser_tools.py
    data_tools.py
    doc_tools.py
    code_tools.py
```

职责：

- 扩展实际行动能力。
- 每个工具必须接入 schema、permission、risk、approval、audit、rollback。

### 7.10 Evaluation

```text
src/agentforge/evaluation/
  __init__.py
  rubrics.py
  evaluators.py
  critic_agent.py
  regression.py
  benchmark.py
  feedback.py
```

职责：

- 扩展 HQS。
- 支持多 evaluator。
- 支持 benchmark 和 regression。
- 支持用户反馈。

## 8. 数据目录建议

```text
data/autonomy/
  goals.jsonl
  goal_state.json
  task_graphs/
    <goal_id>.json
  schedules.jsonl
  recovery.jsonl

data/multi_agent/
  agent_registry.json
  teams.jsonl
  messages.jsonl
  blackboards/
    <run_id>.json

data/governance/
  approvals.jsonl
  audit.jsonl
  budgets.json
  changes.jsonl
  rollback/
    <change_id>.patch

data/memory/
  working_memory.json
  episodes.jsonl
  semantic_memory.json
  goal_memory.jsonl
  agent_memory.json
  tool_memory.json

data/knowledge/
  documents.jsonl
  chunks.jsonl
  index.sqlite
  fts.sqlite
  ingestion_runs.jsonl
  citations.jsonl
  embeddings/
    <chunk_id>.bin
  multimodal_assets/
    <asset_id>.json
  provider_cache/
    dashscope_qwen3_vl_embedding/

data/files/
  sources.jsonl
  mounts.json
  ingestion_runs.jsonl
  access_events.jsonl
  imported/
    <source_id>/

data/uploads/
  <yyyyMMdd>/
    <uuid>_<safe_filename>

data/context/
  context_records.jsonl
  context_manifests/
    <context_id>.json
  compressions/
    <compression_id>.md
  handoff_packages/
    <handoff_id>.json
  prompt_snapshots_disabled_by_default/
    <model_call_id>.json

data/prompts/
  prompt_versions.jsonl
  agent_specs.jsonl
  policy_versions.jsonl
  rubrics.jsonl

data/evaluation/
  retrieval_eval.jsonl
  retrieval_feedback.jsonl
```

`prompt_snapshots_disabled_by_default/` 表示成熟系统可以支持调试用 prompt snapshot，但默认关闭。启用时只能保存 redacted prompt snapshot 或 prompt manifest，不能保存 secret 明文、未授权私有文件全文、未脱敏 provider error。

SQLite 后续应增加或迁移表：

- goals
- task_nodes
- agent_messages
- agent_assignments
- approvals
- audit_events
- change_records
- budget_events
- recovery_records
- memory_records
- knowledge_documents
- knowledge_chunks
- knowledge_embeddings
- knowledge_citations
- knowledge_ingestion_runs
- knowledge_retrieval_events
- retrieval_feedback
- file_sources
- external_mounts
- file_access_events
- prompt_versions
- policy_versions
- agent_spec_versions
- context_records
- context_compression_records
- context_sources

## 9. Web 工作台目标

成熟多 Agent 平台需要 Web 从 run observability 升级为 Agent operations center。

### 9.1 新页面

```text
Agent
Goals
Goal Detail
Task Graph
Agents
Agent Team
Approvals
Audit
Rollback
Budgets
Memory
Knowledge
Files / Sources
Context
Skills
Tools
Runs
Traces
HQS / Evaluation
Settings
```

### 9.2 Goal Detail

展示：

- goal status
- objective
- success criteria
- task graph
- current active task
- assigned agents
- budget usage
- approvals
- latest artifacts
- audit timeline
- pause/resume/cancel controls

### 9.3 Multi-Agent Run View

展示：

- Supervisor 决策
- Agent handoff timeline
- Blackboard
- Agent messages
- Tool calls
- Critic reviews
- HQS
- Generated artifacts
- Recovery actions

### 9.4 Approval Center

展示：

- pending approvals
- risk level
- proposed action
- affected files/resources
- diff preview
- approve/deny/request changes
- approval history

### 9.5 Rollback Center

展示：

- change records
- rollback availability
- inverse patch preview
- rollback result
- affected runs/goals/tasks

### 9.6 Live Execution

成熟 UI 需要实时进度：

- event stream
- current node
- active agent
- current tool call
- waiting reason
- checkpoint status

### 9.7 Context Inspector

Context Inspector 是成熟自主 Agent 的关键功能页，用来观察和治理每次模型调用的上下文。

展示：

- run / task / agent / model call 维度的 context 列表。
- 每次 context 的 section 构成，例如 system、policy、goal、task state、memory recall、tool schema、artifact summary、blackboard。
- token budget、estimated tokens、实际压缩前后 token。
- memory 召回结果：进入 context 的片段、被拒绝的片段、拒绝原因、相关性分数。
- context compression chain：原始来源、压缩策略、摘要结果、loss risk。
- source citation：memory id、trace id、artifact path、message id、file path。
- stale / low confidence / high risk warning。
- 多 Agent handoff context package。
- reviewer/critic 使用的证据上下文。
- 相邻 step 的 context diff。

交互：

- 查看 context manifest。
- 查看压缩摘要和原始 artifact 引用。
- 标记 memory 片段为 stale、pinned、superseded。
- 将一次 context 组装保存为 regression case。
- 导出 context report，用于调试 prompt、memory 污染和压缩丢失。

### 9.8 Knowledge Base

Knowledge Base 页面用于观察和治理本地知识库。

展示：

- indexed documents
- chunks
- embedding model and dimensions
- ingestion runs
- changed / stale / failed documents
- hybrid search results
- vector search score
- keyword search score
- metadata filters
- source citations
- multimodal assets
- private-data policy status

交互：

- 触发 index / reindex。
- 搜索知识库。
- 查看 document、chunk、embedding metadata。
- 查看 chunk 来源和引用范围。
- 标记 document stale。
- 删除或 tombstone 污染知识。
- 查看 `qwen3-vl-embedding` provider 配置和缓存命中率。

### 9.9 Files / Sources

Files / Sources 页面用于管理 Agent 可处理的文件来源。

展示：

- project files
- uploaded files
- imported external files
- external mounts
- source refs
- source hash
- source size and suffix
- allowed tasks
- read/index/embedding policy
- latest access events
- stale or missing source warnings

交互：

- 上传文件并生成 `uploaded` source refs。
- 导入外部文件副本到 `data/files/imported/`。
- 显式添加 read-only external mount。
- 禁用或移除 external mount。
- 查看 source 被哪些 run、task、knowledge chunk、context 引用。
- 对单个 source 触发 analysis、knowledge index 或 context preview。
- 标记 source stale、superseded 或 tombstone。

## 10. API 目标

### Goal API

```text
POST /api/goals
GET  /api/goals
GET  /api/goals/{goal_id}
POST /api/goals/{goal_id}/plan
POST /api/goals/{goal_id}/run
POST /api/goals/{goal_id}/pause
POST /api/goals/{goal_id}/resume
POST /api/goals/{goal_id}/cancel
POST /api/goals/{goal_id}/archive
```

### Task Graph API

```text
GET  /api/goals/{goal_id}/tasks
GET  /api/tasks/{task_id}
POST /api/tasks/{task_id}/retry
POST /api/tasks/{task_id}/skip
POST /api/tasks/{task_id}/assign
```

### Multi-Agent API

```text
GET  /api/agents
GET  /api/agents/{agent_id}
GET  /api/runs/{run_id}/agents
GET  /api/runs/{run_id}/messages
GET  /api/runs/{run_id}/blackboard
```

### Governance API

```text
GET  /api/governance/approvals
POST /api/governance/approvals/{approval_id}/approve
POST /api/governance/approvals/{approval_id}/deny
POST /api/governance/approvals/{approval_id}/request-changes
GET  /api/governance/audit
GET  /api/governance/changes
POST /api/governance/changes/{change_id}/rollback
GET  /api/governance/budgets
GET  /api/governance/locks
GET  /api/governance/model-usage
```

短路径 `/api/approvals`、`/api/audit`、`/api/changes` 可以作为兼容 alias，但成熟 API 以 `/api/governance/*` 为准。

### Runtime API

```text
GET  /api/runs/{run_id}/events
GET  /api/runs/{run_id}/checkpoints
POST /api/runs/{run_id}/resume
POST /api/runs/{run_id}/cancel
```

### Context API

```text
GET  /api/runs/{run_id}/contexts
GET  /api/contexts/{context_id}
GET  /api/contexts/{context_id}/manifest
GET  /api/contexts/{context_id}/sources
GET  /api/contexts/{context_id}/diff?against=<context_id>
GET  /api/compressions/{compression_id}
POST /api/contexts/{context_id}/save-regression
POST /api/memory/{memory_id}/mark-stale
POST /api/memory/{memory_id}/pin
POST /api/memory/{memory_id}/supersede
```

### Knowledge API

```text
GET  /api/knowledge/documents
GET  /api/knowledge/documents/{document_id}
GET  /api/knowledge/chunks/{chunk_id}
POST /api/knowledge/index
POST /api/knowledge/reindex
POST /api/knowledge/search
POST /api/knowledge/embed
GET  /api/knowledge/ingestion-runs
GET  /api/knowledge/citations/{chunk_id}
GET  /api/knowledge/providers
```

### Files / Sources API

```text
POST /api/uploads
GET  /api/uploads/{relative_path}
GET  /api/files/sources
GET  /api/files/sources/{source_id}
POST /api/files/import
POST /api/files/mounts
GET  /api/files/mounts
DELETE /api/files/mounts/{mount_id}
POST /api/files/sources/{source_id}/mark-stale
POST /api/files/sources/{source_id}/tombstone
POST /api/files/sources/{source_id}/analyze
POST /api/files/sources/{source_id}/index
GET  /api/files/sources/{source_id}/references
```

## 11. CLI 目标

```bash
agentforge goal create --stdin
agentforge goal list
agentforge goal show <goal_id>
agentforge goal plan <goal_id>
agentforge goal run <goal_id> --max-steps 5
agentforge goal pause <goal_id>
agentforge goal resume <goal_id>
agentforge goal cancel <goal_id>

agentforge agents list
agentforge agents show <agent_id>
agentforge team run --goal <goal_id>

agentforge approvals list
agentforge approvals approve <approval_id>
agentforge approvals deny <approval_id>

agentforge audit list --goal <goal_id>
agentforge changes list --goal <goal_id>
agentforge rollback <change_id>

agentforge budget show --goal <goal_id>
agentforge memory consolidate --goal <goal_id>

agentforge context list --run <run_id>
agentforge context show <context_id>
agentforge context sources <context_id>
agentforge context diff <context_id> --against <context_id>
agentforge context compression show <compression_id>

agentforge knowledge index --paths README.md docs skills
agentforge knowledge reindex --changed-only
agentforge knowledge search "multi-agent runtime"
agentforge knowledge show-document <document_id>
agentforge knowledge show-chunk <chunk_id>
agentforge knowledge providers

agentforge files list
agentforge files import <path>
agentforge files mount add <path> --read-only
agentforge files mount list
agentforge files mount remove <mount_id>
agentforge files show <source_id>
agentforge files analyze <source_id>
```

## 12. 与现有模块的关系

成熟平台不是替换现有模块，而是重新分层。

```text
Mature Multi-Agent Platform
  -> runtime/
  -> multi_agent/
  -> autonomy/
  -> governance/
  -> files/
  -> context/

Existing AgentForge Core
  -> skills
  -> memory
  -> knowledge
  -> file sources
  -> HQS
  -> traces
  -> runs
  -> tools
  -> task router
  -> providers

Web Workbench
  -> goals
  -> agents
  -> tasks
  -> knowledge
  -> files/sources
  -> context
  -> approvals
  -> audit
  -> rollback
  -> runs/traces/tools/memory/HQS
```

现有模块改造方向：

- `AgentHarness`：从总控类逐步变成 runtime graph 的一个 facade。
- `WorkflowRunner`：升级或合并进 runtime checkpoint/event 系统。
- `AgentRunLoop`：变成 runtime node executor 或 tool-call node。
- `ToolCallingLoop`：变成 Agent graph 中的 planner/executor 子图。
- `TaskRouter`：继续作为业务任务入口。
- `RunService`：继续作为可观察索引核心，扩展 goal/agent/audit 表。
- `FileSourceResolver`：新增为项目内文件、上传文件和外部挂载来源的统一解析层。
- `MemoryManager`：升级为 Memory 2.0。
- `KnowledgeLayer`：新增为本地知识库、混合检索、embedding 和 citation 管理层。
- `ContextManager`：新增为模型调用前的上下文组装、预算、压缩和引用治理层。
- `Skill` 系统：保留并升级为能力资产系统。

## 13. 分阶段实施计划

### Phase 1: Runtime 收敛

目标：建立成熟 Agent runtime 基础。

交付：

- `runtime/state.py`
- `runtime/graph.py`
- `runtime/executor.py`
- `runtime/events.py`
- typed `AgentState`
- checkpoint/resume 基础
- event stream 基础

验收：

- 现有 `harness_workflow` 可通过 runtime graph 跑通。
- run steps、trace、HQS、memory 行为不退化。
- `AgentRunLoop`、`WorkflowRunner` 的职责边界更清晰。

### Phase 2: Goal Store + Task Graph

目标：长期目标和任务图落地。

交付：

- `Goal`
- `GoalStore`
- `TaskGraph`
- `TaskNode`
- task graph persistence
- goal/task API
- CLI goal 基础命令

验收：

- 能创建 goal。
- 能生成/编辑 task graph。
- 能查询当前 ready tasks。
- goal 状态可暂停、恢复、取消。

### Phase 3: Scheduler + Autonomous Loop

目标：系统能跨 run 推进目标。

交付：

- `Scheduler`
- `AutonomousLoop`
- `StopConditions`
- `RecoveryPolicy`
- run resume

验收：

- 对一个小型目标自动选择下一项任务执行。
- 失败后能 retry/replan/blocked。
- 预算或审批阻塞时可暂停。

### Phase 4: Governance 基础

目标：审批、预算、审计和最小运行治理先落地，作为外部文件、模型调用和工具执行的前置条件。

交付：

- `PolicyEngine`
- `RiskEvaluator`
- `ApprovalManager`
- `BudgetManager`
- `AuditLog`
- `ExecutionProfile`
- `SecretRef`
- secret redaction
- `ModelRouter` MVP
- `ResourceLockManager` MVP

验收：

- write/execute/network/model_spend 可按策略审批。
- 所有关键状态变化写 audit。
- budget 消耗可查询。
- secrets 不进入 trace、memory、context manifest、prompt snapshot、artifact 明文。
- 所有模型调用通过 ModelRouter 记录 provider/model/usage/failure。
- 写文件、写 Skill、写 memory 前可以获取 resource lock 或明确拒绝。

### Phase 5: Change Log + Rollback

目标：写操作可追踪、尽量可撤销。

交付：

- `ChangeRecord`
- `ChangeLog`
- `RollbackManager`
- file patch rollback
- memory tombstone
- Skill version pointer rollback

验收：

- 文件 patch 可记录和回滚。
- Skill 可回退 best version。
- rollback 操作写 trace 和 audit。

### Phase 6: Multi-Agent Registry + Supervisor

目标：真正多 Agent 运行。

交付：

- `AgentSpec`
- `AgentRegistry`
- `SupervisorAgent`
- `AgentMessage`
- `Blackboard`
- basic handoff

验收：

- Supervisor 能选择 Planner/Executor/Reviewer。
- Agent message 可记录和查询。
- Blackboard 可在 run detail 中查看。

### Phase 7: Multi-Agent Planner / Executor / Reviewer

目标：形成完整多 Agent 执行闭环。

交付：

- Planner Agent
- Research Agent
- Executor Agent
- Reviewer Agent
- Critic Agent
- Skill Architect Agent

验收：

- 一个代码分析/修改任务能通过 planner -> executor -> reviewer -> critic 跑通。
- reviewer 可要求返工。
- critic/HQS 可触发 replan。

### Phase 8: Tool Ecosystem 扩展

目标：具备成熟 Agent 的行动能力，并建立统一文件来源治理。

交付：

- File Source Management
- `SourceRef`
- `FileSourceResolver`
- `ExternalMountRegistry`
- structured `uploads` consumption in `/chat`
- file read/write/patch tools
- safe shell/test tools
- git tools
- HTTP/browser tools
- data/doc/code tools
- sandbox/risk/approval integration

验收：

- 高风险工具不会绕过审批。
- tool calls 全部可审计。
- 失败输出可用于 replanner。
- 上传文件、项目内文件和显式授权 external mount 都能解析为统一 `SourceRef`。
- `/chat` 能结构化使用上传文件，而不是只依赖自然语言路径。
- 任意未授权项目外绝对路径默认被拒绝。
- external mount 默认 read-only，并记录 file access events。

### Phase 9: Memory 2.0

目标：长期自治需要更强记忆。

交付：

- goal memory
- agent memory
- memory consolidation
- memory citations
- memory policy

验收：

- 长期目标重启后能恢复关键上下文。
- Memory Curator 能整理运行经验。
- Skill selection 能结合 semantic memory 和 Knowledge Layer 检索结果。

### Phase 10: Knowledge Layer + qwen3-vl-embedding

目标：建立 local-first hybrid knowledge base，为 ContextManager 提供可引用的事实检索来源。

交付：

- `KnowledgeIndexer`
- `KnowledgeChunker`
- `EmbeddingProvider`
- DashScope `qwen3-vl-embedding` provider adapter
- SQLite FTS / BM25 index
- local vector store
- embedding cache
- citation records
- retrieval event records
- retrieval evaluation dataset
- knowledge ingestion CLI/API

验收：

- 能索引 README、AGENTS、docs、skills、handoff 和代码结构摘要。
- 能通过 `qwen3-vl-embedding` 生成并缓存 chunk vectors。
- 能执行 hybrid retrieval：keyword + vector + metadata filter。
- 私有代码发送外部 embedding API 前必须通过配置允许。
- 检索结果进入 context 前带 source citation。
- 能记录 retrieval quality signals，例如 recall@k、citation accuracy、stale retrieval rate。

### Phase 11: Context Engineering + Compression

目标：让系统能解释、压缩和治理每次模型调用实际看到的上下文。

交付：

- `ContextManager`
- `ContextBudgeter`
- `ContextCompressor`
- context manifest
- compression record
- source citation
- handoff context package
- Context Inspector API

验收：

- 每次关键 model call 都能查询 context manifest。
- 长 trace / artifact / conversation 能压缩为带来源引用的摘要。
- Memory / Knowledge 召回进入 context 的原因可解释。
- 多 Agent handoff 能生成可审计 context package。
- Reviewer/Critic 能看到执行证据和来源引用。

### Phase 12: Evaluation 2.0

目标：让系统具备成熟质量控制。

交付：

- Critic Agent
- evaluator registry
- benchmark runner
- regression suite
- user feedback records

验收：

- 任务完成前必须经过 evaluator。
- 代码任务能运行测试/lint/typecheck。
- 低质量输出触发 retry/replan。

### Phase 13: Web Operations Center

目标：Web 成为成熟 Agent 平台工作台。

交付：

- Goals 页面
- Task Graph 页面
- Agents 页面
- Approval Center
- Audit 页面
- Rollback 页面
- Budget 页面
- Files / Sources 页面
- Knowledge Base
- Context Inspector
- Live Run Graph
- Multi-Agent timeline

验收：

- 用户能看到目标、计划、当前 Agent、工具调用、文件来源、外部挂载、知识库索引、上下文构成、memory/knowledge 召回、压缩链路、审批、风险、预算、产物、回滚入口。

### Phase 14: Hardening and Framework Interop

目标：工程成熟化和框架互操作。

交付：

- runtime adapter interface
- LangGraph-style graph compatibility evaluation
- provider adapter hardening
- plugin/tool package format
- stress tests
- migration docs

验收：

- 可以选择继续自研 runtime 或接入成熟 graph runtime。
- 外部 Agent framework 能通过 adapter 使用 AgentForge tools/skills/memory/HQS。

## 14. 测试计划

### Unit Tests

- AgentState schema
- graph node execution
- conditional edges
- checkpoint/resume
- goal lifecycle
- task graph dependencies
- scheduler ready task selection
- policy/risk decision
- approval lifecycle
- budget consumption
- audit append-only
- rollback record
- agent registry
- handoff protocol
- blackboard read/write
- message schema
- source ref schema
- file source resolver
- external mount policy
- memory consolidation
- knowledge chunking
- embedding cache key
- hybrid retrieval scoring
- knowledge citation creation
- retrieval evaluation metrics
- prompt/policy version records
- context budget calculation
- context source citation
- context compression record

### Integration Tests

- goal -> plan -> task graph -> run -> checkpoint -> complete
- goal pause/resume
- failure -> replan -> retry
- high-risk tool -> approval -> execute
- approval denied -> replan/blocked
- file patch -> change record -> rollback
- supervisor -> planner -> executor -> reviewer -> critic
- multi-agent messages persisted
- upload -> source ref -> task router analysis
- external mount -> source ref -> read-only analysis
- unauthorized external absolute path -> rejected
- docs/skills/handoff -> knowledge index -> hybrid search
- qwen3-vl-embedding provider -> local vector cache
- retrieval feedback -> evaluation dataset -> reranking/chunking decision
- run record references prompt/policy/AgentSpec versions
- memory retrieval -> context assembly -> model call manifest
- long artifact -> compression -> cited context summary
- web API reads goal/task/agent/knowledge/audit state

### E2E Tests

- 创建长期目标并自动推进 3 个任务。
- 多 Agent 代码审查并生成报告。
- 多 Agent 修改小文件、运行测试、通过 reviewer。
- 上传外部文件并通过结构化 source ref 完成数据/文档/代码分析。
- 显式挂载外部只读目录后分析其中一个文件。
- 未授权项目外绝对路径被拒绝并写入可解释错误。
- 高风险写操作进入审批中心。
- rollback 恢复文件。
- Web 显示 task graph、Knowledge Base、Context Inspector 和 multi-agent timeline。

### Real Provider Tests

- provider-backed planner 生成 task graph。
- provider-backed supervisor 分配 agent。
- provider-backed reviewer 识别失败。
- provider-backed critic 触发 replan。
- provider-backed `qwen3-vl-embedding` 生成知识库向量。
- provider-backed context compressor 生成带引用摘要。

真实 provider 测试必须默认跳过，通过环境变量显式启用。

## 15. 完成定义

AgentForge 达到成熟完整多 Agent 自主平台时，应满足：

- 支持长期 goal 创建、规划、运行、暂停、恢复、取消和归档。
- 支持 task graph 和依赖调度。
- 支持多 Agent registry、team、handoff、blackboard 和 message persistence。
- 支持 supervisor/planner/executor/reviewer/critic 等核心角色。
- 支持工具生态，且所有工具有 schema、risk、permission、approval 和 audit。
- 支持 File Source Management，包括 project、uploaded、external_mount 三类来源、结构化 `SourceRef`、只读外部挂载、来源引用和访问审计。
- 支持人工审批和预算控制。
- 支持 change log 和 rollback。
- 支持 Memory 2.0，包括 working、episodic、semantic、goal、agent、tool、project memory，以及指向 Knowledge Layer 的 retrieval references。
- 支持 Knowledge Layer，包括 local-first 原文索引、SQLite FTS、`qwen3-vl-embedding` 向量索引、hybrid retrieval 和 citation。
- 支持 Knowledge retrieval evaluation，包括 retrieval event、feedback、recall@k、citation accuracy 和 stale retrieval rate。
- 支持 Context Engineering，包括 context manifest、token budget、compression record、source citation 和 Context Inspector。
- 支持运行治理，包括 execution profiles、SecretRef redaction、ModelRouter、resource locks、model usage 和 governance audit。
- 支持 Skill 资产持续生成、评估、演化、回退和复用。
- 支持 prompt、policy、AgentSpec、rubric 和 model routing config 的版本化与 run-level 引用。
- 支持 evaluator/critic/test-driven verification。
- 支持 checkpoint/resume 和失败恢复。
- 支持 Web Operations Center 观察和控制全部关键状态。
- 所有运行都有 trace、run records、artifacts、tool calls、agent messages、audit events。
- 每次阶段性开发完成、暂停或阻塞时，都更新 `docs/development_handoff.md`，记录当前进度、验证结果、下一步和未解决问题。

达到这个标准后，AgentForge 可以称为：

> 本地优先、可观察、可治理、可回滚、支持长期自主任务推进的成熟 Multi-Agent Autonomous Platform。

## 16. 风险与控制

### 16.1 复杂度失控

控制：

- 先 runtime，再 autonomy，再 multi-agent。
- 每个阶段必须保持测试通过。
- 每个 Agent 都必须有 schema 和权限。

### 16.2 多 Agent 变成无效讨论

控制：

- 不做无边界群聊。
- Supervisor 必须有决策权。
- 每轮协作必须产生 artifact、decision 或 blocked reason。

### 16.3 工具权限风险

控制：

- 默认只读。
- 写入/执行/网络/花费必须走 policy。
- destructive/admin 默认拒绝。

### 16.4 外部文件越权读取

控制：

- 默认拒绝任意项目外绝对路径。
- 外部文件必须来自 upload、import、external mount 或一次性 approval。
- external mount 默认 read-only。
- 系统资产目录仍限制在项目内专用目录。
- 所有外部文件 read/index/embedding 都写 trace 和 audit。
- 私有文件进入 embedding 前必须经过 policy。

### 16.5 Memory 污染

控制：

- 长期 memory 写入需要 schema 和 audit。
- 重要记忆可以由 Memory Curator 汇总。
- 支持 supersede/tombstone。

### 16.6 回滚不可靠

控制：

- 明确 `rollback_available`。
- 先支持 file patch、Skill pointer、memory tombstone。
- 高风险不可逆操作必须审批。

### 16.7 Context 压缩丢失关键信息

控制：

- 压缩结果必须带 source citation。
- 原始 artifact、trace、diff、日志不被删除。
- 高风险证据进入 context 时优先保留原文片段。
- Reviewer/Critic 可以回看原始来源。
- Context Inspector 暴露 token budget、压缩链路和 loss risk。

### 16.8 Knowledge Base 污染或隐私泄露

控制：

- 私有代码和私有文档默认不发送外部 embedding API。
- `allow_external_embedding_for_private_code` 必须显式开启。
- 每个 chunk 保存 source、hash、indexed_at、model 和 dimension。
- 通过 content hash 避免重复索引和陈旧向量。
- 支持 stale、supersede、tombstone。
- Knowledge Base 页面展示 ingestion failure 和 stale documents。

### 16.9 过度依赖某个外部框架

控制：

- AgentForge 保持自己的核心 contract。
- 外部框架只作为 runtime adapter 或可替换执行层。
- Skill/HQS/Trace/Run/Memory 是 AgentForge 的核心资产，不绑定外部框架。

## 17. 优先级建议

目标可以很大，但实施顺序必须稳：

1. Runtime 收敛和 typed state。
2. Goal store 和 task graph。
3. Scheduler 和 autonomous loop。
4. Governance foundation：approval、budget、audit、execution profiles、SecretRef、ModelRouter、resource locks。
5. Change log 和 rollback。
6. Multi-agent registry、supervisor、blackboard。
7. Planner/Executor/Reviewer/Critic Agent。
8. Tool ecosystem 和 File Source Management。
9. Memory 2.0。
10. Knowledge Layer 和 `qwen3-vl-embedding` 混合检索。
11. Context Engineering 和压缩治理。
12. Evaluation 2.0。
13. Web Operations Center。
14. Framework interop 和 hardening。

最小成熟闭环不是只做 Goal Store，而是：

```text
Goal
  -> Task Graph
  -> Supervisor
  -> Planner
  -> Executor
  -> Reviewer/Critic
  -> Approval if needed
  -> SourceRef resolution
  -> Knowledge retrieval
  -> Tool execution
  -> Verification
  -> Audit + Trace + Memory + Context Record
  -> Resume next task
```

这条闭环跑通后，AgentForge 才真正从 Agent Harness 进入 Multi-Agent Autonomous Platform 阶段。

## 18. 开发 Handoff 文档机制

AgentForge 的开发周期会跨越多个阶段、多个模块和多个 Agent 执行上下文。为了避免“开发到哪一步忘了”，项目必须维护一个固定的开发交接文档：

```text
docs/development_handoff.md
```

这个文件不是产品文档，也不是 trace 的替代品，而是给下一次开发启动时使用的人工可读进度锚点。

### 18.1 更新时机

每次出现以下情况，都必须更新 handoff 文档：

- 完成一个功能、阶段、文档更新或重构。
- 完成一次较长的 Agent 开发任务。
- 暂停开发，需要下次继续。
- 遇到阻塞，需要用户或后续 Agent 接手。
- 修改了阶段计划、模块边界、架构决策或下一步优先级。
- 运行了关键验证，例如 tests、lint、typecheck、build、manual check。

### 18.2 必填内容

`docs/development_handoff.md` 至少包含：

- 当前日期和更新人。
- 当前阶段和当前目标。
- 已完成事项。
- 正在进行但未完成的事项。
- 下一步建议。
- 变更过的关键文件。
- 已运行的验证命令和结果。
- 未运行的验证和原因。
- 重要架构决策。
- 已知风险、阻塞和待确认问题。
- 下次启动开发时应该先读哪些文件。

### 18.3 与 Trace / Memory / Context 的关系

开发 handoff 文档只记录面向开发者的进度摘要：

- trace 记录系统运行事实。
- memory 记录长期可检索知识。
- context record 记录模型调用时实际看到的内容。
- handoff 文档记录“下一位开发者或 Agent 应该从哪里继续”。

因此，handoff 文档必须引用 trace、run、artifact、commit、diff 或关键文件路径，但不需要复制所有原始内容。

### 18.4 完成定义

任何阶段性任务不能只以“代码已改完”作为完成。完成时必须确认：

- 相关文件已保存。
- 必要验证已运行或说明未运行原因。
- 文档或目标状态已同步。
- `docs/development_handoff.md` 已更新。

如果 handoff 没有更新，这次开发就不应被视为完整交付。

## 19. 二级设计文档

长期目标文档只定义平台方向。涉及运行安全、文件来源、外部路径、模型调用、凭证、并发锁和产物生命周期的细化设计，放在：

```text
docs/runtime_governance_and_source_design.md
```

该文档是实现以下能力前必须优先阅读的设计入口：

- File Source Management
- Sandbox / execution profiles
- Secrets redaction
- Model Router
- Artifact lifecycle
- Resource locks and leases
- Policy / Approval / Audit 汇合点
- Prompt / Policy / AgentSpec versioning
- Retrieval evaluation
