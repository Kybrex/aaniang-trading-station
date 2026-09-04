"""One-click consolidated stock research for AANIANG V7."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable

import numpy as np
import pandas as pd
import yfinance as yf

from v3_features import load_snapshot, research_brief
from v4_features import copilot_answer
from v5_features import catalysts, dividend_intelligence, insider_activity, management_score, ownership
from v6_features import advanced_indicators, detect_patterns, load_history, support_resistance, technical_alerts, technical_score, trade_plan


def _safe(call: Callable[[], Any], default: Any) -> tuple[Any, str | None]:
    try:
        return call(), None
    except Exception as exc:
        return default, str(exc)[:180]


def ai_research_summary(snapshot: dict, technical_score_value: int, patterns: list[dict], alerts: list[str], management_value: int) -> dict[str, str]:
    """Create a grounded, explainable research synthesis from measured fields."""
    symbol = str(snapshot.get("Symbol") or "The company")
    risk = copilot_answer("What are the principal risks?", snapshot)
    valuation = copilot_answer("Is the valuation attractive?", snapshot)
    momentum = copilot_answer("How is momentum?", snapshot)
    quality_raw = snapshot.get("Quality"); quality = float(quality_raw) if quality_raw is not None else None
    gap = snapshot.get("Value gap")
    gap_text = f"{float(gap):.1f}%" if gap is not None else "unavailable"
    pattern_text = ", ".join(str(item.get("Pattern")) for item in patterns[:3]) or "No high-confidence chart pattern was detected"
    alert_text = "; ".join(alerts[:4]) or "No configured technical alert is active"
    if quality is None:
        stance = "Fundamental quality data was unavailable in this run, so the conclusion relies more heavily on price history and must be regenerated before fundamental decisions."
        valuation = "Valuation could not be assessed because current fundamental and analyst fields were not returned."
        risk = "Fundamental risk could not be assessed in this run; technical risk data remains available elsewhere in the report."
    elif quality >= 70 and technical_score_value >= 70:
        stance = "The measured quality and technical trend are both constructive, but entry price and downside risk still require review."
    elif quality >= 70:
        stance = "Business quality appears stronger than the current technical setup; patience and confirmation may be appropriate."
    elif technical_score_value >= 70:
        stance = "Momentum is stronger than the fundamental quality score, so the thesis depends more heavily on price action."
    else:
        stance = "Neither the quality nor technical score currently provides a strong quantitative confirmation."
    return {
        "Executive view": f"{symbol} has a quality score of {f'{quality:.0f}/100' if quality is not None else 'unavailable'}, technical score of {technical_score_value}/100, management score of {f'{management_value}/100' if management_value is not None else 'unavailable'}, and analyst value gap of {gap_text}. {stance}",
        "Valuation view": valuation,
        "Risk view": risk,
        "Technical view": f"{momentum} Pattern scan: {pattern_text}. Active signals: {alert_text}.",
        "Research conclusion": "Use this synthesis as a research shortcut, not a recommendation. Confirm the thesis against current filings, earnings guidance, cash-flow durability, competitive risks, and a predefined margin of safety.",
    }


def _professional_sections(snapshot: dict, technical: pd.DataFrame, levels: pd.DataFrame, technical_value: int, management_value: int, peers: pd.DataFrame) -> dict:
    price = float(snapshot.get("Price") or 0); quality = float(snapshot["Quality"]) if snapshot.get("Quality") is not None else None
    growth = float(snapshot.get("Revenue growth") or 0); debt = float(snapshot.get("Debt/Equity") or 0)
    beta = float(snapshot.get("Beta") or 1); value_gap = float(snapshot.get("Value gap") or 0)
    valuation_score = float(np.clip(50 + value_gap * 2, 0, 100))
    growth_score = float(np.clip(50 + growth * 2, 0, 100))
    financial_score = float(np.clip(80 - max(debt - 50, 0) * .35 + (10 if float(snapshot.get("Current ratio") or 0) >= 1 else 0), 0, 100))
    risk_score = float(np.clip(100 - abs(beta - 1) * 35 - max(debt - 100, 0) * .15, 0, 100))
    components = pd.DataFrame([
        {"Component":"Business quality","Score":quality,"Weight %":25}, {"Component":"Technical trend","Score":technical_value,"Weight %":20},
        {"Component":"Management","Score":management_value,"Weight %":15}, {"Component":"Valuation","Score":valuation_score,"Weight %":15},
        {"Component":"Growth","Score":growth_score,"Weight %":10}, {"Component":"Financial health","Score":financial_score,"Weight %":10},
        {"Component":"Risk profile","Score":risk_score,"Weight %":5},
    ])
    valid = components.dropna(subset=["Score"])
    overall = int(round((valid.Score * valid["Weight %"]).sum() / valid["Weight %"].sum())) if not valid.empty else 0
    classification = "Investigate" if overall >= 75 else "Watch" if overall >= 60 else "Wait" if overall >= 45 else "Avoid"
    base_growth = float(np.clip(growth, -10, 25)); base_pe = float(snapshot.get("Forward P/E") or snapshot.get("Trailing P/E") or 20)
    scenario_rows = []
    for name, adjustment, multiple_change in (("Bear",-6,-.25),("Base",0,0),("Bull",6,.25)):
        scenario_growth = float(np.clip(base_growth+adjustment,-20,35)); estimated = price * (1+scenario_growth/100)**3 * max(.4, 1+multiple_change)
        scenario_rows.append({"Scenario":name,"3Y growth assumption %":scenario_growth,"Exit P/E":base_pe*(1+multiple_change),"Estimated price":estimated,"Return %":(estimated/price-1)*100 if price else 0})
    returns = technical.Close.pct_change().dropna() if not technical.empty else pd.Series(dtype=float)
    drawdown = (technical.Close / technical.Close.cummax() - 1).min()*100 if not technical.empty else 0
    volatility = returns.std()*np.sqrt(252)*100 if not returns.empty else 0
    risk = pd.DataFrame([{"Beta":beta,"Annualized volatility %":volatility,"Maximum drawdown %":drawdown,"Debt/Equity":debt,"Risk score":risk_score,"Risk level":"Low" if risk_score>=75 else "Medium" if risk_score>=50 else "High"}])
    support = levels.loc[levels.Type.eq("Support"),"Level"].max() if not levels.empty and levels.Type.eq("Support").any() else price*.92
    resistance = levels.loc[levels.Type.eq("Resistance"),"Level"].min() if not levels.empty and levels.Type.eq("Resistance").any() else price*1.15
    stop = float(support)*.985; target = float(resistance); plan = trade_plan(price, stop, target, 25000, 1) if price else {}
    plan_frame = pd.DataFrame([{"Entry":price,"Stop":stop,"Target":target,**plan}])
    analyst = pd.DataFrame([{"Current price":price,"Mean target":snapshot.get("Analyst target"),"Implied upside %":value_gap,"Trailing P/E":snapshot.get("Trailing P/E"),"Forward P/E":snapshot.get("Forward P/E"),"Estimate signal":"Positive" if value_gap>=10 else "Neutral" if value_gap>=0 else "Cautious"}])
    checks = [
        ("Business quality",quality is not None and quality>=70,f"Quality {quality:.0f}/100" if quality is not None else "Quality unavailable"), ("Positive growth",growth>0,f"Revenue growth {growth:.1f}%"),
        ("Financial health",financial_score>=60,f"Financial score {financial_score:.0f}/100"), ("Management",management_value is not None and management_value>=70,f"Management {management_value}/100" if management_value is not None else "Management unavailable"),
        ("Valuation",value_gap>=10,f"Analyst value gap {value_gap:.1f}%"), ("Technical trend",technical_value>=70,f"Technical {technical_value}/100"),
        ("Controlled risk",risk_score>=60,f"Risk score {risk_score:.0f}/100"), ("Reward/risk",float(plan.get("Reward/risk",0))>=2,f"Reward/risk {float(plan.get('Reward/risk',0)):.2f}R"),
    ]
    checklist = pd.DataFrame([{"Check":name,"Result":"PASS" if passed else "REVIEW","Evidence":evidence} for name,passed,evidence in checks])
    peer_columns = [c for c in ["Symbol","Company","Quality","Forward P/E","Revenue growth","Operating margin","Value gap","6M return"] if c in peers]
    peer_view = peers[peer_columns].head(12).copy() if peer_columns else pd.DataFrame()
    return {"overall_score":overall,"classification":classification,"score_components":components,"valuation_scenarios":pd.DataFrame(scenario_rows),"risk_dashboard":risk,"peer_comparison":peer_view,"analyst_estimates":analyst,"trade_plan":plan_frame,"checklist":checklist}


def complete_stock_research(symbol: str, fmp_key: str = "", universe: pd.DataFrame | None = None) -> dict:
    """Run all ticker-only research modules and return a report-ready bundle."""
    symbol = symbol.strip().upper()
    snapshot, snapshot_error = _safe(lambda: load_snapshot(symbol, fmp_key), None)
    if not snapshot:
        raise ValueError(f"No company data was returned for {symbol}.")

    history, history_error = _safe(lambda: load_history(symbol, "2y"), pd.DataFrame())
    technical = advanced_indicators(history) if not history.empty else history
    score_result, score_error = _safe(lambda: technical_score(technical), (0, []))
    levels, levels_error = _safe(lambda: support_resistance(technical), pd.DataFrame())
    patterns, patterns_error = _safe(lambda: detect_patterns(technical), [])
    alerts, alerts_error = _safe(lambda: technical_alerts(technical), [])
    management, management_error = _safe(lambda: management_score(snapshot), (0, []))
    if not snapshot.get("Fundamentals available", True):
        management = (None, ["Management score unavailable because fundamental fields were not returned."])
    dividend, dividend_error = _safe(lambda: dividend_intelligence(symbol), (pd.DataFrame(), {}))
    insiders, insider_error = _safe(lambda: insider_activity(symbol), pd.DataFrame())
    holder_data, ownership_error = _safe(lambda: ownership(symbol), (pd.DataFrame(), pd.DataFrame(), pd.DataFrame()))
    catalyst_data, catalyst_error = _safe(lambda: catalysts(symbol), (pd.DataFrame(), pd.DataFrame()))
    ai_summary = ai_research_summary(snapshot, score_result[0], patterns, alerts, management[0])
    peers = universe if isinstance(universe, pd.DataFrame) else pd.DataFrame()
    if not peers.empty and "Sector" in peers:
        peers = peers[(peers.Sector == snapshot.get("Sector")) | (peers.Symbol == symbol)].copy()
    professional = _professional_sections(snapshot, technical, levels, score_result[0], management[0], peers)
    trends, trend_error = _safe(lambda: _financial_trends(symbol), pd.DataFrame())
    if trend_error: errors["Financial trends"] = trend_error

    errors = {
        "Company snapshot": snapshot_error, "Price history": history_error,
        "Technical score": score_error, "Support/resistance": levels_error,
        "Pattern detection": patterns_error, "Technical alerts": alerts_error,
        "Management quality": management_error, "Dividend intelligence": dividend_error,
        "Insider activity": insider_error, "Ownership": ownership_error,
        "Catalysts": catalyst_error,
    }
    return {
        "symbol": symbol,
        "generated_at": datetime.now(timezone.utc),
        "snapshot": snapshot,
        "brief": research_brief(snapshot),
        "ai_summary": ai_summary,
        "technical_score": score_result[0],
        "technical_checks": score_result[1],
        "technical_history": technical.tail(252).copy(),
        "levels": levels,
        "patterns": patterns,
        "alerts": alerts,
        "management_score": management[0],
        "management_reasons": management[1],
        "dividend_history": dividend[0],
        "dividend_metrics": dividend[1],
        "insiders": insiders,
        "institutions": holder_data[0],
        "funds": holder_data[1],
        "major_holders": holder_data[2],
        "calendar": catalyst_data[0],
        "news": catalyst_data[1],
        "errors": {name: error for name, error in errors.items() if error},
        "financial_trends": trends,
        **professional,
        "input_required": [
            "Earnings Call Analyzer - transcript required",
            "Portfolio Health and Optimizer - holdings required",
            "Paper Trading and Tax Center - transaction ledger required",
            "Options Analytics - expiration and contract selection required",
            "Relative Strength and Market Breadth - comparison universe required",
        ],
    }


def _financial_trends(symbol: str) -> pd.DataFrame:
    ticker = yf.Ticker(symbol); income = ticker.financials; cash = ticker.cashflow; balance = ticker.balance_sheet
    columns = sorted(set(income.columns).union(cash.columns).union(balance.columns))[-5:]
    rows = []
    mapping = [("Revenue",income,"Total Revenue"),("Net income",income,"Net Income"),("Operating cash flow",cash,"Operating Cash Flow"),("Free cash flow",cash,"Free Cash Flow"),("Total debt",balance,"Total Debt")]
    for date in columns:
        row={"Year":getattr(date,"year",str(date))}
        for label,frame,key in mapping: row[label]=frame.at[key,date] if key in frame.index and date in frame else None
        rows.append(row)
    return pd.DataFrame(rows).sort_values("Year")

