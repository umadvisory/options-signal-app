from fastapi import FastAPI
import duckdb
import pandas as pd
import glob
import os
import math
import json
import re
from copy import deepcopy
from datetime import datetime, timezone

app = FastAPI()


# 🔍 Find latest CSV from your ML output
def get_latest_file():
    base_path = ROOT_DIR / "ML" if "ROOT_DIR" in globals() else Path(__file__).resolve().parents[1] / "ML"
    files = glob.glob(str(base_path / "sample_predictions_with_tiers_*.csv"))
    
    if not files:
        return None
    
    latest_file = max(files, key=os.path.getmtime)
    return latest_file

def get_previous_file(current_file: str | None):
    base_path = ROOT_DIR / "ML" if "ROOT_DIR" in globals() else Path(__file__).resolve().parents[1] / "ML"
    files = sorted(glob.glob(str(base_path / "sample_predictions_with_tiers_*.csv")), key=os.path.getmtime, reverse=True)
    if not files:
        return None
    if current_file and current_file in files:
        current_index = files.index(current_file)
        if current_index + 1 < len(files):
            return files[current_index + 1]
        return None
    return files[1] if len(files) > 1 else None

def extract_signal_file_date(file_path: str | None):
    if not file_path:
        return None
    match = re.search(r"sample_predictions_with_tiers_(\d{8})\.csv$", os.path.basename(file_path))
    if not match:
        return None
    try:
        return datetime.strptime(match.group(1), "%Y%m%d").date()
    except ValueError:
        return None

def get_recent_signal_files(current_file: str | None, count: int = 5):
    base_path = ROOT_DIR / "ML" if "ROOT_DIR" in globals() else Path(__file__).resolve().parents[1] / "ML"
    files = []
    for path in glob.glob(str(base_path / "sample_predictions_with_tiers_*.csv")):
        if extract_signal_file_date(path) is not None:
            files.append(path)

    files = sorted(files, key=lambda p: extract_signal_file_date(p) or datetime.min.date())
    if not files:
        return []

    if current_file and current_file in files:
        current_index = files.index(current_file)
        start_index = max(0, current_index - count)
        return list(reversed(files[start_index:current_index]))

    return list(reversed(files[-(count + 1):-1])) if len(files) > 1 else []

from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
ML_DIR = ROOT_DIR / "ML"
REPORTS_DIR = ROOT_DIR / "data" / "master" / "reports"
MACRO_DIR = ROOT_DIR / "data" / "macro"
TRADES_DB_PATH = ROOT_DIR / "data" / "master" / "trades_master.duckdb"
SNAPSHOT_PATH = ROOT_DIR / "backend" / "data" / "production_snapshot.json"
TOP_TRADES_OUTPUT_PATH = ROOT_DIR / "data" / "outputs" / "top_trades_latest.csv"
RANKED_TRADES_OUTPUT_PATH = ROOT_DIR / "data" / "outputs" / "ranked_trades_latest.csv"
ETF_SHEET_NAME = "ETF_Overlay_Summary"
SECTOR_SUMMARY_SHEET = "Sector Summary"
TICKER_SUMMARY_SHEET = "Ticker Summary"
TOP_TRADES_PAYLOAD_CACHE = {}

SECTOR_TO_ETF_FALLBACK = {
    "Basic Materials": "XLB",
    "Communication Services": "XLC",
    "Consumer Cyclical": "XLY",
    "Consumer Defensive": "XLP",
    "Energy": "XLE",
    "Financial Services": "XLF",
    "Healthcare": "XLV",
    "Industrials": "XLI",
    "Technology": "XLK",
    "Utilities": "XLU",
    "Real Estate": "XLRE",
}

def get_latest_matching_file(folder: Path, pattern: str):
    files = list(folder.glob(pattern))
    if not files:
        return None
    return max(files, key=lambda f: f.stat().st_mtime)

def load_latest_etf_overlay():
    latest_xlsx = get_latest_matching_file(ML_DIR, "ml_predictions_summary_*.xlsx")
    if latest_xlsx is None:
        return {}

    try:
        df = pd.read_excel(
            latest_xlsx,
            sheet_name=ETF_SHEET_NAME,
            skiprows=2
        )

        df.columns = [str(c).strip().lower() for c in df.columns]

        required_cols = ["sector", "etf", "bias", "win_rate_4d", "breadth"]
        existing_cols = [c for c in required_cols if c in df.columns]
        df = df[existing_cols].copy()

        if "sector" not in df.columns:
            return {}

        df["sector"] = df["sector"].astype(str).str.strip()

        # sector -> overlay info
        return df.set_index("sector").to_dict(orient="index")

    except Exception as e:
        print(f"[ETF OVERLAY] Failed to load: {e}")
        return {}

