# AgentForge Agent 平台前端重做目标文档

## 背景

当前 Web 前端更接近内部工作台/控制台：默认进入 `dashboard`，顶部是运行状态和很多功能 tab，右侧常驻诊断面板，聊天只是其中一个操作页。下一阶段需要把它重做成用户可以直接问答、执行任务、查看结果的 Agent 平台体验。

本阶段先只定义开发目标和设计方案，不修改前端代码。

## 目标

1. 首屏从“工作台/控制台”转为“Agent 问答与操作入口”。
2. 默认开启真实模型调用：前端初始请求应使用 `use_provider: true`。
3. 保留 `harness_workflow` 和 `tool_calling` 两种 Agent 模式，并在页面上清楚解释差异。
4. 让用户以自然语言发起任务，同时看到任务进展、使用了哪些能力、生成了什么结果、是否需要复核，以及本次运行记录入口。
5. 将 Runs、Tasks、Tools、Memory、HQS、Trace Viewer 从主视觉中心退到高级抽拉页，但不能丢失能力。
6. 新页面要更像 Agent 产品，而不是普通后台：对话优先、操作卡片辅助、过程可解释、结果可继续追问。

## 参考产品与设计依据

参考方向不是复制界面，而是吸收同类产品的信息架构：

- ChatGPT：以对话为第一入口，并把写作、代码、数据分析、文件理解、Agent 操作放进同一个自然语言入口。
- Claude：强调自然对话、可靠文本处理和可 steer 的助手体验。
- Dify：区分 Workflow 与 Chatflow，说明工作流可以作为更底层的编排能力承载不同应用类型。
- LangGraph Studio：把复杂 Agent 的图、步骤、工具调用和状态暴露出来，便于可视化调试和迭代。

参考来源：

- https://chatgpt.com/overview/
- https://www.anthropic.com/news/introducing-claude
- https://docs.dify.ai/en/learn/key-concepts
- https://www.langchain.com/blog/langgraph-studio-the-first-agent-ide

## 产品定位

新的 AgentForge Web 应定位为：

> 一个本地优先、可观察、可控的 Agent 平台。用户第一眼看到的是“我可以让 Agent 做什么”，而不是“系统内部有哪些模块”。

更具体地说，AgentForge 不是通用闲聊机器人，也不是单纯的后台控制台。它应该是一个“用自然语言驱动本地任务执行的 Agent 操作平台”：

- 用户用一句话提出需求，例如分析代码、诊断一次失败运行、总结文档、检查数据、生成或改进 Skill。
- 系统负责理解意图、选择执行路径、调用模型和工具、生成用户能读懂的结果。
- 平台在后台保留可追踪记录，方便有能力的用户或开发者继续检查、复盘、调试和改进。

这个项目的核心价值：

1. 把临时聊天变成可重复的 Agent 执行流程。
2. 把模型回答变成带证据、产物和改进建议的任务结果。
3. 把 Skill 生成、运行、评估和进化串成一个可持续增强的闭环。
4. 把复杂的工具调用、运行记录、记忆和质量评估藏在可展开的专业视图里，而不是压到普通用户面前。

## Harness Agent 成熟度补充目标

这次前端重做不只是换视觉风格，还要把“AgentForge 已经具备 Harness Agent 原型能力，但产品表达还不成熟”的问题显式解决。

### 需要在前端解决的问题

1. **Harness 能力用户不可感知**

   现在系统内部有 intent、Task Router、Workflow Runner、Tool Registry、Memory、HQS、Trace，但普通用户不应该看到这些内部名词。前端要把它们翻译成：

   - 系统理解了什么任务。
   - 正在使用哪些能力。
   - 做出了什么结果。
   - 哪些内容需要复核。
   - 本次运行记录在哪里。

2. **Skill 还没有被表达成长期能力资产**

   Skill 不能只作为文件路径或调试产物出现。页面应把 Skill 表达成“可复用能力”：

   - 这个 Skill 能做什么。
   - 什么时候会被使用。
   - 当前版本是什么。
   - 最近一次运行效果如何。
   - 是否可以继续优化。
   - 下次类似任务是否会复用它。

   对用户来说，Skill 的价值不是 `skills/foo/v2/SKILL.md`，而是“AgentForge 已经学会了一种可复用的工作方式”。

3. **运行记录要成为证据，不是负担**

   Runs、Trace、Tool Calls、HQS 等内容只应作为“证据层”存在。主页面负责回答和操作，高级抽拉页负责让有能力的用户确认证据、复盘过程、排查问题。

