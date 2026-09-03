# AANIANG Trading Station

A standalone Streamlit research app that scans US equities and supports both swing-trading and long-term investment research. It is for education and research, not investment advice.

## V2 decision center

The V2 interface installs twelve connected modules:

1. Yahoo daily data with an optional Alpha Vantage fallback for single-symbol research.
2. Backtests with expectancy, win rate, profit factor, total R, drawdown, slippage allowance, equity curve, and a 70/30 sample label.
3. Weekly, daily, and four-hour trend alignment.
4. Base breakout, breakdown, EMA20 pullback, volatility contraction, relative-strength breakout, post-event gap, and reversal checks.
5. Portfolio heat, sector concentration, position correlation, and risk per position.
6. Downloadable bracket/OCO order plans. These plans do not transmit broker orders.
7. Telegram/SMTP alert delivery with duplicate-transition protection and an optional scheduled worker.
8. Journal screenshots and analytics by setup, P/L, R multiple, win rate, and profit factor.
9. Explainable quality, growth, valuation, profitability, leverage, and available annual financial history.
10. Bear/base/bull discounted-cash-flow scenarios.
11. Swing/investment positions, country, currency, dividends, target weights, and rebalance research actions.
12. Symbol search, company/manual calendars, printable PDF, and a complete Excel workbook.

The external score labels and rebalance actions are research classifications, not personalized recommendations. Verify all prices, events, and order details with your broker before acting.

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

## Optional secrets

Copy `.streamlit/secrets.example.toml` to `.streamlit/secrets.toml` for local use, or enter the same names in Streamlit Cloud **Settings → Secrets**. Leave unused services blank. Never commit real keys.

- `ALPHAVANTAGE_API_KEY`: optional daily single-symbol fallback and enhanced symbol search.
- `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID`: Telegram alerts.
- `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, and `ALERT_EMAIL`: email alerts.

To evaluate alerts while the Streamlit page is closed, configure Windows Task Scheduler or cron to run `python alert_worker.py` periodically on an always-on machine. Streamlit cannot run background work while a free app is asleep. The worker sends only a new transition into `TRIGGERED`, not the same condition repeatedly.

## Reliability and validation

Batch downloads use timeouts and empty/bad symbols are skipped. `data.symbol_frame()` explicitly handles yfinance's MultiIndex and one-ticker output shapes. `data.last_number()` extracts a scalar safely before any conversion, avoiding `float(Series)` errors.

Before running the UI, validate source and imports with:

    python -m compileall .
    python -c "import app, advanced, investor, portfolio, reporting; print('Imports passed')"
    python -m unittest discover -s tests -v

For a basic scanner smoke test (uses live Yahoo data):

    python -c "from scanner import ScanSettings,scan_market; r,n=scan_market(['AAPL','MSFT','NVDA'],ScanSettings('Both',0,10,1,1,25000,1,3),lambda *x:None); print(r[['Symbol','Score','Signal']]); print('Skipped:',n)"

Yahoo Finance is an unofficial data source and can throttle or occasionally omit symbols. The app skips failed symbols, limits the default scan to 250 symbols, and stops early after repeated empty batches rather than hanging indefinitely. The Alpha Vantage fallback is intended for selected-symbol daily research, not thousands of fallback requests during a broad scan.
\n\n## AANIANG company intelligence V2\n\nEnter a ticker to open an explainable company-research workspace. It includes a 0–100 quality score with category-level evidence, annual revenue/earnings/cash-flow history, five-year price history, company and valuation metrics, and an adjustable intrinsic-value laboratory. Bear, base, and bull presets combine available DCF/free-cash-flow, earnings-multiple, book-value, and analyst-consensus estimates. Missing Yahoo fields receive no quality points and unavailable valuation methods are omitted rather than invented.\n