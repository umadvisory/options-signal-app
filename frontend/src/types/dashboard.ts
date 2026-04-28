export type TradeAction = "ENTER" | "WATCH" | "PASS";
export type TradeTier = "A+" | "A" | "A-" | "B+" | "B";

export type StrategyStats = {
  winRate: number | null;
  sampleSize: number | null;
  tickerCount?: number | null;
  minDate?: string | null;
  maxDate?: string | null;
  avgReturnPct: number | null;
  medianReturnPct: number | null;
  worstDrawdownProxy?: number | null;
  lossRate?: number | null;
  largeLossRate?: number | null;
  returnDistribution?: Array<{
    range: string;
    count: number;
    percentage?: number | null;
  }>;
  equityCurve?: Array<{
    date: string;
    value: number | null;
  }>;
};

export type TopTrade = {
  rank: number;
  ticker: string;
  companyName: string | null;
  tier: TradeTier;
  action: TradeAction;
  optionType: "CALL" | "PUT";
  signalStrength: "STRONG" | "MODERATE" | "WEAK" | "UNKNOWN";
  contract: {
    optionSymbol: string;
    strike: number;
    expiry: string;
    dte: number;
    underlyingPrice: number;
    distanceToStrikePct: number;
    moneyness: string | null;
    itmFlag: string | null;
    strikePositionLabel: string;
    strikePositionText: string;
  };
  market: {
    volume: number;
    openInterest: number;
  };
  context: {
    sector: string;
    rsi: number;
  };
  etfOverlay: {
    etf: string;
    bias: string;
    winRate4d: number | null;
    breadth: number | null;
  };
  scores: {
    adaptiveScoreFinal: number | null;
    adaptiveScore: number | null;
    adaptiveRank: number | null;
    priorityScore: number | null;
    probCalibrated: number | null;
    expectedValue: number | null;
    evPct: number | null;
    rankScore: number | null;
    regimeAdj: number | null;
    sectorScore: number | null;
    rsiScore: number | null;
  };
  classification: {
    predictedTierCal: string | null;
    predictedTierRaw: string | null;
    adaptiveTier: string | null;
    filteredTier: string | null;
    dteBucket: string | null;
    vixBucket: string | null;
  };
  execution: {
    liveEligible: boolean | null;
    selected: boolean | null;
    aPlus: boolean | null;
    rankAlpha: boolean | null;
    failReason: string | null;
  };
  risk: {
    midPrice: number | null;
    bidAskPct: number | null;
    bidOk: boolean | null;
    volumeOk: boolean | null;
    dteOk: boolean | null;
    spyTrendOk: boolean | null;
    liquidityOk: boolean | null;
    openInterestOk: boolean | null;
  };
  executionGuidance?: {
    favorable: string[];
    caution: string[];
    unfavorable: string[];
  };
  decisionContext?: {
    today: {
      rank: number | null;
      candidateCount: number | null;
      topPercent: number | null;
      todayScore: number | null;
    };
    historical: {
      windowDays: number | null;
      sampleSize: number | null;
      distinctTickerCount: number | null;
      winRate: number | null;
      avgRMultiple: number | null;
      medianHoldDays: number | null;
      holdP25Days: number | null;
      holdP75Days: number | null;
      cohortLabel: string | null;
      matchStrength: string | null;
      supportLabel: string | null;
    };
    translation: string | null;
    executionEdge: string[];
    invalidation: string[];
    expectation: {
      timeframe: string | null;
      baseCase: string | null;
      risk: string | null;
    };
  };
  provenance: {
    sourceFile: string | null;
    strategyStatsFile: string | null;
    mlModelVersion: string | null;
    filterVersion: string | null;
    dataCutoff: string | null;
    runTimestamp: string | null;
    signalDate: string | null;
  };
};

export type WatchlistItem = {
  ticker: string;
  action: TradeAction;
  tier: TradeTier;
};

export type SectorContext = {
  sector: string;
  etf: string;
  bias: string;
  count: number;
  winRate4d: number;
  breadth: number;
  tickers: string[];
};

export type SectorOutlookTicker = {
  ticker: string;
  grade: string | null;
  direction: string | null;
  aGradeCount: number;
  signalCount: number;
};

export type SectorOutlook = {
  rank: number;
  sector: string;
  etf: string;
  bias: string;
  totalSignals: number;
  strongSignalCount: number | null;
  aTierDensity?: number | null;
  netScore: number | null;
  convictionScore: number | null;
  flowSkew: string;
  visibleSetups?: number;
  topTickers: SectorOutlookTicker[];
};

export type YesterdayTradeStatus = {
  ticker: string;
  grade: string | null;
  signalDate?: string | null;
  yesterdayEntryPrice: number | null;
  currentPrice: number | null;
  priceChangePct: number | null;
  status: string;
  stillInTodayList: boolean;
};

export type MarketRegime = {
  date: string | null;
  regime: string;
  summary: string;
  vix: {
    level: number | null;
    label: string;
    momentum3d: number | null;
    percentile: number | null;
  };
  spy: {
    return1d: number | null;
    trend3d: number | null;
    trend5d: number | null;
    trendLabel: string;
  };
  risk: {
    shockDay: boolean;
    trendStrength: number | null;
  };
};

export type DashboardData = {
  generatedAt: string;
  signalDate?: string | null;
  marketRegime: MarketRegime | null;
  watchlist: WatchlistItem[];
  strategyStats: {
    highConviction: StrategyStats;
    broadBase: StrategyStats;
  };
  trades: TopTrade[];
  sectorOutlook: SectorOutlook[];
  yesterdayStatus: YesterdayTradeStatus[];
};
