# AANIANG Trading Station

A standalone Streamlit research app that scans US equities with Yahoo Finance and ranks LONG or SHORT swing-trading setups. It is for education and research, not investment advice.

## Windows setup

Open PowerShell in this folder and run:

    py -m venv .venv
    .\.venv\Scripts\Activate.ps1
    python -m pip install --upgrade pip
    pip install -r requirements.txt
    streamlit run app.py

If PowerShell blocks activation, run this once in the same PowerShell window, then activate again:

    Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass

Open the local address displayed by Streamlit (normally http://localhost:8501).

## What it scans

The default broad universe is Nasdaq's US-listed screener endpoint (up to 5,000 listed symbols). If that endpoint is unavailable, the app automatically uses the included liquid-US-stock fallback list. Yahoo Finance is used for all OHLCV price data; Internet access is required.

The initial broad scan can take several minutes. Start with the liquid fallback and 50–250 symbols. The scanner pauses between Yahoo batches and stops safely after two consecutive empty batches instead of appearing frozen during a rate limit.

## Trading workspace additions

The upgraded app includes market-regime context (SPY, QQQ, and VIX), 20-day relative strength versus SPY, a best-effort earnings-date safety filter, validated breakout and EMA-pullback labels, 20-day support/resistance, volume under the chart, capped position sizing and portfolio-heat guidance, a local watchlist, local alert reference conditions, a trade journal, and a transparent selected-symbol historical backtest. Histories downloaded by the scanner are reused for charts and research instead of immediately requesting the same Yahoo data again. Local watchlist and journal data is saved under `user_data` beside the app. Alerts are visible when the app is open; they are not background notifications or broker orders.

## Setup scoring

Each setup scores 0–100 from trend, EMA20 slope, 20/60-day momentum, relative volume, and setup quality. A breakout must actually cross the prior 20-day high/low with adequate volume and without being excessively extended. An EMA pullback must touch the EMA20 and close back in the trend direction. Plain trend alignment is no longer mislabeled as a setup. Entry is the latest adjusted daily close, not a guaranteed live quote; stop is 1.5 × ATR(14), and targets are 2R/3R. Position size equals account-risk dollars divided by risk per share, rounded down.

## Reliability and validation

Batch downloads use timeouts and empty/bad symbols are skipped. `data.symbol_frame()` explicitly handles yfinance's MultiIndex and one-ticker output shapes. `data.last_number()` extracts a scalar safely before any conversion, avoiding `float(Series)` errors.

Before running the UI, validate source and imports with:

    python -m compileall app.py data.py indicators.py scanner.py charts.py universe.py
    python -c "import app, scanner, data, charts, universe; print('Imports passed')"
    python -m unittest discover -s tests -v

For a basic scanner smoke test (uses live Yahoo data):

    python -c "from scanner import ScanSettings,scan_market; r,n=scan_market(['AAPL','MSFT','NVDA'],ScanSettings('Both',0,10,1,1,25000,1,3),lambda *x:None); print(r[['Symbol','Score','Signal']]); print('Skipped:',n)"

Yahoo Finance is an unofficial data source and can throttle or occasionally omit symbols. The app skips failed symbols, limits the default scan to 250 symbols, and stops early after repeated empty batches rather than hanging indefinitely.
