import { formatPct } from "@/lib/format";
import type { MarketRegime } from "@/types/dashboard";

export function MarketRegimeStrip({
  regime,
  insight,
  leadingTicker
}: {
  regime: MarketRegime | null;
  insight?: string | null;
  leadingTicker?: string | null;
}) {
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

  const displayRegime = regime.regime === "Neutral-to-Supportive" ? "Neutral \u2192 Slightly Supportive" : regime.regime;
  const regimeMode = resolveRegimeMode(regime);
  const contextLine = resolveContextLine(regime);
  const actionLine = resolveActionLine(regimeMode);
  const opportunityLine = leadingTicker
    ? `Clean setups exist - focus on top-ranked names (${leadingTicker} leading).`
    : "Clean setups exist - focus on top-ranked names.";

  return (
    <section className="rounded-lg border border-blue-200 bg-white px-6 py-5 shadow-soft">
      <div className="flex flex-col gap-5 xl:flex-row xl:items-start xl:justify-between">
        <div className="max-w-2xl">
          <p className="text-xs font-bold text-muted">Market Regime</p>
          <h2 className="mt-1 text-[30px] font-black leading-none text-ink">{displayRegime}</h2>
          <div className="mt-2 flex flex-wrap items-center gap-2">
            <p className={modeClass(regimeMode)}>{regimeMode}</p>
            <span className={badgeClass(regime.risk.shockDay)}>{regime.risk.shockDay ? "Elevated macro event risk" : "Stable event backdrop"}</span>
          </div>
          <p className="mt-3 max-w-xl text-sm leading-6 text-muted">{contextLine}</p>
          <p className="mt-2 max-w-xl text-base font-black leading-6 text-ink">{actionLine}</p>
          <p className="mt-2 max-w-xl text-sm leading-6 text-slate-700">{opportunityLine}</p>
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

function resolveRegimeMode(regime: MarketRegime) {
  const regimeLabel = (regime.regime || "").toLowerCase();
  if (regimeLabel.includes("risk-off")) return "Defensive Mode";
  if (regimeLabel.includes("cautious")) return "Cautious Mode";
  if (regimeLabel.includes("supportive")) return "Opportunity Mode";
  return "Balanced Mode";
}

function resolveContextLine(regime: MarketRegime) {
  const volPct = regime.vix.percentile;
  const summary = (regime.summary || "").trim();
  if (summary) return summary;
  if (volPct == null) return "Macro conditions are mixed.";
  if (volPct >= 70) return "Elevated volatility. Conditions are unstable.";
  if (volPct >= 40) return "Moderate volatility. Mixed conditions.";
  return "Calmer volatility backdrop. Conditions are improving.";
}

function resolveActionLine(mode: string) {
  if (mode === "Defensive Mode") return "Protect capital first. Avoid heavy directional exposure.";
  if (mode === "Cautious Mode") return "Wait for confirmation. Avoid heavy directional exposure.";
  if (mode === "Opportunity Mode") return "Prioritize clean entries. Add exposure selectively.";
  return "Stay selective. Focus on high-quality execution.";
}

function modeClass(mode: string) {
  const base = "inline-flex rounded-sm px-2.5 py-0.5 text-xs font-black";
  if (mode === "Defensive Mode") return `${base} bg-red-100 text-red-800`;
  if (mode === "Cautious Mode") return `${base} bg-amber-100 text-amber-800`;
  if (mode === "Opportunity Mode") return `${base} bg-emerald-100 text-emerald-800`;
  return `${base} bg-slate-200 text-slate-700`;
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
  const base = "inline-flex h-7 items-center rounded-md px-2.5 text-[10px] font-semibold";
  if (shockDay) return `${base} bg-red-50 text-red-700 ring-1 ring-red-100`;
  return `${base} bg-slate-100 text-slate-600 ring-1 ring-slate-200`;
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
