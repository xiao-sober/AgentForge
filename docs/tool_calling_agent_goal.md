# AgentForge Tool-Calling Agent 目标文档

## 1. 当前状态判断

AgentForge 目前已经不是普通 chatbot，也不是单纯的脚本集合。它已经具备一个 Agent Harness MVP 的关键外围能力：

- Web / CLI 入口
- Provider 配置和模型调用适配
- Skill 生成、运行、演化、版本管理
- Working / episodic / semantic 三层 memory
- Response / Skill / System HQS
- 可读 trace 和 run artifacts
- 状态驱动 Planner / Executor
- Web 工作台中的 trace、HQS、Skill diff、memory 可钻取视图

但当前核心执行方式仍是 **Harness-driven workflow**：

```text
receive_input
-> parse_intent
-> retrieve_memory_context
-> select_skill
-> build_plan
-> execute_plan
-> observe_execution
-> update_semantic_memory
-> build_response
-> evaluate_response_hqs
-> hqs_gate
-> reflect
-> reinforcement_check
-> save_episode_memory
```

这条链路由代码固定调度。模型主要参与：

- 生成 Skill
- 执行 Skill
- 改写 Skill

模型目前不会看到完整 tool registry，也不会自主决定下一步调用哪个 tool。因此，当前系统更准确地说是：

> 本地优先、可观测、可演化的 Agent Harness / Agent Workflow Platform MVP。

还不能称为：

> 完整的模型自主 Tool-Calling Agent。

## 2. 下一阶段目标

下一阶段目标是把 AgentForge 从 **Harness-driven workflow** 升级为 **Tool-Calling Agent Harness**。

目标形态：

```text
User Request
  -> Harness receives input
  -> Harness exposes allowed tool schemas
  -> Model proposes structured tool call
  -> Harness validates tool call
  -> Harness executes tool
  -> Harness returns observation
  -> Model decides next tool or final answer
  -> HQS evaluates answer
  -> Trace records every call, observation, error, and decision
```

核心变化：

- 现在：代码决定调用哪些 tools，模型只在部分节点生成文本。
- 目标：模型能在受控 tool registry 内选择 tool，Harness 负责校验、执行、审计和停止。

## 3. 范围边界

本阶段要做：

- 暴露现有 `AgentTool` 为模型可见 tool schema
- 增加模型驱动的 tool-call loop
- 支持模型输出结构化 tool call
- Harness 校验 tool 名称、参数 schema、权限、循环预算
- 记录 tool call / observation / error / retry trace
- 支持最终回答和 HQS gate
- 保留当前 deterministic Harness workflow 作为 fallback / baseline

本阶段不做：

- 多 Agent 协作
- 分布式任务队列
- 云部署
- RBAC / 企业权限系统
- 插件市场
- 任意 shell / filesystem tool 暴露给模型
- 无限自主执行

## 4. 当前 15 个 Harness Tools

当前已注册的内部 tools：

1. `receive_input`
2. `parse_intent`
3. `retrieve_memory_context`
4. `select_skill`
5. `build_plan`
6. `execute_plan`
7. `observe_execution`
8. `update_semantic_memory`
9. `build_response`
10. `evaluate_response_hqs`
11. `hqs_gate`
12. `replan_response`
13. `reflect`
14. `reinforcement_check`
15. `save_episode_memory`

这些 tools 需要被分成两类：

### 4.1 模型可调用 tools

建议第一阶段只暴露低风险、高价值 tools：

- `retrieve_memory_context`
- `select_skill`
- `build_plan`
- `execute_plan`
- `observe_execution`
- `build_response`
- `evaluate_response_hqs`

### 4.2 Harness-only tools

这些 tools 暂时不建议模型直接调用：

- `receive_input`
- `update_semantic_memory`
- `hqs_gate`
- `replan_response`
- `reflect`
- `reinforcement_check`
- `save_episode_memory`

原因：

- memory 写入、reinforcement、HQS gate 影响系统状态，应由 Harness 控制。
- 模型可以建议反思或强化，但不应直接触发高影响写操作。

## 5. Tool Schema 设计

需要把 `AgentTool.to_dict()` 转成模型可读的 tool schema。

建议内部结构：

```json
{
  "name": "execute_plan",
  "description": "Execute the current plan.",
  "permission_level": "execute",
  "idempotent": false,
  "input_schema": {
    "type": "object",
    "properties": {},
    "required": []
  }
}
```

模型输出统一使用 AgentForge 自己的中间格式，不直接绑定某个供应商：

```json
{
  "type": "tool_call",
  "tool_name": "select_skill",
  "arguments": {}
}
```

