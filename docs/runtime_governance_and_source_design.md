# AgentForge Runtime Governance and Source Design

## 1. 文档目的

本文档是 `docs/multi_agent_autonomous_platform_goal.md` 的二级设计文档，聚焦成熟多 Agent 系统最容易失控的基础层：

- Sandbox / 执行隔离
- Secrets / 凭证治理
- Model Router / 模型治理
- File Source Management / 文件来源治理
- Artifact Lifecycle / 产物生命周期
- Locks / 并发锁与资源租约
- Policy / Approval / Audit 的统一落点

目标不是马上实现全部能力，而是先明确 AgentForge 在长期自治、多 Agent 协作、外部文件处理、外部模型调用和工具执行时的安全边界。

## 2. 当前基线

当前代码里已经有一些良好的安全边界：

- Web 上传文件会复制到 `data/uploads/`，再作为项目内文件处理。
- `code_analysis`、`document_analysis`、`data_analysis` 都要求路径留在 `project_root` 下。
- `skill_path`、`taskset_path`、`trace_path` 等系统资产都有目录约束。
- `ToolRegistry` 已有 tool schema、permission level、timeout 和基础错误模型。
- `RunService`、trace、artifact、HQS、memory 已经能记录运行结果。

当前不足：

- `/chat` 虽然接收 `uploads` 字段，但后端主要依赖前端把上传路径拼进自然语言 message。
- 文件来源没有统一 `SourceRef`，Task Router、Knowledge、Context、Artifact 各自理解路径。
- 没有显式 external mount 概念，项目外绝对路径默认被拒绝但缺少可治理扩展路径。
- Sandbox、secrets、model router、resource locks、artifact retention 还没有完整设计。
- 多 Agent 并发后，文件、Skill、memory、预算、provider 调用容易出现冲突。

## 3. 总体原则

1. 默认安全，显式授权。
2. 系统资产和用户资料分开治理。
3. 项目外文件不能通过简单放开绝对路径实现。
4. 工具执行必须可审计、可取消、可解释。
5. secrets 永不进入 trace、prompt snapshot、artifact 明文。
6. 模型调用必须走 provider/model router，不允许散落调用。
7. 长期运行必须有 cleanup、retention 和 lock 机制。
8. 所有进入 context 的外部事实必须有 citation。

## 4. 信任边界

AgentForge 应至少区分以下信任域：

| 信任域 | 示例 | 默认策略 |
| --- | --- | --- |
| project | `src/`、`docs/`、`skills/` | 允许读，写入按工具策略 |
| system_assets | `traces/`、`runs/`、`config/`、`tasksets/` | 专用 resolver，禁止任意 external mount 替代 |
| uploaded | `data/uploads/...` | 允许读，按来源记录处理 |
| imported | `data/files/imported/...` | 允许读，保留 original source metadata |
| external_mount | `D:/datasets/...` | 默认 read-only，需要显式授权 |
| provider | LLM、embedding、reranker API | 受 model policy、budget、secrets 控制 |
| network | HTTP、browser、package docs | 默认受 network policy 控制 |
| execution | shell、test、script、browser automation | 必须选择 execution profile |

## 5. Execution Profiles

所有工具执行应绑定一个 execution profile。

| profile | 能力 | 默认风险 | 典型工具 |
| --- | --- | --- | --- |
| `read_only_inspect` | 读项目文件、读 trace、读 run、读 memory | low | grep、file read、trace inspect |
| `uploaded_read` | 读上传或导入文件 | low-medium | data/document/code analysis |
| `external_read_only` | 读 external mount 文件 | medium | external dataset analysis |
| `project_write` | 写项目内文件 | medium | patch、Skill write、report write |
| `test_execution` | 运行测试、lint、typecheck、build | medium | pytest、npm test、typecheck |
| `network_read` | 网络读取 | medium | docs lookup、HTTP GET |
| `browser_automation` | 浏览器访问和截图 | medium-high | Playwright/browser |
| `provider_model_call` | 调用模型供应商 | medium | chat、embedding、rerank |
| `destructive_admin` | 删除、移动、发布、push | high | recursive delete、git push、release |

Profile 规则：

- 每个 tool 必须声明默认 profile。
- policy 可以提升或拒绝 profile。
- high risk profile 必须 approval。
- shell 不能直接继承项目全权限；必须由 safe shell wrapper 执行。
- Windows 上执行文件操作要使用 `-LiteralPath` 或原生 API，避免字符串拼接造成误删。