def load_latest_sector_outlook():
    latest_xlsx = get_latest_matching_file(ML_DIR, "ml_predictions_summary_*.xlsx")
    if latest_xlsx is None:
        return {
            "sectors": [],
            "sourceFile": None
        }

    try:
        sector_df = pd.read_excel(latest_xlsx, sheet_name=SECTOR_SUMMARY_SHEET)
        ticker_df = pd.read_excel(latest_xlsx, sheet_name=TICKER_SUMMARY_SHEET)

        sector_df.columns = [str(c).strip().lower() for c in sector_df.columns]
        ticker_df.columns = [str(c).strip().lower() for c in ticker_df.columns]

        if "sector" not in sector_df.columns or "sector" not in ticker_df.columns or "ticker" not in ticker_df.columns:
            return {
                "sectors": [],
                "sourceFile": latest_xlsx.name
            }

        sector_df["sector"] = sector_df["sector"].astype(str).str.strip()
        ticker_df["sector"] = ticker_df["sector"].astype(str).str.strip()
        ticker_df["ticker"] = ticker_df["ticker"].astype(str).str.strip()

        for col in [
            "call_score_sum",
            "put_score_sum",
            "total_signals",
            "avg_score",
            "net_score",
            "conviction_score"
        ]:
            if col in sector_df.columns:
                sector_df[col] = pd.to_numeric(sector_df[col], errors="coerce")

        for col in [
            "num_a",
            "total_signals",
            "conviction_score",
            "net_score"
        ]:
            if col in ticker_df.columns:
                ticker_df[col] = pd.to_numeric(ticker_df[col], errors="coerce")

        if "direction" in ticker_df.columns:
            ticker_df["direction"] = ticker_df["direction"].astype(str).str.strip()

        if "quant_rating" in ticker_df.columns:
            ticker_df["quant_rating"] = ticker_df["quant_rating"].astype(str).str.strip()

        # Ticker Summary is already one row per ticker, so we can rank sectors from
        # single-ticker contributions without reintroducing option-row duplication.
        ticker_level_df = ticker_df[["ticker", "sector"]].copy()
        ticker_level_df["avg_score"] = pd.to_numeric(ticker_df.get("avg_score"), errors="coerce")
        ticker_level_df["conviction_score"] = pd.to_numeric(ticker_df.get("conviction_score"), errors="coerce")
        ticker_level_df["num_a"] = pd.to_numeric(ticker_df.get("num_a"), errors="coerce").fillna(0.0)
        ticker_level_df["total_signals"] = pd.to_numeric(ticker_df.get("total_signals"), errors="coerce").fillna(0.0)

        # Use avg_score as the primary per-ticker quality proxy because conviction_score
        # is more affected by repeat signal volume. Fall back to conviction_score if needed.
        ticker_level_df["best_score"] = ticker_level_df["avg_score"].where(
            ticker_level_df["avg_score"].notna(),
            ticker_level_df["conviction_score"]
        )

        sector_a_counts = {}
        if "num_a" in ticker_df.columns:
            sector_a_counts = (
                ticker_df.groupby("sector", dropna=False)["num_a"]
                .sum(min_count=1)
                .fillna(0)
                .astype(int)
                .to_dict()
            )

        sector_df["strong_signal_count"] = sector_df["sector"].map(sector_a_counts).fillna(0)
        total_signal_series = pd.to_numeric(sector_df.get("total_signals"), errors="coerce")
        avg_score_series = pd.to_numeric(sector_df.get("avg_score"), errors="coerce")
        density = sector_df["strong_signal_count"] / total_signal_series.replace(0, pd.NA)
        sector_df["a_tier_density"] = density.fillna(0.0)
        sector_df["focus_score"] = (avg_score_series.fillna(0.0) * sector_df["a_tier_density"]).fillna(0.0)
        previous_rank_df = sector_df.copy()
        previous_sort_cols = [c for c in ["focus_score", "conviction_score", "net_score", "total_signals"] if c in previous_rank_df.columns]
        if previous_sort_cols:
            previous_rank_df = previous_rank_df.sort_values(by=previous_sort_cols, ascending=[False] * len(previous_sort_cols))
        previous_rank_map = {
            str(row.get("sector")).strip(): rank
            for rank, (_, row) in enumerate(previous_rank_df.iterrows(), start=1)
            if str(row.get("sector")).strip()
        }

        ticker_sort_cols = []
        for col in ["num_a", "conviction_score", "total_signals", "net_score"]:
            if col in ticker_df.columns:
                ticker_sort_cols.append(col)

        ascending = [False] * len(ticker_sort_cols) if ticker_sort_cols else None
        if ticker_sort_cols:
            ticker_df = ticker_df.sort_values(by=ticker_sort_cols, ascending=ascending)

        top_tickers_by_sector = {}
        for sector, group in ticker_df.groupby("sector", dropna=False):
            top_rows = group.head(3)
            top_tickers_by_sector[sector] = [
                {
                    "ticker": str(row.get("ticker")).strip(),
                    "grade": None if pd.isna(row.get("quant_rating")) else str(row.get("quant_rating")).strip(),
                    "direction": None if pd.isna(row.get("direction")) else str(row.get("direction")).strip(),
                    "aGradeCount": int(row.get("num_a")) if pd.notna(row.get("num_a")) else 0,
                    "signalCount": int(row.get("total_signals")) if pd.notna(row.get("total_signals")) else 0
                }
                for _, row in top_rows.iterrows()
                if str(row.get("ticker")).strip()
            ]

        etf_overlay_map = load_latest_etf_overlay()

        def classify_flow(call_score, put_score):
            call_value = pd.to_numeric(pd.Series([call_score]), errors="coerce").iloc[0]
            put_value = pd.to_numeric(pd.Series([put_score]), errors="coerce").iloc[0]

            if pd.isna(call_value) or pd.isna(put_value):
                return "Balanced"

            spread = call_value - put_value
            if spread >= 100:
                return "Call-led"
            if spread <= -100:
                return "Put-led"
            return "Balanced"

        sector_metric_rows = []
        for sector_name, group in ticker_level_df.groupby("sector", dropna=False):
            ranked_group = group.sort_values(by=["best_score", "num_a", "total_signals"], ascending=[False, False, False])
            ticker_count = int(ranked_group["ticker"].nunique())
            a_tier_ticker_count = int((ranked_group["num_a"] > 0).sum())
            avg_best_score = pd.to_numeric(ranked_group["best_score"], errors="coerce").mean()
            top5_avg_score = pd.to_numeric(ranked_group["best_score"], errors="coerce").head(5).mean()

            contribution_group = ranked_group.sort_values(by=["num_a", "best_score", "total_signals"], ascending=[False, False, False])
            contribution_weights = pd.to_numeric(contribution_group["num_a"], errors="coerce").fillna(0.0).clip(lower=0.0)
            total_contribution = float(contribution_weights.sum())
            top1_share = float(contribution_weights.iloc[0] / total_contribution * 100.0) if total_contribution > 0 and len(contribution_weights) > 0 else 0.0
            top3_share = float(contribution_weights.head(3).sum() / total_contribution * 100.0) if total_contribution > 0 else 0.0

            raw_breadth = math.log1p(ticker_count)
            capped_breadth = min(raw_breadth, 6.0)
            sector_score = (
                0.5 * (float(top5_avg_score) if pd.notna(top5_avg_score) else 0.0) +
                0.3 * (float(avg_best_score) if pd.notna(avg_best_score) else 0.0) +
                0.2 * capped_breadth
            )

            sector_metric_rows.append(
                {
                    "sector": str(sector_name).strip(),
                    "tickerCount": ticker_count,
                    "aTierTickerCount": a_tier_ticker_count,
                    "avgBestScore": None if pd.isna(avg_best_score) else float(avg_best_score),
                    "top5AvgScore": None if pd.isna(top5_avg_score) else float(top5_avg_score),
                    "top1Share": top1_share,
                    "top3Share": top3_share,
                    "sectorScore": sector_score,
                    "rawBreadth": raw_breadth,
                    "cappedBreadth": capped_breadth,
                }
            )

        sector_metrics_df = pd.DataFrame(sector_metric_rows)
        if not sector_metrics_df.empty:
            sector_metrics_df = sector_metrics_df.sort_values(
                by=["sectorScore", "top5AvgScore", "avgBestScore", "tickerCount"],
                ascending=[False, False, False, False]
            )

        sectors = []
        sector_lookup_df = sector_df.set_index("sector", drop=False)
        for rank, (_, metric_row) in enumerate(sector_metrics_df.iterrows(), start=1):
            sector_name = str(metric_row.get("sector")).strip()
            if not sector_name:
                continue

            if sector_name not in sector_lookup_df.index:
                continue

            row = sector_lookup_df.loc[sector_name]

            etf_info = etf_overlay_map.get(sector_name, {})
            fallback_etf = SECTOR_TO_ETF_FALLBACK.get(sector_name)
            total_signals = int(row.get("total_signals")) if pd.notna(row.get("total_signals")) else 0
            net_score = float(row.get("net_score")) if pd.notna(row.get("net_score")) else None
            conviction_score = float(row.get("conviction_score")) if pd.notna(row.get("conviction_score")) else None
            a_tier_density = float(row.get("a_tier_density")) if pd.notna(row.get("a_tier_density")) else None
            avg_best_score = metric_row.get("avgBestScore")
            top5_avg_score = metric_row.get("top5AvgScore")
            sector_score = metric_row.get("sectorScore")
            top1_share = metric_row.get("top1Share")
            top3_share = metric_row.get("top3Share")
            raw_breadth = metric_row.get("rawBreadth")
            capped_breadth = metric_row.get("cappedBreadth")

            sectors.append({
                "rank": rank,
                "sector": sector_name,
                "etf": str(etf_info.get("etf")).strip() if etf_info.get("etf") is not None else (fallback_etf or "N/A"),
                "bias": str(etf_info.get("bias")).strip() if etf_info.get("bias") is not None else ("No overlay" if fallback_etf else "Neutral"),
                "totalSignals": total_signals,
                "strongSignalCount": sector_a_counts.get(sector_name),
                "aTierDensity": round(a_tier_density * 100, 1) if a_tier_density is not None else None,
                "netScore": round(net_score, 2) if net_score is not None else None,
                "convictionScore": round(conviction_score, 4) if conviction_score is not None else None,
                "flowSkew": classify_flow(row.get("call_score_sum"), row.get("put_score_sum")),
                "topTickers": top_tickers_by_sector.get(sector_name, []),
                "tickerCount": int(metric_row.get("tickerCount") or 0),
                "aTierTickerCount": int(metric_row.get("aTierTickerCount") or 0),
                "top1Share": round(float(top1_share), 1) if top1_share is not None and not pd.isna(top1_share) else None,
                "top3Share": round(float(top3_share), 1) if top3_share is not None and not pd.isna(top3_share) else None,
                "avgBestScore": round(float(avg_best_score), 4) if avg_best_score is not None and not pd.isna(avg_best_score) else None,
                "top5AvgScore": round(float(top5_avg_score), 4) if top5_avg_score is not None and not pd.isna(top5_avg_score) else None,
                "sectorScore": round(float(sector_score), 4) if sector_score is not None and not pd.isna(sector_score) else None,
                "rawBreadth": round(float(raw_breadth), 4) if raw_breadth is not None and not pd.isna(raw_breadth) else None,
                "cappedBreadth": round(float(capped_breadth), 4) if capped_breadth is not None and not pd.isna(capped_breadth) else None,
                "previousRank": previous_rank_map.get(sector_name)
            })

        return {
            "sectors": sectors[:6],
            "sourceFile": latest_xlsx.name
        }

    except Exception as e:
        print(f"[SECTOR OUTLOOK] Failed to load: {e}")
        return {
            "sectors": [],
            "sourceFile": None
        }