### 不在本前端阶段直接解决，但必须记录的后端成熟度依赖

1. **`AgentRunLoop` 与 `WorkflowRunner` 仍存在双层执行结构**

   当前项目已经有 Workflow Runner 和 RunService，也有 AgentRunLoop。前端可以统一展示运行结果，但不能真正消除后端双层 loop。后续后端硬化阶段应考虑把 AgentRunLoop 包装为 workflow step handler，或者进一步收敛到统一 Workflow Runner 编排模型。

2. **Harness Agent 的成熟度不只由 UI 决定**

   前端可以让 Harness Agent 更像产品，但真正成熟还依赖：

   - 更稳定的 task schema。
   - 更一致的 workflow step contract。
   - 更清晰的 tool permission/policy。
   - 更强的失败恢复和重试策略。
   - 更可解释的 Skill 选择与进化记录。

页面应支持三类用户心智：

1. 普通使用者：直接输入问题或任务，得到答案和产物。
2. 高级使用者：选择执行模式，查看更详细的运行记录和诊断依据。
3. 开发调试者：从抽拉页进入 Runs、Tasks、Tools、Memory、HQS、Trace Viewer 等详细视图排查系统行为。

## 主界面表达原则

主页面面向“完成任务”，不面向“阅读系统内部数据”。默认情况下不要输出 JSON、raw payload、trace 原文、tool call 原始参数、HQS 维度表等普通用户难以理解的内容。

必须做语言转换：

| 内部概念 | 主界面推荐说法 | 展示方式 |
| --- | --- | --- |
| `timeline` / workflow steps | 正在处理、已完成的步骤 | 简短阶段条或进度节点 |
| tool calls | 使用了哪些能力 | “读取文件”“分析代码”“生成报告”等人类可读动作 |
| artifacts | 生成的文件/结果 | 文件卡片、打开入口、摘要 |
| HQS | 回答质量检查 | “质量检查通过/需复核”，必要时显示简短原因 |
| trace | 本次运行记录 | “查看运行记录”按钮，进入抽拉页 |
| raw JSON | 调试数据 | 默认隐藏，只在高级抽拉页的开发者区域显示 |

主界面可以告诉用户“系统正在分析代码并生成建议”，不要直接写“执行 tool_call: code_analysis，HQS=4.2，trace_path=...”。内部字段可以保留在数据层，但展示层必须翻译成用户能理解的任务语言。

## 核心页面方案

### 1. 顶部产品栏

顶部不再只显示 API 链接和健康状态，而是承担产品导航与模式状态：

- 左侧：AgentForge 标识、当前运行状态、当前模型状态。
- 中间：主要入口，例如 `Agent`、`Skills`、`Settings`，以及一个 `Details`/`记录` 抽拉入口。
- 右侧：语言切换、模型调用状态、设置入口。

要求：

- 模型调用默认显示为“已开启”。
- 如果 `config/providers.json` 不可用或模型调用失败，需要显示明确错误和“切换本地模式”的恢复路径。
- 顶部状态不能挤占首屏主体空间。

### 2. 首屏 Agent Composer

首屏主体是一个对话/操作输入区，而不是 dashboard 指标卡。

建议结构：

- 主标题：`Ask AgentForge to inspect, build, diagnose, or evolve`
- 中文文案：`直接描述你的任务，AgentForge 会理解需求、执行相关操作，并给出可继续追问的结果。`
- 大输入框：支持多行任务输入。
- 主要按钮：`运行 Agent`
- 次要按钮：`查看示例`、`使用本地模式`
- 快捷任务 chips：
  - `诊断运行记录`
  - `分析代码`
  - `分析文档`
  - `分析数据`
  - `生成 Skill`
  - `进化 Skill`

要求：

- 输入框是第一视觉焦点。
- 任务 chips 只能辅助，不应像控制台按钮矩阵。
- 运行中按钮要禁用并显示加载状态，避免重复提交。
- 支持 `Ctrl/Cmd + Enter` 发送。

### 3. 模式选择与差异说明

页面必须说明 `Harness Workflow` 与 `tool_call` 模式的区别。建议使用一个紧凑的分段控件加解释卡，不放在隐藏设置里。

默认选择：

- `use_provider: true`
- `agent_mode: "harness_workflow"`

模式说明：

