from __future__ import annotations

import argparse
import re
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd


ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_ML_DIR = ROOT_DIR / "ML"
DEFAULT_TRADES_DB = ROOT_DIR / "data" / "master" / "trades_master.duckdb"
DEFAULT_OUTPUT_DIR = ROOT_DIR / "data" / "outputs"
DEFAULT_TOP_TRADES_LATEST = DEFAULT_OUTPUT_DIR / "top_trades_latest.csv"
DEFAULT_RANKED_TRADES_LATEST = DEFAULT_OUTPUT_DIR / "ranked_trades_latest.csv"
DEFAULT_PERFORMANCE_LOG = DEFAULT_OUTPUT_DIR / "performance_log.csv"

PREDICTED_TIER_BONUS = {
    "A": 1.25,
    "B": 0.85,
    "C": -0.25,
    "D": -1.25,
}

FILTERED_TIER_BONUS = {
    "A": 1.1,
    "A_PRIME": 0.8,
    "B": 0.15,
    "C": 0.45,
    "DROPPED": -0.35,
    "D": -1.1,
}

GRADE_BUCKET_BONUS = {
    "A+": 0.9,
    "A": 0.8,
    "A-": 0.7,
    "B+": 0.45,
    "B": 0.3,
    "B-": 0.2,
    "C+": -0.1,
    "C": -0.15,
    "C-": -0.2,
    "D+": -0.3,
    "D": -0.4,
    "D-": -0.45,
    "F": -0.5,
}

QUANT_RATING_BONUS = {
    "STRONG BUY": 0.45,
    "BUY": 0.25,
    "HOLD": 0.0,
    "SELL": -0.2,
    "STRONG SELL": -0.35,
}

BIAS_BONUS = {
    "BULLISH": 0.35,
    "NEUTRAL": 0.0,
    "BEARISH": -0.2,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Select top tradeable options signals from the latest ML output."
    )
    parser.add_argument(
        "--latest-csv",
        type=Path,
        default=None,
        help="Optional explicit path to sample_predictions_with_tiers_*.csv.",
    )
    parser.add_argument(
        "--ml-dir",
        type=Path,
        default=DEFAULT_ML_DIR,
        help="Directory containing sample_predictions_with_tiers_*.csv files.",
    )
    parser.add_argument(
        "--trades-db",
        type=Path,
        default=DEFAULT_TRADES_DB,
        help="DuckDB file containing trades_master history.",
    )
    parser.add_argument(
        "--output-csv",
        type=Path,
        default=DEFAULT_TOP_TRADES_LATEST,
        help="Where to save the latest selected top trades CSV.",
    )
    parser.add_argument(
        "--ranked-output-csv",
        type=Path,
        default=DEFAULT_RANKED_TRADES_LATEST,
        help="Where to save the latest ranked-universe CSV.",
    )
    parser.add_argument(
        "--performance-log-csv",
        type=Path,
        default=DEFAULT_PERFORMANCE_LOG,
        help="Append/update per-run summary metrics here.",
    )
    parser.add_argument(
        "--top-n",
        type=int,
        default=25,
        help="Number of trades to keep after ranking A+ and A candidates.",
    )
    parser.add_argument(
        "--history-days",
        type=int,
        default=30,
        help="Maximum number of prior trading days to use from trades_master.",
    )
    parser.add_argument(
        "--segment-min-history",
        type=int,
        default=5000,
        help="Fallback to global percentile when a segment has fewer rows than this.",
    )
    return parser.parse_args()


def extract_signal_date_from_name(path: Path) -> pd.Timestamp | None:
    match = re.search(r"sample_predictions_with_tiers_(\d{8})\.csv$", path.name)
    if not match:
        return None
    return pd.to_datetime(match.group(1), format="%Y%m%d", errors="coerce")


def find_latest_prediction_csv(ml_dir: Path) -> Path:
    candidates: list[tuple[pd.Timestamp, float, Path]] = []
    for path in ml_dir.glob("sample_predictions_with_tiers_*.csv"):
        file_date = extract_signal_date_from_name(path)
        if file_date is None or pd.isna(file_date):
            continue
        candidates.append((file_date, path.stat().st_mtime, path))

    if not candidates:
        raise FileNotFoundError(
            f"No dated sample_predictions_with_tiers_*.csv files found in {ml_dir}"
        )

    candidates.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return candidates[0][2]


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


def normalize_text(series: pd.Series) -> pd.Series:
    return series.astype(str).str.strip()


