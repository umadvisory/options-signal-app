"""
Offline strategy evaluator for comparing:

1. Strategy A (baseline)
   - rebuilt directly from each historical file:
     ML/sample_predictions_with_tiers_YYYYMMDD.csv
   - rules:
     * predicted_tier_cal = A
     * filteredtier = A
     * is_tradeable = 1
     * dedupe to one row per ticker
     * keep top 25 by adaptive_score_final

2. Strategy B (selector-style)
   - rebuilt directly from that same historical prediction file
   - rules:
     * optionType = call
     * predicted_tier_cal = A
     * filteredtier = A
     * live_eligible = 1 (if present)
     * dedupe to one row per ticker using highest adaptive_score_final
     * compute rolling historical percentiles from trades_master using prior scored days only
     * segmentation: optionType + DTE bucket
     * keep final_tier in {A+, A}

Why this script exists
----------------------
This script implements the simple historical A-vs-B comparison method used in
our earlier analysis where the selector materially outperformed the baseline.
It is intentionally simple and offline:

- no API dependency
- no reliance on saved selector snapshot CSVs
- no live or unrealized cohort logic

Instead, it reconstructs both strategies from historical daily prediction CSVs
and joins them to realized outcomes from:

  data/master/trades_master.duckdb

How matching works
------------------
Trades are matched to realized outcomes using:
  * optionSymbol
  * signal_date == CAST(entry_time AS DATE)

Realized return is computed as:
  return_pct = pnl / total_risked_usd * 100

Important scope
---------------
This evaluator only scores signal dates that already have realized rows in
trades_master. It is therefore a realized / completed-trade validation tool,
not a mark-to-market monitor for currently open positions.

Where this script lives
-----------------------
  post_processing/evaluate_strategy_comparison.py

Files written
-------------
1. Summary output
   data/outputs/Backtests/strategy_comparison_latest.csv

2. Daily breakdown output
   data/outputs/Backtests/strategy_comparison_daily.csv

CMD-friendly run commands
-------------------------
Open Command Prompt, change into the repo root, then run one of:

1. Go to the repo root
   cd /d C:\\Users\\umarm\\options-mvp

2. Default run
   C:\\Users\\umarm\\.cache\\codex-runtimes\\codex-primary-runtime\\dependencies\\python\\python.exe post_processing\\evaluate_strategy_comparison.py

3. Use a 10-day lookback instead
   C:\\Users\\umarm\\.cache\\codex-runtimes\\codex-primary-runtime\\dependencies\\python\\python.exe post_processing\\evaluate_strategy_comparison.py --lookback-days 10

4. Explicitly pass paths
   C:\\Users\\umarm\\.cache\\codex-runtimes\\codex-primary-runtime\\dependencies\\python\\python.exe post_processing\\evaluate_strategy_comparison.py --ml-dir ML --trades-db data\\master\\trades_master.duckdb
"""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd


ROOT_DIR = Path(__file__).resolve().parents[1]
BACKTESTS_DIR = ROOT_DIR / "data" / "outputs" / "Backtests"
ML_DIR = ROOT_DIR / "ML"
TRADES_DB_PATH = ROOT_DIR / "data" / "master" / "trades_master.duckdb"

SUMMARY_OUTPUT_PATH = BACKTESTS_DIR / "strategy_comparison_latest.csv"
DAILY_OUTPUT_PATH = BACKTESTS_DIR / "strategy_comparison_daily.csv"


@dataclass(frozen=True)
class SignalSnapshot:
    signal_date: str
    prediction_path: Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compare baseline top-25 signals versus selector-based top trades using realized outcomes."
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
        help="CSV path for strategy summary output.",
    )
    parser.add_argument(
        "--daily-output",
        default=str(DAILY_OUTPUT_PATH),
        help="CSV path for daily strategy breakdown output.",
    )
    return parser.parse_args()


def discover_prediction_snapshots(ml_dir: Path, lookback_days: int, max_realized_signal_date: str | None) -> list[SignalSnapshot]:
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

        snapshots.append(
            SignalSnapshot(
                signal_date=signal_date,
                prediction_path=prediction_path,
            )
        )

    return snapshots[-lookback_days:]


