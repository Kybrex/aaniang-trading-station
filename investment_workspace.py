"""Pure investment research calculations and portable private notebook validation."""
from __future__ import annotations
import json
import re
from datetime import datetime, timezone
from urllib.parse import urlparse
import pandas as pd
from fundamentals import number, financial_history

MOATS = ['Brand and pricing power', 'Switching costs', 'Network effects', 'Cost advantage', 'Distribution or scarce assets']


def symbol(value):
    value = str(value).strip().upper()
    if not re.fullmatch(r'[A-Z][A-Z0-9.-]{0,14}', value):
        raise ValueError('Enter a valid stock ticker.')
    return value


def scorecard(bundle):
    info = bundle['info']
    hist = financial_history(bundle)
    fcf = hist.get('Free cash flow', pd.Series(dtype=float)).dropna()
    rows = []
    def add(category, metric, value, unit, favorable, concern, basis):
        n = number(value)
        status = 'Unavailable' if n is None else 'Favorable' if favorable(n) else 'Review' if concern(n) else 'Mixed'
        rows.append({'Area': category, 'Metric': metric, 'Value': n, 'Unit': unit, 'Assessment': status, 'Basis': basis})
    add('Profitability', 'Operating margin', number(info.get('operatingMargins')), 'fraction', lambda x:x>=.20, lambda x:x<=0, '>=20% favorable; <=0% review')
    add('Profitability', 'Return on assets', info.get('returnOnAssets'), 'fraction', lambda x:x>=.08, lambda x:x<=0, '>=8% favorable; <=0% review')
    add('Growth', 'Revenue growth (provider)', info.get('revenueGrowth'), 'fraction', lambda x:x>=.05, lambda x:x<0, '>=5% favorable; negative review; provider reporting period')
    add('Growth', 'Earnings growth (provider)', info.get('earningsGrowth'), 'fraction', lambda x:x>=.05, lambda x:x<0, '>=5% favorable; negative review; may be distorted by one-offs')
    add('Cash flow', 'Latest annual free cash flow', fcf.iloc[-1] if len(fcf) else None, info.get('financialCurrency','Unknown'), lambda x:x>0, lambda x:x<=0, 'Positive favorable; operating cash flow less capital expenditure')
    add('Debt', 'Debt / equity', info.get('debtToEquity'), '%', lambda x:0<=x<=50, lambda x:x>150 or x<0, '<=50% favorable; >150% or negative review')
    add('Debt', 'Current ratio', info.get('currentRatio'), 'x', lambda x:x>=1.5, lambda x:x<1, '>=1.5 favorable; <1 review')
    add('Valuation', 'Forward P/E', info.get('forwardPE'), 'x', lambda x:False, lambda x:x<=0, 'Compare with peers and growth; no universal cheap multiple')
    return pd.DataFrame(rows)


def price_status(price, target):
    price, target = number(price), number(target)
    if price is None or price<=0 or target is None or target<=0:
        return 'Unavailable', None
    return ('At/below your buy price' if price <= target else 'Waiting'), (price / target - 1) * 100


def quarter_metrics(income, cashflow):
    """Align quarter dates; never mix annual/TTM values with quarterly targets."""
    def series(frame, names):
        for name in names:
            if name in frame.index:
                s = pd.to_numeric(frame.loc[name], errors='coerce')
                s.index = pd.to_datetime(s.index, errors='coerce')
                return s[~s.index.isna()].sort_index()
        return pd.Series(dtype=float)
    revenue = series(income, ['Total Revenue','Operating Revenue'])
    operating = series(income, ['Operating Income'])
    ocf = series(cashflow, ['Operating Cash Flow','Total Cash From Operating Activities'])
    capex = series(cashflow, ['Capital Expenditure','Capital Expenditures']).abs()
    frame = pd.DataFrame({'Revenue': revenue, 'Operating income': operating, 'Free cash flow': ocf-capex}).sort_index()
    if frame.empty or revenue.dropna().empty:
        return {'period': None, 'revenue_growth': None, 'margin': None, 'fcf': None}
    latest = revenue.dropna().index.max()
    current = number(revenue.get(latest))
    prior_dates = [d for d in revenue.dropna().index if 330 <= (latest-d).days <= 400]
    prior = number(revenue.loc[min(prior_dates, key=lambda d:abs((latest-d).days-365))]) if prior_dates else None
    op = number(operating.get(latest))
    return {'period': latest.date().isoformat(), 'revenue_growth': (current/prior-1)*100 if current is not None and prior and prior>0 else None,
            'margin': op/current*100 if op is not None and current and current>0 else None, 'fcf': number((ocf-capex).get(latest))}