最终回答格式：

```json
{
  "type": "final_answer",
  "content": "..."
}
```

错误或无法继续：

```json
{
  "type": "cannot_continue",
  "reason": "...",
  "needed_input": ["..."]
}
```

## 6. 模型输出约束

Provider prompt 必须明确：

- 只能返回 JSON object
- 只能选择 `available_tools` 里的 tool
- 不得编造 tool
- 不得输出思维链
- 不得请求直接读写任意文件
- 如果需要用户补充信息，返回 `cannot_continue`
- 如果任务完成，返回 `final_answer`

系统提示词应包含：

```text
你是 AgentForge Tool-Calling Planner。
你不能直接执行工具。
你只能在 available_tools 中选择一个工具调用，或者给出 final_answer。
所有输出必须是 JSON object。
不要输出 Markdown、解释文本或思维链。
```

## 7. Tool-Calling Loop 设计

新增模块建议：

```text
src/agentforge/agent/tool_calling/
  __init__.py
  schema_adapter.py
  model_planner.py
  loop.py
  parser.py
  policy.py
  prompts.py
```

### 7.1 Loop 状态

建议新增 `ToolCallingState`：

```python
@dataclass
class ToolCallingState:
    run_id: str
    user_input: str
    iteration: int
    max_iterations: int
    available_tools: list[dict]
    observations: list[dict]
    final_answer: str | None
    errors: list[dict]
    status: str
```

### 7.2 单轮循环

```text
1. Build model prompt:
   - user input
   - available tools
   - current memory summary
   - previous observations

2. Model returns JSON:
   - tool_call
   - final_answer
   - cannot_continue

3. Parse and validate:
   - JSON shape
   - tool exists
   - schema validation
   - permission policy

4. Execute tool through ToolRegistry

5. Append observation

6. Continue until:
   - final_answer
   - max_iterations
   - blocking error
   - repeated invalid tool call
```

## 8. Policy 和安全边界

必须增加 `ToolCallPolicy`：

```python
@dataclass
class ToolCallPolicy:
    allowed_tools: set[str]
    max_iterations: int
    max_invalid_calls: int
    max_tool_errors: int
    allow_write_tools: bool
    allow_admin_tools: bool
```

默认策略：

- `max_iterations = 8`
- `max_invalid_calls = 2`
- `max_tool_errors = 2`
- `allow_write_tools = false`
- `allow_admin_tools = false`

高影响 tools 默认不暴露：

- `update_semantic_memory`
- `reinforcement_check`
- `save_episode_memory`

## 9. Trace 要求

新增 trace type：

```text
tool_calling_agent
```

每轮必须记录：

```json
{
  "iteration": 1,
  "model_decision": {
    "type": "tool_call",
    "tool_name": "select_skill"
  },
  "validation": {
    "valid": true,
    "errors": []
  },
  "tool_result": {
    "status": "completed",
    "output": {}
  },
  "observation": {}
}
```

trace artifacts：

- selected Skill
- run result
- child skill_execution trace
- response HQS report
- final answer

## 10. Web 工作台要求

Web 需要新增或增强：

- Agent run mode 标识：
  - `harness_workflow`
  - `tool_calling_agent`
- Tool call timeline
- 每次 model decision 可展开查看
- tool arguments 可展开查看
- tool observation 可展开查看
- invalid tool call / schema error 高亮
- final answer 与 HQS 显示在同一 run 详情里

建议新增 API：

```text
POST /agent/tool-chat
GET /agent/runs/:runId
GET /agent/runs/:runId/tool-calls
```

也可以先复用 `/chat`：

```json
{
  "message": "...",
  "use_provider": true,
  "agent_mode": "tool_calling"
}
```

## 11. CLI 要求

新增：

```bash
agentforge agent-chat --stdin --use-provider --agent-mode tool-calling --json
```

或者先扩展现有 chat 能力，如果 CLI 当前没有 chat 命令，可先只做 Web/API。

## 12. Provider 适配要求

不要把 tool calling 绑定到某个 provider 的原生 function calling API。

第一阶段使用 JSON prompt 协议：

- 所有 provider 都走普通 chat completion
- prompt 中给出 tool schema
- 要求模型返回 JSON
- AgentForge 自己解析 JSON

优点：

- 对 DeepSeek、Qwen、OpenAI-compatible provider 都通用
- 易测试
- 易记录 trace
- 不依赖供应商 function calling 字段差异

后续可选：

- 为支持原生 tool calling 的 provider 增加 adapter
- 但内部仍转成 AgentForge 统一 `ToolCallDecision`

## 13. 测试计划

