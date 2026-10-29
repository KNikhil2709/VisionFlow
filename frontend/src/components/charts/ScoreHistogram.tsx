import {
  Bar, BarChart, Cell, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import type { Metrics } from "../../api/types";

/** Score distribution with the three decision bands shaded by bar colour:
 * below t_low = auto-pass (green), middle = review (pink), above t_high = reject (red). */
export default function ScoreHistogram({ metrics }: { metrics: Metrics | null }) {
  if (!metrics) return <div className="hint">waiting for data…</div>;
  const { t_low, t_high } = metrics.thresholds;
  const data = metrics.score_hist.map((n, i) => {
    const center = (i + 0.5) / 20;
    const band = center < t_low ? "pass" : center > t_high ? "reject" : "review";
    return { bin: (i / 20).toFixed(2), n, band };
  });
  const color = (b: string) =>
    b === "pass" ? "var(--success)" : b === "reject" ? "var(--danger)" : "var(--secondary)";
  return (
    <ResponsiveContainer width="100%" height={200}>
      <BarChart data={data} margin={{ top: 8, right: 8, left: -18, bottom: 0 }}>
        <XAxis dataKey="bin" tick={{ fill: "var(--text-muted)", fontSize: 10 }}
          interval={3} axisLine={false} tickLine={false} />
        <YAxis tick={{ fill: "var(--text-muted)", fontSize: 10 }} axisLine={false} tickLine={false} allowDecimals={false} />
        <Tooltip
          contentStyle={{ background: "var(--bg-solid)", border: "1px solid var(--border)", borderRadius: 10, fontSize: 12 }}
          labelStyle={{ color: "var(--text-muted)" }}
          formatter={(v: number, _n, p) => [`${v} runs`, (p.payload as { band: string }).band]}
        />
        <ReferenceLine x={(Math.round(t_low * 20) / 20).toFixed(2)} stroke="var(--text-secondary)" strokeDasharray="3 3" />
        <ReferenceLine x={(Math.round(t_high * 20) / 20).toFixed(2)} stroke="var(--text-secondary)" strokeDasharray="3 3" />
        <Bar dataKey="n" radius={[3, 3, 0, 0]}>
          {data.map((d, i) => (
            <Cell key={i} fill={color(d.band)} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
