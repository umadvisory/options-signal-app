from fastapi import FastAPI
import duckdb
import pandas as pd
import glob
import os
import math

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

from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
ML_DIR = ROOT_DIR / "ML"
REPORTS_DIR = ROOT_DIR / "data" / "master" / "reports"
MACRO_DIR = ROOT_DIR / "data" / "macro"
TRADES_DB_PATH = ROOT_DIR / "data" / "master" / "trades_master.duckdb"
ETF_SHEET_NAME = "ETF_Overlay_Summary"
SECTOR_SUMMARY_SHEET = "Sector Summary"
TICKER_SUMMARY_SHEET = "Ticker Summary"

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

        sectors = []
        sort_cols = [c for c in ["focus_score", "conviction_score", "net_score", "total_signals"] if c in sector_df.columns]
        if sort_cols:
            sector_df = sector_df.sort_values(by=sort_cols, ascending=[False] * len(sort_cols))

        for rank, (_, row) in enumerate(sector_df.iterrows(), start=1):
            sector_name = str(row.get("sector")).strip()
            if not sector_name:
                continue

            etf_info = etf_overlay_map.get(sector_name, {})
            fallback_etf = SECTOR_TO_ETF_FALLBACK.get(sector_name)
            total_signals = int(row.get("total_signals")) if pd.notna(row.get("total_signals")) else 0
            net_score = float(row.get("net_score")) if pd.notna(row.get("net_score")) else None
            conviction_score = float(row.get("conviction_score")) if pd.notna(row.get("conviction_score")) else None
            a_tier_density = float(row.get("a_tier_density")) if pd.notna(row.get("a_tier_density")) else None

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
                "topTickers": top_tickers_by_sector.get(sector_name, [])
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
    latest_csv = get_latest_matching_file(REPORTS_DIR, "*strategy_uplift*.csv")
    if latest_csv is None:
        return {
            "highConviction": None,
            "broadBase": None,
            "sourceFile": None
        }

    try:
        df = pd.read_csv(latest_csv)
        df.columns = [str(c).strip().lower() for c in df.columns]

        print("[STRATEGY STATS] Using file:", latest_csv.name)
        print("[STRATEGY STATS] Columns:", df.columns.tolist())

        if "section" not in df.columns:
            return {
                "highConviction": None,
                "broadBase": None,
                "sourceFile": latest_csv.name
            }

        df["section"] = df["section"].astype(str).str.strip().str.upper()

        metric_cols = [
            "win_rate",
            "n_trades",
            "avg_return_pct",
            "median_return_pct",
            "worst_drawdown_proxy"
        ]

        for col in metric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        def escape_sql_literal(value):
            if value is None or pd.isna(value):
                return None
            return str(value).replace("'", "''")

        def format_date_value(value):
            if value is None or pd.isna(value):
                return None
            try:
                return pd.to_datetime(value).date().isoformat()
            except Exception:
                return str(value)

        def fetch_strategy_backing_metadata(section_name: str, row):
            if not TRADES_DB_PATH.exists():
                return {
                    "sampleSize": None,
                    "tickerCount": None,
                    "minDate": None,
                    "maxDate": None
                }

            start_ts = escape_sql_literal(row.get("window_start"))
            end_ts = escape_sql_literal(row.get("window_end"))

            if not start_ts or not end_ts:
                return {
                    "sampleSize": None,
                    "tickerCount": None,
                    "minDate": None,
                    "maxDate": None
                }

            valuation_rank_case = """
                CASE upper(trim(valuation))
                  WHEN 'A+' THEN 1 WHEN 'A' THEN 2 WHEN 'A-' THEN 3
                  WHEN 'B+' THEN 4 WHEN 'B' THEN 5 WHEN 'B-' THEN 6
                  WHEN 'C+' THEN 7 WHEN 'C' THEN 8 WHEN 'C-' THEN 9
                  WHEN 'D+' THEN 10 WHEN 'D' THEN 11 WHEN 'D-' THEN 12
                  WHEN 'F' THEN 13
                  ELSE NULL
                END
            """

            where_clauses = [
                f"entry_time >= TIMESTAMP '{start_ts}'",
                f"entry_time < TIMESTAMP '{end_ts}'",
                "upper(trim(optiontype)) = 'CALL'"
            ]

            normalized = section_name.upper()
            if normalized.startswith("S13"):
                where_clauses.extend(
                    [
                        "predicted_tier_cal = 'A'",
                        "filteredtier = 'A'",
                        "adaptive_tier = 'A'",
                        "upper(trim(momentum)) IN ('A+','A','A-','B+','B','B-')",
                        f"({valuation_rank_case}) <= 10",
                        "(is_tradeable = TRUE OR is_tradeable = 1)",
                        "upper(trim(quant_rating)) IN ('BUY','STRONG BUY')"
                    ]
                )
            elif normalized.startswith("S11"):
                where_clauses.extend(
                    [
                        "predicted_tier_cal = 'A'",
                        "filteredtier = 'A'",
                        "adaptive_tier != 'A'"
                    ]
                )
            else:
                return {
                    "sampleSize": None,
                    "tickerCount": None,
                    "minDate": None,
                    "maxDate": None
                }

            query = f"""
                SELECT
                    COUNT(*) AS trade_count,
                    COUNT(DISTINCT ticker) AS ticker_count,
                    MIN(CAST(entry_time AS DATE)) AS min_date,
                    MAX(CAST(entry_time AS DATE)) AS max_date
                FROM trades_master
                WHERE {' AND '.join(where_clauses)}
            """

            try:
                con = duckdb.connect(str(TRADES_DB_PATH), read_only=True)
                result = con.execute(query).fetchone()
                con.close()
            except Exception as e:
                print(f"[STRATEGY STATS] DuckDB metadata lookup failed for {section_name}: {e}")
                return {
                    "sampleSize": None,
                    "tickerCount": None,
                    "minDate": None,
                    "maxDate": None
                }

            if not result:
                return {
                    "sampleSize": None,
                    "tickerCount": None,
                    "minDate": None,
                    "maxDate": None
                }

            return {
                "sampleSize": int(result[0]) if result[0] is not None else None,
                "tickerCount": int(result[1]) if result[1] is not None else None,
                "minDate": format_date_value(result[2]),
                "maxDate": format_date_value(result[3])
            }

        def extract_section_stats(section_name: str):
            section_name = section_name.upper()
            df_sec = df[df["section"] == section_name].copy()

            if df_sec.empty:
                df_sec = df[df["section"].str.startswith(section_name)].copy()

            if df_sec.empty:
                return None

            if "n_trades" in df_sec.columns:
                df_sec = df_sec.sort_values(by="n_trades", ascending=False)

            row = df_sec.iloc[0]
            backing = fetch_strategy_backing_metadata(section_name, row)

            win_rate = row.get("win_rate")
            if pd.notna(win_rate):
                win_rate = round(float(win_rate) * 100, 1) if win_rate <= 1 else round(float(win_rate), 1)

            avg_return_pct = row.get("avg_return_pct")
            if pd.notna(avg_return_pct):
                avg_return_pct = round(float(avg_return_pct), 1)

            median_return_pct = row.get("median_return_pct")
            if pd.notna(median_return_pct):
                median_return_pct = round(float(median_return_pct), 1)

            worst_drawdown_proxy = row.get("worst_drawdown_proxy")
            if pd.notna(worst_drawdown_proxy):
                worst_drawdown_proxy = round(float(worst_drawdown_proxy), 1)

            sample_size = backing.get("sampleSize")
            if sample_size is None:
                sample_size = row.get("n_trades")
                if pd.notna(sample_size):
                    sample_size = int(sample_size)

            return {
                "winRate": win_rate if pd.notna(row.get("win_rate")) else None,
                "sampleSize": sample_size,
                "tickerCount": backing.get("tickerCount"),
                "minDate": backing.get("minDate"),
                "maxDate": backing.get("maxDate"),
                "avgReturnPct": avg_return_pct,
                "medianReturnPct": median_return_pct,
                "worstDrawdownProxy": worst_drawdown_proxy
            }

        return {
            "highConviction": extract_section_stats("S13"),
            "broadBase": extract_section_stats("S11"),
            "sourceFile": latest_csv.name
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

def classify_historical_support(win_rate, avg_r_multiple, sample_size):
    if sample_size is None or sample_size < 15 or win_rate is None or avg_r_multiple is None:
        return "Limited"

    if win_rate >= 75 and avg_r_multiple >= 1.0:
        return "Strong"
    if win_rate >= 65 and avg_r_multiple >= 0.75:
        return "Moderate"
    if win_rate >= 65 and avg_r_multiple < 0.75:
        return "Mixed"
    if win_rate < 65 and avg_r_multiple >= 1.0:
        return "Volatile"
    return "Weak"

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
        items.append(f"{etf} overlay: {etf_win_rate}% recent hit rate across {int(etf_breadth)} names.")
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

def fetch_historical_context(con, latest_entry_time, sector, option_type, structure_bucket, dte):
    if con is None or latest_entry_time is None or not sector or not option_type:
        return {
            "windowDays": 365,
            "sampleSize": None,
            "winRate": None,
            "avgRMultiple": None,
            "medianHoldDays": None,
            "cohortLabel": None,
            "matchStrength": "none"
        }

    band_low, band_high, band_label = dte_band(dte)
    window_start = pd.Timestamp(latest_entry_time) - pd.Timedelta(days=365)
    structure_label = structure_bucket or "ATM"

    cohorts = [
        {
            "name": "tight",
            "label": f"{sector} {option_type.upper()}s, {structure_label}, {band_label}, A-filtered",
            "where": """
                AND sector = ?
                AND lower(optionType) = ?
                AND CASE
                      WHEN upper(coalesce(itm_flag, '')) IN ('DEEP ITM', 'ITM') THEN 'ITM'
                      WHEN upper(coalesce(itm_flag, '')) = 'ATM' THEN 'ATM'
                      ELSE 'OTM'
                    END = ?
                AND dte BETWEEN ? AND ?
                AND live_eligible = 1
                AND upper(coalesce(predicted_tier_cal, '')) = 'A'
                AND upper(coalesce(filteredtier, '')) = 'A'
                AND upper(coalesce(adaptive_tier, '')) = 'A'
            """,
            "params": [sector, option_type.lower(), structure_label, band_low, band_high]
        },
        {
            "name": "medium",
            "label": f"{sector} {option_type.upper()}s, {structure_label}, {band_label}",
            "where": """
                AND sector = ?
                AND lower(optionType) = ?
                AND CASE
                      WHEN upper(coalesce(itm_flag, '')) IN ('DEEP ITM', 'ITM') THEN 'ITM'
                      WHEN upper(coalesce(itm_flag, '')) = 'ATM' THEN 'ATM'
                      ELSE 'OTM'
                    END = ?
                AND dte BETWEEN ? AND ?
                AND live_eligible = 1
            """,
            "params": [sector, option_type.lower(), structure_label, band_low, band_high]
        },
        {
            "name": "broad",
            "label": f"{sector} {option_type.upper()}s, {structure_label}",
            "where": """
                AND sector = ?
                AND lower(optionType) = ?
                AND CASE
                      WHEN upper(coalesce(itm_flag, '')) IN ('DEEP ITM', 'ITM') THEN 'ITM'
                      WHEN upper(coalesce(itm_flag, '')) = 'ATM' THEN 'ATM'
                      ELSE 'OTM'
                    END = ?
                AND live_eligible = 1
            """,
            "params": [sector, option_type.lower(), structure_label]
        },
        {
            "name": "sector",
            "label": f"{sector} {option_type.upper()}s",
            "where": """
                AND sector = ?
                AND lower(optionType) = ?
                AND live_eligible = 1
            """,
            "params": [sector, option_type.lower()]
        }
    ]

    base_query = """
        WITH comp AS (
            SELECT
                pnl,
                CASE
                    WHEN total_risked_usd IS NOT NULL AND total_risked_usd != 0 THEN pnl / total_risked_usd
                    WHEN pnl_pct IS NOT NULL THEN pnl_pct
                    ELSE NULL
                END AS r_multiple,
                datediff('day', entry_time, exit_time) AS hold_days
            FROM trades_master
            WHERE entry_time >= ?
              AND exit_time IS NOT NULL
              {where_clause}
        )
        SELECT
            count(*) AS sample_size,
            avg(CASE WHEN pnl > 0 THEN 1.0 ELSE 0.0 END) AS win_rate,
            avg(r_multiple) AS avg_r_multiple,
            median(hold_days) AS median_hold_days,
            quantile_cont(hold_days, 0.25) AS hold_p25_days,
            quantile_cont(hold_days, 0.75) AS hold_p75_days
        FROM comp
        WHERE r_multiple IS NOT NULL
          AND hold_days IS NOT NULL
    """

    for cohort in cohorts:
        query = base_query.format(where_clause=cohort["where"])
        result = con.execute(query, [window_start, *cohort["params"]]).fetchone()
        sample_size = int(result[0]) if result and result[0] is not None else 0
        if sample_size >= 15:
            win_rate = round(float(result[1]) * 100, 1) if result[1] is not None else None
            avg_r = round(float(result[2]), 2) if result[2] is not None else None
            median_hold = round(float(result[3]), 1) if result[3] is not None else None
            hold_p25 = round(float(result[4]), 1) if result[4] is not None else None
            hold_p75 = round(float(result[5]), 1) if result[5] is not None else None
            return {
                "windowDays": 365,
                "sampleSize": sample_size,
                "winRate": win_rate,
                "avgRMultiple": avg_r,
                "medianHoldDays": median_hold,
                "holdP25Days": hold_p25,
                "holdP75Days": hold_p75,
                "cohortLabel": cohort["label"],
                "matchStrength": cohort["name"],
                "supportLabel": classify_historical_support(win_rate, avg_r, sample_size)
            }

    return {
        "windowDays": 365,
        "sampleSize": None,
        "winRate": None,
        "avgRMultiple": None,
        "medianHoldDays": None,
        "holdP25Days": None,
        "holdP75Days": None,
        "cohortLabel": None,
        "matchStrength": "none",
        "supportLabel": "Limited"
    }

def build_ranked_trade_slice(df: pd.DataFrame):
    if df is None or df.empty:
        return pd.DataFrame()

    working = df.copy()
    working["optiontype"] = working.get("optiontype", working.get("optionType")).astype(str).str.lower()
    working["adaptive_tier"] = working["adaptive_tier"].astype(str).str.strip()
    working["predicted_tier_cal"] = working["predicted_tier_cal"].astype(str).str.strip()
    working["live_eligible"] = pd.to_numeric(working["live_eligible"], errors="coerce").fillna(0).astype(int)

    ranked = working[
        (working["live_eligible"] == 1) &
        (working["predicted_tier_cal"] == "A") &
        (working["adaptive_tier"] == "A") &
        (working["optiontype"] == "call")
    ].copy()

    if ranked.empty:
        return ranked

    ranked = ranked.sort_values(by="adaptive_score_final", ascending=False)
    ranked = ranked.drop_duplicates(subset=["ticker"])
    return ranked.head(25).copy()

def classify_yesterday_status(price_change_pct):
    if price_change_pct is None:
        return "Price unavailable - check live data"
    if abs(price_change_pct) <= 0.02:
        return "Still valid"
    if price_change_pct > 0.02:
        return "Extended - avoid new entries"
    return "Weak - needs confirmation"

def build_yesterday_status(today_df: pd.DataFrame, current_file: str | None):
    previous_file = get_previous_file(current_file)
    if previous_file is None or today_df is None or today_df.empty:
        return []

    try:
        yesterday_df = pd.read_csv(previous_file, low_memory=False)
    except Exception as e:
        print(f"[YESTERDAY STATUS] Failed to load previous file: {e}")
        return []

    ranked_yesterday = build_ranked_trade_slice(yesterday_df)
    if ranked_yesterday.empty:
        return []

    today_prices = {}
    today_in_list = set()
    for _, row in today_df.iterrows():
        ticker = str(row.get("ticker")).strip() if pd.notna(row.get("ticker")) else None
        if not ticker:
            continue
        today_in_list.add(ticker)
        price_value = pd.to_numeric(pd.Series([row.get("underlyingPrice")]), errors="coerce").iloc[0]
        if pd.notna(price_value):
            today_prices[ticker] = float(price_value)

    items = []
    for _, row in ranked_yesterday.iterrows():
        ticker = str(row.get("ticker")).strip() if pd.notna(row.get("ticker")) else None
        if not ticker:
            continue

        yesterday_price = pd.to_numeric(pd.Series([row.get("underlyingPrice")]), errors="coerce").iloc[0]
        current_price = today_prices.get(ticker)

        price_change_pct = None
        if pd.notna(yesterday_price) and yesterday_price not in (0, None) and current_price is not None:
            price_change_pct = round((float(current_price) - float(yesterday_price)) / float(yesterday_price), 4)

        items.append({
            "ticker": ticker,
            "grade": None if pd.isna(row.get("adaptive_tier")) else str(row.get("adaptive_tier")).strip(),
            "yesterdayEntryPrice": round(float(yesterday_price), 2) if pd.notna(yesterday_price) else None,
            "currentPrice": round(float(current_price), 2) if current_price is not None else None,
            "priceChangePct": round(price_change_pct * 100, 1) if price_change_pct is not None else None,
            "status": classify_yesterday_status(price_change_pct),
            "stillInTodayList": ticker in today_in_list
        })

    return items[:10]


@app.get("/")
def home():
    return {"message": "Options API is running"}


@app.get("/top-trades")
def top_trades(include_pass: bool = True):
    historical_con = None
    try:
        file = get_latest_file()

        if not file:
            return {"error": "No CSV file found. Run your ML script first."}

        df = pd.read_csv(file, low_memory=False)

        # --- NORMALIZATION ---
        df["optiontype"] = df.get("optiontype", df.get("optionType")).astype(str).str.lower()
        df["adaptive_tier"] = df["adaptive_tier"].astype(str).str.strip()
        df["predicted_tier_cal"] = df["predicted_tier_cal"].astype(str).str.strip()
        df["live_eligible"] = pd.to_numeric(df["live_eligible"], errors="coerce").fillna(0).astype(int)

        # --- FILTER / SORT ---
        df_filtered = build_ranked_trade_slice(df)
        candidate_total = len(df_filtered)
        yesterday_status = build_yesterday_status(df_filtered, file)

        cols = [
            "ticker",
            "company_name",
            "optionSymbol",
            "optionType",
            "strike",
            "expiryDate",
            "dte",
            "adaptive_score_final",
            "adaptive_score",
            "adaptive_rank",
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

        cols = [c for c in cols if c in df_filtered.columns]
        df_filtered = df_filtered[cols].head(25).copy()

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
        
        def build_tier(row):
            score = pd.to_numeric(row.get("adaptive_score_final"), errors="coerce")

            if pd.isna(score):
                return "N/A"
            if score >= 1.9:
                return "A+"
            elif score >= 1.8:
                return "A"
            elif score >= 1.6:
                return "A-"
            elif score >= 1.3:
                return "B+"
            else:
                return "B"
        
        def build_action(row):
            score = pd.to_numeric(row.get("adaptive_score_final"), errors="coerce")

            if pd.isna(score):
                return "UNKNOWN"
            if score >= 1.8:
                return "ENTER"
            elif score >= 1.3:
                return "WATCH"
            else:
                return "PASS"
        

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
            elif action == "PASS":
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

        for i, (_, row) in enumerate(df_filtered.iterrows(), start=1):
            sector_raw = safe_str(row.get("sector"))
            sector = sector_raw.strip() if sector_raw else None
            etf_info = etf_overlay_map.get(sector, {}) if sector else {}
            fallback_etf = SECTOR_TO_ETF_FALLBACK.get(sector) if sector else None
            action = build_action(row)
            tier = build_tier(row)
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
                sector=sector,
                option_type=option_type,
                structure_bucket=structure_bucket,
                dte=current_dte
            )

            today_top_pct = math.ceil((i / candidate_total) * 100) if candidate_total else None
            today_score = round(100 * ((candidate_total - i + 1) / candidate_total)) if candidate_total else None

            response.append({
                "rank": i,
                "ticker": safe_str(row.get("ticker")),
                "companyName": safe_str(row.get("company_name")),
                "tier": tier,
                "action": action,
                "optionType": option_type,
                "signalStrength": build_signal(row),

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
                    "adaptiveScore": safe_float(row.get("adaptive_score"), 3),
                    "adaptiveRank": safe_int(row.get("adaptive_rank")),
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
                        "rank": i,
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
                    "strategyStatsFile": strategy_stats.get("sourceFile"),
                    "mlModelVersion": safe_str(row.get("ml_model_version")),
                    "filterVersion": safe_str(row.get("filter_version")),
                    "dataCutoff": safe_str(row.get("data_cutoff")),
                    "runTimestamp": safe_str(row.get("run_timestamp")),
                    "signalDate": safe_str(row.get("signal_date"))
                },

            })
        
        if not include_pass:
            response = [trade for trade in response if trade.get("action") != "PASS"]

        if historical_con is not None:
            historical_con.close()
            historical_con = None

        return {
            "marketRegime": market_regime,
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
