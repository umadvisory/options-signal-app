import { formatPct } from "@/lib/format";
import type { MarketRegime } from "@/types/dashboard";

export function MarketRegimeStrip({ regime }: { regime: MarketRegime | null }) {
  if (!regime) {
    return (
      <section className="rounded-lg border border-slate-200 bg-white px-6 py-5 shadow-soft">
        <div className="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="text-xs font-bold text-muted">Market Regime</p>
            <h2 className="mt-1 text-lg font-black text-ink">Macro context unavailable</h2>
          </div>
          <p className="text-xs font-semibold text-muted">Signals still load from the live trade API.</p>
        </div>
      </section>
    );
  }

  const posture = buildTradingPosture(regime);

  return (
    <section className="rounded-lg border border-blue-200 bg-white px-6 py-5 shadow-soft">
      <div className="flex flex-col gap-5 xl:flex-row xl:items-start xl:justify-between">
        <div className="max-w-2xl">
          <p className="text-xs font-bold text-muted">Market Regime</p>
          <div className="mt-1 flex flex-wrap items-center gap-3">
            <h2 className="text-[30px] font-black leading-none text-ink">{regime.regime}</h2>
            <span className={badgeClass(regime.risk.shockDay)}>{regime.risk.shockDay ? "Elevated Event Risk" : "Low Event Risk"}</span>
          </div>
          <p className="mt-3 max-w-xl text-sm font-semibold leading-6 text-muted">{posture.contextLine}</p>
          <p className="mt-2 max-w-xl text-sm font-black leading-6 text-ink">{posture.actionLine}</p>
        </div>

        <div className="grid gap-3 sm:grid-cols-2 xl:min-w-[500px] xl:grid-cols-4">
          <MacroMetric
            label="VIX"
            value={regime.vix.level?.toFixed(1) ?? "N/A"}
            sublabel={regime.vix.label}
            tooltip="Measures market volatility. Higher values usually imply higher option premiums and risk."
          />
          <MacroMetric
            label="SPY 5D"
            value={formatPct(regime.spy.trend5d, true)}
            sublabel={regime.spy.trendLabel}
            tooltip="Short-term S&P 500 trend over the last five trading days."
          />
          <MacroMetric
            label="Vol %ile"
            value={formatPct(regime.vix.percentile)}
            sublabel="Relative range"
            tooltip="Current volatility level compared with recent historical range."
          />
          <MacroMetric
            label="As Of"
            value={formatDate(regime.date)}
            sublabel="Macro snapshot"
            tooltip="Date of the market regime snapshot."
          />
        </div>
      </div>
    </section>
  );
}

function buildTradingPosture(regime: MarketRegime) {
  const vixLevel = regime.vix.level ?? null;
  const spyTrend5d = regime.spy.trend5d ?? null;
  const shockDay = Boolean(regime.risk.shockDay);

  const supportiveTrend = spyTrend5d !== null && spyTrend5d > 0;
  const trendNotSupportive = spyTrend5d !== null && spyTrend5d <= 0;

  let contextLine = "Moderate volatility - expect mixed conditions";
  let actionLine = "Be selective; prioritize strongest setups only";

  if (vixLevel !== null && vixLevel < 20 && supportiveTrend) {
    contextLine = "Low-to-moderate volatility with supportive trend";
    actionLine = "Favor directional call setups; avoid chasing extended momentum";
  } else if (vixLevel !== null && vixLevel > 30) {
    contextLine = "High volatility - unstable trading environment";
    actionLine = "Reduce exposure; avoid aggressive entries";
  } else if (vixLevel !== null && vixLevel >= 20 && vixLevel <= 30) {
    contextLine = "Moderate volatility - expect mixed conditions";
    actionLine = "Be selective; prioritize strongest setups only";
  }

  if (trendNotSupportive) {
    contextLine = `${contextLine}. Trend not supportive`;
    actionLine = "Reduce directional exposure; wait for confirmation";
  }

  if (shockDay) {
    contextLine = `${contextLine}. Elevated event risk`;
  }

  return { contextLine, actionLine };
}

function MacroMetric({ label, value, sublabel, tooltip }: { label: string; value: string; sublabel: string; tooltip?: string }) {
  return (
    <div className="rounded-md border border-slate-200 bg-slate-50 px-3.5 py-3" title={tooltip} aria-label={tooltip}>
      <p
        className={`text-[10px] font-bold tracking-[0.04em] text-muted ${tooltip ? "cursor-help underline decoration-dotted underline-offset-2" : ""}`}
        title={tooltip}
        aria-label={tooltip}
      >
        {label}
      </p>
      <p className="mt-1.5 text-[28px] font-black leading-none text-ink">{value}</p>
      <p className="mt-1 text-[11px] font-semibold text-muted">{sublabel}</p>
    </div>
  );
}

function badgeClass(shockDay: boolean) {
  const base = "inline-flex h-8 items-center rounded-md px-3 text-[11px] font-black uppercase";
  if (shockDay) return `${base} bg-red-100 text-red-700 ring-1 ring-red-200`;
  return `${base} bg-emerald-100 text-emerald-700 ring-1 ring-emerald-200`;
}

function formatDate(value: string | null) {
  if (!value) return "N/A";
  const parsed = new Date(`${value}T00:00:00`);
  if (Number.isNaN(parsed.getTime())) return value;

  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric"
  }).format(parsed);
}
