# Agent 运行模式：本地 / Provider 与 Harness Workflow / Tool-Calling Agent

本文说明 AgentForge 聊天流程中的四种运行组合：

- 运行后端：本地确定性逻辑，或 `config/providers.json` 中配置的大模型 provider。
- Agent 模式：固定的 `harness_workflow`，或模型规划的 `tool_calling_agent`。

关键区别：

- `use_provider` 决定是否允许调用外部大模型 provider。
- `agent_mode` 决定下一步由谁选择：固定 Harness workflow，还是 Tool-Calling Agent planner。

## 快速对比

| 运行后端 | Agent 模式 | 谁选择下一步 | 模型角色 | Trace 类型 | 适合场景 |
| --- | --- | --- | --- | --- | --- |
| 本地 | `harness_workflow` | Harness 固定流程 | 无，使用确定性本地逻辑 | `agent_chat` | 基线测试、离线开发、确定性调试 |
| Provider | `harness_workflow` | Harness 固定流程 | 某些需要文本生成的步骤可调用 provider | `agent_chat` | 稳定编排 + 模型内容生成 |
| 本地 | `tool_calling_agent` | 脚本化本地 planner | 无，脚本 planner 按少量规则发出工具决策 | `tool_calling_agent` | 测试工具调用 policy、trace、memory、UI timeline 和 Harness 控制 |
| Provider | `tool_calling_agent` | Provider planner 提出工具调用 | Provider 返回 JSON 决策，Harness 校验并执行工具 | `tool_calling_agent` | 真实模型驱动的工具规划验收 |

## 两个独立开关

### `use_provider`

`use_provider: false` 表示本地确定性执行，不需要外部模型调用。

`use_provider: true` 表示 AgentForge 会从 `config/providers.json` 创建默认 provider client。密钥必须放在本地配置或环境变量引用中，不能写死在代码里。

### `agent_mode`

`agent_mode: "harness_workflow"` 使用确定性的 Harness 顺序：

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

`agent_mode: "tool_calling"` 或 `tool_calling_agent` 使用工具调用循环：

```text
Harness setup
-> expose allowed tool schemas
-> planner returns one JSON decision
-> Harness validates policy/schema/state
-> Harness executes tool
-> observation is summarized
-> planner chooses next tool or final_answer
-> Harness evaluates HQS
-> optional one controlled response retry
-> Harness saves memory and trace
```

API 入参使用 `tool_calling`；内部和响应里的规范模式名通常是 `tool_calling_agent`。CLI 使用 `--agent-mode tool-calling`。

## 模式详情

### 1. 本地 + `harness_workflow`

这是最确定、最容易复现的模式。

特性：

- 不需要外部 provider。
- Harness 按固定顺序决定所有步骤。
- Skill 生成和 Skill 执行会尽量使用本地确定性回退逻辑。
- Trace 类型是 `agent_chat`。
- HQS、memory、trace 写入和 reinforcement check 仍由 Harness 执行。

适合：

- 建立稳定基线。
- 调试 intent parsing、plan construction、memory、HQS 或 trace 结构。
- 编写不依赖 provider 可用性的测试。

API 示例：

```json
{
  "message": "Review dashboard layout readability.",
  "use_provider": false,
  "agent_mode": "harness_workflow"
}
```

CLI 示例：

```bash
agentforge agent-chat --input "Review dashboard layout readability." --json
```

### 2. Provider + `harness_workflow`

这个模式保留固定 Harness 编排，但在需要模型文本的步骤调用 provider。

特性：

- 步骤顺序仍由 Harness 决定。
- Provider 不选择工具，也不控制流程。
- Provider 可用于 Skill 生成、Skill 执行或 rewrite 等内容生成步骤。
- Trace 类型是 `agent_chat`。
- 相比 provider tool-calling，这个模式更稳定，因为模型只提供内容，不控制下一步。

适合：

- 希望使用模型提升生成或执行质量。
- 仍然希望编排顺序可预测。
- 对比 provider 输出质量，但暂时不测试模型规划工具调用。

API 示例：

```json
{
  "message": "Generate a Skill for API response contract review.",
  "use_provider": true,
  "agent_mode": "harness_workflow"
}
```

CLI 示例：

```bash
agentforge agent-chat --input "Generate a Skill for API response contract review." --use-provider --json
```

### 3. 本地 + `tool_calling_agent`

这个模式用于在不调用真实模型的情况下验证工具调用架构。

特性：

- AgentForge 使用脚本化本地 planner。
- planner 会根据已解析 intent 选择确定性的工具决策序列。
- Harness 的 policy、状态前置条件、工具执行、observation 摘要、final answer 处理和 trace timeline 都会被覆盖。
- Trace 类型是 `tool_calling_agent`。
- `build_response` 运行后，`final_answer_source` 通常是 `harness_response`。

重要边界：

- 本地脚本 planner 不是通用意图感知模型。
- 它只覆盖内置规则：普通 Skill 执行、trace inspection、memory query、Skill 生成和 direct response。
- 因此，本地 `tool_calling_agent` 适合做 loop、policy、trace、memory 和 UI 冒烟测试；更开放的自然语言规划能力仍需要 provider 模式验收。

