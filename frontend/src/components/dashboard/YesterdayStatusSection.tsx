"use client";

import { useEffect, useMemo, useState, type ReactNode } from "react";
import type { YesterdayTradeStatus } from "@/types/dashboard";

type TrackerState = "PULLBACK" | "STABLE" | "EXTENDED" | "BROKEN" | "OVEREXTENDED" | "PLAYED OUT";
type TrackerAction = "ENTER" | "ENTER (better price)" | "WATCH (near entry)" | "WATCH" | "WAIT" | "DROP";
type GroupKey = "REENTRY" | "NEAR_ENTRY" | "PASSIVE_MONITOR";

type TrackerRow = {
  ticker: string;
  rawSignalDate: string;
  displaySignalDate: string;
  originalAction: "ENTER" | "WATCH" | "WAIT";
  todayAction: "ENTER" | "WATCH" | "WAIT" | null;
  changePct: number;
  state: TrackerState;
  finalAction: TrackerAction;
  group: GroupKey;
  statusNote: string | null;
};

const ACTION_PRIORITY: Record<TrackerAction, number> = {
  "ENTER": 0,
  "ENTER (better price)": 1,
  "WATCH (near entry)": 2,
  "WATCH": 3,
  "WAIT": 4,
  "DROP": 5
};

const GROUP_ORDER: GroupKey[] = ["REENTRY", "NEAR_ENTRY", "PASSIVE_MONITOR"];