## 6. SandboxManager

推荐模块：

```text
src/agentforge/governance/
  sandbox.py
  execution_profile.py
  process_runner.py
  network_policy.py
  shell_policy.py
```

SandboxManager 职责：

- 为每个 tool call 选择 execution profile。
- 限制 cwd、env、timeout、stdout/stderr size。
- 禁止未经批准的 destructive command。
- 记录 process exit code、duration、truncated output。
- 对外部目录执行只读检查。
- 为失败恢复提供可结构化解析的错误。

ToolExecutionRequest 示例：

```json
{
  "tool_call_id": "tool_...",
  "tool_name": "run_tests",
  "profile": "test_execution",
  "cwd": "G:/AgentForge",
  "timeout_seconds": 120,
  "network": false,
  "write_scope": ["project"],
  "env_refs": ["secret:provider.openai.api_key"],
  "risk_level": "medium"
}
```

## 7. Secrets 治理

Secrets 不是普通配置。成熟 AgentForge 应通过 SecretRef 管理敏感值。

推荐模块：

```text
src/agentforge/governance/
  secrets.py
  redaction.py
```

SecretRef 示例：

```json
{
  "secret_ref": "secret:dashscope.api_key",
  "provider": "env",
  "env": "DASHSCOPE_API_KEY",
  "scope": "provider",
  "allowed_tools": ["model_chat", "embedding"],
  "redaction_label": "[SECRET:dashscope.api_key]"
}
```

规则：

- provider config 只能保存 env 引用或 secret ref，不保存明文 key。
- secret 明文不能进入 trace、memory、context manifest、prompt snapshot、artifact。
- tool stdout/stderr、model error、HTTP error 必须做 redaction。
- 每次 secret 被解析或注入都写 audit event。
- Agent 不能直接读取 secret value，只能请求具备能力的 tool 使用 secret ref。
- 用户粘贴疑似 secret 时，应触发 warning，并建议迁移到 env/config。

Prompt snapshot 策略：

- 默认不保存完整 prompt snapshot。
- 默认只保存 prompt manifest：section 名称、token 估算、source refs、policy refs、hash。
- 启用完整 snapshot 必须显式配置，并通过 policy。
- 完整 snapshot 必须先 redaction，且不能包含 secret 明文、未授权私有文件全文、未脱敏 provider error。
- snapshot retention 必须短于 trace/run retention，除非被用户 pin 或纳入 regression case。

## 8. Model Router

所有模型调用应走 ModelRouter，避免散落调用。

推荐模块：

```text
src/agentforge/models/
  router.py
  request.py
  capability.py
  budget.py
  fallback.py
  rate_limit.py
  usage.py
```

ModelCapability：

- `chat`
- `tool_calling`
- `json_schema`
- `long_context`
- `vision`
- `embedding`
- `multimodal_embedding`
- `rerank`

ModelRequest 示例：

```json
{
  "model_call_id": "model_...",
  "purpose": "planner",
  "agent_id": "planner_agent",
  "capabilities": ["chat", "json_schema"],
  "privacy_level": "project",
  "token_budget": 12000,
  "cost_budget": 0.05,
  "preferred_provider": "dashscope",
  "fallback_policy": "same_capability_lower_cost"
}
```

模型治理要求：

- planner、executor、reviewer、critic、embedding 可以使用不同模型。
- `qwen3-vl-embedding` 作为 Knowledge Layer 默认 embedding 模型，但必须通过 provider adapter。
- chat model 和 embedding model 的隐私策略分开配置。
- 私有代码进入外部模型前必须通过 policy。
- 记录 usage：tokens、latency、cost estimate、provider、model、failure。
- fallback 必须保留 capability 等价性，不能把 JSON schema 任务 fallback 到不支持结构化输出的模型。

多模态模型调用要求：

- 图片、截图、PDF 页面、视频抽帧必须先作为 `SourceRef` 注册。
- 多模态 embedding 请求必须记录 source id、派生 asset id、尺寸、MIME、hash、模型和维度。
- 视频不能直接全量送入外部 provider；应按 policy 抽帧并限制数量。
- OCR、caption、视觉摘要属于派生 artifact，必须引用原始 source。
- 私有多模态资料默认禁止外部 embedding，除非 policy 显式允许。

