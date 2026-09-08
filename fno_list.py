"""
fno_list.py
-----------
Provides the NSE F&O stock universe as Yahoo-Finance-style tickers (SYMBOL.NS).

NSE's official CSV endpoint changes / blocks scripts fairly often, so this
module ALWAYS has a solid hardcoded fallback list of ~150 liquid F&O names.
If you want to try live-updating it, use `try_fetch_live_fno_list()` --
it's best-effort and silently falls back if it fails.
"""

import requests

# A broad, liquid F&O fallback list (kept deliberately hardcoded so the app
# never breaks if NSE's website changes). Update occasionally if you like.
FALLBACK_FNO_LIST = [
    "RELIANCE", "TCS", "HDFCBANK", "ICICIBANK", "INFY", "HINDUNILVR", "ITC",
    "SBIN", "BHARTIARTL", "KOTAKBANK", "LT", "AXISBANK", "BAJFINANCE",
    "ASIANPAINT", "MARUTI", "TITAN", "SUNPHARMA", "ULTRACEMCO", "WIPRO",
    "NESTLEIND", "ONGC", "NTPC", "POWERGRID", "M&M", "TATAMOTORS", "TATASTEEL",
    "ADANIENT", "ADANIPORTS", "COALINDIA", "BAJAJFINSV", "HCLTECH", "TECHM",
    "DRREDDY", "CIPLA", "DIVISLAB", "GRASIM", "JSWSTEEL", "HINDALCO",
    "BRITANNIA", "EICHERMOT", "BPCL", "SHREECEM", "UPL", "APOLLOHOSP",
    "SBILIFE", "HDFCLIFE", "INDUSINDBK", "TATACONSUM", "BAJAJ-AUTO",
    "HEROMOTOCO", "VEDL", "PIDILITIND", "DABUR", "GODREJCP", "SIEMENS",
    "DLF", "GAIL", "AMBUJACEM", "ACC", "BANKBARODA", "PNB", "CANBK",
    "IDFCFIRSTB", "FEDERALBNK", "AUBANK", "BANDHANBNK", "CHOLAFIN",
    "MUTHOOTFIN", "PFC", "RECLTD", "IRFC", "SAIL", "NMDC", "NATIONALUM",
    "JINDALSTEL", "TATAPOWER", "TORNTPOWER", "ADANIGREEN", "ADANIPOWER",
    "ATGL", "IOC", "PETRONET", "GUJGASLTD", "MRF", "BALKRISIND", "APOLLOTYRE",
    "ASHOKLEY", "TVSMOTOR", "BOSCHLTD", "MOTHERSON", "EXIDEIND", "SONACOMS",
    "TRENT", "DMART", "NAUKRI", "ZOMATO", "PAYTM", "NYKAA", "IRCTC", "INDIGO",
    "PVRINOX", "JUBLFOOD", "VOLTAS", "HAVELLS", "CROMPTON", "POLYCAB",
    "DIXON", "AMBER", "PERSISTENT", "COFORGE", "LTIM", "MPHASIS", "LTTS",
    "OFSS", "TATAELXSI", "CYIENT", "BSOFT", "ZEEL", "SUNTV", "PVR",
    "LUPIN", "AUROPHARMA", "ALKEM", "TORNTPHARM", "BIOCON", "GLENMARK",
    "IPCALAB", "LAURUSLABS", "SYNGENE", "GRANULES", "ABBOTINDIA",
    "PIIND", "SRF", "DEEPAKNTR", "AARTIIND", "NAVINFLUOR", "TATACHEM",
    "UPL", "COROMANDEL", "GNFC", "CHAMBLFERT", "RCF",
    "LICHSGFIN", "MANAPPURAM", "BAJAJHLDNG", "ICICIPRULI", "ICICIGI",
    "MAXHEALTH", "FORTIS", "LALPATHLAB", "METROPOLIS", "SYNGENE",
    "HAL", "BEL", "BHEL", "BEML", "COCHINSHIP", "MAZDOCK", "IRCON",
    "RVNL", "CONCOR", "GMRINFRA", "IDEA", "INDUSTOWER", "TATACOMM",
    "OBEROIRLTY", "GODREJPROP", "PRESTIGE", "PHOENIXLTD", "LODHA",
    "MFSL", "PEL", "ABFRL", "PAGEIND", "RELAXO", "BATAINDIA", "VBL",
    "COLPAL", "MARICO", "EMAMILTD", "GILLETTE", "WHIRLPOOL",
]


def get_fno_tickers(force_refresh: bool = False) -> list[str]:
    """Return NSE F&O tickers in Yahoo Finance format, e.g. 'RELIANCE.NS'."""
    symbols = FALLBACK_FNO_LIST
    if force_refresh:
        live = try_fetch_live_fno_list()
        if live:
            symbols = live
    return [f"{s}.NS" for s in symbols]


def try_fetch_live_fno_list(timeout: int = 8) -> list[str] | None:
    """
    Best-effort attempt to pull the live F&O list from NSE's public archive.
    Returns None on any failure (blocked, timeout, format change, etc.) so
    the caller can safely fall back to FALLBACK_FNO_LIST.
    """
    url = "https://archives.nseindia.com/content/fo/fo_mktlots.csv"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        resp = requests.get(url, headers=headers, timeout=timeout)
        resp.raise_for_status()
        lines = resp.text.strip().splitlines()
        symbols = []
        for line in lines[1:]:
            parts = [p.strip() for p in line.split(",")]
            if len(parts) > 1 and parts[1] and parts[1] != "Symbol":
                symbols.append(parts[1])
        return symbols if symbols else None
    except Exception:
        return None
