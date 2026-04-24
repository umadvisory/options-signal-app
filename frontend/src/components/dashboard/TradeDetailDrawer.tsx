"use client";

import { ActionBadge, TierBadge } from "@/components/ui/Badge";
import { formatCurrency, formatExpiry, formatNumber, formatPct } from "@/lib/format";
import type { MarketRegime, TopTrade } from "@/types/dashboard";

export function TradeDetailDrawer({
  trade,
  marketRegime,
  isWatched = false,
  onToggleWatchlist,
  onClose
}: {
  trade: TopTrade | null;
  marketRegime?: MarketRegime | null;
  isWatched?: boolean;
  onToggleWatchlist?: (trade: TopTrade) => void;
  onClose: () => void;
}) {
  if (!trade) return null;

  const conviction = getConvictionLabel(trade);
  const tradeability = getTradeabilityLabel(trade);
  const entryPosture = getEntryPosture(trade);
  const decisionState = getDecisionState(trade);
  const decisionContext = trade.decisionContext;
  const checks = [
    ["Tradeable contract", trade.execution.liveEligible],
    ["Liquidity screen", trade.risk.liquidityOk],
    ["Open interest", trade.risk.openInterestOk],
    ["Volume", trade.risk.volumeOk],
    ["Expiry window", trade.risk.dteOk],
    ["Market trend", trade.risk.spyTrendOk],
    ["Quote sanity", trade.risk.bidOk]
  ];

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-slate-950/30 backdrop-blur-sm" role="dialog" aria-modal="true">
      <button className="absolute inset-0 cursor-default" type="button" onClick={onClose} aria-label="Close trade details" />
      <aside className="relative flex h-full w-full max-w-2xl flex-col overflow-y-auto bg-white shadow-2xl">
        <header className="sticky top-0 z-10 border-b border-slate-200 bg-white px-6 py-5">
          <div className="flex items-start justify-between gap-4">
            <div>
              <div className="flex flex-wrap items-center gap-2">
                <h2 className="text-4xl font-black tracking-tight text-ink">{trade.ticker}</h2>
                <TierBadge tier={trade.tier} />
                <ActionBadge action={decisionState.action} />
              </div>
              <p className="mt-2 text-sm font-semibold text-muted">{trade.companyName || trade.contract.optionSymbol}</p>
            </div>
            <div className="flex items-center gap-2">
              {onToggleWatchlist ? (
                <button
                  type="button"
                  onClick={() => onToggleWatchlist(trade)}
                  className={`inline-flex h-10 items-center justify-center rounded-md border px-4 text-xs font-black transition ${
                    isWatched
                      ? "border-amber-200 bg-amber-50 text-amber-700"
                      : "border-slate-200 bg-white text-slate-700 hover:border-amber-300 hover:text-amber-700"
                  }`}
                >
                  {isWatched ? "Saved" : "Watch"}
                </button>
              ) : null}
              <button
                type="button"
                onClick={onClose}
                className="flex h-10 w-10 items-center justify-center rounded-md border border-slate-200 text-xl font-black text-muted transition hover:border-blue-300 hover:text-blue-700"
              >
                x
              </button>
            </div>
          </div>
        </header>

        <div className="space-y-6 px-6 py-5">
          <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
            <Metric label="Action" value={decisionState.action} detail={decisionState.explanation} tone={decisionState.tone} emphasize />
            <Metric label="Rank" value={`#${trade.rank}`} tone="blue" emphasize />
            <Metric label="Entry posture" value={entryPosture.label} detail={entryPosture.note} tone={entryPosture.tone} emphasize />
            <Metric label="Tradeability" value={tradeability} />
            <Metric label="Structure" value={`${trade.contract.strikePositionLabel} ${trade.optionType}`} />
          </section>

          {decisionContext ? (
            <section className="rounded-lg border border-emerald-200 bg-emerald-50 p-5">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <p className="text-[11px] font-black uppercase tracking-[0.14em] text-emerald-700">Why This Trade Made The Cut</p>
                  <h3 className="mt-2 text-xl font-black text-ink">
                    {trade.ticker} - {trade.tier} Setup
                  </h3>
                </div>
                <div className="rounded-md bg-white/80 px-3 py-2 text-right">
                  <p className="text-[10px] font-black uppercase tracking-[0.12em] text-muted">Translation</p>
                  <p className="mt-1 text-sm font-bold text-ink">{decisionContext.translation || buildSummary(trade)}</p>
                </div>
              </div>

              <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
                <CutStat
                  label="Today Rank"
                  value={
                    decisionContext.today.rank && decisionContext.today.candidateCount
                      ? `#${decisionContext.today.rank} of ${decisionContext.today.candidateCount}`
                      : `#${trade.rank}`
                  }
                  sublabel="Live rank inside today's qualified list"
                />
                <CutStat
                  label="Historical Support"
                  value={decisionContext.historical.supportLabel || "Limited"}
                  sublabel={
                    decisionContext.historical.winRate !== null && decisionContext.historical.winRate !== undefined
                      ? `${decisionContext.historical.winRate}% win rate · ${decisionContext.historical.sampleSize || 0} trades/${decisionContext.historical.windowDays || 365} days`
                      : "Not enough clean comparables yet"
                  }
                />
                <CutStat
                  label="Typical Hold"
                  value={decisionContext.expectation.timeframe || "N/A"}
                  sublabel={
                    decisionContext.historical.avgRMultiple !== null && decisionContext.historical.avgRMultiple !== undefined
                      ? `Avg return ${decisionContext.historical.avgRMultiple > 0 ? "+" : ""}${decisionContext.historical.avgRMultiple}R (= ${decisionContext.historical.avgRMultiple > 0 ? "+" : ""}${Math.round(
                          decisionContext.historical.avgRMultiple * 100
                        )}% of risk per trade)`
                      : "Expectation frame"
                  }
                />
              </div>

              <div className="mt-4 grid gap-4 lg:grid-cols-3">
                <ExecutionColumn title="Execution Edge" tone="green" items={decisionContext.executionEdge} />
                <ExecutionColumn title="Skip Conditions" tone="amber" items={decisionContext.invalidation} />
                <ExpectationPanel
                  timeframe={decisionContext.expectation.timeframe}
                  baseCase={decisionContext.expectation.baseCase}
                  risk={decisionContext.expectation.risk}
                />
              </div>
            </section>
          ) : (
            <section className="grid gap-4 lg:grid-cols-[minmax(0,1.2fr)_minmax(260px,0.8fr)]">
              <section className="rounded-lg border border-emerald-200 bg-emerald-50 p-4">
                <h3 className="text-sm font-black text-ink">Decision Note</h3>
                <p className="mt-2 text-sm font-semibold leading-6 text-slate-700">{buildSummary(trade)}</p>
              </section>

              <section className="rounded-lg border border-slate-200 p-4">
                <h3 className="text-sm font-black text-ink">Decision</h3>
                <p className="mt-2 text-sm font-semibold leading-6 text-slate-700">{buildActionRationale(trade)}</p>
              </section>
            </section>
          )}

          <section className="rounded-lg border border-slate-200 bg-slate-50 p-4">
            <h3 className="text-sm font-black text-ink">Contract</h3>
            <div className="mt-3 grid gap-3 sm:grid-cols-3">
              <Metric label="Type" value={trade.optionType} />
              <Metric label="Strike" value={formatCurrency(trade.contract.strike)} />
              <Metric label="Expiry" value={`${formatExpiry(trade.contract.expiry)} / ${trade.contract.dte}d`} />
              <Metric label="Spot" value={formatCurrency(trade.contract.underlyingPrice)} />
              <Metric label="Position" value={trade.contract.strikePositionLabel} />
              <Metric label="Distance" value={trade.contract.strikePositionText} />
            </div>
            <p className="mt-3 text-xs font-semibold text-muted">
              Premiums move quickly. Confirm the live bid/ask before entering any contract.
            </p>
          </section>

          <details className="group rounded-lg border border-slate-200 bg-slate-50">
            <summary className="flex cursor-pointer list-none items-center justify-between gap-4 px-4 py-4">
              <div>
                <h3 className="text-sm font-black text-ink">View Trade Plan</h3>
                <p className="mt-1 text-[11px] font-semibold text-muted">Lower-cost idea, execution notes, and risk checks.</p>
              </div>
              <span className="text-xs font-black text-blue-700 transition group-open:rotate-180">⌄</span>
            </summary>

            <div className="space-y-4 border-t border-slate-200 px-4 py-4">
              <p className="text-[11px] font-semibold leading-5 text-slate-500">
                Model-driven idea. Confirm pricing, liquidity, and suitability before trading.
              </p>

              <section className="rounded-lg border border-violet-200 bg-violet-50 p-4">
                <h3 className="text-sm font-black text-ink">Lower-Cost Idea</h3>
                <p className="mt-2 text-sm font-semibold leading-6 text-slate-700">{buildLowerCostIdea(trade)}</p>
                {buildSpreadSketch(trade) ? (
                  <div className="mt-3 rounded-md border border-violet-200 bg-white px-4 py-3">
                    <p className="text-[11px] font-bold text-muted">Modeled same-expiry spread</p>
                    <div className="mt-2 space-y-1">
                      <p className="text-sm font-black text-ink">{buildSpreadSketch(trade)?.buyLine}</p>
                      <p className="text-sm font-black text-ink">{buildSpreadSketch(trade)?.sellLine}</p>
                    </div>
                    <p className="mt-2 text-[11px] font-semibold text-muted">{buildSpreadSketch(trade)?.note}</p>
                    {buildSpreadSketch(trade)?.caution ? (
                      <p className="mt-1 text-[11px] font-semibold text-amber-700">{buildSpreadSketch(trade)?.caution}</p>
                    ) : null}
                  </div>
                ) : null}
                <ul className="mt-3 space-y-2 text-sm font-semibold text-slate-700">
                  {buildLowerCostChecklist(trade).map((item) => (
                    <li key={item} className="flex gap-2">
                      <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-violet-600" />
                      <span>{item}</span>
                    </li>
                  ))}
                </ul>
                <p className="mt-3 text-[11px] font-semibold leading-5 text-muted">
                  Capital-efficiency idea only. Confirm the live option chain before choosing strikes or entering any spread.
                </p>
              </section>

              {trade.executionGuidance ? (
                <section className="rounded-lg border border-slate-200 bg-white p-4">
                  <h3 className="text-sm font-black text-ink">Execution Notes</h3>
                  <div className="mt-3 grid gap-3 sm:grid-cols-3">
                    <ExecutionColumn title="Favorable" tone="green" items={trade.executionGuidance.favorable} />
                    <ExecutionColumn title="Caution" tone="amber" items={trade.executionGuidance.caution} />
                    <ExecutionColumn title="Unfavorable" tone="slate" items={trade.executionGuidance.unfavorable} />
                  </div>
                </section>
              ) : null}

              <section className="rounded-lg border border-blue-200 bg-blue-50 p-4">
                <h3 className="text-sm font-black text-ink">Risk Notes</h3>
                <ul className="mt-3 space-y-2 text-sm font-semibold text-slate-700">
                  {buildBeforeActChecklist(trade).map((item) => (
                    <li key={item} className="flex gap-2">
                      <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-blue-600" />
                      <span>{item}</span>
                    </li>
                  ))}
                </ul>
              </section>

              <section className="rounded-lg border border-slate-200 bg-white p-4">
                <h3 className="text-sm font-black text-ink">Tradeability Checks</h3>
                <div className="mt-3 grid gap-2 sm:grid-cols-2">
                  {checks.map(([label, passed]) => (
                    <div key={String(label)} className="flex items-center justify-between rounded-md bg-slate-50 px-3 py-2">
                      <span className="text-xs font-black text-ink">{label}</span>
                      <span className={`text-xs font-black ${passed ? "text-emerald-600" : "text-slate-400"}`}>
                        {passed === null ? "N/A" : passed ? "PASS" : "CHECK"}
                      </span>
                    </div>
                  ))}
                </div>
                {getCustomerReason(trade.execution.failReason) ? (
                  <p className="mt-3 rounded-md bg-amber-50 px-3 py-2 text-[11px] font-bold text-amber-800">
                    {getCustomerReason(trade.execution.failReason)}
                  </p>
                ) : null}
              </section>
            </div>
          </details>

          <section className="grid gap-4 sm:grid-cols-2">
            <InfoPanel
              title="Market Context"
              rows={[
                ["Sector", trade.context.sector],
                ["ETF", `${trade.etfOverlay.etf} / ${trade.etfOverlay.bias}`],
                ["Macro", marketRegime?.regime || "N/A"],
                ["Recent hit rate", formatPct(trade.etfOverlay.winRate4d)],
                ["Participation", formatNumber(trade.etfOverlay.breadth)]
              ]}
            />
            <InfoPanel
              title="Setup Profile"
              rows={[
                ["Conviction", conviction],
                ["Tradeability", tradeability],
                ["Signal", trade.signalStrength === "UNKNOWN" ? trade.action : trade.signalStrength],
                ["Market Regime", trade.classification.vixBucket || "Normal"]
              ]}
            />
          </section>

          <section className="rounded-lg border border-slate-200 bg-slate-50 p-4">
            <h3 className="text-sm font-black text-ink">Freshness</h3>
            <p className="mt-2 text-xs font-semibold leading-5 text-muted">
              Latest signal run: {formatFreshness(trade.provenance.runTimestamp || trade.provenance.signalDate)}.
              Use this as a decision-support signal, not an execution quote.
            </p>
          </section>
        </div>
      </aside>
    </div>
  );
}