def normalize_upper_token(series: pd.Series) -> pd.Series:
    return normalize_text(series).str.upper().str.replace(" ", "_")


def normalize_bool_series(series: pd.Series) -> pd.Series:
    if pd.api.types.is_bool_dtype(series):
        return series.fillna(False)

    text = normalize_text(series).str.lower()
    return text.isin(["1", "true", "yes", "y"])


def normalize_grade_value(value: object) -> str:
    if value is None or pd.isna(value):
        return ""
    return str(value).strip().upper()


def add_optional_numeric_column(frame: pd.DataFrame, column_name: str) -> None:
    if column_name not in frame.columns:
        frame[column_name] = np.nan
    else:
        frame[column_name] = pd.to_numeric(frame[column_name], errors="coerce")


def add_optional_text_column(frame: pd.DataFrame, column_name: str) -> None:
    if column_name not in frame.columns:
        frame[column_name] = ""
    else:
        frame[column_name] = normalize_text(frame[column_name])


def add_optional_bool_column(frame: pd.DataFrame, column_name: str) -> None:
    if column_name not in frame.columns:
        frame[column_name] = False
    else:
        frame[column_name] = normalize_bool_series(frame[column_name])


def scaled_series(series: pd.Series, scale: float) -> pd.Series:
    numeric = pd.to_numeric(series, errors="coerce")
    if numeric.notna().sum() == 0:
        return pd.Series(np.zeros(len(series)), index=series.index, dtype=float)

    lower = float(numeric.quantile(0.05))
    upper = float(numeric.quantile(0.95))
    if not np.isfinite(lower) or not np.isfinite(upper) or upper <= lower:
        filled = numeric.fillna(float(numeric.median() if numeric.notna().any() else 0.0))
        return pd.Series(np.zeros(len(series)), index=series.index, dtype=float) if filled.nunique(dropna=True) <= 1 else (
            ((filled - filled.min()) / (filled.max() - filled.min())).clip(0.0, 1.0) * scale
        )

    return ((numeric.clip(lower, upper) - lower) / (upper - lower)).fillna(0.0).clip(0.0, 1.0) * scale


def build_context_rerank_features(latest: pd.DataFrame) -> pd.DataFrame:
    work = latest.copy()

    work["predicted_tier_bonus"] = normalize_text(work.get("predicted_tier_cal", "")).map(PREDICTED_TIER_BONUS).fillna(0.0)
    work["filtered_tier_bonus"] = normalize_upper_token(work.get("filteredtier", "")).map(FILTERED_TIER_BONUS).fillna(0.0)
    work["growth_bonus"] = work.get("growth", "").map(normalize_grade_value).map(GRADE_BUCKET_BONUS).fillna(0.0)
    work["momentum_bonus"] = work.get("momentum", "").map(normalize_grade_value).map(GRADE_BUCKET_BONUS).fillna(0.0)
    work["eps_rev_bonus"] = work.get("eps_rev", "").map(normalize_grade_value).map(GRADE_BUCKET_BONUS).fillna(0.0)
    work["quant_rating_bonus"] = work.get("quant_rating", "").map(normalize_grade_value).map(QUANT_RATING_BONUS).fillna(0.0)
    work["bias_bonus"] = work.get("bias", "").map(normalize_grade_value).map(BIAS_BONUS).fillna(0.0)

    iv_crush_penalty = np.where(work.get("iv_crush_risk", False), -1.35, 0.3)
    gamma_penalty = np.where(work.get("gamma_penalty_flag", False), -0.8, 0.0)
    work["iv_crush_bonus"] = pd.Series(iv_crush_penalty, index=work.index, dtype=float)
    work["gamma_penalty_bonus"] = pd.Series(gamma_penalty, index=work.index, dtype=float)

    expiry_bonus = np.select(
        [
            normalize_text(work.get("expiry_bucket", "")).str.lower().eq("medium_term"),
            normalize_text(work.get("expiry_bucket", "")).str.lower().eq("long_term"),
            normalize_text(work.get("expiry_bucket", "")).str.lower().eq("short_term"),
        ],
        [0.25, 0.05, -0.3],
        default=0.0,
    )
    work["expiry_bonus"] = pd.Series(expiry_bonus, index=work.index, dtype=float)

    work["sector_score_bonus"] = scaled_series(work.get("sector_score", np.nan), 0.85)
    work["rsi_score_bonus"] = scaled_series(work.get("rsi_score", np.nan), 0.75)
    work["trend_score_bonus"] = scaled_series(work.get("score_trend_adj_raw", np.nan), 0.55)
    work["iv_context_bonus"] = scaled_series(work.get("score_iv_context", np.nan), 0.45)
    work["priority_score_bonus"] = scaled_series(work.get("priority_score", np.nan), 0.35)
    work["prob_calibrated_bonus"] = scaled_series(work.get("prob_calibrated", np.nan), 0.35)

    rsi_values = pd.to_numeric(work.get("rsi", np.nan), errors="coerce")
    work["rsi_window_bonus"] = np.select(
        [
            rsi_values.between(55, 75, inclusive="both"),
            rsi_values.between(50, 80, inclusive="both"),
            rsi_values.notna(),
        ],
        [0.25, 0.1, -0.15],
        default=0.0,
    )

    work["context_rerank_score"] = (
        work["predicted_tier_bonus"]
        + work["filtered_tier_bonus"]
        + work["growth_bonus"]
        + work["momentum_bonus"]
        + work["eps_rev_bonus"]
        + work["quant_rating_bonus"]
        + work["bias_bonus"]
        + work["iv_crush_bonus"]
        + work["gamma_penalty_bonus"]
        + work["expiry_bonus"]
        + work["sector_score_bonus"]
        + work["rsi_score_bonus"]
        + work["trend_score_bonus"]
        + work["iv_context_bonus"]
        + work["priority_score_bonus"]
        + work["prob_calibrated_bonus"]
        + work["rsi_window_bonus"]
    )

    return work