def load_realized_outcomes(trades_db_path: Path, signal_dates: list[str]) -> pd.DataFrame:
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
    outcomes["return_pct"] = (
        outcomes["pnl"] / outcomes["total_risked_usd"]
    ) * 100.0
    outcomes = outcomes[
        outcomes["return_pct"].notna() & outcomes["total_risked_usd"].notna() & (outcomes["total_risked_usd"] != 0)
    ].copy()
    return outcomes


def fetch_max_realized_signal_date(trades_db_path: Path) -> str | None:
    con = duckdb.connect(str(trades_db_path), read_only=True)
    try:
        row = con.execute("SELECT MAX(CAST(entry_time AS DATE)) AS max_signal_date FROM trades_master").fetchone()
    finally:
        con.close()

    if not row or row[0] is None:
        return None

    return pd.to_datetime(row[0]).strftime("%Y-%m-%d")


def normalize_is_tradeable(series: pd.Series) -> pd.Series:
    text = series.astype(str).str.strip().str.lower()
    return text.isin({"1", "true", "yes", "y"})


def normalize_live_eligible(series: pd.Series) -> pd.Series:
    text = series.astype(str).str.strip().str.lower()
    return text.isin({"1", "true", "yes", "y"})


def dte_bucket(dte: float) -> str:
    if pd.isna(dte):
        return "unknown"
    dte = float(dte)
    if dte <= 7:
        return "1-7"
    if dte <= 21:
        return "8-21"
    if dte <= 45:
        return "22-45"
    return "46+"


def empirical_percentile(sorted_hist: np.ndarray, values: np.ndarray) -> np.ndarray:
    left = np.searchsorted(sorted_hist, values, side="left")
    right = np.searchsorted(sorted_hist, values, side="right")
    return 100.0 * (left + 0.5 * (right - left)) / len(sorted_hist)


def classify_selector_tier(segmented_pct: float, global_pct: float) -> str:
    if segmented_pct >= 99.0 and global_pct >= 92.0:
        return "A+"
    if segmented_pct >= 96.0 and global_pct >= 82.0:
        return "A"
    if segmented_pct >= 88.0:
        return "B"
    return "lower"


def build_baseline_selection(prediction_path: Path, signal_date: str) -> pd.DataFrame:
    df = pd.read_csv(prediction_path, low_memory=False)
    required_columns = {"ticker", "optionSymbol", "predicted_tier_cal", "filteredtier", "is_tradeable", "adaptive_score_final"}
    missing = required_columns - set(df.columns)
    if missing:
        raise ValueError(f"{prediction_path.name} is missing required columns: {sorted(missing)}")

    work = df.copy()
    work["predicted_tier_cal"] = work["predicted_tier_cal"].astype(str).str.strip()
    work["filteredtier"] = work["filteredtier"].astype(str).str.strip()
    work["adaptive_score_final"] = pd.to_numeric(work["adaptive_score_final"], errors="coerce")
    work["is_tradeable_flag"] = normalize_is_tradeable(work["is_tradeable"])

    work = work[
        (work["predicted_tier_cal"] == "A")
        & (work["filteredtier"] == "A")
        & work["is_tradeable_flag"]
        & work["adaptive_score_final"].notna()
    ].copy()

    work = work.sort_values(
        ["ticker", "adaptive_score_final", "optionSymbol"],
        ascending=[True, False, True],
        kind="mergesort",
    )
    work = work.drop_duplicates(subset=["ticker"], keep="first")
    work = work.sort_values(
        ["adaptive_score_final", "ticker", "optionSymbol"],
        ascending=[False, True, True],
        kind="mergesort",
    ).head(25)

    return pd.DataFrame(
        {
            "signal_date": signal_date,
            "optionSymbol": work["optionSymbol"].astype(str).str.strip(),
            "ticker": work["ticker"].astype(str).str.strip(),
            "strategy": "baseline",
        }
    )


