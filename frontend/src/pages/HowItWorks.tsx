import { Database, RefreshCw, ShieldCheck, PauseCircle, GitBranch, Eye } from "lucide-react";
import { useReveal } from "../hooks/useReveal";

const CONCEPTS = [
  {
    icon: Database,
    title: "Event sourcing — the log is the only truth",
    body: (
      <>
        A run stores nothing but an append-only list of events (<code>WORKFLOW_STARTED</code>,{" "}
        <code>ACTIVITY_COMPLETED</code>, <code>SIGNAL_RECEIVED</code>…). Its status, score and
        verdict are never stored authoritatively — they are <em>derived</em> by folding the log.
        The status table you see is just a cache, rebuildable at any time.
      </>
    ),
  },
  {
    icon: RefreshCw,
    title: "Deterministic replay — how a crashed run resumes",
    body: (
      <>
        To make progress, the worker re-runs the workflow function from the top against the
        history. Any activity already in the log returns its <em>recorded</em> result without
        re-executing; the first activity not yet recorded is the frontier and runs for real. So a
        restarted worker rebuilds the exact in-memory state and continues — expensive inference is
        never recomputed.
      </>
    ),
  },
  {
    icon: ShieldCheck,
    title: "Exactly-once side effects — idempotency keys",
    body: (
      <>
        Every side effect (writing a verdict, firing a reject alert) carries a deterministic key{" "}
        <code>run:callindex:activity</code> and is written to a sink with that key as its PRIMARY
        KEY. If the worker dies <em>after</em> the effect fired but <em>before</em> its event was
        persisted, replay re-runs the activity — but the sink’s <code>ON CONFLICT DO NOTHING</code>{" "}
        means the alert is still sent exactly once.
      </>
    ),
  },
  {
    icon: PauseCircle,
    title: "Durable pause — human-in-the-loop without a held process",
    body: (
      <>
        An ambiguous score calls <code>wait_for_signal("human_verdict")</code>. With no matching
        signal in the log, the run suspends: a <code>WORKFLOW_SUSPENDED</code> event is appended and
        the worker moves on. No thread, no process is held — the run could wait for days. A reviewer’s
        verdict is appended as a <code>SIGNAL_RECEIVED</code> event, and the run becomes runnable
        again.
      </>
    ),
  },
  {
    icon: GitBranch,
    title: "Workflow vs. activity — the determinism boundary",
    body: (
      <>
        Workflow code is pure orchestration: it may only branch on values it got from the context.
        All non-determinism — the CV model, file I/O, clocks, randomness — lives in <em>activities</em>.
        That boundary is exactly what makes replay safe, and it keeps the swappable PatchCore model
        cleanly separable from the engine.
      </>
    ),
  },
  {
    icon: Eye,
    title: "The CV core is swappable",
    body: (
      <>
        The default backend is a deterministic simulated scorer so the whole system runs with no
        GPU or dataset. Setting <code>VF_CV_BACKEND=patchcore</code> drops in the real PatchCore
        model (frozen WideResNet-50 backbone, coreset memory bank, nearest-neighbour patch scoring)
        on MVTec AD — the engine never changes.
      </>
    ),
  },
];

export default function HowItWorks() {
  const [ref, cls] = useReveal<HTMLDivElement>();
  return (
    <>
      <div className="page-head">
        <h1>How It Works</h1>
        <p>
          VisionFlow is a small durable-execution engine (in the spirit of Temporal) built
          specifically for a computer-vision inspection pipeline. The CV model is the swappable
          part; the hard engineering is making the pipeline around it survive crashes and
          multi-day human-review pauses without losing or duplicating work.
        </p>
      </div>

      <div className="card" style={{ marginBottom: 18 }}>
        <div className="card-title">Pipeline</div>
        <pre style={{
          fontFamily: "var(--mono)", fontSize: 12.5, color: "var(--text-secondary)",
          overflowX: "auto", lineHeight: 1.7,
        }}>{`image ─▶ ingest ─▶ run_inference ─▶ ┌ score < t_low  ─▶ PASS ─────────────┐
                    (CV model)      │ score > t_high ─▶ REJECT + alert ──┤─▶ finalize ─▶ done
                                    └ otherwise      ─▶ wait_for_signal ─┘
                                                        (durable human review)`}</pre>
      </div>

      <div ref={ref} className={`card ${cls}`}>
        <div className="card-title">Core concepts</div>
        {CONCEPTS.map(({ icon: Icon, title, body }) => (
          <div className="concept" key={title}>
            <div className="ic"><Icon size={22} /></div>
            <div>
              <h3>{title}</h3>
              <p>{body}</p>
            </div>
          </div>
        ))}
      </div>
    </>
  );
}
