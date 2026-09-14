"""Readable market context and tools for the current scan."""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, ROUND_FLOOR
from html import escape
import math
import pandas as pd
import streamlit as st


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def market_snapshot() -> dict:
    from data import download_batch, symbol_frame, last_number
    from indicators import add_indicators

    raw = download_batch(["SPY", "QQQ", "^VIX"], period="1y", timeout=15)
    checked = utc_now()
    cards = []
    for symbol, label in [("SPY", "S&P 500"), ("QQQ", "Nasdaq 100"), ("^VIX", "VIX")]:
        frame = symbol_frame(raw, symbol)
        item = dict(symbol=symbol, label=label, value=None, state="Unavailable",
                    data_date="Unavailable", checked=checked, reason="No usable price history returned.")
        if not frame.empty:
            item["data_date"] = pd.Timestamp(frame.index[-1]).date().isoformat()
            close = last_number(frame.Close.iloc[-1])
            if close is not None and math.isfinite(close) and close > 0:
                if symbol == "^VIX":
                    item.update(value=close, state="Elevated" if close >= 22 else "Calm",
                                reason=f"VIX is {close:.1f}. This app labels volatility elevated at 22 or above, and calm below 22.")
                elif len(frame) < 200:
                    item["reason"] = "At least 200 daily bars are needed to classify the trend."
                else:
                    sma = last_number(add_indicators(frame).SMA200.iloc[-1])
                    if sma is not None and math.isfinite(sma) and sma > 0:
                        state = "Risk-on" if close > sma else "Risk-off"
                        relation = "above" if close > sma else "at or below"
                        item.update(value=close, state=state,
                                    reason=f"{symbol} price {close:.2f} is {relation} its 200-day average of {sma:.2f}. "
                                           f"The app uses this rule for {state.lower()}.")
        cards.append(item)
    return {"checked": checked, "cards": cards}


def position_size(entry, stop, amount, equity, risk_pct, max_position_pct, side) -> dict:
    """Whole shares from planned notional; calculate a separate risk-limited size."""
    values = [entry, stop, amount, equity, risk_pct, max_position_pct]
    try:
        if not all(math.isfinite(float(x)) for x in values):
            raise ValueError
        entry, stop, amount, equity, risk_pct, max_position_pct = map(lambda x: Decimal(str(x)), values)
    except (TypeError, ValueError, ArithmeticError):
        raise ValueError("Enter finite numbers for the price, stop, amount and limits.") from None
    if entry <= 0 or stop <= 0 or amount < 0 or equity <= 0 or not 0 < risk_pct <= 100 or not 0 < max_position_pct <= 100:
        raise ValueError("Prices and limits must be positive; the planned amount can be zero.")
    if side not in ("LONG", "SHORT"):
        raise ValueError("A LONG or SHORT signal is required.")
    if (side == "LONG" and stop >= entry) or (side == "SHORT" and stop <= entry):
        raise ValueError("The stop must be below entry for LONG and above entry for SHORT.")
    per_share = abs(entry - stop)
    whole = lambda value: int(value.to_integral_value(rounding=ROUND_FLOOR))
    shares = whole(amount / entry)
    budget = equity * risk_pct / 100
    cap = equity * max_position_pct / 100
    limited = min(shares, whole(budget / per_share), whole(cap / entry))
    return dict(shares=shares, notional=float(shares * entry), loss=float(shares * per_share),
                unused=float(amount - shares * entry), risk_per_share=float(per_share),
                budget=float(budget), cap=float(cap), limited_shares=limited,
                limited_notional=float(limited * entry), limited_loss=float(limited * per_share))


