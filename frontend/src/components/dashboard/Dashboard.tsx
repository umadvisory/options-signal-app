import { JoinBetaDialog } from "@/components/dashboard/JoinBetaDialog";
import { MarketRegimeStrip } from "@/components/dashboard/MarketRegimeStrip";
import { SectorContextCards } from "@/components/dashboard/SectorContextCards";
import { SummaryCard } from "@/components/dashboard/SummaryCard";
import { TopTradesTable } from "@/components/dashboard/TopTradesTable";
import { TradeFilters, type TradeFiltersState } from "@/components/dashboard/TradeFilters";
import { WatchlistBar } from "@/components/dashboard/WatchlistBar";
import { YesterdayStatusSection } from "@/components/dashboard/YesterdayStatusSection";
import type { DashboardData, TopTrade } from "@/types/dashboard";

export function Dashboard({
  data,
  heroTrade,
  topRankedTrade,
  allTrades,
  totalTrades,
  filters,
  sectors,
  showExtended,
  isRefreshing,
  actionableCount,
  tradeEmptyState,
  systemInsight,
  fullWorkbenchActionMap,
  onFiltersChange,
  onToggleExtended,
  onToggleWatchlist,
  onSelectTrade,
  onRefresh,
  userEmail,
  onLogout
}: {
  data: DashboardData;
  heroTrade?: TopTrade | null;
  topRankedTrade?: TopTrade | null;
  allTrades?: TopTrade[];
  totalTrades?: number;
  filters?: TradeFiltersState;
  sectors?: string[];
  showExtended?: boolean;
  isRefreshing?: boolean;
  actionableCount?: number;
  tradeEmptyState?: { title: string; message: string } | null;
  systemInsight?: string | null;
  fullWorkbenchActionMap?: Record<string, "ENTER" | "WATCH" | "WAIT">;
  onFiltersChange?: (filters: TradeFiltersState) => void;
  onToggleExtended?: () => void;
  onToggleWatchlist?: (trade: TopTrade) => void;
  onSelectTrade?: (trade: TopTrade) => void;
  onRefresh?: () => void;
  userEmail?: string | null;
  onLogout?: () => void;
}) {
  const enterCount = data.trades.filter((trade) => trade.action === "ENTER").length;
  const watchCount = data.trades.filter((trade) => trade.action === "WATCH").length;
  const workbenchActionMap = Object.fromEntries(
    data.trades.map((trade) => [trade.ticker, trade.action])
  ) as Record<string, "ENTER" | "WATCH" | "WAIT">;
  const leadingEnterTrade = data.trades.find((trade) => trade.action === "ENTER") ?? null;
  const resolvedHeroTrade = heroTrade ?? null;
  const heroDecision = resolvedHeroTrade ? resolvedHeroTrade.action : null;
  const resolvedTopRankedTrade = topRankedTrade ?? null;

  return (
    <main className="min-h-screen px-4 py-4 sm:px-6 lg:px-8">
      <div className="mx-auto flex max-w-7xl flex-col gap-6">
        <div className="flex flex-col gap-4 rounded-lg border border-slate-200 bg-white px-5 py-5 shadow-soft lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="text-xs font-bold text-muted">Options MVP</p>
            <h1 className="mt-1 text-[32px] font-black leading-tight text-ink">Signals Dashboard</h1>
            <p className="mt-2 max-w-2xl text-sm font-semibold leading-6 text-muted">
              A curated view of today&apos;s qualified options setups, with market regime context and trade-level decision support.
            </p>
            <p className="mt-2 max-w-2xl text-xs font-semibold leading-5 text-slate-500">
              Educational signals only. Not investment advice. Trades shown are model-generated and for research purposes.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2 lg:justify-end">
            {userEmail ? <TopChip label="User" value={userEmail} tone="slate" /> : null}
            <TopChip label="Priority" value={String(enterCount)} tone="green" />
            <TopChip label="Watch" value={String(watchCount)} tone="amber" />
            {data.signalDate ? <TopChip label="Signal date" value={formatSignalDate(data.signalDate)} tone="slate" /> : null}
            <TopChip label="Updated" value={formatGeneratedAt(data.generatedAt)} tone="slate" />
            <JoinBetaDialog />
            {onRefresh ? (
              <button
                type="button"
                onClick={onRefresh}
                className="inline-flex h-9 items-center justify-center rounded-md border border-slate-200 bg-slate-50 px-4 text-xs font-black text-ink transition hover:border-blue-300 hover:bg-white hover:text-blue-700"
              >
                Refresh
              </button>
            ) : null}
            {onLogout && userEmail ? (
              <button
                type="button"
                onClick={onLogout}
                className="inline-flex h-9 items-center justify-center rounded-md border border-slate-200 bg-white px-4 text-xs font-black text-slate-700 transition hover:border-red-300 hover:text-red-700"
              >
                Logout
              </button>
            ) : null}
          </div>
        </div>

        <MarketRegimeStrip
          regime={data.marketRegime}
          insight={systemInsight ?? data.marketRegime?.insight ?? null}
          leadingTicker={leadingEnterTrade?.ticker ?? resolvedTopRankedTrade?.ticker ?? null}
        />

        <WatchlistBar
          items={data.watchlist}
          allTrades={allTrades ?? data.trades}
          yesterdayStatus={data.yesterdayStatus}
          currentActionByTicker={fullWorkbenchActionMap}
          onSelectTrade={onSelectTrade}
        />

        {resolvedHeroTrade && heroDecision ? (
          <section className="rounded-lg border border-blue-300 bg-slate-950 px-6 py-4 text-white shadow-[0_18px_42px_rgba(15,23,42,0.18)]">
            <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
              <div className="max-w-3xl">
                <p className="text-xs font-bold tracking-[0.06em] text-blue-200">
                  {heroDecision === "ENTER" ? "Best Entry Now" : "Best Setup (Timing Developing)"}
                </p>
                <div className="mt-3 flex flex-wrap items-center gap-3">
                  <h2 className="text-[34px] font-black leading-none text-white">{resolvedHeroTrade.ticker}</h2>
                  <span className={heroGradeClass(resolvedHeroTrade.tier)}>{resolvedHeroTrade.tier}</span>
                  <span className={heroActionClass(heroDecision)}>{heroDecision}</span>
                </div>
                <p className="mt-2 text-xs font-semibold text-slate-400">Ranked #{resolvedHeroTrade.rank} overall</p>
                {resolvedHeroTrade.companyName ? (
                  <p className="mt-2 text-base font-semibold text-slate-300">{resolvedHeroTrade.companyName}</p>
                ) : null}
                <p className="mt-3 text-base font-semibold leading-7 text-slate-200">
                  {buildHeroRationale(resolvedHeroTrade, {
                    topTrade: resolvedTopRankedTrade
                      ? {
                          ...resolvedTopRankedTrade,
                          action:
                            fullWorkbenchActionMap?.[resolvedTopRankedTrade.ticker] ??
                            resolvedTopRankedTrade.action
                        }
                      : null,
                    trades: data.trades
                  })}
                </p>
              </div>
              <div className="grid gap-3 sm:grid-cols-2 lg:min-w-[320px] lg:max-w-[420px] lg:flex-1">
                <HeroStat label="Expected Window" value={resolvedHeroTrade.decisionContext?.expectation.timeframe || `${resolvedHeroTrade.contract.dte} trading days`} />
                <HeroStat label="Execution Snapshot" value={buildHeroStructure(resolvedHeroTrade)} />
              </div>
            </div>
          </section>
        ) : null}

        <section className="grid gap-5 lg:grid-cols-2">
          <SummaryCard
            title="High Conviction"
            stats={data.strategyStats.highConviction}
            accent="green"
            eyebrow="Historical Benchmark"
            benchmarkContext="Shows how the model has performed recently - across different signal profiles."
            description="Fewer trades with higher upside per trade. Best used when signals align and selective entry matters."
            interpretationLabel="Payoff-driven"
            winRateContext="higher payoff skew"
            avgReturnLabel="Avg Return (per trade)"
            avgReturnContext="skewed by high payoff trades"
            chartContext="Payoff distribution (last 30 days)"
          />
          <SummaryCard
            title="Broad Base"
            stats={data.strategyStats.broadBase}
            accent="ink"
            eyebrow="Historical Benchmark"
            benchmarkContext="Shows how the model has performed recently - across different signal profiles."
            description="More frequent trades with smoother outcomes. Useful for understanding overall model consistency."
            interpretationLabel="Consistency-driven"
            winRateContext="more consistent outcomes"
            avgReturnLabel="Avg Return (per trade)"
            avgReturnContext="skewed by high payoff trades"
            chartContext="Payoff distribution (last 30 days)"
          />
        </section>

        {filters && onFiltersChange && onToggleExtended ? (
          <TradeFilters
            filters={filters}
            sectors={sectors ?? []}
            totalCount={totalTrades ?? data.trades.length}
            visibleCount={data.trades.length}
            actionableCount={actionableCount ?? 0}
            showExtended={showExtended ?? false}
            isRefreshing={isRefreshing ?? false}
            onChange={onFiltersChange}
            onToggleExtended={onToggleExtended}
          />
        ) : null}

        <section className="flex flex-col gap-3">
          <TopTradesTable
            trades={data.trades}
            sectorOutlook={data.sectorOutlook}
            watchlist={data.watchlist}
            heroTicker={resolvedHeroTrade?.ticker ?? null}
            emptyState={tradeEmptyState ?? null}
            onToggleWatchlist={onToggleWatchlist}
            onSelectTrade={onSelectTrade}
          />
        </section>

        <YesterdayStatusSection
          items={data.yesterdayStatus}
          fallbackSignalDate={data.signalDate ?? null}
          workbenchActionMap={fullWorkbenchActionMap ?? workbenchActionMap}
        />

        <section className="pt-1">
          <SectorContextCards sectors={data.sectorOutlook} />
        </section>

        <footer className="pb-2 text-center text-[11px] font-semibold leading-5 text-slate-400">
          This platform provides model-driven trade ideas for educational purposes only. We do not provide financial
          advice. Always confirm prices, liquidity, and suitability before making trading decisions.
        </footer>
      </div>
    </main>
  );
}

