# AgentForge Autonomous Agent Platform 长期目标文档

## 1. 文档目的

本文档定义 AgentForge 在完成 Tool-Calling Agent Harness 之后，进一步演进为 Autonomous Agent Platform 的长期目标。

当前不进行开发。本文件用于后续规划、拆阶段、评估风险和明确边界。

与 `tool_calling_agent_goal.md` 的区别：

- `tool_calling_agent_goal.md` 解决：模型如何在受控范围内选择并调用工具。
- 本文档解决：系统如何围绕长期目标自主推进任务，并具备审批、回滚、审计和安全边界。

## 2. 当前阶段定位

AgentForge 当前定位：

```text
Agent Harness MVP
  -> Tool-Calling Agent Harness
  -> Autonomous Agent Platform
```

其中：

- **Agent Harness MVP**：代码驱动流程，模型参与 Skill 生成、执行、改写。
- **Tool-Calling Agent Harness**：模型能看到 tool schema，自主选择 tool，Harness 校验并执行。
- **Autonomous Agent Platform**：系统可以围绕长期目标进行跨轮次、跨会话、可审计、可审批、可回滚的自主任务推进。

本文档描述第三阶段。

## 3. Autonomous Agent Platform 的定义

在 AgentForge 语境中，Autonomous Agent Platform 不是“无限自主执行”，而是：

> 在明确目标、权限、预算、审批策略和回滚机制下，Agent 可以持续规划、执行、观察、学习和推进任务，并且所有行为可追踪、可解释、可中止、可回滚。

关键特征：

- 长期目标管理
- 自主任务拆解和排期
- 多轮自主推进
- 状态持久化
- 权限审批
- 高风险操作前人工确认
- 执行审计
- 变更回滚
- 预算和停止条件
- 失败恢复和复盘

## 4. 不追求的方向

即使进入 Autonomous Agent Platform 阶段，也不应追求无边界自主：

- 不允许无限循环执行
- 不允许默认获得 shell / filesystem / network 高权限
- 不允许绕过审批修改重要文件
- 不允许隐式提交代码、删除数据、调用付费 API
- 不允许隐藏执行历史
- 不允许模型自行扩大权限范围

Autonomy 必须受 Harness 约束。

## 5. 核心能力目标

### 5.1 长期目标管理

系统需要支持用户创建、查看、暂停、恢复、取消长期目标。

目标示例：

```text
在接下来的多轮任务中，把 AgentForge 从 Harness MVP 演进为 Tool-Calling Agent Harness，并持续完善测试和文档。
```

目标需要持久化：

```json
{
  "goal_id": "goal_...",
  "title": "Implement Tool-Calling Agent Harness",
  "objective": "...",
  "status": "active",
  "created_at": "...",
  "updated_at": "...",
  "owner": "local_user",
  "constraints": [],
  "success_criteria": [],
  "budgets": {},
  "current_plan_id": "plan_..."
}
```

状态建议：

```text
draft
active
paused
blocked
completed
cancelled
failed
archived
```

### 5.2 自主任务推进

长期目标需要被拆解为任务树：

```text
Goal
  -> Milestone
  -> Task
  -> Step
  -> Tool call
```

Agent 可以在每次运行时：

- 读取当前 goal 状态
- 检查最近执行记录
- 选择下一项可执行任务
- 调用工具执行
- 记录结果
- 更新 plan
- 判断是否需要用户审批或输入

### 5.3 权限审批

所有工具和操作需要按风险等级分类。

建议权限等级：

```text
read
write
execute
network
model_spend
git_stage
git_commit
git_push
destructive
admin
```

审批策略：

```json
{
  "policy_id": "policy_default",
  "auto_approve": ["read"],
  "require_confirmation": ["write", "execute", "model_spend"],
  "deny_by_default": ["destructive", "admin"],
  "per_goal_overrides": {}
}
```

原则：

