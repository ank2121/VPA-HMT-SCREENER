"""
screeners.py
------------
The three screening strategies from the playbook. Each screener function
takes the per-ticker data dict from data_fetch.fetch_universe() and returns
a list of "hit" dicts describing any matching setup.
"""

import numpy as np
import pandas as pd

import indicators as ind

NEAR_LEVEL_PCT = 0.005          # +/- 0.5% for "near support/resistance"
PULLBACK_PCT = 0.01             # +/- 1% for swing pullback
VOL_SURGE_MULTIPLE = 2.0
COMPRESSION_ATR_MULTIPLE = 1.2


def _pct_near(price: float, level: float, pct: float = NEAR_LEVEL_PCT) -> bool:
    if level is None or level == 0 or pd.isna(level):
        return False
    return abs(price - level) / level <= pct


def _swing_low(daily: pd.DataFrame, lookback: int = 20) -> float:
    return daily["Low"].iloc[-lookback:-1].min() if len(daily) > lookback else np.nan


def _swing_high(daily: pd.DataFrame, lookback: int = 20) -> float:
    return daily["High"].iloc[-lookback:-1].max() if len(daily) > lookback else np.nan


# ---------------------------------------------------------------------------
# SCREENER 1: Reversal (Stopping Volume + HTM Reversal confirmation)
# ---------------------------------------------------------------------------
def screener_reversal(ticker: str, data: dict) -> list[dict]:
    hits = []
    daily = data["daily"]
    m75 = data["m75"]
    intraday = data["m15"] if data["m15"] is not None and not data["m15"].empty else data["m5"]
    if daily is None or m75 is None or intraday is None or len(m75) < 25 or len(intraday) < 5:
        return hits

    pivots = ind.daily_weekly_monthly_pivots(daily)
    htm75 = ind.htm_indicator(m75)
    if htm75.empty or htm75["rsi9"].isna().all():
        return hits

    last_price = intraday["Close"].iloc[-1]
    last_rsi75 = htm75["rsi9"].iloc[-1]
    candle_label = ind.classify_candle(intraday, len(intraday) - 1)

    swing_low = _swing_low(daily)
    swing_high = _swing_high(daily)

    support_levels = {"Swing Low": swing_low}
    resistance_levels = {"Swing High": swing_high}
    for scope in ("daily", "weekly"):
        if scope in pivots:
            support_levels[f"{scope.title()} S1"] = pivots[scope]["S1"]
            support_levels[f"{scope.title()} S2"] = pivots[scope]["S2"]
            resistance_levels[f"{scope.title()} R1"] = pivots[scope]["R1"]
            resistance_levels[f"{scope.title()} R2"] = pivots[scope]["R2"]

    bullish_candle = candle_label in ("Hammer", "Doji", "Bullish Engulfing", "Stopping Volume (Bullish)")
    bearish_candle = candle_label in ("Shooting Star", "Doji", "Bearish Engulfing", "Stopping Volume (Bearish)")

    signal_time = intraday.index[-1]
    timeframe_label = "15m" if data["m15"] is not None and not data["m15"].empty else "5m"

    def _level_type(level_name: str) -> str:
        return "Intraday Swing Level" if level_name.startswith("Swing ") else "Daily/Weekly Pivot"

    # Bullish reversal
    if bullish_candle and last_rsi75 < 30 and ind.htm_bullish_cross_widening(htm75):
        for name, level in support_levels.items():
            if _pct_near(last_price, level):
                hits.append({
                    "Symbol": ticker.replace(".NS", ""),
                    "Screener": "Screener 1: Reversal",
                    "Direction": "Long",
                    "LTP": round(last_price, 2),
                    "Key Level": name,
                    "Level Type": _level_type(name),
                    "Candle": candle_label,
                    "HTM RSI (75m)": f"{last_rsi75:.1f}",
                    "HTM Signal": "Bullish cross, widening",
                    "Signal Time": signal_time.strftime("%Y-%m-%d %H:%M"),
                    "Timeframe": timeframe_label,
                })
                break

    # Bearish reversal
    if bearish_candle and last_rsi75 > 70 and ind.htm_bearish_cross_widening(htm75):
        for name, level in resistance_levels.items():
            if _pct_near(last_price, level):
                hits.append({
                    "Symbol": ticker.replace(".NS", ""),
                    "Screener": "Screener 1: Reversal",
                    "Direction": "Short",
                    "LTP": round(last_price, 2),
                    "Key Level": name,
                    "Level Type": _level_type(name),
                    "Candle": candle_label,
                    "HTM RSI (75m)": f"{last_rsi75:.1f}",
                    "HTM Signal": "Bearish cross, widening",
                    "Signal Time": signal_time.strftime("%Y-%m-%d %H:%M"),
                    "Timeframe": timeframe_label,
                })
                break

    return hits


