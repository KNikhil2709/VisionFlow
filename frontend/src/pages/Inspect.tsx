import { useEffect, useRef, useState } from "react";
import { UploadCloud, CheckCircle2, XCircle, HelpCircle, Loader2 } from "lucide-react";
import { Link } from "react-router-dom";
import { api, dataUrl } from "../api/client";
import type { InspectResult } from "../api/types";

const VERDICT_UI = {
  pass: { icon: CheckCircle2, color: "var(--success)", title: "Looks fine" },
  reject: { icon: XCircle, color: "var(--danger)", title: "Defect found" },
  review: { icon: HelpCircle, color: "var(--secondary)", title: "Needs a person to look" },
} as const;

export default function Inspect() {
  const [runId, setRunId] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [result, setResult] = useState<InspectResult | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [drag, setDrag] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!runId) return;
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout>;
    const poll = async () => {
      try {
        const { state } = await api.run(runId);
        if (cancelled) return;
        setErr(null);
        if (state.status === "FAILED") {
          setErr("Inspection failed. See the run history on the Pipeline page.");
          setBusy(false);
          return;
        }
        if (state.status === "PAUSED" || state.status === "COMPLETED") {
          const verdict = state.status === "PAUSED" ? "review" : state.verdict!;
          const policy = state.input.policy as { t_low: number; t_high: number };
          setResult({
            score: state.score!, verdict, heatmap: state.heatmap!,
            image: state.input.image_id as string, thresholds: policy,
            label: VERDICT_UI[verdict].title,
            explanation: verdict === "review"
              ? "This inspection is saved in the review queue for a human decision."
              : "The inspection and its decision are saved in the pipeline history.",
          });
          setBusy(false);
          return;
        }
      } catch {
        if (cancelled) return;
        setErr("Reconnecting… Your submitted inspection remains saved.");
      }
      timer = setTimeout(poll, 800);
    };
    void poll();
    return () => { cancelled = true; clearTimeout(timer); };
  }, [runId]);

  useEffect(() => () => { if (preview) URL.revokeObjectURL(preview); }, [preview]);

  const run = async (file: File) => {
    if (busy) return;
    setRunId(null);
    setErr(null);
    setResult(null);
    setPreview(URL.createObjectURL(file));
    setBusy(true);
    try {
      const submitted = await api.inspect(file);
      setRunId(submitted.run_id);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Something went wrong");
      setBusy(false);
    }
  };

  const onPick = (f?: File | null) => f && run(f);
  const v = result ? VERDICT_UI[result.verdict] : null;

  return (
    <>
      <div className="page-head">
        <h1>Check an Image</h1>
        <p>
          Drop in a photo matching the trained brushed-metal sample parts and the AI will say whether it looks fine, looks
          defective, or is too close to call and needs a person. The red glow on the
          heatmap shows where it found something unusual.
        </p>
      </div>

      <div className="grid grid-2">
        {/* Upload zone */}
        <div
          className="card"
          onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
          onDragLeave={() => setDrag(false)}
          onDrop={(e) => { e.preventDefault(); setDrag(false); onPick(e.dataTransfer.files?.[0]); }}
          style={{
            borderStyle: "dashed", borderColor: drag ? "var(--primary)" : "var(--border-light)",
            display: "flex", flexDirection: "column", alignItems: "center",
            justifyContent: "center", textAlign: "center", minHeight: 280, cursor: "pointer",
          }}
          onClick={() => inputRef.current?.click()}
        >
          <input ref={inputRef} type="file" accept="image/*" hidden disabled={busy}
            onChange={(e) => onPick(e.target.files?.[0])} />
          {preview ? (
            <img src={preview} alt="your upload" style={{
              maxWidth: "100%", maxHeight: 220, borderRadius: 10, border: "1px solid var(--border)" }} />
          ) : (
            <>
              <UploadCloud size={44} color="var(--primary-light)" />
              <div style={{ marginTop: 12, fontWeight: 600 }}>Drop an image here</div>
              <div className="hint" style={{ marginTop: 4 }}>or click to choose a file</div>
            </>
          )}
        </div>

        {/* Result */}
        <div className="card">
          <div className="card-title">Result</div>
          {busy && (
            <div className="hint" style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <Loader2 size={16} className="spin" /> {runId ? "Inspection queued or running…" : "Uploading…"}
            </div>
          )}
          {runId && <p className="hint">Saved run: {runId} · <Link to="/pipeline">View pipeline</Link></p>}
          {result?.verdict === "review" && <p><Link to="/review">Open review queue</Link></p>}
          {err && <div style={{ color: "var(--danger)" }}>{err}</div>}
          {!busy && !err && !result && (
            <div className="hint">Upload an image to see the verdict, score and heatmap.</div>
          )}
          {result && v && (
            <>
              <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 12 }}>
                <v.icon size={26} color={v.color} />
                <span style={{ fontSize: 20, fontWeight: 800, color: v.color }}>{v.title}</span>
              </div>
              <img className="review-img" src={dataUrl(result.heatmap)} alt="heatmap"
                style={{ maxWidth: 260, marginBottom: 12 }} />
              <div style={{ marginBottom: 8 }}>
                <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12 }}>
                  <span className="muted">anomaly score</span>
                  <strong>{result.score.toFixed(3)}</strong>
                </div>
                <div className="score-bar" style={{ marginTop: 6 }}>
                  <div className="score-bands">
                    <span className="band-line" style={{ left: `${result.thresholds.t_low * 100}%` }} />
                    <span className="band-line" style={{ left: `${result.thresholds.t_high * 100}%` }} />
                  </div>
                  <span className="score-knob" style={{ left: `${Math.min(result.score, 1) * 100}%` }} />
                </div>
                <div className="hint" style={{ marginTop: 5 }}>
                  pass &lt; {result.thresholds.t_low} · unsure · {result.thresholds.t_high} &lt; reject
                </div>
              </div>
              <p style={{ fontSize: 14, color: "var(--text-secondary)" }}>{result.explanation}</p>
            </>
          )}
        </div>
      </div>

      <div className="card" style={{ marginTop: 18 }}>
        <div className="hint">
          No image handy? Sample part photos are in <code>data/samples/test</code> — drag one
          from the <code>good</code> or <code>defect</code> folder. This check uses the same
          detector as the pipeline. Every upload is saved as a durable inspection.
        </div>
      </div>
    </>
  );
}
