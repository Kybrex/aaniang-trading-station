"""Optional sign-in and explicit cloud save/load for private investment notebooks."""
import streamlit as st
from investment_cloud import CloudError, config, sign_in, fresh_session, load_cloud, save_cloud, api


def setting(name):
    try: return str(st.secrets.get(name,''))
    except Exception: return ''


def render():
    with st.expander('Account and cross-device saving'):
        url,key=setting('SUPABASE_URL'),setting('SUPABASE_PUBLISHABLE_KEY')
        if not url or not key:
            st.info('Account saving is not configured yet. Notebook download and restore remain available.')
            st.link_button('Account setup instructions','https://github.com/Kybrex/aaniang-trading-station/blob/main/CLOUD_SETUP.md')
            return
        try: config(url,key)
        except CloudError as exc: st.error(str(exc)); return
        current=st.session_state.get('investment_account')
        if not current:
            st.caption('Sign in with an account created in the Aaniang Supabase project. Credentials are sent only to that configured account service.')
            with st.form('cloud_signin',clear_on_submit=True):
                email=st.text_input('Account email')
                password=st.text_input('Account password',type='password')
                submit=st.form_submit_button('Sign in')
            if submit:
                try:
                    st.session_state.investment_account=sign_in(url,key,email,password)
                    st.session_state.pop('cloud_version',None)
                    st.rerun()
                except CloudError as exc: st.error(str(exc))
            return
        st.write('Signed in as '+current['email'])
        st.caption('Load your cloud notebook first, then save changes explicitly. Concurrent edits from another device are detected. Download a backup before replacing local notes.')
        replace=st.checkbox('Replace this session’s notes with my cloud notebook',key='cloud_replace')
        if st.button('Load cloud notebook',disabled=not replace):
            try:
                current=fresh_session(url,key,current); st.session_state.investment_account=current
                book,version=load_cloud(url,key,current)
                st.session_state.investment_book=book; st.session_state.cloud_version=version
                for k in list(st.session_state):
                    if k.startswith(('iw_edit_','research_guidance_','research_warning_rows')): del st.session_state[k]
                st.rerun()
            except CloudError as exc: st.error(str(exc))
        if st.button('Save notebook to my account',disabled='cloud_version' not in st.session_state):
            try:
                current=fresh_session(url,key,current); st.session_state.investment_account=current
                st.session_state.cloud_version=save_cloud(url,key,current,st.session_state.get('investment_book',{}),st.session_state.cloud_version)
                st.success('Notebook saved. Sign in on another device and load it there.')
            except (CloudError,ValueError) as exc: st.error(str(exc))
        if st.button('Sign out and clear this session’s investment notes'):
            try: api(url,key,'/auth/v1/logout','POST',token=current['access_token'])
            except CloudError: pass
            for k in list(st.session_state):
                if k.startswith(('iw_','cloud_','investment_','research_')): del st.session_state[k]
            st.rerun()
