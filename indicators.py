"""
indicators.py
--------------
All math lives here: Pivot Points, Anchored VWAP, the HTM (Hilega to Milega)
indicator, and candlestick pattern detection.

Every function takes a pandas DataFrame with columns:
    Open, High, Low, Close, Volume
and a DatetimeIndex, and returns either a new column/Series or a dict.
"""

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# 1. PIVOT POINTS (Traditional / Standard)
# ---------------------------------------------------------------------------
def calc_pivot_points(prev_high: float, prev_low: float, prev_close: float) -> dict:
    """Standard floor-trader pivots from the PREVIOUS period's H/L/C."""
    p = (prev_high + prev_low + prev_close) / 3
    s1 = (2 * p) - prev_high
    s2 = p - (prev_high - prev_low)
    r1 = (2 * p) - prev_low
    r2 = p + (prev_high - prev_low)
    return {"P": p, "S1": s1, "S2": s2, "R1": r1, "R2": r2}


def daily_weekly_monthly_pivots(df: pd.DataFrame) -> dict:
    """
    Given a Daily OHLCV DataFrame (DatetimeIndex), returns pivot levels for:
      - 'daily'   : based on the last completed trading day
      - 'weekly'  : based on the last completed calendar week
      - 'monthly' : based on the last completed calendar month
    """
    out = {}
    if len(df) < 2:
        return out

    # Daily: previous day's bar
    prev_day = df.iloc[-2]
    out["daily"] = calc_pivot_points(prev_day["High"], prev_day["Low"], prev_day["Close"])

    # Weekly: resample to week, use the last COMPLETED week
    weekly = df.resample("W").agg({"High": "max", "Low": "min", "Close": "last"}).dropna()
    if len(weekly) >= 2:
        pw = weekly.iloc[-2]
        out["weekly"] = calc_pivot_points(pw["High"], pw["Low"], pw["Close"])

    # Monthly: resample to month, use the last COMPLETED month
    monthly = df.resample("ME").agg({"High": "max", "Low": "min", "Close": "last"}).dropna()
    if len(monthly) >= 2:
        pm = monthly.iloc[-2]
        out["monthly"] = calc_pivot_points(pm["High"], pm["Low"], pm["Close"])

    return out


# ---------------------------------------------------------------------------
# 2. ANCHORED VWAP
# ---------------------------------------------------------------------------
def anchored_vwap(df: pd.DataFrame, anchor_date=None) -> pd.Series:
    """
    Anchored VWAP starting from `anchor_date` (a string or Timestamp).
    If anchor_date is None, anchors from the first row (i.e. normal cumulative VWAP).
    Returns a Series aligned to df.index (NaN before the anchor).
    """
    typical_price = (df["High"] + df["Low"] + df["Close"]) / 3
    tpv = typical_price * df["Volume"]

    avwap = pd.Series(index=df.index, dtype=float)

    if anchor_date is None:
        start_pos = 0
    else:
        anchor_ts = pd.Timestamp(anchor_date)
        matches = df.index[df.index >= anchor_ts]
        if len(matches) == 0:
            return avwap  # all NaN, anchor is in the future / not found
        start_pos = df.index.get_loc(matches[0])

    cum_tpv = tpv.iloc[start_pos:].cumsum()
    cum_vol = df["Volume"].iloc[start_pos:].cumsum().replace(0, np.nan)
    avwap.iloc[start_pos:] = cum_tpv / cum_vol
    return avwap


# ---------------------------------------------------------------------------
# 3. HTM (Hilega to Milega) INDICATOR
# ---------------------------------------------------------------------------
def wilder_rsi(close: pd.Series, period: int = 9) -> pd.Series:
    """Wilder's smoothed RSI."""
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()

    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    rsi = rsi.fillna(50)  # neutral where undefined (e.g. no losses yet)
    return rsi


def _linear_wma(series: pd.Series, period: int) -> pd.Series:
    weights = np.arange(1, period + 1)
    return series.rolling(period).apply(
        lambda x: np.dot(x, weights) / weights.sum(), raw=True
    )


def htm_indicator(df: pd.DataFrame, rsi_period: int = 9,
                   price_ema: int = 3, volume_wma: int = 21) -> pd.DataFrame:
    """
    Returns a DataFrame with columns:
      rsi9        - 9-period Wilder RSI of Close
      price_line  - 3-EMA of the RSI ("fast" line)
      volume_line - 21-period linear WMA of the RSI ("slow" line)
      gap         - price_line - volume_line (positive = bullish, widening = strengthening)
      baseline    - constant 50
    """
    rsi = wilder_rsi(df["Close"], rsi_period)
    price_line = rsi.ewm(span=price_ema, adjust=False).mean()
    volume_line = _linear_wma(rsi, volume_wma)

    out = pd.DataFrame(index=df.index)
    out["rsi9"] = rsi
    out["price_line"] = price_line
    out["volume_line"] = volume_line
    out["gap"] = price_line - volume_line
    out["baseline"] = 50.0
    return out


