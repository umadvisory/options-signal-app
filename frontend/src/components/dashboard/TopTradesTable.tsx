"use client";

import { useMemo, useState } from "react";
import { ActionBadge, Badge, TierBadge } from "@/components/ui/Badge";
import { formatCurrency, formatExpiry, formatNumber } from "@/lib/format";
import type { SectorOutlook, TopTrade, WatchlistItem } from "@/types/dashboard";

export function TopTradesTable({
  trades,
  sectorOutlook = [],
  watchlist = [],
  heroTicker,
  emptyState,
  onToggleWatchlist,
  onSelectTrade
}: {
  trades: TopTrade[];
  sectorOutlook?: SectorOutlook[];
  watchlist?: WatchlistItem[];
  heroTicker?: string | null;
  emptyState?: { title: string; message: string } | null;
  onToggleWatchlist?: (trade: TopTrade) => void;
  onSelectTrade?: (trade: TopTrade) => void;
}) {
  const [showHowToUse, setShowHowToUse] = useState(false);
  const sectorLabelByName = useMemo(() => {
    return new Map(
      sectorOutlook.map((sector) => [sector.sector, classifySector(sector).label] as const)
    );
  }, [sectorOutlook]);

  return (
    <section className="overflow-hidden rounded-lg border border-slate-200 bg-white shadow-soft">
      <div className="border-b border-slate-200 px-5 py-4">
        <div className="flex items-center justify-between gap-4">
          <div>
            <h2 className="text-lg font-black text-ink">
              Qualified Setups <span className="text-sm font-bold text-muted">(from High Conviction)</span>
            </h2>
            <p className="mt-1 text-xs font-semibold text-muted">
              Showing top actionable setups by overall rank.
            </p>
          </div>
          <span className="text-xs font-bold text-muted">{trades.length} visible setups</span>
        </div>

        <div className="mt-2">
          <button
            type="button"
            aria-expanded={showHowToUse}
            aria-controls="qualified-how-to-use"
            onClick={() => setShowHowToUse((current) => !current)}
            className="inline-flex items-center gap-1 text-[11px] font-bold text-slate-600 transition hover:opacity-80 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-300 focus-visible:ring-offset-1"
          >
            <span aria-hidden="true">{showHowToUse ? "▼" : "▶"}</span>
            <span>How to use these setups</span>
          </button>
        </div>
        <div
          id="qualified-how-to-use"
          className={`overflow-hidden transition-all duration-200 ease-out ${showHowToUse ? "mt-2 max-h-64 opacity-100" : "max-h-0 opacity-0"}`}
        >
          <div className="rounded-md border border-slate-200 bg-slate-50 px-3 py-3">
            <p className="text-[11px] font-semibold leading-5 text-slate-600">Focus on top-ranked names.</p>
            <p className="mt-1 text-[11px] font-semibold leading-5 text-slate-600">Use Action to time entry.</p>
            <p className="mt-2 text-[11px] font-black text-ink">ENTER = good timing now</p>
            <p className="mt-1 text-[11px] font-black text-ink">WATCH = valid setup, wait for better entry</p>
            <p className="mt-1 text-[11px] font-black text-ink">WAIT = extended or no clean entry</p>
            <p className="mt-2 text-[11px] font-semibold leading-5 text-slate-600">Rank = priority</p>
            <p className="text-[11px] font-semibold leading-5 text-slate-600">Action = timing</p>
          </div>
        </div>
      </div>

      <div className="thin-scrollbar overflow-x-auto">
        <table className="min-w-[940px] w-full border-collapse text-left">
          <thead>
            <tr className="bg-slate-50 text-[11px] font-bold text-muted">
              <HeaderCell className="w-12 px-4 py-3" label="Save" tip="Save this setup to the watchlist for quick follow-up." />
              <HeaderCell className="w-12 px-4 py-3" label="Rank" tip="Original rank among the qualified setups before any filtering." />
              <HeaderCell className="px-3 py-3" label="Ticker / Context" tip="Ticker, sector context, and grade." />
              <HeaderCell className="px-3 py-3" label="Action" tip="Primary timing cue. ENTER now, WATCH for improved setup, WAIT when extended." />
              <HeaderCell className="px-3 py-3" label="Contract / Expiry" tip="Contract type, strike, expiry, and strike setup context." />
              <HeaderCell className="px-3 py-3" label="Depth" tip="Contract volume and open interest from the signal snapshot." />
              <HeaderCell className="px-3 py-3" label="RSI" tip="Underlying stock RSI. Context only, not a standalone entry signal." />
              <th className="w-8 px-2 py-3" aria-hidden="true" />
            </tr>
          </thead>
          <tbody>
            {trades.length === 0 ? (
              <tr>
                  <td colSpan={8} className="px-5 py-16 text-center">
                  <p className="text-base font-black text-ink">{emptyState?.title || "No ranked trades available"}</p>
                  <p className="mt-2 text-sm font-semibold text-muted">
                    {emptyState?.message || "The live API returned successfully, but the trades array is empty."}
                  </p>
                </td>
              </tr>
            ) : null}

            {trades.map((trade) => {
              const isHero = heroTicker === trade.ticker;
              const sectorContextLabel = sectorLabelByName.get(trade.context.sector) || "Balanced Opportunity";

              return (
                <tr
                  key={trade.contract.optionSymbol}
                  onClick={() => onSelectTrade?.(trade)}
                  className={`group cursor-pointer border-t text-sm transition duration-200 ${
                    isHero
                      ? "border-l-[3px] border-l-emerald-500 border-slate-700 bg-slate-800 hover:bg-slate-700 hover:shadow-[inset_0_0_0_1px_rgba(148,163,184,0.24)]"
                      : "border-l-[3px] border-l-transparent border-slate-100 hover:bg-blue-50/45 hover:shadow-[inset_0_0_0_1px_rgba(148,163,184,0.18)]"
                  }`}
                >
                  <td className="px-4 py-4">
                    <button
                      type="button"
                      aria-label={isWatched(trade, watchlist) ? `Remove ${trade.ticker} from watchlist` : `Add ${trade.ticker} to watchlist`}
                      title={isWatched(trade, watchlist) ? "Saved to watchlist" : "Save to watchlist"}
                      onClick={(event) => {
                        event.stopPropagation();
                        onToggleWatchlist?.(trade);
                      }}
                      className={`inline-flex h-8 w-8 items-center justify-center rounded-md border text-sm transition ${
                        isWatched(trade, watchlist)
                          ? "border-amber-200 bg-amber-50 text-amber-600"
                          : isHero
                            ? "border-blue-500/50 bg-blue-600/15 text-blue-100 hover:border-blue-300 hover:bg-blue-500/20 hover:text-white"
                            : "border-slate-200 bg-white text-slate-400 hover:border-amber-300 hover:text-amber-600"
                      }`}
                    >
                      {isWatched(trade, watchlist) ? "★" : "☆"}
                    </button>
                  </td>
                  <td className="px-4 py-4">
                    <span className={`inline-flex h-8 min-w-9 items-center justify-center rounded-full px-2 text-xs font-black ring-2 ${
                      isHero ? "bg-blue-600 text-white ring-slate-700" : "bg-slate-100 text-slate-700 ring-slate-100"
                    }`}>
                      {trade.rank}
                    </span>
                  </td>
                  <td className="px-3 py-4">
                    <div className="space-y-1">
                      <div className="flex items-center gap-2">
                        <p className={`text-base font-black leading-none ${isHero ? "text-white" : "text-ink"}`}>{trade.ticker}</p>
                        <TierBadge tier={trade.tier} className="h-6 min-w-[38px] px-2 text-[10px]" />
                      </div>
                      {trade.companyName ? <p className={`text-[11px] font-semibold ${isHero ? "text-slate-300" : "text-muted"}`}>{trade.companyName}</p> : null}
                      <p className={`text-[11px] font-semibold ${isHero ? "text-slate-400" : "text-slate-500"}`}>
                        {trade.context.sector} ({sectorContextLabel})
                      </p>
                    </div>
                  </td>
                  <td className="px-3 py-4">
                    <div className="space-y-2">
                      <ActionBadge action={trade.action} className={`h-10 min-w-[96px] text-xs ${isHero ? "brightness-110 shadow-[0_10px_22px_rgba(15,23,42,0.42)]" : ""}`} />
                      <p className={`text-[11px] font-semibold ${isHero ? "text-slate-300" : "text-slate-600"}`}>{actionTone(trade.action)}</p>
                    </div>
                  </td>
                  <td className="px-3 py-4">
                    <div className="space-y-1">
                      <p className={`text-[11px] font-black uppercase ${isHero ? "text-slate-200" : "text-ink"}`}>{trade.optionType} {formatCurrency(trade.contract.strike)}</p>
                      <p className={`text-xs font-semibold ${isHero ? "text-slate-200" : "text-slate-700"}`}>{formatExpiry(trade.contract.expiry)} • {trade.contract.dte}d</p>
                      <div className="flex items-center gap-2">
                        <Badge tone={positionTone(trade.contract.strikePositionLabel)} className="h-6 px-2 text-[10px]">
                          {trade.contract.strikePositionLabel}
                        </Badge>
                        <span className={`text-[11px] font-semibold ${isHero ? "text-slate-300" : "text-muted"}`}>{trade.contract.strikePositionText}</span>
                      </div>
                    </div>
                  </td>
                  <td className="px-3 py-4">
                    <div className="space-y-1 text-right">
                      <p className={`text-xs font-bold ${isHero ? "text-slate-200" : "text-slate-700"}`}>Vol {formatNumber(trade.market.volume)}</p>
                      <p className={`text-[11px] font-semibold ${isHero ? "text-slate-300" : "text-slate-500"}`}>OI {formatNumber(trade.market.openInterest)}</p>
                    </div>
                  </td>
                  <td className={`px-3 py-4 text-right text-[11px] font-semibold ${isHero ? "text-slate-300" : "text-slate-500"}`}>
                    {Number.isFinite(trade.context.rsi) ? trade.context.rsi.toFixed(1) : "N/A"}
                  </td>
                  <td className="px-2 py-4 text-center">
                    <span
                      aria-hidden="true"
                      className={`inline-block text-base leading-none transition-opacity duration-200 ${
                        isHero
                          ? "text-slate-300/45 group-hover:text-slate-200 group-hover:opacity-90"
                          : "text-slate-400/40 group-hover:text-slate-500 group-hover:opacity-90"
                      }`}
                    >
                      ›
                    </span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function HeaderCell({
  label,
  tip,
  className = "px-3 py-3"
}: {
  label: string;
  tip: string;
  className?: string;
}) {
  return (
    <th className={className}>
      <span className="group relative inline-flex cursor-help items-center border-b border-dotted border-slate-300 pb-0.5">
        {label}
        <span className="pointer-events-none absolute left-1/2 top-full z-30 mt-2 w-56 -translate-x-1/2 rounded-md border border-slate-200 bg-slate-950 px-3 py-2 text-left text-[11px] font-semibold leading-5 tracking-normal text-white opacity-0 shadow-card transition group-hover:opacity-100 group-focus:opacity-100">
          {tip}
          <span className="absolute -top-1 left-1/2 h-2 w-2 -translate-x-1/2 rotate-45 bg-slate-950" />
        </span>
      </span>
    </th>
  );
}

function positionTone(label: string) {
  if (label.includes("ITM")) return "green";
  if (label === "ATM") return "blue";
  return "neutral";
}

function isWatched(trade: TopTrade, watchlist: WatchlistItem[]) {
  return watchlist.some((item) => item.ticker === trade.ticker);
}

function actionTone(action: TopTrade["action"]) {
  if (action === "ENTER") return "Favorable entry (aligned with sector strength)";
  if (action === "WATCH") return "Valid setup - timing not ideal";
  return "Extended - timing risk elevated";
}

function classifySector(sector: SectorOutlook) {
  const tickerCount = Math.max(0, Number(sector.tickerCount ?? 0));
  const aTierTickerCount = Math.max(0, Number(sector.aTierTickerCount ?? 0));
  const top3Share = Number(sector.top3Share ?? 0);
  const breadthRatio = tickerCount > 0 ? aTierTickerCount / tickerCount : 0;

  if (top3Share > 70) return { label: "Highly Concentrated" };
  if (breadthRatio > 0.06 && top3Share < 40) return { label: "Broad Strength" };
  if (breadthRatio < 0.03) return { label: "Narrow Opportunity" };
  if (top3Share >= 50 && top3Share <= 75) return { label: "Moderately Concentrated" };
  return { label: "Balanced Opportunity" };
}