function getConvictionLabel(trade: TopTrade) {
  if (trade.action === "ENTER" && trade.tier === "A+") return "Very High";
  if (trade.action === "ENTER") return "High";
  if (trade.tier === "A" || trade.tier === "A-") return "Medium-High";
  return "Medium";
}

function getTradeabilityLabel(trade: TopTrade) {
  const checks = [
    trade.execution.liveEligible,
    trade.risk.liquidityOk,
    trade.risk.openInterestOk,
    trade.risk.volumeOk,
    trade.risk.dteOk
  ];
  const passed = checks.filter(Boolean).length;

  if (passed >= 4) return "Passed";
  if (passed >= 2) return "Review";
  return "Check Live";
}

function buildSummary(trade: TopTrade) {
  const decision = getDecisionState(trade);

  const actionCall =
    decision.action === "ENTER"
      ? "Entry candidate if pricing stays clean."
      : decision.action === "WATCH"
        ? "Qualified, but wait for a cleaner entry."
        : "Valid setup, but extension argues for patience over chasing.";

  const structure = `${trade.contract.strikePositionLabel} ${trade.optionType.toLowerCase()}, ${trade.contract.dte}DTE.`;

  const backdrop =
    trade.etfOverlay.bias && trade.etfOverlay.bias !== "Neutral" && trade.etfOverlay.bias !== "No overlay"
      ? `${trade.etfOverlay.etf} backdrop: ${trade.etfOverlay.bias.toLowerCase()}.`
      : trade.etfOverlay.bias === "No overlay"
        ? `${trade.etfOverlay.etf}: no live overlay.`
        : "Sector backdrop: neutral.";

  const tapeNote =
    trade.context.rsi >= 70
      ? "Avoid chasing after strength."
      : trade.context.rsi <= 45
        ? "Needs momentum confirmation."
        : "Momentum looks workable.";

  return `${actionCall} ${structure} ${backdrop} ${tapeNote}`;
}

