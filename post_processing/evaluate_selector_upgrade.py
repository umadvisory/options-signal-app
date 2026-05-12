from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from post_processing.top_trades_selector import (  # noqa: E402
    build_top_trades,
    find_latest_prediction_csv,
    load_historical_scored_rows,
    load_latest_predictions,
)


ML_DIR = ROOT_DIR / "ML"
TRADES_DB_PATH = ROOT_DIR / "data" / "master" / "trades_master.duckdb"
OUTPUT_DIR = ROOT_DIR / "data" / "outputs" / "Backtests"
SUMMARY_OUTPUT_PATH = OUTPUT_DIR / "selector_upgrade_summary.csv"
DAILY_OUTPUT_PATH = OUTPUT_DIR / "selector_upgrade_daily.csv"
PICKS_OUTPUT_PATH = OUTPUT_DIR / "selector_upgrade_picks.csv"


@dataclass(frozen=True)
class SignalSnapshot:
    signal_date: str
    prediction_path: Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compare legacy selector vs reranked selector using realized outcomes."
    )
    parser.add_argument(
        "--lookback-days",
        type=int,
        default=15,
        help="Maximum number of completed trading days to evaluate (default: 15).",
    )
    parser.add_argument(
        "--ml-dir",
        default=str(ML_DIR),
        help="Directory containing sample_predictions_with_tiers_YYYYMMDD.csv files.",
    )
    parser.add_argument(
        "--trades-db",
        default=str(TRADES_DB_PATH),
        help="Path to trades_master.duckdb.",
    )
    parser.add_argument(
        "--summary-output",
        default=str(SUMMARY_OUTPUT_PATH),
        help="CSV path for summary output.",
    )
    parser.add_argument(
        "--daily-output",
        default=str(DAILY_OUTPUT_PATH),
        help="CSV path for daily breakdown output.",
    )
    parser.add_argument(
        "--picks-output",
        default=str(PICKS_OUTPUT_PATH),
        help="CSV path for trade-level picks output.",
    )
    parser.add_argument(
        "--history-days",
        type=int,
        default=30,
        help="Lookback days for historical percentile scoring.",
    )
    parser.add_argument(
        "--segment-min-history",
        type=int,
        default=5000,
        help="Fallback threshold for segmented history.",
    )
    parser.add_argument(
        "--top-n",
        type=int,
        default=25,
        help="Number of trades selected each day.",
    )
    return parser.parse_args()


def fetch_max_realized_signal_date(trades_db_path: Path) -> str | None:
    con = duckdb.connect(str(trades_db_path), read_only=True)
    try:
        row = con.execute("SELECT MAX(CAST(entry_time AS DATE)) AS max_signal_date FROM trades_master").fetchone()
    finally:
        con.close()

    if not row or row[0] is None:
        return None
    return pd.to_datetime(row[0]).strftime("%Y-%m-%d")


def discover_prediction_snapshots(
    ml_dir: Path,
    lookback_days: int,
    max_realized_signal_date: str | None,
) -> list[SignalSnapshot]:
    prediction_pattern = re.compile(r"sample_predictions_with_tiers_(\d{8})\.csv$")
    snapshots: list[SignalSnapshot] = []
    for prediction_path in sorted(ml_dir.glob("sample_predictions_with_tiers_*.csv")):
        match = prediction_pattern.match(prediction_path.name)
        if not match:
            continue

        yyyymmdd = match.group(1)
        signal_date = f"{yyyymmdd[0:4]}-{yyyymmdd[4:6]}-{yyyymmdd[6:8]}"
        if max_realized_signal_date is not None and signal_date > max_realized_signal_date:
            continue

        snapshots.append(SignalSnapshot(signal_date=signal_date, prediction_path=prediction_path))

    return snapshots[-lookback_days:]


