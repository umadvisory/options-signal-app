"use client";

import { useEffect, useMemo, useState } from "react";
import type { YesterdayTradeStatus } from "@/types/dashboard";

type FollowUpAction =
  | "ENTER"
  | "ENTER (BETTER PRICE)"
  | "HOLD"
  | "WATCH"
  | "WAIT"
  | "DO NOT ENTER";
type FollowGroup = "REENTRY" | "WORKING" | "PASSIVE";

type TrackerRow = {
  ticker: string;
  signalDate: string;
  currentDate: string;
  grade: string | null;
  sector: string | null;
  originalAction: "ENTER" | "WATCH" | "WAIT";
  todayAction: "ENTER" | "WATCH" | "WAIT" | null;
  movePct: number | null;
  setupStatus:
    | "Near entry"
    | "Still valid"
    | "Better price"
    | "Pullback forming"
    | "Follow-through"
  | "Follow-through / extended"
  | "Extended"
  | "Broken setup";
  followupAction: FollowUpAction;
  group: FollowGroup;
};

const ACTION_PRIORITY: Record<FollowUpAction, number> = {
  "ENTER": 0,
  "ENTER (BETTER PRICE)": 1,
  "HOLD": 2,
  "WATCH": 3,
  "WAIT": 4,
  "DO NOT ENTER": 5
};

export function YesterdayStatusSection({
  items,
  fallbackSignalDate,
  workbenchActionMap
}: {
  items: YesterdayTradeStatus[];
  fallbackSignalDate?: string | null;
  workbenchActionMap?: Record<string, "ENTER" | "WATCH" | "WAIT">;
}) {
  const baseRows = useMemo(
    () =>
      items
        .map((item) => buildTrackerRow(item, fallbackSignalDate ?? null, workbenchActionMap ?? {}))
        .filter((row): row is TrackerRow => row !== null)
        .sort((a, b) => {
          const dateSort = toSortTime(b.signalDate) - toSortTime(a.signalDate);
          if (dateSort !== 0) return dateSort;
          if (a.group !== b.group) return groupOrder(a.group) - groupOrder(b.group);
          if (a.followupAction !== b.followupAction) return ACTION_PRIORITY[a.followupAction] - ACTION_PRIORITY[b.followupAction];
          return a.ticker.localeCompare(b.ticker);
        }),
    [fallbackSignalDate, items, workbenchActionMap]
  );

  if (!baseRows.length) return null;

  const aGradeRows = baseRows.filter((row) => row.grade === "A+" || row.grade === "A");
  const scopedInputRows = aGradeRows.length > 0 ? aGradeRows : baseRows.slice(0, 16);

  const signalDateOptions = useMemo(
    () => Array.from(new Set(scopedInputRows.map((row) => row.signalDate))).sort((a, b) => toSortTime(b) - toSortTime(a)),
    [scopedInputRows]
  );
  const [selectedSignalDate, setSelectedSignalDate] = useState("");
  useEffect(() => {
    if (!signalDateOptions.length) {
      setSelectedSignalDate("ALL");
      return;
    }
    if (!selectedSignalDate || (selectedSignalDate !== "ALL" && !signalDateOptions.includes(selectedSignalDate))) {
      setSelectedSignalDate(signalDateOptions[0]);
    }
  }, [selectedSignalDate, signalDateOptions]);

  const scopedRows = useMemo(() => {
    return selectedSignalDate === "ALL"
      ? scopedInputRows
      : scopedInputRows.filter((row) => row.signalDate === selectedSignalDate);
  }, [scopedInputRows, selectedSignalDate]);

  const reEntryRows = scopedRows.filter((row) => row.group === "REENTRY");
  const workingRows = scopedRows.filter((row) => row.group === "WORKING");
  const passiveRows = scopedRows.filter((row) => row.group === "PASSIVE");
  const reEntryVisibleRows = reEntryRows.slice(0, 5);
  const workingVisibleRows = workingRows.slice(0, 5);
  const passiveVisibleRows = passiveRows.slice(0, 5);
  const [showPassive, setShowPassive] = useState(false);
  useEffect(() => setShowPassive(false), [selectedSignalDate, passiveRows.length]);

  return (
    <section className="rounded-lg border border-slate-200 bg-white px-5 py-4 shadow-soft">
      <div className="flex items-center justify-between gap-4">
        <div>
          <h2 className="text-lg font-black text-ink">Recent Signal Follow-Up</h2>
          <p className="mt-1 text-xs font-semibold text-muted">
            Tracks recent A+ and A setups after they appeared, highlighting better-price re-entries and follow-through.
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
            {reEntryRows.length} re-entry - {workingRows.length} follow-through - {passiveRows.length} monitor
          </p>
        </div>
      </div>

      <div className="mt-4 space-y-5">
        {reEntryRows.length > 0 ? <FollowUpGroup title="Re-Entry Opportunities" rows={reEntryVisibleRows} totalRows={reEntryRows.length} /> : null}
        {workingRows.length > 0 ? (
          <FollowUpGroup
            title="Signals That Worked"
            helperText="Signals that moved in the expected direction after the original setup."
            rows={workingVisibleRows}
            totalRows={workingRows.length}
          />
        ) : null}
        {passiveRows.length > 0 ? (
          <div>
            <div className="flex items-center justify-between gap-3">
              <h3 className="text-xs font-black uppercase tracking-[0.08em] text-muted">Passive Monitor ({passiveRows.length})</h3>
              <button
                type="button"
                onClick={() => setShowPassive((current) => !current)}
                className="text-xs font-black text-blue-700 transition hover:text-blue-800"
              >
                {showPassive ? "Hide Passive Monitor" : `Show Passive Monitor (${passiveRows.length})`}
              </button>
            </div>
            <p className="mt-1 text-[11px] font-semibold text-muted">WATCH = valid setup, timing not ideal - WAIT = extended or no clean entry</p>
            {showPassive ? <FollowUpGroup title="" rows={passiveVisibleRows} totalRows={passiveRows.length} hideTitle /> : null}
          </div>
        ) : null}
      </div>
    </section>
  );
}

