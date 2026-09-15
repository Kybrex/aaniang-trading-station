"""Evidence-led investment report. Pure calculations; no network or UI calls."""
from __future__ import annotations
from datetime import datetime, timezone
import math
import pandas as pd


def num(value):
    try:
        result = float(value)
        return result if math.isfinite(result) else None
    except (ValueError, TypeError):
        return None


def fmt(value, suffix=""):
    value = num(value)
    return "Unavailable" if value is None else f"{value:,.2f}{suffix}"


def sector_model(snapshot):
    industry = str(snapshot.get("Industry", "")).lower()
    sector = str(snapshot.get("Sector", "")).lower()
    if "bank" in industry: return "Bank"
    if "insurance" in industry: return "Insurer"
    if "reit" in industry: return "REIT"
    if "financial" in sector: return "Financial services"
    return "Operating company"


DEFAULTS = dict(growth=5.0, discount=10.0, terminal_growth=2.5, exit_multiple=18.0,
                margin_safety=25.0, years=5, portfolio_value=0.0, planned_amount=0.0,
                position_cap=5.0, loss_budget=1.0, ffo_per_share=None, book_per_share=None)


def assumptions(values=None):
    result = {**DEFAULTS, **(values or {})}
    for key in DEFAULTS:
        if key in ("ffo_per_share", "book_per_share") and result[key] is None: continue
        value = num(result[key])
        if value is None: raise ValueError(f"{key} must be a finite number.")
        result[key] = value
    if result["years"] != int(result["years"]) or not 1 <= result["years"] <= 15:
        raise ValueError("Investment horizon must be 1 to 15 whole years.")
    result["years"] = int(result["years"])
    if not -40 <= result["growth"] <= 40: raise ValueError("Growth must be between -40% and 40%.")
    if not 0 < result["discount"] <= 40 or not -5 <= result["terminal_growth"] < result["discount"]:
        raise ValueError("Discount rate must be positive and exceed terminal growth.")
    if not 0 < result["exit_multiple"] <= 100: raise ValueError("Exit multiple must be positive and at most 100.")
    if not 0 <= result["margin_safety"] < 100: raise ValueError("Margin of safety must be below 100%.")
    if min(result["portfolio_value"], result["planned_amount"]) < 0: raise ValueError("Portfolio values cannot be negative.")
    if not 0 < result["position_cap"] <= 100 or not 0 < result["loss_budget"] <= 100:
        raise ValueError("Portfolio limits must be above 0% and at most 100%.")
    for key in ("ffo_per_share", "book_per_share"):
        if result[key] is not None and result[key] <= 0: raise ValueError(f"{key} must be positive or blank.")
    return result


def dcf_per_share(cash, growth, discount, terminal, years):
    if cash is None or cash <= 0 or discount <= terminal: return None
    g, r, t = growth/100, discount/100, terminal/100
    return sum(cash*(1+g)**y/(1+r)**y for y in range(1, years+1)) + cash*(1+g)**years*(1+t)/(r-t)/(1+r)**years


def latest(trends, key):
    if trends.empty or key not in trends: return None
    # Use the latest annual period; never silently mix different financial years.
    return num(trends.sort_values("Year").iloc[-1][key])


