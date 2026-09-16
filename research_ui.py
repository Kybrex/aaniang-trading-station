"""Source-backed company research extensions for the investment workspace."""
import pandas as pd
import streamlit as st
import yfinance as yf
from fundamentals import number, financial_history
from investment_research import filing_list, sec_get, filing_passages, earnings_changes, sensitivity, allocation, thesis_warning
from cloud_ui import setting


@st.cache_data(ttl=3600,max_entries=40,show_spinner=False)
def annual_evidence(ticker,contact):
    filings=filing_list(ticker,contact)
    annual=next((f for f in filings if f['Form'] in ('10-K','20-F')),None)
    if annual is None: raise ValueError('No annual filing in the available recent filing list. Use the SEC company page.')
    return annual,filing_passages(sec_get(annual['URL'],contact),annual['URL']),filings


@st.cache_data(ttl=3600,max_entries=80,show_spinner=False)
def document_evidence(url,contact):
    return filing_passages(sec_get(url,contact),url)


@st.cache_data(ttl=900,max_entries=40,show_spinner=False)
def quarter_data(ticker):
    t=yf.Ticker(ticker); result={}; errors=[]
    for key,attr in [('income','quarterly_income_stmt'),('cashflow','quarterly_cashflow'),('balance','quarterly_balance_sheet')]:
        try: result[key]=getattr(t,attr)
        except Exception: result[key]=pd.DataFrame();errors.append(key)
    return result,errors


def warnings(book):
    with st.expander('Thesis warning dashboard',expanded=False):
        available=[s for s,r in book.items() if r.get('thesis_updated')]
        if not available:
            st.info('Save an investment thesis to enable warnings for that company.')
            return
        selected=st.multiselect('Companies to check (up to 20)',available,default=available[:10],max_selections=20,key='research_warning_symbols')
        if st.button('Refresh thesis warnings',key='research_warnings'):
            from investment_ui import quarters
            rows=[]
            for ticker in selected[:20]:
                try: rows.append(thesis_warning(ticker,quarters(ticker),book[ticker]))
                except Exception: rows.append({'Symbol':ticker,'Status':'Data unavailable','Reason':'Quarterly data could not be retrieved.'})
            st.session_state.research_warning_rows=rows
        if st.session_state.get('research_warning_rows'):
            st.dataframe(pd.DataFrame(st.session_state.research_warning_rows),hide_index=True,width='stretch')
        st.caption('On-demand checks against saved growth, margin and cash-flow thresholds. Qualitative conditions still need your review. No background notifications; refresh after changing a thesis.')