| 模式 | 页面显示名 | 适合场景 | 用户应理解的差异 |
| --- | --- | --- | --- |
| `harness_workflow` | Harness 工作流 | 稳定任务、可复用流程、质量检查、运行记录可回放 | 系统先理解任务，再按固定流程执行，结果更稳定，适合常见结构化任务 |
| `tool_calling` | Tool Call 模式 | 开放任务、探索型任务、需要动态组合能力的任务 | 模型会根据上下文决定下一步使用什么能力，过程更灵活，但更需要查看详细记录 |

建议页面文案：

- Harness 工作流：`更稳、更可复现。适合分析代码、诊断运行记录、分析文档、检查数据、生成或改进 Skill。`
- Tool Call 模式：`更灵活。适合让模型自己决定下一步使用什么能力，但建议在需要时打开详细记录查看过程。`

### 4. 运行过程视图

提交任务后，页面不应等待一个最终 JSON，也不应把内部运行字段直接抛给用户。需要用普通语言展示“Agent 正在做什么”：

- 当前阶段：理解需求、准备资料、执行分析、整理结果、检查质量、保存记录。
- 进度节点：每个节点显示“进行中/已完成/需要处理”，不直接暴露 step id。
- 使用能力：用“读取项目文件”“分析运行记录”“生成 Skill 草稿”等说法替代 tool call 原始名。
- 生成内容：用“生成了 2 个结果文件”“已保存本次运行记录”等说法替代 artifacts/trace 原始字段。
- 质量提示：用“回答质量检查通过”“建议人工复核以下 2 点”等说法替代 HQS 原始表。
- 可恢复入口：重新运行、切换本地模式、查看详细记录。

主体验应保持“对话结果 + 人类可读过程摘要”。详细 JSON、原始 tool 参数、trace 路径只允许放到高级抽拉页的开发者区域。

### 5. 结果区

结果区需要从 JSON dump 变成可消费的 Agent 输出：

- 自然语言回答。
- 结构化任务结果卡：
  - `trace_diagnosis`：关键异常、关联 trace、建议修复。
  - `code_analysis`：按 severity 分组的 findings、文件位置、建议。
  - `document_analysis`：摘要、主题、风险点、引用片段。
  - `data_analysis`：数据摘要、异常值、表格/图表建议。
  - `skill_*`：Skill 路径、版本、HQS、diff、下一步。
- 生成内容列表：报告、文件、Skill 版本、对比结果、运行记录入口。
- 后续追问入口：`基于这次结果继续问`。

### 6. 观察视图

Runs、Tasks、Tools、Memory、HQS、Trace Viewer 等观察/调试内容不应主导首屏，也不应压缩主页面的问答和操作体验。它们应统一收进“高级观察抽拉页”。

建议交互：

- 桌面端：右侧抽拉页，默认收起，只显示一个“查看运行记录/调试详情”入口。
- 移动端：底部 Sheet，默认收起。
- 抽拉页打开后不改变主输入区和结果区的核心布局。
- 普通用户可以完全不打开抽拉页，也能完成任务和理解结果。
- 有能力查看记录的用户，可以在抽拉页中进入详细诊断。
- 内容分 tab：
  - `过程记录`：人类可读 timeline。
  - `使用能力`：tool calls 的友好摘要。
  - `生成内容`：artifacts 的文件和摘要。
  - `质量检查`：HQS 的结论和简短原因。
  - `运行记录`：trace/run 链接。
  - `开发者数据`：Raw JSON，仅高级区域展示。

Runs、Tasks、Tools、Memory、HQS、Trace Viewer 可以保留独立深层页面，但首页只通过抽拉页进入，不能像现在一样把这些模块铺满主页面。

## API 与数据契约目标

### Chat 请求

默认模型调用：

```json
{
  "message": "分析这个 trace 为什么失败",
  "use_provider": true,
  "agent_mode": "harness_workflow"
}
```

Tool Call 模式：

```json
{
  "message": "先查看可用工具，再帮我分析最近一次运行失败原因",
  "use_provider": true,
  "agent_mode": "tool_calling"
}
```

### 前端需要消费的响应字段

前端应优先读取这些字段，而不是依赖完整 debug JSON：

- `response`
- `run_id`
- `agent_mode`
- `intent.task_type`
- `task_result`
- `timeline`
- `tool_call_timeline`
- `artifacts`
- `hqs`
- `system_hqs`
- `trace_url`
- `trace_path`
- `warnings`
- `provider_warnings`
- `stop_reason`

### 错误状态