def load_latest_strategy_stats():
    if not TRADES_DB_PATH.exists():
        return {
            "highConviction": None,
            "broadBase": None,
            "sourceFile": None
        }

    try:
        return_expr = """
            COALESCE(
              CASE
                WHEN pnl_pct IS NULL THEN NULL
                ELSE
                  CASE
                    WHEN ABS(TRY_CAST(regexp_replace(CAST(pnl_pct AS VARCHAR), '[^0-9\\.-]', '', 'g') AS DOUBLE)) <= 1.5
                      THEN TRY_CAST(regexp_replace(CAST(pnl_pct AS VARCHAR), '[^0-9\\.-]', '', 'g') AS DOUBLE) * 100.0
                    ELSE
                      TRY_CAST(regexp_replace(CAST(pnl_pct AS VARCHAR), '[^0-9\\.-]', '', 'g') AS DOUBLE)
                  END
              END,
              CASE
                WHEN total_risked_usd IS NULL OR TRY_CAST(total_risked_usd AS DOUBLE) = 0 THEN NULL
                ELSE (TRY_CAST(pnl AS DOUBLE) / TRY_CAST(total_risked_usd AS DOUBLE)) * 100.0
              END,
              CASE
                WHEN entry_price IS NULL OR TRY_CAST(entry_price AS DOUBLE) = 0 THEN NULL
                ELSE (TRY_CAST(pnl AS DOUBLE) / TRY_CAST(entry_price AS DOUBLE)) * 100.0
              END
            )
        """

        def format_date_value(value):
            if value is None or pd.isna(value):
                return None
            try:
                return pd.to_datetime(value).date().isoformat()
            except Exception:
                return str(value)

        def fetch_cohort_stats(label: str, cohort_condition: str):
            base_cte = f"""
                WITH prepared AS (
                    SELECT
                        ticker,
                        entry_time,
                        {return_expr} AS return_pct
                    FROM trades_master
                    WHERE entry_time IS NOT NULL
                      AND entry_time >= CURRENT_DATE - INTERVAL '30 days'
                      AND {cohort_condition}
                ),
                cohort AS (
                    SELECT *
                    FROM prepared
                    WHERE return_pct IS NOT NULL
                )
            """

            query = base_cte + """
                SELECT
                    COUNT(*) AS trade_count,
                    COUNT(DISTINCT ticker) AS ticker_count,
                    AVG(CASE WHEN return_pct > 0 THEN 1.0 ELSE 0.0 END) AS win_rate,
                    AVG(return_pct) AS avg_return_pct,
                    quantile_cont(return_pct, 0.50) AS median_return_pct,
                    AVG(CASE WHEN return_pct < 0 THEN 1.0 ELSE 0.0 END) AS loss_rate,
                    AVG(CASE WHEN return_pct < -30 THEN 1.0 ELSE 0.0 END) AS large_loss_rate,
                    MIN(CAST(entry_time AS DATE)) AS min_date,
                    MAX(CAST(entry_time AS DATE)) AS max_date
                FROM cohort
            """

            con = duckdb.connect(str(TRADES_DB_PATH), read_only=True)
            result = con.execute(query).fetchone()

            bucket_query = base_cte + """
                SELECT
                    bucket_range,
                    COUNT(*) AS trade_count
                FROM (
                    SELECT
                        CASE
                            WHEN return_pct < -50 THEN '<-50%'
                            WHEN return_pct >= -50 AND return_pct < 0 THEN '-50%–0%'
                            WHEN return_pct >= 0 AND return_pct < 50 THEN '0–50%'
                            WHEN return_pct >= 50 AND return_pct <= 150 THEN '50–150%'
                            ELSE '>150%'
                        END AS bucket_range
                    FROM cohort
                ) buckets
                GROUP BY bucket_range
            """
            bucket_rows = con.execute(bucket_query).fetchall()

            equity_query = base_cte + """
                , daily AS (
                    SELECT
                        CAST(entry_time AS DATE) AS entry_day,
                        SUM(return_pct) AS daily_return
                    FROM cohort
                    GROUP BY 1
                )
                SELECT
                    entry_day,
                    SUM(daily_return) OVER (
                        ORDER BY entry_day
                        ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
                    ) AS cumulative_return
                FROM daily
                ORDER BY entry_day
            """
            equity_rows = con.execute(equity_query).fetchall()
            con.close()

            if not result or result[0] is None:
                return None

            bucket_order = [
                "<-50%",
                "-50%–0%",
                "0–50%",
                "50–150%",
                ">150%"
            ]
            bucket_map = {str(label): int(count) for label, count in bucket_rows}
            return_distribution = [
                {
                    "range": bucket,
                    "count": bucket_map.get(bucket, 0),
                    "percentage": round((bucket_map.get(bucket, 0) / int(result[0])) * 100, 1) if result[0] else 0.0
                }
                for bucket in bucket_order
            ]

            equity_curve = [
                {
                    "date": format_date_value(day),
                    "value": round(float(value), 1) if value is not None else None
                }
                for day, value in equity_rows
            ]

            return {
                "winRate": round(float(result[2]) * 100, 1) if result[2] is not None else None,
                "sampleSize": int(result[0]) if result[0] is not None else None,
                "tickerCount": int(result[1]) if result[1] is not None else None,
                "minDate": format_date_value(result[7]),
                "maxDate": format_date_value(result[8]),
                "avgReturnPct": round(float(result[3]), 1) if result[3] is not None else None,
                "medianReturnPct": round(float(result[4]), 1) if result[4] is not None else None,
                "lossRate": round(float(result[5]) * 100, 1) if result[5] is not None else None,
                "largeLossRate": round(float(result[6]) * 100, 1) if result[6] is not None else None,
                "worstDrawdownProxy": None,
                "returnDistribution": return_distribution,
                "equityCurve": equity_curve,
                "label": label
            }

        cohort_a_condition = """
            live_eligible = 1
            AND predicted_tier_cal = 'A'
            AND filteredtier = 'A'
            AND adaptive_tier = 'A'
        """

        cohort_b_condition = """
            predicted_tier_cal = 'A'
            AND filteredtier = 'A'
            AND (is_tradeable = TRUE OR is_tradeable = 1)
        """

        return {
            "highConviction": fetch_cohort_stats("Cohort A", cohort_a_condition),
            "broadBase": fetch_cohort_stats("Cohort B", cohort_b_condition),
            "sourceFile": TRADES_DB_PATH.name
        }

    except Exception as e:
        print(f"[STRATEGY STATS] Failed to load: {e}")
        return {
            "highConviction": None,
            "broadBase": None,
            "sourceFile": None
        }

def load_latest_market_regime():
    macro_file = MACRO_DIR / "macro_regime_enriched.csv"
    if not macro_file.exists():
        return None

    try:
        df = pd.read_csv(macro_file)
        if df.empty:
            return None

        df.columns = [str(c).strip().lower() for c in df.columns]
        if "signal_date" in df.columns:
            df["signal_date"] = pd.to_datetime(df["signal_date"], errors="coerce")
            df = df.dropna(subset=["signal_date"]).sort_values("signal_date")

        if df.empty:
            return None

        row = df.iloc[-1]

        def n(col):
            value = pd.to_numeric(pd.Series([row.get(col)]), errors="coerce").iloc[0]
            return float(value) if pd.notna(value) else None

        def pct(value):
            return round(float(value) * 100, 1) if value is not None else None

        vix_level = n("vix_level")
        spy_return = n("spy_return")
        spy_trend_3d = n("spy_trend_3d")
        spy_trend_5d = n("spy_trend_5d")
        trend_strength = n("trend_strength")
        shock_day = n("shock_day")
        vix_mom_3d = n("vix_mom_3d")
        vix_pctile_est = n("vix_pctile_est")

        if vix_level is None:
            vol_label = "Unknown"
        elif vix_level < 15:
            vol_label = "Low"
        elif vix_level < 20:
            vol_label = "Moderate"
        elif vix_level < 25:
            vol_label = "Elevated"
        else:
            vol_label = "High"

        trend_label = "Neutral"
        if spy_trend_5d is not None:
            if spy_trend_5d >= 0.005:
                trend_label = "Supportive"
            elif spy_trend_5d <= -0.005:
                trend_label = "Weak"
            elif spy_trend_5d > 0:
                trend_label = "Mildly Supportive"
            elif spy_trend_5d < 0:
                trend_label = "Mildly Weak"

        is_shock_day = bool(shock_day and shock_day >= 1)
        if is_shock_day:
            regime_label = "Risk-Off"
        elif trend_label in {"Supportive", "Mildly Supportive"} and vol_label in {"Low", "Moderate", "Elevated"}:
            regime_label = "Neutral-to-Supportive"
        elif trend_label in {"Weak", "Mildly Weak"} or vol_label == "High":
            regime_label = "Cautious"
        else:
            regime_label = "Neutral"

        summary = f"VIX is {vol_label.lower()} at {round(vix_level, 1) if vix_level is not None else 'N/A'}, SPY trend is {trend_label.lower()}, and shock-day risk is {'on' if is_shock_day else 'off'}."

        signal_date = row.get("signal_date")
        if pd.notna(signal_date):
            signal_date = str(pd.to_datetime(signal_date).date())
        else:
            signal_date = None

        return {
            "date": signal_date,
            "regime": regime_label,
            "summary": summary,
            "vix": {
                "level": round(vix_level, 2) if vix_level is not None else None,
                "label": vol_label,
                "momentum3d": round(vix_mom_3d, 2) if vix_mom_3d is not None else None,
                "percentile": pct(vix_pctile_est)
            },
            "spy": {
                "return1d": pct(spy_return),
                "trend3d": pct(spy_trend_3d),
                "trend5d": pct(spy_trend_5d),
                "trendLabel": trend_label
            },
            "risk": {
                "shockDay": is_shock_day,
                "trendStrength": round(trend_strength, 2) if trend_strength is not None else None
            }
        }

    except Exception as e:
        print(f"[MARKET REGIME] Failed to load: {e}")
        return None

def canonical_structure_bucket(label):
    normalized = (label or "").strip().upper()
    if normalized in {"DEEP ITM", "ITM"}:
        return "ITM"
    if normalized == "ATM":
        return "ATM"
    return "OTM"

def dte_band(dte):
    if dte is None:
        return (0, 21, "0-21 DTE")
    if dte <= 21:
        return (0, 21, "0-21 DTE")
    if dte <= 45:
        return (22, 45, "22-45 DTE")
    return (46, 90, "46-90 DTE")

def format_hold_window(hold_p25_days, hold_p75_days, median_hold_days):
    if hold_p25_days is not None and hold_p75_days is not None:
        lower = max(1, int(round(hold_p25_days)))
        upper = max(1, int(round(hold_p75_days)))
        if lower == upper:
            return f"{lower} trading days"
        if upper < lower:
            upper = lower
        return f"{lower}-{upper} trading days"
    if median_hold_days is None:
        return None
    lower = max(1, int(round(median_hold_days - 2)))
    upper = max(lower + 1, int(round(median_hold_days + 2)))
    return f"{lower}-{upper} trading days"

def classify_historical_support(win_rate, avg_r_multiple, sample_size, distinct_ticker_count=None):
    if sample_size is None or sample_size < 30 or win_rate is None:
        return "Limited history"
    if sample_size >= 75 and win_rate >= 60:
        return "Strong"
    if sample_size >= 40:
        return "Moderate"
    return "Limited"

def build_translation(action, rsi, etf_bias):
    bias = (etf_bias or "Neutral").strip().lower()
    if action == "ENTER":
        if rsi is not None and rsi >= 68:
            return "Strong continuation setup, but timing matters because momentum is already extended."
        if bias == "bullish":
            return "High-conviction continuation setup, not a late chase."
        return "Higher-priority setup with a clean enough entry profile."
    if action == "WATCH":
        return "Qualified setup, but entry quality matters more than signal strength here."
    return "Broadly qualified, but not a priority versus cleaner names today."

