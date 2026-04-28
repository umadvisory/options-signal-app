import type { DashboardData, SectorOutlook, StrategyStats, TopTrade } from "@/types/dashboard";

const DASHBOARD_ENDPOINT = "/api/top-trades";

type TopTradesApiResponse = {
  generatedAt?: string;
  signalDate?: string | null;
  marketRegime?: DashboardData["marketRegime"];
  strategyStats?: Partial<DashboardData["strategyStats"]>;
  sectorOutlook?: DashboardData["sectorOutlook"];
  yesterdayStatus?: DashboardData["yesterdayStatus"];
  trades?: TopTrade[];
  error?: string;
};

const emptyStats: StrategyStats = {
  winRate: null,
  sampleSize: null,
  tickerCount: null,
  minDate: null,
  maxDate: null,
  avgReturnPct: null,
  medianReturnPct: null,
  worstDrawdownProxy: null,
  lossRate: null,
  largeLossRate: null,
  returnDistribution: [],
  equityCurve: []
};

export async function fetchDashboardData(signal?: AbortSignal): Promise<DashboardData> {
  const response = await fetch(DASHBOARD_ENDPOINT, {
    method: "GET",
    cache: "no-store",
    signal
  });

  let payload: TopTradesApiResponse;
  try {
    payload = (await response.json()) as TopTradesApiResponse;
  } catch {
    throw new Error("The dashboard API returned an unreadable response.");
  }

  if (!response.ok || payload.error) {
    throw new Error(payload.error || `Dashboard API request failed with status ${response.status}.`);
  }

  const trades = Array.isArray(payload.trades) ? payload.trades.map(normalizeTrade) : [];

  return {
    generatedAt: payload.generatedAt ?? new Date().toISOString(),
    signalDate: payload.signalDate ?? trades[0]?.provenance?.signalDate ?? null,
    marketRegime: normalizeMarketRegime(payload.marketRegime),
    watchlist: [],
    strategyStats: {
      highConviction: normalizeStats(payload.strategyStats?.highConviction),
      broadBase: normalizeStats(payload.strategyStats?.broadBase)
    },
    trades,
    sectorOutlook: normalizeSectorOutlook(payload.sectorOutlook),
    yesterdayStatus: normalizeYesterdayStatus(payload.yesterdayStatus)
  };
}

function normalizeMarketRegime(regime: DashboardData["marketRegime"] | undefined): DashboardData["marketRegime"] {
  if (!regime) return null;

  return {
    date: regime.date ?? null,
    regime: regime.regime || "Neutral",
    summary: regime.summary || "Macro context is available for the latest signal run.",
    vix: {
      level: numberOrNull(regime.vix?.level),
      label: regime.vix?.label || "Unknown",
      momentum3d: numberOrNull(regime.vix?.momentum3d),
      percentile: numberOrNull(regime.vix?.percentile)
    },
    spy: {
      return1d: numberOrNull(regime.spy?.return1d),
      trend3d: numberOrNull(regime.spy?.trend3d),
      trend5d: numberOrNull(regime.spy?.trend5d),
      trendLabel: regime.spy?.trendLabel || "Neutral"
    },
    risk: {
      shockDay: Boolean(regime.risk?.shockDay),
      trendStrength: numberOrNull(regime.risk?.trendStrength)
    }
  };
}

function normalizeStats(stats: Partial<StrategyStats> | null | undefined): StrategyStats {
  const sampleSize = stats?.sampleSize ?? null;
  const normalizedDistribution = normalizeReturnDistribution(stats?.returnDistribution, sampleSize);
  const derivedLossProfile = deriveLossProfile(stats?.returnDistribution, sampleSize);

  return {
    winRate: stats?.winRate ?? null,
    sampleSize,
    tickerCount: stats?.tickerCount ?? null,
    minDate: stats?.minDate ?? null,
    maxDate: stats?.maxDate ?? null,
    avgReturnPct: stats?.avgReturnPct ?? null,
    medianReturnPct: stats?.medianReturnPct ?? null,
    worstDrawdownProxy: stats?.worstDrawdownProxy ?? null,
    lossRate: stats?.lossRate ?? derivedLossProfile.lossRate,
    largeLossRate: stats?.largeLossRate ?? derivedLossProfile.largeLossRate,
    returnDistribution: normalizedDistribution,
    equityCurve: Array.isArray(stats?.equityCurve)
      ? stats!.equityCurve!.map((point) => ({
          date: String(point.date || ""),
          value: point.value === null || point.value === undefined ? null : Number(point.value)
        }))
      : []
  };
}