function HeroStat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-white/15 bg-white/5 px-4 py-3">
      <p className="text-[10px] font-bold tracking-[0.08em] text-slate-300">{label}</p>
      <p className="mt-2 whitespace-pre-line text-base font-black leading-6 text-white">{value}</p>
    </div>
  );
}

function buildHeroStructure(trade: TopTrade) {
  const strike = Number.isFinite(trade.contract?.strike) ? `$${formatCompactCurrency(trade.contract.strike)}` : null;
  const optionType = trade.optionType
    ? `${trade.optionType.charAt(0).toUpperCase()}${trade.optionType.slice(1).toLowerCase()}`
    : null;
  const expiry = formatHeroExpiry(trade.contract?.expiry ?? null);
  const lineOne = strike && optionType && expiry ? `${strike} ${optionType} • ${expiry}` : `${trade.contract?.strikePositionLabel ?? "ATM"} ${optionType ?? "Call"}`;

  const spot = Number.isFinite(trade.contract?.underlyingPrice) ? `$${trade.contract.underlyingPrice.toFixed(2)}` : null;
  const distancePct = Number.isFinite(trade.contract?.distanceToStrikePct) ? trade.contract.distanceToStrikePct : null;
  const lineTwo =
    spot !== null && distancePct !== null
      ? `Spot ${spot} • ${distancePct >= 0 ? "+" : ""}${distancePct.toFixed(1)}%`
      : null;

  return lineTwo ? `${lineOne}\n${lineTwo}` : lineOne;
}