# ---------------------------------------------------------------------------
# SCREENER 2: Intraday Trend-Following Momentum
# ---------------------------------------------------------------------------
def screener_intraday_momentum(ticker: str, data: dict) -> list[dict]:
    hits = []
    daily = data["daily"]
    m75 = data["m75"]
    if daily is None or m75 is None or len(daily) < 25 or len(m75) < 25:
        return hits

    daily = daily.copy()
    daily["SMA5"] = daily["Close"].rolling(5).mean()
    daily["SMA20"] = daily["Close"].rolling(20).mean()
    price = daily["Close"].iloc[-1]
    sma5, sma5_prev = daily["SMA5"].iloc[-1], daily["SMA5"].iloc[-2]
    sma20, sma20_prev = daily["SMA20"].iloc[-1], daily["SMA20"].iloc[-2]
    if pd.isna(sma5) or pd.isna(sma20):
        return hits

    vol_rising = daily["Volume"].iloc[-1] > daily["Volume"].iloc[-5:-1].mean()
    yesterday_high = daily["High"].iloc[-2]
    yesterday_low = daily["Low"].iloc[-2]

    htm75 = ind.htm_indicator(m75)
    if htm75.empty:
        return hits
    rsi75 = htm75["rsi9"].iloc[-1]
    gap75, gap75_prev = htm75["gap"].iloc[-1], htm75["gap"].iloc[-2]
    signal_time = m75.index[-1]

    # Long
    if (price > sma5 > sma20 and sma5 > sma5_prev and sma20 > sma20_prev
            and vol_rising and rsi75 > 50 and gap75 > 0 and gap75 > gap75_prev
            and price > yesterday_high):
        hits.append({
            "Symbol": ticker.replace(".NS", ""),
            "Screener": "Screener 2: Intraday Momentum",
            "Direction": "Long",
            "LTP": round(price, 2),
            "Key Level": "Broke Yesterday's High",
            "Candle": "-",
            "HTM RSI (75m)": f"{rsi75:.1f}",
            "HTM Signal": "Bullish, gap widening",
            "Signal Time": signal_time.strftime("%Y-%m-%d %H:%M"),
            "Timeframe": "75m (Daily trend confirmed)",
        })

    # Short
    if (price < sma5 < sma20 and sma5 < sma5_prev and sma20 < sma20_prev
            and vol_rising and rsi75 < 50 and gap75 < 0 and gap75 < gap75_prev
            and price < yesterday_low):
        hits.append({
            "Symbol": ticker.replace(".NS", ""),
            "Screener": "Screener 2: Intraday Momentum",
            "Direction": "Short",
            "LTP": round(price, 2),
            "Key Level": "Broke Yesterday's Low",
            "Candle": "-",
            "HTM RSI (75m)": f"{rsi75:.1f}",
            "HTM Signal": "Bearish, gap widening",
            "Signal Time": signal_time.strftime("%Y-%m-%d %H:%M"),
            "Timeframe": "75m (Daily trend confirmed)",
        })

    return hits