- 默认最小权限
- 高风险操作必须人工确认
- 审批记录必须写入 audit log
- 审批不能由模型伪造

### 5.4 回滚机制

任何持久化变更都应尽量有回滚方案。

变更类型：

- 文件修改
- Skill 新版本
- memory 写入
- trace / run artifact
- config 修改
- git 操作

回滚策略：

- 文件修改：记录 patch / inverse patch
- Skill 版本：不覆盖旧版本，通过版本指针回退
- memory 写入：append-only + tombstone / superseded 标记
- config 修改：保存 before/after snapshot
- git 操作：依赖 commit / branch / revert

回滚记录：

```json
{
  "change_id": "change_...",
  "goal_id": "goal_...",
  "run_id": "run_...",
  "type": "file_patch",
  "target": "src/...",
  "before_hash": "...",
  "after_hash": "...",
  "rollback_available": true,
  "rollback_artifact": "..."
}
```

### 5.5 审计日志

Autonomous 阶段必须具备强审计。

审计事件：

- goal created / updated / paused / completed
- plan created / revised
- task started / completed / failed
- tool call requested
- tool call approved / denied
- tool call executed
- file changed
- memory updated
- model called
- budget consumed
- rollback executed

审计事件格式：

```json
{
  "audit_id": "audit_...",
  "created_at": "...",
  "goal_id": "goal_...",
  "run_id": "run_...",
  "actor": "model|harness|user",
  "event_type": "tool_call_executed",
  "risk_level": "medium",
  "summary": "...",
  "details": {},
  "approval_id": null,
  "trace_id": "trace_..."
}
```

审计日志要求：

- append-only
- readable local format
- 可按 goal / run / tool / risk 查询
- 不包含明文密钥
- 能关联 trace

### 5.6 预算管理

长期自主任务需要预算约束。

预算类型：

- 最大迭代次数
- 最大 wall-clock 时间
- 最大模型调用次数
- 最大 token 预算
- 最大 API 花费
- 最大文件变更数
- 最大失败次数

示例：

```json
{
  "goal_id": "goal_...",
  "budgets": {
    "max_iterations": 20,
    "max_model_calls": 50,
    "max_tokens": 500000,
    "max_write_operations": 30,
    "max_consecutive_failures": 3
  }
}
```

### 5.7 人工介入点

Agent 必须知道何时停下来请求用户确认。

需要确认的情况：

- 高风险写操作
- 删除文件
- 修改 config
- 调用真实付费模型进行大批量任务
- 生成或演化大量 Skill
- 执行不可逆操作
- 连续失败
- 目标范围不清楚
- 预算不足
- HQS 长期低于阈值

### 5.8 失败恢复

失败不能只记录 error。系统应能判断下一步：

- retry
- replan
- ask_user
- rollback
- mark_blocked
- mark_failed

失败恢复记录：

```json
{
  "failure_id": "failure_...",
  "error_type": "...",
  "recoverable": true,
  "attempted_recovery": "replan",
  "result": "blocked",
  "next_required_input": "..."
}
```

## 6. 推荐架构

建议新增模块：

```text
src/agentforge/autonomy/
  __init__.py
  goals.py
  goal_store.py
  task_graph.py
  scheduler.py
  approval.py
  policy.py
  audit_log.py
  rollback.py
  budget.py
  autonomous_loop.py
  recovery.py
  schemas.py
```

### 6.1 Goal Store

职责：

- 创建 goal
- 更新状态
- 读取 active goals
- 记录 current plan
- 保存 success criteria

存储建议：

```text
data/autonomy/goals.jsonl
data/autonomy/goal_state.json
```

### 6.2 Task Graph

职责：

- 维护 goal -> milestones -> tasks -> steps
- 支持依赖关系
- 支持任务状态流转
- 支持下一步选择

任务状态：

```text
pending
ready
running
blocked
completed
failed
skipped
cancelled
```

### 6.3 Scheduler

职责：

