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
This script now uses a two-step matching rule for each selected contract:

1. same-day exact match
   * optionSymbol
   * signal_date == CAST(entry_time AS DATE)

2. fallback later match
   * if no same-day row exists, use the first later realized row found for
     the same optionSymbol in trades_master

Realized return is computed as:
  return_pct = pnl / total_risked_usd * 100

Important scope
---------------
This evaluator is still a realized / completed-trade validation tool, not a
mark-to-market monitor for currently open positions. It now follows selected
contracts forward when same-day logging is incomplete, and reports coverage
explicitly so unresolved picks remain visible.

Where this script lives
-----------------------
  post_processing/evaluate_strategy_comparison.py

Files written
-------------
1. Summary output
   data/outputs/Backtests/strategy_comparison_latest.csv

2. Daily breakdown output
   data/outputs/Backtests/strategy_comparison_daily.csv

3. Selector action breakdown output
   data/outputs/Backtests/selector_action_breakdown.csv

4. Selector action daily output
   data/outputs/Backtests/selector_action_daily.csv

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
ACTION_BREAKDOWN_OUTPUT_PATH = BACKTESTS_DIR / "selector_action_breakdown.csv"
ACTION_DAILY_OUTPUT_PATH = BACKTESTS_DIR / "selector_action_daily.csv"


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
    parser.add_argument(
        "--action-breakdown-output",
        default=str(ACTION_BREAKDOWN_OUTPUT_PATH),
        help="CSV path for selector action breakdown output.",
    )
    parser.add_argument(
        "--action-daily-output",
        default=str(ACTION_DAILY_OUTPUT_PATH),
        help="CSV path for selector action daily breakdown output.",
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


def safe_pct_distance(strike: object, underlying: object) -> float | None:
    try:
        strike_value = float(strike)
        underlying_value = float(underlying)
    except (TypeError, ValueError):
        return None
    if underlying_value == 0:
        return None
    return (strike_value - underlying_value) / underlying_value * 100.0


def build_trade_action_from_entry_profile_fields(row: pd.Series) -> str:
    rsi = pd.to_numeric(pd.Series([row.get("rsi")]), errors="coerce").iloc[0]
    distance_pct = safe_pct_distance(row.get("strike"), row.get("underlyingPrice"))

    rsi_value = 0 if pd.isna(rsi) else float(rsi)
    distance_value = 0 if distance_pct is None or pd.isna(distance_pct) else float(distance_pct)

    if rsi_value < 55:
        rsi_score = 0.9
    elif rsi_value <= 70:
        rsi_score = 0.7
    elif rsi_value <= 80:
        rsi_score = 0.5
    else:
        rsi_score = 0.2

    distance_score = max(0.0, min(1.0, 1 - distance_value / 15))
    entry_score = round(rsi_score * 0.6 + distance_score * 0.4, 2)

    if rsi_value > 85 or entry_score < 0.3:
        return "WAIT"
    if entry_score >= 0.5:
        return "ENTER"
    return "WATCH"


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


def build_selector_selection_with_context(
    prediction_path: Path,
    signal_date: str,
    trades_db_path: Path,
    history_days: int = 30,
    segment_min_history: int = 5000,
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
        "rsi",
        "strike",
        "underlyingPrice",
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
    work["rsi"] = pd.to_numeric(work["rsi"], errors="coerce")
    work["strike"] = pd.to_numeric(work["strike"], errors="coerce")
    work["underlyingPrice"] = pd.to_numeric(work["underlyingPrice"], errors="coerce")

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
        return pd.DataFrame(
            columns=[
                "signal_date",
                "optionSymbol",
                "ticker",
                "strategy",
                "final_tier",
                "action",
                "rsi",
                "strike",
                "underlyingPrice",
            ]
        )

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
        return pd.DataFrame(
            columns=[
                "signal_date",
                "optionSymbol",
                "ticker",
                "strategy",
                "final_tier",
                "action",
                "rsi",
                "strike",
                "underlyingPrice",
            ]
        )

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
    work["action"] = work.apply(build_trade_action_from_entry_profile_fields, axis=1)

    return pd.DataFrame(
        {
            "signal_date": signal_date,
            "optionSymbol": work["optionSymbol"].astype(str).str.strip(),
            "ticker": work["ticker"].astype(str).str.strip(),
            "strategy": "selector",
            "final_tier": work["final_tier"].astype(str).str.strip(),
            "action": work["action"].astype(str).str.strip(),
            "rsi": work["rsi"],
            "strike": work["strike"],
            "underlyingPrice": work["underlyingPrice"],
        }
    )


def main() -> None:
    args = parse_args()
    ml_dir = Path(args.ml_dir)
    trades_db_path = Path(args.trades_db)
    summary_output_path = Path(args.summary_output)
    daily_output_path = Path(args.daily_output)
    action_breakdown_output_path = Path(args.action_breakdown_output)
    action_daily_output_path = Path(args.action_daily_output)

    max_realized_signal_date = fetch_max_realized_signal_date(trades_db_path)
    snapshots = discover_prediction_snapshots(
        ml_dir=ml_dir,
        lookback_days=args.lookback_days,
        max_realized_signal_date=max_realized_signal_date,
    )

    summary_output_path.parent.mkdir(parents=True, exist_ok=True)
    daily_output_path.parent.mkdir(parents=True, exist_ok=True)
    action_breakdown_output_path.parent.mkdir(parents=True, exist_ok=True)
    action_daily_output_path.parent.mkdir(parents=True, exist_ok=True)

    if not snapshots:
        summary_df = pd.DataFrame(
            columns=[
                "strategy",
                "days_evaluated",
                "selected_trades",
                "matched_trades",
                "same_day_matched",
                "later_matched",
                "unresolved_trades",
                "coverage_pct",
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
                "selected_trades",
                "matched_trades",
                "same_day_matched",
                "later_matched",
                "unresolved_trades",
                "coverage_pct",
                "total_trades",
                "win_rate",
                "avg_return_pct",
                "median_return_pct",
                "avg_win_pct",
                "avg_loss_pct",
                "expected_value_pct",
            ]
        )
        action_breakdown_df = pd.DataFrame(
            columns=[
                "final_tier",
                "action",
                "matched_trades",
                "same_day_matched",
                "later_matched",
                "total_trades",
                "win_rate",
                "avg_return_pct",
                "median_return_pct",
                "avg_win_pct",
                "avg_loss_pct",
                "expected_value_pct",
            ]
        )
        action_daily_df = pd.DataFrame(
            columns=[
                "signal_date",
                "final_tier",
                "action",
                "matched_trades",
                "same_day_matched",
                "later_matched",
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
        action_breakdown_df.to_csv(action_breakdown_output_path, index=False)
        action_daily_df.to_csv(action_daily_output_path, index=False)
        print(
            "No historical prediction files fall on completed realized trade dates yet. "
            f"Latest realized signal date in trades_master is {max_realized_signal_date or 'N/A'}."
        )
        print(f"Saved empty summary: {summary_output_path}")
        print(f"Saved empty daily breakdown: {daily_output_path}")
        print(f"Saved empty action breakdown: {action_breakdown_output_path}")
        print(f"Saved empty action daily breakdown: {action_daily_output_path}")
        return

    signal_dates = [snapshot.signal_date for snapshot in snapshots]
    outcomes = load_realized_outcomes(trades_db_path=trades_db_path, signal_dates=signal_dates)

    strategy_frames: list[pd.DataFrame] = []
    coverage_rows: list[dict[str, object]] = []
    selector_context_frames: list[pd.DataFrame] = []
    for snapshot in snapshots:
        baseline = build_baseline_selection(snapshot.prediction_path, snapshot.signal_date)
        selector = build_selector_selection(
            prediction_path=snapshot.prediction_path,
            signal_date=snapshot.signal_date,
            trades_db_path=trades_db_path,
        )
        selector_with_context = build_selector_selection_with_context(
            prediction_path=snapshot.prediction_path,
            signal_date=snapshot.signal_date,
            trades_db_path=trades_db_path,
        )
        if not selector_with_context.empty:
            selector_context_frames.append(selector_with_context)

        for strategy_name, picks in (("baseline", baseline), ("selector", selector)):
            resolved, coverage = resolve_selected_outcomes(
                picks=picks,
                same_day_outcomes=outcomes,
                trades_db_path=trades_db_path,
                signal_date=snapshot.signal_date,
            )
            coverage_rows.append(coverage)
            strategy_frames.append(resolved)

    results = pd.concat(strategy_frames, ignore_index=True) if strategy_frames else pd.DataFrame()
    if results.empty:
        raise SystemExit("No realized outcomes matched the selected strategies for the available snapshot dates.")

    daily_rows: list[dict[str, object]] = []
    coverage_df = pd.DataFrame(coverage_rows).sort_values(["signal_date", "strategy"]).reset_index(drop=True)

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

    if selector_context_frames:
        selector_context_df = pd.concat(selector_context_frames, ignore_index=True)
        selector_results = results[results["strategy"] == "selector"].copy()
        selector_resolved = selector_results.merge(
            selector_context_df[["signal_date", "optionSymbol", "final_tier", "action"]],
            on=["signal_date", "optionSymbol"],
            how="inner",
        )

        action_breakdown_rows: list[dict[str, object]] = []
        for (final_tier, action), frame in selector_resolved.groupby(["final_tier", "action"], sort=True):
            metrics = compute_metrics(frame)
            action_breakdown_rows.append(
                {
                    "final_tier": final_tier,
                    "action": action,
                    "matched_trades": int(len(frame)),
                    "same_day_matched": int((frame["match_type"] == "same_day").sum()),
                    "later_matched": int((frame["match_type"] == "later").sum()),
                    **metrics,
                }
            )
        action_breakdown_df = pd.DataFrame(action_breakdown_rows).sort_values(["final_tier", "action"]).reset_index(drop=True)

        action_daily_rows: list[dict[str, object]] = []
        for (signal_date, final_tier, action), frame in selector_resolved.groupby(
            ["signal_date", "final_tier", "action"], sort=True
        ):
            metrics = compute_metrics(frame)
            action_daily_rows.append(
                {
                    "signal_date": signal_date,
                    "final_tier": final_tier,
                    "action": action,
                    "matched_trades": int(len(frame)),
                    "same_day_matched": int((frame["match_type"] == "same_day").sum()),
                    "later_matched": int((frame["match_type"] == "later").sum()),
                    **metrics,
                }
            )
        action_daily_df = pd.DataFrame(action_daily_rows).sort_values(
            ["signal_date", "final_tier", "action"]
        ).reset_index(drop=True)
    else:
        action_breakdown_df = pd.DataFrame(
            columns=[
                "final_tier",
                "action",
                "matched_trades",
                "same_day_matched",
                "later_matched",
                "total_trades",
                "win_rate",
                "avg_return_pct",
                "median_return_pct",
                "avg_win_pct",
                "avg_loss_pct",
                "expected_value_pct",
            ]
        )
        action_daily_df = pd.DataFrame(
            columns=[
                "signal_date",
                "final_tier",
                "action",
                "matched_trades",
                "same_day_matched",
                "later_matched",
                "total_trades",
                "win_rate",
                "avg_return_pct",
                "median_return_pct",
                "avg_win_pct",
                "avg_loss_pct",
                "expected_value_pct",
            ]
        )

    action_breakdown_df.to_csv(action_breakdown_output_path, index=False)
    action_daily_df.to_csv(action_daily_output_path, index=False)

    print("Strategy Comparison Summary")
    print(summary_df.to_string(index=False))
    print()
    print("Coverage by day")
    print(coverage_df.to_string(index=False))
    print()
    print(f"Saved summary: {summary_output_path}")
    print(f"Saved daily breakdown: {daily_output_path}")
    print(f"Saved action breakdown: {action_breakdown_output_path}")
    print(f"Saved action daily breakdown: {action_daily_output_path}")


if __name__ == "__main__":
    main()