function normalizeTrade(trade: TopTrade): TopTrade {
  const optionType = String(trade.optionType || "CALL").toUpperCase() === "PUT" ? "PUT" : "CALL";
  const action = ["ENTER", "WATCH", "PASS"].includes(String(trade.action)) ? trade.action : "WATCH";
  const tier = ["A+", "A", "A-", "B+", "B"].includes(String(trade.tier)) ? trade.tier : "B";
  const signalStrength = ["STRONG", "MODERATE", "WEAK", "UNKNOWN"].includes(String(trade.signalStrength))
    ? trade.signalStrength
    : "UNKNOWN";

  return {
    ...trade,
    rank: Number(trade.rank) || 0,
    ticker: String(trade.ticker || "N/A"),
    companyName: trade.companyName ?? null,
    tier,
    action,
    optionType,
    signalStrength,
    contract: {
      optionSymbol: trade.contract?.optionSymbol || `${trade.ticker || "UNKNOWN"}-${trade.rank || 0}`,
      strike: Number(trade.contract?.strike) || 0,
      expiry: trade.contract?.expiry || "",
      dte: Number(trade.contract?.dte) || 0,
      underlyingPrice: Number(trade.contract?.underlyingPrice) || 0,
      distanceToStrikePct: Number(trade.contract?.distanceToStrikePct) || 0,
      moneyness: trade.contract?.moneyness ?? null,
      itmFlag: trade.contract?.itmFlag ?? null,
      strikePositionLabel: trade.contract?.strikePositionLabel || "N/A",
      strikePositionText: trade.contract?.strikePositionText || "N/A"
    },
    market: {
      volume: Number(trade.market?.volume) || 0,
      openInterest: Number(trade.market?.openInterest) || 0
    },
    context: {
      sector: trade.context?.sector || "Unknown",
      rsi: Number(trade.context?.rsi) || 0
    },
    etfOverlay: {
      etf: trade.etfOverlay?.etf || "N/A",
      bias: trade.etfOverlay?.bias || "Neutral",
      winRate4d: trade.etfOverlay?.winRate4d ?? null,
      breadth: trade.etfOverlay?.breadth ?? null
    },
    scores: {
      adaptiveScoreFinal: numberOrNull(trade.scores?.adaptiveScoreFinal),
      adaptiveScore: numberOrNull(trade.scores?.adaptiveScore),
      adaptiveRank: numberOrNull(trade.scores?.adaptiveRank),
      priorityScore: numberOrNull(trade.scores?.priorityScore),
      probCalibrated: numberOrNull(trade.scores?.probCalibrated),
      expectedValue: numberOrNull(trade.scores?.expectedValue),
      evPct: numberOrNull(trade.scores?.evPct),
      rankScore: numberOrNull(trade.scores?.rankScore),
      regimeAdj: numberOrNull(trade.scores?.regimeAdj),
      sectorScore: numberOrNull(trade.scores?.sectorScore),
      rsiScore: numberOrNull(trade.scores?.rsiScore)
    },
    classification: {
      predictedTierCal: trade.classification?.predictedTierCal ?? null,
      predictedTierRaw: trade.classification?.predictedTierRaw ?? null,
      adaptiveTier: trade.classification?.adaptiveTier ?? null,
      filteredTier: trade.classification?.filteredTier ?? null,
      dteBucket: trade.classification?.dteBucket ?? null,
      vixBucket: trade.classification?.vixBucket ?? null
    },
    execution: {
      liveEligible: boolOrNull(trade.execution?.liveEligible),
      selected: boolOrNull(trade.execution?.selected),
      aPlus: boolOrNull(trade.execution?.aPlus),
      rankAlpha: boolOrNull(trade.execution?.rankAlpha),
      failReason: trade.execution?.failReason ?? null
    },
    risk: {
      midPrice: numberOrNull(trade.risk?.midPrice),
      bidAskPct: numberOrNull(trade.risk?.bidAskPct),
      bidOk: boolOrNull(trade.risk?.bidOk),
      volumeOk: boolOrNull(trade.risk?.volumeOk),
      dteOk: boolOrNull(trade.risk?.dteOk),
      spyTrendOk: boolOrNull(trade.risk?.spyTrendOk),
      liquidityOk: boolOrNull(trade.risk?.liquidityOk),
      openInterestOk: boolOrNull(trade.risk?.openInterestOk)
    },
    executionGuidance: trade.executionGuidance
      ? {
          favorable: Array.isArray(trade.executionGuidance.favorable) ? trade.executionGuidance.favorable : [],
          caution: Array.isArray(trade.executionGuidance.caution) ? trade.executionGuidance.caution : [],
          unfavorable: Array.isArray(trade.executionGuidance.unfavorable) ? trade.executionGuidance.unfavorable : []
        }
      : undefined,
    decisionContext: trade.decisionContext
      ? {
          today: {
            rank: numberOrNull(trade.decisionContext.today?.rank),
            candidateCount: numberOrNull(trade.decisionContext.today?.candidateCount),
            topPercent: numberOrNull(trade.decisionContext.today?.topPercent),
            todayScore: numberOrNull(trade.decisionContext.today?.todayScore)
          },
          historical: {
            windowDays: numberOrNull(trade.decisionContext.historical?.windowDays),
            sampleSize: numberOrNull(trade.decisionContext.historical?.sampleSize),
            distinctTickerCount: numberOrNull((trade.decisionContext.historical as { distinctTickerCount?: unknown })?.distinctTickerCount),
            winRate: numberOrNull(trade.decisionContext.historical?.winRate),
            avgReturnPct: numberOrNull((trade.decisionContext.historical as { avgReturnPct?: unknown })?.avgReturnPct),
            avgRMultiple: numberOrNull(trade.decisionContext.historical?.avgRMultiple),
            medianHoldDays: numberOrNull(trade.decisionContext.historical?.medianHoldDays),
            holdP25Days: numberOrNull(trade.decisionContext.historical?.holdP25Days),
            holdP75Days: numberOrNull(trade.decisionContext.historical?.holdP75Days),
            cohortLabel: trade.decisionContext.historical?.cohortLabel ?? null,
            matchStrength: trade.decisionContext.historical?.matchStrength ?? null,
            supportLabel: trade.decisionContext.historical?.supportLabel ?? null
          },
          translation: trade.decisionContext.translation ?? null,
          executionEdge: Array.isArray(trade.decisionContext.executionEdge) ? trade.decisionContext.executionEdge : [],
          invalidation: Array.isArray(trade.decisionContext.invalidation) ? trade.decisionContext.invalidation : [],
          expectation: {
            timeframe: trade.decisionContext.expectation?.timeframe ?? null,
            baseCase: trade.decisionContext.expectation?.baseCase ?? null,
            risk: trade.decisionContext.expectation?.risk ?? null
          }
        }
      : undefined,
    provenance: {
      sourceFile: trade.provenance?.sourceFile ?? null,
      strategyStatsFile: trade.provenance?.strategyStatsFile ?? null,
      mlModelVersion: trade.provenance?.mlModelVersion ?? null,
      filterVersion: trade.provenance?.filterVersion ?? null,
      dataCutoff: trade.provenance?.dataCutoff ?? null,
      runTimestamp: trade.provenance?.runTimestamp ?? null,
      signalDate: trade.provenance?.signalDate ?? null
    }
  };
}

