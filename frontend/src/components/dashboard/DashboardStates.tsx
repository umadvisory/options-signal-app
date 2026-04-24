import { Dashboard } from "@/components/dashboard/Dashboard";
import type { DashboardData } from "@/types/dashboard";

const emptyStats = {
  winRate: null,
  sampleSize: null,
  avgReturnPct: null,
  medianReturnPct: null,
  worstDrawdownProxy: null
};

const emptyDashboard: DashboardData = {
  generatedAt: new Date().toISOString(),
  marketRegime: null,
  watchlist: [],
  strategyStats: {
    highConviction: emptyStats,
    broadBase: emptyStats
  },
  trades: [],
  sectorOutlook: [],
  yesterdayStatus: []
};

export function DashboardLoadingState() {
  return (
    <main className="min-h-screen px-4 py-4 sm:px-6 lg:px-8">
      <div className="mx-auto flex max-w-7xl flex-col gap-4">
        <SkeletonBlock className="h-[82px]" />
        <section className="grid gap-4 lg:grid-cols-2">
          <SkeletonBlock className="h-[156px]" />
          <SkeletonBlock className="h-[156px]" />
        </section>
        <SkeletonBlock className="h-[360px]" />
        <section className="grid gap-4 lg:grid-cols-2">
          <SkeletonBlock className="h-[176px]" />
          <SkeletonBlock className="h-[176px]" />
        </section>
      </div>
    </main>
  );
}

export function DashboardErrorState({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <StateShell
      title="Could not load live signals"
      message={message}
      actionLabel="Retry"
      onAction={onRetry}
      tone="error"
    />
  );
}

export function DashboardEmptyState({ data, onRefresh }: { data: DashboardData; onRefresh: () => void }) {
  return (
    <div>
      <Dashboard data={data} onRefresh={onRefresh} />
      <div className="mx-auto -mt-48 max-w-xl px-4">
        <StateCard
          title="No live trades returned"
          message="The API responded successfully, but there are no ranked setups in the current payload."
          actionLabel="Refresh"
          onAction={onRefresh}
          tone="empty"
        />
      </div>
    </div>
  );
}

function StateShell({
  title,
  message,
  actionLabel,
  onAction,
  tone
}: {
  title: string;
  message: string;
  actionLabel: string;
  onAction: () => void;
  tone: "error" | "empty";
}) {
  return (
    <main className="grid min-h-screen place-items-center px-4 py-8">
      <StateCard title={title} message={message} actionLabel={actionLabel} onAction={onAction} tone={tone} />
    </main>
  );
}

function StateCard({
  title,
  message,
  actionLabel,
  onAction,
  tone
}: {
  title: string;
  message: string;
  actionLabel: string;
  onAction: () => void;
  tone: "error" | "empty";
}) {
  const styles =
    tone === "error"
      ? "border-red-200 bg-red-50 text-red-700"
      : "border-slate-200 bg-white text-slate-700";

  return (
    <section className={`rounded-lg border p-6 text-center shadow-card ${styles}`}>
      <h1 className="text-xl font-black text-ink">{title}</h1>
      <p className="mx-auto mt-3 max-w-md text-sm font-semibold leading-6">{message}</p>
      <button
        type="button"
        onClick={onAction}
        className="mt-5 inline-flex h-10 items-center justify-center rounded-md bg-blue-600 px-5 text-sm font-black text-white shadow-soft transition hover:bg-blue-700"
      >
        {actionLabel}
      </button>
    </section>
  );
}

function SkeletonBlock({ className }: { className: string }) {
  return (
    <div
      className={`relative overflow-hidden rounded-lg border border-slate-200 bg-white shadow-soft ${className}`}
      aria-hidden="true"
    >
      <div className="absolute inset-0 -translate-x-full animate-[shimmer_1.5s_infinite] bg-gradient-to-r from-transparent via-slate-100 to-transparent" />
    </div>
  );
}

export { emptyDashboard };
