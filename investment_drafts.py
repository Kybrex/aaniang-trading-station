"""Company research starting points from retrieved data, never asserted moat ratings."""
import re
import pandas as pd
from fundamentals import number, financial_history
from investment_workspace import MOATS, symbol


def research_draft(bundle):
    ticker = symbol(bundle['symbol'])
    info = bundle.get('info') or {}
    profile = f'https://finance.yahoo.com/quote/{ticker}/profile/'
    statistics = f'https://finance.yahoo.com/quote/{ticker}/key-statistics/'
    cash_source = f'https://finance.yahoo.com/quote/{ticker}/cash-flow/'
    description = str(info.get('longBusinessSummary') or '').strip()
    sentences = re.split(r'(?<=[.!?])\s+', description)
    checks = [
        ('Operating margin', 'operatingMargins', 100, '%'),
        ('Gross margin', 'grossMargins', 100, '%'),
        ('Revenue growth (provider period)', 'revenueGrowth', 100, '%'),
        ('Return on assets', 'returnOnAssets', 100, '%'),
        ('Debt / equity', 'debtToEquity', 1, '%'),
    ]
    facts = []
    for label, key, scale, unit in checks:
        value = number(info.get(key))
        facts.append({'Measure': label, 'Observation': 'Unavailable' if value is None else f'{value*scale:,.2f}{unit}',
                      'Source': statistics, 'Available': value is not None})
    history = financial_history({**bundle, 'income': bundle.get('income', pd.DataFrame()),
                                 'cashflow': bundle.get('cashflow', pd.DataFrame())})
    fcf = history.get('Free cash flow', pd.Series(dtype=float)).dropna()
    latest = number(fcf.iloc[-1]) if len(fcf) else None
    cash = 'Unavailable' if latest is None else f"{latest:,.2f} {info.get('financialCurrency') or 'currency unavailable'} (annual {fcf.index[-1]})"
    facts.append({'Measure': 'Free cash flow', 'Observation': cash, 'Source': cash_source, 'Available': latest is not None})
    keywords = [('brand', 'premium', 'trademark'), ('subscription', 'software', 'service', 'platform'),
                ('network', 'marketplace', 'platform'), ('manufactur', 'scale', 'cost'),
                ('distribut', 'patent', 'store', 'license')]
    questions = [
        'Verify price increases, customer retention and market share; a margin alone does not establish pricing power.',
        'Verify renewal rates, churn and the cost of replacing the product; recurring services alone do not establish switching costs.',
        'Verify whether each additional user improves value for other users; a platform alone is not proof of a network effect.',
        'Compare unit costs and margins with genuine peers across several years; scale alone does not prove a cost advantage.',
        'Verify exclusivity, replacement cost and competitor access to distribution, licenses or assets.',
    ]
    moat = []
    for i, advantage in enumerate(MOATS):
        match = next((s for s in sentences if any(word in s.lower() for word in keywords[i])), '')
        observation = ('Business description: ' + match[:1600]) if match else 'No direct qualitative evidence returned for this advantage.'
        if i in (0, 3):
            observation += '\nOperating margin: ' + facts[0]['Observation'] + '. Financial context only. Source: ' + statistics
        moat.append({'Advantage': advantage, 'Evidence': 'UNREVIEWED RESEARCH DRAFT. ' + observation,
                     'Threat': questions[i], 'Source': profile if match else statistics if i in (0, 3) and facts[0]['Available'] else '',
                     'Reviewed': ''})
    available = [f"{r['Measure']}: {r['Observation']} (source: {r['Source']})" for r in facts if r['Available']]
    name = str(info.get('longName') or ticker)
    thesis = f'RESEARCH DRAFT — review before saving. {name} ({ticker}).\n'
    thesis += (description[:2200] + '\n\n') if description else 'Business description unavailable.\n\n'
    thesis += 'Current evidence:\n' + ('\n'.join(available) if available else 'Company fundamentals were not returned; no investment case can be established from this data.')
    thesis += '\n\nThe investment case depends on durable customer demand, cash generation and a purchase price supported by your valuation. Confirm the competitive advantage with company filings.'
    thesis += f'\nRetrieved: {bundle.get("retrieved", "unknown")}. Business source: {profile}'
    catalysts = 'Research milestones, not confirmed events or forecasts: review the next reported results for revenue growth, margins and cash conversion; check management guidance and evidence of customer retention.'
    invalidation = 'Reconsider if demand weakens, margins deteriorate, cash generation fails to support earnings, debt becomes harder to service, or the evidence for the competitive advantage weakens. Set your own quarterly thresholds below; provider growth and margin figures above may use different periods.'
    return {'moat': moat, 'facts': pd.DataFrame(facts).drop(columns='Available'),
            'thesis': thesis, 'catalysts': catalysts, 'invalidation': invalidation,
            'has_data': bool(description or available)}
