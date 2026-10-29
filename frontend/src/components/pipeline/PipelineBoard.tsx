import type { Metrics } from "../../api/types";
import { STAGES, STAGE_META } from "../../lib/format";

export default function PipelineBoard({ metrics }: { metrics: Metrics | null }) {
  const byStage = metrics?.by_stage ?? {};
  // Only animate the flow when the worker is actually running.
  const working = metrics?.worker.state === "running";
  return (
    <div className="pipeline">
      {STAGES.map((stage) => {
        const meta = STAGE_META[stage];
        const count = byStage[stage] ?? 0;
        const active = count > 0 && stage !== "done";
        const flowing = active && working && stage !== "review";
        return (
          <div
            key={stage}
            className={`stage${active ? " active" : ""}`}
            style={{ ["--accent" as string]: meta.color }}
          >
            <div className="s-name">{meta.label}</div>
            <div className="s-sub">{meta.sub}</div>
            <div className={`s-count${count > 0 ? " hot" : ""}`}>{count}</div>
            {flowing && (
              <div className="flow-track">
                {[0, 0.7, 1.4].map((d, i) => (
                  <span key={i} className="flow-dot" style={{ animationDelay: `${d}s` }} />
                ))}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
