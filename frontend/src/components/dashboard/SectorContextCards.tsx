import { formatNumber } from "@/lib/format";
import type { SectorOutlook } from "@/types/dashboard";

export function SectorContextCards({ sectors }: { sectors: SectorOutlook[] }) {
  const focusSectors = sectors.slice(0, 2);
  const avoidSectors = sectors.slice(Math.max(sectors.length - 2, 0));
  const densityRanks = new Map(
    [...sectors]
      .sort((a, b) => (b.aTierDensity ?? -1) - (a.aTierDensity ?? -1))
      .map((sector, index) => [sector.sector, index + 1])
  );

  return (
    <section className="rounded-lg border border-slate-200 bg-white px-5 py-4 shadow-soft">
      <div className="flex items-center gap-4">
        <div>
          <h2 className="text-lg font-black text-ink">Sector Outlook</h2>
          <p className="mt-1 text-xs font-semibold text-muted">
            Where long-call pressure is clustering in the broader daily run.
          </p>
          {sectors.length > 0 ? (
            <div className="mt-3 inline-flex flex-wrap items-center gap-2 rounded-lg border border-slate-200 bg-[linear-gradient(180deg,rgba(248,250,252,1),rgba(241,245,249,0.92))] px-3 py-2 shadow-[0_8px_18px_rgba(15,23,42,0.06)]">
              <span className="text-[11px] font-black uppercase tracking-[0.08em] text-blue-700">Focus Today</span>
              {focusSectors.map((sector, index) => (
                <span key={`focus-${sector.sector}`} className={focusPillClass(index === 0 ? 1 : 2)}>
                  {sector.sector}
                </span>
              ))}
              <span className="ml-2 text-[11px] font-black uppercase tracking-[0.08em] text-red-700">Avoid</span>
              {avoidSectors.map((sector, index) => (
                <span
                  key={`avoid-${sector.sector}`}
                  className={focusPillClass(index === avoidSectors.length - 1 ? "avoid-1" : "avoid-2")}
                >
                  {sector.sector}
                </span>
              ))}
            </div>
          ) : null}
        </div>
      </div>

      <div className="mt-4 grid gap-4 xl:grid-cols-3">
        {sectors.length === 0 ? (
          <div className="rounded-lg border border-dashed border-slate-300 bg-slate-50 px-5 py-10 text-center xl:col-span-3">
            <p className="text-base font-black text-ink">No sector outlook available yet</p>
            <p className="mt-2 text-sm font-semibold text-muted">
              Sector outlook cards will appear once the latest ML summary workbook is available.
            </p>
          </div>
        ) : null}

        {sectors.map((sector) => {
          const topTickers = [...sector.topTickers]
            .sort((a, b) => {
              if ((b.aGradeCount ?? 0) !== (a.aGradeCount ?? 0)) return (b.aGradeCount ?? 0) - (a.aGradeCount ?? 0);
              return (b.signalCount ?? 0) - (a.signalCount ?? 0);
            })
            .slice(0, 3);

          return (
            <article
              key={sector.sector}
              className={`rounded-lg border p-4 ${sectorCardClass(sector.rank, sectors.length)}`}
            >
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="text-[11px] font-bold text-muted">{groupLabel(sector.rank, sectors.length)} • Rank #{sector.rank}</p>
                  <h3 className={`text-base leading-tight text-ink ${sector.rank <= 2 ? "font-black" : "font-extrabold"}`}>{sector.sector}</h3>
                  <p className="mt-1 text-xs font-semibold text-muted">
                    {sector.etf} · {sector.bias}
                  </p>
                </div>
                <MiniBadge>{sector.flowSkew}</MiniBadge>
              </div>

              <p className="mt-3 text-sm font-semibold leading-6 text-slate-700">{buildSummary(sector, sectors.length)}</p>

              <div className="mt-4 grid grid-cols-2 gap-4">
                <Stat label="ETF backdrop" value={sector.bias} />
                <Stat label="Flow" value={sector.flowSkew} />
                <Stat
                  label="A-tier density"
                  value={formatDensity(sector.aTierDensity)}
                  detail={formatDensityContext(densityRanks.get(sector.sector) ?? null, sectors.length)}
                />
                <Stat label="Active setups today" value={formatNumber(sector.visibleSetups ?? 0)} />
              </div>

              <div className="mt-4">
                <p className="text-[11px] font-bold text-muted">Tickers repeatedly appearing in top-ranked setups</p>
                <div className="mt-2 space-y-2">
                  {topTickers.map((ticker) => (
                    <div
                      key={`${sector.sector}-${ticker.ticker}`}
                      className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-3 rounded-md border border-slate-200 bg-white px-3 py-2"
                    >
                      <div className="min-w-0">
                        <p className="truncate text-sm font-black text-ink">{ticker.ticker}</p>
                      </div>
                      <div className="flex items-center gap-2">
                        <span className="text-[11px] font-semibold text-muted">A-tier x{formatNumber(ticker.aGradeCount ?? 0)}</span>
                        {ticker.direction && ticker.direction !== "Neutral" ? <MiniBadge>{ticker.direction}</MiniBadge> : null}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </article>
          );
        })}
      </div>
    </section>
  );
}

function focusPillClass(rank: 1 | 2 | "avoid-1" | "avoid-2") {
  if (rank === 1) {
    return "rounded-md bg-blue-700 px-2.5 py-1 text-xs font-black text-white";
  }

  if (rank === 2) {
    return "rounded-md bg-blue-500 px-2.5 py-1 text-xs font-black text-white";
  }

  if (rank === "avoid-1") {
    return "rounded-md bg-red-500 px-2.5 py-1 text-xs font-black text-white";
  }

  return "rounded-md bg-red-200 px-2.5 py-1 text-xs font-black text-red-800 ring-1 ring-red-300";
}

function sectorCardClass(rank: number, total: number) {
  if (rank === 1) {
    return "border-blue-500 bg-[linear-gradient(180deg,rgba(29,78,216,0.2),rgba(219,234,254,0.92))] shadow-[0_14px_30px_rgba(37,99,235,0.16)]";
  }

  if (rank === 2) {
    return "border-blue-400 bg-[linear-gradient(180deg,rgba(96,165,250,0.16),rgba(239,246,255,0.96))] shadow-[0_10px_22px_rgba(59,130,246,0.1)]";
  }

  if (rank === total) {
    return "border-red-400 bg-[linear-gradient(180deg,rgba(239,68,68,0.18),rgba(254,242,242,0.98))] shadow-[0_10px_22px_rgba(239,68,68,0.08)]";
  }

  if (rank === Math.max(total - 1, 1)) {
    return "border-red-300 bg-[linear-gradient(180deg,rgba(254,226,226,0.82),rgba(248,250,252,0.98))]";
  }

  return "border-slate-200 bg-slate-50";
}

function groupLabel(rank: number, total: number) {
  if (rank <= 2) return "Focus Today";
  if (rank >= Math.max(total - 1, 1)) return "Avoid";
  return "Secondary";
}

function Stat({ label, value, detail }: { label: string; value: string; detail?: string | null }) {
  return (
    <div>
      <p className="text-[11px] font-bold text-muted">{label}</p>
      <p className="mt-2 text-lg font-black leading-none text-ink">{value}</p>
      {detail ? <p className="mt-1 text-[11px] font-semibold text-muted">{detail}</p> : null}
    </div>
  );
}

function MiniBadge({ children }: { children: React.ReactNode }) {
  return (
    <span className="inline-flex items-center rounded-md border border-slate-200 bg-slate-50 px-2 py-1 text-[11px] font-bold text-slate-700">
      {children}
    </span>
  );
}

function buildSummary(sector: SectorOutlook, total: number) {
  if (sector.rank <= 2) {
    return "Primary sector for call exposure today.";
  }

  if (sector.rank >= Math.max(total - 1, 1)) {
    return "Lower conviction - avoid aggressive new entries.";
  }

  return "Secondary exposure - consider after focus sectors.";
}

function formatDensity(value: number | null | undefined) {
  if (value === null || value === undefined) return "N/A";
  return `${value.toFixed(1)}%`;
}

function formatDensityContext(rank: number | null, total: number) {
  if (!rank || total <= 0) return null;
  const percentile = Math.round((rank / total) * 100);
  return `Top ${percentile}% by density today`;
}
