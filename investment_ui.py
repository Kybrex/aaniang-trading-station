"""Investment workspace alongside the existing V7 app."""
from datetime import datetime, timezone
import pandas as pd
import streamlit as st
import yfinance as yf
from fundamentals import load_company, number, financial_history
from investment_workspace import (MOATS, symbol, scorecard, price_status, quarter_metrics,
                                  quarter_check, peer_row, validate_record, load_notebook, export_notebook)


@st.cache_data(ttl=900, max_entries=80, show_spinner=False)
def company(ticker):
    bundle = load_company(symbol(ticker))
    bundle['retrieved'] = datetime.now(timezone.utc).isoformat(timespec='seconds')
    return bundle


@st.cache_data(ttl=900, max_entries=40, show_spinner=False)
def quarters(ticker):
    t = yf.Ticker(symbol(ticker))
    return quarter_metrics(t.quarterly_income_stmt, t.quarterly_cashflow)


def display(value, unit=''):
    value = number(value)
    if value is None: return 'Unavailable'
    if unit == 'fraction': return f'{value:.1%}'
    return f'{value:,.2f}' + (f' {unit}' if unit else '')


def render():
    st.header('Company investment workspace')
    st.caption('Company quality, competitive advantage, buy prices and the investment case in one place.')
    book = st.session_state.setdefault('investment_book', {})
    with st.expander('Save or restore your investment notebook'):
        st.caption('Notes stay in this browser session. Download your notebook before closing or refreshing the page; restore it here next time. They are not stored in a shared server file.')
        upload = st.file_uploader('Restore notebook (.json)', type=['json'], key='iw_upload')
        if st.button('Restore notebook', key='iw_restore', disabled=upload is None):
            try:
                restored = load_notebook(upload.getvalue())
                st.session_state.investment_book = restored['companies']
                # Clear editor drafts so imported values appear immediately.
                for key in list(st.session_state):
                    if key.startswith('iw_edit_'): del st.session_state[key]
                st.rerun()
            except (ValueError, TypeError, UnicodeError) as exc: st.error(str(exc))
    with st.form('iw_search'):
        ticker_text = st.text_input('Research company', 'AAPL', key='iw_ticker')
        run = st.form_submit_button('Load investment overview', type='primary')
    if run:
        try:
            with st.spinner('Loading company fundamentals...'):
                selected = symbol(ticker_text)
                st.session_state.iw_bundle = company(selected)
        except Exception as exc:
            st.session_state.pop('iw_bundle', None)
            st.error(f'Company data could not be loaded: {exc}')
    bundle = st.session_state.get('iw_bundle')
    if not bundle:
        st.info('Load a company to open its six investment tools. Your saved notebook is available above.')
        st.download_button('Download investment notebook', export_notebook(book), 'aaniang-investment-notebook.json', 'application/json', key='iw_download')
        return
    ticker = bundle['symbol']; info = bundle['info']; record = book.setdefault(ticker, {})
    quote_currency = info.get('currency', 'Unknown')
    price = number(info.get('currentPrice')) or number(info.get('regularMarketPrice'))
    st.subheader(f"{info.get('longName', ticker)} ({ticker})")
    st.caption(f"{info.get('sector', 'Sector unavailable')} | Quote currency: {quote_currency} | Retrieved {bundle['retrieved']}; provider quotes may be delayed")
    panels = st.tabs(['Company scorecard', 'Moat evidence', 'Buy-price watchlist', 'Investment thesis', 'Quarterly progress', 'Peer comparison'])
    with panels[0]:
        card = scorecard(bundle)
        a,b,c=st.columns(3)
        a.metric('Price', display(price, quote_currency))
        b.metric('Favorable checks', f'{int(card.Assessment.eq("Favorable").sum())} / {int(card.Value.notna().sum())} available')
        c.metric('Checks needing review', int(card.Assessment.eq('Review').sum()))
        view=card.copy(); view['Value']=[display(v,u) for v,u in zip(view.Value,view.Unit)]
        st.dataframe(view.drop(columns='Unit'),hide_index=True,width='stretch')
        st.caption('Transparent screening rules, not a buy rating. Thresholds are general heuristics and can be unsuitable for financials, REITs or other sectors. Missing values never count as favorable. Compare with the three peers below.')
        st.write(info.get('longBusinessSummary','Business description unavailable.'))
        annual=financial_history(bundle).tail(4)
        if not annual.empty:
            st.caption(f"Annual results in millions of {info.get('financialCurrency','unknown currency')}.")
            st.dataframe((annual/1e6).round(2),width='stretch')
        st.link_button('Review company filings',f'https://www.sec.gov/edgar/browse/?CIK={ticker}&owner=exclude')
    with panels[1]:
        st.write('Record the competitive advantage, supporting filing evidence and what could weaken it.')
        st.caption('Evidence is your assessment from the cited source. Profitability scores alone do not verify a moat. Read the annual report business, competition and risk sections using the filings link above.')
        rows=record.get('moat') or [{'Advantage':m,'Evidence':'','Threat':'','Source':'','Reviewed':''} for m in MOATS]
        with st.form('iw_moat_'+ticker):
            edited=st.data_editor(pd.DataFrame(rows),num_rows='dynamic',hide_index=True,width='stretch',key='iw_edit_moat_'+ticker,
                                  column_config={'Source':st.column_config.TextColumn('Filing URL'),'Reviewed':st.column_config.TextColumn('Reviewed date (YYYY-MM-DD)')})
            save=st.form_submit_button('Save moat evidence')
        if save:
            try:
                candidate={**record,'moat':edited.fillna('').astype(str).to_dict('records')}
                validate_record(candidate); book[ticker]=candidate; record=candidate
                st.success('Moat evidence saved in this session. Download the notebook to keep it.')
            except ValueError as exc: st.error(str(exc))
        supported=sum(bool(r.get('Evidence','').strip() and r.get('Source','').strip()) for r in record.get('moat',[]))
        st.metric('Evidence entries with a source',supported)
        st.caption('Source presence is not verification of the claim or a wide-moat rating.')
    with panels[2]:
        with st.form('iw_watch_'+ticker):
            st.caption(f'Enter your own values in {quote_currency}. A buy-price hit is a research prompt, not an order.')
            fair=st.number_input('Your fair-value estimate',min_value=.01,value=float(record.get('fair_value',price or 100)),key='iw_edit_fair_'+ticker)
            target=st.number_input('Your maximum buy price',min_value=.01,value=float(record.get('buy_price',price or 100)),key='iw_edit_buy_'+ticker)
            assumptions=st.text_area('Valuation assumptions',value=record.get('assumptions',''),key='iw_edit_assumptions_'+ticker)
            reason=st.text_area('Why wait / what must improve?',value=record.get('reason',''),key='iw_edit_reason_'+ticker)
            save=st.form_submit_button('Save buy-price plan')
        if save:
            try:
                candidate={**record,'fair_value':fair,'buy_price':target,'assumptions':assumptions,'reason':reason,'currency':quote_currency}
                validate_record(candidate); book[ticker]=candidate; record=candidate
                st.success('Buy-price plan saved. Download the notebook to keep it.')
            except ValueError as exc: st.error(str(exc))
        if record.get('fair_value'):
            st.metric('Discount of your buy price to your fair value',f"{(1-record['buy_price']/record['fair_value'])*100:.1f}%")
        if st.button('Refresh saved watchlist prices',key='iw_refresh_watch'):
            rows=[]
            for key, plan in book.items():
                if not plan.get('buy_price'): continue
                try:
                    loaded=company(key); current=number(loaded['info'].get('currentPrice')) or number(loaded['info'].get('regularMarketPrice'))
                    currency=loaded['info'].get('currency','Unknown')
                    status,gap=price_status(current,plan['buy_price']) if currency==plan.get('currency') else ('Currency mismatch - review plan',None)
                    rows.append({'Symbol':key,'Price':current,'Buy price':plan['buy_price'],'Currency':currency,'Distance to buy price %':gap,'Status':status,'As of':loaded['retrieved']})
                except Exception:
                    rows.append({'Symbol':key,'Buy price':plan['buy_price'],'Status':'Price unavailable'})
            st.session_state.iw_watch_rows=rows
        if st.session_state.get('iw_watch_rows'):
            st.dataframe(pd.DataFrame(st.session_state.iw_watch_rows),hide_index=True,width='stretch')
        else:
            st.info('Save a buy-price plan, then refresh to compare all saved companies.')
        st.caption('Prices are cached for up to 15 minutes. Status is evaluated when refreshed here; no background alerts are sent.')
    with panels[3]:
        with st.form('iw_thesis_'+ticker):
            thesis=st.text_area('Why own this company?',value=record.get('thesis',''),key='iw_edit_thesis_'+ticker)
            catalysts=st.text_area('What do you expect to happen?',value=record.get('catalysts',''),key='iw_edit_catalysts_'+ticker)
            invalidation=st.text_area('What would make you reconsider?',value=record.get('invalidation',''),key='iw_edit_invalidation_'+ticker)
            growth=st.number_input('Minimum quarterly revenue growth YoY (%)',min_value=-100.,max_value=1000.,value=float(record.get('min_growth',5)),key='iw_edit_growth_'+ticker)
            margin=st.number_input('Minimum quarterly operating margin (%)',min_value=-1000.,max_value=100.,value=float(record.get('min_margin',10)),key='iw_edit_margin_'+ticker)
            fcf=st.checkbox('Expect positive quarterly free cash flow',value=record.get('positive_fcf',True),key='iw_edit_fcf_'+ticker)
            save=st.form_submit_button('Save investment thesis')
        if save:
            candidate={**record,'thesis':thesis,'catalysts':catalysts,'invalidation':invalidation,'min_growth':growth,'min_margin':margin,'positive_fcf':fcf,'thesis_updated':datetime.now(timezone.utc).isoformat()}
            validate_record(candidate); book[ticker]=candidate; record=candidate
            st.success('Investment thesis saved. The quarterly check will use these expectations.')
    with panels[4]:
        st.caption('On-demand comparison of the latest available quarter with your saved thesis. Revenue growth uses the comparable prior-year quarter when available; cash flow uses the same quarter as revenue.')
        if not record.get('thesis_updated'): st.info('Save your investment thesis first to set the expectations for this check.')
        if st.button('Check latest quarter',disabled=not record.get('thesis_updated'),key='iw_check_'+ticker):
            try:
                actual=quarters(ticker)
                if not actual['period']: st.warning('Quarterly results unavailable from the provider.')
                else: st.session_state['iw_quarter_'+ticker]=actual
            except Exception as exc: st.error(f'Quarterly data unavailable: {exc}')
        actual=st.session_state.get('iw_quarter_'+ticker)
        if actual:
            st.write('Quarter ended: '+actual['period'])
            checks=quarter_check(actual,record)
            st.dataframe(checks,hide_index=True,width='stretch')
            prior=record.get('last_review')
            if prior:
                st.caption('Previous saved review: '+str(prior.get('period','Unknown')))
                changes=[{'Metric':key,'Previously saved':prior.get(key),'Current':actual.get(key)} for key in ['revenue_growth','margin','fcf']]
                st.dataframe(pd.DataFrame(changes),hide_index=True,width='stretch')
                if prior.get('period')==actual['period']: st.info('Same quarter as your previous review. Differences may reflect restatements or provider revisions.')
            st.write('Reconsideration conditions: '+record.get('invalidation','Not supplied'))
            note=st.text_area('Your quarterly conclusion',key='iw_edit_quarter_note_'+ticker)
            if st.button('Save this quarterly review',key='iw_save_review_'+ticker):
                record['last_review']={**actual,'note':note,'saved':datetime.now(timezone.utc).isoformat(),'thesis_updated':record.get('thesis_updated')}
                st.success('Quarterly baseline saved. Download the notebook to keep it.')
    with panels[5]:
        with st.form('iw_peers_'+ticker):
            peers=st.text_input('Three peer tickers, separated by commas',key='iw_peers_input_'+ticker)
            compare=st.form_submit_button('Compare companies')
        if compare:
            try:
                selected=[symbol(x) for x in peers.split(',') if x.strip()]
                if len(selected)!=3 or len(set([ticker]+selected))!=4: raise ValueError('Enter three different peers, excluding the selected company.')
                rows=[peer_row(bundle)]; errors=[]
                with st.spinner('Loading three peer companies...'):
                    for peer in selected:
                        try: rows.append(peer_row(company(peer)))
                        except Exception: errors.append(peer+' data unavailable')
                st.session_state['iw_peer_rows_'+ticker]=(rows,errors)
            except ValueError as exc: st.error(str(exc))
        if 'iw_peer_rows_'+ticker in st.session_state:
            rows,errors=st.session_state['iw_peer_rows_'+ticker]
            st.dataframe(pd.DataFrame(rows),hide_index=True,width='stretch')
            for error in errors: st.warning(error)
            st.caption('Select genuine competitors yourself. Ratios avoid comparing absolute values in different currencies; reporting dates, accounting policies and business mixes may still differ. Favorable checks are the transparent scorecard rules, not a peer ranking.')
    st.download_button('Download investment notebook', export_notebook(book), 'aaniang-investment-notebook.json', 'application/json', key='iw_download')