def load_historical_scores_for_signal_date(trades_db_path: Path, signal_date: str, history_days: int) -> pd.DataFrame:
    con = duckdb.connect(str(trades_db_path), read_only=True)
    try:
        hist = con.execute(
            """
            WITH scored AS (
                SELECT
                    ticker,
                    entry_time,
                    CAST(entry_time AS DATE) AS trade_date,
                    optionType,
                    dte,
                    adaptive_score_final
                FROM trades_master
                WHERE adaptive_score_final IS NOT NULL
                  AND entry_time IS NOT NULL
            ),
            hist_days AS (
                SELECT DISTINCT trade_date
                FROM scored
                WHERE trade_date < ?
                ORDER BY trade_date DESC
                LIMIT ?
            )
            SELECT
                ticker,
                entry_time,
                trade_date,
                optionType,
                dte,
                adaptive_score_final
            FROM scored
            WHERE trade_date IN (SELECT trade_date FROM hist_days)
            """,
            [signal_date, history_days],
        ).fetchdf()
    finally:
        con.close()

    if hist.empty:
        return hist

    hist["optionType"] = hist["optionType"].astype(str).str.strip().str.lower()
    hist["dte"] = pd.to_numeric(hist["dte"], errors="coerce")
    hist["adaptive_score_final"] = pd.to_numeric(hist["adaptive_score_final"], errors="coerce")
    hist["dte_bucket"] = hist["dte"].map(dte_bucket)
    hist["segment"] = hist["optionType"].astype(str) + "|" + hist["dte_bucket"].astype(str)
    hist = hist.dropna(subset=["adaptive_score_final"]).copy()
    return hist


def build_selector_selection(prediction_path: Path, signal_date: str, trades_db_path: Path, history_days: int = 30, segment_min_history: int = 5000) -> pd.DataFrame:
    df = pd.read_csv(prediction_path, low_memory=False)
    required_columns = {"ticker", "optionSymbol", "predicted_tier_cal", "filteredtier", "adaptive_score_final", "optionType", "dte"}
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
        work["live_eligible_flag"] = normalize_live_eligible(work["live_eligible"])
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

    work["dte_bucket"] = work["dte"].map(dte_bucket)
    work["segment"] = work["optionType"] + "|" + work["dte_bucket"]

    work = work.sort_values(
        ["ticker", "adaptive_score_final", "optionSymbol"],
        ascending=[True, False, True],
        kind="mergesort",
    )
    work = work.drop_duplicates(subset=["ticker"], keep="first").copy()

    hist = load_historical_scores_for_signal_date(trades_db_path, signal_date, history_days)
    if hist.empty:
        return pd.DataFrame(columns=["signal_date", "optionSymbol", "ticker", "strategy"])

    global_hist_sorted = np.sort(hist["adaptive_score_final"].to_numpy())
    work["global_percentile"] = empirical_percentile(global_hist_sorted, work["adaptive_score_final"].to_numpy())

    seg_hist = {
        seg: np.sort(group["adaptive_score_final"].to_numpy())
        for seg, group in hist.groupby("segment")
    }
    seg_sizes = {seg: len(arr) for seg, arr in seg_hist.items()}

    segmented_percentiles = []
    for seg, score in zip(work["segment"], work["adaptive_score_final"]):
        arr = seg_hist.get(seg)
        if arr is None or len(arr) == 0:
            segmented_percentiles.append(np.nan)
        else:
            segmented_percentiles.append(empirical_percentile(arr, np.array([score]))[0])

    work["segment_hist_n"] = work["segment"].map(seg_sizes).fillna(0).astype(int)
    work["segment_fallback"] = work["segment_hist_n"] < segment_min_history
    work["segmented_percentile"] = np.where(
        work["segment_fallback"],
        work["global_percentile"],
        segmented_percentiles,
    )
    work["final_tier"] = [
        classify_selector_tier(seg, glob)
        for seg, glob in zip(work["segmented_percentile"], work["global_percentile"])
    ]
    work = work[work["final_tier"].isin(["A+", "A"])].copy()

    return pd.DataFrame(
        {
            "signal_date": signal_date,
            "optionSymbol": work["optionSymbol"].astype(str).str.strip(),
            "ticker": work["ticker"].astype(str).str.strip(),
            "strategy": "selector",
        }
    )


def compute_metrics(frame: pd.DataFrame) -> dict[str, float | int | str | None]:
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


