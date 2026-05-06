"use client";

import { useEffect, useMemo, useState } from "react";
import { Dashboard } from "@/components/dashboard/Dashboard";
import { DashboardEmptyState, DashboardErrorState, DashboardLoadingState } from "@/components/dashboard/DashboardStates";
import { TradeDetailDrawer } from "@/components/dashboard/TradeDetailDrawer";
import { applyTradeFilters, type TradeFiltersState } from "@/components/dashboard/TradeFilters";
import { fetchDashboardData } from "@/lib/api/options-client";
import { supabase } from "@/lib/supabaseClient";
import type { DashboardData, SectorOutlook, TopTrade, WatchlistItem } from "@/types/dashboard";

type LoadState =
  | { status: "loading"; data: null; error: null }
  | { status: "ready"; data: DashboardData; error: null }
  | { status: "empty"; data: DashboardData; error: null }
  | { status: "error"; data: null; error: string };

export function DashboardClient() {
  const [state, setState] = useState<LoadState>({ status: "loading", data: null, error: null });
  const [selectedTrade, setSelectedTrade] = useState<TopTrade | null>(null);
  const [filters, setFilters] = useState<TradeFiltersState>({
    action: "ALL",
    tier: "ALL",
    sector: "ALL",
    query: ""
  });
  const [showExtended, setShowExtended] = useState(false);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [watchlist, setWatchlist] = useState<WatchlistItem[]>([]);
  const [userEmail, setUserEmail] = useState<string | null>(null);

  useEffect(() => {
    try {
      const raw = window.localStorage.getItem("options-mvp-watchlist");
      if (!raw) return;
      const parsed = JSON.parse(raw) as WatchlistItem[];
      if (Array.isArray(parsed)) setWatchlist(parsed);
    } catch {
      // no-op
    }
  }, []);

  useEffect(() => {
    try {
      window.localStorage.setItem("options-mvp-watchlist", JSON.stringify(watchlist));
    } catch {
      // no-op
    }
  }, [watchlist]);

  useEffect(() => {
    let mounted = true;

    async function syncSession() {
      const { data } = await supabase.auth.getSession();
      if (!mounted) return;

      setUserEmail(data.session?.user?.email ?? null);
      if (data.session?.user?.email) {
        console.log("Logged in user:", data.session.user.email);
      }
    }

    void syncSession();

    const {
      data: { subscription }
    } = supabase.auth.onAuthStateChange((_event, session) => {
      setUserEmail(session?.user?.email ?? null);
      if (session?.user?.email) {
        console.log("Logged in user:", session.user.email);
      }
    });

    return () => {
      mounted = false;
      subscription.unsubscribe();
    };
  }, []);

  async function loadDashboard(includeExtended: boolean, signal?: AbortSignal) {
    const hasExistingData = state.data !== null;

    if (hasExistingData) {
      setIsRefreshing(true);
    } else {
      setState({ status: "loading", data: null, error: null });
    }

    try {
      const data = await fetchDashboardData(includeExtended, signal);
      console.log("Dashboard API payload loaded", data);
      setSelectedTrade(null);
      setState({
        status: data.trades.length > 0 ? "ready" : "empty",
        data,
        error: null
      });
    } catch (error) {
      if (error instanceof DOMException && error.name === "AbortError") return;

      if (hasExistingData) {
        console.error("Unable to refresh dashboard data", error);
        setIsRefreshing(false);
        return;
      }

      setState({
        status: "error",
        data: null,
        error: error instanceof Error ? error.message : "Unable to load dashboard data."
      });
    } finally {
      setIsRefreshing(false);
    }
  }

  useEffect(() => {
    const controller = new AbortController();
    void loadDashboard(showExtended, controller.signal);

    return () => controller.abort();
  }, [showExtended]);

  async function handleLogout() {
    await supabase.auth.signOut();
  }

  if (state.status === "loading") {
    return <DashboardLoadingState />;
  }

  if (state.status === "error") {
    return <DashboardErrorState message={state.error} onRetry={() => void loadDashboard(showExtended)} />;
  }

  if (state.status === "empty") {
    return <DashboardEmptyState data={state.data} onRefresh={() => void loadDashboard(showExtended)} />;
  }

  return (
      <DashboardWithState
        data={state.data}
        filters={filters}
        showExtended={showExtended}
        isRefreshing={isRefreshing}
        watchlist={watchlist}
        selectedTrade={selectedTrade}
        onFiltersChange={setFilters}
        onToggleExtended={() => setShowExtended((current) => !current)}
        onToggleWatchlist={(trade) => setWatchlist((current) => toggleWatch(current, trade))}
        onSelectTrade={setSelectedTrade}
        onCloseTrade={() => setSelectedTrade(null)}
        onRefresh={() => void loadDashboard(showExtended)}
        userEmail={userEmail}
        onLogout={() => void handleLogout()}
    />
  );
}

