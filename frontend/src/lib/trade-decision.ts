import type { TradeAction } from "@/types/dashboard";

export function actionExplanation(action: TradeAction) {
  if (action === "ENTER") return "Good entry zone";
  if (action === "WAIT") return "Momentum extended - wait";
  return "Setup valid, timing not ideal";
}

export function actionTone(action: TradeAction): "green" | "amber" | "red" {
  if (action === "ENTER") return "green";
  if (action === "WAIT") return "red";
  return "amber";
}
