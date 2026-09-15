"""Monitoring and scenario sections; explicit assumptions and no invented history."""
from __future__ import annotations
from datetime import date
import pandas as pd
from decision_report import num, fmt, latest, sector_model

EXTRA_DEFAULTS = dict(profit_growth=5., share_change=0., annual_dividend=None,
                      refinance_pct=25., sales_shock=10., margin_shock=3., rate_shock=2.,
                      target_revenue_growth=0., target_margin=10., target_fcf=0.,
                      target_debt_equity=150., target_dilution=2.)

def extra_inputs(values):
    result={**EXTRA_DEFAULTS, **{k:v for k,v in values.items() if k in EXTRA_DEFAULTS}}
    for key,value in result.items():
        if key=='annual_dividend' and value is None: continue
        value=num(value)
        if value is None: raise ValueError(f'{key} must be finite.')
        result[key]=value
    for key in ('profit_growth','share_change'):
        if not -40<=result[key]<=40: raise ValueError(f'{key} must be between -40% and 40%.')
    for key in ('refinance_pct','sales_shock'):
        if not 0<=result[key]<=100: raise ValueError(f'{key} must be between 0% and 100%.')
    for key in ('margin_shock','rate_shock'):
        if not 0<=result[key]<=30: raise ValueError(f'{key} must be between 0 and 30 percentage points.')
    if result['annual_dividend'] is not None and result['annual_dividend']<0: raise ValueError('Dividends cannot be negative.')
    return result

def history_rows(rows):
    if not isinstance(rows,list) or len(rows)>1000: raise ValueError('Valuation history must contain at most 1000 observations.')
    clean=[]
    for row in rows:
        if not isinstance(row,dict): raise ValueError('Invalid valuation observation.')
        if all(v is None or v=='' for v in row.values()): continue
        try: day=date.fromisoformat(str(row.get('Date',''))).isoformat()
        except ValueError: raise ValueError('Use YYYY-MM-DD dates for valuation observations.')
        pe=num(row.get('Trailing P/E')); source=row.get('Source')
        if pe is None or pe<=0 or not isinstance(source,str) or not source.strip():
            raise ValueError('Each historical observation needs a positive trailing P/E and a source.')
        clean.append({'Date':day,'Trailing P/E':pe,'Source':source.strip()})
    return clean

def valuation_history(report, previous, manual):
    s=report['snapshot']; today=report['generated_at'].date().isoformat()
    rows=history_rows((previous or {}).get('valuation_history',[]))+history_rows(manual)
    rows=[r for r in rows if r['Date']<=today]
    pe=num(s.get('Trailing P/E'))
    if pe is not None and pe>0:
        rows.append({'Date':today,'Trailing P/E':pe,'Source':s.get('Source','Provider')})
    frame=pd.DataFrame(rows,columns=['Date','Trailing P/E','Source']).drop_duplicates('Date',keep='last').sort_values('Date')
    past=frame[frame.Date.lt(today)]
    note='Saved and user-sourced trailing P/E observations only; not a reconstructed daily history. Keep the notebook to accumulate observations. Forward P/E is not mixed into this series.'
    stats=[]
    if len(past)>=3:
        values=past['Trailing P/E']
        stats=[('Prior observations',str(len(past))),('Historical low',fmt(values.min())),('Historical median',fmt(values.median())),('Historical high',fmt(values.max())),('Current trailing P/E',fmt(pe)),('Prior observations below current (%)',fmt(values.lt(pe).mean()*100) if pe is not None else 'Unavailable')]
    else: stats=[('Coverage',f'{len(past)} earlier observations. At least 3 are required for a range comparison.')]
    return frame,pd.DataFrame(stats,columns=['Measure','Value']),note