## 9. File Source Management

文件来源治理是外部文件处理的核心。不要在 handler 中直接放开绝对路径。

推荐模块：

```text
src/agentforge/files/
  source_ref.py
  resolver.py
  access_policy.py
  ingestion.py
  mounts.py
  scanners.py
  citations.py
  audit.py
```

SourceRef 类型：

| source_type | 说明 | 默认能力 |
| --- | --- | --- |
| `project` | 项目内文件 | read，可按工具策略写 |
| `uploaded` | Web 上传并存入 `data/uploads` 的文件 | read |
| `imported` | 从外部复制进 `data/files/imported` 的文件 | read |
| `external_mount` | 用户显式授权的外部目录或文件 | read-only |
| `inline` | 用户输入或代码块 | read |
| `artifact` | run 产物、trace、报告 | read |

SourceRef 示例：

```json
{
  "source_id": "src_...",
  "source_type": "uploaded",
  "display_name": "sample.csv",
  "original_path": "sample.csv",
  "resolved_path": "data/uploads/20260710/uuid_sample.csv",
  "content_hash": "sha256:...",
  "size_bytes": 1024,
  "suffix": ".csv",
  "mime_type": "text/csv",
  "access_mode": "read_only",
  "allowed_tasks": ["data_analysis", "knowledge_index"],
  "created_at": "2026-07-10T00:00:00Z"
}
```

Resolver 规则：

- project relative path 只能解析到 `project_root` 内。
- uploaded path 只能解析到 `data/uploads` 内。
- imported path 只能解析到 `data/files/imported` 内。
- external path 只有匹配 mount registry 时才允许。
- symlink 默认不跨越允许根目录。
- 默认排除 `.git`、`.venv`、`node_modules`、`dist`、cache 目录。
- 每次 resolver 成功或失败都可以写 access event。

`/chat` 改造目标：

当前前端会发送：

```json
{
  "message": "...",
  "uploads": [
    {
      "upload_id": "...",
      "relative_path": "data/uploads/..."
    }
  ]
}
```

成熟目标中，后端应把 uploads 转为结构化 `SourceRef`，并传入 Agent runtime：

```json
{
  "message": "...",
  "source_refs": ["src_..."]
}
```

Agent、Task Router、Knowledge Layer、ContextManager 都应使用同一套 `source_refs`。

## 10. Artifact Lifecycle

长期运行会产生大量 trace、run、upload、embedding、报告和截图。必须有生命周期管理。

ArtifactRecord 示例：

```json
{
  "artifact_id": "artifact_...",
  "run_id": "run_...",
  "task_id": "task_...",
  "type": "report",
  "path": "runs/.../report.md",
  "content_hash": "sha256:...",
  "size_bytes": 2048,
  "created_at": "2026-07-10T00:00:00Z",
  "retention_policy": "default_90_days",
  "referenced_by": ["trace_...", "context_..."],
  "cleanup_status": "active"
}
```

策略：

- trace、run index 默认长期保留。
- 大型 stdout、上传文件、embedding cache 需要 retention policy。
- 被 context、knowledge chunk、handoff、audit 引用的 artifact 不应直接删除。
- cleanup 应先 mark stale，再 tombstone，最后物理删除。
- 删除前要检查 references。
- cleanup 本身写 audit 和 trace。

## 11. Locks and Leases

多 Agent 并发后，需要资源锁。

Lock 类型：

| lock_type | 资源 | 目的 |
| --- | --- | --- |
| `file_write` | 文件或目录 | 防止两个 Agent 同时改同一文件 |
| `skill_version` | Skill slug/version | 防止并发写版本 |
| `memory_write` | memory scope/key | 防止覆盖长期记忆 |
| `goal_task` | task node | 防止重复执行 |
| `external_source` | external source id | 防止并发索引或读取超限 |
| `provider_budget` | provider/model | 防止超预算或超速率 |
| `artifact_cleanup` | artifact id | 防止清理正在使用的产物 |

ResourceLock 示例：

```json
{
  "lock_id": "lock_...",
  "lock_type": "file_write",
  "resource_id": "file:G:/AgentForge/src/agentforge/runtime/state.py",
  "owner_run_id": "run_...",
  "owner_agent_id": "executor_agent",
  "lease_expires_at": "2026-07-10T00:05:00Z",
  "status": "active"
}
```