def signal_reasons(row) -> list[str]:
    required = ["EMA20", "EMA50", "SMA200", "EMA20 prior", "ATR14", "Volume ratio",
                "Session open", "Session high", "Session low"]
    if any(pd.isna(row.get(key)) for key in required):
        return ["Run Scan market again to capture the indicator evidence for this candidate."]
    long = row["Signal"] == "LONG"
    relation, slope = ("above", "rising") if long else ("below", "falling")
    reasons = [
        f"Trend: price {row['Entry']:.2f} is {relation} the 200-day average {row['SMA200']:.2f}. "
        f"The 20-day exponential average ({row['EMA20']:.2f}) is {relation} the 50-day "
        f"({row['EMA50']:.2f}) and {slope} versus ten sessions ago ({row['EMA20 prior']:.2f})."
    ]
    if row["Setup"] == "Breakout":
        level = row["Resistance"] if long else row["Support"]
        reasons.append(f"Breakout: price crossed {relation} the prior 20-session "
                       f"{'high' if long else 'low'} ({level:.2f}), by no more than 0.75 × "
                       f"average true range. Volume was {row['Volume ratio']:.2f}× its 20-session average "
                       f"(minimum 0.80×).")
    else:
        extreme = row["Session low"] if long else row["Session high"]
        reasons.append(f"Pullback: the session {'low' if long else 'high'} ({extreme:.2f}) touched or crossed "
                       f"the 20-day exponential average; price finished {relation} that average "
                       f"and {relation} the session open ({row['Session open']:.2f}).")
    reasons.append(f"Momentum: {row['20D Momentum']:+.2f}% over 20 sessions and "
                   f"{row['60D Momentum']:+.2f}% over 60 sessions. Momentum in the signal's direction adds points.")
    reasons.append(f"Stop: 1.5 × 14-day average true range ({row['ATR14']:.2f}), "
                   f"giving {row['Risk/Share']:.2f} risk per share.")
    return reasons


def render_market(snapshot: dict) -> None:
    st.markdown("""<style>
    .aa-market-card {background:#fff;border:1px solid #ccd4dc;border-top:4px solid var(--risk-color);
      border-radius:8px;padding:18px;min-height:185px;box-sizing:border-box;}
    .aa-market-label {font-size:1rem;color:#526478;}
    .aa-market-value {font-size:2.1rem;font-weight:800;color:#172b4d;overflow-wrap:anywhere;}
    .aa-market-state {display:inline-block;font-weight:750;font-size:1.15rem;
      color:var(--risk-color);background:var(--risk-bg);padding:4px 12px;border-radius:6px;
      white-space:nowrap;margin:6px 0;}
    .aa-market-date {font-size:.8rem;color:#526478;margin-top:8px;}
    </style>""", unsafe_allow_html=True)
    palette = {"Risk-on": ("#11613d", "#e6f4eb"), "Risk-off": ("#a12626", "#fceaea"),
               "Calm": ("#11613d", "#e6f4eb"), "Elevated": ("#8a4b00", "#fff0d5"),
               "Unavailable": ("#526478", "#edf0f3")}
    for column, card in zip(st.columns(3), snapshot["cards"]):
        with column:
            color, bg = palette[card["state"]]
            value = "—" if card["value"] is None else format(card["value"], ".1f" if card["symbol"] == "^VIX" else ".2f")
            proxy = f" · {card['symbol']} ETF" if card["symbol"] != "^VIX" else ""
            st.markdown(f"""<div class="aa-market-card" style="--risk-color:{color};--risk-bg:{bg}">
              <div class="aa-market-label">{escape(card['label'] + proxy)}</div>
              <div class="aa-market-value">{value}</div>
              <div class="aa-market-state">{escape(card['state'])}</div>
              <div class="aa-market-date">Price data: {escape(card['data_date'])}</div>
            </div>""", unsafe_allow_html=True)
            with st.expander(f"Why this signal? · {card['label']}"):
                st.write(card["reason"])
    st.caption(f"Market data last checked: {snapshot['checked']}. Daily bars may include an unfinished session; "
               "the date above is the price-data date, not a live quote timestamp.")