# ---------------------------------------------------------------------------
# SCREENER 3: Swing Trend-Following (Long only)
# ---------------------------------------------------------------------------
def screener_swing(ticker: str, data: dict) -> list[dict]:
    hits = []
    daily = data["daily"]
    m75 = data["m75"]
    if daily is None or len(daily) < 210:
        return hits

    d = daily.copy()
    d["EMA20"] = d["Close"].ewm(span=20, adjust=False).mean()
    d["SMA50"] = d["Close"].rolling(50).mean()
    d["SMA100"] = d["Close"].rolling(100).mean()
    d["SMA200"] = d["Close"].rolling(200).mean()

    price = d["Close"].iloc[-1]
    ema20, ema20_prev = d["EMA20"].iloc[-1], d["EMA20"].iloc[-6]
    sma50, sma50_prev = d["SMA50"].iloc[-1], d["SMA50"].iloc[-6]
    sma100, sma100_prev = d["SMA100"].iloc[-1], d["SMA100"].iloc[-6]
    sma200, sma200_prev = d["SMA200"].iloc[-1], d["SMA200"].iloc[-6]

    if any(pd.isna(x) for x in [ema20, sma50, sma100, sma200]):
        return hits

    aligned = price > ema20 > sma50 > sma100 > sma200
    sloped_up = (ema20 > ema20_prev and sma50 > sma50_prev
                 and sma100 > sma100_prev and sma200 > sma200_prev)

    ytd_start = f"{d.index[-1].year}-01-01"
    ytd_avwap = ind.anchored_vwap(d, ytd_start).iloc[-1]
    above_ytd_avwap = (not pd.isna(ytd_avwap)) and price > ytd_avwap

    if not (aligned and sloped_up and above_ytd_avwap):
        return hits  # core trend condition not met -- no setup either way

    # --- Trigger A: Pullback to rising 20 EMA on declining volume ---
    near_ema = _pct_near(price, ema20, PULLBACK_PCT)
    vol_declining = d["Volume"].iloc[-1] < d["Volume"].iloc[-6:-1].mean()

    htm_confirm_a = False
    if m75 is not None and len(m75) > 5:
        htm75 = ind.htm_indicator(m75)
        if not htm75.empty:
            vline, vline_prev = htm75["volume_line"].iloc[-1], htm75["volume_line"].iloc[-2]
            pline, pline_prev = htm75["price_line"].iloc[-1], htm75["price_line"].iloc[-2]
            rsi_prev = htm75["rsi9"].iloc[-2]
            crossed_above_rsi = pline_prev <= rsi_prev and pline > htm75["rsi9"].iloc[-1]
            htm_confirm_a = bool(vline < 50 and crossed_above_rsi)

    if near_ema and vol_declining and htm_confirm_a:
        hits.append({
            "Symbol": ticker.replace(".NS", ""),
            "Screener": "Screener 3: Swing (Pullback)",
            "Direction": "Long",
            "LTP": round(price, 2),
            "Key Level": "Pullback to rising 20 EMA",
            "Candle": "-",
            "HTM RSI (75m)": "-",
            "HTM Signal": "75m Volume Line < 50, Price crossed RSI",
            "Signal Time": d.index[-1].strftime("%Y-%m-%d"),
            "Timeframe": "Daily",
        })

    # --- Trigger B: Base breakout on volume surge ---
    last5 = d.iloc[-5:]
    range5 = last5["High"].max() - last5["Low"].min()
    tr = pd.concat([
        d["High"] - d["Low"],
        (d["High"] - d["Close"].shift()).abs(),
        (d["Low"] - d["Close"].shift()).abs(),
    ], axis=1).max(axis=1)
    atr5 = tr.iloc[-5:].mean()
    compressed = (not pd.isna(atr5)) and atr5 > 0 and range5 < COMPRESSION_ATR_MULTIPLE * atr5

    consolidation_high = d["High"].iloc[-8:-1].max()
    vol_sma20 = d["Volume"].iloc[-21:-1].mean()
    breakout = (price > consolidation_high
                and d["Volume"].iloc[-1] >= VOL_SURGE_MULTIPLE * vol_sma20)

    if compressed and breakout:
        hits.append({
            "Symbol": ticker.replace(".NS", ""),
            "Screener": "Screener 3: Swing (Base Breakout)",
            "Direction": "Long",
            "LTP": round(price, 2),
            "Key Level": "7-day Base Breakout",
            "Candle": "-",
            "HTM RSI (75m)": "-",
            "HTM Signal": f"Volume {round(d['Volume'].iloc[-1] / vol_sma20, 1)}x avg",
            "Signal Time": d.index[-1].strftime("%Y-%m-%d"),
            "Timeframe": "Daily",
        })

    return hits