export function YesterdayStatusSection({
  items,
  fallbackSignalDate,
  workbenchActionMap
}: {
  items: YesterdayTradeStatus[];
  fallbackSignalDate?: string | null;
  workbenchActionMap?: Record<string, "ENTER" | "WATCH" | "WAIT">;
}) {
  const activeRows = items
    .map((item) => buildTrackerRow(item, fallbackSignalDate ?? null, workbenchActionMap ?? {}))
    .filter((row): row is TrackerRow => row !== null)
    .sort((a, b) => {
      if (a.group !== b.group) return GROUP_ORDER.indexOf(a.group) - GROUP_ORDER.indexOf(b.group);

      const aTime = toSortTime(a.displaySignalDate);
      const bTime = toSortTime(b.displaySignalDate);
      if (aTime !== bTime) return bTime - aTime;

      return ACTION_PRIORITY[a.finalAction] - ACTION_PRIORITY[b.finalAction];
    });

  if (!activeRows.length) return null;

  const signalDateOptions = useMemo(
    () =>
      Array.from(new Set(activeRows.map((row) => row.displaySignalDate))).sort(
        (a, b) => toSortTime(b) - toSortTime(a)
      ),
    [activeRows]
  );
  const [selectedSignalDate, setSelectedSignalDate] = useState("");
  useEffect(() => {
    if (!signalDateOptions.length) {
      setSelectedSignalDate("ALL");
      return;
    }
    if (!selectedSignalDate) {
      setSelectedSignalDate(signalDateOptions[0]);
      return;
    }
    if (selectedSignalDate !== "ALL" && !signalDateOptions.includes(selectedSignalDate)) {
      setSelectedSignalDate(signalDateOptions[0]);
    }
  }, [selectedSignalDate, signalDateOptions]);

  const scopedRows = useMemo(() => {
    if (selectedSignalDate === "ALL") return activeRows;
    return activeRows.filter((row) => row.displaySignalDate === selectedSignalDate);
  }, [activeRows, selectedSignalDate]);

  const reEntryRows = scopedRows.filter((row) => row.group === "REENTRY");
  const nearEntryRows = scopedRows.filter((row) => row.group === "NEAR_ENTRY");
  const passiveMonitorRows = scopedRows.filter((row) => row.group === "PASSIVE_MONITOR");
  const [showAllMonitor, setShowAllMonitor] = useState(false);
  const [activeOnlyMonitor, setActiveOnlyMonitor] = useState(false);
  const monitorCollapsedByDefault = passiveMonitorRows.length > 0;

  useEffect(() => {
    setShowAllMonitor(false);
    setActiveOnlyMonitor(false);
  }, [passiveMonitorRows.length]);

  const visibleMonitorRows = useMemo(() => {
    if (!monitorCollapsedByDefault || showAllMonitor) {
      if (!activeOnlyMonitor) return passiveMonitorRows;
      return passiveMonitorRows.filter((row) => row.finalAction === "WATCH" || row.finalAction === "ENTER");
    }
    return [];
  }, [activeOnlyMonitor, monitorCollapsedByDefault, passiveMonitorRows, showAllMonitor]);

  return (
    <section className="rounded-lg border border-slate-200 bg-white px-5 py-4 shadow-soft">
      <div className="flex items-center justify-between gap-4">
        <div>
          <h2 className="text-lg font-black text-ink">Recent Signals - Follow-Up</h2>
          <p className="mt-1 text-xs font-semibold text-muted">
            Tracks recent signals through their active lifecycle based on price action.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <label className="flex items-center gap-2 text-xs font-semibold text-muted">
            <span>Signal Date</span>
            <select
              value={selectedSignalDate}
              onChange={(event) => setSelectedSignalDate(event.target.value)}
              className="h-8 rounded-md border border-slate-200 bg-slate-50 px-2 text-xs font-bold text-ink outline-none transition focus:border-blue-400 focus:bg-white"
            >
              <option value="ALL">All dates</option>
              {signalDateOptions.map((date) => (
                <option key={date} value={date}>
                  {formatSignalDate(date)}
                </option>
              ))}
            </select>
          </label>
          <p className="text-xs font-black text-muted">
            {reEntryRows.length} re-entry · {nearEntryRows.length} near entry · {passiveMonitorRows.length} monitor
          </p>
        </div>
      </div>

      <div className="mt-4 space-y-5">
        {reEntryRows.length ? (
          <FollowUpGroup title="Re-Entry Opportunities" rows={reEntryRows} />
        ) : null}
        {nearEntryRows.length ? (
          <FollowUpGroup title={`Near Entry (${nearEntryRows.length})`} rows={nearEntryRows} />
        ) : null}
        {passiveMonitorRows.length ? (
          <div>
            <div className="flex items-center justify-between gap-3">
              <h3 className="text-xs font-black uppercase tracking-[0.08em] text-muted">
                Passive Monitor ({passiveMonitorRows.length})
              </h3>
              <div className="flex items-center gap-3">
                <label className="inline-flex items-center gap-2 text-[11px] font-semibold text-muted">
                  <input
                    type="checkbox"
                    checked={activeOnlyMonitor}
                    onChange={(event) => setActiveOnlyMonitor(event.target.checked)}
                    className="h-3.5 w-3.5 rounded border-slate-300 text-blue-600"
                  />
                  Active setups only
                </label>
                <button
                  type="button"
                  onClick={() => setShowAllMonitor((current) => !current)}
                  className="text-xs font-black text-blue-700 transition hover:text-blue-800"
                >
                  {showAllMonitor ? "Hide Passive Monitor" : `Show Passive Monitor (${passiveMonitorRows.length})`}
                </button>
              </div>
            </div>
            <p className="mt-1 text-[11px] font-semibold text-muted">
              WATCH = valid setup, timing not ideal • WAIT = extended or no clean entry
            </p>
            {showAllMonitor ? <FollowUpGroup title="" rows={visibleMonitorRows} hideTitle /> : null}
            {showAllMonitor && activeOnlyMonitor && visibleMonitorRows.length === 0 ? (
              <p className="mt-2 text-[11px] font-semibold text-muted">No active setups right now</p>
            ) : null}
          </div>
        ) : null}
      </div>
    </section>
  );
}