def main() -> None:
    args = parse_args()
    ml_dir = Path(args.ml_dir)
    trades_db_path = Path(args.trades_db)
    summary_output_path = Path(args.summary_output)
    daily_output_path = Path(args.daily_output)

    max_realized_signal_date = fetch_max_realized_signal_date(trades_db_path)
    snapshots = discover_prediction_snapshots(
        ml_dir=ml_dir,
        lookback_days=args.lookback_days,
        max_realized_signal_date=max_realized_signal_date,
    )

    summary_output_path.parent.mkdir(parents=True, exist_ok=True)
    daily_output_path.parent.mkdir(parents=True, exist_ok=True)

    if not snapshots:
        summary_df = pd.DataFrame(
            columns=[
                "strategy",
                "days_evaluated",
                "total_trades",
                "win_rate",
                "avg_return_pct",
                "median_return_pct",
                "avg_win_pct",
                "avg_loss_pct",
                "expected_value_pct",
            ]
        )
        daily_df = pd.DataFrame(
            columns=[
                "signal_date",
                "strategy",
                "total_trades",
                "win_rate",
                "avg_return_pct",
                "median_return_pct",
                "avg_win_pct",
                "avg_loss_pct",
                "expected_value_pct",
            ]
        )
        summary_df.to_csv(summary_output_path, index=False)
        daily_df.to_csv(daily_output_path, index=False)
        print(
            "No historical prediction files fall on completed realized trade dates yet. "
            f"Latest realized signal date in trades_master is {max_realized_signal_date or 'N/A'}."
        )
        print(f"Saved empty summary: {summary_output_path}")
        print(f"Saved empty daily breakdown: {daily_output_path}")
        return

    signal_dates = [snapshot.signal_date for snapshot in snapshots]
    outcomes = load_realized_outcomes(trades_db_path=trades_db_path, signal_dates=signal_dates)

    strategy_frames: list[pd.DataFrame] = []
    coverage_rows: list[dict[str, object]] = []
    for snapshot in snapshots:
        baseline = build_baseline_selection(snapshot.prediction_path, snapshot.signal_date)
        selector = build_selector_selection(
            prediction_path=snapshot.prediction_path,
            signal_date=snapshot.signal_date,
            trades_db_path=trades_db_path,
        )

        for strategy_name, picks in (("baseline", baseline), ("selector", selector)):
            merged = picks.merge(outcomes, on=["optionSymbol", "signal_date"], how="inner")
            coverage_rows.append(
                {
                    "signal_date": snapshot.signal_date,
                    "strategy": strategy_name,
                    "selected_trades": int(len(picks)),
                    "realized_trades": int(len(merged)),
                }
            )
            strategy_frames.append(merged)

    results = pd.concat(strategy_frames, ignore_index=True) if strategy_frames else pd.DataFrame()
    if results.empty:
        raise SystemExit("No realized outcomes matched the selected strategies for the available snapshot dates.")

    daily_rows: list[dict[str, object]] = []
    for (signal_date, strategy_name), frame in results.groupby(["signal_date", "strategy"], sort=True):
        metrics = compute_metrics(frame)
        daily_rows.append(
            {
                "signal_date": signal_date,
                "strategy": strategy_name,
                **metrics,
            }
        )

    daily_df = pd.DataFrame(daily_rows).sort_values(["signal_date", "strategy"]).reset_index(drop=True)

    summary_rows: list[dict[str, object]] = []
    for strategy_name, frame in results.groupby("strategy", sort=True):
        metrics = compute_metrics(frame)
        summary_rows.append(
            {
                "strategy": strategy_name,
                "days_evaluated": int(frame["signal_date"].nunique()),
                **metrics,
            }
        )

    summary_df = pd.DataFrame(summary_rows).sort_values("strategy").reset_index(drop=True)

    summary_df.to_csv(summary_output_path, index=False)
    daily_df.to_csv(daily_output_path, index=False)

    coverage_df = pd.DataFrame(coverage_rows).sort_values(["signal_date", "strategy"]).reset_index(drop=True)

    print("Strategy Comparison Summary")
    print(summary_df.to_string(index=False))
    print()
    print("Coverage by day")
    print(coverage_df.to_string(index=False))
    print()
    print(f"Saved summary: {summary_output_path}")
    print(f"Saved daily breakdown: {daily_output_path}")


if __name__ == "__main__":
    main()