def build_execution_edge_items(rsi, dte, etf_bias, risk_flags, option_type, etf, etf_win_rate, etf_breadth, sector_rank):
    items = []
    bias = (etf_bias or "Neutral").strip().lower()
    option_side = (option_type or "CALL").strip().upper()

    if risk_flags.get("bidOk") and risk_flags.get("liquidityOk") and risk_flags.get("openInterestOk") and risk_flags.get("volumeOk"):
        items.append("Spread and liquidity snapshot support cleaner fills.")
    else:
        items.append("Use the live chain to confirm spread and depth before entry.")

    if etf and etf != "N/A" and etf_win_rate is not None and etf_breadth is not None:
        items.append(f"{etf} sector signal strength: {etf_win_rate}% 4d win rate across {int(etf_breadth)} stocks.")
    elif (bias == "bullish" and option_side == "CALL") or (bias == "bearish" and option_side == "PUT"):
        items.append(f"{etf or 'Sector'} backdrop aligns with the trade direction.")
    elif bias == "no overlay":
        items.append("No live sector overlay, so price action matters more than backdrop.")

    if sector_rank is not None and sector_rank <= 3:
        items.append(f"Sector ranks #{sector_rank} in today's conviction map.")

    if rsi is not None and rsi < 68:
        items.append(f"RSI {round(float(rsi), 1)} stays below the late-extension zone.")
    elif rsi is not None:
        items.append(f"RSI {round(float(rsi), 1)} is elevated, so timing needs more care.")

    return items[:3]

def build_invalidation_items(underlying_price, rsi, dte, etf_bias, risk_flags, option_type):
    items = []
    option_side = (option_type or "CALL").strip().upper()
    move_threshold = 2 if (rsi is not None and rsi >= 65) or (dte is not None and dte <= 21) else 3

    if option_side == "CALL":
        items.append(f"Skip if price moves more than {move_threshold}% above the snapshot before entry.")
    else:
        items.append(f"Skip if price moves more than {move_threshold}% below the snapshot before entry.")

    if rsi is not None and rsi < 68:
        items.append("Skip if RSI pushes into the 68-70 rejection zone before entry.")
    else:
        items.append("Skip if momentum extends further without a reset.")

    if not (risk_flags.get("bidOk") and risk_flags.get("liquidityOk")):
        items.append("Skip unless the live spread and liquidity improve.")
    else:
        items.append("Skip if spread or liquidity deteriorates on the live chain.")

    return items[:3]

def build_expectation_frame(action, dte, median_hold_days, hold_p25_days, hold_p75_days, structure_bucket):
    timeframe = format_hold_window(hold_p25_days, hold_p75_days, median_hold_days)
    if timeframe is None:
        if dte is not None and dte <= 21:
            timeframe = "3-7 trading days"
        elif dte is not None and dte <= 45:
            timeframe = "1-2 weeks"
        else:
            timeframe = "2-4 weeks"

    if action == "ENTER":
        base_case = "Orderly continuation if the trend and liquidity stay intact."
    elif action == "WATCH":
        base_case = "Valid setup, but follow-through matters more than immediacy."
    else:
        base_case = "Secondary setup unless the tape improves."

    if dte is not None and dte <= 21:
        risk = "Time decay becomes the main risk if price chops sideways."
    elif structure_bucket == "OTM":
        risk = "Premium can decay quickly if the move stalls."
    else:
        risk = "The edge weakens if momentum cools and sector support fades."

    return {
        "timeframe": timeframe,
        "baseCase": base_case,
        "risk": risk
    }


def build_market_insight(market_regime, trades):
    counts = {"ENTER": 0, "WATCH": 0, "WAIT": 0}
    for trade in trades or []:
        action = str(trade.get("action") or "").strip().upper()
        if action in counts:
            counts[action] += 1

    enter_count = counts["ENTER"]
    watch_count = counts["WATCH"]
    wait_count = counts["WAIT"]

    regime_label = str((market_regime or {}).get("regime") or "").strip().lower()
    risk_soft = False
    if market_regime:
        vix_level = market_regime.get("vix", {}).get("level")
        spy_trend = market_regime.get("spy", {}).get("trend5d")
        shock_day = bool(market_regime.get("risk", {}).get("shockDay"))
        vix_soft = vix_level is not None and float(vix_level) >= 30
        spy_soft = spy_trend is not None and float(spy_trend) <= 0
        risk_soft = shock_day or vix_soft or spy_soft or regime_label in {"risk-off", "defensive", "unstable"}

    if risk_soft:
        return "System Insight: Risk conditions are softer; reduce aggression and wait for cleaner entries."
    if enter_count >= 3:
        return "System Insight: Multiple entry-grade setups available; prioritize clean entries over extended momentum."
    if 1 <= enter_count <= 2:
        return "System Insight: Selective entry environment; focus on the few clean setups and avoid chasing."
    if enter_count == 0 and watch_count > 0:
        return "System Insight: No clean entries yet; several setups remain on watch for better timing."
    if wait_count > enter_count + watch_count:
        return "System Insight: Momentum is extended across many names; patience is favored."
    return "System Insight: Mixed signal quality; stay selective and favor the cleanest setups."

def fetch_historical_context(con, latest_entry_time, predicted_tier_cal, filtered_tier, option_type, structure_bucket, dte):
    if con is None or not option_type or not predicted_tier_cal or not filtered_tier or dte is None:
        return {
            "windowDays": 90,
            "sampleSize": None,
            "distinctTickerCount": None,
            "winRate": None,
            "avgReturnPct": None,
            "avgRMultiple": None,
            "medianHoldDays": None,
            "holdP25Days": None,
            "holdP75Days": None,
            "cohortLabel": None,
            "matchStrength": "none",
            "supportLabel": "Limited history"
        }

    structure_label = structure_bucket or "ATM"

    base_query = """
        WITH prepared AS (
            SELECT
                ticker,
                entry_time,
                exit_time,
                pnl,
                optionSymbol,
                CASE
                    WHEN total_risked_usd IS NOT NULL AND total_risked_usd != 0 THEN (pnl / total_risked_usd) * 100.0
                    WHEN pnl_pct IS NOT NULL THEN
                        CASE
                            WHEN ABS(TRY_CAST(regexp_replace(CAST(pnl_pct AS VARCHAR), '[^0-9\\.-]', '', 'g') AS DOUBLE)) <= 1.5
                                THEN TRY_CAST(regexp_replace(CAST(pnl_pct AS VARCHAR), '[^0-9\\.-]', '', 'g') AS DOUBLE) * 100.0
                            ELSE TRY_CAST(regexp_replace(CAST(pnl_pct AS VARCHAR), '[^0-9\\.-]', '', 'g') AS DOUBLE)
                        END
                    ELSE NULL
                END AS return_pct,
                datediff('day', entry_time, exit_time) AS hold_days
            FROM trades_master
            WHERE entry_time >= CURRENT_DATE - INTERVAL '90 days'
              AND entry_time IS NOT NULL
              AND exit_time IS NOT NULL
              AND lower(optionType) = ?
              AND upper(coalesce(predicted_tier_cal, '')) = ?
              AND upper(coalesce(filteredtier, '')) = ?
              AND (is_tradeable = TRUE OR is_tradeable = 1)
              AND upper(coalesce(quant_rating, '')) IN ('BUY', 'STRONG BUY')
              AND CASE
                    WHEN upper(coalesce(itm_flag, '')) IN ('DEEP ITM', 'ITM') THEN 'ITM'
                    WHEN upper(coalesce(itm_flag, '')) = 'ATM' THEN 'ATM'
                    ELSE 'OTM'
                  END = ?
              AND dte BETWEEN ? AND ?
        ),
        deduped AS (
            SELECT *
            FROM (
                SELECT
                    *,
                    row_number() OVER (
                        PARTITION BY ticker, coalesce(optionSymbol, ''), entry_time, exit_time
                        ORDER BY entry_time
                    ) AS row_num
                FROM prepared
            )
            WHERE row_num = 1
        ),
        comp AS (
            SELECT
                ticker,
                return_pct,
                hold_days
            FROM deduped
            WHERE return_pct IS NOT NULL
              AND hold_days IS NOT NULL
        )
        SELECT
            count(*) AS sample_size,
            count(DISTINCT ticker) AS distinct_ticker_count,
            avg(CASE WHEN return_pct > 0 THEN 1.0 ELSE 0.0 END) AS win_rate,
            avg(return_pct) AS avg_return_pct,
            median(hold_days) AS median_hold_days,
            quantile_cont(hold_days, 0.25) AS hold_p25_days,
            quantile_cont(hold_days, 0.75) AS hold_p75_days
        FROM comp
    """

    result = con.execute(
        base_query,
        [
            option_type.lower(),
            str(predicted_tier_cal).strip().upper(),
            str(filtered_tier).strip().upper(),
            structure_label,
            max(0, dte - 5),
            dte + 5
        ]
    ).fetchone()
    sample_size = int(result[0]) if result and result[0] is not None else 0
    if sample_size > 0:
        distinct_ticker_count = int(result[1]) if result[1] is not None else None
        win_rate = round(float(result[2]) * 100, 1) if result[2] is not None else None
        avg_return_pct = round(float(result[3]), 1) if result[3] is not None else None
        median_hold = round(float(result[4]), 1) if result[4] is not None else None
        hold_p25 = round(float(result[5]), 1) if result[5] is not None else None
        hold_p75 = round(float(result[6]), 1) if result[6] is not None else None
        return {
            "windowDays": 90,
            "sampleSize": sample_size,
            "distinctTickerCount": distinct_ticker_count,
            "winRate": win_rate,
            "avgReturnPct": avg_return_pct,
            "avgRMultiple": None,
            "medianHoldDays": median_hold,
            "holdP25Days": hold_p25,
            "holdP75Days": hold_p75,
            "cohortLabel": f"Based on similar setups over the last 90 days",
            "matchStrength": "setup",
            "supportLabel": classify_historical_support(win_rate, None, sample_size, distinct_ticker_count)
        }

    return {
        "windowDays": 90,
        "sampleSize": None,
        "distinctTickerCount": None,
        "winRate": None,
        "avgReturnPct": None,
        "avgRMultiple": None,
        "medianHoldDays": None,
        "holdP25Days": None,
        "holdP75Days": None,
        "cohortLabel": None,
        "matchStrength": "none",
        "supportLabel": "Limited history"
    }

