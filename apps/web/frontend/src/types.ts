export type Lang = "zh" | "en";
export type AgentMode = "harness_workflow" | "tool_calling";
export type TabKey =
  | "agent"
  | "dashboard"
  | "chat"
  | "generate"
  | "run"
  | "evolve"
  | "runs"
  | "skills"
  | "tasks"
  | "hqs"
  | "traces"
  | "tools"
  | "memory"
  | "settings";
export type DrilldownKey = "trace" | "hqs" | "memory" | "diff";

export type JsonRecord = Record<string, unknown>;

export interface WarningItem {
  type?: string;
  message?: string;
}

export interface ArtifactItem {
  type?: string;
  path?: string;
  relative_path?: string;
}

export interface UploadedFileRecord extends JsonRecord {
  upload_id: string;
  original_name: string;
  stored_name: string;
  relative_path: string;
  url: string;
  content_type: string;
  size_bytes: number;
  kind: string;
  supported_tasks: string[];
}

export interface ScoreReport {
  average_score?: number;
  confidence?: number;
  scores?: Record<string, number>;
}

export interface SkillSummary {
  skill_slug: string;
  title?: string;
  latest_version?: string;
  latest_skill_path?: string;
  versions?: string[];
  version?: string;
  source?: string;
  skill_path?: string;
  relative_path?: string;
  metadata?: JsonRecord;
  match_score?: number;
  reasons?: string[];
}

export interface TasksetSummary {
  name: string;
  description?: string;
  path?: string;
  relative_path?: string;
  task_count?: number;
  format?: string;
  error?: string;
}

export interface TimelineStep extends JsonRecord {
  name?: string;
  kind?: string;
  status?: string;
  step_id?: string;
  artifact_count?: number;
  error_count?: number;
  iteration?: number;
  decision_type?: string;
  tool_name?: string;
  arguments?: JsonRecord;
  model_decision?: JsonRecord;
  validation?: JsonRecord;
  validation_errors?: unknown[];
  observation?: JsonRecord;
  observation_summary?: JsonRecord;
  parse_repair?: JsonRecord;
  tool_result?: JsonRecord;
  errors?: unknown[];
}

export interface WebPayload extends JsonRecord {
  response?: string;
  run_id?: string;
  agent_mode?: string;
  final_answer_source?: string;
  stop_reason?: string;
  parse_repair_count?: number;
  trace_file?: string;
  trace_path?: string;
  trace_url?: string;
  hqs?: ScoreReport;
  system_hqs?: ScoreReport;
  last_response_hqs?: ScoreReport;
  last_system_hqs?: ScoreReport;
  current_system_hqs?: ScoreReport;
  intent?: JsonRecord;
  plan?: JsonRecord;
  selected_skill?: SkillSummary;
  execution?: JsonRecord;
  execution_state?: JsonRecord;
  memory_context?: JsonRecord;
  memory_retrieval?: JsonRecord;
  warnings?: WarningItem[];
  provider_warnings?: WarningItem[];
  artifacts?: ArtifactItem[];
  timeline?: TimelineStep[];
  tool_call_timeline?: TimelineStep[];
  run?: {
    steps?: TimelineStep[];
    run_id?: string;
  };
  skill_name?: string;
  skill_slug?: string;
  version?: string;
  generation_mode?: string;
  skill_path?: string;
  relative_skill_path?: string;
  final_skill_path?: string;
  relative_final_skill_path?: string;
  result_path?: string;
  run_dir?: string;
  relative_run_dir?: string;
  mode?: string;
  output?: string;
  iterations?: Array<{
    iteration?: number;
    average_hqs?: number;
    candidate_average_hqs?: number | null;
    decision?: string;
  }>;
}

export interface RunRecord extends JsonRecord {
  run_id: string;
  task_type: string;
  title: string;
  status: string;
  input?: JsonRecord;
  output?: JsonRecord | null;
  trace_path?: string | null;
  created_at: string;
  updated_at?: string;
  completed_at?: string | null;
}

export interface RunStepRecord extends JsonRecord {
  step_id: string;
  run_id: string;
  name: string;
  kind: string;
  status: string;
  input?: unknown;
  output?: unknown;
  error?: unknown;
  started_at?: string | null;
  completed_at?: string | null;
}