function FollowUpGroup({
  title,
  rows,
  footer,
  hideTitle = false
}: {
  title: string;
  rows: TrackerRow[];
  footer?: ReactNode;
  hideTitle?: boolean;
}) {
  return (
    <div>
      {!hideTitle ? <h3 className="text-xs font-black uppercase tracking-[0.08em] text-muted">{title}</h3> : null}
      <div className="mt-2 overflow-x-auto">
        <table className="min-w-full border-separate border-spacing-0 text-sm">
          <thead>
            <tr className="text-left">
              {["Ticker", "Signal Date", "Original Signal", "Underlying Ticker Move %", "Setup Status", "Follow-Up Action"].map((label) => (
                <th
                  key={label}
                  className={`border-b border-slate-200 px-2.5 py-2 text-[11px] font-black uppercase tracking-[0.08em] text-muted ${
                    label === "Follow-Up Action" ? "pl-4" : ""
                  } ${label === "Underlying Ticker Move %" ? "text-right" : "text-left"}`}
                >
                  {label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => {
              const tone = getStateTone(row.state);

              return (
                <tr key={`${row.ticker}-${row.rawSignalDate}`} className="hover:bg-slate-50">
                  <td className="border-b border-slate-100 px-2.5 py-2.5 font-black text-ink">{row.ticker}</td>
                  <td className="border-b border-slate-100 px-2.5 py-2.5 font-semibold text-slate-600">
                    {formatSignalDate(row.displaySignalDate)}
                  </td>
                  <td className="border-b border-slate-100 px-2.5 py-2.5">
                    <span className={`inline-flex rounded-md px-1.5 py-0.5 text-[10px] font-semibold ${getOriginalActionTone(row.originalAction)}`}>
                      {row.originalAction}
                    </span>
                  </td>
                  <td className="border-b border-slate-100 px-2.5 py-2.5 text-right font-semibold tabular-nums text-slate-700">
                    {row.changePct > 0 ? "+" : ""}
                    {row.changePct.toFixed(1)}%
                  </td>
                  <td className="border-b border-slate-100 px-2.5 py-2.5">
                    <span className={`inline-flex rounded-md px-2 py-1 text-[11px] font-black ${tone.badge}`}>
                      {formatStateLabel(row.state)}
                    </span>
                  </td>
                  <td className="border-b border-slate-100 px-2.5 py-2.5 pl-4">
                    <span
                      title={getActionTooltip(row.finalAction)}
                      aria-label={getActionTooltip(row.finalAction)}
                      className={`inline-flex h-8 min-w-[102px] items-center justify-center rounded-md px-3.5 text-[11px] font-black uppercase tracking-wide ${getFollowupActionTone(
                        row.finalAction
                      )}`}
                    >
                      {row.finalAction}
                    </span>
                    {row.statusNote ? (
                      <div className="mt-1 text-[11px] font-semibold text-muted">{row.statusNote}</div>
                    ) : null}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      {footer ? <div className="mt-2">{footer}</div> : null}
    </div>
  );
}

function buildTrackerRow(
  item: YesterdayTradeStatus,
  fallbackSignalDate: string | null,
  workbenchActionMap: Record<string, "ENTER" | "WATCH" | "WAIT">
): TrackerRow | null {
  const signalDate = item.signalDate ?? fallbackSignalDate ?? null;
  const currentDate = item.currentDate ?? fallbackSignalDate ?? null;
  const originalAction = item.originalAction ?? "WATCH";
  const snapshotPrice = item.snapshotPrice ?? item.yesterdayEntryPrice ?? null;
  const currentPrice = item.currentPrice ?? null;

  if (!signalDate || !currentDate) return null;

  const displaySignalDate = normalizeIsoDate(signalDate) ?? signalDate;

  const daysSinceSignal = diffDays(displaySignalDate, currentDate);
  if (daysSinceSignal === null || daysSinceSignal > 14) {
    return null;
  }

  if (snapshotPrice === null || currentPrice === null) {
    return null;
  }

  const changePct = item.priceChangePct ?? calculateChangePct(snapshotPrice, currentPrice);
  if (changePct === null) {
    return null;
  }

  const state = normalizeState(item.followupState) ?? classifyState(changePct);
  if (state === "BROKEN" || state === "OVEREXTENDED" || state === "PLAYED OUT") {
    return null;
  }

  const todayAction = workbenchActionMap[item.ticker] ?? null;
  if (todayAction === "ENTER") {
    return null;
  }
  const rawAction = normalizeTrackerAction(item.rawFollowupAction) ?? mapAction(originalAction, state);
  const { finalAction, statusNote } = capAction(rawAction, todayAction, item.statusNote ?? null);
  if (finalAction === "DROP") {
    return null;
  }
  const group = getGroup(finalAction);
  if (!group) {
    return null;
  }

  return {
    ticker: item.ticker,
    rawSignalDate: signalDate,
    displaySignalDate,
    originalAction,
    todayAction,
    changePct,
    state,
    finalAction,
    group,
    statusNote
  };
}

function classifyState(changePct: number): TrackerState {
  if (changePct <= -12) return "BROKEN";
  if (changePct <= -3) return "PULLBACK";
  if (changePct <= 2) return "STABLE";
  if (changePct <= 6) return "EXTENDED";
  if (changePct < 20) return "OVEREXTENDED";
  return "PLAYED OUT";
}

function mapAction(originalAction: TrackerRow["originalAction"], state: TrackerState): TrackerAction {
  if (originalAction === "ENTER") {
    switch (state) {
      case "PULLBACK":
        return "ENTER (better price)";
      case "STABLE":
        return "ENTER";
      case "EXTENDED":
        return "WAIT";
      case "BROKEN":
      case "OVEREXTENDED":
      case "PLAYED OUT":
        return "DROP";
    }
  }

  if (originalAction === "WATCH") {
    switch (state) {
      case "PULLBACK":
        return "WATCH (near entry)";
      case "STABLE":
        return "WATCH";
      case "EXTENDED":
        return "WAIT";
      case "BROKEN":
      case "OVEREXTENDED":
      case "PLAYED OUT":
        return "DROP";
    }
  }

  switch (state) {
    case "PULLBACK":
      return "WATCH";
    case "STABLE":
    case "EXTENDED":
      return "WAIT";
    case "BROKEN":
    case "OVEREXTENDED":
    case "PLAYED OUT":
      return "DROP";
  }
}

function capAction(
  rawAction: TrackerAction,
  todayAction: TrackerRow["todayAction"],
  fallbackNote: string | null
) {
  const normalizedFallback = normalizeStatusNote(fallbackNote, todayAction);

  if (todayAction === "WAIT" && rawAction !== "WAIT" && rawAction !== "DROP") {
    return {
      finalAction: "WAIT" as TrackerAction,
      statusNote: normalizedFallback ?? "Prior setup improved, but today's signal remains WAIT."
    };
  }

  if (todayAction === "WATCH" && rawAction.startsWith("ENTER")) {
    return {
      finalAction: "WATCH" as TrackerAction,
      statusNote: normalizedFallback ?? "Prior setup improved, but today's signal remains WATCH."
    };
  }

  if (todayAction === "WATCH" && rawAction !== "DROP" && rawAction !== "WAIT") {
    return {
      finalAction: "WATCH" as TrackerAction,
      statusNote: normalizedFallback ?? "Prior setup improved, and today's signal remains WATCH."
    };
  }

  return { finalAction: rawAction, statusNote: normalizedFallback };
}

function normalizeStatusNote(
  note: string | null,
  todayAction: TrackerRow["todayAction"]
) {
  if (!note) return null;
  const text = note.trim();
  if (!text) return null;
  if (todayAction === "WATCH" && text.toUpperCase().includes("REMAINS WAIT")) {
    return "Prior setup improved, and today's signal remains WATCH.";
  }
  if (todayAction === "WAIT" && text.toUpperCase().includes("REMAINS WATCH")) {
    return "Prior setup improved, but today's signal remains WAIT.";
  }
  return text;
}

function getGroup(action: TrackerAction): GroupKey | null {
  if (action === "ENTER" || action === "ENTER (better price)") {
    return "REENTRY";
  }
  if (action === "WATCH (near entry)") {
    return "NEAR_ENTRY";
  }
  if (action === "WATCH" || action === "WAIT") {
    return "PASSIVE_MONITOR";
  }
  return null;
}

function formatStateLabel(state: TrackerState) {
  switch (state) {
    case "PULLBACK":
      return "Pullback forming";
    case "STABLE":
      return "Stable";
    case "EXTENDED":
      return "Extended";
    case "BROKEN":
      return "Broken";
    case "OVEREXTENDED":
      return "Overextended";
    case "PLAYED OUT":
      return "Played out";
  }
}

function getStateTone(state: TrackerState) {
  return { badge: "bg-slate-100 text-slate-600 ring-1 ring-slate-200 text-[10px] font-semibold" };
}

function getOriginalActionTone(action: TrackerRow["originalAction"]) {
  switch (action) {
    case "ENTER":
      return "bg-slate-100 text-slate-500";
    case "WATCH":
      return "bg-slate-100 text-slate-500";
    case "WAIT":
      return "bg-slate-100 text-slate-500";
  }
}

function getFollowupActionTone(action: TrackerAction) {
  if (action === "ENTER" || action === "ENTER (better price)") {
    return "bg-emerald-600 text-white ring-1 ring-emerald-300 shadow-[0_10px_24px_rgba(5,150,105,0.28)]";
  }
  if (action === "WATCH" || action === "WATCH (near entry)") {
    return "bg-amber-500 text-white shadow-[0_8px_18px_rgba(245,158,11,0.22)]";
  }
  return "bg-red-600 text-white shadow-[0_8px_18px_rgba(220,38,38,0.22)]";
}

function getActionTooltip(action: TrackerAction) {
  if (action === "ENTER" || action === "ENTER (better price)") return "Good entry conditions";
  if (action === "WATCH" || action === "WATCH (near entry)") return "Valid setup, timing not ideal";
  return "Extended or no clean entry";
}

function calculateChangePct(snapshotPrice: number, currentPrice: number) {
  if (!snapshotPrice || currentPrice === null) {
    return null;
  }

  return Number((((currentPrice - snapshotPrice) / snapshotPrice) * 100).toFixed(1));
}

function normalizeState(value: string | null | undefined): TrackerState | null {
  switch ((value ?? "").trim().toUpperCase()) {
    case "PULLBACK":
      return "PULLBACK";
    case "STABLE":
      return "STABLE";
    case "EXTENDED":
      return "EXTENDED";
    case "BROKEN":
      return "BROKEN";
    case "OVEREXTENDED":
      return "OVEREXTENDED";
    case "PLAYED_OUT":
    case "PLAYED OUT":
      return "PLAYED OUT";
    default:
      return null;
  }
}

function normalizeTrackerAction(value: string | null | undefined): TrackerAction | null {
  switch ((value ?? "").trim()) {
    case "ENTER":
    case "ENTER (better price)":
    case "WATCH (near entry)":
    case "WATCH":
    case "WAIT":
    case "DROP":
      return value!.trim() as TrackerAction;
    default:
      return null;
  }
}

function diffDays(start: string, end: string) {
  const startParts = parseIsoDateParts(start);
  const endParts = parseIsoDateParts(end);
  if (!startParts || !endParts) {
    return null;
  }

  const startUtc = Date.UTC(startParts.year, startParts.month - 1, startParts.day);
  const endUtc = Date.UTC(endParts.year, endParts.month - 1, endParts.day);
  return Math.floor((endUtc - startUtc) / (1000 * 60 * 60 * 24));
}

function toSortTime(value: string) {
  const parts = parseIsoDateParts(value);
  return parts ? Date.UTC(parts.year, parts.month - 1, parts.day) : 0;
}

function formatSignalDate(value: string) {
  const parts = parseIsoDateParts(value);
  if (!parts) return value;
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    timeZone: "UTC"
  }).format(new Date(Date.UTC(parts.year, parts.month - 1, parts.day)));
}

function normalizeIsoDate(value: string) {
  const parts = parseIsoDateParts(value);
  if (!parts) return null;
  return `${parts.year.toString().padStart(4, "0")}-${parts.month.toString().padStart(2, "0")}-${parts.day
    .toString()
    .padStart(2, "0")}`;
}

function parseIsoDateParts(value: string) {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(value).trim());
  if (!match) return null;
  return {
    year: Number(match[1]),
    month: Number(match[2]),
    day: Number(match[3])
  };
}
