export type Status = "RUNNING" | "PAUSED" | "COMPLETED" | "FAILED";
export type Stage = "ingest" | "inference" | "decision" | "review" | "finalize" | "done";
export type Verdict = "pass" | "reject" | null;

export interface RunRow {
  policy?: { t_low: number; t_high: number } | null;
  run_id: string;
  workflow: string;
  status: Status;
  stage: Stage | null;
  waiting_for: string | null;
  verdict: Verdict;
  score: number | null;
  image_id: string | null;
  heatmap: string | null;
  auto: boolean | null;
  n_events: number | null;
  created_at: string;
  updated_at: string;
}

export interface EventRow {
  seq: number;
  type: string;
  payload: Record<string, unknown>;
  idempotency_key: string | null;
  at: string | null;
}

export interface InspectResult {
  score: number;
  verdict: "pass" | "reject" | "review";
  label: string;
  image: string;
  heatmap: string;
  thresholds: { t_low: number; t_high: number };
  explanation: string;
}

export interface RunDetail {
  caption: string;
  state: {
    status: Status;
    stage: Stage;
    score: number | null;
    verdict: Verdict;
    heatmap: string | null;
    image: string | null;
    auto: boolean | null;
    waiting_for: string | null;
    workflow: string;
    input: Record<string, unknown>;
    result: Record<string, unknown> | null;
    n_events: number;
    steps: { name: string; call_index: number; result: unknown; seq: number }[];
  };
  events: EventRow[];
  alerts: number;
  verdicts: number;
}

export interface WorkerStatus {
  state: "running" | "crashed" | "stopped";
  processed: number;
  last_crash_point: string | null;
}

export interface Metrics {
  total: number;
  by_status: Record<string, number>;
  by_stage: Record<string, number>;
  by_verdict: Record<string, number>;
  review_pending: number;
  worker: WorkerStatus;
  score_hist: number[];
  thresholds: { t_low: number; t_high: number };
}