def empirical_percentile(sorted_hist: np.ndarray, values: np.ndarray) -> np.ndarray:
    left = np.searchsorted(sorted_hist, values, side="left")
    right = np.searchsorted(sorted_hist, values, side="right")
    return 100.0 * (left + 0.5 * (right - left)) / len(sorted_hist)


def classify_final_tier(segmented_pct: float, global_pct: float) -> str:
    if segmented_pct >= 99.0 and global_pct >= 92.0:
        return "A+"
    if segmented_pct >= 96.0 and global_pct >= 82.0:
        return "A"
    if segmented_pct >= 88.0:
        return "B"
    return "lower"


def build_signal_id(ticker: str, signal_date: pd.Timestamp) -> str:
    return f"{ticker}_{signal_date.strftime('%Y-%m-%d')}"


def normalize_entry_time(latest_df: pd.DataFrame, signal_date: pd.Timestamp) -> pd.Series:
    if "entry_time" in latest_df.columns:
        entry = pd.to_datetime(latest_df["entry_time"], errors="coerce")
        if entry.notna().any():
            return entry

    if "signal_date" in latest_df.columns:
        signal_entry = pd.to_datetime(latest_df["signal_date"], errors="coerce")
        if signal_entry.notna().any():
            return signal_entry

    return pd.Series(pd.Timestamp(signal_date.date()), index=latest_df.index)


def load_latest_predictions(csv_path: Path) -> tuple[pd.DataFrame, pd.Timestamp]:
    latest = pd.read_csv(csv_path, low_memory=False)
    signal_date = None

    if "signal_date" in latest.columns:
        signal_dates = pd.to_datetime(latest["signal_date"], errors="coerce").dropna()
        if not signal_dates.empty:
            signal_date = signal_dates.iloc[0].normalize()

    if signal_date is None:
        signal_date = extract_signal_date_from_name(csv_path)

    if signal_date is None or pd.isna(signal_date):
        raise ValueError(
            f"Could not determine signal date from {csv_path}. "
            "Expected signal_date column or dated filename."
        )

    required_cols = ["ticker", "adaptive_score_final", "optionType", "dte"]
    missing = [col for col in required_cols if col not in latest.columns]
    if missing:
        raise ValueError(f"Latest predictions file is missing required columns: {missing}")

    latest = latest.copy()
    latest["ticker"] = latest["ticker"].astype(str).str.strip()
    if "optionSymbol" in latest.columns:
        latest["optionSymbol"] = latest["optionSymbol"].astype(str).str.strip()
    else:
        latest["optionSymbol"] = pd.Series([None] * len(latest), index=latest.index)
    latest["optionType"] = latest["optionType"].astype(str).str.strip().str.lower()
    latest["dte"] = pd.to_numeric(latest["dte"], errors="coerce")
    latest["adaptive_score_final"] = pd.to_numeric(
        latest["adaptive_score_final"], errors="coerce"
    )
    if "predicted_tier_cal" in latest.columns:
        latest["predicted_tier_cal"] = latest["predicted_tier_cal"].astype(str).str.strip()
    if "filteredtier" in latest.columns:
        latest["filteredtier"] = latest["filteredtier"].astype(str).str.strip()
    if "live_eligible" in latest.columns:
        live = latest["live_eligible"]
        if pd.api.types.is_bool_dtype(live):
            latest["live_eligible"] = live
        else:
            latest["live_eligible"] = (
                live.astype(str).str.strip().str.lower().isin(["1", "true", "yes"])
            )

    add_optional_text_column(latest, "growth")
    add_optional_text_column(latest, "momentum")
    add_optional_text_column(latest, "eps_rev")
    add_optional_text_column(latest, "quant_rating")
    add_optional_text_column(latest, "bias")
    add_optional_text_column(latest, "expiry_bucket")
    add_optional_bool_column(latest, "iv_crush_risk")
    add_optional_bool_column(latest, "gamma_penalty_flag")
    add_optional_numeric_column(latest, "sector_score")
    add_optional_numeric_column(latest, "rsi_score")
    add_optional_numeric_column(latest, "priority_score")
    add_optional_numeric_column(latest, "prob_calibrated")
    add_optional_numeric_column(latest, "score_trend_adj_raw")
    add_optional_numeric_column(latest, "score_iv_context")
    add_optional_numeric_column(latest, "rsi")
    latest["entry_time"] = normalize_entry_time(latest, signal_date)
    latest["dte_bucket"] = latest["dte"].map(dte_bucket)

    latest = latest.dropna(
        subset=["ticker", "adaptive_score_final", "optionType", "dte", "entry_time"]
    ).copy()

    return latest, signal_date


