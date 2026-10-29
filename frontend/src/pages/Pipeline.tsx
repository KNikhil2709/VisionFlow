import { useState } from "react";
import { Play, Zap, RotateCcw, AlertTriangle } from "lucide-react";
import { api, dataUrl } from "../api/client";
import { usePolling } from "../hooks/usePolling";
import { useReveal } from "../hooks/useReveal";
import PipelineBoard from "../components/pipeline/PipelineBoard";
import RunDrawer from "../components/pipeline/RunDrawer";
import ScoreHistogram from "../components/charts/ScoreHistogram";
import StatusDonut from "../components/charts/StatusDonut";
import { shortId } from "../lib/format";

export default function Pipeline() {
  const metrics = usePolling(() => api.metrics(), 700);
  const runsData = usePolling(() => api.runs(), 900);
  const [count, setCount] = useState(60);
  const [ratio, setRatio] = useState(0.6);
  const [busy, setBusy] = useState(false);
  const [selected, setSelected] = useState<string | null>(null);
  const [r1, c1] = useReveal<HTMLDivElement>();
  const [r2, c2] = useReveal<HTMLDivElement>();

  const runs = runsData?.runs ?? [];
  const w = metrics?.worker;

  const submit = async () => {
    setBusy(true);
    try {
      await api.submitBatch(count, ratio);
    } finally {
      setBusy(false);
    }
  };
  const crash = async () => { await api.workerCrash("after_record:ingest"); };
  const restart = async () => { await api.workerStart(); };

  const stat = (label: string, n: number | undefined) => (
    <div className="card stat">
      <div className="n">{n ?? 0}</div>
      <div className="l">{label}</div>
    </div>
  );

  return (
    <>
      <div className="page-head">
        <h1>Inspection Pipeline</h1>
        <p>
          Submit a batch of parts and watch each one flow through the steps: load the
          image, AI check, decide, optional human review, record the result. Then press
          “Simulate crash” and “Restart worker” — every item picks up from exactly where
          it stopped, and nothing is lost or done twice.
        </p>
      </div>

      {/* Controls */}
      <div className="card" style={{ marginBottom: 18 }}>
        <div className="controls">
          <div className="field">
            <label>Batch size</label>
            <input type="number" min={1} max={500} value={count}
              onChange={(e) => setCount(+e.target.value)} />
          </div>
          <div className="field">
            <label>Normal ratio</label>
            <input type="number" min={0} max={1} step={0.1} value={ratio}
              onChange={(e) => setRatio(+e.target.value)} />
          </div>
          <button className="btn btn-primary" onClick={submit} disabled={busy}>
            <Play size={15} /> {busy ? "submitting…" : "Submit batch"}
          </button>
          <div className="spacer" />
          <button className="btn btn-danger" onClick={crash} title="Arm a one-shot crash at the next ingest boundary">
            <AlertTriangle size={15} /> Simulate crash
          </button>
          <button className="btn btn-success" onClick={restart}>
            <RotateCcw size={15} /> Restart worker
          </button>
        </div>
        {w?.state === "crashed" && (
          <div className="hint" style={{ marginTop: 12, color: "var(--danger)" }}>
            <Zap size={13} style={{ verticalAlign: "-2px" }} /> worker crashed at{" "}
            <code>{w.last_crash_point}</code> after processing {w.processed} runs — hit
            “Restart worker” to watch in-flight runs resume from the event log.
          </div>
        )}
      </div>

      {/* Pipeline board */}
      <div className="card" style={{ marginBottom: 18 }}>
        <div className="card-title">Live flow</div>
        <PipelineBoard metrics={metrics} />
      </div>

      {/* Stats */}
      <div className="grid grid-4" style={{ marginBottom: 18 }}>
        {stat("Total runs", metrics?.total)}
        {stat("Running", metrics?.by_status.RUNNING)}
        {stat("Awaiting review", metrics?.by_status.PAUSED)}
        {stat("Completed", metrics?.by_status.COMPLETED)}
      </div>

      {/* Charts */}
      <div ref={r1} className={`grid grid-2 ${c1}`} style={{ marginBottom: 18 }}>
        <div className="card">
          <div className="card-title">Run status</div>
          <StatusDonut metrics={metrics} />
        </div>
        <div className="card">
          <div className="card-title">Anomaly score distribution & decision bands</div>
          <ScoreHistogram metrics={metrics} />
        </div>
      </div>

      {/* Recent runs */}
      <div ref={r2} className={`card ${c2}`}>
        <div className="card-title">Recent runs — click to inspect the event log</div>
        <div style={{ overflowX: "auto" }}>
          <table className="table">
            <thead>
              <tr>
                <th>Run</th><th>Image</th><th>Stage</th><th>Status</th>
                <th>Score</th><th>Verdict</th><th>Events</th><th>Heatmap</th>
              </tr>
            </thead>
            <tbody>
              {runs.slice(-14).reverse().map((r) => (
                <tr key={r.run_id} onClick={() => setSelected(r.run_id)}>
                  <td className="mono">{shortId(r.run_id)}</td>
                  <td className="mono">{r.image_id}</td>
                  <td style={{ textTransform: "capitalize" }}>{r.stage ?? "—"}</td>
                  <td><span className={`chip ${r.status}`}>{r.status}</span></td>
                  <td className="mono">{r.score != null ? r.score.toFixed(3) : "—"}</td>
                  <td>{r.verdict ? <span className={`chip ${r.verdict}`}>{r.verdict}</span> : "—"}</td>
                  <td className="mono">{r.n_events ?? "—"}</td>
                  <td>
                    {r.heatmap ? (
                      <img src={dataUrl(r.heatmap)} alt="" width={34} height={34}
                        style={{ borderRadius: 6, border: "1px solid var(--border)", objectFit: "cover" }} />
                    ) : "—"}
                  </td>
                </tr>
              ))}
              {!runs.length && (
                <tr><td colSpan={8} className="hint">No runs yet — submit a batch above.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {selected && <RunDrawer runId={selected} onClose={() => setSelected(null)} />}
    </>
  );
}
