# 📈 VPA + HTM Screener

A free, forever, NSE F&O stock screener implementing three strategies from your
VPA/HTM playbook:

1. **Reversal** — Stopping Volume candle at support/resistance, confirmed by the HTM indicator on the 75-minute chart.
2. **Intraday Momentum** — Trend-following breakout above/below yesterday's High/Low, confirmed by HTM.
3. **Swing (long-only)** — Stage-2 trend alignment (Price > 20 EMA > 50 SMA > 100 SMA > 200 SMA, all sloped up, above YTD Anchored VWAP), with two trigger setups: Pullback and Base Breakout.

No broker login is required — data comes free from Yahoo Finance. This means
**zero ongoing cost, forever**, and no daily token refresh hassle.

---

## 🗂 What's in this folder

| File | What it does |
|---|---|
| `app.py` | The dashboard you actually open in your browser |
| `indicators.py` | The math: pivots, Anchored VWAP, HTM indicator, candlestick patterns |
| `data_fetch.py` | Downloads price data for Daily/75m/15m/5m timeframes |
| `screeners.py` | The 3 screening strategies |
| `fno_list.py` | The list of NSE F&O stocks to scan |
| `requirements.txt` | The list of Python add-ons the app needs |

---

## 🖥️ PART 1 — Run it on your own computer (5 minutes)

**Step 1 — Install Python** (skip if you already have it)
- Go to https://www.python.org/downloads/
- Download and install the latest version.
- **Important:** On the first installer screen, tick the box that says **"Add Python to PATH"** before clicking Install.

**Step 2 — Download this project**
- Save all the files above into one folder on your computer, e.g. `Documents/vpa-htm-screener`.

**Step 3 — Open a terminal in that folder**
- Windows: open the folder, click the address bar, type `cmd`, press Enter.
- Mac: right-click the folder → "New Terminal at Folder" (or open Terminal and `cd` into it).

**Step 4 — Install the required add-ons** (one-time)
```
pip install -r requirements.txt
```

**Step 5 — Launch the app**
```
streamlit run app.py
```
A browser tab will open automatically at `http://localhost:8501` with your dashboard.

**Step 6 — Use it**
- In the left sidebar, choose how many stocks to scan (start with 80).
- Click **"Run Scan Now."**
- Wait for the progress bar (downloading ~80–200 stocks takes 1–3 minutes).
- Results appear in tabs: Reversal, Intraday Momentum, Swing, and All Results.
- Click **Download CSV** any time to save the results.

---

## ☁️ PART 2 — Put it online for free, forever (so you can open it from your phone too)

This uses **Streamlit Community Cloud** — Anthropic and Streamlit have no
connection, this is just a genuinely free hosting service made for exactly
this kind of app.

**Step 1 — Create a free GitHub account** at https://github.com (skip if you have one).

**Step 2 — Create a new repository**
- Click the **+** icon top-right → "New repository."
- Name it `vpa-htm-screener`, keep it Public, click **Create repository**.

**Step 3 — Upload your files**
- On the new repo page, click **"uploading an existing file."**
- Drag in all 6 files listed above (app.py, indicators.py, data_fetch.py, screeners.py, fno_list.py, requirements.txt).
- Click **Commit changes**.

**Step 4 — Deploy on Streamlit Cloud**
- Go to https://share.streamlit.io and sign in with your GitHub account.
- Click **"Create app"** → choose your `vpa-htm-screener` repo → set the main file to `app.py`.
- Click **Deploy**. Wait 1–2 minutes.
- You'll get a permanent free link like `https://yourname-vpa-htm-screener.streamlit.app` — open this from your phone or any computer, any time, for free.

---

## 💡 Ideas to add later (just ask, I'll build any of these)

- **Telegram alert** the moment a new setup appears, so you don't have to keep the tab open.
- **"Top Setup of the Day"** card — one ranked, highlighted best trade instead of scrolling a list.
- **Signal history log** — auto-save every hit to a CSV/Google Sheet so you can track your win rate over time.
- **Auto-refresh** every 15/75 minutes during market hours without clicking the button.
- **Fyers live data** as an optional upgrade for slightly faster/more accurate intraday prices (adds a daily login step).

---

## ⚠️ A note on the numbers

This tool is for **idea generation and screening only** — it highlights stocks
that match a technical pattern. It is not investment advice, and it can and
will produce false signals. Always confirm on your own chart and manage risk
before taking a trade.
