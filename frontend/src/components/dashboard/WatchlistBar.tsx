import type { WatchlistItem } from "@/types/dashboard";
import { ActionBadge, TierBadge } from "@/components/ui/Badge";

export function WatchlistBar({ items }: { items: WatchlistItem[] }) {
  if (items.length === 0) {
    return (
      <section className="rounded-lg border border-slate-200 bg-white px-5 py-3.5 shadow-soft">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <div className="flex items-center gap-3">
              <h2 className="text-base font-black text-ink">Watchlist</h2>
              <span className="inline-flex h-6 min-w-6 items-center justify-center rounded-full bg-slate-100 px-2 text-xs font-black text-slate-600">
                0
              </span>
            </div>
            <p className="mt-1.5 text-xs font-semibold leading-5 text-muted">No saved setups yet for this session.</p>
          </div>
          <div className="inline-flex items-center rounded-md bg-slate-50 px-3 py-1.5 text-[11px] font-bold text-muted">
            Add setups from the trade drawer
          </div>
        </div>
      </section>
    );
  }

  return (
    <section className="rounded-lg border border-amber-200 bg-white px-5 py-4 shadow-soft">
      <div className="flex flex-col gap-3">
        <div>
          <div className="flex items-center gap-3">
            <h2 className="text-base font-black text-ink">Watchlist</h2>
            <span className="inline-flex h-6 min-w-6 items-center justify-center rounded-full bg-amber-100 px-2 text-xs font-black text-amber-700">
              {items.length}
            </span>
          </div>
          <p className="mt-1.5 text-xs font-semibold leading-5 text-muted">
            {items.length > 0 ? (
              <>Trades marked for follow-up from today&apos;s signal set.</>
            ) : (
              <>
                No tickers watched yet. Add setups from the trade drawer.
              </>
            )}
          </p>
        </div>

        {items.length > 0 ? (
          <div className="thin-scrollbar flex max-h-[160px] flex-wrap gap-2 overflow-y-auto pr-1 sm:flex-row">
            {items.map((item) => (
              <div
                key={item.ticker}
                className="grid min-w-[220px] grid-cols-[minmax(0,1fr)_52px_96px] items-center gap-2 rounded-md border border-slate-200 bg-slate-50 px-2.5 py-1.5"
              >
                <span className="truncate text-xs font-black text-ink">{item.ticker}</span>
                <TierBadge tier={item.tier} />
                <ActionBadge action={item.action} />
              </div>
            ))}
          </div>
        ) : null}
      </div>
    </section>
  );
}