def build_ranked_trade_slice(df: pd.DataFrame):
    if df is None or df.empty:
        return pd.DataFrame()

    working = df.copy()
    working["optiontype"] = working.get("optiontype", working.get("optionType")).astype(str).str.lower()
    working["adaptive_tier"] = working["adaptive_tier"].astype(str).str.strip()
    working["predicted_tier_cal"] = working["predicted_tier_cal"].astype(str).str.strip()
    working["filteredtier"] = working["filteredtier"].astype(str).str.strip()
    tradeable_source = working["is_tradeable"] if "is_tradeable" in working.columns else pd.Series([0] * len(working), index=working.index)
    working["is_tradeable"] = tradeable_source.isin([True, 1, "1", "true", "True"]).astype(int)

    print("API using CORE-only trade selection")
    if "trade_class" in working.columns:
        ranked = working[working["trade_class"].astype(str).str.strip() == "CORE"].copy()
    else:
        live_source = working["live_eligible"] if "live_eligible" in working.columns else pd.Series([0] * len(working), index=working.index)
        working["live_eligible"] = pd.to_numeric(live_source, errors="coerce").fillna(0).astype(int)
        ranked = working[working["live_eligible"] == 1].copy()

    if ranked.empty:
        return ranked

    rank_col = "adaptive_score_for_rank" if "adaptive_score_for_rank" in ranked.columns else "adaptive_score_final"
    ranked = ranked.sort_values(by=rank_col, ascending=False)
    ranked = ranked.drop_duplicates(subset=["ticker"])
    return ranked.head(25).copy()


def safe_pct_distance_value(strike, spot):
    strike_v = pd.to_numeric(pd.Series([strike]), errors="coerce").iloc[0]
    spot_v = pd.to_numeric(pd.Series([spot]), errors="coerce").iloc[0]
    if pd.isna(strike_v) or pd.isna(spot_v) or spot_v == 0:
        return None
    return abs(round(((strike_v - spot_v) / spot_v) * 100, 1))

def build_trade_action_from_entry_profile(row):
    rsi = pd.to_numeric(pd.Series([row.get("rsi")]), errors="coerce").iloc[0]
    distance_pct = safe_pct_distance_value(row.get("strike"), row.get("underlyingPrice"))

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

def classify_yesterday_status(price_change_pct):
    if price_change_pct is None:
        return "Price unavailable - check live data"
    if abs(price_change_pct) <= 0.02:
        return "Still valid"
    if price_change_pct > 0.02:
        return "Extended - avoid new entries"
    return "Weak - needs confirmation"

def classify_followup_state(price_change_pct):
    if price_change_pct is None:
        return None
    if price_change_pct <= -12:
        return "BROKEN"
    if price_change_pct <= -3:
        return "PULLBACK"
    if price_change_pct <= 2:
        return "STABLE"
    if price_change_pct <= 6:
        return "EXTENDED"
    if price_change_pct < 20:
        return "OVEREXTENDED"
    return "PLAYED_OUT"

def map_followup_action(original_action, state):
    normalized_action = str(original_action or "WATCH").strip().upper()
    if normalized_action == "ENTER":
        if state == "PULLBACK":
            return "ENTER (better price)"
        if state == "STABLE":
            return "ENTER"
        if state == "EXTENDED":
            return "WAIT"
        return "DROP"

    if normalized_action == "WATCH":
        if state == "PULLBACK":
            return "WATCH (near entry)"
        if state == "STABLE":
            return "WATCH"
        if state == "EXTENDED":
            return "WAIT"
        return "DROP"

    if state == "PULLBACK":
        return "WATCH"
    if state in {"STABLE", "EXTENDED"}:
        return "WAIT"
    return "DROP"

def cap_followup_action(raw_action, today_action):
    normalized_today = None if today_action is None else str(today_action).strip().upper()
    normalized_raw = str(raw_action or "WAIT").strip()

    if normalized_today == "WAIT" and normalized_raw not in {"WAIT", "DROP"}:
        return "WAIT", "Prior setup improved, but today's signal remains WAIT"

    if normalized_today == "WATCH" and normalized_raw.startswith("ENTER"):
        return "WATCH", "Prior setup near entry, but today's signal remains WATCH"

    return normalized_raw, None

def build_yesterday_status(today_df: pd.DataFrame, current_file: str | None, historical_con=None):
    recent_files = get_recent_signal_files(current_file, count=5)
    if not recent_files or today_df is None or today_df.empty:
        return []

    today_ranked = build_ranked_trade_slice(today_df)

    today_prices = {}
    today_actions = {}
    today_in_list = set()
    current_signal_date = None
    if "signal_date" in today_df.columns and not today_df.empty:
        raw_signal_date = today_df.iloc[0].get("signal_date")
        if pd.notna(raw_signal_date):
            current_signal_date = str(raw_signal_date)
    if current_signal_date is None:
        current_file_date = extract_signal_file_date(current_file)
        if current_file_date is not None:
            current_signal_date = current_file_date.isoformat()

    for _, row in today_df.iterrows():
        ticker = str(row.get("ticker")).strip() if pd.notna(row.get("ticker")) else None
        if not ticker:
            continue
        price_value = pd.to_numeric(pd.Series([row.get("underlyingPrice")]), errors="coerce").iloc[0]
        if pd.notna(price_value):
            today_prices[ticker] = float(price_value)

    for _, row in today_ranked.iterrows():
        ticker = str(row.get("ticker")).strip() if pd.notna(row.get("ticker")) else None
        if not ticker:
            continue
        today_in_list.add(ticker)
        today_actions[ticker] = build_trade_action_from_entry_profile(row)

    items_by_ticker = {}
    for prior_file in recent_files:
        try:
            prior_df = pd.read_csv(prior_file, low_memory=False)
        except Exception as e:
            print(f"[YESTERDAY STATUS] Failed to load prior file {prior_file}: {e}")
            continue

        ranked_prior = build_ranked_trade_slice(prior_df)
        if ranked_prior.empty:
            continue

        prior_file_date = extract_signal_file_date(prior_file)
        for _, row in ranked_prior.iterrows():
            ticker = str(row.get("ticker")).strip() if pd.notna(row.get("ticker")) else None
            if not ticker or ticker in items_by_ticker:
                continue

            snapshot_price = pd.to_numeric(pd.Series([row.get("underlyingPrice")]), errors="coerce").iloc[0]
            current_price = today_prices.get(ticker)
            if pd.isna(snapshot_price) or snapshot_price in (0, None) or current_price is None:
                continue

            price_change_decimal = round((float(current_price) - float(snapshot_price)) / float(snapshot_price), 4)
            price_change_pct = round(price_change_decimal * 100, 1)
            state = classify_followup_state(price_change_pct)
            if state in {"BROKEN", "OVEREXTENDED", "PLAYED_OUT"}:
                continue

            original_action = build_trade_action_from_entry_profile(row)
            raw_followup_action = map_followup_action(original_action, state)
            if raw_followup_action == "DROP":
                continue

            today_action = today_actions.get(ticker)
            capped_followup_action, status_note = cap_followup_action(raw_followup_action, today_action)
            if capped_followup_action == "DROP":
                continue

            dte_value = pd.to_numeric(pd.Series([row.get("dte")]), errors="coerce").iloc[0]
            historical_context = fetch_historical_context(
                con=historical_con,
                latest_entry_time=None,
                predicted_tier_cal=None if pd.isna(row.get("predicted_tier_cal")) else str(row.get("predicted_tier_cal")).strip(),
                filtered_tier=None if pd.isna(row.get("filteredtier")) else str(row.get("filteredtier")).strip(),
                option_type=None if pd.isna(row.get("optionType")) else str(row.get("optionType")).strip(),
                structure_bucket=canonical_structure_bucket(None if pd.isna(row.get("itm_flag")) else str(row.get("itm_flag")).strip()),
                dte=None if pd.isna(dte_value) else int(dte_value)
            )
            median_hold_days = historical_context.get("medianHoldDays")
            typical_hold_days = int(round(median_hold_days)) if median_hold_days is not None else None

            signal_date = None if pd.isna(row.get("signal_date")) else str(row.get("signal_date")).strip()
            if not signal_date and prior_file_date is not None:
                signal_date = prior_file_date.isoformat()

            items_by_ticker[ticker] = {
                "ticker": ticker,
                "grade": None if pd.isna(row.get("adaptive_tier")) else str(row.get("adaptive_tier")).strip(),
                "signalDate": signal_date,
                "currentDate": current_signal_date,
                "originalAction": original_action,
                "todayAction": today_action,
                "snapshotPrice": round(float(snapshot_price), 2) if pd.notna(snapshot_price) else None,
                "yesterdayEntryPrice": round(float(snapshot_price), 2) if pd.notna(snapshot_price) else None,
                "currentPrice": round(float(current_price), 2) if current_price is not None else None,
                "priceChangePct": price_change_pct,
                "typicalHoldDays": typical_hold_days,
                "status": status_note or classify_yesterday_status(price_change_decimal),
                "statusNote": status_note,
                "rawFollowupAction": raw_followup_action,
                "cappedFollowupAction": capped_followup_action,
                "followupState": state,
                "stillInTodayList": ticker in today_in_list
            }

    items = list(items_by_ticker.values())
    items.sort(key=lambda item: str(item.get("signalDate") or ""), reverse=True)
    return items