规则：

- lock 必须有 lease，避免崩溃后永久锁死。
- 写文件、写 Skill、写 memory、执行 task node 前获取锁。
- 可重试锁冲突，但不能无限等待。
- lock acquisition / release / timeout 写 audit。
- 幂等操作必须带 idempotency key。

## 12. Policy / Approval / Audit 汇合点

成熟系统中，PolicyEngine 应在以下动作前运行：

- tool execution
- file source resolution
- external mount access
- model call
- secret injection
- memory write
- knowledge indexing
- context snapshot save
- artifact cleanup
- git operation

AuditEvent 最低字段：

```json
{
  "audit_id": "audit_...",
  "event_type": "file_source_resolved",
  "actor_type": "agent",
  "actor_id": "executor_agent",
  "run_id": "run_...",
  "task_id": "task_...",
  "resource": "src_...",
  "risk_level": "medium",
  "decision": "allowed",
  "policy_id": "policy_...",
  "created_at": "2026-07-10T00:00:00Z"
}
```

## 13. Prompt / Policy / AgentSpec Versioning

以下对象会直接改变 Agent 行为，必须版本化：

- system prompt
- Agent role prompt
- AgentSpec
- planner prompt
- reviewer / critic rubric
- model routing policy
- file source policy
- memory write policy
- approval policy
- retrieval/chunking policy

VersionRecord 示例：

```json
{
  "version_id": "prompt_v...",
  "type": "planner_prompt",
  "name": "default_planner",
  "content_hash": "sha256:...",
  "created_at": "2026-07-10T00:00:00Z",
  "created_by": "operator",
  "active": true,
  "change_reason": "Add source_refs to planning instructions."
}
```

规则：

- 每次 run 记录实际使用的 prompt/policy/AgentSpec/rubric/model routing config 版本。
- 修改版本对象需要 audit event。
- 旧版本不可覆盖，只能 supersede。
- 版本对象可以参与 regression 对比，解释行为变化。

## 14. Retrieval Evaluation

Knowledge Layer 不能只建索引，还需要评估检索质量。

RetrievalEvent 示例：

```json
{
  "retrieval_id": "ret_...",
  "query": "File Source Management",
  "retrieval_mode": "hybrid",
  "returned_chunks": ["chunk_1", "chunk_2"],
  "selected_for_context": ["chunk_1"],
  "citation_count": 2,
  "stale_count": 0,
  "created_at": "2026-07-10T00:00:00Z"
}
```

指标：

- recall@k
- citation accuracy
- stale retrieval rate
- source coverage
- no-answer accuracy
- user correction rate
- critic/reviewer citation error rate

规则：

- 用户纠错和 Reviewer/Critic 发现的错误引用应写入 retrieval feedback。
- chunking strategy、embedding model、reranker、metadata filter 的版本必须记录。
- retrieval evaluation 不要求一开始完整自动化，但事件记录必须先落地。

## 15. 数据目录

```text
data/governance/
  approvals.jsonl
  audit.jsonl
  policies.json
  policy_versions.jsonl
  locks.jsonl
  secrets_access.jsonl
  model_usage.jsonl

data/prompts/
  prompt_versions.jsonl
  agent_specs.jsonl
  rubrics.jsonl

data/evaluation/
  retrieval_events.jsonl
  retrieval_feedback.jsonl

data/files/
  sources.jsonl
  mounts.json
  ingestion_runs.jsonl
  access_events.jsonl
  imported/
    <source_id>/

data/artifacts/
  artifacts.jsonl
  cleanup_runs.jsonl
  tombstones.jsonl

data/models/
  usage.jsonl
  rate_limits.json
  failures.jsonl
```

## 16. API 目标

```text
GET  /api/files/sources
GET  /api/files/sources/{source_id}
POST /api/files/import
POST /api/files/mounts
GET  /api/files/mounts
DELETE /api/files/mounts/{mount_id}

GET  /api/governance/audit
GET  /api/governance/locks
POST /api/governance/locks/{lock_id}/release
GET  /api/governance/model-usage
GET  /api/governance/policy-versions

GET  /api/artifacts
GET  /api/artifacts/{artifact_id}
POST /api/artifacts/cleanup

GET  /api/prompts/versions
GET  /api/prompts/agent-specs
GET  /api/evaluation/retrieval
```

## 17. CLI 目标

