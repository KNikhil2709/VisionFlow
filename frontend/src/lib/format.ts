import type { Stage } from "../api/types";

export const shortId = (id: string) => id.slice(0, 8);

export const STAGE_META: Record<Stage, { label: string; color: string; sub: string }> = {
  ingest: { label: "Load image", color: "var(--stage-ingest)", sub: "open the photo" },
  inference: { label: "AI check", color: "var(--stage-inference)", sub: "score the image" },
  decision: { label: "Decide", color: "var(--stage-decision)", sub: "pass / reject / ask" },
  review: { label: "Human review", color: "var(--stage-review)", sub: "person decides" },
  finalize: { label: "Record result", color: "var(--stage-finalize)", sub: "save + alert" },
  done: { label: "Finished", color: "var(--stage-done)", sub: "complete" },
};

export const STAGES: Stage[] = ["ingest", "inference", "decision", "review", "finalize", "done"];

export const EVENT_COLOR: Record<string, string> = {
  WORKFLOW_STARTED: "var(--info)",
  ACTIVITY_COMPLETED: "var(--primary-light)",
  WORKFLOW_SUSPENDED: "var(--secondary)",
  SIGNAL_RECEIVED: "var(--warning)",
  WORKFLOW_COMPLETED: "var(--success)",
  WORKFLOW_FAILED: "var(--danger)",
};

export const pct = (x: number, total: number) => (total ? Math.round((x / total) * 100) : 0);