# ---------------------------------------------------------------------------
# DIAGNOSTICS — "how close did this stock get?" for each screener.
# This exists so a 0-result scan can be checked, not just trusted blindly.
# ---------------------------------------------------------------------------
def diagnose_swing(ticker: str, data: dict) -> dict | None:
    daily = data["daily"]
    if daily is None or len(daily) < 210:
        return None
    d = daily.copy()
    d["EMA20"] = d["Close"].ewm(span=20, adjust=False).mean()
    d["SMA50"] = d["Close"].rolling(50).mean()
    d["SMA100"] = d["Close"].rolling(100).mean()
    d["SMA200"] = d["Close"].rolling(200).mean()
    price = d["Close"].iloc[-1]
    ema20, ema20_prev = d["EMA20"].iloc[-1], d["EMA20"].iloc[-6]
    sma50, sma50_prev = d["SMA50"].iloc[-1], d["SMA50"].iloc[-6]
    sma100, sma100_prev = d["SMA100"].iloc[-1], d["SMA100"].iloc[-6]
    sma200, sma200_prev = d["SMA200"].iloc[-1], d["SMA200"].iloc[-6]
    if any(pd.isna(x) for x in [ema20, sma50, sma100, sma200]):
        return None

    ytd_start = f"{d.index[-1].year}-01-01"
    ytd_avwap = ind.anchored_vwap(d, ytd_start).iloc[-1]

    conditions = {
        "Price > 20 EMA": price > ema20,
        "20 EMA > 50 SMA": ema20 > sma50,
        "50 SMA > 100 SMA": sma50 > sma100,
        "100 SMA > 200 SMA": sma100 > sma200,
        "All 4 MAs sloped up (5d)": (ema20 > ema20_prev and sma50 > sma50_prev
                                     and sma100 > sma100_prev and sma200 > sma200_prev),
        "Above YTD Anchored VWAP": (not pd.isna(ytd_avwap)) and price > ytd_avwap,
    }
    score = sum(conditions.values())
    return {"Symbol": ticker.replace(".NS", ""), "LTP": round(price, 2),
            "Score": f"{score}/{len(conditions)}", "_score": score, "_total": len(conditions),
            **{k: ("✅" if v else "❌") for k, v in conditions.items()}}


def diagnose_momentum(ticker: str, data: dict) -> dict | None:
    daily, m75 = data["daily"], data["m75"]
    if daily is None or m75 is None or len(daily) < 25 or len(m75) < 25:
        return None
    d = daily.copy()
    d["SMA5"] = d["Close"].rolling(5).mean()
    d["SMA20"] = d["Close"].rolling(20).mean()
    price = d["Close"].iloc[-1]
    sma5, sma5_prev = d["SMA5"].iloc[-1], d["SMA5"].iloc[-2]
    sma20, sma20_prev = d["SMA20"].iloc[-1], d["SMA20"].iloc[-2]
    if pd.isna(sma5) or pd.isna(sma20):
        return None
    htm75 = ind.htm_indicator(m75)
    if htm75.empty:
        return None
    rsi75 = htm75["rsi9"].iloc[-1]
    gap75, gap75_prev = htm75["gap"].iloc[-1], htm75["gap"].iloc[-2]
    yesterday_high = d["High"].iloc[-2]

    conditions_long = {
        "Price>SMA5>SMA20": price > sma5 > sma20,
        "SMA5 & SMA20 rising": sma5 > sma5_prev and sma20 > sma20_prev,
        "Volume rising": d["Volume"].iloc[-1] > d["Volume"].iloc[-5:-1].mean(),
        "75m RSI > 50": rsi75 > 50,
        "HTM gap positive & widening": gap75 > 0 and gap75 > gap75_prev,
        "Broke yesterday's High": price > yesterday_high,
    }
    score = sum(conditions_long.values())
    return {"Symbol": ticker.replace(".NS", ""), "LTP": round(price, 2),
            "Score": f"{score}/{len(conditions_long)}", "_score": score, "_total": len(conditions_long),
            **{k: ("✅" if v else "❌") for k, v in conditions_long.items()}}


