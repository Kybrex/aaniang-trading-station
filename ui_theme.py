"""AANIANG financial-terminal visual system."""
from __future__ import annotations

import streamlit as st


THEME_CSS = r"""
<style>
:root {
  --aa-navy: #172b4d;
  --aa-blue: #245a8d;
  --aa-teal: #0f7b75;
  --aa-green: #17845c;
  --aa-red: #c44343;
  --aa-gold: #d89b2b;
  --aa-ink: #17202a;
  --aa-muted: #5c6b7a;
  --aa-line: #ccd4dc;
  --aa-panel: #ffffff;
  --aa-canvas: #eef1f4;
}

html, body, [class*="css"] {
  font-family: Inter, ui-sans-serif, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}

.stApp, [data-testid="stAppViewContainer"] {
  color: var(--aa-ink);
  background:
    linear-gradient(180deg, #e7ebef 0, var(--aa-canvas) 190px, #f5f7f9 100%);
}

[data-testid="stHeader"] {
  background: rgba(238, 241, 244, 0.88);
  backdrop-filter: blur(10px);
  border-bottom: 1px solid rgba(23, 43, 77, 0.12);
}

.block-container {
  max-width: 1580px;
  padding-top: 3.9rem;
  padding-bottom: 5rem;
}

h1, h2, h3 { letter-spacing: -0.025em; }
h1 {
  color: var(--aa-navy) !important;
  font-size: clamp(1.65rem, 3vw, 2.35rem) !important;
  font-weight: 800 !important;
  margin-bottom: 0 !important;
}
h2 {
  color: #fff !important;
  background: linear-gradient(105deg, var(--aa-navy), #284d73);
  border-left: 5px solid #27a69a;
  border-radius: 6px;
  padding: 0.62rem 0.85rem !important;
  margin: 1.6rem 0 0.75rem !important;
  font-size: clamp(1.08rem, 2vw, 1.38rem) !important;
  box-shadow: 0 4px 14px rgba(23, 43, 77, 0.12);
}
h3 {
  color: var(--aa-navy) !important;
  background: #e4e9ee;
  border: 1px solid var(--aa-line);
  border-left: 4px solid var(--aa-blue);
  border-radius: 5px;
  padding: 0.48rem 0.7rem !important;
  margin-top: 1rem !important;
  font-size: 1.02rem !important;
}

p, label, [data-testid="stCaptionContainer"] { color: var(--aa-ink); }
[data-testid="stCaptionContainer"], .stCaption { color: var(--aa-muted) !important; }
hr { border-color: #c7d0d9 !important; margin: 1.25rem 0 !important; }

[data-testid="stMetric"] {
  background: linear-gradient(180deg, #fff, #f8fafb);
  border: 1px solid var(--aa-line);
  border-top: 3px solid var(--aa-blue);
  border-radius: 6px;
  padding: 0.72rem 0.8rem;
  box-shadow: 0 2px 7px rgba(23, 43, 77, 0.06);
}
[data-testid="stMetricLabel"] { color: var(--aa-muted) !important; font-weight: 650; }
[data-testid="stMetricValue"] { color: var(--aa-navy) !important; font-weight: 780; }

[data-testid="stForm"], [data-testid="stExpander"], [data-testid="stVerticalBlockBorderWrapper"] {
  background: rgba(255,255,255,0.92);
  border-color: var(--aa-line) !important;
  border-radius: 6px !important;
  box-shadow: 0 2px 8px rgba(23, 43, 77, 0.045);
}

.stButton > button, .stDownloadButton > button, .stLinkButton > a {
  min-height: 2.35rem;
  border-radius: 5px !important;
  border: 1px solid #aebbc7 !important;
  background: linear-gradient(180deg, #ffffff, #e8edf2) !important;
  color: var(--aa-navy) !important;
  font-weight: 700 !important;
  box-shadow: 0 1px 2px rgba(23, 43, 77, 0.08);
  transition: transform .12s ease, border-color .12s ease, box-shadow .12s ease;
}
.stButton > button:hover, .stDownloadButton > button:hover, .stLinkButton > a:hover {
  border-color: var(--aa-blue) !important;
  color: var(--aa-blue) !important;
  box-shadow: 0 3px 9px rgba(36, 90, 141, 0.16);
  transform: translateY(-1px);
}
.stButton > button[kind="primary"], .stFormSubmitButton > button[kind="primary"] {
  color: #fff !important;
  border-color: #173f67 !important;
  background: linear-gradient(180deg, #3274ab, #245a8d) !important;
}
[data-testid="stBaseButton-primary"], [data-testid="stFormSubmitButton"] button {
  color: #fff !important;
  border-color: #173f67 !important;
  background: linear-gradient(180deg, #3274ab, #245a8d) !important;
}
[data-testid="stBaseButton-primary"] p, [data-testid="stFormSubmitButton"] button p {
  color: #fff !important;
}

[data-baseweb="input"] > div, [data-baseweb="select"] > div,
[data-baseweb="textarea"] > div, [data-testid="stNumberInputContainer"] {
  background: #fff !important;
  border-color: #aebbc7 !important;
  border-radius: 4px !important;
}
input, textarea { color: var(--aa-ink) !important; }

[data-testid="stDataFrame"], [data-testid="stTable"] {
  background: #fff;
  border: 1px solid #bfc9d3;
  border-radius: 5px;
  overflow: hidden;
  box-shadow: 0 2px 7px rgba(23,43,77,.055);
}
[data-testid="stDataFrame"] { font-size: 0.83rem; }

[data-baseweb="tab-list"] {
  gap: 0.2rem;
  background: #dfe5eb;
  border: 1px solid #c4ced7;
  border-radius: 5px;
  padding: 0.22rem;
}
[data-baseweb="tab"] {
  height: 2.45rem;
  border-radius: 4px;
  color: #34495e !important;
  font-weight: 700;
  padding-left: 0.8rem !important;
  padding-right: 0.8rem !important;
}
[aria-selected="true"][data-baseweb="tab"] {
  color: #fff !important;
  background: var(--aa-blue) !important;
}
button[role="tab"][aria-selected="true"] {
  color: #fff !important;
  background: var(--aa-blue) !important;
}
button[role="tab"][aria-selected="true"] p { color: #fff !important; }

[data-testid="stAlert"] { border-radius: 5px; border-width: 1px; }
[data-testid="stProgress"] > div > div { background-color: var(--aa-teal) !important; }

[data-testid="stSidebar"] {
  background: #e2e7ec;
  border-right: 1px solid #bcc7d1;
}
[data-testid="stSidebar"] h2 {
  background: transparent;
  color: var(--aa-navy) !important;
  border: 0;
  box-shadow: none;
  padding-left: 0 !important;
}

/* Compact module launchers read like a financial navigation grid. */
[data-testid="stColumn"] .stButton > button {
  font-size: 0.82rem;
  line-height: 1.15;
}

@media (max-width: 720px) {
  .block-container { padding: 3.45rem 0.6rem 4rem; }
  h1 { font-size: 1.55rem !important; }
  h2 { font-size: 1.02rem !important; padding: .55rem .65rem !important; }
  h3 { font-size: .96rem !important; }
  [data-testid="stMetric"] { padding: .55rem .6rem; }
  [data-testid="stColumn"] .stButton > button {
    min-height: 3rem;
    padding: .35rem .3rem;
    font-size: .74rem;
  }
  [data-baseweb="tab-list"] { overflow-x: auto; flex-wrap: nowrap; }
}
</style>
"""


def apply_theme() -> None:
    st.markdown(THEME_CSS, unsafe_allow_html=True)
    st.markdown(
        """
        <div style="display:flex;align-items:center;justify-content:space-between;gap:12px;
                    background:#172b4d;color:white;border-radius:6px;padding:8px 12px;
                    margin:0 0 12px;border-bottom:3px solid #27a69a;font-size:12px;font-weight:700;">
          <span>AANIANG MARKET INTELLIGENCE</span>
          <span style="color:#9edbd5;">RESEARCH • RISK • DECISIONS</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