def render_comparison(results: pd.DataFrame) -> None:
    st.subheader("Compare candidates")
    options = results.Symbol.tolist()
    key = "scan_compare_symbols"
    if key in st.session_state:
        st.session_state[key] = [s for s in st.session_state[key] if s in options][:3]
    else:
        st.session_state[key] = options[:3]
    chosen = st.multiselect("Choose up to three candidates", options,
                            max_selections=3, key=key)
    if len(chosen) < 2:
        st.info("Select two or three candidates to compare." if len(options) >= 2
                else "This scan found one candidate. Run a broader scan to compare more.")
        return
    fields = ["Data date", "Score", "Signal", "Setup", "20D Momentum", "60D Momentum",
              "Entry", "Stop", "Risk/Share", "RS vs SPY", "Earnings"]
    comparison = results.set_index("Symbol").loc[chosen, fields].T.copy()
    for symbol in chosen:
        for field in fields:
            value = comparison.at[field, symbol]
            if pd.isna(value):
                text = "Unavailable"
            elif field in ("Entry", "Stop", "Risk/Share"):
                text = f"${float(value):,.2f}"
            elif "Momentum" in field:
                text = f"{float(value):+.2f}%"
            elif field == "RS vs SPY":
                text = f"{float(value):+.2f} pp"
            else:
                text = str(value)
            comparison.at[field, symbol] = text
    st.dataframe(comparison.rename_axis("Measure").reset_index(), hide_index=True, width="stretch")
    st.caption("RS vs SPY is the 20-session return difference in percentage points. Scores rank setups; they are not win probabilities.")


def render_candidate(row, equity: float, risk_pct: float, max_position_pct: float) -> None:
    symbol = str(row["Symbol"])
    left, right = st.columns([1, 1])
    with left:
        st.subheader(f"Why this signal? · {symbol}")
        for reason in signal_reasons(row):
            st.write(reason)
        keys = ["Trend points", "Momentum points", "Volume points", "Setup points", "Extension penalty"]
        if all(pd.notna(row.get(k)) for k in keys):
            values = [float(row[k]) * (-1 if k == "Extension penalty" else 1) for k in keys]
            st.dataframe(pd.DataFrame({"Score component": keys, "Points": values}),
                         hide_index=True, width="stretch",
                         column_config={"Points": st.column_config.NumberColumn(format="%.2f")})
            st.caption(f"Total is rounded to a whole number and capped at 100. This candidate: {int(row['Score'])}/100.")
        if row.get("Earnings", "Unknown") == "Unknown":
            st.caption("Earnings date is unknown; it has not been confirmed safe.")
    with right:
        st.subheader(f"Position-size calculator · {symbol}")
        st.caption(f"{row['Signal']} · Entry ${row['Entry']:.2f} · Stop ${row['Stop']:.2f} · Price data: {row['Data date']}")
        amount = st.number_input("Planned position amount ($)", min_value=0.0,
                                 value=float(equity * max_position_pct / 100), step=100.0,
                                 key=f"scan_amount_{symbol}",
                                 help="Position value at entry. For a short, this is not the broker's margin requirement.")
        try:
            calc = position_size(row["Entry"], row["Stop"], amount, equity, risk_pct, max_position_pct, row["Signal"])
        except ValueError as exc:
            st.error(str(exc))
            return
        a, b = st.columns(2)
        a.metric("Planned shares", f"{calc['shares']:,}")
        b.metric("Estimated loss at stop", f"${calc['loss']:,.2f}")
        st.caption(f"Position value: ${calc['notional']:,.2f} · Unallocated amount: ${calc['unused']:,.2f}")
        if calc["loss"] > calc["budget"]:
            st.warning(f"Planned loss exceeds your ${calc['budget']:,.2f} per-trade risk budget.")
        if calc["notional"] > calc["cap"]:
            st.warning(f"Planned position exceeds your ${calc['cap']:,.2f} position-value limit.")
        st.markdown(f"**Within your current limits: {calc['limited_shares']:,} shares**")
        st.write(f"Position value ${calc['limited_notional']:,.2f} · Estimated loss at stop ${calc['limited_loss']:,.2f}")
        st.caption(f"Uses account equity ${equity:,.2f}, risk budget {risk_pct:g}% and position cap {max_position_pct:g}%. "
                   "Existing positions are not included in this calculation.")
        st.caption("Assumes a fill at the stop price; gaps, slippage, fees and short-borrow costs can increase loss.")