def diagnose_reversal(ticker: str, data: dict) -> dict | None:
    daily, m75 = data["daily"], data["m75"]
    intraday = data["m15"] if data["m15"] is not None and not data["m15"].empty else data["m5"]
    if daily is None or m75 is None or intraday is None or len(m75) < 25 or len(intraday) < 5:
        return None
    htm75 = ind.htm_indicator(m75)
    if htm75.empty or htm75["rsi9"].isna().all():
        return None
    last_price = intraday["Close"].iloc[-1]
    last_rsi75 = htm75["rsi9"].iloc[-1]
    candle_label = ind.classify_candle(intraday, len(intraday) - 1)
    swing_low = _swing_low(daily)
    nearest_support_dist = abs(last_price - swing_low) / swing_low if swing_low and not pd.isna(swing_low) else np.nan

    conditions = {
        "Candle is a reversal shape": candle_label != "-",
        "75m RSI < 30 (oversold) or > 70 (overbought)": (last_rsi75 < 30 or last_rsi75 > 70),
        "HTM lines just crossed & widening": (ind.htm_bullish_cross_widening(htm75)
                                               or ind.htm_bearish_cross_widening(htm75)),
        "Within 0.5% of a support/resistance level": (not pd.isna(nearest_support_dist)
                                                        and nearest_support_dist <= 0.005),
    }
    score = sum(conditions.values())
    return {"Symbol": ticker.replace(".NS", ""), "LTP": round(last_price, 2),
            "Score": f"{score}/{len(conditions)}", "_score": score, "_total": len(conditions),
            **{k: ("✅" if v else "❌") for k, v in conditions.items()}}


def run_diagnostics(universe: dict[str, dict]) -> dict[str, pd.DataFrame]:
    """Returns {'Reversal': df, 'Intraday Momentum': df, 'Swing': df}, each
    sorted by score descending -- the stocks that came CLOSEST to firing."""
    rows = {"Reversal": [], "Intraday Momentum": [], "Swing": []}
    for ticker, data in universe.items():
        try:
            r = diagnose_reversal(ticker, data)
            if r:
                rows["Reversal"].append(r)
            m = diagnose_momentum(ticker, data)
            if m:
                rows["Intraday Momentum"].append(m)
            s = diagnose_swing(ticker, data)
            if s:
                rows["Swing"].append(s)
        except Exception:
            continue
    out = {}
    for name, lst in rows.items():
        df = pd.DataFrame(lst)
        if not df.empty:
            df = df.sort_values("_score", ascending=False).drop(columns=["_score", "_total"])
        out[name] = df
    return out


def run_all_screeners(universe: dict[str, dict]) -> pd.DataFrame:
    """universe = {ticker: data_dict} from data_fetch.fetch_universe()."""
    all_hits = []
    for ticker, data in universe.items():
        try:
            all_hits.extend(screener_reversal(ticker, data))
            all_hits.extend(screener_intraday_momentum(ticker, data))
            all_hits.extend(screener_swing(ticker, data))
        except Exception:
            continue  # never let one bad ticker crash the whole scan
    if not all_hits:
        return pd.DataFrame(columns=[
            "Symbol", "Screener", "Direction", "LTP", "Key Level", "Level Type",
            "Candle", "HTM RSI (75m)", "HTM Signal", "Signal Time", "Timeframe",
        ])
    return pd.DataFrame(all_hits)