### 13.1 单元测试

- tool schema adapter 输出正确 JSON schema
- model decision parser 解析：
  - valid tool_call
  - valid final_answer
  - invalid JSON
  - unknown tool
  - invalid arguments
- policy 拒绝未授权 tool
- loop 在 max_iterations 停止
- loop 在 repeated invalid calls 停止
- loop 可以完成 select_skill -> execute_plan -> final_answer

### 13.2 集成测试

- Fake model 按脚本返回 tool_call 序列
- Harness 执行真实 ToolRegistry
- trace 包含 model decision、tool result、observation
- HQS 仍能执行
- memory 写入仍由 Harness 控制

### 13.3 真实模型测试

使用 DeepSeek-V4-Pro：

- API 设计评审任务
- Skill 生成任务
- Trace inspection 任务
- Memory 查询任务

验收重点：

- 模型是否只调用 allowed tools
- 是否能在 observation 后继续选择正确工具
- 是否能停止并输出 final answer
- 是否出现虚构 tool
- 是否遵守 JSON 输出

## 14. 分阶段实现计划

### Phase A: Tool Schema 和 Decision Parser

目标：

- 从 `AgentTool` 生成可给模型看的 schema
- 定义统一决策结构
- 解析模型 JSON 输出

交付：

- `schema_adapter.py`
- `parser.py`
- 单元测试

验收：

- 不调用模型也能测试所有 parser 分支

### Phase B: Fake Model Tool-Calling Loop

目标：

- 用 fake model 跑通 tool_call -> observation -> final_answer
- 不接真实 provider

交付：

- `loop.py`
- `policy.py`
- trace 写入
- Fake model tests

验收：

- 可以稳定执行一条 scripted tool-call run
- trace schema valid

### Phase C: Provider-backed Model Planner

目标：

- 接入 DeepSeek / openai_compatible provider
- 模型根据 prompt 输出 JSON decision

交付：

- `model_planner.py`
- `prompts.py`
- provider-backed integration test，可默认跳过真实 API

验收：

- DeepSeek 能完成至少一轮 select_skill -> execute_plan -> final_answer

### Phase D: Web/API 集成

目标：

- Web/API 支持 `agent_mode=tool_calling`
- 可查看 tool call timeline

交付：

- `/chat` 扩展或新增 `/agent/tool-chat`
- Web drilldown panel

验收：

- UI 可查看每轮 tool call、arguments、observation、errors

### Phase E: 质量门禁和强化

目标：

- final answer 后接 HQS
- 低 HQS 时允许一次受控 replan
- reinforcement 仍由 Harness 控制

交付：

- HQS gate 集成
- retry/replan policy

验收：

- 低质量输出不会无限循环
- trace 可解释为什么重试或停止

## 15. 验收标准

完成后，AgentForge 应满足：

- 模型能看到 allowed tool schemas
- 模型能输出结构化 tool calls
- Harness 能校验并执行 tool calls
- 模型能基于 observation 继续下一步
- 所有 tool calls 有 trace
- 不允许未知 tool
- 不允许越权 tool
- 不允许无限循环
- 支持 final answer
- 支持 HQS evaluation
- 当前 deterministic workflow 仍可用

达到这些标准后，AgentForge 可以更有把握地称为：

> 一个本地优先、可观测、带 Skill / Memory / HQS 的 Tool-Calling Agent Harness。

## 16. 关键风险

### 16.1 模型输出不是合法 JSON

缓解：

- 严格 parser
- 最多重试一次 JSON repair prompt
- 仍失败则停止并写 trace

### 16.2 模型虚构 tool

缓解：

- ToolRegistry 校验
- unknown tool 记为 invalid call
- 超过次数停止

### 16.3 模型重复调用同一 tool

缓解：

- observation 去重
- max_iterations
- repeated call detector

### 16.4 模型调用高影响 tool

缓解：

- allowed_tools 白名单
- permission policy
- write/admin tool 默认 Harness-only

### 16.5 Tool-call prompt 过长

缓解：

- 第一阶段只暴露少量 tools
- tool schema 精简
- memory context 摘要化

## 17. 建议优先级

最推荐的第一批实现顺序：

1. `ToolDecision` 数据结构
2. `AgentTool -> model schema` adapter
3. JSON decision parser
4. policy 校验
5. fake model loop
6. trace 写入
7. provider-backed planner
8. Web drilldown

不要一开始就做所有工具开放。先用 3 个工具跑通：

- `select_skill`
- `execute_plan`
- `build_response`

跑通后再加入：

- `retrieve_memory_context`
- `observe_execution`
- `evaluate_response_hqs`