function getActionLabel(trade: TopTrade) {
  if (trade.action === "PASS") return "Review";
  return trade.action.charAt(0) + trade.action.slice(1).toLowerCase();
}

function buildActionRationale(trade: TopTrade) {
  const decision = getDecisionState(trade);

  if (decision.action === "ENTER") {
    return "Higher-priority candidate. Take it only if live quote and depth still look clean.";
  }

  if (decision.action === "WATCH") {
    return "Worth tracking. Prefer confirmation and a better entry over forcing it.";
  }

  return "The setup is still valid, but extension makes a fresh entry less attractive right now.";
}

function buildBeforeActChecklist(trade: TopTrade) {
  const decision = getDecisionState(trade);
  const checklist = [
    "Confirm the live bid/ask and avoid stale quotes.",
    "Avoid chasing if the underlying has moved sharply since the snapshot.",
    "Size the trade so a full premium loss is acceptable.",
    "Check for earnings, major news, or market-moving events before entry."
  ];

  if (decision.action !== "ENTER") {
    checklist.unshift("Treat this as a monitor/review candidate unless live conditions improve.");
  }

  if (trade.risk.liquidityOk === false || trade.risk.openInterestOk === false || trade.risk.volumeOk === false) {
    checklist.unshift("Re-check contract depth carefully; liquidity may be weaker than preferred.");
  }

  return checklist;
}