function DashboardWithState({
  data,
  filters,
  showExtended,
  isRefreshing,
  watchlist,
  selectedTrade,
  onFiltersChange,
  onToggleExtended,
  onToggleWatchlist,
  onSelectTrade,
  onCloseTrade,
  onRefresh,
  userEmail,
  onLogout
}: {
  data: DashboardData;
  filters: TradeFiltersState;
  showExtended: boolean;
  isRefreshing: boolean;
  watchlist: WatchlistItem[];
  selectedTrade: TopTrade | null;
  onFiltersChange: (filters: TradeFiltersState) => void;
  onToggleExtended: () => void;
  onToggleWatchlist: (trade: TopTrade) => void;
  onSelectTrade: (trade: TopTrade) => void;
  onCloseTrade: () => void;
  onRefresh: () => void;
  userEmail: string | null;
  onLogout: () => void;
}) {
  const rankedTrades = useMemo(() => data.trades, [data.trades]);
  const heroTrade = useMemo(
    () =>
      rankedTrades.find((trade) => trade.action === "ENTER") ??
      rankedTrades.find((trade) => trade.action === "WATCH") ??
      rankedTrades[0] ??
      null,
    [rankedTrades]
  );
  const topRankedTrade = useMemo(() => rankedTrades.find((trade) => trade.rank === 1) ?? null, [rankedTrades]);
  const sectors = useMemo(
    () => Array.from(new Set(rankedTrades.map((trade) => trade.context.sector).filter(Boolean))).sort(),
    [rankedTrades]
  );
  const filteredTrades = useMemo(() => applyTradeFilters(rankedTrades, filters), [rankedTrades, filters]);
  const displayedTrades = useMemo(() => filteredTrades, [filteredTrades]);
  const sectorOutlook = useMemo(() => enrichSectorOutlook(data.sectorOutlook, displayedTrades), [data.sectorOutlook, displayedTrades]);
  const actionableCount = useMemo(
    () => filteredTrades.filter((trade) => trade.action === "ENTER").length,
    [filteredTrades]
  );
  const fullWorkbenchActionMap = useMemo(
    () =>
      Object.fromEntries(
        rankedTrades.map((trade) => [trade.ticker, trade.action])
      ) as Record<string, "ENTER" | "WATCH" | "WAIT">,
    [rankedTrades]
  );
  const computedTradeEmptyState = useMemo(() => buildTradeEmptyState(filters, showExtended), [filters, showExtended]);
  const systemInsight = useMemo(() => buildSystemInsight(data.marketRegime, rankedTrades), [data.marketRegime, rankedTrades]);

  return (
    <>
      <Dashboard
        data={{ ...data, watchlist, trades: displayedTrades, sectorOutlook }}
        heroTrade={heroTrade}
        topRankedTrade={topRankedTrade}
        allTrades={rankedTrades}
        totalTrades={rankedTrades.length}
        filters={filters}
        sectors={sectors}
        showExtended={showExtended}
        actionableCount={actionableCount}
        tradeEmptyState={computedTradeEmptyState}
        systemInsight={systemInsight}
        fullWorkbenchActionMap={fullWorkbenchActionMap}
        onFiltersChange={onFiltersChange}
        onToggleExtended={onToggleExtended}
        onToggleWatchlist={onToggleWatchlist}
        onSelectTrade={onSelectTrade}
        onRefresh={onRefresh}
        userEmail={userEmail}
        onLogout={onLogout}
      />
      <TradeDetailDrawer
        trade={selectedTrade}
        marketRegime={data.marketRegime}
        isWatched={selectedTrade ? watchlist.some((item) => item.ticker === selectedTrade.ticker) : false}
        onToggleWatchlist={onToggleWatchlist}
        onClose={onCloseTrade}
      />
    </>
  );
}

