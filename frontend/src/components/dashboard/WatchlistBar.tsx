import { ActionBadge } from "@/components/ui/Badge";
import type { TopTrade, WatchlistItem, YesterdayTradeStatus } from "@/types/dashboard";

type TrackerRow = {
  ticker: string;
  originalAction: "ENTER" | "WATCH" | "WAIT";
  currentAction: "ENTER" | "WATCH" | "WAIT";
  movePct: number | null;
  signalDate: string | null;
  status: string;
  trade: TopTrade | null;
};

export function WatchlistBar({
  items,
  allTrades,
  yesterdayStatus,
  currentActionByTicker,
  onSelectTrade
}: {
  items: WatchlistItem[];
  allTrades: TopTrade[];
  yesterdayStatus: YesterdayTradeStatus[];
  currentActionByTicker?: Record<string, "ENTER" | "WATCH" | "WAIT">;
  onSelectTrade?: (trade: TopTrade) => void;
}) {
  if (items.length === 0) {
    return (
      <section className="rounded-lg border border-slate-200 bg-white px-5 py-3.5 shadow-soft">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <div className="flex items-center gap-3">
              <h2 className="text-base font-black text-ink">Follow-up Opportunities</h2>
              <span className="inline-flex h-6 min-w-6 items-center justify-center rounded-full bg-slate-100 px-2 text-xs font-black text-slate-600">
                0
              </span>
            </div>
            <p className="mt-1.5 text-xs font-semibold leading-5 text-muted">
              Track how saved setups evolve and where entries improve.
            </p>
          </div>
          <div className="inline-flex items-center rounded-md bg-slate-50 px-3 py-1.5 text-[11px] font-bold text-muted">
            Save setups from the Qualified Setups table
          </div>
        </div>
      </section>
    );
  }

  const rows = buildRows(items, allTrades, yesterdayStatus, currentActionByTicker);

  return (
    <section className="rounded-lg border border-slate-200 bg-slate-50/35 px-5 py-4 shadow-soft">
      <div className="flex flex-col gap-3">
        <div>
          <div className="flex items-center gap-3">
            <h2 className="text-base font-black text-ink">Follow-up Opportunities</h2>
            <span className="inline-flex h-6 min-w-6 items-center justify-center rounded-full bg-amber-100 px-2 text-xs font-black text-amber-700">
              {rows.length}
            </span>
          </div>
          <p className="mt-1.5 text-xs font-semibold leading-5 text-muted">
            Track how saved setups evolve and where entries improve.
          </p>
        </div>

        <div className="thin-scrollbar overflow-x-auto">
          <table className="min-w-[860px] w-full border-separate border-spacing-y-2 text-left">
            <thead>
              <tr className="text-[11px] font-semibold text-slate-500">
                {["Ticker", "Signal", "Move (since signal)", "Status", "Action"].map((label) => (
                  <th key={label} className="px-4 py-1.5">{label}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr
                  key={row.ticker}
                  onClick={() => row.trade && onSelectTrade?.(row.trade)}
                  className={`rounded-lg bg-white text-sm transition ${
                    row.trade ? "cursor-pointer hover:bg-blue-50/35 hover:shadow-[0_6px_16px_rgba(15,23,42,0.05)]" : ""
                  }`}
                >
                  <td className="px-4 py-3 text-[15px] font-black text-ink">{row.ticker}</td>
                  <td className="px-4 py-3 text-xs font-bold tracking-[0.03em] text-slate-700">
                    {row.originalAction !== row.currentAction ? (
                      <>
                        <span className="text-ink">
                          {row.originalAction} <span className="px-1 text-slate-900">→</span> {row.currentAction}
                        </span>
                        {row.signalDate ? <span className="ml-1 text-slate-500">({formatShortDate(row.signalDate)})</span> : null}
                      </>
                    ) : (
                      <>
                        <span className="text-slate-700">{row.currentAction}</span>
                        {row.movePct === null ? <span className="ml-1 text-[11px] font-semibold tracking-normal text-slate-500">• New</span> : null}
                      </>
                    )}
                  </td>
                  <td className={`px-4 py-3 text-center text-xs font-semibold ${moveTone(row.movePct)}`}>
                    {formatMove(row.movePct)}
                  </td>
                  <td className="px-4 py-3 text-xs font-semibold text-slate-500">{row.status}</td>
                  <td className="px-4 py-3">
                    <ActionBadge action={row.currentAction} className="h-9 min-w-[92px] text-xs" />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </section>
  );
}

function buildRows(
  items: WatchlistItem[],
  allTrades: TopTrade[],
  yesterdayStatus: YesterdayTradeStatus[],
  currentActionByTicker?: Record<string, "ENTER" | "WATCH" | "WAIT">
): TrackerRow[] {
  const tradeByTicker = new Map(allTrades.map((trade) => [trade.ticker, trade] as const));
  const statusByTicker = new Map(yesterdayStatus.map((row) => [row.ticker, row] as const));

  return items.map((item) => {
    const statusRow = statusByTicker.get(item.ticker);
    const currentAction = currentActionByTicker?.[item.ticker] ?? tradeByTicker.get(item.ticker)?.action ?? item.action;
    const movePct = Number.isFinite(statusRow?.priceChangePct as number) ? (statusRow?.priceChangePct as number) : null;

    return {
      ticker: item.ticker,
      originalAction: item.action,
      currentAction,
      movePct,
      signalDate: statusRow?.signalDate ?? null,
      status: interpretStatus(item.action, currentAction, movePct),
      trade: tradeByTicker.get(item.ticker) ?? null
    };
  });
}

function interpretStatus(
  originalAction: "ENTER" | "WATCH" | "WAIT",
  currentAction: "ENTER" | "WATCH" | "WAIT",
  movePct: number | null
) {
  if (movePct === null || !Number.isFinite(movePct)) return "Setup intact";
  if (movePct < 0) return "Pullback forming";
  if (movePct > 0 && movePct <= 2) return "Holding strength";
  if (movePct > 2) return "Extended — wait";
  return "Setup intact";
}

function formatMove(value: number | null) {
  if (value === null) return "—";
  return `${value > 0 ? "+" : ""}${value.toFixed(1)}%`;
}

function moveTone(value: number | null) {
  if (value === null) return "text-slate-400";
  if (value > 0) return "text-emerald-600";
  if (value < 0) return "text-red-500";
  return "text-slate-600";
}

function formatShortDate(value: string) {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;

  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric"
  }).format(parsed);
}