def load_same_day_outcomes(trades_db_path: Path, signal_dates: list[str]) -> pd.DataFrame:
    if not signal_dates:
        return pd.DataFrame(
            columns=["optionSymbol", "signal_date", "pnl", "total_risked_usd", "win_loss", "return_pct"]
        )

    quoted_dates = ", ".join(f"DATE '{value}'" for value in signal_dates)
    query = f"""
        SELECT
            optionSymbol,
            CAST(entry_time AS DATE) AS signal_date,
            pnl,
            total_risked_usd,
            win_loss
        FROM trades_master
        WHERE optionSymbol IS NOT NULL
          AND entry_time IS NOT NULL
          AND CAST(entry_time AS DATE) IN ({quoted_dates})
    """

    con = duckdb.connect(str(trades_db_path), read_only=True)
    try:
        outcomes = con.execute(query).fetchdf()
    finally:
        con.close()

    if outcomes.empty:
        return outcomes

    outcomes["signal_date"] = pd.to_datetime(outcomes["signal_date"]).dt.strftime("%Y-%m-%d")
    outcomes["pnl"] = pd.to_numeric(outcomes["pnl"], errors="coerce")
    outcomes["total_risked_usd"] = pd.to_numeric(outcomes["total_risked_usd"], errors="coerce")
    outcomes["win_loss"] = pd.to_numeric(outcomes["win_loss"], errors="coerce")
    outcomes["return_pct"] = (outcomes["pnl"] / outcomes["total_risked_usd"]) * 100.0
    outcomes = outcomes[
        outcomes["return_pct"].notna()
        & outcomes["total_risked_usd"].notna()
        & (outcomes["total_risked_usd"] != 0)
    ].copy()
    return outcomes


def load_first_later_outcomes(trades_db_path: Path, signal_date: str, option_symbols: list[str]) -> pd.DataFrame:
    if not option_symbols:
        return pd.DataFrame(
            columns=[
                "optionSymbol",
                "pnl",
                "total_risked_usd",
                "win_loss",
                "return_pct",
                "resolved_signal_date",
                "match_type",
            ]
        )

    quoted_symbols = ", ".join("'" + str(value).replace("'", "''") + "'" for value in sorted(set(option_symbols)))
    query = f"""
        WITH candidates AS (
            SELECT
                optionSymbol,
                CAST(entry_time AS DATE) AS resolved_signal_date,
                pnl,
                total_risked_usd,
                win_loss,
                ROW_NUMBER() OVER (PARTITION BY optionSymbol ORDER BY entry_time ASC) AS rn
            FROM trades_master
            WHERE optionSymbol IN ({quoted_symbols})
              AND optionSymbol IS NOT NULL
              AND entry_time IS NOT NULL
              AND CAST(entry_time AS DATE) > DATE '{signal_date}'
              AND pnl IS NOT NULL
              AND total_risked_usd IS NOT NULL
              AND total_risked_usd != 0
        )
        SELECT
            optionSymbol,
            resolved_signal_date,
            pnl,
            total_risked_usd,
            win_loss
        FROM candidates
        WHERE rn = 1
    """

    con = duckdb.connect(str(trades_db_path), read_only=True)
    try:
        later = con.execute(query).fetchdf()
    finally:
        con.close()

    if later.empty:
        return pd.DataFrame(
            columns=[
                "optionSymbol",
                "pnl",
                "total_risked_usd",
                "win_loss",
                "return_pct",
                "resolved_signal_date",
                "match_type",
            ]
        )

    later["resolved_signal_date"] = pd.to_datetime(later["resolved_signal_date"]).dt.strftime("%Y-%m-%d")
    later["pnl"] = pd.to_numeric(later["pnl"], errors="coerce")
    later["total_risked_usd"] = pd.to_numeric(later["total_risked_usd"], errors="coerce")
    later["win_loss"] = pd.to_numeric(later["win_loss"], errors="coerce")
    later["return_pct"] = (later["pnl"] / later["total_risked_usd"]) * 100.0
    later["match_type"] = "later"
    return later


def compute_metrics(frame: pd.DataFrame) -> dict[str, float | int | None]:
    total_trades = int(len(frame))
    if total_trades == 0:
        return {
            "total_trades": 0,
            "win_rate": None,
            "avg_return_pct": None,
            "median_return_pct": None,
            "avg_win_pct": None,
            "avg_loss_pct": None,
            "expected_value_pct": None,
        }

    returns = frame["return_pct"].astype(float)
    wins = returns[returns > 0]
    losses = returns[returns <= 0]
    win_rate = float((frame["win_loss"] > 0).mean() * 100.0) if "win_loss" in frame else float((returns > 0).mean() * 100.0)

    return {
        "total_trades": total_trades,
        "win_rate": round(win_rate, 2),
        "avg_return_pct": round(float(returns.mean()), 2),
        "median_return_pct": round(float(returns.median()), 2),
        "avg_win_pct": round(float(wins.mean()), 2) if not wins.empty else None,
        "avg_loss_pct": round(float(losses.mean()), 2) if not losses.empty else None,
        "expected_value_pct": round(float(returns.mean()), 2),
    }