def quarter_check(metrics, thesis):
    checks = []
    for key,label,target_key in [('revenue_growth','Revenue growth YoY (%)','min_growth'),('margin','Operating margin (%)','min_margin')]:
        actual, target = number(metrics.get(key)), number(thesis.get(target_key))
        checks.append({'Metric':label,'Actual':actual,'Minimum expected':target,'Result':'Unavailable' if actual is None or target is None else 'Meets thesis' if actual>=target else 'Review thesis'})
    if thesis.get('positive_fcf'):
        actual=number(metrics.get('fcf'))
        checks.append({'Metric':'Quarterly free cash flow','Actual':actual,'Minimum expected':0,'Result':'Unavailable' if actual is None else 'Meets thesis' if actual>0 else 'Review thesis'})
    return pd.DataFrame(checks)


def peer_row(bundle):
    i=bundle['info']; s=scorecard(bundle)
    return {'Symbol':bundle['symbol'],'Sector':i.get('sector','Unknown'),'Currency':i.get('currency','Unknown'),
            'Available checks':int(s.Value.notna().sum()),'Favorable checks':int(s.Assessment.eq('Favorable').sum()),
            'Operating margin %':number(i.get('operatingMargins'))*100 if number(i.get('operatingMargins')) is not None else None,
            'Revenue growth %':number(i.get('revenueGrowth'))*100 if number(i.get('revenueGrowth')) is not None else None,
            'Debt / equity %':number(i.get('debtToEquity')),'Forward P/E':number(i.get('forwardPE'))}


def validate_record(record):
    if not isinstance(record, dict): raise ValueError('Invalid notebook record.')
    for key in ['buy_price','fair_value','min_growth','min_margin']:
        if key in record and (number(record[key]) is None or (key in ['buy_price','fair_value'] and record[key]<=0)):
            raise ValueError(f'Invalid {key}.')
    if 'min_growth' in record and not -100<=record['min_growth']<=1000: raise ValueError('Invalid growth expectation.')
    if 'min_margin' in record and not -1000<=record['min_margin']<=100: raise ValueError('Invalid margin expectation.')
    if ('buy_price' in record) != ('fair_value' in record): raise ValueError('Buy-price plans need both buy price and fair value.')
    if 'currency' in record and (not isinstance(record['currency'],str) or len(record['currency'])>20): raise ValueError('Invalid currency.')
    for key in ['thesis_updated']:
        if key in record and not isinstance(record[key],str): raise ValueError('Invalid saved date.')
    if 'last_review' in record:
        review=record['last_review']
        if not isinstance(review,dict): raise ValueError('Invalid quarterly review.')
        for key in ['revenue_growth','margin','fcf']:
            if review.get(key) is not None and number(review[key]) is None: raise ValueError('Invalid quarterly value.')
        for key in ['period','note','saved','thesis_updated']:
            if review.get(key) is not None and (not isinstance(review[key],str) or len(review[key])>10000): raise ValueError('Invalid review text.')
    for key in ['reason','assumptions','thesis','catalysts','invalidation','guidance_before','guidance_after','guidance_sources']:
        if key in record and (not isinstance(record[key],str) or len(record[key])>10000): raise ValueError('Invalid note text.')
    if 'positive_fcf' in record and not isinstance(record['positive_fcf'],bool): raise ValueError('Invalid cash-flow expectation.')
    evidence=record.get('moat',[])
    if not isinstance(evidence,list) or len(evidence)>100: raise ValueError('Invalid moat evidence.')
    for row in evidence:
        if not isinstance(row,dict): raise ValueError('Invalid moat evidence row.')
        for key in ['Advantage','Evidence','Threat','Source','Reviewed']:
            if not isinstance(row.get(key,''),str) or len(row.get(key,''))>10000: raise ValueError('Invalid moat evidence text.')
        url=row.get('Source','')
        if url and (urlparse(url).scheme not in ('https','http') or not urlparse(url).netloc): raise ValueError('Source must be an http(s) filing URL.')
    return record


def load_notebook(raw):
    if len(raw)>2_000_000: raise ValueError('Notebook is too large (maximum 2 MB).')
    data=json.loads(raw)
    if not isinstance(data,dict) or data.get('version')!=1 or not isinstance(data.get('companies'),dict) or len(data['companies'])>200:
        raise ValueError('Use an Aaniang investment notebook export.')
    for key,value in data['companies'].items():
        if symbol(key)!=key: raise ValueError('Invalid saved ticker.')
        validate_record(value)
    return data


def export_notebook(companies):
    data={'version':1,'companies':companies}
    raw=json.dumps(data,allow_nan=False,indent=2)
    load_notebook(raw)
    return raw
