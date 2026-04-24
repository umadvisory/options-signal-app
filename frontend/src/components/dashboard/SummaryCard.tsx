import type { StrategyStats } from "@/types/dashboard";
import { formatNumber, formatPct } from "@/lib/format";

type SummaryCardProps = {
  title: string;
  stats: StrategyStats;
  accent: "green" | "ink";
  description?: string;
  eyebrow?: string;
};

export function SummaryCard({ title, stats, accent, description, eyebrow }: SummaryCardProps) {
  const accentClass = accent === "green" ? "text-emerald-600" : "text-slate-950";
  const borderClass = accent === "green" ? "border-emerald-200 bg-white" : "border-slate-200 bg-white";
  const backingLabel = formatBackingLabel(stats);

  return (
    <section className={`rounded-lg border px-5 py-6.5 shadow-soft ${borderClass}`}>
      <div className="flex items-start justify-between gap-4">
        <div>
          {eyebrow ? <p className="pt-0.5 text-[11px] font-bold text-muted">{eyebrow}</p> : null}
          <h2 className="mt-1 text-[22px] font-black leading-tight text-ink">{title}</h2>
          {description ? <p className="mt-3 max-w-[44ch] text-[11px] font-semibold leading-5 text-muted">{description}</p> : null}
        </div>
        <span className="pt-1 text-[11px] font-bold text-muted">{backingLabel}</span>
      </div>

      <div className="mt-6 flex items-end gap-3 border-b border-slate-200 pb-5">
        <p className={`text-4xl font-black tracking-normal ${accentClass}`}>{formatPct(stats.winRate)}</p>
        <p className="pb-1 text-xs font-bold text-muted">Win rate</p>
      </div>

      <div className="mt-6 grid grid-cols-2 gap-4 pb-1">
        <Metric label="Avg Return (per trade)" value={formatPct(stats.avgReturnPct, true)} positive />
        <Metric label="Worst Drawdown" value={formatPct(stats.worstDrawdownProxy, true)} danger />
      </div>
    </section>
  );
}

function formatBackingLabel(stats: StrategyStats) {
  const parts: string[] = ["Past 30 days"];

  if (stats.sampleSize !== null && stats.sampleSize !== undefined) {
    parts.push(`${formatNumber(stats.sampleSize)} trades`);
  }

  if (stats.tickerCount !== null && stats.tickerCount !== undefined) {
    parts.push(`${formatNumber(stats.tickerCount)} tickers`);
  }

  return parts.join(" | ") || "Benchmark backing";
}

function Metric({
  label,
  value,
  positive,
  danger
}: {
  label: string;
  value: string;
  positive?: boolean;
  danger?: boolean;
}) {
  return (
    <div>
      <p className="text-[11px] font-bold text-muted">{label}</p>
      <p className={`mt-2 text-[28px] leading-none font-black ${positive ? "text-emerald-600" : ""} ${danger ? "text-red-600" : ""}`}>
        {value}
      </p>
    </div>
  );
}
