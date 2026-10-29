import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";
import type { Metrics } from "../../api/types";

const COLORS: Record<string, string> = {
  RUNNING: "var(--info)",
  PAUSED: "var(--secondary)",
  COMPLETED: "var(--success)",
  FAILED: "var(--danger)",
};

export default function StatusDonut({ metrics }: { metrics: Metrics | null }) {
  if (!metrics) return <div className="hint">waiting for data…</div>;
  const data = Object.entries(metrics.by_status).map(([name, value]) => ({ name, value }));
  if (!data.length) return <div className="hint">no runs yet — submit a batch</div>;
  return (
    <ResponsiveContainer width="100%" height={200}>
      <PieChart>
        <Pie data={data} dataKey="value" nameKey="name" innerRadius={52} outerRadius={80} paddingAngle={2} stroke="none">
          {data.map((d) => (
            <Cell key={d.name} fill={COLORS[d.name] ?? "var(--text-muted)"} />
          ))}
        </Pie>
        <Tooltip
          contentStyle={{ background: "var(--bg-solid)", border: "1px solid var(--border)", borderRadius: 10, fontSize: 12 }}
        />
      </PieChart>
    </ResponsiveContainer>
  );
}