def valuation(snapshot, trends, inputs):
    a = assumptions(inputs); model = sector_model(snapshot)
    price = num(snapshot.get("Price")); eps = num(snapshot.get("Trailing EPS"))
    shares = latest(trends, "Diluted shares"); fcf = latest(trends, "Free cash flow")
    same_currency = snapshot.get("Financial currency") == snapshot.get("Currency") and bool(snapshot.get("Currency"))
    cash = fcf/shares if fcf is not None and shares and shares > 0 and same_currency else None
    book = a["book_per_share"] or num(snapshot.get("Book value/share"))
    selected = "Earnings multiple"
    base_unit = eps
    if model == "REIT": selected, base_unit = "FFO multiple", a["ffo_per_share"]
    elif model in ("Bank", "Insurer", "Financial services"):
        selected, base_unit = "Earnings multiple", eps
    elif cash is not None and cash > 0: selected, base_unit = "Cash-flow sensitivity", cash
    rows=[]; models=[]
    for name, change, multiple in [("Bear", -5, .75), ("Base", 0, 1), ("Bull", 5, 1.25)]:
        growth = a["growth"]+change; exit_mult = a["exit_multiple"]*multiple
        terminal_price = base_unit*(1+growth/100)**a["years"]*exit_mult if base_unit and base_unit > 0 else None
        if selected == "Cash-flow sensitivity":
            fair = dcf_per_share(base_unit, growth, a["discount"], a["terminal_growth"], a["years"])
            terminal_price = base_unit*(1+growth/100)**a["years"]*(1+a["terminal_growth"]/100)/((a["discount"]-a["terminal_growth"])/100)
        else:
            fair = terminal_price/(1+a["discount"]/100)**a["years"] if terminal_price else None
        annual = ((terminal_price/price)**(1/a["years"])-1)*100 if terminal_price and price and price>0 else None
        rows.append({"Scenario":name,"Growth %":growth,"Fair value today":fair,"Horizon price":terminal_price,
                     "Annual price return %":annual,"Price change %":(terminal_price/price-1)*100 if terminal_price and price and price>0 else None})
    if eps and eps>0 and model != "REIT":
        models.append({"Method":"Earnings multiple", "Value today":eps*(1+a["growth"]/100)**a["years"]*a["exit_multiple"]/(1+a["discount"]/100)**a["years"],"Basis":"Reported trailing EPS; assumed growth and exit P/E"})
    if model == "Operating company" and cash and cash>0:
        models.append({"Method":"Cash-flow sensitivity", "Value today":dcf_per_share(cash,a["growth"],a["discount"],a["terminal_growth"],a["years"]),"Basis":"Annual FCF / diluted shares; levered cash proxy, not audited FCFE"})
    if model in ("Bank", "Insurer", "Financial services") and book and book>0:
        roe = num(snapshot.get("ROE"))
        sustainable = book*(roe-a["terminal_growth"])/(a["discount"]-a["terminal_growth"]) if roe is not None and roe>a["terminal_growth"] else None
        models.append({"Method":"Stable return on equity", "Value today":sustainable,"Basis":"Book value x (ROE - growth)/(cost of equity - growth); assumes sustainable ROE"})
    if model=="REIT": models.append({"Method":"FFO multiple", "Value today":rows[1]["Fair value today"],"Basis":"User-sourced FFO/share; assumed growth and exit P/FFO"})
    reverse = None
    if price and price>0 and base_unit and base_unit>0:
        if selected == "Cash-flow sensitivity":
            lo,hi=-50.,100.
            if dcf_per_share(base_unit,lo,a["discount"],a["terminal_growth"],a["years"]) <= price <= dcf_per_share(base_unit,hi,a["discount"],a["terminal_growth"],a["years"]):
                for _ in range(80):
                    mid=(lo+hi)/2
                    if dcf_per_share(base_unit,mid,a["discount"],a["terminal_growth"],a["years"])<price: lo=mid
                    else: hi=mid
                reverse=(lo+hi)/2
        else:
            reverse=((price*(1+a["discount"]/100)**a["years"]/(base_unit*a["exit_multiple"]))**(1/a["years"])-1)*100
    base=rows[1]["Fair value today"]
    return dict(model=selected, sector=model, scenarios=pd.DataFrame(rows), models=pd.DataFrame(models),
                reverse_growth=reverse, fair_value=base, buy_price=base*(1-a["margin_safety"]/100) if base else None,
                note="Scenario assumptions are editable research inputs, not forecasts or probabilities. Annual price returns exclude dividends, tax and costs. FCF is after interest but before net borrowing; the cash-flow model is a sensitivity estimate and requires capital-structure review.")


