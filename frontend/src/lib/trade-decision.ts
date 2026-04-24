import type { TopTrade } from "@/types/dashboard";

export type EntryPosture = {
  label: "Favorable" | "Caution" | "Wait";
  note: string;
  tone: "green" | "amber" | "red";
  score: number;
};

export type DecisionState = {
  posture: EntryPosture["label"];
  action: "ENTER" | "WATCH" | "WAIT";
  explanation: string;
  tone: EntryPosture["tone"];
  score: number;
};

export function getEntryPosture(trade: TopTrade): EntryPosture {
  const rsi = Number.isFinite(trade.context.rsi) ? trade.context.rsi : 0;
  const distancePct = Math.abs(Number.isFinite(trade.contract.distanceToStrikePct) ? trade.contract.distanceToStrikePct : 0);

  const rsiScore = getRsiScore(rsi);
  const distanceScore = clamp(1 - distancePct / 15, 0, 1);
  const entryScore = Number((rsiScore * 0.6 + distanceScore * 0.4).toFixed(2));

  if (rsi > 78 || entryScore < 0.35) {
    return {
      label: "Wait",
      note: "Momentum extended",
      tone: "red",
      score: entryScore
    };
  }

  if (entryScore >= 0.6) {
    return {
      label: "Favorable",
      note: "Not extended",
      tone: "green",
      score: entryScore
    };
  }

  return {
    label: "Caution",
    note: "Timing not ideal",
    tone: "amber",
    score: entryScore
  };
}

export function getDecisionState(trade: TopTrade): DecisionState {
  const posture = getEntryPosture(trade);

  if (posture.label === "Favorable") {
    return {
      posture: posture.label,
      action: "ENTER",
      explanation: "Good entry zone",
      tone: posture.tone,
      score: posture.score
    };
  }

  if (posture.label === "Wait") {
    return {
      posture: posture.label,
      action: "WAIT",
      explanation: "Momentum extended - wait",
      tone: posture.tone,
      score: posture.score
    };
  }

  return {
    posture: posture.label,
    action: "WATCH",
    explanation: "Setup valid, timing not ideal",
    tone: posture.tone,
    score: posture.score
  };
}

function getRsiScore(rsi: number) {
  if (rsi < 60) return 0.9;
  if (rsi <= 78) return 0.55;
  return 0.15;
}

function clamp(value: number, min: number, max: number) {
  return Math.min(max, Math.max(min, value));
}
