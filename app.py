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
from screeners import run_all_screeners, run_diagnostics

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
    .main { background-color: #0b0e14; }
    div[data-testid="stMetricValue"] { font-size: 1.7rem; }
    .stDataFrame { border-radius: 10px; overflow: hidden; }

    .screener-card {
        border-radius: 12px;
        padding: 18px 20px;
        margin-bottom: 6px;
        border: 1px solid rgba(255,255,255,0.08);
    }
    .card-reversal   { background: linear-gradient(135deg, rgba(168,85,247,0.12), rgba(168,85,247,0.02)); border-left: 4px solid #a855f7; }
    .card-momentum   { background: linear-gradient(135deg, rgba(56,189,248,0.12), rgba(56,189,248,0.02)); border-left: 4px solid #38bdf8; }
    .card-swing      { background: linear-gradient(135deg, rgba(34,197,94,0.12), rgba(34,197,94,0.02)); border-left: 4px solid #22c55e; }
    .card-title { font-size: 0.85rem; text-transform: uppercase; letter-spacing: 0.06em; opacity: 0.75; margin-bottom: 4px; }
    .card-count { font-size: 2.1rem; font-weight: 800; line-height: 1.1; }
    .card-desc  { font-size: 0.82rem; opacity: 0.7; margin-top: 4px; }
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
for key, default in [("results", None), ("diagnostics", None), ("scan_time", None),
                      ("scanned_count", 0), ("requested_count", 0)]:
    if key not in st.session_state:
        st.session_state[key] = default

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
    st.session_state.results = run_all_screeners(universe)
    st.session_state.diagnostics = run_diagnostics(universe)
    progress_bar.empty()

    st.session_state.scan_time = time.strftime("%Y-%m-%d %H:%M:%S")
    st.session_state.scanned_count = len(universe)
    st.session_state.requested_count = len(tickers)

results = st.session_state.results
diag = st.session_state.diagnostics

# ---------------------------------------------------------------------------
# TOP METRICS
# ---------------------------------------------------------------------------
mcol1, mcol2, mcol3 = st.columns(3)
with mcol1:
    st.metric("Stocks Requested", st.session_state.requested_count)
with mcol2:
    st.metric("Passed Liquidity Filter", st.session_state.scanned_count)
with mcol3:
    st.metric("Last Scan", st.session_state.scan_time or "—")

st.write("")


def _count(screener_prefix: str) -> int:
    if results is None or results.empty:
        return 0
    return int(results["Screener"].str.startswith(screener_prefix).sum())


c1, c2, c3 = st.columns(3)
with c1:
    st.markdown(f"""<div class="screener-card card-reversal">
        <div class="card-title">🔄 Reversal</div>
        <div class="card-count">{_count("Screener 1")}</div>
        <div class="card-desc">Stopping-volume candle at support/resistance, HTM-confirmed</div>
    </div>""", unsafe_allow_html=True)
with c2:
    st.markdown(f"""<div class="screener-card card-momentum">
        <div class="card-title">⚡ Intraday Momentum</div>
        <div class="card-count">{_count("Screener 2")}</div>
        <div class="card-desc">Trend-following breakout above/below yesterday's range</div>
    </div>""", unsafe_allow_html=True)
with c3:
    st.markdown(f"""<div class="screener-card card-swing">
        <div class="card-title">📊 Swing Trend</div>
        <div class="card-count">{_count("Screener 3")}</div>
        <div class="card-desc">Stage-2 trend alignment + pullback / base-breakout trigger</div>
    </div>""", unsafe_allow_html=True)

st.divider()

# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------
def _style_direction(df: pd.DataFrame):
    if "Direction" not in df.columns:
        return df
    return df.style.map(
        lambda v: "color: #16c784; font-weight: 700" if v == "Long"
        else ("color: #ea3943; font-weight: 700" if v == "Short" else ""),
        subset=["Direction"],
    )


def _near_miss_expander(label: str, diag_key: str):
    d = None if diag is None else diag.get(diag_key)
    if d is not None and not d.empty:
        with st.expander(f"🔎 See closest near-misses for {label} (diagnostic view — not a bug checker, just transparency)"):
            st.caption("Each check shows whether that specific condition was true for this stock at scan time. "
                       "A stock needs (almost) all checks true to fire — this shows how close each stock got.")
            st.dataframe(d.head(15), use_container_width=True, hide_index=True)


def _render_screener_tab(screener_prefix: str, label: str, diag_key: str, explainer: str):
    sub = pd.DataFrame() if results is None else results[results["Screener"].str.startswith(screener_prefix)]

    if results is None:
        st.info("👈 Run a scan from the sidebar to see results here.")
        return

    if not sub.empty:
        st.dataframe(_style_direction(sub), use_container_width=True, hide_index=True)
    else:
        st.warning(f"No **{label}** setups fired in this scan. {explainer}")

    _near_miss_expander(label, diag_key)


def _render_reversal_tab():
    """Reversal gets a special side-by-side layout: Intraday-level setups
    (near a recent swing high/low) vs Swing/Pivot-level setups (near a
    Daily or Weekly pivot S/R) — shown as two slick columns."""
    if results is None:
        st.info("👈 Run a scan from the sidebar to see results here.")
        return

    sub = results[results["Screener"].str.startswith("Screener 1")]
    intraday_sub = sub[sub.get("Level Type") == "Intraday Swing Level"] if not sub.empty else sub
    swing_sub = sub[sub.get("Level Type") == "Daily/Weekly Pivot"] if not sub.empty else sub

    left, right = st.columns(2)
    with left:
        st.markdown("""<div class="screener-card card-momentum" style="margin-bottom:10px;">
            <div class="card-title">🕐 Intraday-Level Reversals</div>
            <div class="card-desc">Reversal near a recent 20-bar swing high/low</div>
        </div>""", unsafe_allow_html=True)
        if not intraday_sub.empty:
            st.dataframe(_style_direction(intraday_sub.drop(columns=["Level Type"])),
                         use_container_width=True, hide_index=True)
        else:
            st.caption("No intraday-level reversal setups fired.")

    with right:
        st.markdown("""<div class="screener-card card-swing" style="margin-bottom:10px;">
            <div class="card-title">📐 Swing / Pivot-Level Reversals</div>
            <div class="card-desc">Reversal near a Daily or Weekly Pivot S/R</div>
        </div>""", unsafe_allow_html=True)
        if not swing_sub.empty:
            st.dataframe(_style_direction(swing_sub.drop(columns=["Level Type"])),
                         use_container_width=True, hide_index=True)
        else:
            st.caption("No swing/pivot-level reversal setups fired.")

    if sub.empty:
        st.warning("No **Reversal** setups fired in this scan. This needs an HTM cross to happen on the "
                   "*current* candle, right at a support/resistance level — a rare, precise alignment.")

    _near_miss_expander("Reversal", "Reversal")


# ---------------------------------------------------------------------------
# TABS — always visible, regardless of scan outcome
# ---------------------------------------------------------------------------
tab1, tab2, tab3, tab_all = st.tabs([
    "🔄 Reversal", "⚡ Intraday Momentum", "📊 Swing", "📋 All Results"
])

with tab1:
    _render_reversal_tab()
with tab2:
    _render_screener_tab("Screener 2", "Intraday Momentum", "Intraday Momentum",
                          "This needs the daily trend, volume, HTM, and a breakout of yesterday's range to all align *today*.")
with tab3:
    _render_screener_tab("Screener 3", "Swing", "Swing",
                          "This needs 4 moving averages stacked and rising together, above the yearly VWAP — a strict 'healthy uptrend' filter.")

with tab_all:
    if results is None:
        st.info("👈 Run a scan from the sidebar to see results here.")
    elif results.empty:
        st.warning("No setups matched any screener in this scan. Check the near-miss tables in each tab above, "
                   "or try again after the next candle close / widen the universe size.")
    else:
        st.dataframe(_style_direction(results), use_container_width=True, hide_index=True)
        csv = results.to_csv(index=False).encode("utf-8")
        st.download_button("⬇️ Download CSV", csv, "nse_screener_results.csv", "text/csv",
                            use_container_width=True)