function FollowUpGroup({
  title,
  helperText,
  rows,
  totalRows,
  hideTitle = false
}: {
  title: string;
  helperText?: string;
  rows: TrackerRow[];
  totalRows: number;
  hideTitle?: boolean;
}) {
  return (
    <div>
      {!hideTitle ? <h3 className="text-xs font-black uppercase tracking-[0.08em] text-muted">{title}</h3> : null}
      {!hideTitle && helperText ? <p className="mt-1 text-[11px] font-semibold text-muted">{helperText}</p> : null}
      <div className="mt-2 overflow-x-auto">
        <table className="min-w-full border-separate border-spacing-0 text-sm">
          <thead>
            <tr className="text-left">
              {["Ticker", "Signal Date", "Days Since", "Signal", "Move Since Signal", "Setup Status", "Follow-Up Action"].map((label) => (
                <th
                  key={label}
                  className={`border-b border-slate-200 px-2.5 py-2 text-[11px] font-black uppercase tracking-[0.08em] text-muted ${
                    label === "Move Since Signal" ? "text-right" : "text-left"
                  }`}
                >
                  {label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={`${row.ticker}-${row.signalDate}`} className="hover:bg-slate-50">
                <td className="border-b border-slate-100 px-2.5 py-2.5 font-black text-ink">{row.ticker}</td>
                <td className="border-b border-slate-100 px-2.5 py-2.5 font-semibold text-slate-600">{formatSignalDate(row.signalDate)}</td>
                <td className="border-b border-slate-100 px-2.5 py-2.5 text-xs font-semibold text-slate-600">{formatDaysSince(row.signalDate, row.currentDate)}</td>
                <td className="border-b border-slate-100 px-2.5 py-2.5">
                  <span className="inline-flex rounded-md bg-slate-100 px-1.5 py-0.5 text-[10px] font-semibold text-slate-600">
                    {row.originalAction}
                    {row.grade ? ` (${row.grade})` : ""}
                  </span>
                </td>
                <td className={`border-b border-slate-100 px-2.5 py-2.5 text-right font-semibold tabular-nums ${moveTone(row.movePct)}`}>
                  {formatMove(row.movePct)}
                </td>
                <td className="border-b border-slate-100 px-2.5 py-2.5">
                  <span className="inline-flex rounded-md bg-slate-100 px-2 py-1 text-[11px] font-black text-slate-600 ring-1 ring-slate-200">
                    {displayStatus(row)}
                  </span>
                </td>
                <td className="border-b border-slate-100 px-2.5 py-2.5">
                  <span className={`inline-flex h-8 min-w-[124px] items-center justify-center rounded-md px-3.5 text-[11px] font-black uppercase tracking-wide ${actionTone(displayAction(row))}`}>
                    {displayAction(row)}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {totalRows > rows.length ? (
        <p className="mt-2 text-[11px] font-semibold text-muted">Showing top 5 of {totalRows}</p>
      ) : null}
    </div>
  );
}

function buildTrackerRow(
  item: YesterdayTradeStatus,
  fallbackSignalDate: string | null,
  workbenchActionMap: Record<string, "ENTER" | "WATCH" | "WAIT">
): TrackerRow | null {
  const signalDate = normalizeIsoDate(item.signalDate ?? fallbackSignalDate ?? "");
  if (!signalDate) return null;

  const currentDate = normalizeIsoDate(item.currentDate ?? fallbackSignalDate ?? "");
  if (!currentDate) return null;
  const daysSinceSignal = diffDays(signalDate, currentDate);
  if (daysSinceSignal === null || daysSinceSignal > 14) return null;

  const snapshotPrice = item.snapshotPrice ?? item.yesterdayEntryPrice ?? null;
  const currentPrice = item.currentPrice ?? null;
  const snapshotValue = Number.isFinite(snapshotPrice as number) ? Number(snapshotPrice) : null;
  const currentValue = Number.isFinite(currentPrice as number) ? Number(currentPrice) : null;
  const movePct =
    Number.isFinite(item.priceChangePct as number)
      ? (item.priceChangePct as number)
      : snapshotValue !== null && currentValue !== null && snapshotValue !== 0
        ? Number((((currentValue - snapshotValue) / snapshotValue) * 100).toFixed(1))
        : null;

  const originalAction = item.originalAction ?? "WATCH";
  const todayAction = workbenchActionMap[item.ticker] ?? item.todayAction ?? null;
  const followupAction = deriveFollowupAction(originalAction, todayAction, movePct);
  const setupStatus = deriveStatus(movePct);
  const group = deriveGroup(originalAction, followupAction, movePct);

  return {
    ticker: item.ticker,
    signalDate,
    currentDate,
    grade: normalizeGrade(item.grade),
    sector: null,
    originalAction,
    todayAction,
    movePct,
    setupStatus,
    followupAction,
    group
  };
}

function deriveFollowupAction(
  _originalAction: "ENTER" | "WATCH" | "WAIT",
  _todayAction: "ENTER" | "WATCH" | "WAIT" | null,
  movePct: number | null
): FollowUpAction {
  const status = deriveStatus(movePct);

  // Hard contradiction rule: broken setups can never be entry/valid labels.
  if (status === "Broken setup") return "DO NOT ENTER";
  if (status === "Extended" || status === "Follow-through / extended") return "WAIT";
  if (status === "Better price" || status === "Pullback forming") return "ENTER (BETTER PRICE)";
  if (status === "Near entry" || status === "Still valid") return "ENTER";
  if (status === "Follow-through") return "HOLD";
  return "WATCH";
}

function deriveGroup(
  originalAction: "ENTER" | "WATCH" | "WAIT",
  followupAction: FollowUpAction,
  movePct: number | null
): FollowGroup {
  if (
    (originalAction === "ENTER" || originalAction === "WATCH") &&
    (followupAction === "ENTER" || followupAction === "ENTER (BETTER PRICE)") &&
    (movePct === null || movePct <= 1)
  ) {
    return "REENTRY";
  }
  if (movePct !== null && movePct >= 2) {
    return "WORKING";
  }
  return "PASSIVE";
}

function deriveStatus(movePct: number | null): TrackerRow["setupStatus"] {
  if (movePct === null) return "Still valid";
  if (movePct <= -8) return "Broken setup";
  if (movePct <= -3) return "Pullback forming";
  if (movePct < 0) return "Better price";
  if (movePct >= 5) return "Follow-through / extended";
  if (movePct > 2 && movePct < 5) return "Follow-through";
  if (movePct > 0) return "Still valid";
  return "Near entry";
}

function displayStatus(row: TrackerRow) {
  return row.setupStatus;
}

function formatDaysSince(signalDate: string, currentDate: string) {
  const days = diffDays(signalDate, currentDate);
  if (days === null || days < 0) return "-";
  return `${days}d`;
}

function displayAction(row: TrackerRow) {
  return row.followupAction;
}

function normalizeGrade(value: string | null | undefined) {
  const grade = (value ?? "").trim().toUpperCase();
  if (grade === "A+" || grade === "A") return grade;
  return null;
}

function groupOrder(group: FollowGroup) {
  if (group === "REENTRY") return 0;
  if (group === "WORKING") return 1;
  return 2;
}

function actionTone(action: FollowUpAction) {
  if (action === "ENTER" || action === "ENTER (BETTER PRICE)") {
    return "bg-emerald-600 text-white ring-1 ring-emerald-300 shadow-[0_10px_24px_rgba(5,150,105,0.28)]";
  }
  if (action === "HOLD" || action === "WATCH" || action === "WAIT") {
    return "bg-amber-500 text-white shadow-[0_8px_18px_rgba(245,158,11,0.22)]";
  }
  return "bg-red-600 text-white shadow-[0_8px_18px_rgba(220,38,38,0.22)]";
}

function formatMove(value: number | null) {
  if (value === null || !Number.isFinite(value)) return "-";
  return `${value > 0 ? "+" : ""}${value.toFixed(1)}%`;
}

function moveTone(value: number | null) {
  if (value === null || !Number.isFinite(value)) return "text-slate-500";
  if (value > 0) return "text-emerald-600";
  if (value < 0) return "text-red-500";
  return "text-slate-700";
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
  return { year: Number(match[1]), month: Number(match[2]), day: Number(match[3]) };
}

function diffDays(start: string, end: string) {
  const startParts = parseIsoDateParts(start);
  const endParts = parseIsoDateParts(end);
  if (!startParts || !endParts) return null;
  const startUtc = Date.UTC(startParts.year, startParts.month - 1, startParts.day);
  const endUtc = Date.UTC(endParts.year, endParts.month - 1, endParts.day);
  return Math.floor((endUtc - startUtc) / (1000 * 60 * 60 * 24));
}

function toSortTime(value: string) {
  const parts = parseIsoDateParts(value);
  return parts ? Date.UTC(parts.year, parts.month - 1, parts.day) : 0;
}
