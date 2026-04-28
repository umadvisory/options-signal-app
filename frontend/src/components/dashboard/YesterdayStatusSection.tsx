"use client";

import type { YesterdayTradeStatus } from "@/types/dashboard";

type TrackerRow = {
  ticker: string;
  signalDate: string | null;
  originalAction: "ENTER" | "WATCH" | "WAIT";
  changePct: number | null;
  state: "STABLE" | "PULLBACK" | "EXTENDED" | "OVEREXTENDED" | "BROKEN";
  action: string;
  entryQuality: string;
};

const STATE_PRIORITY: Record<TrackerRow["state"], number> = {
  STABLE: 0,
  PULLBACK: 1,
  EXTENDED: 2,
  OVEREXTENDED: 3,
  BROKEN: 4
};

const ACTION_PRIORITY: Record<TrackerRow["originalAction"], number> = {
  ENTER: 0,
  WATCH: 1,
  WAIT: 2
};

export function YesterdayStatusSection({
  items,
  fallbackSignalDate
}: {
  items: YesterdayTradeStatus[];
  fallbackSignalDate?: string | null;
}) {
  const activeRows = items
    .map((item) => buildTrackerRow(item, fallbackSignalDate ?? null))
    .filter((row): row is TrackerRow => row !== null)
    .sort((a, b) => {
      const aTime = toSortTime(a.signalDate);
      const bTime = toSortTime(b.signalDate);
      if (aTime !== bTime) return bTime - aTime;

      const actionPriority = ACTION_PRIORITY[a.originalAction] - ACTION_PRIORITY[b.originalAction];
      if (actionPriority !== 0) return actionPriority;

      return STATE_PRIORITY[a.state] - STATE_PRIORITY[b.state];
    })
    .slice(0, 12);

  if (!activeRows.length) return null;

  return (
    <section className="rounded-lg border border-slate-200 bg-white px-5 py-4 shadow-soft">
      <div className="flex items-center justify-between gap-4">
        <div>
          <h2 className="text-lg font-black text-ink">Recent Signals - Follow-Up</h2>
          <p className="mt-1 text-xs font-semibold text-muted">Follow-up on recent signals based on current price action.</p>
        </div>
        <p className="text-xs font-black text-muted">{activeRows.length} active signals</p>
      </div>

      <div className="mt-4 overflow-x-auto">
        <table className="min-w-full border-separate border-spacing-0 text-sm">
          <thead>
            <tr className="text-left">
              {["Ticker", "Signal Date", "Original Signal", "Change %", "State", "Entry Quality", "Action"].map((label) => (
                <th
                  key={label}
                  className="border-b border-slate-200 px-3 py-2 text-[11px] font-black uppercase tracking-[0.08em] text-muted"
                >
                  {label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {activeRows.map((row) => {
              const tone = getStateTone(row.state);

              return (
                <tr key={`${row.ticker}-${row.signalDate ?? "na"}`} className="hover:bg-slate-50">
                  <td className="border-b border-slate-100 px-3 py-3 font-black text-ink">{row.ticker}</td>
                  <td className="border-b border-slate-100 px-3 py-3 font-semibold text-slate-600">
                    {row.signalDate ? formatSignalDate(row.signalDate) : "N/A"}
                  </td>
                  <td className="border-b border-slate-100 px-3 py-3">
                    <span className={`inline-flex rounded-md px-2 py-1 text-[11px] font-black ${getOriginalActionTone(row.originalAction)}`}>
                      {row.originalAction}
                    </span>
                  </td>
                  <td className="border-b border-slate-100 px-3 py-3 font-semibold text-slate-700">
                    {row.changePct === null ? "N/A" : `${row.changePct > 0 ? "+" : ""}${row.changePct.toFixed(1)}%`}
                  </td>
                  <td className="border-b border-slate-100 px-3 py-3">
                    <span className={`inline-flex rounded-md px-2 py-1 text-[11px] font-black ${tone.badge}`}>{row.state}</span>
                  </td>
                  <td className="border-b border-slate-100 px-3 py-3 font-semibold text-slate-700">{row.entryQuality}</td>
                  <td className="border-b border-slate-100 px-3 py-3 font-semibold text-slate-700">{row.action}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function buildTrackerRow(item: YesterdayTradeStatus, fallbackSignalDate: string | null): TrackerRow | null {
  const signalDate = item.signalDate ?? fallbackSignalDate ?? null;
  const currentDate = item.currentDate ?? fallbackSignalDate ?? null;
  const typicalHoldDays = item.typicalHoldDays ?? null;
  const originalAction = item.originalAction ?? "WATCH";
  const changePct = item.priceChangePct ?? calculateChangePct(item.snapshotPrice ?? item.yesterdayEntryPrice, item.currentPrice);

  if (!signalDate || !currentDate || typicalHoldDays === null || typicalHoldDays === undefined) {
    return null;
  }

  const daysSinceSignal = diffDays(signalDate, currentDate);
  if (daysSinceSignal === null) {
    return null;
  }

  const activeWindow = Math.min(typicalHoldDays * 1.5, 14);
  if (daysSinceSignal > activeWindow) {
    return null;
  }

  const state = classifyState(changePct);
  return {
    ticker: item.ticker,
    signalDate,
    originalAction,
    changePct,
    state,
    action: mapAction(originalAction, state),
    entryQuality: mapEntryQuality(originalAction, state)
  };
}

function classifyState(changePct: number | null): TrackerRow["state"] {
  if (changePct === null) return "BROKEN";
  if (changePct <= -10) return "BROKEN";
  if (changePct <= -2) return "PULLBACK";
  if (changePct <= 2) return "STABLE";
  if (changePct <= 6) return "EXTENDED";
  return "OVEREXTENDED";
}

function mapAction(originalAction: TrackerRow["originalAction"], state: TrackerRow["state"]) {
  if (originalAction === "ENTER") {
    switch (state) {
      case "STABLE":
        return "Enter";
      case "PULLBACK":
        return "Enter (better price)";
      case "EXTENDED":
        return "Wait";
      case "OVEREXTENDED":
        return "Avoid new entry";
      case "BROKEN":
        return "Drop";
    }
  }

  if (originalAction === "WATCH") {
    switch (state) {
      case "STABLE":
        return "Watch";
      case "PULLBACK":
        return "Watch -> approaching entry";
      case "EXTENDED":
        return "Wait";
      case "OVEREXTENDED":
        return "Avoid";
      case "BROKEN":
        return "Drop";
    }
  }

  switch (state) {
    case "STABLE":
      return "Wait";
    case "PULLBACK":
      return "Watch";
    case "EXTENDED":
      return "Wait";
    case "OVEREXTENDED":
      return "Avoid";
    case "BROKEN":
      return "Drop";
  }
}

function mapEntryQuality(originalAction: TrackerRow["originalAction"], state: TrackerRow["state"]) {
  if (state === "BROKEN") return "Invalid";
  if (state === "OVEREXTENDED") return "Too late";
  if (state === "PULLBACK") return "Improving";
  if (state === "EXTENDED") return "Late";

  if (originalAction === "ENTER") return "Good";
  if (originalAction === "WATCH") return "Neutral";
  return "Waiting";
}

function getStateTone(state: TrackerRow["state"]) {
  switch (state) {
    case "STABLE":
      return { badge: "bg-emerald-50 text-emerald-700" };
    case "PULLBACK":
      return { badge: "bg-blue-50 text-blue-700" };
    case "EXTENDED":
      return { badge: "bg-amber-50 text-amber-700" };
    case "OVEREXTENDED":
      return { badge: "bg-red-50 text-red-700" };
    case "BROKEN":
      return { badge: "bg-slate-100 text-slate-600" };
  }
}

function getOriginalActionTone(action: TrackerRow["originalAction"]) {
  switch (action) {
    case "ENTER":
      return "bg-emerald-50 text-emerald-700";
    case "WATCH":
      return "bg-amber-50 text-amber-700";
    case "WAIT":
      return "bg-slate-100 text-slate-700";
  }
}

function calculateChangePct(snapshotPrice: number | null | undefined, currentPrice: number | null) {
  if (snapshotPrice === null || snapshotPrice === undefined || snapshotPrice === 0 || currentPrice === null) {
    return null;
  }

  return Number((((currentPrice - snapshotPrice) / snapshotPrice) * 100).toFixed(1));
}

function diffDays(start: string, end: string) {
  const startDate = new Date(start);
  const endDate = new Date(end);
  if (Number.isNaN(startDate.getTime()) || Number.isNaN(endDate.getTime())) {
    return null;
  }

  return Math.floor((endDate.getTime() - startDate.getTime()) / (1000 * 60 * 60 * 24));
}

function toSortTime(value: string | null) {
  if (!value) return 0;
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? 0 : parsed.getTime();
}

function formatSignalDate(value: string) {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;

  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric"
  }).format(parsed);
}