def build_legacy_selector_selection(
    prediction_path: Path,
    signal_date: str,
    trades_db_path: Path,
    top_n: int,
    history_days: int,
    segment_min_history: int,
) -> pd.DataFrame:
    df = pd.read_csv(prediction_path, low_memory=False)
    required_columns = {
        "ticker",
        "optionSymbol",
        "predicted_tier_cal",
        "filteredtier",
        "adaptive_score_final",
        "optionType",
        "dte",
    }
    missing = required_columns - set(df.columns)
    if missing:
        raise ValueError(f"{prediction_path.name} is missing required columns: {sorted(missing)}")

    work = df.copy()
    work["ticker"] = work["ticker"].astype(str).str.strip()
    work["optionSymbol"] = work["optionSymbol"].astype(str).str.strip()
    work["predicted_tier_cal"] = work["predicted_tier_cal"].astype(str).str.strip()
    work["filteredtier"] = work["filteredtier"].astype(str).str.strip()
    work["optionType"] = work["optionType"].astype(str).str.strip().str.lower()
    work["adaptive_score_final"] = pd.to_numeric(work["adaptive_score_final"], errors="coerce")
    work["dte"] = pd.to_numeric(work["dte"], errors="coerce")

    if "live_eligible" in work.columns:
        live = work["live_eligible"].astype(str).str.strip().str.lower()
        work["live_eligible_flag"] = live.isin({"1", "true", "yes", "y"})
    else:
        work["live_eligible_flag"] = True

    work = work[
        (work["optionType"] == "call")
        & (work["predicted_tier_cal"] == "A")
        & (work["filteredtier"] == "A")
        & work["live_eligible_flag"]
        & work["adaptive_score_final"].notna()
        & work["dte"].notna()
    ].copy()

    if work.empty:
        return pd.DataFrame(columns=["signal_date", "optionSymbol", "ticker", "strategy"])

    work["dte_bucket"] = work["dte"].map(lambda value: "1-7" if value <= 7 else "8-21" if value <= 21 else "22-45" if value <= 45 else "46+")
    work["segment"] = work["optionType"] + "|" + work["dte_bucket"]

    work = work.sort_values(
        ["ticker", "adaptive_score_final", "optionSymbol"],
        ascending=[True, False, True],
        kind="mergesort",
    )
    work = work.drop_duplicates(subset=["ticker"], keep="first").copy()

    hist_df = load_historical_scored_rows(trades_db_path, pd.Timestamp(signal_date), history_days)
    if hist_df.empty:
        return pd.DataFrame(columns=["signal_date", "optionSymbol", "ticker", "strategy"])
    hist_df = hist_df.copy()
    hist_df["segment"] = hist_df["optionType"].astype(str) + "|" + hist_df["dte_bucket"].astype(str)

    global_hist_sorted = hist_df["adaptive_score_final"].sort_values().to_numpy()
    work["global_percentile"] = (
        100.0
        * (
            np.searchsorted(global_hist_sorted, work["adaptive_score_final"].to_numpy(), side="left")
            + 0.5
            * (
                np.searchsorted(global_hist_sorted, work["adaptive_score_final"].to_numpy(), side="right")
                - np.searchsorted(global_hist_sorted, work["adaptive_score_final"].to_numpy(), side="left")
            )
        )
        / len(global_hist_sorted)
    )

    seg_hist = {
        seg: group["adaptive_score_final"].sort_values().to_numpy()
        for seg, group in hist_df.groupby("segment")
    }
    seg_sizes = {seg: len(arr) for seg, arr in seg_hist.items()}
    segmented_percentiles: list[float] = []
    for seg, score in zip(work["segment"], work["adaptive_score_final"]):
        arr = seg_hist.get(seg)
        if arr is None or len(arr) == 0:
            segmented_percentiles.append(float("nan"))
        else:
            left = np.searchsorted(arr, np.array([score]), side="left")[0]
            right = np.searchsorted(arr, np.array([score]), side="right")[0]
            segmented_percentiles.append(100.0 * (left + 0.5 * (right - left)) / len(arr))

    work["segment_hist_n"] = work["segment"].map(seg_sizes).fillna(0).astype(int)
    work["segment_fallback"] = work["segment_hist_n"] < segment_min_history
    work["segmented_percentile"] = pd.Series(segmented_percentiles, index=work.index)
    work.loc[work["segment_fallback"], "segmented_percentile"] = work.loc[work["segment_fallback"], "global_percentile"]
    work["final_tier"] = "lower"
    work.loc[(work["segmented_percentile"] >= 99.0) & (work["global_percentile"] >= 92.0), "final_tier"] = "A+"
    work.loc[(work["final_tier"] == "lower") & (work["segmented_percentile"] >= 96.0) & (work["global_percentile"] >= 82.0), "final_tier"] = "A"
    work.loc[(work["final_tier"] == "lower") & (work["segmented_percentile"] >= 88.0), "final_tier"] = "B"
    work = work[work["final_tier"].isin(["A+", "A"])].copy()
    work = work.sort_values(
        ["segmented_percentile", "global_percentile", "adaptive_score_final"],
        ascending=[False, False, False],
        kind="mergesort",
    ).head(top_n)

    return pd.DataFrame(
        {
            "signal_date": signal_date,
            "optionSymbol": work["optionSymbol"].astype(str).str.strip(),
            "ticker": work["ticker"].astype(str).str.strip(),
            "strategy": "legacy_selector",
        }
    )