function buildLowerCostIdea(trade: TopTrade) {
  const decision = getDecisionState(trade);
  const spread = buildSpreadSketch(trade);
  if (!spread) {
    return "If premium is elevated vs recent levels or IV is high, use the live chain to compare a same-expiry vertical before taking the outright option.";
  }

  if (decision.action === "ENTER") {
    return `If premium is elevated vs recent levels or IV is high, tighten this into a same-expiry ${trade.optionType.toLowerCase()} spread using the current strike as the anchor.`;
  }

  return `If this firms up and premium stays rich, a same-expiry ${trade.optionType.toLowerCase()} spread around this strike can reduce upfront cost without abandoning the setup.`;
}

function buildLowerCostChecklist(trade: TopTrade) {
  const decision = getDecisionState(trade);
  const spread = buildSpreadSketch(trade);
  const widthText = spread ? formatCurrency(spread.width) : "the spread width";
  const checklist = [
    "Reduces upfront cost while keeping directional exposure.",
    "Max profit if price reaches or clears the short strike at expiry.",
    `Caps max profit at ${widthText} per spread.`,
    "Confirm the short strike exists with usable depth on the live chain."
  ];

  if (decision.action !== "ENTER") {
    checklist.unshift("Wait for confirmation before committing to the spread.");
  }

  if (trade.contract.dte <= 21) {
    checklist.push("With shorter-dated contracts, make sure time decay does not overwhelm the spread.");
  }

  checklist.push("Avoid this adjustment if you expect a breakout well beyond the short strike.");

  return checklist;
}

