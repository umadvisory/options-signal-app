import type { TradeAction, TradeTier } from "@/types/dashboard";

type UiAction = TradeAction;

const actionStyles: Record<UiAction, string> = {
  ENTER: "bg-emerald-600 text-white ring-1 ring-emerald-300 shadow-[0_10px_24px_rgba(5,150,105,0.28)]",
  WATCH: "bg-amber-500 text-white shadow-[0_8px_18px_rgba(245,158,11,0.22)]",
  WAIT: "bg-red-600 text-white shadow-[0_8px_18px_rgba(220,38,38,0.22)]"
};

const tierStyles: Record<TradeTier, string> = {
  "A+": "bg-emerald-600 text-white",
  A: "bg-emerald-100 text-emerald-800 ring-1 ring-emerald-200",
  "A-": "bg-lime-100 text-lime-800 ring-1 ring-lime-200",
  "B+": "bg-orange-100 text-orange-800 ring-1 ring-orange-200",
  B: "bg-slate-100 text-slate-700 ring-1 ring-slate-200"
};

type BadgeProps = {
  children: React.ReactNode;
  tone?: "neutral" | "blue" | "green" | "soft";
  className?: string;
};

export function Badge({ children, tone = "neutral", className = "" }: BadgeProps) {
  const tones = {
    neutral: "bg-slate-100 text-slate-700 ring-1 ring-slate-200",
    blue: "bg-blue-100 text-blue-700 ring-1 ring-blue-200",
    green: "bg-emerald-100 text-emerald-700 ring-1 ring-emerald-200",
    soft: "bg-white text-slate-700 ring-1 ring-slate-200"
  };

  return (
    <span
      className={`inline-flex h-7 min-w-7 items-center justify-center rounded-md px-2.5 text-[11px] font-black uppercase leading-none ${tones[tone]} ${className}`}
    >
      {children}
    </span>
  );
}

export function ActionBadge({ action }: { action: UiAction }) {
  return (
    <span
      className={`inline-flex h-9 min-w-[86px] items-center justify-center rounded-md px-4 text-[11px] font-black uppercase tracking-wide ${actionStyles[action]}`}
    >
      {action}
    </span>
  );
}

export function TierBadge({ tier }: { tier: TradeTier }) {
  return (
    <span
      className={`inline-flex h-8 min-w-[46px] items-center justify-center rounded-md px-3 text-[11px] font-black uppercase ${tierStyles[tier]}`}
    >
      {tier}
    </span>
  );
}