@app.get("/")
def home():
    return {"message": "Options API is running"}


def load_production_snapshot():
    if not SNAPSHOT_PATH.exists():
        return None

    try:
        with SNAPSHOT_PATH.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        if isinstance(payload, dict):
            return hydrate_snapshot_payload(payload)
    except Exception as e:
        print(f"[SNAPSHOT] Failed to load production snapshot: {e}")

    return None


def hydrate_snapshot_payload(payload):
    if not isinstance(payload, dict):
        return payload

    hydrated = dict(payload)
    strategy_stats = hydrated.get("strategyStats")
    if not isinstance(strategy_stats, dict):
        return hydrated

    updated_stats = dict(strategy_stats)
    for key in ("highConviction", "broadBase"):
        stat_block = updated_stats.get(key)
        if not isinstance(stat_block, dict):
            continue

        stat_copy = dict(stat_block)
        distribution = stat_copy.get("returnDistribution")
        if isinstance(distribution, list):
            sample_size = stat_copy.get("sampleSize")
            sample_size = int(sample_size) if sample_size not in (None, "") else 0
            negative_count = 0
            large_loss_count = 0
            collapsed_buckets = {
                "<-50%": 0,
                "-50%–0%": 0,
                "0–50%": 0,
                "50–150%": 0,
                ">150%": 0
            }

            for bucket in distribution:
                if not isinstance(bucket, dict):
                    continue
                count = int(bucket.get("count") or 0)
                range_label = str(bucket.get("range") or "")

                if range_label in {"<-100%", "-100% to -50%"}:
                    collapsed_buckets["<-50%"] += count
                elif range_label in {"-50% to -20%", "-20% to 0%", "-50%–0%"}:
                    collapsed_buckets["-50%–0%"] += count
                elif range_label in {"0% to 50%", "0–50%"}:
                    collapsed_buckets["0–50%"] += count
                elif range_label in {"50% to 100%", "100% to 200%", "50–150%"}:
                    collapsed_buckets["50–150%"] += count
                elif range_label in {">200%", ">150%"}:
                    collapsed_buckets[">150%"] += count

                if range_label in {"<-100%", "-100% to -50%", "-50% to -20%", "-20% to 0%", "<-50%", "-50%–0%"}:
                    negative_count += count
                if range_label in {"<-100%", "-100% to -50%", "-50% to -20%"}:
                    large_loss_count += count

            stat_copy["returnDistribution"] = [
                {
                    "range": bucket_label,
                    "count": bucket_count,
                    "percentage": round((bucket_count / sample_size) * 100, 1) if sample_size else 0.0
                }
                for bucket_label, bucket_count in collapsed_buckets.items()
            ]
            if stat_copy.get("lossRate") is None:
                stat_copy["lossRate"] = round((negative_count / sample_size) * 100, 1) if sample_size else 0.0
            if stat_copy.get("largeLossRate") is None:
                stat_copy["largeLossRate"] = round((large_loss_count / sample_size) * 100, 1) if sample_size else 0.0

        stat_copy["worstDrawdownProxy"] = None
        updated_stats[key] = stat_copy

    hydrated["strategyStats"] = updated_stats
    return hydrated


def apply_include_pass_to_payload(payload, include_pass: bool):
    if include_pass or not isinstance(payload, dict):
        return payload

    trades = payload.get("trades")
    if not isinstance(trades, list):
        return payload

    filtered_trades = [trade for trade in trades if str(trade.get("action") or "").strip().upper() != "WAIT"]
    filtered_payload = dict(payload)
    filtered_payload["trades"] = filtered_trades

    record_counts = filtered_payload.get("recordCounts")
    if isinstance(record_counts, dict):
        updated_counts = dict(record_counts)
        updated_counts["returnedTrades"] = len(filtered_trades)
        filtered_payload["recordCounts"] = updated_counts

    return filtered_payload


def load_selector_trade_rows(include_extended: bool) -> pd.DataFrame:
    selector_path = RANKED_TRADES_OUTPUT_PATH if include_extended else TOP_TRADES_OUTPUT_PATH
    if not selector_path.exists():
        raise FileNotFoundError(
            f"Selector output not found at {selector_path}. Run post_processing/top_trades_selector.py first."
        )

    selector_df = pd.read_csv(selector_path, low_memory=False)
    if selector_df.empty:
        return selector_df

    selector_df = selector_df.copy().reset_index(drop=True)
    if "optionSymbol" not in selector_df.columns:
        raise ValueError(f"Selector output {selector_path} is missing required column optionSymbol.")

    selector_df["optionSymbol"] = selector_df["optionSymbol"].astype(str).str.strip()
    selector_df["final_tier"] = selector_df.get("final_tier", pd.Series(index=selector_df.index)).astype(str).str.strip()

    allowed_tiers = ["A+", "A", "B"] if include_extended else ["A+", "A"]
    selector_df = selector_df[selector_df["final_tier"].isin(allowed_tiers)].copy()
    selector_df["selector_rank"] = range(1, len(selector_df) + 1)
    return selector_df


def build_top_trades_cache_signature(include_extended: bool):
    latest_prediction_file = get_latest_file()
    latest_workbook = get_latest_matching_file(ML_DIR, "ml_predictions_summary_*.xlsx")
    selector_path = RANKED_TRADES_OUTPUT_PATH if include_extended else TOP_TRADES_OUTPUT_PATH
    macro_file = MACRO_DIR / "macro_regime_enriched.csv"

    def path_signature(path_like):
        if not path_like:
            return None

        path = Path(path_like)
        if not path.exists():
            return None

        stat = path.stat()
        return (str(path.resolve()), stat.st_mtime_ns, stat.st_size)

    return (
        include_extended,
        path_signature(latest_prediction_file),
        path_signature(selector_path),
        path_signature(latest_workbook),
        path_signature(macro_file),
        path_signature(TRADES_DB_PATH),
    )


def get_cached_top_trades_payload(include_extended: bool):
    cache_key = ("top-trades", include_extended)
    signature = build_top_trades_cache_signature(include_extended)
    cached = TOP_TRADES_PAYLOAD_CACHE.get(cache_key)

    if cached and cached.get("signature") == signature:
        return deepcopy(cached["payload"])

    payload = _build_top_trades_payload_uncached(include_extended=include_extended)
    if isinstance(payload, dict) and "error" not in payload:
        TOP_TRADES_PAYLOAD_CACHE[cache_key] = {
            "signature": signature,
            "payload": deepcopy(payload),
        }

    return payload