function buildSpreadSketch(trade: TopTrade) {
  const currentStrike = trade.contract.strike;
  if (currentStrike === null || currentStrike === undefined) return null;

  const spot = trade.contract.underlyingPrice;
  if (!spot || spot <= 0) return null;

  const baseWidth = inferSpreadWidth(trade.contract.strike, spot);
  const step = inferStrikeStep(Math.max(currentStrike, spot || currentStrike));
  const maxWidth = Math.min(15, spot * 0.05);
  const structure = trade.contract.strikePositionLabel;
  const distancePct = Math.abs(trade.contract.distanceToStrikePct ?? 0);

  let shortStrike: number | null = null;
  let caution: string | null = null;

  if (trade.optionType === "CALL") {
    if ((structure === "OTM" || structure === "FAR OTM") && distancePct > 8) {
      return null;
    }

    if ((structure === "OTM" || structure === "FAR OTM") && distancePct > 5) {
      caution = "Use cautiously — OTM spreads further reduce probability of payoff.";
    }

    const targetShort = spot * 1.03;
    const minValidShort = roundUpToStep(Math.max(spot * 1.02, currentStrike + step), step);
    const preferredShort = roundUpToStep(Math.max(targetShort, currentStrike + step), step);
    const widthCapShort = roundToStep(currentStrike + maxWidth, step);

    if (preferredShort <= widthCapShort && preferredShort > spot) {
      shortStrike = preferredShort;
    } else if (widthCapShort > spot) {
      shortStrike = roundUpToStep(Math.max(widthCapShort, minValidShort), step);
    } else {
      shortStrike = minValidShort;
      caution = caution
        ? `${caution} Long strike sits deep ITM, so the spread stays wider than usual.`
        : "Long strike sits deep ITM, so the spread stays wider than usual.";
    }

    if (shortStrike <= spot) return null;
  } else {
    shortStrike = currentStrike - baseWidth;
  }

  if (shortStrike === null || shortStrike <= 0) return null;

  return {
    width: roundToStep(Math.abs(shortStrike - currentStrike), step),
    buyLine: `Buy the ${formatCurrency(currentStrike)} ${trade.optionType.toLowerCase()}`,
    sellLine: `Sell the ${formatCurrency(shortStrike)} ${trade.optionType.toLowerCase()} (same expiry)`,
    note:
      trade.optionType === "CALL"
        ? "Short strike set ~2-5% above spot to preserve upside."
        : "Short strike selected below current price to preserve downside.",
    caution
  };
}

