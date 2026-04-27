"use client";

import { useState } from "react";
import type { YesterdayTradeStatus } from "@/types/dashboard";

export function YesterdayStatusSection({ items, fallbackSignalDate }: { items: YesterdayTradeStatus[]; fallbackSignalDate?: string | null }) {
  const [showAll, setShowAll] = useState(false);

  if (!items.length) return null;

  const visibleItems = showAll ? items : items.slice(0, 5);

  return (
    <section className="rounded-lg border border-slate-200 bg-white px-5 py-4 shadow-soft">
      <div className="flex items-center justify-between gap-4">
        <div>
          <h2 className="text-lg font-black text-ink">Recent Signals - Status Update</h2>
          <p className="mt-1 text-xs font-semibold text-muted">Follow-up on recently ranked names versus latest price action.</p>
        </div>
        {items.length > 5 ? (
          <button
            type="button"
            onClick={() => setShowAll((current) => !current)}
            className="inline-flex h-9 items-center justify-center rounded-md border border-slate-200 bg-slate-50 px-4 text-xs font-black text-ink transition hover:border-blue-300 hover:bg-white hover:text-blue-700"
          >
            {showAll ? "Show less" : "Show all"}
          </button>
        ) : null}
      </div>

      <div className="mt-4 grid gap-3 lg:grid-cols-3">
        {visibleItems.map((item) => {
          const tone = getStatusTone(item.status);
          const signalDate = item.signalDate ?? fallbackSignalDate ?? null;

          return (
            <article key={item.ticker} className={`rounded-lg border p-4 ${tone.card}`}>
              <div className="flex items-center gap-2">
                <h3 className="text-base font-black text-ink">{item.ticker}</h3>
                {item.grade ? <span className="text-sm font-semibold text-muted">({item.grade})</span> : null}
              </div>
              <p className={`mt-3 text-sm font-black ${tone.text}`}>
                {item.status}
                {item.stillInTodayList ? <span className="font-semibold text-muted"> (still in today&apos;s list)</span> : null}
              </p>
              {item.priceChangePct !== null ? (
                <p className="mt-2 text-xs font-semibold text-muted">
                  Change since signal snapshot: {item.priceChangePct > 0 ? "+" : ""}
                  {item.priceChangePct}%
                </p>
              ) : (
                <p className="mt-2 text-xs font-semibold text-muted">Current price comparison unavailable.</p>
              )}
              {signalDate ? <p className="mt-2 text-[11px] font-semibold text-slate-500">Signal date: {formatSignalDate(signalDate)}</p> : null}
            </article>
          );
        })}
      </div>
    </section>
  );
}

function getStatusTone(status: string) {
  const normalized = status.toLowerCase();

  if (normalized.includes("still valid")) {
    return {
      card: "border-emerald-200 bg-emerald-50",
      text: "text-emerald-700"
    };
  }

  if (normalized.includes("extended")) {
    return {
      card: "border-red-200 bg-red-50",
      text: "text-red-700"
    };
  }

  return {
    card: "border-amber-200 bg-amber-50",
    text: "text-amber-700"
  };
}

function formatSignalDate(value: string) {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;

  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric"
  }).format(parsed);
}