def load_historical_scored_rows(
    trades_db: Path,
    signal_date: pd.Timestamp,
    history_days: int,
) -> pd.DataFrame:
    con = duckdb.connect(str(trades_db), read_only=True)
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
                s.ticker,
                s.entry_time,
                s.trade_date,
                s.optionType,
                s.dte,
                s.adaptive_score_final
            FROM scored s
            JOIN hist_days h
              ON s.trade_date = h.trade_date
            """,
            [signal_date.date(), history_days],
        ).fetchdf()
    finally:
        con.close()

    if hist.empty:
        raise ValueError(
            f"No historical adaptive_score_final rows found before {signal_date.date()}"
        )

    hist["optionType"] = hist["optionType"].astype(str).str.strip().str.lower()
    hist["dte"] = pd.to_numeric(hist["dte"], errors="coerce")
    hist["adaptive_score_final"] = pd.to_numeric(hist["adaptive_score_final"], errors="coerce")
    hist["trade_date"] = pd.to_datetime(hist["trade_date"], errors="coerce").dt.date
    hist["dte_bucket"] = hist["dte"].map(dte_bucket)
    hist = hist.dropna(subset=["adaptive_score_final", "optionType", "dte"]).copy()
    return hist


def build_top_trades(
    latest_df: pd.DataFrame,
    hist_df: pd.DataFrame,
    top_n: int,
    segment_min_history: int,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, int | float | str]]:
    latest = latest_df.copy()
    hist = hist_df.copy()

    counts = {"before_filter": len(latest)}

    latest = latest[latest["optionType"] == "call"].copy()
    if "predicted_tier_cal" in latest.columns:
        latest = latest[latest["predicted_tier_cal"].isin(["A", "B"])].copy()
    if "filteredtier" in latest.columns:
        latest = latest[latest["filteredtier"].isin(["A", "A_prime", "C"])].copy()
    if "live_eligible" in latest.columns:
        latest = latest[latest["live_eligible"]].copy()

    counts["after_filter"] = len(latest)

    latest["segment"] = latest[["optionType", "dte_bucket"]].astype(str).agg("|".join, axis=1)
    hist["segment"] = hist[["optionType", "dte_bucket"]].astype(str).agg("|".join, axis=1)

    # Keep one live candidate per ticker using the best adaptive_score_final.
    latest = (
        latest.sort_values(
            ["ticker", "adaptive_score_final", "entry_time"],
            ascending=[True, False, False],
        )
        .drop_duplicates(subset=["ticker"], keep="first")
        .copy()
    )
    counts["after_dedupe"] = len(latest)

    global_hist_sorted = np.sort(hist["adaptive_score_final"].to_numpy())
    latest["global_percentile"] = empirical_percentile(
        global_hist_sorted,
        latest["adaptive_score_final"].to_numpy(),
    )

    seg_hist = {
        seg: np.sort(group["adaptive_score_final"].to_numpy())
        for seg, group in hist.groupby("segment")
    }
    seg_sizes = {seg: len(arr) for seg, arr in seg_hist.items()}

    segmented_raw = []
    for seg, score in zip(latest["segment"], latest["adaptive_score_final"]):
        hist_scores = seg_hist.get(seg)
        if hist_scores is None or len(hist_scores) == 0:
            segmented_raw.append(np.nan)
        else:
            segmented_raw.append(empirical_percentile(hist_scores, np.array([score]))[0])

    latest["segment_hist_n"] = latest["segment"].map(seg_sizes).fillna(0).astype(int)
    latest["segment_fallback"] = latest["segment_hist_n"] < segment_min_history
    latest["segmented_percentile"] = np.where(
        latest["segment_fallback"],
        latest["global_percentile"],
        segmented_raw,
    )
    latest["final_tier"] = [
        classify_final_tier(seg, glob)
        for seg, glob in zip(latest["segmented_percentile"], latest["global_percentile"])
    ]
    latest = build_context_rerank_features(latest)
    latest["selector_rank_score"] = (
        latest["segmented_percentile"]
        + (0.35 * latest["global_percentile"])
        + (2.75 * latest["context_rerank_score"])
    )

    latest["signal_date"] = latest["entry_time"].dt.strftime("%Y-%m-%d")
    latest["signal_id"] = [
        build_signal_id(ticker, pd.Timestamp(signal_date))
        for ticker, signal_date in zip(latest["ticker"], latest["entry_time"].dt.normalize())
    ]

    ranked_universe = latest[
        [
            "signal_id",
            "ticker",
            "optionSymbol",
            "signal_date",
            "optionType",
            "dte",
            "dte_bucket",
            "adaptive_score_final",
            "segmented_percentile",
            "global_percentile",
            "final_tier",
            "segment_hist_n",
            "segment_fallback",
            "context_rerank_score",
            "selector_rank_score",
            "predicted_tier_cal",
            "filteredtier",
            "growth",
            "momentum",
            "eps_rev",
            "quant_rating",
            "bias",
            "iv_crush_risk",
            "gamma_penalty_flag",
            "sector_score",
            "rsi_score",
            "priority_score",
            "prob_calibrated",
            "score_trend_adj_raw",
            "score_iv_context",
        ]
    ].copy()
    tier_rank_order = {"A+": 0, "A": 1, "B": 2, "lower": 3}
    ranked_universe["_tier_order"] = ranked_universe["final_tier"].map(tier_rank_order).fillna(9)
    ranked_universe = ranked_universe.sort_values(
        ["_tier_order", "selector_rank_score", "segmented_percentile", "global_percentile", "adaptive_score_final"],
        ascending=[True, False, False, False, False],
    )
    ranked_universe = ranked_universe.drop(columns=["_tier_order"])

    counts["total_a_plus"] = int((latest["final_tier"] == "A+").sum())
    counts["total_a"] = int((latest["final_tier"] == "A").sum())
    counts["total_b"] = int((latest["final_tier"] == "B").sum())

    selected = latest[latest["final_tier"].isin(["A+", "A"])].copy()
    selected = selected.sort_values(
        ["selector_rank_score", "segmented_percentile", "global_percentile", "adaptive_score_final"],
        ascending=[False, False, False, False],
    ).head(top_n)

    result = selected[
        [
            "signal_id",
            "ticker",
            "optionSymbol",
            "signal_date",
            "entry_time",
            "optionType",
            "dte",
            "dte_bucket",
            "adaptive_score_final",
            "segmented_percentile",
            "global_percentile",
            "final_tier",
            "context_rerank_score",
            "selector_rank_score",
            "predicted_tier_cal",
            "filteredtier",
            "growth",
            "momentum",
            "eps_rev",
            "quant_rating",
            "bias",
            "iv_crush_risk",
            "gamma_penalty_flag",
            "sector_score",
            "rsi_score",
            "priority_score",
            "prob_calibrated",
            "score_trend_adj_raw",
            "score_iv_context",
        ]
    ].copy()
    counts["final_selected"] = len(result)
    counts["avg_segmented_percentile_selected"] = (
        round(float(selected["segmented_percentile"].mean()), 6) if not selected.empty else np.nan
    )
    counts["avg_global_percentile_selected"] = (
        round(float(selected["global_percentile"].mean()), 6) if not selected.empty else np.nan
    )
    return result, ranked_universe, counts


def snapshot_path(latest_path: Path, signal_date: pd.Timestamp) -> Path:
    return latest_path.with_name(
        latest_path.name.replace("_latest.csv", f"_{signal_date.strftime('%Y%m%d')}.csv")
    )


def save_outputs(
    top_trades: pd.DataFrame,
    ranked_universe: pd.DataFrame,
    signal_date: pd.Timestamp,
    top_latest_csv: Path,
    ranked_latest_csv: Path,
) -> dict[str, Path]:
    top_dated_csv = snapshot_path(top_latest_csv, signal_date)
    ranked_dated_csv = snapshot_path(ranked_latest_csv, signal_date)

    for output_path in [top_latest_csv, ranked_latest_csv, top_dated_csv, ranked_dated_csv]:
        output_path.parent.mkdir(parents=True, exist_ok=True)

    top_trades.to_csv(top_latest_csv, index=False)
    top_trades.to_csv(top_dated_csv, index=False)
    ranked_universe.to_csv(ranked_latest_csv, index=False)
    ranked_universe.to_csv(ranked_dated_csv, index=False)

    return {
        "top_latest": top_latest_csv,
        "top_dated": top_dated_csv,
        "ranked_latest": ranked_latest_csv,
        "ranked_dated": ranked_dated_csv,
    }


def update_performance_log(
    log_csv: Path,
    signal_date: pd.Timestamp,
    counts: dict[str, int | float | str],
) -> None:
    log_csv.parent.mkdir(parents=True, exist_ok=True)
    log_date = signal_date.strftime("%Y-%m-%d")
    row = pd.DataFrame(
        [
            {
                "date": log_date,
                "total_candidates_before_filter": counts["before_filter"],
                "total_after_filter": counts["after_filter"],
                "total_after_dedupe": counts["after_dedupe"],
                "total_A_plus": counts["total_a_plus"],
                "total_A": counts["total_a"],
                "total_B": counts["total_b"],
                "total_selected": counts["final_selected"],
                "avg_segmented_percentile_selected": counts["avg_segmented_percentile_selected"],
                "avg_global_percentile_selected": counts["avg_global_percentile_selected"],
            }
        ]
    )

    if log_csv.exists():
        existing = pd.read_csv(log_csv, low_memory=False)
        if "date" not in existing.columns:
            existing = pd.DataFrame(columns=row.columns)
        existing = existing[existing["date"].astype(str) != log_date].copy()
        updated = pd.concat([existing, row], ignore_index=True)
    else:
        updated = row

    updated["date"] = pd.to_datetime(updated["date"], errors="coerce").dt.strftime("%Y-%m-%d")
    updated = updated.sort_values("date").reset_index(drop=True)
    updated.to_csv(log_csv, index=False)


def main() -> None:
    args = parse_args()
    latest_csv = args.latest_csv or find_latest_prediction_csv(args.ml_dir)
    latest_df, signal_date = load_latest_predictions(latest_csv)
    hist_df = load_historical_scored_rows(args.trades_db, signal_date, args.history_days)
    top_trades, ranked_universe, counts = build_top_trades(
        latest_df=latest_df,
        hist_df=hist_df,
        top_n=args.top_n,
        segment_min_history=args.segment_min_history,
    )
    saved_paths = save_outputs(
        top_trades=top_trades,
        ranked_universe=ranked_universe,
        signal_date=signal_date,
        top_latest_csv=args.output_csv,
        ranked_latest_csv=args.ranked_output_csv,
    )
    update_performance_log(args.performance_log_csv, signal_date, counts)

    print(f"Latest predictions file: {latest_csv}")
    print(f"Date processed: {signal_date.date()}")
    print(f"Historical scored rows used: {len(hist_df)}")
    print(f"Candidates before filter: {counts['before_filter']}")
    print(f"Candidates after filter: {counts['after_filter']}")
    print(f"Candidates after dedupe: {counts['after_dedupe']}")
    print(f"A+ trades: {counts['total_a_plus']}")
    print(f"A trades: {counts['total_a']}")
    print(f"Total selected: {counts['final_selected']}")
    print(f"Top trades latest saved to: {saved_paths['top_latest']}")
    print(f"Top trades dated saved to: {saved_paths['top_dated']}")
    print(f"Ranked universe latest saved to: {saved_paths['ranked_latest']}")
    print(f"Ranked universe dated saved to: {saved_paths['ranked_dated']}")
    print(f"Performance log updated at: {args.performance_log_csv}")
    print(top_trades.to_string(index=False))


if __name__ == "__main__":
    main()
