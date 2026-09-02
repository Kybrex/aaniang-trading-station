"""Explainable company fundamentals, valuation, comparison, and event research."""
from __future__ import annotations

from datetime import datetime, timezone
import math
import pandas as pd
import requests
import yfinance as yf


def number(value: object) -> float | None:
    try:
        result=float(value); return result if math.isfinite(result) else None
    except (TypeError,ValueError):return None


def fundamental_snapshot(symbol: str) -> dict:
    try: info=yf.Ticker(symbol).get_info()
    except Exception:return {"Symbol":symbol,"Status":"Unavailable"}
    roe=number(info.get("returnOnEquity")); margin=number(info.get("operatingMargins")); debt=number(info.get("debtToEquity")); growth=number(info.get("revenueGrowth")); earnings=number(info.get("earningsGrowth")); fcf=number(info.get("freeCashflow")); cap=number(info.get("marketCap")); price=number(info.get("currentPrice")) or number(info.get("regularMarketPrice")); shares=number(info.get("sharesOutstanding")); cash=number(info.get("totalCash")) or 0; total_debt=number(info.get("totalDebt")) or 0
    quality=(25 if roe and roe>=.20 else 15 if roe and roe>=.12 else 0)+(25 if margin and margin>=.18 else 15 if margin and margin>=.10 else 0)+(25 if debt is not None and debt<=100 else 12 if debt is not None and debt<=200 else 0)+(25 if fcf and fcf>0 else 0)
    growth_score=(50 if growth and growth>=.15 else 30 if growth and growth>=.07 else 0)+(50 if earnings and earnings>=.15 else 30 if earnings and earnings>=.07 else 0)
    pe=number(info.get("trailingPE")); forward_pe=number(info.get("forwardPE")); ev_ebitda=number(info.get("enterpriseToEbitda")); fcf_yield=(fcf/cap*100) if fcf and cap else None
    valuation=(35 if pe and pe<20 else 20 if pe and pe<30 else 5)+(30 if forward_pe and forward_pe<20 else 15 if forward_pe and forward_pe<30 else 5)+(20 if ev_ebitda and ev_ebitda<15 else 10 if ev_ebitda and ev_ebitda<25 else 0)+(15 if fcf_yield and fcf_yield>=4 else 8 if fcf_yield and fcf_yield>=2 else 0)
    classification="ADD RESEARCH" if quality>=70 and growth_score>=60 and valuation>=55 else "HOLD / WATCH" if quality>=55 else "WATCH / REDUCE RISK"
    return {"Symbol":symbol,"Company":info.get("longName",symbol),"Sector":info.get("sector","Unknown"),"Country":info.get("country","Unknown"),"Currency":info.get("currency","Unknown"),"Price":price,"Market cap":cap,"Revenue growth %":growth*100 if growth is not None else None,"Earnings growth %":earnings*100 if earnings is not None else None,"ROE %":roe*100 if roe is not None else None,"Operating margin %":margin*100 if margin is not None else None,"Debt/Equity":debt,"Free cash flow":fcf,"FCF yield %":fcf_yield,"Trailing P/E":pe,"Forward P/E":forward_pe,"EV/EBITDA":ev_ebitda,"Quality score":quality,"Growth score":growth_score,"Valuation score":valuation,"Research classification":classification,"Dividend yield %":(number(info.get("dividendYield")) or 0)*100,"Shares":shares,"Net debt":total_debt-cash,"Status":"Available","Updated":datetime.now(timezone.utc).isoformat()}


def compare_companies(symbols: list[str]) -> pd.DataFrame:
    return pd.DataFrame([fundamental_snapshot(symbol) for symbol in symbols])


def fundamental_history(symbol: str) -> pd.DataFrame:
    try:
        ticker=yf.Ticker(symbol);income=ticker.financials;cashflow=ticker.cashflow;rows=[]
        dates=sorted(set(income.columns).union(cashflow.columns))
        for column in dates:
            def item(frame: pd.DataFrame,name: str):
                value=frame.loc[name,column] if name in frame.index and column in frame.columns else None;return number(value)
            rows.append({"Year":pd.Timestamp(column).year,"Revenue":item(income,"Total Revenue"),"Net income":item(income,"Net Income"),"Free cash flow":item(cashflow,"Free Cash Flow")})
        return pd.DataFrame(rows).sort_values("Year")
    except Exception:return pd.DataFrame()


def dcf_valuation(fcf: float, shares: float, net_debt: float, growth: float, terminal_growth: float, discount: float, years: int = 5) -> dict[str,float]:
    if shares<=0 or discount<=terminal_growth:return {}
    cashflows=[]; current=fcf
    for year in range(1,years+1):
        current*=1+growth; cashflows.append(current/(1+discount)**year)
    terminal=current*(1+terminal_growth)/(discount-terminal_growth)/(1+discount)**years
    equity_value=sum(cashflows)+terminal-net_debt
    return {"Enterprise present value":sum(cashflows)+terminal,"Equity value":equity_value,"Fair value/share":equity_value/shares,"Terminal value share %":terminal/max(sum(cashflows)+terminal,1)*100}


def company_events(symbol: str) -> pd.DataFrame:
    rows=[]
    try:
        ticker=yf.Ticker(symbol); calendar=ticker.calendar; info=ticker.get_info()
        if isinstance(calendar,dict):
            for key,value in calendar.items():
                if "date" in str(key).lower():rows.append({"Symbol":symbol,"Type":key,"Date":str(value)})
        elif isinstance(calendar,pd.DataFrame):
            for key in calendar.index:
                if "date" in str(key).lower():rows.append({"Symbol":symbol,"Type":str(key),"Date":str(calendar.loc[key].iloc[0])})
        ex=info.get("exDividendDate")
        if ex:rows.append({"Symbol":symbol,"Type":"Ex-dividend","Date":datetime.fromtimestamp(ex,tz=timezone.utc).date().isoformat()})
    except Exception:pass
    return pd.DataFrame(rows)


def search_symbols(query: str, api_key: str | None = None) -> pd.DataFrame:
    if not query.strip():return pd.DataFrame()
    if api_key:
        try:
            response=requests.get("https://www.alphavantage.co/query",params={"function":"SYMBOL_SEARCH","keywords":query,"apikey":api_key},timeout=15);response.raise_for_status();rows=response.json().get("bestMatches",[])
            return pd.DataFrame([{"Symbol":row.get("1. symbol"),"Name":row.get("2. name"),"Type":row.get("3. type"),"Region":row.get("4. region"),"Currency":row.get("8. currency")} for row in rows])
        except requests.RequestException:pass
    try:
        quotes=yf.Search(query,max_results=10).quotes
        return pd.DataFrame([{"Symbol":row.get("symbol"),"Name":row.get("longname") or row.get("shortname"),"Type":row.get("quoteType"),"Region":row.get("exchange"),"Currency":row.get("currency")} for row in quotes if row.get("symbol")])
    except Exception:return pd.DataFrame()
