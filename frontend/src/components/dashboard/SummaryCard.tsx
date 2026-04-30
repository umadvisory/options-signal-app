"use client";

import type { StrategyStats } from "@/types/dashboard";
import { formatNumber, formatPct } from "@/lib/format";
import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

type SummaryCardProps = {
  title: string;
  stats: StrategyStats;
  accent: "green" | "ink";
  description?: string;
  eyebrow?: string;
  interpretationLabel?: string;
  benchmarkContext?: string;
  winRateContext?: string;
  avgReturnLabel?: string;
  avgReturnContext?: string;
  chartContext?: string;
};

export function SummaryCard({
  title,
  stats,
  accent,
  description,
  eyebrow,
  interpretationLabel,
  benchmarkContext,
  winRateContext,
  avgReturnLabel,
  avgReturnContext,
  chartContext
}: SummaryCardProps) {
  const accentClass = accent === "green" ? "text-emerald-600" : "text-slate-950";
  const borderClass = accent === "green" ? "border-emerald-200 bg-white" : "border-slate-200 bg-white";
  const backingLabel = formatBackingLabel(stats);
  const sampleSize = stats.sampleSize ?? 0;
  const distribution = (stats.returnDistribution ?? []).map((bucket) => ({
    ...bucket,
    count: Number(bucket.count) || 0,
    percentage:
      bucket.percentage === null || bucket.percentage === undefined
        ? sampleSize
          ? roundToOneDecimal(((Number(bucket.count) || 0) / sampleSize) * 100)
          : 0
        : Number(bucket.percentage) || 0
  }));
  const derivedLossRate = roundToOneDecimal(
    distribution
      .filter((bucket) => ["<-50%", "-50%–0%"].includes(bucket.range))
      .reduce((sum, bucket) => sum + bucket.percentage, 0)
  );
  const derivedLargeLossRate = roundToOneDecimal(
    distribution
      .filter((bucket) => bucket.range === "<-50%")
      .reduce((sum, bucket) => sum + bucket.percentage, 0)
  );
  const lossRate = stats.lossRate ?? derivedLossRate;
  const largeLossRate = stats.largeLossRate ?? derivedLargeLossRate;
  const displayedWinRate = roundToOneDecimal(Number(stats.winRate ?? 0));
  const displayedLossRate = roundToOneDecimal(100 - displayedWinRate);

  return (
    <section className={`rounded-lg border px-5 py-6.5 shadow-soft ${borderClass}`}>
      <div className="flex items-start justify-between gap-4">
        <div>
          {eyebrow ? <p className="pt-0.5 text-[11px] font-bold text-muted">{eyebrow}</p> : null}
          {eyebrow && benchmarkContext ? (
            <p className="mt-1 text-[11px] font-semibold text-slate-500">
              {benchmarkContext}
            </p>
          ) : null}
          <h2 className="mt-1 text-[22px] font-black leading-tight text-ink">{title}</h2>
          {description ? <p className="mt-3 max-w-[44ch] text-[11px] font-semibold leading-5 text-muted">{description}</p> : null}
        </div>
        <span className="pt-1 text-[11px] font-bold text-muted">{backingLabel}</span>
      </div>

      <div className="mt-6 flex items-end gap-3 border-b border-slate-200 pb-5">
        <p className={`text-4xl font-black tracking-normal ${accentClass}`}>{formatPct(displayedWinRate)}</p>
        <p className="pb-1 text-xs font-bold text-muted">
          Win rate
          {winRateContext ? <span className="ml-1 font-semibold text-slate-400">({winRateContext})</span> : null}
        </p>
      </div>
      {interpretationLabel ? (
        <p className="mt-2 text-[11px] font-semibold text-slate-500">{interpretationLabel}</p>
      ) : null}

      <div className="mt-6 grid grid-cols-2 gap-4 pb-1">
        <Metric
          label={avgReturnLabel ?? "Avg Return (per trade)"}
          value={formatPct(stats.avgReturnPct, true)}
          positive
          context={avgReturnContext ?? null}
        />
        <LossProfile lossRate={displayedLossRate} largeLossRate={largeLossRate} />
      </div>

      <div className="mt-6">
        <p className="text-[11px] font-bold text-muted">Trade Outcome Profile</p>
        <p className="mt-1 text-[11px] text-muted">{chartContext ?? "Distribution of trade outcomes (last 30 days)"}</p>
        <div className="mt-2 h-40 rounded-md border border-slate-100 bg-slate-50/50 px-2 py-2">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={distribution} margin={{ top: 4, right: 4, left: -20, bottom: 16 }} barCategoryGap="20%">
              <CartesianGrid vertical={false} stroke="#e2e8f0" strokeDasharray="2 3" strokeOpacity={0.35} />
              <XAxis
                dataKey="range"
                tick={{ fontSize: 9, fill: "#64748b" }}
                interval={0}
                angle={-22}
                textAnchor="end"
                height={42}
              />
              <YAxis tick={{ fontSize: 10, fill: "#9ca3af" }} axisLine={false} tickLine={false} width={26} />
              <Tooltip cursor={{ fill: "rgba(148, 163, 184, 0.08)" }} content={<DistributionTooltip />} />
              <Bar dataKey="count" minPointSize={2} maxBarSize={44} radius={[4, 4, 0, 0]} isAnimationActive={false}>
                {distribution.map((bucket, index) => (
                  <Cell key={`${bucket.range}-${index}`} fill={bucket.range === "<-50%" || bucket.range === "-50%–0%" ? "#ef4444" : "#10b981"} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
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
  danger,
  context
}: {
  label: string;
  value: string;
  positive?: boolean;
  danger?: boolean;
  context?: string | null;
}) {
  return (
    <div>
      <p className="text-[11px] font-bold text-muted">{label}</p>
      {context ? <p className="mt-1 text-[11px] font-semibold text-slate-400">{context}</p> : null}
      <p className={`mt-2 text-[28px] leading-none font-black ${positive ? "text-emerald-600" : ""} ${danger ? "text-red-600" : ""}`}>
        {value}
      </p>
    </div>
  );
}

function LossProfile({
  lossRate,
  largeLossRate
}: {
  lossRate: number | null | undefined;
  largeLossRate: number | null | undefined;
}) {
  return (
    <div>
      <p className="text-[11px] font-bold text-muted">Loss Profile</p>
      <p className="mt-2 text-sm font-semibold text-ink">{formatPct(lossRate)} non-winning trades</p>
      <p className="mt-1 text-sm font-semibold text-muted">{formatPct(largeLossRate)} of trades were large losses (&gt;30%), included above</p>
    </div>
  );
}

function DistributionTooltip({
  active,
  payload
}: {
  active?: boolean;
  payload?: Array<{ payload?: { range?: string; count?: number; percentage?: number } }>;
}) {
  if (!active || !payload?.length || !payload[0]?.payload) return null;

  const data = payload[0].payload;

  return (
    <div className="rounded-md bg-slate-900 px-2.5 py-1.5 text-xs text-white shadow-lg">
      <div>{data.range}</div>
      <div>
        <strong>{formatNumber(data.count ?? 0)}</strong> trades
      </div>
      <div>{formatPct(data.percentage ?? 0)}</div>
    </div>
  );
}

function roundToOneDecimal(value: number) {
  return Math.round(value * 10) / 10;
}
