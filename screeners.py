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
                    "Candle": candle_label,
                    "HTM RSI (75m)": round(last_rsi75, 1),
                    "HTM Signal": "Bullish cross, widening",
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
                    "Candle": candle_label,
                    "HTM RSI (75m)": round(last_rsi75, 1),
                    "HTM Signal": "Bearish cross, widening",
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
            "HTM RSI (75m)": round(rsi75, 1),
            "HTM Signal": "Bullish, gap widening",
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
            "HTM RSI (75m)": round(rsi75, 1),
            "HTM Signal": "Bearish, gap widening",
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
        })

    return hits


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
            "Symbol", "Screener", "Direction", "LTP", "Key Level",
            "Candle", "HTM RSI (75m)", "HTM Signal",
        ])
    return pd.DataFrame(all_hits)