def _build_top_trades_payload_uncached(include_extended: bool = False):
    historical_con = None
    try:
        file = get_latest_file()

        if not file:
            return {"error": "No CSV file found. Run your ML script first."}

        selector_df = load_selector_trade_rows(include_extended=include_extended)
        candidate_total = len(selector_df)
        yesterday_status = []

        df = pd.read_csv(file, low_memory=False)
        if "optionSymbol" not in df.columns:
            return {"error": "Latest ML CSV is missing optionSymbol; cannot join selector output."}
        df["optionSymbol"] = df["optionSymbol"].astype(str).str.strip()
        df = df.drop_duplicates(subset=["optionSymbol"], keep="first").copy()

        cols = [
            "ticker",
            "company_name",
            "optionSymbol",
            "optionType",
            "strike",
            "expiryDate",
            "dte",
            "adaptive_score_final",
            "adjusted_score_final",
            "adaptive_score",
            "adaptive_rank",
            "score_decile",
            "baseline_wr",
            "recent_wr",
            "recent_n",
            "degradation",
            "regime_state",
            "regime_multiplier",
            "adaptive_tier",
            "predicted_tier_cal",
            "predicted_tier_raw",
            "filteredtier",
            "priority_score",
            "prob_calibrated",
            "expected_value",
            "ev_pct",
            "rank_score",
            "rank_alpha_flag",
            "regime_adj",
            "dte_bucket",
            "vix_bucket",
            "live_eligible",
            "selected_flag",
            "a_plus_flag",
            "fail_reason",
            "ba_pct",
            "midprice",
            "bid_ok",
            "vol_ok",
            "dte_ok",
            "spy_ok",
            "liq_ok",
            "oi_ok",
            "sector_score",
            "rsi_score",
            "ml_model_version",
            "filter_version",
            "data_cutoff",
            "run_timestamp",
            "signal_date",
            "sector",
            "rsi",
            "volume",
            "openInterest",
            "underlyingPrice",
            "moneyness",
            "itm_flag"
        ]

        cols = [c for c in cols if c in df.columns]
        df = df[cols].copy()
        df_filtered = selector_df.merge(df, on="optionSymbol", how="left", suffixes=("", "_ml"))
        for base_col in ["ticker", "signal_date", "optionType", "dte", "adaptive_score_final"]:
            ml_col = f"{base_col}_ml"
            if ml_col in df_filtered.columns:
                df_filtered[base_col] = df_filtered[base_col].where(df_filtered[base_col].notna(), df_filtered[ml_col])
        if "ticker_ml" in df_filtered.columns:
            df_filtered = df_filtered.drop(columns=[c for c in df_filtered.columns if c.endswith("_ml")])

        # --- SIGNAL LABEL ---
        def build_signal(row):
            score = pd.to_numeric(row.get("adaptive_score_final"), errors="coerce")
            if pd.isna(score):
                return "UNKNOWN"
            if score >= 1.8:
                return "STRONG"
            elif score >= 1.0:
                return "MODERATE"
            else:
                return "WEAK"

        df_filtered["signal_strength"] = df_filtered.apply(build_signal, axis=1)
        
        # --- SAFE HELPERS ---
        def safe_int(val):
            v = pd.to_numeric(pd.Series([val]), errors="coerce").iloc[0]
            return int(v) if pd.notna(v) else None

        def safe_float(val, decimals=1):
            v = pd.to_numeric(pd.Series([val]), errors="coerce").iloc[0]
            return round(float(v), decimals) if pd.notna(v) else None

        def safe_str(val):
            return None if pd.isna(val) else str(val)

        def safe_bool(val):
            if pd.isna(val):
                return None
            if isinstance(val, bool):
                return val
            text = str(val).strip().lower()
            if text in {"1", "true", "yes", "y"}:
                return True
            if text in {"0", "false", "no", "n"}:
                return False
            return None
        
        etf_overlay_map = load_latest_etf_overlay()
        sector_outlook = load_latest_sector_outlook()
        sector_rank_map = {
            str(item.get("sector")).strip(): item.get("rank")
            for item in sector_outlook.get("sectors", [])
            if item.get("sector")
        }
        strategy_stats = load_latest_strategy_stats() or {
            "highConviction": None,
            "broadBase": None,
            "sourceFile": None
        }
        market_regime = load_latest_market_regime()
        latest_hist_entry_time = None
        if TRADES_DB_PATH.exists():
            try:
                historical_con = duckdb.connect(str(TRADES_DB_PATH), read_only=True)
                latest_hist_entry_time = historical_con.execute("SELECT max(entry_time) FROM trades_master").fetchone()[0]
            except Exception as e:
                print(f"[HISTORICAL CONTEXT] Failed to connect: {e}")
                historical_con = None
                latest_hist_entry_time = None
        
        def safe_pct_distance(strike, spot):
            strike_v = pd.to_numeric(pd.Series([strike]), errors="coerce").iloc[0]
            spot_v = pd.to_numeric(pd.Series([spot]), errors="coerce").iloc[0]

            if pd.isna(strike_v) or pd.isna(spot_v) or spot_v == 0:
                return None

            return round(((strike_v - spot_v) / spot_v) * 100, 1)
        
        def build_strike_position_label(itm_flag, distance_pct):
            flag = safe_str(itm_flag)

            if flag:
                return flag.upper()

            dist = pd.to_numeric(pd.Series([distance_pct]), errors="coerce").iloc[0]
            if pd.isna(dist):
                return "N/A"

            if dist <= -15:
                return "DEEP ITM"
            elif dist < -2:
                return "ITM"
            elif abs(dist) <= 2:
                return "ATM"
            elif dist <= 10:
                return "OTM"
            else:
                return "FAR OTM"


        def build_strike_position_text(distance_pct):
            dist = pd.to_numeric(pd.Series([distance_pct]), errors="coerce").iloc[0]

            if pd.isna(dist):
                return None

            if abs(dist) <= 0.5:
                return "At spot"

            if dist > 0:
                return f"{abs(round(float(dist), 1))}% above spot"
            else:
                return f"{abs(round(float(dist), 1))}% below spot"

        def build_execution_guidance(action, option_type, strike_pos_label, dte, rsi, etf_bias, risk_flags):
            favorable = []
            caution = []
            unfavorable = []

            bias = (etf_bias or "Neutral").strip()
            if bias.lower() == "bullish":
                favorable.append("Sector/ETF backdrop supportive.")
            elif bias.lower() == "bearish":
                caution.append("Sector/ETF backdrop is bearish; confirm before entry.")
            elif bias.lower() == "no overlay":
                caution.append("No live sector overlay; use price action to confirm.")

            if action == "ENTER":
                favorable.append("Higher-priority candidate in today's list.")
            elif action == "WATCH":
                caution.append("Qualified but needs cleaner confirmation.")
            elif action == "WAIT":
                unfavorable.append("Behind stronger names today; only revisit if conditions improve.")

            if strike_pos_label in {"DEEP ITM", "ITM"}:
                favorable.append("ITM structure supports follow-through if trend holds.")
            elif strike_pos_label in {"OTM", "FAR OTM"}:
                caution.append("OTM structure: avoid paying up if move is already extended.")

            if rsi is not None and rsi >= 70:
                caution.append("Momentum extended; avoid chasing strength.")
            elif rsi is not None and rsi <= 45:
                caution.append("Momentum soft; wait for confirmation.")

            if dte is not None and dte <= 21:
                caution.append("Short duration: time decay risk is higher.")

            # Tradeability flags (from the snapshot)
            liq_ok = risk_flags.get("liquidityOk")
            oi_ok = risk_flags.get("openInterestOk")
            vol_ok = risk_flags.get("volumeOk")
            bid_ok = risk_flags.get("bidOk")

            if liq_ok is False or oi_ok is False or vol_ok is False:
                unfavorable.append("Contract depth is weaker than preferred.")
            if bid_ok is False:
                unfavorable.append("Quote sanity failed; verify live bid/ask.")

            # If we have no hard red flags, still provide "avoid if..." disconfirmations
            # so the UI doesn't read like an empty placeholder.
            if not unfavorable:
                if bias.lower() == "bullish":
                    unfavorable.append("Avoid if sector support fades.")
                elif bias.lower() == "bearish":
                    unfavorable.append("Avoid if sector stays heavy against the setup.")
                else:
                    unfavorable.append("Avoid if price action weakens.")

                if rsi is not None and rsi >= 70:
                    unfavorable.append("Avoid if momentum rolls over after extension.")
                elif rsi is not None and rsi <= 45:
                    unfavorable.append("Avoid if momentum fails to firm up.")
                else:
                    unfavorable.append("Avoid if momentum weakens.")

                if dte is not None and dte <= 21:
                    unfavorable.append("Avoid if the move does not start quickly (decay).")
                elif bid_ok is not False:
                    unfavorable.append("Avoid if bid/ask widens materially.")

            # Keep it tight for the UI.
            return {
                "favorable": favorable[:3],
                "caution": caution[:3],
                "unfavorable": unfavorable[:3]
            }

        # --- RESPONSE ---
        response = []

        for _, row in df_filtered.iterrows():
            selector_rank = safe_int(row.get("selector_rank")) or len(response) + 1
            sector_raw = safe_str(row.get("sector"))
            sector = sector_raw.strip() if sector_raw else None
            etf_info = etf_overlay_map.get(sector, {}) if sector else {}
            fallback_etf = SECTOR_TO_ETF_FALLBACK.get(sector) if sector else None
            action = build_trade_action_from_entry_profile(row)
            tier = safe_str(row.get("final_tier")) or "B"
            strike_distance = safe_pct_distance(row.get("strike"), row.get("underlyingPrice"))
            strike_pos_label = build_strike_position_label(row.get("itm_flag"), strike_distance)
            strike_pos_text = build_strike_position_text(strike_distance)
            structure_bucket = canonical_structure_bucket(strike_pos_label)

            risk_flags = {
                "bidOk": safe_bool(row.get("bid_ok")),
                "volumeOk": safe_bool(row.get("vol_ok")),
                "dteOk": safe_bool(row.get("dte_ok")),
                "spyTrendOk": safe_bool(row.get("spy_ok")),
                "liquidityOk": safe_bool(row.get("liq_ok")),
                "openInterestOk": safe_bool(row.get("oi_ok"))
            }
            option_type = safe_str(row.get("optionType")) or "CALL"
            etf_bias = safe_str(etf_info.get("bias")) or ("No overlay" if fallback_etf else "Neutral")
            current_rsi = safe_float(row.get("rsi"), 1)
            current_dte = safe_int(row.get("dte"))
            historical_context = fetch_historical_context(
                con=historical_con,
                latest_entry_time=latest_hist_entry_time,
                predicted_tier_cal=safe_str(row.get("predicted_tier_cal")),
                filtered_tier=safe_str(row.get("filteredtier")),
                option_type=option_type,
                structure_bucket=structure_bucket,
                dte=current_dte
            )

            today_top_pct = math.ceil((selector_rank / candidate_total) * 100) if candidate_total else None
            today_score = round(100 * ((candidate_total - selector_rank + 1) / candidate_total)) if candidate_total else None

            response.append({
                "rank": selector_rank,
                "selector_rank": selector_rank,
                "ticker": safe_str(row.get("ticker")),
                "signal_date": safe_str(row.get("signal_date")),
                "companyName": safe_str(row.get("company_name")),
                "tier": tier,
                "final_tier": tier,
                "action": action,
                "action_override": False,
                "optionType": option_type,
                "signalStrength": build_signal(row),
                "segmented_percentile": safe_float(row.get("segmented_percentile"), 6),
                "global_percentile": safe_float(row.get("global_percentile"), 6),
                "adaptive_score_final": safe_float(row.get("adaptive_score_final"), 6),

                "contract": {
                    "optionSymbol": safe_str(row.get("optionSymbol")),
                    "strike": safe_int(row.get("strike")),
                    "expiry": safe_str(row.get("expiryDate")),
                    "dte": safe_int(row.get("dte")),
                    "underlyingPrice": safe_float(row.get("underlyingPrice"), 2),
                    "distanceToStrikePct": strike_distance,
                    "moneyness": safe_str(row.get("moneyness")),
                    "itmFlag": safe_str(row.get("itm_flag")),
                    "strikePositionLabel": strike_pos_label,
                    "strikePositionText": strike_pos_text
                },

                "market": {
                    "volume": safe_int(row.get("volume")),
                    "openInterest": safe_int(row.get("openInterest"))
                },

                "context": {
                    "sector": sector,
                    "rsi": current_rsi
                },

                "etfOverlay": {
                    "etf": safe_str(etf_info.get("etf")) or fallback_etf or "N/A",
                    "bias": etf_bias,
                    "winRate4d": (
                        round(float(etf_info.get("win_rate_4d")) * 100, 1)
                        if etf_info.get("win_rate_4d") is not None
                        else None
                    ),
                    "breadth": safe_int(etf_info.get("breadth"))
                },

                "scores": {
                    "adaptiveScoreFinal": safe_float(row.get("adaptive_score_final"), 3),
                    "adjustedScoreFinal": safe_float(row.get("adjusted_score_final"), 3),
                    "adaptiveScore": safe_float(row.get("adaptive_score"), 3),
                    "adaptiveRank": safe_int(row.get("adaptive_rank")),
                    "scoreDecile": safe_int(row.get("score_decile")),
                    "baselineWr": safe_float(row.get("baseline_wr"), 4),
                    "recentWr": safe_float(row.get("recent_wr"), 4),
                    "recentN": safe_int(row.get("recent_n")),
                    "degradation": safe_float(row.get("degradation"), 4),
                    "regimeMultiplier": safe_float(row.get("regime_multiplier"), 3),
                    "priorityScore": safe_float(row.get("priority_score"), 3),
                    "probCalibrated": safe_float(row.get("prob_calibrated"), 3),
                    "expectedValue": safe_float(row.get("expected_value"), 3),
                    "evPct": safe_float(row.get("ev_pct"), 2),
                    "rankScore": safe_float(row.get("rank_score"), 3),
                    "regimeAdj": safe_float(row.get("regime_adj"), 3),
                    "sectorScore": safe_float(row.get("sector_score"), 3),
                    "rsiScore": safe_float(row.get("rsi_score"), 3)
                },

                "classification": {
                    "predictedTierCal": safe_str(row.get("predicted_tier_cal")),
                    "predictedTierRaw": safe_str(row.get("predicted_tier_raw")),
                    "adaptiveTier": safe_str(row.get("adaptive_tier")),
                    "filteredTier": safe_str(row.get("filteredtier")),
                    "regimeState": safe_str(row.get("regime_state")),
                    "dteBucket": safe_str(row.get("dte_bucket")),
                    "vixBucket": safe_str(row.get("vix_bucket"))
                },

                "execution": {
                    "liveEligible": safe_bool(row.get("live_eligible")),
                    "selected": safe_bool(row.get("selected_flag")),
                    "aPlus": safe_bool(row.get("a_plus_flag")),
                    "rankAlpha": safe_bool(row.get("rank_alpha_flag")),
                    "failReason": safe_str(row.get("fail_reason"))
                },

                "risk": {
                    "midPrice": safe_float(row.get("midprice"), 2),
                    "bidAskPct": safe_float(row.get("ba_pct"), 3),
                    "bidOk": risk_flags.get("bidOk"),
                    "volumeOk": risk_flags.get("volumeOk"),
                    "dteOk": risk_flags.get("dteOk"),
                    "spyTrendOk": risk_flags.get("spyTrendOk"),
                    "liquidityOk": risk_flags.get("liquidityOk"),
                    "openInterestOk": risk_flags.get("openInterestOk")
                },

                "executionGuidance": build_execution_guidance(
                    action=action,
                    option_type=option_type,
                    strike_pos_label=strike_pos_label,
                    dte=current_dte,
                    rsi=current_rsi,
                    etf_bias=etf_bias,
                    risk_flags=risk_flags
                ),

                "decisionContext": {
                    "today": {
                        "rank": selector_rank,
                        "candidateCount": candidate_total,
                        "topPercent": today_top_pct,
                        "todayScore": today_score
                    },
                    "historical": historical_context,
                    "translation": build_translation(action, current_rsi, etf_bias),
                    "executionEdge": build_execution_edge_items(
                        current_rsi,
                        current_dte,
                        etf_bias,
                        risk_flags,
                        option_type,
                        safe_str(etf_info.get("etf")) or fallback_etf or "N/A",
                        (
                            round(float(etf_info.get("win_rate_4d")) * 100, 1)
                            if etf_info.get("win_rate_4d") is not None
                            else None
                        ),
                        safe_int(etf_info.get("breadth")),
                        sector_rank_map.get(sector) if sector else None
                    ),
                    "invalidation": build_invalidation_items(
                        underlying_price=safe_float(row.get("underlyingPrice"), 2),
                        rsi=current_rsi,
                        dte=current_dte,
                        etf_bias=etf_bias,
                        risk_flags=risk_flags,
                        option_type=option_type
                    ),
                    "expectation": build_expectation_frame(
                        action=action,
                        dte=current_dte,
                        median_hold_days=historical_context.get("medianHoldDays"),
                        hold_p25_days=historical_context.get("holdP25Days"),
                        hold_p75_days=historical_context.get("holdP75Days"),
                        structure_bucket=structure_bucket
                    )
                },

                "provenance": {
                    "sourceFile": os.path.basename(file),
                    "selectorFile": TOP_TRADES_OUTPUT_PATH.name if not include_extended else RANKED_TRADES_OUTPUT_PATH.name,
                    "strategyStatsFile": strategy_stats.get("sourceFile"),
                    "mlModelVersion": safe_str(row.get("ml_model_version")),
                    "filterVersion": safe_str(row.get("filter_version")),
                    "dataCutoff": safe_str(row.get("data_cutoff")),
                    "runTimestamp": safe_str(row.get("run_timestamp")),
                    "signalDate": safe_str(row.get("signal_date"))
                },

            })

        enter_count_before_override = sum(1 for trade in response if str(trade.get("action") or "").strip().upper() == "ENTER")
        if enter_count_before_override == 0 and response:
            override_count = min(2, len(response))
            for idx in range(override_count):
                response[idx]["action"] = "ENTER"
                response[idx]["action_override"] = True

        if historical_con is not None:
            historical_con.close()
            historical_con = None

        signal_date = response[0]["provenance"]["signalDate"] if response else None
        market_regime_payload = dict(market_regime) if isinstance(market_regime, dict) else market_regime
        if isinstance(market_regime_payload, dict):
            market_regime_payload["insight"] = build_market_insight(market_regime_payload, response)
        return {
            "generatedAt": datetime.now(timezone.utc).isoformat(),
            "signalDate": signal_date,
            "sourceFiles": {
                "predictionCsv": os.path.basename(file),
                "selectorCsv": RANKED_TRADES_OUTPUT_PATH.name if include_extended else TOP_TRADES_OUTPUT_PATH.name,
                "strategyStats": strategy_stats.get("sourceFile"),
                "sectorOutlookWorkbook": sector_outlook.get("sourceFile"),
                "marketRegime": MACRO_DIR.joinpath("macro_regime_enriched.csv").name if (MACRO_DIR / "macro_regime_enriched.csv").exists() else None,
                "tradesDb": TRADES_DB_PATH.name if TRADES_DB_PATH.exists() else None
            },
            "recordCounts": {
                "candidateTrades": candidate_total,
                "returnedTrades": len(response),
                "yesterdayStatus": len(yesterday_status),
                "sectorCount": len(sector_outlook.get("sectors", []))
            },
            "marketRegime": market_regime_payload,
            "strategyStats": {
                "highConviction": strategy_stats.get("highConviction"),
                "broadBase": strategy_stats.get("broadBase")
            },
            "sectorOutlook": sector_outlook.get("sectors", []),
            "yesterdayStatus": yesterday_status,
            "trades": response
        }

    except Exception as e:
        import traceback
        if historical_con is not None:
            historical_con.close()
        return {
            "error": str(e),
            "trace": traceback.format_exc()
        }


def build_top_trades_payload(include_pass: bool = True, include_extended: bool = False):
    payload = get_cached_top_trades_payload(include_extended=include_extended)
    if isinstance(payload, dict) and payload.get("error"):
        detail = str(payload.get("error") or "")
        if "Selector output not found" in detail:
            snapshot_payload = load_production_snapshot()
            if snapshot_payload is not None:
                return apply_include_pass_to_payload(snapshot_payload, include_pass)
    return apply_include_pass_to_payload(payload, include_pass)


@app.get("/top-trades")
def top_trades(include_pass: bool = True, include_extended: bool = False):
    return build_top_trades_payload(include_pass=include_pass, include_extended=include_extended)

