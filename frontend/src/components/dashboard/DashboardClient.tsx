"use client";

import { useEffect, useMemo, useState } from "react";
import { Dashboard } from "@/components/dashboard/Dashboard";
import { DashboardEmptyState, DashboardErrorState, DashboardLoadingState } from "@/components/dashboard/DashboardStates";
import { TradeDetailDrawer } from "@/components/dashboard/TradeDetailDrawer";
import { applyTradeFilters, type TradeFiltersState } from "@/components/dashboard/TradeFilters";
import { fetchDashboardData } from "@/lib/api/options-client";
import { supabase } from "@/lib/supabaseClient";
import { getDecisionState } from "@/lib/trade-decision";
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
  const [showReview, setShowReview] = useState(false);
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

  async function loadDashboard(signal?: AbortSignal) {
    setState({ status: "loading", data: null, error: null });

    try {
      const data = await fetchDashboardData(signal);
      console.log("Dashboard API payload loaded", data);
      setSelectedTrade(null);
      setState({
        status: data.trades.length > 0 ? "ready" : "empty",
        data,
        error: null
      });
    } catch (error) {
      if (error instanceof DOMException && error.name === "AbortError") return;

      setState({
        status: "error",
        data: null,
        error: error instanceof Error ? error.message : "Unable to load dashboard data."
      });
    }
  }

  useEffect(() => {
    const controller = new AbortController();
    void loadDashboard(controller.signal);

    return () => controller.abort();
  }, []);

  async function handleLogout() {
    await supabase.auth.signOut();
  }

  if (state.status === "loading") {
    return <DashboardLoadingState />;
  }

  if (state.status === "error") {
    return <DashboardErrorState message={state.error} onRetry={() => void loadDashboard()} />;
  }

  if (state.status === "empty") {
    return <DashboardEmptyState data={state.data} onRefresh={() => void loadDashboard()} />;
  }

  return (
      <DashboardWithState
        data={state.data}
        filters={filters}
        showReview={showReview}
        watchlist={watchlist}
        selectedTrade={selectedTrade}
        onFiltersChange={setFilters}
        onToggleReview={() => setShowReview((current) => !current)}
        onToggleWatchlist={(trade) => setWatchlist((current) => toggleWatch(current, trade))}
        onSelectTrade={setSelectedTrade}
        onCloseTrade={() => setSelectedTrade(null)}
        onRefresh={() => void loadDashboard()}
        userEmail={userEmail}
        onLogout={() => void handleLogout()}
    />
  );
}

function DashboardWithState({
  data,
  filters,
  showReview,
  watchlist,
  selectedTrade,
  onFiltersChange,
  onToggleReview,
  onToggleWatchlist,
  onSelectTrade,
  onCloseTrade,
  onRefresh,
  userEmail,
  onLogout
}: {
  data: DashboardData;
  filters: TradeFiltersState;
  showReview: boolean;
  watchlist: WatchlistItem[];
  selectedTrade: TopTrade | null;
  onFiltersChange: (filters: TradeFiltersState) => void;
  onToggleReview: () => void;
  onToggleWatchlist: (trade: TopTrade) => void;
  onSelectTrade: (trade: TopTrade) => void;
  onCloseTrade: () => void;
  onRefresh: () => void;
  userEmail: string | null;
  onLogout: () => void;
}) {
  const heroTrade = useMemo(
    () =>
      data.trades.find((trade) => getDecisionState(trade).action === "ENTER") ??
      data.trades.find((trade) => getDecisionState(trade).action === "WATCH") ??
      data.trades[0] ??
      null,
    [data.trades]
  );
  const sectors = useMemo(
    () => Array.from(new Set(data.trades.map((trade) => trade.context.sector).filter(Boolean))).sort(),
    [data.trades]
  );
  const filteredTrades = useMemo(() => applyTradeFilters(data.trades, filters, showReview), [data.trades, filters, showReview]);
  const sectorOutlook = useMemo(() => enrichSectorOutlook(data.sectorOutlook, filteredTrades), [data.sectorOutlook, filteredTrades]);
  const reviewCount = useMemo(() => data.trades.filter((trade) => trade.action === "PASS").length, [data.trades]);

  return (
    <>
      <Dashboard
        data={{ ...data, watchlist, trades: filteredTrades, sectorOutlook }}
        heroTrade={heroTrade}
        totalTrades={data.trades.length}
        filters={filters}
        sectors={sectors}
        showReview={showReview}
        reviewCount={reviewCount}
        onFiltersChange={onFiltersChange}
        onToggleReview={onToggleReview}
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
