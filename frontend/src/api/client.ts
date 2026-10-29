import type { Metrics, RunDetail, RunRow, WorkerStatus } from "./types";

// In dev, Vite proxies /api and /data to the backend (see vite.config.ts).
const BASE = import.meta.env.VITE_API_URL || "";

async function j<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(BASE + path, {
    headers: { "content-type": "application/json" },
    ...init,
  });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json() as Promise<T>;
}

export const api = {
  health: () => j<{ ok: boolean; cv_backend: string }>("/api/health"),
  metrics: () => j<Metrics>("/api/metrics"),
  runs: () => j<{ runs: RunRow[] }>("/api/runs"),
  run: (id: string) => j<RunDetail>(`/api/runs/${id}`),
  review: () => j<{ queue: RunRow[] }>("/api/review"),
  submitBatch: (count: number, normal_ratio: number, seed?: number) =>
    j<{ submitted: number }>("/api/batch", {
      method: "POST",
      body: JSON.stringify({ count, normal_ratio, seed }),
    }),
  verdict: (id: string, verdict: "pass" | "reject") =>
    j<{ ok: boolean }>(`/api/runs/${id}/verdict`, {
      method: "POST",
      body: JSON.stringify({ verdict }),
    }),
  inspect: async (fileBlob: File) => {
    const fd = new FormData();
    fd.append("file", fileBlob);
    const res = await fetch(BASE + "/api/inspect", { method: "POST", body: fd });
    if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || res.statusText);
    return res.json() as Promise<{ run_id: string }>;
  },
  worker: () => j<WorkerStatus>("/api/worker"),
  workerStart: () => j<WorkerStatus>("/api/worker/start", { method: "POST" }),
  workerCrash: (point: string) =>
    j<{ armed: string }>("/api/worker/crash", {
      method: "POST",
      body: JSON.stringify({ point }),
    }),
};

// Image/heatmap URL for a path like "heatmaps/defect_0001.png".
export const dataUrl = (p: string | null | undefined) => (p ? `${BASE}/data/${p}` : "");