export interface RunArtifactRecord extends JsonRecord {
  artifact_id: string;
  run_id: string;
  type: string;
  path?: string | null;
  content_type?: string | null;
  metadata?: JsonRecord | null;
  created_at: string;
}

export interface RunToolCallRecord extends JsonRecord {
  tool_call_id: string;
  run_id: string;
  step_id?: string | null;
  tool_name: string;
  status: string;
  arguments?: JsonRecord;
  result?: JsonRecord | null;
  error?: unknown;
  started_at: string;
  completed_at?: string | null;
}

export interface RunHqsRecord extends JsonRecord {
  hqs_id: string;
  run_id: string;
  scope: string;
  average_score: number;
  report: ScoreReport;
  created_at: string;
}

export interface RunWorkflowCheckpointRecord extends JsonRecord {
  checkpoint_id: string;
  run_id: string;
  workflow_id: string;
  step_name?: string | null;
  state?: JsonRecord;
  created_at: string;
}

export interface RunDetailRecord extends RunRecord {
  steps?: RunStepRecord[];
  artifacts?: RunArtifactRecord[];
  tool_calls?: RunToolCallRecord[];
  hqs_reports?: RunHqsRecord[];
  workflow_checkpoints?: RunWorkflowCheckpointRecord[];
}

export interface ToolRecord extends JsonRecord {
  name: string;
  kind: string;
  description?: string;
  input_schema?: JsonRecord;
  output_schema?: JsonRecord;
  error_specs?: unknown[];
  permission_level?: string;
  idempotent?: boolean;
  side_effects?: boolean;
  timeout_seconds?: number | null;
}

export interface MemoryEpisodeRecord extends JsonRecord {
  episode_id?: string;
  created_at?: string;
  user_input?: string;
  response?: string;
}

export interface SemanticMemoryRecord extends JsonRecord {
  key?: string;
  updated_at?: string;
  summary?: string;
  tags?: unknown[];
}

export interface TaskTypeRecord extends JsonRecord {
  task_type: string;
  title: string;
  description: string;
  input_schema?: JsonRecord;
  options_schema?: JsonRecord;
  stable?: boolean;
}

export interface TraceSummaryRecord extends JsonRecord {
  filename: string;
  path?: string;
  type?: string;
  created_at?: string;
  trace_id?: string;
  error?: string;
}

export interface TraceDetailRecord extends JsonRecord {
  trace_id?: string;
  type?: string;
  created_at?: string;
  input?: unknown;
  steps?: unknown[];
  output?: unknown;
  artifacts?: unknown[];
  errors?: unknown[];
}

export interface HqsStatusRecord extends JsonRecord {
  last_response_hqs?: ScoreReport;
  last_system_hqs?: ScoreReport;
  current_system_hqs?: ScoreReport;
}

export interface HealthDirectoryRecord extends JsonRecord {
  path: string;
  exists?: boolean;
  is_dir?: boolean;
  writable?: boolean;
}

export interface HealthStatusRecord extends JsonRecord {
  status?: string;
  version?: JsonRecord;
  directories?: HealthDirectoryRecord[];
  config?: JsonRecord;
}

export interface ProviderSummaryRecord extends JsonRecord {
  name?: string;
  type?: string;
  base_url?: string;
  model?: string;
  has_api_key?: boolean;
  api_key_env?: string | null;
  timeout_seconds?: number;
}

export interface ConfigStatusRecord extends JsonRecord {
  project_root?: string;
  provider_config_path?: string;
  provider_config_exists?: boolean;
  provider_example_exists?: boolean;
  default_provider?: string;
  providers?: ProviderSummaryRecord[];
  selected_provider?: JsonRecord;
  errors?: unknown[];
}

export interface SkillVersionRecord extends JsonRecord {
  skill_slug: string;
  version: string;
  skill_path?: string;
  source?: string;
  markdown?: string;
  metadata?: JsonRecord | null;
  diff?: string | null;
}

export interface SummaryState {
  responseScore?: number;
  systemScore?: number;
  intent: string;
  plan: string;
  skill: string;
  traceUrl?: string;
  traceLabel?: string;
  warnings: WarningItem[];
  artifacts: ArtifactItem[];
  timeline: TimelineStep[];
}

export interface ProgressState {
  phases: string[];
  startedAt: number;
}