function formatCompactCurrency(value: number) {
  return Number.isInteger(value) ? value.toFixed(0) : value.toFixed(2);
}

function formatHeroExpiry(value: string | null) {
  if (!value) return null;

  const parsed = new Date(`${value}T00:00:00Z`);
  if (Number.isNaN(parsed.getTime())) return value;

  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    timeZone: "UTC"
  }).format(parsed);
}

function buildHeroRationale(
  trade: TopTrade,
  context: {
    topTrade: TopTrade | null;
    trades: TopTrade[];
  }
) {
  const rank = Number.isFinite(trade.rank) ? trade.rank : null;
  const rsi = Number.isFinite(trade.context?.rsi) ? trade.context.rsi : null;
  const distancePct = Number.isFinite(trade.contract?.distanceToStrikePct) ? trade.contract.distanceToStrikePct : null;
  const moneynessValue = trade.contract?.moneyness;
  const moneynessText = String(moneynessValue ?? "").trim().toUpperCase();
  const moneynessNumber = Number(moneynessValue);
  const isAtm =
    moneynessText === "ATM" || (Number.isFinite(moneynessNumber) && moneynessNumber >= 0.97 && moneynessNumber <= 1.03);

  if (
    rank === null ||
    rsi === null ||
    distancePct === null ||
    (!moneynessText && !Number.isFinite(moneynessNumber)) ||
    (rank > 1 && !context.topTrade)
  ) {
    return "Top-ranked setup based on current model signals.";
  }

  const topAction = context.topTrade?.action ?? null;
  console.log("Hero Logic:", {
    trade: trade.ticker,
    rank: trade.rank,
    topAction
  });

  const differentiator =
    rank > 1 && topAction === "WAIT"
      ? "Cleaner timing than extended top-ranked setup"
      : rank === 1
      ? "Top-ranked setup"
      : "Strong alternative to higher-ranked setup";

  const entryQuality = isAtm ? "ATM entry" : distancePct <= 3 ? "slightly extended entry" : "extended entry";
  const momentum =
    rsi >= 65 ? "elevated momentum" : rsi >= 55 ? "balanced momentum" : "early momentum";

  const sentence = `${differentiator}, ${entryQuality}, ${momentum}.`;
  const words = sentence.trim().split(/\s+/);
  if (words.length <= 18) return sentence;

  return `${differentiator}, ${entryQuality}, ${momentum}.`;
}

