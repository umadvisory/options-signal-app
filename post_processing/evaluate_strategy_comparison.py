"""
Offline strategy evaluation script for comparing:

1. Baseline strategy
   - source: ML/sample_predictions_with_tiers_YYYYMMDD.csv
   - rules:
     * predicted_tier_cal = A
     * filteredtier = A
     * is_tradeable = 1
     * dedupe to one row per ticker
     * keep top 25 by adaptive_score_final

2. Selector strategy
   - source: data/outputs/top_trades_YYYYMMDD.csv
   - rules:
     * use saved selector outputs only
     * keep only final_tier in {A+, A}

Why this script exists
----------------------
This script gives us a repeatable, API-independent way to validate whether the
new selector-based post-processing layer improves trade quality versus the
baseline v25-style selection logic.

It does not recompute selector logic, modify ML logic, or depend on the API.
Instead, it compares already-saved daily signal files against realized outcomes
stored in data/master/trades_master.duckdb.

How matching works
------------------
Trades are matched to realized outcomes using:
  * optionSymbol
  * signal_date == CAST(entry_time AS DATE)

Realized return is computed as:
  return_pct = pnl / total_risked_usd * 100

Metrics produced
----------------
For each strategy, the script computes:
  * total_trades
  * win_rate
  * avg_return_pct
  * median_return_pct
  * avg_win_pct
  * avg_loss_pct
  * expected_value_pct

Files written
-------------
1. Summary output
   data/outputs/strategy_comparison_latest.csv

2. Daily breakdown output
   data/outputs/strategy_comparison_daily.csv

Important current limitation
----------------------------
The script can only evaluate dates that satisfy BOTH:
  * a dated selector snapshot exists: top_trades_YYYYMMDD.csv
  * realized outcomes exist in trades_master for that signal date

If selector snapshots are newer than the latest completed realized trade date in
DuckDB, the script will write empty output files and explain why.

Windows / CMD-friendly run commands
-----------------------------------
From the repo root:

1. Default run
   C:\\Users\\umarm\\.cache\\codex-runtimes\\codex-primary-runtime\\dependencies\\python\\python.exe post_processing\\evaluate_strategy_comparison.py

2. Use a different lookback window
   C:\\Users\\umarm\\.cache\\codex-runtimes\\codex-primary-runtime\\dependencies\\python\\python.exe post_processing\\evaluate_strategy_comparison.py --lookback-days 15

3. Explicitly pass paths
   C:\\Users\\umarm\\.cache\\codex-runtimes\\codex-primary-runtime\\dependencies\\python\\python.exe post_processing\\evaluate_strategy_comparison.py --outputs-dir data\\outputs --ml-dir ML --trades-db data\\master\\trades_master.duckdb
"""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path

import duckdb
import pandas as pd


ROOT_DIR = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT_DIR / "data" / "outputs"
ML_DIR = ROOT_DIR / "ML"
TRADES_DB_PATH = ROOT_DIR / "data" / "master" / "trades_master.duckdb"

SUMMARY_OUTPUT_PATH = OUTPUT_DIR / "strategy_comparison_latest.csv"
DAILY_OUTPUT_PATH = OUTPUT_DIR / "strategy_comparison_daily.csv"


@dataclass(frozen=True)
class SignalSnapshot:
    signal_date: str
    selector_path: Path
    prediction_path: Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compare baseline top-25 signals versus selector-based top trades using realized outcomes."
    )
    parser.add_argument(
        "--lookback-days",
        type=int,
        default=10,
        help="Maximum number of completed trading days to evaluate (default: 10).",
    )
    parser.add_argument(
        "--outputs-dir",
        default=str(OUTPUT_DIR),
        help="Directory containing dated selector outputs.",
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


def discover_snapshots(outputs_dir: Path, ml_dir: Path, lookback_days: int) -> list[SignalSnapshot]:
    selector_pattern = re.compile(r"top_trades_(\d{8})\.csv$")
    prediction_template = "sample_predictions_with_tiers_{date}.csv"

    snapshots: list[SignalSnapshot] = []
    for selector_path in sorted(outputs_dir.glob("top_trades_*.csv")):
        match = selector_pattern.match(selector_path.name)
        if not match:
            continue

        yyyymmdd = match.group(1)
        prediction_path = ml_dir / prediction_template.format(date=yyyymmdd)
        if not prediction_path.exists():
            continue

        signal_date = f"{yyyymmdd[0:4]}-{yyyymmdd[4:6]}-{yyyymmdd[6:8]}"
        snapshots.append(
            SignalSnapshot(
                signal_date=signal_date,
                selector_path=selector_path,
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


def build_selector_selection(selector_path: Path, signal_date: str) -> pd.DataFrame:
    df = pd.read_csv(selector_path, low_memory=False)
    required_columns = {"ticker", "optionSymbol", "final_tier"}
    missing = required_columns - set(df.columns)
    if missing:
        raise ValueError(f"{selector_path.name} is missing required columns: {sorted(missing)}")

    work = df.copy()
    work["final_tier"] = work["final_tier"].astype(str).str.strip()
    work["optionSymbol"] = work["optionSymbol"].astype(str).str.strip()
    work["ticker"] = work["ticker"].astype(str).str.strip()
    work = work[work["final_tier"].isin(["A+", "A"])].copy()

    return pd.DataFrame(
        {
            "signal_date": signal_date,
            "optionSymbol": work["optionSymbol"],
            "ticker": work["ticker"],
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
    outputs_dir = Path(args.outputs_dir)
    ml_dir = Path(args.ml_dir)
    trades_db_path = Path(args.trades_db)
    summary_output_path = Path(args.summary_output)
    daily_output_path = Path(args.daily_output)

    snapshots = discover_snapshots(outputs_dir=outputs_dir, ml_dir=ml_dir, lookback_days=args.lookback_days)
    if not snapshots:
        raise SystemExit(
            "No dated selector snapshots found. Save daily top_trades_YYYYMMDD.csv files first, then rerun."
        )

    max_realized_signal_date = fetch_max_realized_signal_date(trades_db_path)
    if max_realized_signal_date is not None:
        snapshots = [snapshot for snapshot in snapshots if snapshot.signal_date <= max_realized_signal_date]

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
            "No selector snapshots fall on completed realized trade dates yet. "
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
        selector = build_selector_selection(snapshot.selector_path, snapshot.signal_date)

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