function normalizeSectorOutlook(sectors: DashboardData["sectorOutlook"] | undefined): SectorOutlook[] {
  if (!Array.isArray(sectors)) return [];

  return sectors.map((sector) => ({
    rank: Number(sector.rank) || 0,
    sector: String(sector.sector || "Unknown"),
    etf: String(sector.etf || "N/A"),
    bias: String(sector.bias || "Neutral"),
    totalSignals: Number(sector.totalSignals) || 0,
    strongSignalCount: numberOrNull(sector.strongSignalCount),
    aTierDensity: numberOrNull(sector.aTierDensity),
    netScore: numberOrNull(sector.netScore),
    convictionScore: numberOrNull(sector.convictionScore),
    flowSkew: String(sector.flowSkew || "Balanced"),
    visibleSetups: numberOrNull(sector.visibleSetups) ?? 0,
    topTickers: Array.isArray(sector.topTickers)
      ? sector.topTickers.map((ticker) => ({
          ticker: String(ticker.ticker || "N/A"),
          grade: ticker.grade ?? null,
          direction: ticker.direction ?? null,
          aGradeCount: Number(ticker.aGradeCount) || 0,
          signalCount: Number(ticker.signalCount) || 0
        }))
      : []
  }));
}

function normalizeYesterdayStatus(items: DashboardData["yesterdayStatus"] | undefined): DashboardData["yesterdayStatus"] {
  if (!Array.isArray(items)) return [];

    return items.map((item) => ({
      ticker: String(item.ticker || "N/A"),
      grade: item.grade ?? null,
      signalDate: item.signalDate ?? null,
      currentDate: item.currentDate ?? null,
      originalAction:
        item.originalAction === "ENTER" || item.originalAction === "WATCH" || item.originalAction === "WAIT"
          ? item.originalAction
          : null,
      snapshotPrice: numberOrNull(item.snapshotPrice),
      yesterdayEntryPrice: numberOrNull(item.yesterdayEntryPrice),
      currentPrice: numberOrNull(item.currentPrice),
    priceChangePct: numberOrNull(item.priceChangePct),
    typicalHoldDays: numberOrNull(item.typicalHoldDays),
    status: String(item.status || "No current price"),
    stillInTodayList: Boolean(item.stillInTodayList)
  }));
}

