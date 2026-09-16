"""Readable insider transaction types from explicit provider descriptions/codes."""
import re
import pandas as pd


def transaction_type(row):
    # A/D acquisition/disposition and share/value signs do not identify a trade.
    code_labels = {'P':'Buy', 'S':'Sell', 'A':'Grant / Award', 'G':'Gift',
                   'M':'Exercise / Conversion', 'C':'Exercise / Conversion',
                   'X':'Exercise / Conversion', 'O':'Exercise / Conversion',
                   'F':'Tax / Exercise payment', 'D':'Disposition to issuer'}
    for key in ('Transaction Code', 'transactionCode'):
        code = row.get(key)
        if isinstance(code,str) and code.strip().upper() in code_labels:
            return code_labels[code.strip().upper()]
    descriptions = [row.get(k) for k in ('Text','Transaction','Description','transactionText')]
    text = ' '.join(x.strip() for x in descriptions if isinstance(x,str) and x.strip()).lower()
    if not text: return 'Unknown'
    # These events may contain words such as acquisition or sale without being trades.
    if re.search(r'\b(gift|donation|donated)\b',text): return 'Gift'
    if re.search(r'\b(tax|withholding|withheld)\b',text): return 'Tax / Exercise payment'
    if re.search(r'\b(exercise|exercised|conversion|converted)\b',text): return 'Exercise / Conversion'
    if re.search(r'\b(grant|granted|award|awarded|vesting|vested)\b',text): return 'Grant / Award'
    buy = bool(re.search(r'\b(buy|bought|purchase|purchased)\b',text))
    sell = bool(re.search(r'\b(sell|sold|sale)\b',text))
    if buy and not sell: return 'Buy'
    if sell and not buy: return 'Sell'
    if re.search(r'\b(acquisition|acquired|disposition|disposed|transfer|transferred)\b',text): return 'Other acquisition / disposition'
    return 'Unknown'


def normalize_insiders(data):
    if not isinstance(data,pd.DataFrame): return pd.DataFrame()
    frame = data.copy()
    if frame.empty: return frame
    frame['Transaction type'] = [transaction_type(row) for row in frame.to_dict('records')]
    first = ['Transaction type'] + [c for c in ('Start Date','Insider','Position','Shares','Value','Text','Transaction') if c in frame]
    return frame[first + [c for c in frame if c not in first]]