function getEntryPosture(trade: TopTrade) {
  const rsi = Number.isFinite(trade.context.rsi) ? trade.context.rsi : 0;
  const distancePct = Math.abs(Number.isFinite(trade.contract.distanceToStrikePct) ? trade.contract.distanceToStrikePct : 0);
  const rsiScore = rsi < 60 ? 0.9 : rsi <= 78 ? 0.55 : 0.15;
  const distanceScore = Math.min(1, Math.max(0, 1 - distancePct / 15));
  const entryScore = Number((rsiScore * 0.6 + distanceScore * 0.4).toFixed(2));

  if (rsi > 78 || entryScore < 0.35) {
    return {
      label: "Wait",
      note: "Momentum extended",
      tone: "red" as const
    };
  }

  if (entryScore >= 0.6) {
    return {
      label: "Favorable",
      note: "Not extended",
      tone: "green" as const
    };
  }

  return {
    label: "Caution",
    note: "Timing not ideal",
    tone: "amber" as const
  };
}

function getDecisionState(trade: TopTrade) {
  const posture = getEntryPosture(trade);

  if (posture.label === "Favorable") {
    return {
      action: "ENTER",
      explanation: "Good entry zone",
      tone: "green" as const
    } as const;
  }

  if (posture.label === "Wait") {
    return {
      action: "WAIT",
      explanation: "Momentum extended — wait",
      tone: "red" as const
    } as const;
  }

  return {
    action: "WATCH",
    explanation: "Setup valid, timing not ideal",
    tone: "amber" as const
  } as const;
}

function inferSpreadWidth(strike: number, underlyingPrice: number) {
  const anchor = Math.max(strike, underlyingPrice || strike);
  const rawWidth = anchor * 0.05;
  const rounded = Math.round(rawWidth / 5) * 5;
  return Math.min(25, Math.max(5, rounded));
}

function inferStrikeStep(anchor: number) {
  if (anchor >= 200) return 5;
  if (anchor >= 100) return 2.5;
  if (anchor >= 25) return 1;
  return 0.5;
}

function roundToStep(value: number, step: number) {
  const rounded = Math.round(value / step) * step;
  return Number(rounded.toFixed(step < 1 ? 2 : 1));
}

function roundUpToStep(value: number, step: number) {
  const rounded = Math.ceil(value / step) * step;
  return Number(rounded.toFixed(step < 1 ? 2 : 1));
}

function getCustomerReason(reason: string | null) {
  if (!reason) return null;

  const normalized = reason.trim().toLowerCase();
  if (normalized === "ok_base" || normalized === "ok" || normalized === "base") {
    return null;
  }

  return reason
    .replaceAll("_", " ")
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

function formatFreshness(value: string | null) {
  if (!value) return "latest available";

  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;

  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit"
  }).format(parsed);
}

function Metric({
  label,
  value,
  detail,
  tone = "default",
  emphasize = false
}: {
  label: string;
  value: string;
  detail?: string | null;
  tone?: "default" | "green" | "amber" | "red" | "blue";
  emphasize?: boolean;
}) {
  const tones = {
    default: "border-slate-200 bg-white",
    green: "border-emerald-200 bg-emerald-50",
    amber: "border-amber-200 bg-amber-50",
    red: "border-red-200 bg-red-50",
    blue: "border-blue-200 bg-blue-50"
  };

  return (
    <div className={`rounded-md border px-3 py-3 ${tones[tone]}`}>
      <p className="text-[10px] font-black uppercase tracking-[0.14em] text-muted">{label}</p>
      <p className={`mt-2 font-black text-ink ${emphasize ? "text-base" : "text-sm"}`}>{value}</p>
      {detail ? <p className="mt-1 text-[11px] font-semibold text-muted">{detail}</p> : null}
    </div>
  );
}

