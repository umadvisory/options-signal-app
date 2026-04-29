import type { TradeAction, TradeTier, TopTrade } from "@/types/dashboard";
import { getDecisionState } from "@/lib/trade-decision";

export type TradeFiltersState = {
  action: TradeAction | "ALL";
  tier: TradeTier | "ALL";
  sector: string;
  query: string;
};

type TradeFiltersProps = {
  filters: TradeFiltersState;
  sectors: string[];
  totalCount: number;
  visibleCount: number;
  actionableCount: number;
  showReview: boolean;
  onChange: (filters: TradeFiltersState) => void;
  onToggleReview: () => void;
};

export function TradeFilters({
  filters,
  sectors,
  totalCount,
  visibleCount,
  actionableCount,
  showReview,
  onChange,
  onToggleReview
}: TradeFiltersProps) {
  return (
    <section className="rounded-lg border border-slate-200 bg-white px-5 py-3.5 shadow-soft">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <p className="text-xs font-bold text-muted">Trade Workbench</p>
          <h2 className="mt-1 text-lg font-black text-ink">
            {showReview ? `${visibleCount} shown · ${actionableCount} actionable available` : `${visibleCount} visible setups`}
          </h2>
        </div>

        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-[180px_140px_170px_240px_190px]">
          <Select
            label="Action"
            value={filters.action}
            onChange={(value) => {
              const nextAction = normalizeActionOption(value);
              if ((nextAction === "WATCH" || nextAction === "WAIT") && showReview) {
                onToggleReview();
              }
              onChange({
                ...filters,
                action: nextAction
              });
            }}
            options={[
              { value: "ALL", label: "ALL" },
              { value: "ENTER", label: "ENTER" },
              { value: "WATCH", label: "WATCH" },
              { value: "WAIT", label: "WAIT" }
            ]}
          />
          <Select
            label="Tier"
            value={filters.tier}
            onChange={(value) => onChange({ ...filters, tier: value as TradeFiltersState["tier"] })}
            options={["ALL", "A+", "A", "A-", "B+", "B"].map((value) => ({ value, label: value }))}
          />
          <Select
            label="Sector"
            value={filters.sector}
            onChange={(value) => onChange({ ...filters, sector: value })}
            options={["ALL", ...sectors].map((value) => ({ value, label: value }))}
          />
          <label className="flex flex-col gap-1.5">
            <span className="text-[11px] font-bold text-muted">Search</span>
            <input
              value={filters.query}
              onChange={(event) => onChange({ ...filters, query: event.target.value })}
              placeholder="Ticker, company, sector"
              className="h-10 rounded-md border border-slate-200 bg-slate-50 px-3 text-sm font-bold text-ink outline-none transition placeholder:text-slate-400 focus:border-blue-400 focus:bg-white"
            />
          </label>
          <div className="flex flex-col gap-1.5">
            <span className="text-[11px] font-bold text-muted">Show actionable setups (ENTER only)</span>
            <button
              type="button"
              onClick={onToggleReview}
              className={`h-10 rounded-md border px-3 text-sm font-black transition ${
                showReview
                  ? "border-blue-300 bg-blue-50 text-blue-700"
                  : "border-slate-200 bg-slate-50 text-slate-700 hover:border-blue-300 hover:text-blue-700"
              }`}
            >
              {showReview ? "ON" : "OFF"}
            </button>
          </div>
        </div>
      </div>
    </section>
  );
}

export function applyTradeFilters(trades: TopTrade[], filters: TradeFiltersState, showReview = false) {
  const query = filters.query.trim().toLowerCase();
  const selectedAction = normalizeActionOption(filters.action);

  return trades.filter((trade) => {
    const decisionAction = getDecisionState(trade).action;
    const normalizedTradeAction = normalizeActionOption(decisionAction);
    if (showReview && normalizedTradeAction !== "ENTER") return false;
    if (selectedAction !== "ALL" && normalizedTradeAction !== selectedAction) return false;
    if (filters.tier !== "ALL" && trade.tier !== filters.tier) return false;
    if (filters.sector !== "ALL" && trade.context.sector !== filters.sector) return false;

    if (!query) return true;

    return [
      trade.ticker,
      trade.companyName,
      trade.context.sector,
      trade.etfOverlay.etf,
      trade.etfOverlay.bias,
      trade.contract.optionSymbol
    ]
      .filter(Boolean)
      .some((value) => String(value).toLowerCase().includes(query));
  });
}

function Select({
  label,
  value,
  options,
  onChange
}: {
  label: string;
  value: string;
  options: Array<{ value: string; label: string }>;
  onChange: (value: string) => void;
}) {
  return (
    <label className="flex flex-col gap-1.5">
      <span className="text-[11px] font-bold text-muted">{label}</span>
      <select
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="h-10 rounded-md border border-slate-200 bg-slate-50 px-3 text-sm font-black text-ink outline-none transition focus:border-blue-400 focus:bg-white"
      >
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </label>
  );
}

function normalizeActionOption(value: string): TradeFiltersState["action"] {
  const normalized = String(value || "").trim().toUpperCase();
  if (normalized === "ENTER" || normalized === "WATCH" || normalized === "WAIT" || normalized === "ALL") {
    return normalized;
  }
  if (normalized === "PASS" || normalized === "REVIEW") {
    return "WAIT";
  }
  return "WATCH";
}
