"""US universe source with a reliable liquid-stock fallback if Nasdaq is unavailable."""
from __future__ import annotations
import requests

FALLBACK = "AAPL MSFT NVDA AMZN GOOGL META TSLA AVGO BRK-B JPM V UNH XOM LLY MA JNJ WMT PG HD CVX MRK COST ABBV KO NFLX AMD CRM BAC ORCL PEP TMO LIN ACN MCD CSCO DIS ABT DHR WFC TXN PM GE IBM QCOM CAT AMGN NOW INTU ISRG VZ AMAT SPGI GS BKNG SCHW BLK ADP GILD MDLZ SYK DE DECK PANW PLTR CRWD MU LRCX KLAC MELI MSTR SHOP UBER ABNB ROKU SNOW SQ COIN HOOD RBLX RIVN NIO F GM BA T GT NKE SBUX LOW TGT CVS CI HUM CHTR CMCSA TFC USB PNC AXP C OPCH RCL CCL DAL UAL AAL MAR HLT WYNN LVS NEM FCX NUC X MEET SLB OXY MPC PSX KMI EOG DVN PXD HAL BKR SOFI AFRM NET DDOG MDB ZS OKTA PATH DOCU TWLO ZM PYPL EBAY ETSY DKNG MGM PENN CELH CAVA CPNG PDD BABA JD BIDU WBD PARA EA TTWO RDDT".split()

def load_universe(broad: bool = True) -> list[str]:
    if not broad: return sorted(set(FALLBACK))
    url = "https://api.nasdaq.com/api/screener/stocks?tableonly=true&limit=5000&download=true"
    try:
        response = requests.get(url, headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"}, timeout=12)
        rows = response.json()["data"]["table"]["rows"]
        symbols = [str(r.get("symbol", "")).replace(".", "-").upper() for r in rows if r.get("symbol") and r.get("marketCategory")]
        return sorted(set(s for s in symbols if s.replace("-", "").isalnum())) or sorted(set(FALLBACK))
    except (requests.RequestException, KeyError, TypeError, ValueError):
        return sorted(set(FALLBACK))