def return_breakdown(report,a):
    s=report['snapshot']; price=num(s.get('Price')); reit=sector_model(s)=='REIT'
    unit=num(a.get('ffo_per_share')) if reit else num(s.get('Trailing EPS'))
    if price is None or price<=0 or unit is None or unit<=0:
        return pd.DataFrame([{'Driver':'Coverage','Contribution to total return (pp)':'Unavailable: positive price and EPS (or sourced REIT FFO/share) required.'}]),'No return estimate with missing or negative earnings.'
    years=a['years']; grown=price*(1+a['profit_growth']/100)**years
    diluted=grown/(1+a['share_change']/100)**years
    end=unit*(1+a['profit_growth']/100)**years/(1+a['share_change']/100)**years*a['exit_multiple']
    dividend=a['annual_dividend']
    if dividend is None: dividend=num(s.get('Annual dividend/share'))
    income=None if dividend is None else dividend*years
    rows=[('Total profit growth',grown-price),('Share-count change',diluted-grown),('Exit multiple change',end-diluted),('Cash dividends',income)]
    frame=pd.DataFrame([{'Driver':label,'Contribution to total return (pp)':fmt(change/price*100) if change is not None else 'Unavailable'} for label,change in rows])
    wealth=None if income is None else end+income
    note=(f'Separate {years}-year earnings/FFO illustration: total profit growth {fmt(a["profit_growth"])}%/year, shares {fmt(a["share_change"])}%/year, exit multiple {fmt(a["exit_multiple"])}. '
          f'Horizon price {fmt(end)}; total return {fmt((wealth/price-1)*100) if wealth is not None else "Unavailable"}%; annualized total return {fmt(((wealth/price)**(1/years)-1)*100) if wealth is not None else "Unavailable"}%. '
          'Contributions are sequential percentage points over the entire horizon, not annual returns. Flat annual cash dividends, no reinvestment, tax or fees. Blank dividend input uses provider annual dividend/share; missing remains unavailable. This illustration is separate from the primary cash-flow valuation; per-share growth is not counted again.')
    return frame,note

def stress_tests(report,a):
    t=report.get('financial_trends',pd.DataFrame()); s=report['snapshot']
    if sector_model(s)!='Operating company':
        return pd.DataFrame([{'Coverage':'Corporate sales/margin stress is not comparable for this sector. Review the sector-specific capital, underwriting or property risks in section 2.'}]),'No generic operating stress applied to banks, insurers, financial services or REITs.'
    revenue=latest(t,'Revenue'); op=latest(t,'Operating income'); debt=latest(t,'Total debt')
    if revenue is None or revenue<=0 or op is None:
        return pd.DataFrame([{'Coverage':'Latest annual revenue and operating income are required.'}]),'Missing inputs remain unavailable.'
    margin=op/revenue; rows=[]
    for label,sales,margin_pp,rate in [('Base',0,0,0),('Sales decline',a['sales_shock'],0,0),('Margin compression',0,a['margin_shock'],0),('Higher borrowing costs',0,0,a['rate_shock']),('Combined stress',a['sales_shock'],a['margin_shock'],a['rate_shock'])]:
        operating=revenue*(1-sales/100)*(margin-margin_pp/100)
        interest=0. if rate==0 else debt*a['refinance_pct']/100*rate/100 if debt is not None else None
        stressed=operating-interest if interest is not None else None
        rows.append({'Scenario':label,'Sales decline %':sales,'Margin drop (pp)':margin_pp,'Rate increase (pp)':rate,'Operating profit':operating,'Extra annual interest':interest,'Profit less extra interest':stressed,'Change vs base profit %':(stressed/op-1)*100 if stressed is not None and op>0 else None})
    return pd.DataFrame(rows),f'Latest annual statement currency. Reprices {fmt(a["refinance_pct"])}% of reported debt. Profit less extra interest is a pretax sensitivity, not net income or a share-price forecast; existing interest, taxes, hedges and management responses are excluded. Sales shocks hold margin constant; margin shocks reduce it by the entered percentage points.'

def earnings_checklist(report,a):
    financial=sector_model(report['snapshot']) in ('Bank','Insurer','Financial services')
    rows=[('Revenue growth','Latest quarter vs same quarter a year earlier',f'>= {fmt(a["target_revenue_growth"])}%'),('Operating margin','Latest quarter operating income / revenue',f'>= {fmt(a["target_margin"])}%'),('Free cash flow','Latest quarter OCF minus capital spending',f'>= {fmt(a["target_fcf"])} in statement currency'),('Debt/equity','Latest reported balance sheet',f'<= {fmt(a["target_debt_equity"])}%'),('Share dilution','Quarterly diluted weighted-average shares vs same quarter a year earlier',f'<= {fmt(a["target_dilution"])}% growth')]
    frame=pd.DataFrame(rows,columns=['Metric','Measure at next earnings','Your threshold'])
    frame['Status']=['Await next filing' if not financial or metric in ('Revenue growth','Share dilution') else 'Sector-specific review required' for metric,_,_ in rows]
    return frame,'Editable research targets, not analyst consensus. Assess comparable quarters after results arrive; current annual figures are not treated as next-quarter results. For financial firms substitute regulatory capital and credit/underwriting measures for corporate cash-flow and leverage rules.'