def financial_checks(snapshot, trends):
    rows=[]; financial=sector_model(snapshot) in ("Bank","Insurer","Financial services")
    def add(name, value, bad, detail):
        rows.append({"Check":name,"Value":value,"Status":"Insufficient evidence" if value is None else "Review" if bad(value) else "No threshold breach","Rule / limitation":detail})
    ni, ocf = latest(trends,"Net income"), latest(trends,"Operating cash flow")
    conversion=ocf/ni if ocf is not None and ni is not None and ni>0 and not financial else None
    add("Cash conversion",conversion,lambda x:x<.8,"OCF/net income below 0.8; not used for financial firms or losses")
    fcf=latest(trends,"Free cash flow") if not financial else None
    add("Annual free cash flow",fcf,lambda x:x<0,"Negative cash flow requires funding review; financial firms require regulatory capital analysis")
    revenue=latest(trends,"Revenue"); sbc=latest(trends,"Stock compensation")
    add("Stock compensation / revenue %",100*sbc/revenue if sbc is not None and revenue and revenue>0 else None,lambda x:x>10,"Review above 10%; a research threshold, not an accounting verdict")
    ordered=trends.sort_values("Year") if not trends.empty else trends
    dilution=None; receivable_gap=None
    if len(ordered)>=2:
        before,after=ordered.iloc[-2],ordered.iloc[-1]
        s0,s1=num(before.get("Diluted shares")),num(after.get("Diluted shares"))
        if s0 and s0>0 and s1 is not None: dilution=(s1/s0-1)*100
        r0,r1=num(before.get("Revenue")),num(after.get("Revenue")); d0,d1=num(before.get("Receivables")),num(after.get("Receivables"))
        if r0 and r0>0 and d0 and d0>0 and r1 is not None and d1 is not None: receivable_gap=(d1/d0-r1/r0)*100
    add("Diluted share growth %",dilution,lambda x:x>2,"Review annual dilution above 2%; check acquisitions and share splits")
    add("Receivables growth less revenue growth (pp)",receivable_gap,lambda x:x>10,"Review gap above 10 percentage points; investigate collection timing")
    add("Debt / equity %",num(snapshot.get("Debt/Equity")) if not financial else None,lambda x:x>150,"Review above 150%; not comparable for financial firms or negative equity")
    add("Debt maturity schedule",None,lambda x:False,"Requires latest filing debt footnote; aggregate debt does not establish refinancing safety")
    add("Adjusted earnings reconciliation",None,lambda x:False,"Review GAAP/adjusted differences in the company earnings release")
    return pd.DataFrame(rows)


def moat_analysis(snapshot, trends, evidence=None):
    evidence=pd.DataFrame() if evidence is None else evidence
    rows=[]
    questions={"Pricing power":"Compare price increases, retention and gross margins with peers.","Switching costs":"Look for renewal rates, churn and costs of migration.","Network effects":"Verify that added users improve value for other users.","Cost advantage":"Compare unit costs and capital efficiency across a cycle.","Intangible assets":"Verify brands, patents, licenses and expiration risks."}
    for factor,question in questions.items():
        match=evidence[evidence["Factor"].eq(factor)] if not evidence.empty and "Factor" in evidence else pd.DataFrame()
        item=match.iloc[0] if not match.empty else {}
        sourced=bool(pd.notna(item.get("Evidence")) and pd.notna(item.get("Source")) and str(item.get("Evidence","")).strip() and str(item.get("Source","")).strip())
        rows.append({"Factor":factor,"Assessment":str(item.get("Assessment","Unassessed")) if sourced else "Insufficient evidence",
                     "Evidence / next check":str(item.get("Evidence")) if sourced else question,
                     "Source":str(item.get("Source","")) if sourced else "Not supplied"})
    return pd.DataFrame(rows)


def peer_view(snapshot, universe):
    if universe is None or universe.empty or "Symbol" not in universe: return pd.DataFrame(),"No peer data loaded. Supply 3-5 same-industry peers."
    peers=universe[universe.Symbol.ne(snapshot.get("Symbol"))].drop_duplicates("Symbol").copy()
    same=peers[peers.Industry.eq(snapshot.get("Industry"))] if "Industry" in peers and snapshot.get("Industry") not in (None,"Unknown","") else pd.DataFrame()
    note="Same-industry peers; compare business mix, geography and accounting before drawing conclusions."
    if same.empty:
        same=peers[peers.Sector.eq(snapshot.get("Sector"))] if "Sector" in peers and snapshot.get("Sector") not in (None,"Unknown","") else pd.DataFrame()
        note="Sector substitutes only; these are not necessarily direct competitors."
    view=pd.concat([pd.DataFrame([snapshot]),same.head(5)],ignore_index=True)
    fields=[c for c in ["Symbol","Industry","ROE","Operating margin","Revenue growth","Forward P/E","Debt/Equity","Currency"] if c in view]
    return view[fields],note


