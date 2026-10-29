import { X } from "lucide-react";
import { api, dataUrl } from "../../api/client";
import { usePolling } from "../../hooks/usePolling";
import { EVENT_COLOR, shortId } from "../../lib/format";

export default function RunDrawer({ runId, onClose }: { runId: string; onClose: () => void }) {
  const detail = usePolling(() => api.run(runId), 700);

  return (
    <div className="overlay" onClick={onClose}>
      <div className="drawer" onClick={(e) => e.stopPropagation()}>
        <button className="btn btn-sm drawer-close" onClick={onClose}>
          <X size={15} /> close
        </button>

        <div className="card-title">Run {shortId(runId)}</div>

        {!detail ? (
          <div className="hint">loading…</div>
        ) : (
          <>
            <div className="card" style={{ marginBottom: 14, borderColor: "var(--border-light)" }}>
              <div style={{ fontSize: 14 }}>{detail.caption}</div>
            </div>

            <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 16 }}>
              <span className={`chip ${detail.state.status}`}>{detail.state.status}</span>
              {detail.state.verdict && (
                <span className={`chip ${detail.state.verdict}`}>verdict: {detail.state.verdict}</span>
              )}
              {detail.state.score != null && (
                <span className="chip">score {detail.state.score.toFixed(3)}</span>
              )}
              {detail.state.auto != null && (
                <span className="chip">{detail.state.auto ? "auto-decided" : "human-reviewed"}</span>
              )}
            </div>

            {detail.state.heatmap && (
              <div style={{ marginBottom: 16 }}>
                <div className="card-title">Anomaly heatmap</div>
                <img className="review-img" src={dataUrl(detail.state.heatmap)} alt="heatmap"
                  style={{ maxWidth: 260 }} />
              </div>
            )}

            <div className="card" style={{ marginBottom: 16 }}>
              <div style={{ fontSize: 13, color: "var(--text-secondary)" }}>
                This view is <strong>reconstructed by folding {detail.state.n_events} events</strong> —
                the log below is the single source of truth. Side effects:{" "}
                <strong>{detail.verdicts}</strong> verdict ·{" "}
                <strong>{detail.alerts}</strong> alert{detail.alerts === 1 ? "" : "s"} written
                (exactly-once).
              </div>
            </div>

            <div className="card-title">Event log</div>
            <div className="timeline">
              {detail.events.map((e) => (
                <div className="tl-item" key={e.seq}
                  style={{ ["--primary" as string]: EVENT_COLOR[e.type] ?? "var(--primary)" }}>
                  <div>
                    <span className="tl-seq">#{e.seq}</span>
                    <span className="tl-type" style={{ color: EVENT_COLOR[e.type] ?? "var(--text-primary)" }}>
                      {e.type}
                    </span>
                  </div>
                  <div className="tl-payload">
                    {JSON.stringify(e.payload, null, 1)}
                    {e.idempotency_key && (
                      <>
                        {"\n"}
                        <span className="tl-key">idempotency_key: {e.idempotency_key}</span>
                      </>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
