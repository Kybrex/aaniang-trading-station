"""Filing excerpts, aligned earnings changes and investment scenario calculations."""
from html.parser import HTMLParser
from urllib.parse import urlparse
from datetime import datetime, timezone
import re
import threading
import time
import pandas as pd
import requests
from fundamentals import number
from investment_workspace import symbol, quarter_check

_SEC_LOCK = threading.Lock()
_SEC_LAST = 0.


def sec_get(url, contact):
    global _SEC_LAST
    parsed=urlparse(url)
    if parsed.scheme!='https' or parsed.hostname not in ('www.sec.gov','data.sec.gov') or parsed.username:
        raise ValueError('Only official SEC sources are supported.')
    if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',contact.strip()):
        raise ValueError('Enter a contact email for SEC fair-access identification.')
    with _SEC_LOCK:
        time.sleep(max(0,.3-(time.monotonic()-_SEC_LAST)))
        _SEC_LAST=time.monotonic()
        response=requests.get(url,headers={'User-Agent':'Aaniang research '+contact.strip(),'Accept-Encoding':'gzip, deflate'},timeout=25,allow_redirects=False,stream=True)
        with response:
            if response.status_code!=200:
                raise ValueError(f'SEC returned HTTP {response.status_code}. Open the filing directly or try again later.')
            chunks=[]; size=0
            for chunk in response.iter_content(65536):
                size+=len(chunk)
                if size>15_000_000: raise ValueError('Filing exceeds the 15 MB reader limit. Open the original filing.')
                chunks.append(chunk)
            return b''.join(chunks).decode('utf-8',errors='replace')


def filing_list(ticker, contact):
    import json
    ticker=symbol(ticker)
    mapping=json.loads(sec_get('https://www.sec.gov/files/company_tickers.json',contact))
    match=next((r for r in mapping.values() if str(r.get('ticker','')).upper()==ticker),None)
    if not match: raise ValueError('No SEC ticker match. Foreign listings and funds may need manual filing lookup.')
    cik=str(match['cik_str']).zfill(10)
    data=json.loads(sec_get(f'https://data.sec.gov/submissions/CIK{cik}.json',contact))
    recent=pd.DataFrame(data.get('filings',{}).get('recent',{}))
    if recent.empty: return []
    rows=[]
    for _,row in recent[recent.form.isin(['10-K','20-F','10-Q','8-K','6-K'])].head(30).iterrows():
        accession=str(row.accessionNumber).replace('-',''); document=str(row.primaryDocument)
        if not accession.isdigit() or not re.fullmatch(r'[A-Za-z0-9_.-]+',document): continue
        rows.append({'Form':str(row.form),'Filed':str(row.filingDate),'Period':str(row.get('reportDate','')),
                     'URL':f'https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession}/{document}'})
    return rows


class FilingText(HTMLParser):
    def __init__(self):
        super().__init__(); self.parts=[]; self.hidden=0
    def handle_starttag(self,tag,attrs):
        if self.hidden:
            if tag not in ['br','hr','img','input','meta','link','wbr']: self.hidden+=1
            return
        attr=dict(attrs)
        if tag in ['script','style','ix:hidden','head'] or 'display:none' in attr.get('style','').replace(' ','').lower(): self.hidden=1
        elif tag in ['p','div','tr','li','br','h1','h2','h3']: self.parts.append('\n')
    def handle_startendtag(self,tag,attrs):
        if not self.hidden and tag=='br': self.parts.append('\n')
    def handle_endtag(self,tag):
        if self.hidden: self.hidden-=1
        elif tag in ['p','div','tr','li']: self.parts.append('\n')
    def handle_data(self,data):
        if not self.hidden: self.parts.append(data)


def filing_passages(html, source):
    parser=FilingText();parser.feed(html)
    paragraphs=[' '.join(p.split()) for p in ''.join(parser.parts).split('\n')]
    topics={'Moat and competition':['brand','competitive advantage','switching','network effect','pricing power','distribution network','patent'],
            'Risks':['risk','competition','regulation','cybersecurity','concentration'],
            'Management outlook':['guidance','outlook','expect','anticipate','forecast'],
            'Capital allocation':['repurchase','dividend','acquisition','capital allocation','repay']}
    rows=[]
    for topic, words in topics.items():
        seen=set()
        matches=[p for p in paragraphs if len(p)>100 and any(w in p.lower() for w in words)]
        matches.sort(key=lambda p:sum(w in p.lower() for w in words),reverse=True)
        for paragraph in matches:
            excerpt=paragraph[:650].rsplit(' ',1)[0]+'…' if len(paragraph)>650 else paragraph
            if excerpt in seen: continue
            seen.add(excerpt); rows.append({'Topic':topic,'Passage':excerpt,'Source':source})
            if len(seen)==2: break
    return pd.DataFrame(rows,columns=['Topic','Passage','Source'])


