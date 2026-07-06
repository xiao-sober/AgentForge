export type Lang = "zh" | "en";
export type AgentMode = "harness_workflow" | "tool_calling";
export type TabKey = "chat" | "generate" | "run" | "evolve";
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
  version?: string;
  source?: string;
  skill_path?: string;
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
