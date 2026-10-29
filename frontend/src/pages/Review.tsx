import { useState } from "react";
import { Check, X } from "lucide-react";
import { api, dataUrl } from "../api/client";
import { usePolling } from "../hooks/usePolling";
import { shortId } from "../lib/format";

export default function Review() {
  const data = usePolling(() => api.review(), 800);
  const metrics = usePolling(() => api.metrics(), 1500);
  const [busy, setBusy] = useState<string | null>(null);

  const queue = data?.queue ?? [];

  const decide = async (id: string, verdict: "pass" | "reject") => {
    setBusy(id);
    try {
      await api.verdict(id, verdict);
    } finally {
      setBusy(null);
    }
  };

  return (
    <>
      <div className="page-head">
        <h1>Human Review Queue</h1>
        <p>
          Runs whose anomaly score fell in the ambiguous band (between the auto-pass and
          auto-reject thresholds) are parked here <strong>durably</strong> — the workflow
          holds no process or thread while it waits. Your verdict is appended as a signal
          event and the parked run resumes from exactly where it suspended.
        </p>
      </div>

      {!queue.length ? (
        <div className="card hint">
          Nothing awaiting review. Submit a batch on the Pipeline page — some runs will
          land in the ambiguous band and appear here.
        </div>
      ) : (
        <div className="grid grid-3">
          {queue.map((r) => {
            const score = r.score ?? 0;
            const t_low = r.policy?.t_low ?? metrics?.thresholds.t_low ?? 0.35;
            const t_high = r.policy?.t_high ?? metrics?.thresholds.t_high ?? 0.65;
            return (
              <div className="card review-card" key={r.run_id}>
                <img className="review-img" src={dataUrl(r.heatmap)} alt={r.image_id ?? ""} />
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <span className="mono">{r.image_id}</span>
                  <span className="mono muted">{shortId(r.run_id)}</span>
                </div>

                <div>
                  <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12 }}>
                    <span className="muted">anomaly score</span>
                    <strong>{score.toFixed(3)}</strong>
                  </div>
                  <div className="score-bar" style={{ marginTop: 6 }}>
                    <div className="score-bands">
                      <span className="band-line" style={{ left: `${t_low * 100}%` }} />
                      <span className="band-line" style={{ left: `${t_high * 100}%` }} />
                    </div>
                    <span className="score-knob" style={{ left: `${score * 100}%` }} />
                  </div>
                  <div className="hint" style={{ marginTop: 5 }}>
                    bands: pass &lt; {t_low} · review · {t_high} &lt; reject
                  </div>
                </div>

                <div style={{ display: "flex", gap: 10 }}>
                  <button className="btn btn-success btn-sm" style={{ flex: 1, justifyContent: "center" }}
                    disabled={busy === r.run_id} onClick={() => decide(r.run_id, "pass")}>
                    <Check size={15} /> Pass
                  </button>
                  <button className="btn btn-danger btn-sm" style={{ flex: 1, justifyContent: "center" }}
                    disabled={busy === r.run_id} onClick={() => decide(r.run_id, "reject")}>
                    <X size={15} /> Reject
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </>
  );
}