def htm_bullish_cross_widening(htm_df: pd.DataFrame) -> bool:
    """True if price_line just crossed above volume_line AND the gap is widening."""
    if len(htm_df) < 3:
        return False
    g = htm_df["gap"]
    crossed_up = g.iloc[-2] <= 0 and g.iloc[-1] > 0
    widening = g.iloc[-1] > g.iloc[-2]
    return bool(crossed_up and widening)


def htm_bearish_cross_widening(htm_df: pd.DataFrame) -> bool:
    """True if price_line just crossed below volume_line AND the (negative) gap is widening."""
    if len(htm_df) < 3:
        return False
    g = htm_df["gap"]
    crossed_dn = g.iloc[-2] >= 0 and g.iloc[-1] < 0
    widening = g.iloc[-1] < g.iloc[-2]
    return bool(crossed_dn and widening)


# ---------------------------------------------------------------------------
# 4. CANDLESTICK PATTERNS
# ---------------------------------------------------------------------------
def _body(row):
    return abs(row["Close"] - row["Open"])


def _range(row):
    return row["High"] - row["Low"]


def is_hammer(row) -> bool:
    rng = _range(row)
    if rng <= 0:
        return False
    body = _body(row)
    lower_wick = min(row["Open"], row["Close"]) - row["Low"]
    upper_wick = row["High"] - max(row["Open"], row["Close"])
    return (lower_wick >= 2 * body) and (upper_wick <= 0.25 * rng) and (body > 0)


def is_shooting_star(row) -> bool:
    rng = _range(row)
    if rng <= 0:
        return False
    body = _body(row)
    upper_wick = row["High"] - max(row["Open"], row["Close"])
    lower_wick = min(row["Open"], row["Close"]) - row["Low"]
    return (upper_wick >= 2 * body) and (lower_wick <= 0.25 * rng) and (body > 0)


def is_doji(row, threshold: float = 0.1) -> bool:
    rng = _range(row)
    if rng <= 0:
        return False
    return _body(row) <= threshold * rng


def is_bullish_engulfing(prev, curr) -> bool:
    return (
        prev["Close"] < prev["Open"]
        and curr["Close"] > curr["Open"]
        and curr["Close"] >= prev["Open"]
        and curr["Open"] <= prev["Close"]
    )


def is_bearish_engulfing(prev, curr) -> bool:
    return (
        prev["Close"] > prev["Open"]
        and curr["Close"] < curr["Open"]
        and curr["Open"] >= prev["Close"]
        and curr["Close"] <= prev["Open"]
    )


def is_stopping_volume(df: pd.DataFrame, i: int, vol_sma_period: int = 20,
                        vol_multiple: float = 2.0, wick_fraction: float = 0.6) -> str | None:
    """
    Returns 'bullish' (red stopping-volume bar absorbing selling),
            'bearish' (green topping-volume bar absorbing buying), or None.
    """
    if i < vol_sma_period:
        return None
    row = df.iloc[i]
    rng = _range(row)
    if rng <= 0:
        return None
    vol_sma = df["Volume"].iloc[i - vol_sma_period:i].mean()
    if vol_sma == 0 or row["Volume"] < vol_multiple * vol_sma:
        return None

    lower_wick = min(row["Open"], row["Close"]) - row["Low"]
    upper_wick = row["High"] - max(row["Open"], row["Close"])
    is_red = row["Close"] < row["Open"]
    is_green = row["Close"] > row["Open"]

    if is_red and lower_wick >= wick_fraction * rng:
        return "bullish"   # heavy volume, sellers absorbed, closed off the low
    if is_green and upper_wick >= wick_fraction * rng:
        return "bearish"   # heavy volume, buyers absorbed, closed off the high
    return None


def classify_candle(df: pd.DataFrame, i: int) -> str:
    """Best-effort single label for the candle at position i."""
    row = df.iloc[i]
    if is_hammer(row):
        return "Hammer"
    if is_shooting_star(row):
        return "Shooting Star"
    if is_doji(row):
        return "Doji"
    if i > 0:
        prev = df.iloc[i - 1]
        if is_bullish_engulfing(prev, row):
            return "Bullish Engulfing"
        if is_bearish_engulfing(prev, row):
            return "Bearish Engulfing"
    sv = is_stopping_volume(df, i)
    if sv == "bullish":
        return "Stopping Volume (Bullish)"
    if sv == "bearish":
        return "Stopping Volume (Bearish)"
    return "-"
