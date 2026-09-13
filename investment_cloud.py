"""User-authenticated Supabase notebook storage; never uses a service-role key."""
import base64
import json
import re
import time
from uuid import UUID
import requests
from investment_workspace import load_notebook, export_notebook


class CloudError(ValueError): pass


def config(url,key):
    url=url.rstrip('/')
    if not re.fullmatch(r'https://[a-z0-9-]+\.supabase\.co',url): raise CloudError('Configure a valid Supabase project URL in Streamlit Secrets.')
    if key.startswith('sb_secret_'): raise CloudError('Use a publishable key, never a secret or service-role key.')
    if not key.startswith('sb_publishable_'):
        try:
            payload=key.split('.')[1]; claims=json.loads(base64.urlsafe_b64decode(payload+'='*(-len(payload)%4)))
            if claims.get('role')!='anon': raise ValueError()
        except Exception: raise CloudError('Use a Supabase publishable key or legacy anon key.') from None
    return url,key


def api(url,key,path,method='GET',token=None,payload=None):
    url,key=config(url,key)
    headers={'apikey':key,'Content-Type':'application/json'}
    if token: headers['Authorization']='Bearer '+token
    try:
        r=requests.request(method,url+path,headers=headers,json=payload,timeout=20,allow_redirects=False)
    except requests.RequestException: raise CloudError('Account service is unreachable. Your local notebook is unchanged.') from None
    if not 200<=r.status_code<300:
        if r.status_code in (401,403): raise CloudError('Sign-in expired or access denied. Sign in again.')
        if r.status_code==409 or (r.status_code==400 and 'notebook_conflict' in r.text): raise CloudError('Another device changed this notebook. Download your local copy, then load the cloud version before saving again.')
        raise CloudError('Account request failed. Check your sign-in and database setup; your local notebook is unchanged.')
    return r.json() if r.content else None


def sign_in(url,key,email,password):
    data=api(url,key,'/auth/v1/token?grant_type=password','POST',payload={'email':email,'password':password})
    return session(data)


def session(data):
    if not isinstance(data,dict) or not data.get('access_token') or not data.get('user',{}).get('id'): raise CloudError('The account service returned an invalid sign-in session.')
    try: UUID(data['user']['id'])
    except (ValueError,TypeError): raise CloudError('Invalid account identity.') from None
    return {'access_token':data['access_token'],'refresh_token':data.get('refresh_token'),'expires_at':time.time()+float(data.get('expires_in',3600)),
            'user_id':data['user']['id'],'email':data['user'].get('email','')}


def fresh_session(url,key,current):
    if current['expires_at']>time.time()+60: return current
    updated=session(api(url,key,'/auth/v1/token?grant_type=refresh_token','POST',payload={'refresh_token':current['refresh_token']}))
    if updated['user_id']!=current['user_id']: raise CloudError('Account identity changed. Sign out and sign in again.')
    return updated


def load_cloud(url,key,current):
    owner=str(UUID(current['user_id']))
    rows=api(url,key,'/rest/v1/investment_notebooks?select=payload,version,user_id&user_id=eq.'+owner,token=current['access_token'])
    if not rows: return {},0
    if len(rows)!=1 or rows[0].get('user_id')!=owner: raise CloudError('Database access rules are misconfigured; notebook loading was stopped.')
    return load_notebook(json.dumps(rows[0]['payload']))['companies'],int(rows[0]['version'])


def save_cloud(url,key,current,companies,version):
    payload=json.loads(export_notebook(companies))
    result=api(url,key,'/rest/v1/rpc/save_investment_notebook','POST',token=current['access_token'],payload={'expected_version':version,'new_payload':payload})
    return int(result)