- 找到 active goal
- 选择 next ready task
- 检查预算
- 检查审批
- 调用 Tool-Calling Agent Harness 执行

### 6.4 Approval Manager

职责：

- 根据 policy 判断是否需要用户确认
- 生成 approval request
- 接收用户 approve / deny
- 写 audit log

审批状态：

```text
pending
approved
denied
expired
cancelled
```

### 6.5 Audit Log

职责：

- append-only 写事件
- 提供查询
- 关联 goal、run、trace、approval、change

### 6.6 Rollback Manager

职责：

- 记录变更
- 判断是否可回滚
- 执行 rollback
- 写 rollback trace

### 6.7 Autonomous Loop

长期循环：

```text
load active goal
-> load task graph
-> select next ready task
-> check budget
-> prepare tool-calling run
-> request approval if needed
-> execute
-> evaluate HQS
-> update task state
-> write audit log
-> maybe replan
-> stop or continue
```

## 7. 数据目录建议

```text
data/autonomy/
  goals.jsonl
  goal_state.json
  task_graphs/
    <goal_id>.json
  approvals.jsonl
  audit.jsonl
  changes.jsonl
  budgets.json
  rollback/
    <change_id>.patch
```

## 8. Web 工作台目标

Autonomous 阶段 Web 应增加：

- Goals 列表
- Goal 详情
- Task graph / timeline
- 当前运行状态
- Pending approvals
- Audit log 查询
- Budget 使用情况
- Rollback 面板
- Risk badge
- Blocked reason
- Resume / pause / cancel 操作

建议路由：

```text
/goals
/goals/:goalId
/goals/:goalId/tasks
/goals/:goalId/audit
/approvals
/changes
/rollback
```

API：

```text
POST /goals
GET /goals
GET /goals/:goalId
POST /goals/:goalId/pause
POST /goals/:goalId/resume
POST /goals/:goalId/cancel
GET /approvals
POST /approvals/:approvalId/approve
POST /approvals/:approvalId/deny
GET /audit?goal_id=...
POST /rollback/:changeId
```

## 9. CLI 目标

建议命令：

```bash
agentforge goal create --stdin
agentforge goal list
agentforge goal show <goal_id>
agentforge goal run <goal_id> --max-steps 3
agentforge goal pause <goal_id>
agentforge goal resume <goal_id>
agentforge approval list
agentforge approval approve <approval_id>
agentforge approval deny <approval_id>
agentforge audit list --goal <goal_id>
agentforge rollback <change_id>
```

## 10. 与 Tool-Calling Agent Harness 的关系

Autonomous Platform 不替代 Tool-Calling Agent Harness，而是使用它。

分层关系：

```text
Autonomy Layer
  - goals
  - scheduler
  - approvals
  - audit
  - rollback
  - budgets

Tool-Calling Agent Harness
  - model selects tools
  - harness validates
  - tools execute
  - observations loop

Core AgentForge
  - skills
  - memory
  - HQS
  - traces
  - providers
```

## 11. 实现阶段

### Phase 1: Goal Store 和 Audit Log

目标：

- 支持创建 goal
- 支持读取 active goal
- 支持 append-only audit log

交付：

- `Goal`
- `GoalStore`
- `AuditEvent`
- `AuditLog`
- CLI 基础命令

验收：

- goal 可创建、查询、状态更新
- 所有状态变化写 audit

### Phase 2: Task Graph 和 Scheduler

目标：

- goal 可拆成 task graph
- scheduler 能选择 next ready task

交付：

- `TaskNode`
- `TaskGraph`
- `Scheduler`

验收：

- 支持任务依赖
- 支持 pending -> ready -> running -> completed
- 支持 blocked 状态

### Phase 3: Approval Policy

目标：

- 高风险操作需要审批
- 用户可 approve / deny

交付：

- `ApprovalRequest`
- `ApprovalManager`
- `PermissionPolicy`

验收：