def portfolio_fit(snapshot, valuation_result, a, holdings=None):
    a=assumptions(a); total=a["portfolio_value"]; planned=a["planned_amount"]
    if total<=0: return pd.DataFrame([{"Measure":"Portfolio fit","Result":"Enter total portfolio value and holdings to calculate exposure."}])
    if planned>total: raise ValueError("Planned amount exceeds portfolio value; enter a cash-funded amount within the portfolio.")
    holdings=pd.DataFrame() if holdings is None else holdings.copy()
    existing=sector=0.; known=0.
    if not holdings.empty:
        if not {"Symbol","Sector","Value"}.issubset(holdings): raise ValueError("Holdings need Symbol, Sector and Value columns.")
        holdings=holdings.dropna(subset=["Symbol","Value"])
        values=holdings.Value.map(num)
        if values.isna().any() or (values<0).any(): raise ValueError("Holding values must be finite and non-negative.")
        holdings["Value"]=values; known=float(values.sum())
        if known+planned>total+.01: raise ValueError("Holdings plus the planned purchase exceed portfolio value. Include available cash in the total.")
        existing=float(holdings.loc[holdings.Symbol.astype(str).str.upper().eq(snapshot.get("Symbol")),"Value"].sum())
        sector=float(holdings.loc[holdings.Sector.eq(snapshot.get("Sector")),"Value"].sum())
    price=num(snapshot.get("Price")); bear=valuation_result["scenarios"].iloc[0]["Fair value today"]
    downside=max(0,1-bear/price) if num(bear) is not None and price and price>0 else None
    cap=max(0,total*a["position_cap"]/100-existing)
    loss_cap=max(0,total*a["loss_budget"]/100/downside-existing) if downside and downside>0 else None
    maximum=min(cap,loss_cap,total-known) if loss_cap is not None else min(cap,total-known)
    rows=[("Existing company exposure %",fmt(existing/total*100)),("After purchase company exposure %",fmt((existing+planned)/total*100)),
          ("Known sector exposure after purchase %",fmt((sector+planned)/total*100)),("Unspecified assets/cash before purchase %",fmt((total-known)/total*100)),
          ("Loss on company holding at bear fair value",fmt((existing+planned)*downside) if downside is not None else "Unavailable"),
          ("Portfolio loss at bear fair value %",fmt((existing+planned)*downside/total*100) if downside is not None else "Unavailable"),
          ("Additional amount within entered limits",fmt(maximum)),("Position limit", "Exceeded" if existing+planned>total*a["position_cap"]/100 else "Within entered limit"),
          ("Currency basis","All holding values and planned amount must be converted to one portfolio currency."),
          ("Coverage","Known direct holdings only; ETF look-through and correlations are not inferred. Bear value is a scenario, not a maximum loss.")]
    return pd.DataFrame(rows,columns=["Measure","Result"])


def thesis_tracker(snapshot, trends, previous=None):
    current={"Price":num(snapshot.get("Price")),"Revenue growth %":num(snapshot.get("Revenue growth")),
             "Operating margin %":num(snapshot.get("Operating margin")),"Free cash flow":latest(trends,"Free cash flow"),
             "Diluted shares":latest(trends,"Diluted shares")}
    prior=previous.get("observations",{}) if previous and previous.get("symbol")==snapshot.get("Symbol") else {}
    triggers={"Price":"Reassess margin of safety after a material price move.","Revenue growth %":"Review thesis if growth turns negative.",
              "Operating margin %":"Review a decline of 3 percentage points or more.","Free cash flow":"Investigate negative annual FCF; use regulatory capital for financial firms.",
              "Diluted shares":"Review an increase above 2% between annual observations."}
    rows=[]
    for key,value in current.items():
        old=num(prior.get(key)); delta=value-old if value is not None and old is not None else None
        breached=(key=="Revenue growth %" and value is not None and value<0) or (key=="Operating margin %" and delta is not None and delta<=-3) or (key=="Free cash flow" and value is not None and value<0 and sector_model(snapshot)=="Operating company") or (key=="Diluted shares" and old is not None and old>0 and value is not None and value/old>1.02)
        rows.append({"Metric":key,"Current":value,"Previous":old,"Change":delta,"Status":"Review triggered" if breached else "Insufficient evidence" if value is None else "Baseline saved" if old is None else "No trigger", "Review condition":triggers[key]})
    return pd.DataFrame(rows),current