function heroGradeClass(tier: TopTrade["tier"]) {
  const tones: Record<TopTrade["tier"], string> = {
    "A+": "inline-flex h-9 items-center justify-center rounded-md bg-emerald-500 px-3 text-sm font-black text-white",
    A: "inline-flex h-9 items-center justify-center rounded-md bg-emerald-100 px-3 text-sm font-black text-emerald-800",
    "A-": "inline-flex h-9 items-center justify-center rounded-md bg-lime-100 px-3 text-sm font-black text-lime-800",
    "B+": "inline-flex h-9 items-center justify-center rounded-md bg-orange-100 px-3 text-sm font-black text-orange-800",
    B: "inline-flex h-9 items-center justify-center rounded-md bg-slate-200 px-3 text-sm font-black text-slate-700"
  };

  return tones[tier];
}

function heroActionClass(label: string) {
  if (label === "ENTER") {
    return "inline-flex h-9 items-center justify-center rounded-md bg-emerald-600 px-3 text-sm font-black text-white ring-1 ring-emerald-300";
  }

  if (label === "WAIT") {
    return "inline-flex h-9 items-center justify-center rounded-md bg-red-600 px-3 text-sm font-black text-white ring-1 ring-red-300";
  }

  return "inline-flex h-9 items-center justify-center rounded-md bg-amber-500 px-3 text-sm font-black text-white ring-1 ring-amber-300";
}

function TopChip({ label, value, tone }: { label: string; value: string; tone: "green" | "amber" | "slate" }) {
  const tones = {
    green: "border-emerald-200 bg-emerald-50 text-emerald-700",
    amber: "border-amber-200 bg-amber-50 text-amber-700",
    slate: "border-slate-200 bg-slate-50 text-slate-700"
  };

  return (
    <div className={`rounded-md border px-3 py-2 ${tones[tone]}`}>
      <p className="text-[10px] font-bold tracking-[0.04em]">{label}</p>
      <p className="mt-1 text-sm font-black">{value}</p>
    </div>
  );
}

function formatGeneratedAt(value: string) {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;

  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit"
  }).format(parsed);
}

function formatSignalDate(value: string) {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;

  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric"
  }).format(parsed);
}