def build_reranked_selector_selection(
    prediction_path: Path,
    signal_date: str,
    trades_db_path: Path,
    top_n: int,
    history_days: int,
    segment_min_history: int,
) -> pd.DataFrame:
    latest_df, parsed_signal_date = load_latest_predictions(prediction_path)
    hist_df = load_historical_scored_rows(trades_db_path, parsed_signal_date, history_days)
    top_trades, _, _ = build_top_trades(
        latest_df=latest_df,
        hist_df=hist_df,
        top_n=top_n,
        segment_min_history=segment_min_history,
    )
    result = top_trades.copy()
    result["strategy"] = "reranked_selector"
    return result[["signal_date", "optionSymbol", "ticker", "strategy"]]


def resolve_selected_outcomes(
    picks: pd.DataFrame,
    same_day_outcomes: pd.DataFrame,
    trades_db_path: Path,
    signal_date: str,
) -> tuple[pd.DataFrame, dict[str, object]]:
    base_cols = ["signal_date", "optionSymbol", "ticker", "strategy"]
    same_day = picks.merge(same_day_outcomes, on=["optionSymbol", "signal_date"], how="inner").copy()
    same_day["match_type"] = "same_day"
    same_day["resolved_signal_date"] = same_day["signal_date"]

    unmatched = picks[~picks["optionSymbol"].isin(same_day["optionSymbol"])].copy()
    later = pd.DataFrame()
    if not unmatched.empty:
        later_matches = load_first_later_outcomes(
            trades_db_path=trades_db_path,
            signal_date=signal_date,
            option_symbols=unmatched["optionSymbol"].astype(str).tolist(),
        )
        if not later_matches.empty:
            later = unmatched[base_cols].merge(later_matches, on="optionSymbol", how="inner")

    result_frames = [same_day]
    if not later.empty:
        result_frames.append(later)
    resolved = pd.concat(result_frames, ignore_index=True) if result_frames else pd.DataFrame()

    selected_trades = int(len(picks))
    same_day_matched = int(len(same_day))
    later_matched = int(len(later))
    matched_trades = same_day_matched + later_matched
    unresolved_trades = selected_trades - matched_trades
    coverage_pct = round(100.0 * matched_trades / selected_trades, 2) if selected_trades else None

    coverage = {
        "signal_date": signal_date,
        "strategy": str(picks["strategy"].iloc[0]) if not picks.empty else None,
        "selected_trades": selected_trades,
        "matched_trades": matched_trades,
        "same_day_matched": same_day_matched,
        "later_matched": later_matched,
        "unresolved_trades": unresolved_trades,
        "coverage_pct": coverage_pct,
    }
    return resolved, coverage