def build_decision_report(report, inputs=None, holdings=None, evidence=None, previous=None):
    a=assumptions(inputs); s=report["snapshot"]; trends=report.get("financial_trends",pd.DataFrame())
    val=valuation(s,trends,a); checks=financial_checks(s,trends); moat=moat_analysis(s,trends,evidence)
    peers,peer_note=peer_view(s,report.get("decision_peers",report.get("peer_comparison",pd.DataFrame())))
    tracker,observations=thesis_tracker(s,trends,previous)
    missing=[k for k in ["Price","ROE","Operating margin","Revenue growth","Trailing EPS"] if num(s.get(k)) is None]
    years=len(trends); confidence="Limited" if missing or years<3 or val["fair_value"] is None else "Moderate"
    strengths=[]; concerns=[]
    if num(s.get("Revenue growth")) is not None and num(s["Revenue growth"])>0: strengths.append(f"Reported revenue growth is positive ({fmt(s['Revenue growth'],'%')}).")
    if num(s.get("Operating margin")) is not None and num(s["Operating margin"])>0: strengths.append(f"Reported operating margin is positive ({fmt(s['Operating margin'],'%')}).")
    if latest(trends,"Free cash flow") is not None and latest(trends,"Free cash flow")>0 and val["sector"]=="Operating company": strengths.append("Latest annual free cash flow is positive.")
    concerns.extend(checks.loc[checks.Status.eq("Review"),"Check"].tolist())
    if missing: concerns.append("Missing snapshot fields: "+", ".join(missing))
    if years<5: concerns.append(f"Only {years} annual periods returned; a 5-10 year record is not available from this feed.")
    if moat.Assessment.eq("Insufficient evidence").any(): concerns.append("Competitive advantage requires sourced qualitative evidence.")
    if s.get("Financial currency") != s.get("Currency"): concerns.append("Statement and trading currencies differ or are unknown; cash-flow valuation disabled.")
    if val["fair_value"] is None: stance="Insufficient evidence to assess valuation"
    elif num(s.get("Price")) is None: stance="Current price unavailable"
    elif s["Price"]<=val["buy_price"]: stance="Below the assumed margin-of-safety price; investigate risks"
    elif s["Price"]<=val["fair_value"]: stance="Below base fair value, above margin-of-safety price"
    else: stance="Above the base fair-value estimate"
    specialist={"Bank":"Review CET1 capital, net interest margin, nonperforming loans, deposit stability and credit-loss coverage.",
                "Insurer":"Review combined ratio (property/casualty), reserve development, solvency capital and investment-portfolio risk.",
                "REIT":"Review sourced FFO/AFFO per share, occupancy, lease maturities, debt maturity and NAV; GAAP EPS is not the primary valuation input.",
                "Financial services":"Review regulatory capital, funding structure and sustainable ROE; corporate FCF and debt screens are not applied.",
                "Operating company":"Review cash conversion, returns on capital, reinvestment needs, margins and debt maturity."}[val["sector"]]
    generated=report["generated_at"].strftime("%Y-%m-%d %H:%M UTC")
    source=f"https://finance.yahoo.com/quote/{report['symbol']}/"
    sources=pd.DataFrame([
        {"Data / method":"Company snapshot","Source":s.get("Source","Unavailable"),"Link":source,"As of":s.get("Snapshot retrieved",generated),"Type":"Provider data"},
        {"Data / method":"Annual financials","Source":"Yahoo Finance annual statements","Link":source+"financials/","As of":str(trends.Year.max()) if not trends.empty else "Unavailable","Type":"Reported periods; retrieved "+generated},
        {"Data / method":"Valuation","Source":"AANIANG editable assumptions","Link":"https://pages.stern.nyu.edu/~adamodar/New_Home_Page/lectures/val.html","As of":generated,"Type":"Model estimate"},
        {"Data / method":"REIT methodology","Source":"Nareit FFO definition","Link":"https://www.reit.com/glossary/funds-operation-ffo","As of":"Method reference","Type":"Methodology"},
        {"Data / method":"Specialist inputs and moat","Source":str(a.get("specialist_source","Not supplied")),"Link":"User-supplied evidence shown in moat table","As of":generated,"Type":"User research; not independently verified"}])
    result = dict(version=1,symbol=report["symbol"],generated=generated,summary=stance,confidence=confidence,
                strengths=strengths[:3] or ["Insufficient evidence to identify a measured strength."], concerns=concerns[:3] or ["Review sector and valuation assumptions before drawing conclusions."],
                valuation=val,assumptions=a,checks=checks,moat=moat,peers=peers,peer_note=peer_note,
                tracker=tracker,observations=observations,portfolio=portfolio_fit(s,val,a,holdings),specialist=specialist,
                sources=sources,history_note=f"{years} annual periods available; financial units are the provider's statement currency. No missing years are invented.",
                prior_date=previous.get("generated","No previous report") if previous else "No previous report",
                currency=s.get("Currency","Unspecified"), missing=missing)
    from report_extensions import add_extensions
    return add_extensions(report,result,previous)