function numberOrNull(value: unknown): number | null {
  const numberValue = Number(value);
  return Number.isFinite(numberValue) ? numberValue : null;
}

function boolOrNull(value: unknown): boolean | null {
  if (typeof value === "boolean") return value;
  if (value === null || value === undefined) return null;
  const text = String(value).trim().toLowerCase();
  if (["1", "true", "yes", "y"].includes(text)) return true;
  if (["0", "false", "no", "n"].includes(text)) return false;
  return null;
}

function normalizeReturnDistribution(
  buckets: StrategyStats["returnDistribution"] | undefined,
  sampleSize: number | null
): NonNullable<StrategyStats["returnDistribution"]> {
  const collapsed = {
    "<-50%": 0,
    "-50%–0%": 0,
    "0–50%": 0,
    "50–150%": 0,
    ">150%": 0
  };

  for (const bucket of buckets ?? []) {
    const count = Number(bucket.count) || 0;
    const range = String(bucket.range || "");

    if (range === "<-50%" || range === "-50%–0%" || range === "0–50%" || range === "50–150%" || range === ">150%") {
      collapsed[range] += count;
      continue;
    }

    if (["<-100%", "-100% to -50%"].includes(range)) {
      collapsed["<-50%"] += count;
    } else if (["-50% to -20%", "-20% to 0%"].includes(range)) {
      collapsed["-50%–0%"] += count;
    } else if (["0% to 50%"].includes(range)) {
      collapsed["0–50%"] += count;
    } else if (["50% to 100%", "100% to 200%"].includes(range)) {
      collapsed["50–150%"] += count;
    } else if ([">200%"].includes(range)) {
      collapsed[">150%"] += count;
    }
  }

  const size = sampleSize ?? 0;
  return Object.entries(collapsed).map(([range, count]) => ({
    range,
    count,
    percentage: size ? roundToOneDecimal((count / size) * 100) : 0
  }));
}

function deriveLossProfile(
  buckets: StrategyStats["returnDistribution"] | undefined,
  sampleSize: number | null
): { lossRate: number | null; largeLossRate: number | null } {
  const size = sampleSize ?? 0;
  if (!size || !Array.isArray(buckets)) {
    return { lossRate: null, largeLossRate: null };
  }

  let negativeCount = 0;
  let largeLossCount = 0;

  for (const bucket of buckets) {
    const count = Number(bucket.count) || 0;
    const range = String(bucket.range || "");

    if (["<-100%", "-100% to -50%", "-50% to -20%", "-20% to 0%", "<-50%", "-50%–0%"].includes(range)) {
      negativeCount += count;
    }

    if (["<-100%", "-100% to -50%", "-50% to -20%", "<-50%"].includes(range)) {
      largeLossCount += count;
    }
  }

  return {
    lossRate: roundToOneDecimal((negativeCount / size) * 100),
    largeLossRate: roundToOneDecimal((largeLossCount / size) * 100)
  };
}

function roundToOneDecimal(value: number) {
  return Math.round(value * 10) / 10;
}