def main() -> None:
    args = parse_args()
    ml_dir = Path(args.ml_dir)
    trades_db_path = Path(args.trades_db)
    summary_output_path = Path(args.summary_output)
    daily_output_path = Path(args.daily_output)
    picks_output_path = Path(args.picks_output)

    summary_output_path.parent.mkdir(parents=True, exist_ok=True)
    daily_output_path.parent.mkdir(parents=True, exist_ok=True)
    picks_output_path.parent.mkdir(parents=True, exist_ok=True)

    max_realized_signal_date = fetch_max_realized_signal_date(trades_db_path)
    snapshots = discover_prediction_snapshots(
        ml_dir=ml_dir,
        lookback_days=args.lookback_days,
        max_realized_signal_date=max_realized_signal_date,
    )

    if not snapshots:
        empty_summary = pd.DataFrame(columns=["strategy"])
        empty_daily = pd.DataFrame(columns=["signal_date", "strategy"])
        empty_picks = pd.DataFrame(columns=["signal_date", "strategy", "optionSymbol", "ticker"])
        empty_summary.to_csv(summary_output_path, index=False)
        empty_daily.to_csv(daily_output_path, index=False)
        empty_picks.to_csv(picks_output_path, index=False)
        print("No eligible historical prediction snapshots found.")
        print(f"Saved empty summary: {summary_output_path}")
        print(f"Saved empty daily: {daily_output_path}")
        print(f"Saved empty picks: {picks_output_path}")
        return

    signal_dates = [snapshot.signal_date for snapshot in snapshots]
    same_day_outcomes = load_same_day_outcomes(trades_db_path=trades_db_path, signal_dates=signal_dates)

    strategy_frames: list[pd.DataFrame] = []
    coverage_rows: list[dict[str, object]] = []
    picks_frames: list[pd.DataFrame] = []

    for snapshot in snapshots:
        legacy = build_legacy_selector_selection(
            prediction_path=snapshot.prediction_path,
            signal_date=snapshot.signal_date,
            trades_db_path=trades_db_path,
            top_n=args.top_n,
            history_days=args.history_days,
            segment_min_history=args.segment_min_history,
        )
        reranked = build_reranked_selector_selection(
            prediction_path=snapshot.prediction_path,
            signal_date=snapshot.signal_date,
            trades_db_path=trades_db_path,
            top_n=args.top_n,
            history_days=args.history_days,
            segment_min_history=args.segment_min_history,
        )

        if not legacy.empty:
            picks_frames.append(legacy.copy())
        if not reranked.empty:
            picks_frames.append(reranked.copy())

        for picks in (legacy, reranked):
            resolved, coverage = resolve_selected_outcomes(
                picks=picks,
                same_day_outcomes=same_day_outcomes,
                trades_db_path=trades_db_path,
                signal_date=snapshot.signal_date,
            )
            coverage_rows.append(coverage)
            strategy_frames.append(resolved)

    results = pd.concat(strategy_frames, ignore_index=True) if strategy_frames else pd.DataFrame()
    picks_df = pd.concat(picks_frames, ignore_index=True) if picks_frames else pd.DataFrame()

    if results.empty:
        raise SystemExit("No realized outcomes matched the compared selector strategies.")

    coverage_df = pd.DataFrame(coverage_rows).sort_values(["signal_date", "strategy"]).reset_index(drop=True)

    daily_rows: list[dict[str, object]] = []
    for (signal_date, strategy_name), frame in results.groupby(["signal_date", "strategy"], sort=True):
        metrics = compute_metrics(frame)
        coverage_row = coverage_df[
            (coverage_df["signal_date"] == signal_date) & (coverage_df["strategy"] == strategy_name)
        ].iloc[0].to_dict()
        daily_rows.append(
            {
                "signal_date": signal_date,
                "strategy": strategy_name,
                "selected_trades": coverage_row["selected_trades"],
                "matched_trades": coverage_row["matched_trades"],
                "same_day_matched": coverage_row["same_day_matched"],
                "later_matched": coverage_row["later_matched"],
                "unresolved_trades": coverage_row["unresolved_trades"],
                "coverage_pct": coverage_row["coverage_pct"],
                **metrics,
            }
        )
    daily_df = pd.DataFrame(daily_rows).sort_values(["signal_date", "strategy"]).reset_index(drop=True)

    summary_rows: list[dict[str, object]] = []
    for strategy_name, frame in results.groupby("strategy", sort=True):
        metrics = compute_metrics(frame)
        strategy_coverage = coverage_df[coverage_df["strategy"] == strategy_name]
        summary_rows.append(
            {
                "strategy": strategy_name,
                "days_evaluated": int(frame["signal_date"].nunique()),
                "selected_trades": int(strategy_coverage["selected_trades"].sum()),
                "matched_trades": int(strategy_coverage["matched_trades"].sum()),
                "same_day_matched": int(strategy_coverage["same_day_matched"].sum()),
                "later_matched": int(strategy_coverage["later_matched"].sum()),
                "unresolved_trades": int(strategy_coverage["unresolved_trades"].sum()),
                "coverage_pct": round(
                    100.0 * float(strategy_coverage["matched_trades"].sum()) / float(strategy_coverage["selected_trades"].sum()),
                    2,
                ) if float(strategy_coverage["selected_trades"].sum()) else None,
                **metrics,
            }
        )
    summary_df = pd.DataFrame(summary_rows).sort_values("strategy").reset_index(drop=True)

    summary_df.to_csv(summary_output_path, index=False)
    daily_df.to_csv(daily_output_path, index=False)
    picks_df.to_csv(picks_output_path, index=False)

    print("Selector Upgrade Summary")
    print(summary_df.to_string(index=False))
    print()
    print("Daily Breakdown")
    print(daily_df.to_string(index=False))
    print()
    print(f"Saved summary: {summary_output_path}")
    print(f"Saved daily breakdown: {daily_output_path}")
    print(f"Saved picks: {picks_output_path}")


if __name__ == "__main__":
    main()