必须覆盖：

- Provider config 缺失或无效。
- 模型 API 超时。
- tool schema validation 失败。
- permission 拒绝。
- workflow/task handler 失败。
- trace/run 保存失败。

错误展示必须包含：

- 发生在哪个阶段。
- 用户能做什么：重试、切换本地模式、查看运行记录、复制开发者调试数据。

## 视觉与交互设计方向

基于 `ui-ux-pro-max` 的设计系统查询，本项目适合采用 `AI-Native UI` 方向：

- conversational
- agentic
- ambient
- minimal chrome
- streaming/progress feedback
- context cards
- smooth reveals

但需要结合 AgentForge 的企业级、本地优先、可观察定位，不要做成单纯聊天玩具或营销首页。

### 视觉风格

- 浅色主界面，背景使用轻微冷色分层或低对比渐变，不使用纯白背景。
- 局部可以使用深色或克制渐变强化“Agent 正在执行”的科技感。
- 紫色/青色只作为状态和交互强调，不要让页面变成单一紫色主题。
- 主要内容使用宽松但不空洞的布局：输入区突出，结果区清晰，观察区密度稍高。
- 卡片分层：主输入面板、结果面板、状态卡、调试面板应有明显层级差异。

### 组件风格

- 优先复用当前项目已有 React 组件和 CSS 变量。
- 不引入新的 UI 框架，除非后续明确评估收益。
- 图标使用 SVG 图标体系；不要用 emoji 当功能图标。
- 模式切换使用 segmented control。
- 模型调用使用明确 toggle/status badge。
- “过程记录”和“使用能力”使用纵向节点流，但主界面只显示用户能理解的摘要。
- 复杂详情使用 drawer/sheet/details，不要把所有模块铺成控制台。

### 可访问性与响应式

必须满足：

- 正文移动端不小于 16px。
- 交互目标最小 44px 高度。
- 键盘可达，焦点态清晰。
- 文本对比度满足 WCAG AA。
- 不依赖 hover 才能发现关键操作。
- 375px、768px、1024px、1440px 下无横向滚动和文字重叠。
- prefers-reduced-motion 下关闭非必要动效。

### 动效与反馈

- 300ms 以内给出运行反馈。
- 超过 1 秒显示阶段进度或 skeleton。
- 运行过程使用 timeline 逐步更新；如果暂不支持 streaming，也要用阶段状态避免长时间 spinner。
- 动效只用于状态变化、面板展开、运行阶段推进，不做装饰性大动画。

## 信息架构调整

建议新的主信息架构：

```text
Agent
  - Ask / Act
  - Current Result
  - Open Detail Drawer

Skills
  - Skill library
  - Generate / Run / Evolve

Settings
  - Provider config status
  - Default mode
  - Local fallback

Advanced Detail Drawer
  - Runs
  - Tasks
  - Tools
  - Memory
  - HQS
  - Trace Viewer
  - Developer Data
```

`Dashboard` 不再作为默认入口。可以删除、降级为 `Overview`，或合并进 Agent 首页的状态摘要。

Runs、Tasks、Tools、Memory、HQS、Trace Viewer 不应作为首屏并列 tab 铺开；它们应该通过抽拉页或高级入口访问。

## 实施步骤

### Step 1：前端信息架构重组

- 将默认 tab 从 `dashboard` 改为新的 `agent` 或 `chat` 入口。
- 收敛顶部导航，减少首屏控制台感。
- 明确哪些旧 tab 收进高级抽拉页。
- 定义 `TabKey` 或新路由结构。

验收：

- 打开 Web 后第一眼是 Agent 输入区。
- Dashboard 指标卡不再占据首屏主体。

### Step 2：Agent 首屏组件

- 新增或重构 Agent 主页面组件。
- 包含大输入框、快捷任务 chips、运行按钮、模型状态、模式选择。
- 初始 `useProvider` 改为 `true`。
- 保留本地模式切换，但作为 fallback/高级选项。

验收：

- 默认请求 payload 包含 `use_provider: true`。
- 用户无需切 tab 即可完成一次 `/api/chat` 调用。

### Step 3：模式解释与执行契约

- 在页面显式展示 Harness 工作流与 Tool Call 模式的差异。
- 切换模式时同步更新请求的 `agent_mode`。
- 根据模式调整运行阶段文案：
  - Harness：理解需求、匹配任务、按流程执行、检查质量、保存记录。
  - Tool Call：模型决定下一步、检查工具请求、执行能力、整理最终回答。