function CutStat({ label, value, sublabel }: { label: string; value: string; sublabel: string }) {
  return (
    <div className="rounded-md border border-emerald-200 bg-white/80 px-3 py-3">
      <p className="text-[10px] font-black uppercase tracking-[0.12em] text-muted">{label}</p>
      <p className="mt-2 text-lg font-black text-ink">{value}</p>
      <p className="mt-1 text-xs font-semibold leading-5 text-muted">{sublabel}</p>
    </div>
  );
}

function InfoPanel({ title, rows }: { title: string; rows: [string, string][] }) {
  return (
    <section className="rounded-lg border border-slate-200 p-4">
      <h3 className="text-sm font-black text-ink">{title}</h3>
      <div className="mt-3 space-y-2">
        {rows.map(([label, value]) => (
          <div key={label} className="flex items-center justify-between gap-3 text-xs">
            <span className="font-black text-muted">{label}</span>
            <span className="text-right font-bold text-ink">{value}</span>
          </div>
        ))}
      </div>
    </section>
  );
}

function TrustPanel({
  title,
  items,
  tone
}: {
  title: string;
  items: string[];
  tone: "green" | "blue" | "amber";
}) {
  const tones = {
    green: {
      card: "border-emerald-200 bg-emerald-50",
      dot: "bg-emerald-600"
    },
    blue: {
      card: "border-blue-200 bg-blue-50",
      dot: "bg-blue-600"
    },
    amber: {
      card: "border-amber-200 bg-amber-50",
      dot: "bg-amber-500"
    }
  };

  return (
    <section className={`rounded-lg border p-4 ${tones[tone].card}`}>
      <h3 className="text-sm font-black text-ink">{title}</h3>
      <ul className="mt-3 space-y-2 text-sm font-semibold leading-6 text-slate-700">
        {items.map((item) => (
          <li key={item} className="flex gap-2">
            <span className={`mt-2 h-1.5 w-1.5 shrink-0 rounded-full ${tones[tone].dot}`} />
            <span>{item}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}

function ExecutionColumn({
  title,
  items,
  tone
}: {
  title: string;
  items: string[];
  tone: "green" | "amber" | "slate";
}) {
  const tones = {
    green: { title: "text-emerald-700", dot: "bg-emerald-600", bg: "bg-emerald-50/60" },
    amber: { title: "text-amber-800", dot: "bg-amber-500", bg: "bg-amber-50/70" },
    slate: { title: "text-slate-700", dot: "bg-slate-400", bg: "bg-slate-50" }
  };

  return (
    <div className={`rounded-md border border-slate-200 px-3 py-3 ${tones[tone].bg}`}>
      <p className={`text-[11px] font-black uppercase tracking-[0.12em] ${tones[tone].title}`}>{title}</p>
      {items.length ? (
        <ul className="mt-3 space-y-2 text-sm font-semibold text-slate-700">
          {items.map((item) => (
            <li key={item} className="flex gap-2">
              <span className={`mt-2 h-1.5 w-1.5 shrink-0 rounded-full ${tones[tone].dot}`} />
              <span>{item}</span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="mt-3 text-sm font-semibold text-slate-600">No major red flags on snapshot.</p>
      )}
    </div>
  );
}

function ExpectationPanel({
  timeframe,
  baseCase,
  risk
}: {
  timeframe: string | null;
  baseCase: string | null;
  risk: string | null;
}) {
  return (
    <section className="rounded-lg border border-slate-200 bg-slate-50 p-4">
      <h3 className="text-sm font-black text-ink">Expectation Frame</h3>
      <div className="mt-3 space-y-3 text-sm font-semibold text-slate-700">
        <div>
          <p className="text-[11px] font-black uppercase tracking-[0.12em] text-muted">Expected Window</p>
          <p className="mt-1">{timeframe || "Timeframe still needs live confirmation."}</p>
        </div>
        <div>
          <p className="text-[11px] font-black uppercase tracking-[0.12em] text-muted">Base Case</p>
          <p className="mt-1">{baseCase || "Continuation if the setup stays intact."}</p>
        </div>
        <div>
          <p className="text-[11px] font-black uppercase tracking-[0.12em] text-muted">Main Risk</p>
          <p className="mt-1">{risk || "The edge weakens if the trade stalls."}</p>
        </div>
      </div>
    </section>
  );
}
