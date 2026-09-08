"""
data_fetch.py
-------------
Free, no-login data fetching via yfinance, with a concurrent downloader
and the baseline liquidity filter (price + volume).

Timeframes supported: Daily, 75-minute (resampled from 15m), 15-minute, 5-minute.
Yahoo Finance limits how far back intraday data goes (~60 days for 5m/15m),
which is plenty for these screeners.
"""

import concurrent.futures as cf
import pandas as pd
import yfinance as yf

MIN_PRICE = 100.0
MIN_AVG_VOLUME = 1_000_000


def fetch_daily(ticker: str, period: str = "1y") -> pd.DataFrame | None:
    df = yf.Ticker(ticker).history(period=period, interval="1d")
    if df is None or df.empty:
        return None
    return df[["Open", "High", "Low", "Close", "Volume"]]


def fetch_intraday(ticker: str, interval: str = "15m", period: str = "60d") -> pd.DataFrame | None:
    df = yf.Ticker(ticker).history(period=period, interval=interval)
    if df is None or df.empty:
        return None
    return df[["Open", "High", "Low", "Close", "Volume"]]


def resample_to_75min(df_15m: pd.DataFrame) -> pd.DataFrame:
    """
    NSE trades 09:15-15:30 = 375 minutes = exactly 5x 75-minute candles per day.
    We build 75m bars by grouping each trading day's 15m bars into 5-bar chunks.
    """
    if df_15m is None or df_15m.empty:
        return pd.DataFrame(columns=["Open", "High", "Low", "Close", "Volume"])

    out_rows = []
    out_index = []
    for _, day_df in df_15m.groupby(df_15m.index.date):
        day_df = day_df.sort_index()
        for start in range(0, len(day_df), 5):
            chunk = day_df.iloc[start:start + 5]
            if chunk.empty:
                continue
            out_rows.append({
                "Open": chunk["Open"].iloc[0],
                "High": chunk["High"].max(),
                "Low": chunk["Low"].min(),
                "Close": chunk["Close"].iloc[-1],
                "Volume": chunk["Volume"].sum(),
            })
            out_index.append(chunk.index[0])
    return pd.DataFrame(out_rows, index=pd.DatetimeIndex(out_index))


def passes_liquidity_filter(daily_df: pd.DataFrame) -> bool:
    if daily_df is None or len(daily_df) < 20:
        return False
    last_close = daily_df["Close"].iloc[-1]
    avg_vol_20 = daily_df["Volume"].iloc[-20:].mean()
    return bool(last_close >= MIN_PRICE and avg_vol_20 >= MIN_AVG_VOLUME)


def fetch_all_timeframes(ticker: str) -> dict | None:
    """
    Fetches Daily, 15m, 5m, and derived 75m data for one ticker.
    Returns None if the ticker fails the liquidity filter or has no data.
    """
    daily = fetch_daily(ticker)
    if not passes_liquidity_filter(daily):
        return None

    m15 = fetch_intraday(ticker, "15m", "60d")
    m5 = fetch_intraday(ticker, "5m", "60d")
    m75 = resample_to_75min(m15) if m15 is not None else None

    return {
        "ticker": ticker,
        "daily": daily,
        "m75": m75,
        "m15": m15,
        "m5": m5,
    }


def fetch_universe(tickers: list[str], max_workers: int = 12,
                    progress_callback=None) -> dict[str, dict]:
    """
    Concurrently fetches all timeframes for every ticker.
    Returns {ticker: data_dict} only for tickers that passed the liquidity filter.
    `progress_callback(done, total)` is called after each ticker if provided.
    """
    results = {}
    total = len(tickers)
    done = 0

    with cf.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(fetch_all_timeframes, t): t for t in tickers}
        for future in cf.as_completed(futures):
            ticker = futures[future]
            done += 1
            try:
                data = future.result()
                if data is not None:
                    results[ticker] = data
            except Exception:
                pass  # skip tickers that error out (delisted, no data, API hiccup, etc.)
            if progress_callback:
                progress_callback(done, total)

    return results