适合：

- 开发 tool-call loop。
- 测试 Web tool-call timeline 展示。
- 覆盖 policy failure、repeated calls、premature final answer、HQS gate、trace shape 等确定性场景。

API 示例：

```json
{
  "message": "Inspect the latest trace.",
  "use_provider": false,
  "agent_mode": "tool_calling"
}
```

CLI 示例：

```bash
agentforge agent-chat --input "Inspect the latest trace." --agent-mode tool-calling --json
```

### 4. Provider + `tool_calling_agent`

这是当前真正的 Tool-Calling Agent 模式。

特性：

- Provider 接收允许调用的工具 schema 和压缩后的 observation。
- Provider 必须返回一个 JSON 决策：
  - `tool_call`
  - `final_answer`
  - `cannot_continue`
- 如果 provider 输出不是合法 JSON，AgentForge 最多做一次受控 JSON repair retry。
- Harness 会校验工具名、参数 schema、权限级别、状态前置条件、重复调用、invalid-call 预算和 tool-error 预算。
- Harness 执行工具，并拥有所有高影响系统动作。
- Trace 类型是 `tool_calling_agent`。
- 最终用户响应优先使用 Harness `build_response` 的输出；当 `state["response"]` 已存在时，模型的 `final_answer` 只作为完成信号。

适合：

- 验证模型是否能选择下一步 Agent 工具。
- 验证 DeepSeek / DashScope 等 provider 的 JSON 稳定性。
- 检查 tool-call timeline、arguments、validation errors 和 observations。
- 验收 trace inspection、memory query、Skill 生成类请求的真实规划行为。

API 示例：

```json
{
  "message": "What useful memory do you have about recent tool-calling provider dry runs?",
  "use_provider": true,
  "agent_mode": "tool_calling"
}
```

CLI 示例：

```bash
agentforge agent-chat \
  --input "What useful memory do you have about recent tool-calling provider dry runs?" \
  --use-provider \
  --agent-mode tool-calling \
  --json
```

需要查看完整内部状态时使用 `--debug`：

```bash
agentforge agent-chat \
  --input "Inspect the latest trace." \
  --use-provider \
  --agent-mode tool-calling \
  --json \
  --debug
```

## 模型可调用工具与 Harness-only 工具

在 `tool_calling_agent` 中，模型只能看到有限工具集。

模型可调用工具：

- `retrieve_memory_context`
- `inspect_latest_trace`
- `select_skill`
- `build_plan`
- `execute_plan`
- `observe_execution`
- `build_response`
- `evaluate_response_hqs`

Harness-only 工具：

- `receive_input`
- `update_semantic_memory`
- `hqs_gate`
- `replan_response`
- `reflect`
- `reinforcement_check`
- `save_episode_memory`

原因：

- memory 写入、HQS gate、retry、reflection、reinforcement 和 episode persistence 会影响系统状态，必须由 Harness 控制。

## 响应和 Trace 差异

### `harness_workflow`

精简 `/chat` payload 包含：

- `run_id`
- `response`
- `trace_path`
- `trace_url`
- `hqs`
- `system_hqs`
- `intent`
- `plan`
- `execution_state`
- `plan_step_results`
- `memory_retrieval`
- `selected_skill`
- `artifacts`
- `timeline`
- `reflection`
- `reinforcement`
- `stop_reason`

### `tool_calling_agent`

精简 `/chat` payload 会额外包含：

- `agent_mode`
- `tool_call_timeline`
- `parse_repair_count`
- `invalid_call_count`
- `final_answer_source`
- `hqs_gate`
- `quality_retry`
- `tool_calling`

`final_answer_source` 的含义：

- `harness_response`：`build_response` 已经生成用户响应。这是正常成功路径。
- `model_final_answer`：没有 Harness response，只能使用模型 final answer 或回退停止消息。

## 安全控制和停止条件

`tool_calling_agent` 额外包含这些保护：

- 最大迭代次数。
- invalid decision 预算。
- tool error 预算。
- 连续相同 `tool_name + arguments` 的重复调用检测。
- memory retrieval 等同类工具的重复调用保护。
- `build_response` 前过早 `final_answer` 保护。
- final answer 后的 HQS gate。
- 低 HQS 时最多一次受控 response retry。
- provider JSON repair retry 最多一次。

`harness_workflow` 天然更保守，因为模型不选择工具，也不控制流程。

## 使用建议

调试时建议按这个顺序推进：

1. 本地 + `harness_workflow`：验证基线行为。
2. Provider + `harness_workflow`：验证模型生成内容质量。
3. 本地 + `tool_calling_agent`：验证工具调用 policy 和 UI timeline。
4. Provider + `tool_calling_agent`：验收真实模型的自主工具规划。

日常开发应先保持本地确定性模式稳定。接入 provider 的 `tool_calling_agent` 更适合作为验收测试，不应该成为唯一调试路径。