```bash
agentforge files list
agentforge files import <path>
agentforge files mount add <path> --read-only
agentforge files mount list
agentforge files show <source_id>

agentforge governance audit --run <run_id>
agentforge governance locks
agentforge governance locks release <lock_id>
agentforge governance model-usage
agentforge governance policy-versions

agentforge artifacts list
agentforge artifacts cleanup --dry-run

agentforge prompts versions
agentforge evaluation retrieval
```

## 18. 与现有代码的迁移关系

优先迁移点：

1. 把 `code_analysis`、`document_analysis`、`data_analysis` 中重复的 `_resolve_under_project` 收敛到 `FileSourceResolver`。
2. 保留当前 project-root 默认限制，不改变安全行为。
3. 让 Web upload 生成 `SourceRef`，并保存在 `data/files/sources.jsonl`。
4. 修改 `/chat`，把 `uploads` 转成 `source_refs` 传给 Agent runtime。
5. Task Router 支持 `input.source_refs`，同时继续兼容 `path`、`paths`、`files`。
6. Knowledge Layer 索引时使用 `SourceRef`，不直接解析任意 path。
7. ContextManager 引用 source citation，而不是裸路径字符串。

## 19. 实施阶段

### Stage 1: Governance Primitives MVP

- `ExecutionProfile`
- `SecretRef`
- redaction helper
- `ModelRouter` wrapper
- model usage record
- minimal resource lock schema

### Stage 2: SourceRef MVP

- 新增 `SourceRef` schema。
- Web upload 写 `sources.jsonl`。
- Task Router 支持 `source_refs`。
- 现有 project-root 安全行为不变。

### Stage 3: FileSourceResolver

- 抽出统一 resolver。
- 三个 analysis handler 改用 resolver。
- 增加 unauthorized external path 测试。

### Stage 4: Structured Uploads in Chat

- `/chat` 消费 `uploads`。
- Agent intent/task_input 携带 `source_refs`。
- trace 记录 source_refs。

### Stage 5: External Mount Read-only

- mount registry。
- read-only external mount。
- policy + audit。
- Web Files / Sources 页面。

### Stage 6: Sandbox and Model Router

- execution profiles。
- model usage tracking。
- secrets redaction。
- provider budget。

### Stage 7: Locks and Artifact Lifecycle

- resource locks。
- artifact records。
- cleanup dry-run。
- retention policy。

### Stage 8: Versioning and Retrieval Evaluation

- prompt/policy/AgentSpec version records。
- run-level version references。
- retrieval events。
- retrieval feedback。

## 20. 测试计划

Unit tests：

- `SourceRef` schema validation。
- resolver rejects unauthorized external absolute path。
- resolver accepts uploaded source。
- resolver accepts read-only external mount。
- secret redaction。
- model router capability matching。
- prompt/policy version record validation。
- retrieval evaluation metric calculation。
- resource lock lease expiration。
- artifact reference check。

Integration tests：

- upload -> SourceRef -> data_analysis。
- chat uploads -> source_refs -> Task Router。
- external mount -> document_analysis read-only。
- private source -> embedding denied by policy。
- model call -> usage record -> audit event。
- run -> prompt/policy/AgentSpec version refs。
- retrieval feedback -> retrieval evaluation dataset。
- file write lock prevents concurrent write。
- artifact cleanup dry-run preserves referenced artifacts。

E2E tests：

- 用户上传 CSV，Agent 通过结构化 source ref 分析数据。
- 用户挂载外部只读目录，Agent 分析其中一个文档。
- 未授权绝对路径被拒绝并返回可解释错误。
- 两个 Agent 同时修改同一文件时，一个获得锁，另一个等待或失败。

## 21. 完成定义

这一层设计完成后，应满足：

- 任意文件处理都能追溯到 `SourceRef`。
- 项目外路径不能绕过 upload/import/mount/approval。
- 所有高风险工具都有 execution profile。
- secrets 不会出现在 trace、context、artifact 明文中。
- 模型调用能记录 provider/model/usage/failure。
- prompt、policy、AgentSpec 和 rubric 修改可版本化并被 run 引用。
- retrieval events 和 feedback 可用于评估检索质量。
- 并发写操作有 lock 或明确拒绝。
- artifact 有 retention、reference、cleanup 规则。
- handoff 文档记录当前实现阶段和未完成项。
