"""One-click consolidated stock research for AANIANG V7."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable

import pandas as pd

from v3_features import load_snapshot, research_brief
from v5_features import catalysts, dividend_intelligence, insider_activity, management_score, ownership
from v6_features import advanced_indicators, detect_patterns, load_history, support_resistance, technical_alerts, technical_score


def _safe(call: Callable[[], Any], default: Any) -> tuple[Any, str | None]:
    try:
        return call(), None
    except Exception as exc:
        return default, str(exc)[:180]


def complete_stock_research(symbol: str, fmp_key: str = "") -> dict:
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
    dividend, dividend_error = _safe(lambda: dividend_intelligence(symbol), (pd.DataFrame(), {}))
    insiders, insider_error = _safe(lambda: insider_activity(symbol), pd.DataFrame())
    holder_data, ownership_error = _safe(lambda: ownership(symbol), (pd.DataFrame(), pd.DataFrame(), pd.DataFrame()))
    catalyst_data, catalyst_error = _safe(lambda: catalysts(symbol), (pd.DataFrame(), pd.DataFrame()))

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
        "input_required": [
            "Earnings Call Analyzer - transcript required",
            "Portfolio Health and Optimizer - holdings required",
            "Paper Trading and Tax Center - transaction ledger required",
            "Options Analytics - expiration and contract selection required",
            "Relative Strength and Market Breadth - comparison universe required",
        ],
    }