def evidence_map(report,d):
    s=report['snapshot']; t=report.get('financial_trends',pd.DataFrame())
    url=f'https://finance.yahoo.com/quote/{report["symbol"]}/'
    period=str(t.Year.max()) if not t.empty else 'Unavailable'
    rows=[{'Conclusion / check':d['summary'],'Evidence':f'Price {fmt(s.get("Price"))}; base fair value {fmt(d["valuation"]["fair_value"])}; safety price {fmt(d["valuation"]["buy_price"])}','Period':d['generated'],'Source':url,'Basis':'Provider price + editable model; assumptions in section 4'}]
    for metric in ('Revenue growth','Operating margin'):
        rows.append({'Conclusion / check':metric,'Evidence':fmt(s.get(metric),'%'),'Period':s.get('Snapshot retrieved',d['generated']),'Source':url+'key-statistics/','Basis':'Provider snapshot; reporting period not supplied'})
    for _,row in d['checks'].iterrows():
        rows.append({'Conclusion / check':row['Check']+' - '+row['Status'],'Evidence':fmt(row['Value'])+'; '+row['Rule / limitation'],'Period':period if row['Check']!='Debt / equity %' else 'Snapshot','Source':url+'financials/','Basis':'Rule applied to provider data; not independently verified'})
    for _,row in d['moat'].iterrows():
        rows.append({'Conclusion / check':row['Factor']+' - '+row['Assessment'],'Evidence':row['Evidence / next check'],'Period':'User research; review source period','Source':row['Source'],'Basis':'User evidence; not independently verified'})
    return pd.DataFrame(rows),'Source links are entry points for checking the evidence, not a claim that filings have been independently verified. Exact reported periods remain unavailable where the provider omits them. SEC filing records, when returned, appear in the appendix.'

def add_extensions(report,d,previous=None):
    a=d['assumptions']; a.update(extra_inputs(a))
    previous=previous if previous and previous.get('symbol')==report['symbol'] else None
    observations=dict(d['observations'],**{'Base fair value':num(d['valuation']['fair_value']),'Total debt':latest(report.get('financial_trends',pd.DataFrame()),'Total debt'),'Trailing EPS':num(report['snapshot'].get('Trailing EPS'))})
    old=(previous or {}).get('observations',{})
    changes=[]
    for metric,value in observations.items():
        prior=num(old.get(metric)); delta=value-prior if value is not None and prior is not None else None
        changes.append({'Metric':metric,'Previous':prior,'Current':value,'Change':delta,'Interpretation':'No comparable baseline' if delta is None else 'Changed' if abs(delta)>1e-9 else 'Unchanged'})
    if previous and previous.get('inputs'):
        for key in ('growth','discount','terminal_growth','exit_multiple','years'):
            prior=num(previous['inputs'].get(key)); current=num(a[key])
            changes.append({'Metric':'Assumption: '+key,'Previous':prior,'Current':current,'Change':current-prior if prior is not None else None,'Interpretation':'Assumption change' if prior is not None and current!=prior else 'Unchanged' if prior is not None else 'No comparable baseline'})
    history,stats,history_note=valuation_history(report,previous,a.get('valuation_history',[]))
    returns,return_note=return_breakdown(report,a); stress,stress_note=stress_tests(report,a); checklist,check_note=earnings_checklist(report,a); evidence,evidence_note=evidence_map(report,d)
    d.update(observations=observations,valuation_history=history.to_dict('records'),extensions=[
        ('11. What changed since the last report',pd.DataFrame(changes),'Compared with '+d['prior_date']+'. Fair-value changes can reflect both new data and edited assumptions; they are not attributed to earnings alone.'),
        ('12. Historical valuation range',stats,history_note),
        ('13. Return breakdown',returns,return_note),
        ('14. Evidence behind the conclusions',evidence,evidence_note),
        ('15. Business stress tests',stress,stress_note),
        ('16. Next earnings checklist',checklist,check_note)])
    return d
