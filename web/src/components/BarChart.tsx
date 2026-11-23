import { formatFull, formatNumber, formatPercent } from "../lib/format";

export interface Bar {
  label: string;
  value: number;
  share: number;
  highlight?: boolean;
}

const LABEL_W = 170;
const VALUE_W = 110;
const ROW_H = 28;
const BAR_H = 14;
const W = 640;

/** Horizontal bar chart in plain SVG (single series: no legend; the table beside it carries the exact numbers). */
export function BarChart({ bars, title }: { bars: Bar[]; title: string }) {
  const max = Math.max(...bars.map((b) => b.value), 1);
  const plotW = W - LABEL_W - VALUE_W;
  const h = bars.length * ROW_H + 4;
  return (
    <svg className="bars" viewBox={`0 0 ${W} ${h}`} role="img" aria-label={title} preserveAspectRatio="xMinYMin meet">
      <title>{title}</title>
      {bars.map((b, i) => {
        const y = i * ROW_H + 2;
        const w = Math.max(2, (b.value / max) * plotW);
        return (
          <g key={b.label}>
            <title>{`${b.label}: ${formatFull(b.value)} DPS (${formatPercent(b.share)})`}</title>
            <text x={LABEL_W - 8} y={y + ROW_H / 2} textAnchor="end" dominantBaseline="middle" className="bar-label">
              {b.label}
            </text>
            <rect x={LABEL_W} y={y + (ROW_H - BAR_H) / 2} width={w} height={BAR_H} rx={3} className={b.highlight ? "bar bar-alt" : "bar"} />
            <text x={LABEL_W + w + 6} y={y + ROW_H / 2} dominantBaseline="middle" className="bar-value">
              {formatNumber(b.value)} · {formatPercent(b.share, 0)}
            </text>
          </g>
        );
      })}
    </svg>
  );
}