验收：

- 非开发用户能在页面上理解两种模式适合什么场景。
- `tool_calling` 模式下，主界面能看到“使用了哪些能力”的友好摘要；高级抽拉页能查看原始 tool call 记录。

### Step 4：结果渲染升级

- 用任务类型驱动结果展示。
- 对 `code_analysis`、`trace_diagnosis`、`document_analysis`、`data_analysis`、`skill_*` 提供专门 summary。
- 主界面不显示原始 JSON；原始 JSON 只放在高级抽拉页的开发者数据区。
- 对 Skill 相关结果必须展示为“能力资产”：用途、版本、最近效果、可复用场景、继续优化入口。

验收：

- 常见任务不需要看 JSON 就能理解结果。
- 问题发现、生成内容、质量检查、运行记录都有清晰入口和普通语言说明。
- 用户能理解生成/进化 Skill 的意义，而不只是看到一个文件路径。

### Step 5：统一高级抽拉页

- 抽出可复用 `RunObservationPanel` 或升级现有组件。
- 首页当前运行、Runs Detail 共用同一个抽拉页内容结构。
- 整理 `过程记录 / 使用能力 / 生成内容 / 质量检查 / 运行记录 / 开发者数据`。

验收：

- 当前运行和历史运行的详细记录体验一致。
- Runs Detail 不再和首页详情重复实现。

### Step 6：响应式与视觉硬化

- 桌面：主对话区优先，高级详情从右侧抽拉。
- 平板：高级详情可折叠。
- 手机：主对话区优先，高级详情进入底部 Sheet。
- 修正所有按钮、输入框、状态 badge 的触控尺寸和换行。

验收：

- 375px、768px、1024px、1440px 均无横向滚动。
- 长任务名、长文件路径、长错误消息不会撑破布局。

### Step 7：测试与真实调用验证

- 前端 typecheck/build。
- 用本地服务真实访问页面。
- 至少验证：
  - 默认 Harness + provider 调用。
  - Tool Call + provider 调用。
  - provider 错误展示。
  - code_analysis 结果渲染。
  - trace_diagnosis 结果渲染。
  - 高级抽拉页中的运行记录视图。

验收：

- `npm run typecheck` 通过。
- `npm run build` 通过。
- Playwright 或浏览器手动截图确认核心断点布局正常。

## 非目标

本阶段不做：

- 登录、权限、计费。
- 云端部署平台。
- 复杂可视化 workflow builder。
- 多 Agent 协作市场。
- 替换后端 provider 配置体系。
- 引入新的设计系统框架或组件库。

## 主要风险

| 风险 | 影响 | 控制方式 |
| --- | --- | --- |
| 默认模型调用导致配置错误暴露更多 | 用户首屏失败 | Provider 状态前置展示，提供本地模式 fallback |
| 对话入口隐藏了高级能力 | 调试效率下降 | 观察视图和高级导航保留，但不占主视觉 |
| 两种模式解释不清 | 用户误用 tool_calling | 模式卡写清适用场景和执行差异 |
| 结果类型越来越多 | 前端渲染复杂 | 先按 `intent.task_type` 做轻量 adapter，再逐步拆组件 |
| 移动端高级详情过重 | 首屏拥挤 | 移动端改底部 Sheet，默认收起 |
| Skill 仍被当成文件路径 | 用户感知不到长期价值 | Skill 结果卡必须表达为可复用能力资产 |
| 只改前端但后端双层 loop 未收敛 | 产品体验统一但工程编排仍复杂 | 在文档中明确这是后续后端硬化依赖，不把前端改造误认为完全成熟 |

## 完成定义

这轮前端重做完成时，应满足：

- 用户打开页面后，可以直接输入任务并运行 Agent。
- 模型调用默认开启，且状态可见。
- 页面明确解释 Harness 工作流与 Tool Call 模式。
- 运行过程有用户能理解的阶段状态。
- 常见任务结果不再依赖用户阅读 JSON。
- Skill 生成/进化结果被表达成可复用能力资产。
- Runs、Tasks、Tools、Memory、HQS、Trace Viewer 等高级内容通过抽拉页访问，不影响主页面布局。
- Runs Detail 与首页当前运行使用一致的详细记录结构。
- 文档明确标注 `AgentRunLoop` 与 `WorkflowRunner` 收敛属于后续后端成熟度任务。
- 前端构建、类型检查和核心浏览器验证通过。
