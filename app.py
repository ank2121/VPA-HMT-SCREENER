"""
app.py
------
VPA + HTM Screener Dashboard — Streamlit app.

Run locally with:
    streamlit run app.py

Free forever hosting: push this repo to GitHub, then deploy on
Streamlit Community Cloud (share.streamlit.io) — no server, no cost.
"""

import time
import pandas as pd
import streamlit as st

from fno_list import get_fno_tickers
from data_fetch import fetch_universe
from screeners import run_all_screeners

st.set_page_config(
    page_title="VPA + HTM Screener",
    page_icon="📈",
    layout="wide",
)

# ---------------------------------------------------------------------------
# STYLE
# ---------------------------------------------------------------------------
st.markdown("""
<style>
    .main { background-color: #0e1117; }
    div[data-testid="stMetricValue"] { font-size: 1.6rem; }
    .long-badge { color: #16c784; font-weight: 700; }
    .short-badge { color: #ea3943; font-weight: 700; }
    .stDataFrame { border-radius: 10px; overflow: hidden; }
</style>
""", unsafe_allow_html=True)

st.title("📈 VPA + HTM Screener")
st.caption("Reversal • Intraday Momentum • Swing Trend-Following — NSE F&O universe, powered by free Yahoo Finance data")

# ---------------------------------------------------------------------------
# SIDEBAR CONTROLS
# ---------------------------------------------------------------------------
with st.sidebar:
    st.header("⚙️ Scan Settings")
    universe_size = st.slider("How many F&O stocks to scan", 20, 200, 80, step=10)
    refresh_live_list = st.checkbox("Try fetching the live NSE F&O list", value=False,
                                     help="If unchecked, uses a reliable built-in list of liquid F&O stocks.")
    st.divider()
    run_button = st.button("🔍 Run Scan Now", type="primary", use_container_width=True)
    st.divider()
    st.markdown(
        "**Free forever.** No broker login needed — data comes from Yahoo Finance. "
        "Deploy this app on Streamlit Community Cloud to run it from your phone or laptop, anytime, at zero cost."
    )

# ---------------------------------------------------------------------------
# STATE
# ---------------------------------------------------------------------------
if "results" not in st.session_state:
    st.session_state.results = None
    st.session_state.scan_time = None

# ---------------------------------------------------------------------------
# RUN SCAN
# ---------------------------------------------------------------------------
if run_button:
    tickers = get_fno_tickers(force_refresh=refresh_live_list)[:universe_size]

    progress_bar = st.progress(0, text="Starting scan...")

    def _progress(done, total):
        progress_bar.progress(done / total, text=f"Fetching data... {done}/{total} stocks")

    with st.spinner("Downloading price data and calculating indicators..."):
        universe = fetch_universe(tickers, max_workers=12, progress_callback=_progress)

    progress_bar.progress(1.0, text="Running screeners...")
    results = run_all_screeners(universe)
    progress_bar.empty()

    st.session_state.results = results
    st.session_state.scan_time = time.strftime("%Y-%m-%d %H:%M:%S")
    st.session_state.scanned_count = len(universe)
    st.session_state.requested_count = len(tickers)

# ---------------------------------------------------------------------------
# TOP METRICS
# ---------------------------------------------------------------------------
results = st.session_state.results

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("Stocks Requested", st.session_state.get("requested_count", 0))
with col2:
    st.metric("Passed Liquidity Filter", st.session_state.get("scanned_count", 0))
with col3:
    st.metric("Setups Found", 0 if results is None else len(results))
with col4:
    st.metric("Last Scan", st.session_state.scan_time or "—")

st.divider()

# ---------------------------------------------------------------------------
# RESULTS
# ---------------------------------------------------------------------------
if results is None:
    st.info("👈 Set your scan size in the sidebar and click **Run Scan Now** to begin.")
elif results.empty:
    st.warning("No setups matched any screener in this scan. Try again after the next candle close, "
               "or widen the universe size.")
else:
    tab1, tab2, tab3, tab_all = st.tabs([
        "🔄 Reversal", "⚡ Intraday Momentum", "📊 Swing", "📋 All Results"
    ])

    def _style_direction(df: pd.DataFrame):
        return df.style.applymap(
            lambda v: "color: #16c784; font-weight: 700" if v == "Long"
            else ("color: #ea3943; font-weight: 700" if v == "Short" else ""),
            subset=["Direction"],
        )

    with tab1:
        sub = results[results["Screener"].str.startswith("Screener 1")]
        st.dataframe(_style_direction(sub) if not sub.empty else sub, use_container_width=True, hide_index=True)

    with tab2:
        sub = results[results["Screener"].str.startswith("Screener 2")]
        st.dataframe(_style_direction(sub) if not sub.empty else sub, use_container_width=True, hide_index=True)

    with tab3:
        sub = results[results["Screener"].str.startswith("Screener 3")]
        st.dataframe(_style_direction(sub) if not sub.empty else sub, use_container_width=True, hide_index=True)

    with tab_all:
        st.dataframe(_style_direction(results), use_container_width=True, hide_index=True)
        csv = results.to_csv(index=False).encode("utf-8")
        st.download_button("⬇️ Download CSV", csv, "nse_screener_results.csv", "text/csv",
                            use_container_width=True)
