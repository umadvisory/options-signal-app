import { ActionBadge, Badge, TierBadge } from "@/components/ui/Badge";
import { formatCurrency, formatExpiry, formatNumber } from "@/lib/format";
import { getDecisionState } from "@/lib/trade-decision";
import type { TopTrade, WatchlistItem } from "@/types/dashboard";

export function TopTradesTable({
  trades,
  watchlist = [],
  heroTicker,
  emptyState,
  onToggleWatchlist,
  onSelectTrade
}: {
  trades: TopTrade[];
  watchlist?: WatchlistItem[];
  heroTicker?: string | null;
  emptyState?: { title: string; message: string } | null;
  onToggleWatchlist?: (trade: TopTrade) => void;
  onSelectTrade?: (trade: TopTrade) => void;
}) {
  return (
    <section className="overflow-hidden rounded-lg border border-slate-200 bg-white shadow-soft">
      <div className="flex items-center justify-between gap-4 border-b border-slate-200 px-5 py-4">
        <div>
          <h2 className="text-lg font-black text-ink">Qualified Setups <span className="text-sm font-bold text-muted">(from High Conviction)</span></h2>
          <p className="mt-1 text-[11px] font-semibold text-muted">Showing top actionable setups by overall rank.</p>
        </div>
        <span className="text-xs font-bold text-muted">{trades.length} visible setups</span>
      </div>

      <div className="thin-scrollbar overflow-x-auto">
        <table className="min-w-[860px] w-full border-collapse text-left">
          <thead>
            <tr className="bg-slate-50 text-[11px] font-bold text-muted">
              <HeaderCell className="w-12 px-4 py-3" label="Save" tip="Save this setup to the watchlist for quick follow-up." />
              <HeaderCell className="w-14 px-5 py-3" label="Overall Rank" tip="Original rank among the qualified setups before any filtering." />
              <HeaderCell label="Ticker" tip="Underlying stock symbol." />
              <HeaderCell label="Grade" tip="Relative setup quality grade from the signal engine. Higher grades indicate stronger alignment across screens." />
              <HeaderCell label="Action" tip="ENTER is in a good entry zone. WATCH is valid but timing is less ideal. WAIT means momentum is extended." />
              <HeaderCell label="Contract" tip="Contract type and strike." />
              <HeaderCell label="Expiry" tip="Expiration date and days to expiration." />
              <HeaderCell label="Setup" tip="Underlying price and strike position relative to spot." />
              <HeaderCell label="Depth" tip="Contract volume and open interest from the signal snapshot." />
              <HeaderCell label="RSI" tip="Underlying stock RSI. Context only, not a standalone entry signal." />
            </tr>
          </thead>
          <tbody>
            {trades.length === 0 ? (
              <tr>
                <td colSpan={10} className="px-5 py-16 text-center">
                  <p className="text-base font-black text-ink">{emptyState?.title || "No ranked trades available"}</p>
                  <p className="mt-2 text-sm font-semibold text-muted">
                    {emptyState?.message || "The live API returned successfully, but the trades array is empty."}
                  </p>
                </td>
              </tr>
            ) : null}

            {trades.map((trade) => {
              const decision = getDecisionState(trade);
              const isHero = heroTicker === trade.ticker;

              return (
                <tr
                  key={trade.contract.optionSymbol}
                  onClick={() => onSelectTrade?.(trade)}
                  className={`cursor-pointer border-t text-sm transition ${
                    isHero
                      ? "border-slate-900 bg-slate-950 hover:bg-slate-900/95"
                      : "border-slate-100 hover:bg-blue-50/35"
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
                  <td className="px-5 py-4">
                    <span
                      className={`inline-flex h-9 min-w-10 items-center justify-center rounded-full text-sm font-black ring-4 ${
                        isHero
                          ? "bg-blue-600 text-white ring-slate-700"
                          : trade.rank === 1
                          ? "bg-blue-700 text-white ring-blue-100"
                          : trade.rank <= 3
                            ? "bg-blue-600 text-white ring-blue-50"
                            : "bg-slate-100 text-slate-600 ring-slate-50"
                      }`}
                    >
                      {trade.rank}
                    </span>
                  </td>
                  <td className="px-3 py-4">
                    <div className="space-y-0.5">
                      <p className={`text-lg font-black leading-none ${isHero ? "text-white" : "text-ink"}`}>{trade.ticker}</p>
                      {trade.companyName ? <p className={`text-[11px] font-semibold ${isHero ? "text-slate-300" : "text-muted"}`}>{trade.companyName}</p> : null}
                    </div>
                  </td>
                  <td className="px-3 py-4">
                    <TierBadge tier={trade.tier} />
                  </td>
                  <td className="px-3 py-4">
                    <div className="space-y-1">
                      <ActionBadge action={decision.action} />
                      <p className={`text-[11px] font-semibold ${isHero ? "text-slate-300" : "text-muted"}`}>{decision.explanation}</p>
                    </div>
                  </td>
                  <td className="px-3 py-4">
                    <div className="space-y-1">
                      <p className={`text-[11px] font-black uppercase ${isHero ? "text-slate-200" : "text-ink"}`}>{trade.optionType}</p>
                      <p className={`text-sm font-black ${isHero ? "text-white" : "text-ink"}`}>{formatCurrency(trade.contract.strike)}</p>
                    </div>
                  </td>
                  <td className="px-3 py-4">
                    <div className="space-y-1">
                      <p className={`text-xs font-bold ${isHero ? "text-slate-200" : "text-slate-700"}`}>{formatExpiry(trade.contract.expiry)}</p>
                      <p className={`text-[11px] font-semibold ${isHero ? "text-slate-300" : "text-muted"}`}>{trade.contract.dte}d to expiry</p>
                    </div>
                  </td>
                  <td className="px-3 py-4">
                    <div className="flex min-w-[150px] flex-col gap-1">
                      <p className={`text-sm font-black ${isHero ? "text-white" : "text-ink"}`}>{formatCurrency(trade.contract.underlyingPrice)}</p>
                      <Badge tone={positionTone(trade.contract.strikePositionLabel)}>{trade.contract.strikePositionLabel}</Badge>
                      <span className={`text-[11px] font-semibold ${isHero ? "text-slate-300" : "text-muted"}`}>{trade.contract.strikePositionText}</span>
                    </div>
                  </td>
                  <td className="px-3 py-4">
                    <div className="space-y-1 text-right">
                      <p className={`text-sm font-black ${isHero ? "text-white" : "text-ink"}`}>Vol {formatNumber(trade.market.volume)}</p>
                      <p className={`text-[11px] font-semibold ${isHero ? "text-slate-300" : "text-muted"}`}>OI {formatNumber(trade.market.openInterest)}</p>
                    </div>
                  </td>
                  <td className={`px-3 py-4 text-sm font-bold ${isHero ? "text-slate-200" : "text-slate-700"}`}>
                    {Number.isFinite(trade.context.rsi) ? trade.context.rsi.toFixed(1) : "N/A"}
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