- write/admin/destructive 操作默认不能自动执行
- 审批结果写 audit

### Phase 4: Budget 和 Stop Conditions

目标：

- 长期任务不会无限执行
- 模型调用和写操作可限制

交付：

- `BudgetManager`
- budget report
- stop reason

验收：

- 达到预算自动停止
- trace 和 audit 能解释停止原因

### Phase 5: Rollback Manager

目标：

- 关键变更可回滚

交付：

- `ChangeRecord`
- `RollbackManager`
- rollback trace

验收：

- 文件 patch 可回滚
- Skill version 可回退指针
- memory 写入可 supersede

### Phase 6: Autonomous Loop

目标：

- goal 可跨 run 自主推进

交付：

- `AutonomousLoop`
- recovery policy
- goal run trace

验收：

- 可以执行一个小型长期目标
- 中途需要审批时暂停
- 用户批准后继续
- 失败时能进入 blocked / replan

### Phase 7: Web 工作台

目标：

- 可观察长期目标和审批状态

交付：

- Goals 页面
- Approval 页面
- Audit 页面
- Rollback 页面

验收：

- 用户能看到 Agent 为什么做、做了什么、等什么、如何撤销

## 12. 测试计划

### 单元测试

- goal 状态流转
- task graph 依赖计算
- policy 判断
- approval approve / deny
- audit append-only
- budget 消耗
- rollback record 生成

### 集成测试

- 创建 goal -> 生成 task graph -> scheduler 选择任务
- tool-calling run 完成后更新 task 状态
- 高风险操作生成 approval
- approval 后继续执行
- budget 达到后停止
- rollback 可执行

### 真实模型测试

在 Tool-Calling Agent Harness 完成后进行：

- 长期目标：改进一个 Skill
- 长期目标：审查 README 并提出更新
- 长期目标：运行测试并总结失败
- 长期目标：根据 HQS 结果提出 Skill 演化计划

要求：

- 所有模型决策可 trace
- 所有状态变更可 audit
- 所有写操作可追踪
- 高风险操作有审批

## 13. 验收标准

完成后，系统应满足：

- 可以创建长期目标
- 可以持久化目标状态
- 可以拆解任务图
- 可以自主选择下一步任务
- 可以调用 Tool-Calling Agent Harness 执行
- 可以在预算内多轮推进
- 可以识别 blocked 状态
- 可以请求人工审批
- 可以记录审计日志
- 可以记录变更
- 可以执行回滚
- 可以在 Web 中查看目标、审批、审计、回滚

达到这些标准后，AgentForge 可以称为：

> 本地优先、可观测、可审批、可回滚的 Autonomous Agent Platform 原型。

## 14. 风险清单

### 14.1 自主范围过大

缓解：

- goal 必须明确
- policy 默认保守
- max steps / budget
- 高风险操作审批

### 14.2 审批体验复杂

缓解：

- 审批请求必须简短
- 明确风险和影响
- 提供 approve / deny / modify

### 14.3 回滚不可靠

缓解：

- 先只支持文件 patch 和 Skill 版本回退
- 不承诺所有操作都可回滚
- rollback_available 明确标记

### 14.4 Audit log 过大

缓解：

- JSONL append-only
- 支持按 goal 分页查询
- 后续支持压缩和归档

### 14.5 模型误判任务状态

缓解：

- Harness 负责最终状态写入
- 模型只能建议，不直接改 goal 状态
- 状态变更需要 schema 校验

## 15. 优先级建议

不要一开始就做完整 Autonomous Platform。

推荐顺序：

1. Goal Store
2. Audit Log
3. Task Graph
4. Scheduler
5. Approval Policy
6. Budget Manager
7. Autonomous Loop
8. Rollback Manager
9. Web 工作台

最小可用版本只需要：

- 一个 active goal
- 一个 task graph
- 一个 scheduler
- 一个 audit log
- 一个手动 approval 流程