def statement(frame,names):
    for name in names:
        if name in frame.index:
            result=pd.to_numeric(frame.loc[name],errors='coerce')
            result.index=pd.to_datetime(result.index,errors='coerce')
            return result[~result.index.isna()].sort_index()
    return pd.Series(dtype=float)


def earnings_changes(income,cashflow,balance):
    revenue=statement(income,['Total Revenue','Operating Revenue'])
    operating=statement(income,['Operating Income'])
    fcf=statement(cashflow,['Operating Cash Flow'])-statement(cashflow,['Capital Expenditure']).abs()
    data=pd.DataFrame({'Revenue':revenue,'Operating margin %':operating/revenue.replace(0,float('nan'))*100,
                       'Free cash flow':fcf,'Total debt':statement(balance,['Total Debt'])}).sort_index()
    valid=revenue.dropna()
    if valid.empty: return pd.DataFrame()
    current=valid.index.max()
    prior_dates=[d for d in valid.index if 330<=(current-d).days<=400]
    if not prior_dates:
        return pd.DataFrame([{'Metric':col,'Current quarter':str(current.date()),'Prior-year quarter':'Unavailable','Current':number(data.at[current,col]),'Previous':None,'Change':None,'Change %':None} for col in data])
    previous=min(prior_dates,key=lambda d:abs((current-d).days-365))
    rows=[]
    for col in data:
        now,before=number(data.at[current,col]),number(data.at[previous,col])
        rows.append({'Metric':col,'Current quarter':str(current.date()),'Prior-year quarter':str(previous.date()),'Current':now,'Previous':before,
                     'Change':now-before if now is not None and before is not None else None,
                     'Change %':(now/before-1)*100 if now is not None and before is not None and before>0 and col!='Operating margin %' else None})
    return pd.DataFrame(rows)


def sensitivity(fcf_per_share,growth,discount,terminal):
    values=[number(x) for x in [fcf_per_share,growth,discount,terminal]]
    if any(x is None for x in values) or fcf_per_share<=0 or growth<=-1 or discount<=terminal or discount<=0:
        raise ValueError('Use positive cash flow per share, growth above -100%, and a positive required return above terminal growth.')
    rows=[]
    for g in [growth-.02,growth,growth+.02]:
        row={'Annual growth':f'{g:.1%}'}
        for r in [discount-.02,discount,discount+.02]:
            if r<=terminal or r<=0 or g<=-1: value=None
            else:
                value=sum(fcf_per_share*(1+g)**y/(1+r)**y for y in range(1,6))
                value+=fcf_per_share*(1+g)**5*(1+terminal)/(r-terminal)/(1+r)**5
            row[f'Required return {r:.1%}']=value
        rows.append(row)
    return pd.DataFrame(rows).set_index('Annual growth')


def allocation(income,cashflow,balance):
    ocf=statement(cashflow,['Operating Cash Flow'])
    capex=statement(cashflow,['Capital Expenditure']).abs()
    frame=pd.DataFrame({'Free cash flow':ocf-capex,
        'Dividends paid':statement(cashflow,['Common Stock Dividend Paid','Cash Dividends Paid']).abs(),
        'Share repurchases':statement(cashflow,['Repurchase Of Capital Stock','Common Stock Payments']).abs(),
        'Net acquisition cash flow (signed)':statement(cashflow,['Net Business Purchase And Sale']),
        'Debt repaid':statement(cashflow,['Repayment Of Debt']).abs(),
        'Debt issued':statement(cashflow,['Issuance Of Debt']),
        'Total debt':statement(balance,['Total Debt']),
        'Diluted average shares':statement(income,['Diluted Average Shares'])}).sort_index()
    frame['Share count change %']=frame['Diluted average shares'].pct_change(fill_method=None)*100
    frame['Dividends + buybacks / FCF %']=(frame['Dividends paid']+frame['Share repurchases'])/frame['Free cash flow'].where(frame['Free cash flow']>0)*100
    return frame.tail(4)


def thesis_warning(ticker,metrics,record):
    if not record.get('thesis_updated'): return {'Symbol':ticker,'Status':'No saved thesis','Quarter':None,'Reason':'Save measurable expectations first.'}
    checks=quarter_check(metrics,record)
    failed=checks[checks.Result.eq('Review thesis')].Metric.tolist()
    missing=checks[checks.Result.eq('Unavailable')].Metric.tolist()
    status='Review thesis' if failed else 'Incomplete data' if missing or not metrics.get('period') else 'Meets saved thresholds'
    if metrics.get('period') and (datetime.now(timezone.utc).date()-pd.Timestamp(metrics['period']).date()).days>200:
        status='Stale results - review'; missing.append('quarter is more than 200 days old')
    return {'Symbol':ticker,'Status':status,'Quarter':metrics.get('period'),'Reason':'; '.join(failed+['Missing: '+x for x in missing]) or 'All available numeric thresholds met; review qualitative conditions separately.'}