def render(bundle,record):
    ticker=bundle['symbol'];info=bundle['info']
    st.subheader('Investment research: filings, earnings and valuation')
    tabs=st.tabs(['Automatic filing evidence','Earnings changes','Valuation sensitivity','Capital allocation'])
    with tabs[0]:
        contact=st.text_input('SEC contact email',value=setting('SEC_CONTACT_EMAIL'),key='research_contact_'+ticker,help='Sent to SEC as the app contact to identify automated requests; not added to your notebook.')
        if st.button('Find annual-report evidence',key='research_filings_'+ticker):
            try:
                with st.spinner('Reading the latest annual filing from SEC...'):
                    st.session_state['research_evidence_'+ticker]=annual_evidence(ticker,contact)
            except Exception as exc: st.error(str(exc))
        result=st.session_state.get('research_evidence_'+ticker)
        if result:
            filing,passages,filings=result
            st.write(f"{filing['Form']} filed {filing['Filed']} | Period {filing['Period']}")
            st.link_button('Open annual filing',filing['URL'])
            if passages.empty: st.info('No matching narrative passages were found. Open the filing to review it directly.')
            else:
                st.dataframe(passages,hide_index=True,width='stretch',column_config={'Source':st.column_config.LinkColumn('Source')})
                if st.button('Add passages to my moat research notes',key='research_save_evidence_'+ticker):
                    existing=record.setdefault('moat',[])
                    for _,row in passages[passages.Topic.eq('Moat and competition')].iterrows():
                        item={'Advantage':'Filing passage - needs review','Evidence':row.Passage,'Threat':'Not yet assessed','Source':row.Source,'Reviewed':''}
                        if item not in existing and len(existing)<100: existing.append(item)
                    st.session_state['iw_moat_version_'+ticker]=st.session_state.get('iw_moat_version_'+ticker,0)+1
                    st.rerun()
            st.caption('Keyword-selected excerpts from the company’s filing, not an AI verdict or proof of a moat. Read the surrounding source and assess contrary evidence.')
            labels=[f"{f['Form']} | {f['Filed']} | {f['Period']}" for f in filings]
            chosen=st.selectbox('Additional filing for guidance or risk review',range(len(filings)),format_func=lambda i:labels[i],key='research_document_'+ticker)
            if st.button('Read selected filing passages',key='research_read_document_'+ticker):
                try: st.session_state['research_extra_'+ticker]=(filings[chosen],document_evidence(filings[chosen]['URL'],contact))
                except Exception as exc: st.error(str(exc))
            if 'research_extra_'+ticker in st.session_state:
                extra,frame=st.session_state['research_extra_'+ticker]
                st.link_button('Open selected filing',extra['URL'])
                st.dataframe(frame,hide_index=True,width='stretch')
                st.caption('An 8-K may reference an earnings release in an exhibit. If guidance is absent here, read the linked original and exhibits; absent text does not mean guidance was unchanged.')
    with tabs[1]:
        if st.button('Compare latest quarterly results',key='research_earnings_'+ticker):
            data,errors=quarter_data(ticker)
            st.session_state['research_changes_'+ticker]=(earnings_changes(**data),errors)
        if 'research_changes_'+ticker in st.session_state:
            frame,errors=st.session_state['research_changes_'+ticker]
            if frame.empty: st.info('Quarterly revenue data is unavailable.')
            else:
                st.dataframe(frame,hide_index=True,width='stretch')
                for _,row in frame.iterrows():
                    if pd.notna(row['Change']):
                        unit=' percentage points' if row.Metric=='Operating margin %' else ' '+str(info.get('financialCurrency','reporting currency'))
                        st.write(f"{row.Metric}: {'increased' if row['Change']>0 else 'decreased' if row['Change']<0 else 'unchanged'} by {abs(row['Change']):,.2f}{unit} versus the comparable prior-year quarter.")
            if errors: st.warning('Unavailable quarterly feeds: '+', '.join(errors))
        st.caption('Revenue, margin, cash flow and debt use aligned quarter-end dates. Growth rates are omitted for zero/negative prior values. A fall in debt has a different interpretation from a fall in cash flow.')
        st.write('Management guidance comparison')
        with st.form('research_guidance_'+ticker):
            before=st.text_area('Previous guidance passage',value=record.get('guidance_before',''),max_chars=10000,key='research_guidance_before_'+ticker)
            after=st.text_area('Latest guidance passage',value=record.get('guidance_after',''),max_chars=10000,key='research_guidance_after_'+ticker)
            source=st.text_input('Guidance source URL(s)',value=record.get('guidance_sources',''),max_chars=10000,key='research_guidance_sources_'+ticker)
            save=st.form_submit_button('Compare and save guidance passages')
        if save:
            record.update(guidance_before=before,guidance_after=after,guidance_sources=source)
        if record.get('guidance_before') and record.get('guidance_after'):
            import difflib
            lines=list(difflib.unified_diff(record['guidance_before'].splitlines(),record['guidance_after'].splitlines(),fromfile='Previous guidance',tofile='Latest guidance',lineterm=''))
            st.code('\n'.join(lines) if lines else 'No text changes in the supplied passages.',language='diff')
            st.caption('Text comparison only. Match metric, fiscal period and currency before interpreting a guidance change. Filing passages above can supply the source text.')
    with tabs[2]:
        hist=financial_history(bundle);fcf=hist.get('Free cash flow',pd.Series(dtype=float)).dropna()
        shares=number(info.get('sharesOutstanding')); same=info.get('currency')==info.get('financialCurrency')
        default=max(.01,float(fcf.iloc[-1]/shares)) if len(fcf) and number(fcf.iloc[-1]) is not None and fcf.iloc[-1]>0 and shares and shares>0 and same else 1.
        st.caption('Five-year discounted equity cash-flow scenarios. Inputs are your assumptions; values are not price predictions. No debt adjustment is applied to this equity cash-flow model.')
        if not same: st.warning('Quote and reporting currencies differ or are missing. Enter a normalized cash-flow figure in the quote currency yourself.')
        with st.form('research_sensitivity_'+ticker):
            cash=st.number_input('Normalized annual equity cash flow per share',min_value=.01,value=default,key='research_cash_'+ticker)
            growth=st.number_input('Five-year annual growth (%)',min_value=-90.,max_value=100.,value=5.,key='research_growth_'+ticker)
            discount=st.number_input('Required return (%)',min_value=.1,max_value=100.,value=10.,key='research_discount_'+ticker)
            terminal=st.number_input('Long-run growth (%)',min_value=-10.,max_value=10.,value=2.,key='research_terminal_'+ticker)
            calculate=st.form_submit_button('Show valuation sensitivity')
        if calculate:
            try: st.session_state['research_sensitivity_result_'+ticker]=sensitivity(cash,growth/100,discount/100,terminal/100)
            except ValueError as exc: st.error(str(exc));st.session_state.pop('research_sensitivity_result_'+ticker,None)
        if 'research_sensitivity_result_'+ticker in st.session_state:
            st.dataframe(st.session_state['research_sensitivity_result_'+ticker].round(2),width='stretch')
        st.caption('The default cash-flow input, when available, is latest annual operating cash flow less capital expenditure divided by current shares. Normalize one-offs, debt funding and share-count changes yourself. Not suited to banks or insurers without a sector-specific model. Empty cells have invalid terminal/discount assumptions.')
    with tabs[3]:
        frame=allocation(bundle['income'],bundle['cashflow'],bundle['balance'])
        if frame.empty: st.info('Capital-allocation statements unavailable.')
        else:
            display=frame.copy();money=[c for c in display if '%' not in c and 'shares' not in c.lower()]
            display[money]=display[money]/1e6;display.index=display.index.strftime('%Y-%m-%d')
            st.caption(f"Annual cash amounts in millions of {info.get('financialCurrency','reporting currency')}; diluted shares are share counts, ratios are percentages.")
            st.dataframe(display.round(2),width='stretch')
            last=frame.iloc[-1]
            if number(last['Share count change %']) is not None and last['Share count change %']>0: st.warning('Diluted average shares increased: assess whether repurchases offset employee awards and new issuance.')
            if number(last['Dividends + buybacks / FCF %']) is not None and last['Dividends + buybacks / FCF %']>100: st.warning('Dividends plus repurchases exceeded annual free cash flow. Check cash reserves, debt funding and sustainability.')
        st.caption('Acquisition cash flow is signed: negative normally represents a net cash outflow. Blank fields mean unavailable. Buybacks do not prove value creation; assess the price paid, dilution and alternative uses of cash.')
