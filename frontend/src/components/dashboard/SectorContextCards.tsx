import { useState } from "react";
import { formatNumber } from "@/lib/format";
import type { SectorOutlook } from "@/types/dashboard";

export function SectorContextCards({ sectors }: { sectors: SectorOutlook[] }) {
  const [showHowToRead, setShowHowToRead] = useState(false);

  return (
    <section className="rounded-lg border border-slate-200 bg-white px-5 py-4 shadow-soft">
      <div className="flex items-center gap-4">
        <div>
          <h2 className="text-lg font-black text-ink">Sector Outlook</h2>
          <p className="mt-1 text-xs font-semibold text-muted">
            Where opportunity is broad vs concentrated today.
          </p>
          <p className="mt-2 max-w-4xl text-[11px] font-semibold leading-5 text-slate-500">
            Based on how A-tier signals are distributed across sectors and tickers.
          </p>
          <div className="mt-2">
            <button
              type="button"
              aria-expanded={showHowToRead}
              aria-controls="sector-how-to-read"
              onClick={() => setShowHowToRead((current) => !current)}
              className="inline-flex items-center gap-1 text-[11px] font-bold text-slate-600 transition hover:opacity-80 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-300 focus-visible:ring-offset-1"
            >
              <span aria-hidden="true">{showHowToRead ? "▼" : "▶"}</span>
              <span>How to read this</span>
            </button>
          </div>
          <div
            id="sector-how-to-read"
            className={`overflow-hidden transition-all duration-200 ease-out ${showHowToRead ? "mt-2 max-h-64 opacity-100" : "max-h-0 opacity-0"}`}
          >
            <div className="rounded-md border border-slate-200 bg-slate-50 px-3 py-3">
              <p className="text-[11px] font-black text-ink">What this tracks</p>
              <p className="mt-1 text-[11px] font-semibold leading-5 text-slate-600">
                This view aggregates A-tier trade signals and evaluates how they are distributed across each sector, separating signal quality from participation breadth.
              </p>
              <p className="mt-2 text-[11px] font-black text-ink">Why this matters</p>
              <p className="mt-1 text-[11px] font-semibold leading-5 text-slate-600">
                Broad participation tends to support more durable trends, while concentrated activity is often driven by a few dominant names and can be less stable.
              </p>
              <p className="mt-2 text-[11px] font-black text-ink">How to use it</p>
              <p className="mt-1 text-[11px] font-semibold leading-5 text-slate-600">
                Focus on Broad Strength sectors for consistency, and treat Highly Concentrated sectors as more tactical opportunities.
              </p>
            </div>
          </div>
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
          const classification = classifySector(sector);
          const topTickers = [...sector.topTickers]
            .sort((a, b) => {
              if ((b.aGradeCount ?? 0) !== (a.aGradeCount ?? 0)) return (b.aGradeCount ?? 0) - (a.aGradeCount ?? 0);
              return (b.signalCount ?? 0) - (a.signalCount ?? 0);
            })
            .slice(0, 3);
          const topTickerLine = topTickers
            .map((ticker) => `${ticker.ticker} (${formatNumber(ticker.aGradeCount ?? 0)})`)
            .join(" • ");

          return (
            <article key={sector.sector} className={`rounded-lg border p-4 ${classification.cardClass}`}>
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="text-[11px] font-bold text-muted">#{sector.rank || "-"}</p>
                  <p className={`text-[11px] font-black ${classification.labelClass}`}>{classification.label}</p>
                  <h3 className="text-base font-extrabold leading-tight text-ink">{sector.sector}</h3>
                  <p className="mt-1 text-xs font-semibold text-muted">{formatOverlayLine(sector)}</p>
                </div>
                <MiniBadge>{sector.flowSkew}</MiniBadge>
              </div>

              <div className="mt-3 space-y-1">
                <p className="text-sm font-black text-ink">{formatDensity(sector.aTierDensity)} A-tier density</p>
                <p className="text-xs font-semibold text-muted">
                  {formatNumber(sector.aTierTickerCount ?? 0)} A-tier tickers of {formatNumber(sector.tickerCount ?? 0)} • Top 3 = {formatShare(sector.top3Share)}
                </p>
              </div>
              <p className="mt-3 text-sm font-semibold leading-6 text-slate-700">{classification.description}</p>

              <div className="mt-4">
                <p className="text-sm font-semibold text-slate-700">{topTickerLine || "No repeated top tickers"}</p>
              </div>
            </article>
          );
        })}
      </div>
    </section>
  );
}

function MiniBadge({ children }: { children: React.ReactNode }) {
  return (
    <span className="inline-flex items-center rounded-md border border-slate-200 bg-slate-50 px-2 py-1 text-[11px] font-bold text-slate-700">
      {children}
    </span>
  );
}

function formatDensity(value: number | null | undefined) {
  if (value === null || value === undefined) return "N/A";
  return `${value.toFixed(1)}%`;
}

function formatShare(value: number | null | undefined) {
  if (value === null || value === undefined) return "N/A";
  return `${value.toFixed(1)}%`;
}

function classifySector(sector: SectorOutlook) {
  const tickerCount = Math.max(0, Number(sector.tickerCount ?? 0));
  const aTierTickerCount = Math.max(0, Number(sector.aTierTickerCount ?? 0));
  const top3Share = Number(sector.top3Share ?? 0);
  const breadthRatio = tickerCount > 0 ? aTierTickerCount / tickerCount : 0;

  if (top3Share > 70) {
    return {
      label: "Highly Concentrated",
      description: "Driven by a few dominant names. Higher risk, less diversification.",
      labelClass: "text-red-700",
      cardClass: "border-red-300 bg-[linear-gradient(180deg,rgba(254,226,226,0.82),rgba(255,255,255,0.98))]"
    };
  }

  if (breadthRatio > 0.06 && top3Share < 40) {
    return {
      label: "Broad Strength",
      description: "Strong participation across multiple tickers. More durable moves.",
      labelClass: "text-emerald-700",
      cardClass: "border-emerald-300 bg-[linear-gradient(180deg,rgba(220,252,231,0.85),rgba(255,255,255,0.98))]"
    };
  }

  if (breadthRatio < 0.03) {
    return {
      label: "Narrow Opportunity",
      description: "Limited participation across the sector. Opportunities are selective.",
      labelClass: "text-amber-700",
      cardClass: "border-amber-300 bg-[linear-gradient(180deg,rgba(254,243,199,0.72),rgba(255,255,255,0.98))]"
    };
  }

  if (top3Share >= 50 && top3Share <= 75) {
    return {
      label: "Moderately Concentrated",
      description: "Participation is uneven with emerging leaders.",
      labelClass: "text-orange-700",
      cardClass: "border-orange-300 bg-[linear-gradient(180deg,rgba(255,237,213,0.78),rgba(255,255,255,0.98))]"
    };
  }

  return {
    label: "Balanced Opportunity",
    description: "Moderate participation with no clear dominance.",
    labelClass: "text-slate-700",
    cardClass: "border-slate-200 bg-slate-50"
  };
}

function formatOverlayLine(sector: SectorOutlook) {
  const fallbackTicker = String(sector.etf ?? "").trim() || "N/A";
  const bias = String(sector.bias ?? "").trim().toLowerCase();
  if (!bias || bias === "no overlay") return fallbackTicker;
  return `${fallbackTicker} - ${sector.bias}`;
}