function toggleWatch(current: WatchlistItem[], trade: TopTrade) {
  const exists = current.some((item) => item.ticker === trade.ticker);
  if (exists) {
    return current.filter((item) => item.ticker !== trade.ticker);
  }

  return [
    {
      ticker: trade.ticker,
      action: trade.action,
      tier: trade.tier
    },
    ...current
  ];
}

function enrichSectorOutlook(outlook: SectorOutlook[], trades: TopTrade[]): SectorOutlook[] {
  const visibleCounts = new Map<string, number>();

  for (const trade of trades) {
    const sector = trade.context.sector || "Unknown";
    visibleCounts.set(sector, (visibleCounts.get(sector) ?? 0) + 1);
  }

  return outlook.map((sector) => ({
    ...sector,
    visibleSetups: visibleCounts.get(sector.sector) ?? 0
  }));
}

function buildTradeEmptyState(filters: TradeFiltersState, showExtended: boolean): { title: string; message: string } {
  if (filters.action === "ENTER") {
    return {
      title: "No ENTER setups match the current filters.",
      message: "Try clearing Sector/Search filters or include extended setups."
    };
  }

  if (filters.action === "WATCH") {
    return {
      title: "No WATCH setups match the current filters.",
      message: "Try clearing Sector/Search filters or include extended setups."
    };
  }

  if (filters.action === "WAIT") {
    return {
      title: "No WAIT setups match the current filters.",
      message: showExtended ? "Try clearing Sector/Search filters." : "Extended setups are off, so WAIT setups may be limited."
    };
  }

  if (!showExtended) {
    return {
      title: "High-conviction setups are limited today.",
      message: "Only the strongest signals are shown."
    };
  }

  return {
    title: "No qualified setups match the current filters.",
    message: "Try clearing Sector/Search filters."
  };
}

function buildSystemInsight(marketRegime: DashboardData["marketRegime"], trades: TopTrade[]) {
  const rows = trades.map((trade) => ({
    trade,
    action: trade.action
  }));
  const enterCount = rows.filter((row) => row.action === "ENTER").length;
  const watchCount = rows.filter((row) => row.action === "WATCH").length;
  const topRanked = rows[0] ?? null;
  const bestEntry = rows.find((row) => row.action === "ENTER") ?? null;
  const marketLabel = marketRegime?.regime ?? "Unknown";
  const riskOff =
    marketRegime?.risk?.shockDay ||
    (typeof marketRegime?.vix?.level === "number" && marketRegime.vix.level >= 30) ||
    /risk-off/i.test(marketLabel);

  if (riskOff) {
    return "System Insight: Risk conditions are softer; reduce aggression and wait for cleaner entries.";
  }

  if (enterCount >= 5 && topRanked?.action === "WAIT") {
    const bestEntryPhrase = bestEntry?.trade.ticker
      ? `${bestEntry.trade.ticker} is the cleaner timing-adjusted entry`
      : "A cleaner timing-adjusted entry is available";
    return `System Insight: Several clean entries are available, but the top-ranked signal is extended. ${bestEntryPhrase}.`;
  }

  if (enterCount >= 5) {
    const bestEntryPhrase = bestEntry?.trade.ticker
      ? `${bestEntry.trade.ticker} leads the group`
      : "The best entry leads the group";
    return `System Insight: Multiple clean entries are available; prioritize the highest-ranked actionable names. ${bestEntryPhrase}.`;
  }

  if (enterCount >= 1 && enterCount <= 4) {
    return "System Insight: Selective entry environment; only a few clean setups are available today.";
  }

  if (enterCount === 0 && watchCount > 0) {
    return "System Insight: No clean entries yet; several setups remain on watch for better timing.";
  }

  if (enterCount === 0 && watchCount === 0) {
    return "System Insight: No actionable setups today; patience is favored.";
  }

  return `System Insight: ${marketLabel} conditions remain mixed; stay selective.`;
}
