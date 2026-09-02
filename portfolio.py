"""Portfolio exposure, correlation, risk, and journal analytics."""
from __future__ import annotations

import math
import pandas as pd

from data import download_batch, last_number, symbol_frame


def portfolio_snapshot(positions: pd.DataFrame, equity: float | None = None) -> tuple[pd.DataFrame, dict[str,float], pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    if positions.empty:
        return pd.DataFrame(),{},pd.DataFrame(),pd.DataFrame(),pd.DataFrame()
    frame=positions.copy(); frame["Symbol"]=frame.Symbol.astype(str).str.upper()
    raw=download_batch(frame.Symbol.tolist()+["SPY"],period="1y",timeout=35)
    prices={}; returns={}
    for symbol in frame.Symbol:
        history=symbol_frame(raw,symbol)
        prices[symbol]=last_number(history.Close.iloc[-1]) if not history.empty else None
        if len(history)>=60: returns[symbol]=history.Close.pct_change().dropna()
    frame["Last"]=frame.Symbol.map(prices)
    for col in ["Shares","Cost","Stop","Dividend Yield","Target Weight"]:
        if col not in frame:frame[col]=0
        frame[col]=pd.to_numeric(frame[col],errors="coerce").fillna(0)
    frame["Market value"]=frame.Shares*frame.Last
    frame["P/L"]=frame.Shares*(frame.Last-frame.Cost)
    frame["Position risk"]=(frame.Last-frame.Stop).abs()*frame.Shares
    total=float(frame["Market value"].sum()); account=float(equity or total or 1)
    frame["Weight %"]=frame["Market value"]/max(total,1)*100
    frame["Risk % equity"]=frame["Position risk"]/max(account,1)*100
    frame["Annual dividend"]=frame["Market value"]*frame["Dividend Yield"]/100
    frame["Target value"]=frame["Target Weight"]/100*total
    frame["Rebalance amount"]=frame["Target value"]-frame["Market value"]
    frame["Research action"]=frame["Rebalance amount"].map(lambda value:"ADD" if value>max(total*.01,100) else "REDUCE" if value<-max(total*.01,100) else "HOLD")
    sector=frame.groupby("Sector",dropna=False)["Market value"].sum().reset_index(); sector["Weight %"]=sector["Market value"]/max(total,1)*100
    purpose=frame.groupby("Purpose",dropna=False)["Market value"].sum().reset_index(); purpose["Weight %"]=purpose["Market value"]/max(total,1)*100
    joined=pd.concat(returns,axis=1).dropna() if returns else pd.DataFrame()
    correlation=joined.corr().round(2) if not joined.empty else pd.DataFrame()
    metrics={"Market value":total,"Unrealized P/L":float(frame["P/L"].sum()),"Portfolio heat %":float(frame["Position risk"].sum()/max(account,1)*100),"Largest position %":float(frame["Weight %"].max()),"Annual dividends":float(frame["Annual dividend"].sum()),"Positions":float(len(frame))}
    return frame,metrics,sector,purpose,correlation


def correlation_matrix(positions: pd.DataFrame) -> pd.DataFrame:
    if positions.empty:return pd.DataFrame()
    symbols=positions.Symbol.astype(str).str.upper().tolist(); raw=download_batch(symbols,period="1y",timeout=35); series={}
    for symbol in symbols:
        frame=symbol_frame(raw,symbol)
        if len(frame)>=60:series[symbol]=frame.Close.pct_change()
    return pd.concat(series,axis=1).dropna().corr().round(2) if series else pd.DataFrame()


def journal_analytics(journal: pd.DataFrame) -> tuple[pd.DataFrame,dict[str,float],pd.DataFrame]:
    if journal.empty:return pd.DataFrame(),{},pd.DataFrame()
    out=journal.copy()
    for col in ["Entry","Exit","Shares","Initial Stop"]:
        if col not in out:out[col]=0
        out[col]=pd.to_numeric(out[col],errors="coerce").fillna(0)
    sign=out.Side.astype(str).str.upper().map({"LONG":1,"SHORT":-1}).fillna(1)
    out["P/L"]=(out.Exit-out.Entry)*out.Shares*sign
    initial_risk=(out.Entry-out["Initial Stop"]).abs()*out.Shares
    out["R multiple"]=out["P/L"]/initial_risk.replace(0,float("nan"))
    valid=out["R multiple"].dropna(); wins=valid[valid>0].sum(); losses=abs(valid[valid<0].sum())
    metrics={"Trades":float(len(out)),"Net P/L":float(out["P/L"].sum()),"Win rate %":float((valid>0).mean()*100) if len(valid) else 0,"Average R":float(valid.mean()) if len(valid) else 0,"Profit factor":float(wins/losses) if losses else math.inf}
    if "Setup" not in out:out["Setup"]="Unspecified"
    by_setup=out.groupby("Setup",dropna=False).agg(Trades=("Symbol","count"),PL=("P/L","sum"),Average_R=("R multiple","mean")).reset_index()
    return out,metrics,by_setup
