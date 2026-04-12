"""
Fundamental analysis engine — standalone, NOT connected to the scoring/signaling system.

Analyzes a stock across 7 silos:
  1. Valuation    — P/E, Forward P/E, PEG, P/S, P/B, EV/EBITDA
  2. Profitability — Margins (gross, operating, net), ROE, ROA + trends
  3. Growth       — Revenue growth, EPS growth, acceleration
  4. Financial Health — Debt/equity, current ratio, interest coverage, FCF
  5. Earnings Quality — Beat rate, surprise %, consistency
  6. Ownership    — Insider activity, institutional holdings
  7. Dividend     — Yield, payout ratio, sustainability

All computations are programmatic. The LLM only narrates the results.
"""
from __future__ import annotations

import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


# ── Safe number parsing ──────────────────────────────────────────────────────

def _safe_float(val, default=None) -> Optional[float]:
    """Convert AV values to float. Handles 'None', '', '-', etc."""
    if val is None or val == "" or val == "None" or val == "-" or val == "N/A":
        return default
    try:
        return float(str(val).replace("%", "").replace(",", ""))
    except (ValueError, TypeError):
        return default


def _safe_int(val, default=None) -> Optional[int]:
    if val is None or val == "" or val == "None" or val == "-":
        return default
    try:
        return int(float(str(val).replace(",", "")))
    except (ValueError, TypeError):
        return default


def _pct(val) -> Optional[float]:
    """Convert AV decimal ratio (e.g. '0.2567') to percentage (25.67)."""
    f = _safe_float(val)
    if f is None:
        return None
    # AV returns ratios < ~1.0 as decimals; actual percentages would be > 1
    if abs(f) < 1.5:
        return round(f * 100, 2)
    return round(f, 2)


def _growth(current, prior) -> Optional[float]:
    """YoY growth rate as percentage."""
    c = _safe_float(current)
    p = _safe_float(prior)
    if c is None or p is None or p == 0:
        return None
    return round((c - p) / abs(p) * 100, 2)


def _ratio(num, den) -> Optional[float]:
    n = _safe_float(num)
    d = _safe_float(den)
    if n is None or d is None or d == 0:
        return None
    return round(n / d, 2)


def _fmt_large(val) -> Optional[str]:
    """Format large numbers (revenue, market cap) for display."""
    f = _safe_float(val)
    if f is None:
        return None
    if abs(f) >= 1e12:
        return f"${f / 1e12:.2f}T"
    if abs(f) >= 1e9:
        return f"${f / 1e9:.2f}B"
    if abs(f) >= 1e6:
        return f"${f / 1e6:.1f}M"
    return f"${f:,.0f}"


# ── Silo 1: Valuation ───────────────────────────────────────────────────────

def analyze_valuation(overview: Dict, current_price: float) -> Dict[str, Any]:
    pe = _safe_float(overview.get("pe_ratio"))
    forward_pe = _safe_float(overview.get("forward_pe"))
    peg = _safe_float(overview.get("peg_ratio"))
    ps = _safe_float(overview.get("price_to_sales"))
    pb = _safe_float(overview.get("price_to_book"))
    ev_ebitda = _safe_float(overview.get("ev_to_ebitda"))
    market_cap = _safe_float(overview.get("market_cap"))
    analyst_target = _safe_float(overview.get("analyst_target_price"))

    metrics = {
        "pe_ratio": pe,
        "forward_pe": forward_pe,
        "peg_ratio": peg,
        "price_to_sales": ps,
        "price_to_book": pb,
        "ev_to_ebitda": ev_ebitda,
        "market_cap": market_cap,
        "market_cap_fmt": _fmt_large(market_cap),
    }

    # Analyst ratings
    ratings_total = 0
    analyst_ratings = {}
    for key, label in [
        ("analyst_strong_buy", "Strong Buy"),
        ("analyst_buy", "Buy"),
        ("analyst_hold", "Hold"),
        ("analyst_sell", "Sell"),
        ("analyst_strong_sell", "Strong Sell"),
    ]:
        v = _safe_int(overview.get(key))
        if v is not None:
            analyst_ratings[label] = v
            ratings_total += v
    if analyst_ratings:
        metrics["analyst_ratings"] = analyst_ratings
        metrics["analyst_ratings_total"] = ratings_total

    if analyst_target and current_price and current_price > 0:
        metrics["analyst_target"] = analyst_target
        metrics["target_upside_pct"] = round((analyst_target - current_price) / current_price * 100, 1)

    # PE compression: forward < trailing means market expects growth
    if pe and forward_pe and pe > 0:
        metrics["pe_compression_pct"] = round((forward_pe - pe) / pe * 100, 1)

    # Scoring
    score = 0
    reasons = []

    if pe is not None:
        if pe < 0:
            score -= 1
            reasons.append(f"Negative P/E ({pe:.1f}) — unprofitable")
        elif pe < 15:
            score += 2
            reasons.append(f"Low P/E ({pe:.1f})")
        elif pe < 25:
            score += 1
            reasons.append(f"Reasonable P/E ({pe:.1f})")
        elif pe > 40:
            score -= 2
            reasons.append(f"High P/E ({pe:.1f})")
        else:
            reasons.append(f"Elevated P/E ({pe:.1f})")

    if peg is not None and peg > 0:
        if peg < 1:
            score += 2
            reasons.append(f"PEG < 1 ({peg:.2f}) — undervalued vs growth")
        elif peg < 2:
            score += 1
            reasons.append(f"Reasonable PEG ({peg:.2f})")
        else:
            score -= 1
            reasons.append(f"High PEG ({peg:.2f})")

    if pb is not None:
        if pb < 1:
            score += 1
            reasons.append(f"Below book value ({pb:.1f}x)")
        elif pb > 15:
            score -= 1
            reasons.append(f"Very high P/B ({pb:.1f}x)")

    if ev_ebitda is not None and ev_ebitda > 0:
        if ev_ebitda < 10:
            score += 1
            reasons.append(f"Low EV/EBITDA ({ev_ebitda:.1f}x)")
        elif ev_ebitda > 25:
            score -= 1
            reasons.append(f"High EV/EBITDA ({ev_ebitda:.1f}x)")

    rating = "attractive" if score >= 3 else "reasonable" if score >= 1 else "fair" if score >= -1 else "expensive"

    return {"metrics": metrics, "rating": rating, "score": score, "reasons": reasons}


# ── Silo 2: Profitability ───────────────────────────────────────────────────

def analyze_profitability(overview: Dict, income: Dict) -> Dict[str, Any]:
    # TTM values from overview — AV always returns as decimals (e.g. 0.25 = 25%)
    # Don't use _pct() for ROE/ROA since they can exceed 1.5 (e.g. 1.478 = 147.8%)
    roe_raw = _safe_float(overview.get("roe"))
    roa_raw = _safe_float(overview.get("roa"))
    roe = round(roe_raw * 100, 2) if roe_raw is not None else None
    roa = round(roa_raw * 100, 2) if roa_raw is not None else None
    profit_margin = _pct(overview.get("profit_margin"))
    operating_margin = _pct(overview.get("operating_margin"))

    # Quarterly margin trends from income statements
    quarterly = income.get("quarterly", [])
    margin_trend = []
    for q in quarterly[:4]:
        rev = _safe_float(q.get("totalRevenue"))
        gp = _safe_float(q.get("grossProfit"))
        op_inc = _safe_float(q.get("operatingIncome"))
        net_inc = _safe_float(q.get("netIncome"))
        entry = {"period": q.get("fiscalDateEnding", "")}
        if rev and rev > 0:
            if gp is not None:
                entry["gross_margin"] = round(gp / rev * 100, 1)
            if op_inc is not None:
                entry["operating_margin"] = round(op_inc / rev * 100, 1)
            if net_inc is not None:
                entry["net_margin"] = round(net_inc / rev * 100, 1)
        margin_trend.append(entry)

    # Use computed quarterly margins if available, else TTM from overview
    latest_gm = margin_trend[0].get("gross_margin") if margin_trend else None
    latest_om = margin_trend[0].get("operating_margin") if margin_trend else None
    latest_nm = margin_trend[0].get("net_margin") if margin_trend else None

    metrics = {
        "gross_margin": latest_gm,
        "operating_margin": latest_om or operating_margin,
        "net_margin": latest_nm or profit_margin,
        "roe": roe,
        "roa": roa,
        "margin_trend": margin_trend,
    }

    # Margin direction
    if len(margin_trend) >= 2:
        first = margin_trend[0].get("gross_margin")
        last = margin_trend[-1].get("gross_margin")
        if first is not None and last is not None:
            metrics["margin_direction"] = "improving" if first > last else "declining" if first < last else "stable"

    # Scoring
    score = 0
    reasons = []

    gm = metrics["gross_margin"]
    if gm is not None:
        if gm > 60:
            score += 2
            reasons.append(f"Excellent gross margin ({gm:.1f}%)")
        elif gm > 40:
            score += 1
            reasons.append(f"Strong gross margin ({gm:.1f}%)")
        elif gm < 20:
            score -= 1
            reasons.append(f"Thin gross margin ({gm:.1f}%)")

    nm = metrics["net_margin"]
    if nm is not None:
        if nm > 20:
            score += 2
            reasons.append(f"High net margin ({nm:.1f}%)")
        elif nm > 10:
            score += 1
            reasons.append(f"Healthy net margin ({nm:.1f}%)")
        elif nm < 0:
            score -= 2
            reasons.append(f"Net loss ({nm:.1f}%)")
        elif nm < 5:
            score -= 1
            reasons.append(f"Thin net margin ({nm:.1f}%)")

    if roe is not None:
        if roe > 25:
            score += 1
            reasons.append(f"Strong ROE ({roe:.1f}%)")
        elif roe < 0:
            score -= 1
            reasons.append(f"Negative ROE ({roe:.1f}%)")

    if metrics.get("margin_direction") == "improving":
        score += 1
        reasons.append("Margins improving over recent quarters")
    elif metrics.get("margin_direction") == "declining":
        score -= 1
        reasons.append("Margins declining over recent quarters")

    rating = "strong" if score >= 3 else "healthy" if score >= 1 else "moderate" if score >= -1 else "weak"

    return {"metrics": metrics, "rating": rating, "score": score, "reasons": reasons}


# ── Silo 3: Growth ───────────────────────────────────────────────────────────

def analyze_growth(income: Dict, earnings: Dict, overview: Dict) -> Dict[str, Any]:
    metrics = {}
    score = 0
    reasons = []

    # Revenue growth from annual income statements
    annual = income.get("annual", [])
    if len(annual) >= 2:
        rev_current = _safe_float(annual[0].get("totalRevenue"))
        rev_prior = _safe_float(annual[1].get("totalRevenue"))
        metrics["revenue_yoy"] = _growth(rev_current, rev_prior)
        metrics["revenue_current"] = _fmt_large(rev_current)
        metrics["revenue_prior"] = _fmt_large(rev_prior)

    # Revenue growth from quarterly (YoY: Q vs same Q last year)
    quarterly = income.get("quarterly", [])
    if len(quarterly) >= 4:
        q_current = _safe_float(quarterly[0].get("totalRevenue"))
        q_yoy = _safe_float(quarterly[3].get("totalRevenue"))  # same quarter last year
        metrics["revenue_qoq_yoy"] = _growth(q_current, q_yoy)

    # Revenue acceleration: is growth speeding up or slowing down?
    if len(quarterly) >= 4:
        revs = []
        for q in quarterly[:4]:
            r = _safe_float(q.get("totalRevenue"))
            if r:
                revs.append(r)
        if len(revs) >= 3:
            recent_growth = _growth(revs[0], revs[1])
            prior_growth = _growth(revs[1], revs[2])
            if recent_growth is not None and prior_growth is not None:
                metrics["revenue_acceleration"] = "accelerating" if recent_growth > prior_growth else "decelerating"

    # EPS growth from earnings
    annual_earnings = earnings.get("annual", [])
    if len(annual_earnings) >= 2:
        eps_current = _safe_float(annual_earnings[0].get("reportedEPS"))
        eps_prior = _safe_float(annual_earnings[1].get("reportedEPS"))
        metrics["eps_yoy"] = _growth(eps_current, eps_prior)

    # Quarterly EPS growth (YoY)
    qe = earnings.get("quarterly", [])
    if len(qe) >= 4:
        q_eps_curr = _safe_float(qe[0].get("reportedEPS"))
        q_eps_yoy = _safe_float(qe[3].get("reportedEPS"))
        metrics["eps_qoq_yoy"] = _growth(q_eps_curr, q_eps_yoy)

    # Net income growth
    if len(annual) >= 2:
        ni_current = _safe_float(annual[0].get("netIncome"))
        ni_prior = _safe_float(annual[1].get("netIncome"))
        metrics["net_income_yoy"] = _growth(ni_current, ni_prior)

    # Overview has quarterly revenue growth
    overview_rev_growth = _pct(overview.get("revenue_growth"))
    if overview_rev_growth is not None:
        metrics["quarterly_revenue_growth_yoy"] = overview_rev_growth

    # Scoring
    rev_g = metrics.get("revenue_yoy") or metrics.get("quarterly_revenue_growth_yoy")
    if rev_g is not None:
        if rev_g > 20:
            score += 2
            reasons.append(f"Strong revenue growth ({rev_g:.1f}% YoY)")
        elif rev_g > 5:
            score += 1
            reasons.append(f"Moderate revenue growth ({rev_g:.1f}% YoY)")
        elif rev_g < -5:
            score -= 2
            reasons.append(f"Revenue declining ({rev_g:.1f}% YoY)")
        elif rev_g < 0:
            score -= 1
            reasons.append(f"Slight revenue decline ({rev_g:.1f}% YoY)")

    eps_g = metrics.get("eps_yoy")
    if eps_g is not None:
        if eps_g > 20:
            score += 2
            reasons.append(f"Strong EPS growth ({eps_g:.1f}% YoY)")
        elif eps_g > 5:
            score += 1
            reasons.append(f"Moderate EPS growth ({eps_g:.1f}% YoY)")
        elif eps_g < -10:
            score -= 1
            reasons.append(f"EPS declining ({eps_g:.1f}% YoY)")

    if metrics.get("revenue_acceleration") == "accelerating":
        score += 1
        reasons.append("Revenue growth accelerating")
    elif metrics.get("revenue_acceleration") == "decelerating":
        reasons.append("Revenue growth decelerating")

    rating = "high growth" if score >= 3 else "growing" if score >= 1 else "stable" if score >= -1 else "declining"

    return {"metrics": metrics, "rating": rating, "score": score, "reasons": reasons}


# ── Silo 4: Financial Health ─────────────────────────────────────────────────

def analyze_financial_health(balance_sheet: Dict, cash_flow: Dict, income: Dict) -> Dict[str, Any]:
    metrics = {}
    score = 0
    reasons = []

    # Most recent quarterly balance sheet
    bs = (balance_sheet.get("quarterly") or balance_sheet.get("annual", [None]))
    latest_bs = bs[0] if bs else {}

    total_assets = _safe_float(latest_bs.get("totalAssets"))
    total_liabilities = _safe_float(latest_bs.get("totalLiabilities"))
    total_equity = _safe_float(latest_bs.get("totalShareholderEquity"))
    current_assets = _safe_float(latest_bs.get("totalCurrentAssets"))
    current_liabilities = _safe_float(latest_bs.get("totalCurrentLiabilities"))
    long_term_debt = _safe_float(latest_bs.get("longTermDebt"))
    short_term_debt = _safe_float(latest_bs.get("shortLongTermDebtTotal")) or _safe_float(latest_bs.get("currentDebt"))
    cash = _safe_float(latest_bs.get("cashAndCashEquivalentsAtCarryingValue")) or _safe_float(latest_bs.get("cashAndShortTermInvestments"))

    total_debt = (long_term_debt or 0) + (short_term_debt or 0)

    # Debt to equity
    de_ratio = _ratio(total_debt, total_equity)
    metrics["debt_to_equity"] = de_ratio

    # Current ratio
    current_ratio = _ratio(current_assets, current_liabilities)
    metrics["current_ratio"] = current_ratio

    # Cash position
    metrics["cash"] = cash
    metrics["cash_fmt"] = _fmt_large(cash)
    metrics["total_debt"] = total_debt if total_debt > 0 else None
    metrics["total_debt_fmt"] = _fmt_large(total_debt) if total_debt > 0 else None

    # Net cash/debt position
    if cash is not None and total_debt is not None:
        net_cash = cash - total_debt
        metrics["net_cash"] = net_cash
        metrics["net_cash_fmt"] = _fmt_large(abs(net_cash))
        metrics["net_position"] = "net cash" if net_cash > 0 else "net debt"

    # Interest coverage from income statement
    latest_inc = (income.get("annual") or [{}])[0]
    op_income = _safe_float(latest_inc.get("operatingIncome"))
    interest_exp = _safe_float(latest_inc.get("interestExpense"))
    if op_income and interest_exp and interest_exp > 0:
        metrics["interest_coverage"] = round(op_income / interest_exp, 1)

    # Free cash flow from cash flow statement
    cf = (cash_flow.get("annual") or cash_flow.get("quarterly", [None]))
    latest_cf = cf[0] if cf else {}
    operating_cf = _safe_float(latest_cf.get("operatingCashflow"))
    capex = _safe_float(latest_cf.get("capitalExpenditures"))
    if operating_cf is not None and capex is not None:
        fcf = operating_cf - abs(capex)
        metrics["free_cash_flow"] = fcf
        metrics["free_cash_flow_fmt"] = _fmt_large(fcf)
    elif operating_cf is not None:
        metrics["free_cash_flow"] = operating_cf
        metrics["free_cash_flow_fmt"] = _fmt_large(operating_cf)

    # FCF margin
    rev = _safe_float(latest_inc.get("totalRevenue"))
    fcf_val = metrics.get("free_cash_flow")
    if fcf_val is not None and rev and rev > 0:
        metrics["fcf_margin"] = round(fcf_val / rev * 100, 1)

    # Scoring
    if de_ratio is not None:
        if de_ratio < 0.5:
            score += 2
            reasons.append(f"Low leverage (D/E {de_ratio:.2f})")
        elif de_ratio < 1.5:
            score += 1
            reasons.append(f"Moderate leverage (D/E {de_ratio:.2f})")
        elif de_ratio > 3:
            score -= 2
            reasons.append(f"High leverage (D/E {de_ratio:.2f})")
        else:
            score -= 1
            reasons.append(f"Elevated leverage (D/E {de_ratio:.2f})")

    if current_ratio is not None:
        if current_ratio > 2:
            score += 1
            reasons.append(f"Strong liquidity (current ratio {current_ratio:.1f})")
        elif current_ratio < 1:
            score -= 2
            reasons.append(f"Liquidity risk (current ratio {current_ratio:.1f})")

    ic = metrics.get("interest_coverage")
    if ic is not None:
        if ic > 10:
            score += 1
            reasons.append(f"Strong interest coverage ({ic:.1f}x)")
        elif ic < 2:
            score -= 1
            reasons.append(f"Tight interest coverage ({ic:.1f}x)")

    if fcf_val is not None:
        if fcf_val > 0:
            score += 1
            reasons.append(f"Positive FCF ({metrics.get('free_cash_flow_fmt', '')})")
        else:
            score -= 1
            reasons.append(f"Negative FCF ({metrics.get('free_cash_flow_fmt', '')})")

    if metrics.get("net_position") == "net cash":
        score += 1
        reasons.append(f"Net cash position ({metrics.get('net_cash_fmt', '')})")

    rating = "strong" if score >= 3 else "healthy" if score >= 1 else "adequate" if score >= -1 else "concerning"

    return {"metrics": metrics, "rating": rating, "score": score, "reasons": reasons}


# ── Silo 5: Earnings Quality ────────────────────────────────────────────────

def analyze_earnings_quality(earnings: Dict) -> Dict[str, Any]:
    metrics = {}
    score = 0
    reasons = []

    quarterly = earnings.get("quarterly", [])
    if not quarterly:
        return {"metrics": {}, "rating": "no data", "score": 0, "reasons": ["No earnings data available"]}

    # Beat/miss history
    beats = 0
    misses = 0
    surprises = []
    history = []

    for q in quarterly[:8]:
        reported = _safe_float(q.get("reportedEPS"))
        estimated = _safe_float(q.get("estimatedEPS"))
        surprise_pct = _safe_float(q.get("surprisePercentage"))

        entry = {
            "date": q.get("reportedDate") or q.get("fiscalDateEnding", ""),
            "reported_eps": reported,
            "estimated_eps": estimated,
            "surprise_pct": surprise_pct,
        }

        if reported is not None and estimated is not None:
            if reported > estimated:
                beats += 1
                entry["result"] = "beat"
            elif reported < estimated:
                misses += 1
                entry["result"] = "miss"
            else:
                entry["result"] = "met"

        if surprise_pct is not None:
            surprises.append(surprise_pct)

        history.append(entry)

    total = beats + misses
    metrics["history"] = history
    metrics["beats"] = beats
    metrics["misses"] = misses
    metrics["total_quarters"] = len(history)

    if total > 0:
        metrics["beat_rate"] = round(beats / total * 100, 1)

    if surprises:
        metrics["avg_surprise_pct"] = round(sum(surprises) / len(surprises), 2)
        # Consistency: are surprises consistently positive?
        positive_surprises = sum(1 for s in surprises if s > 0)
        metrics["positive_surprise_rate"] = round(positive_surprises / len(surprises) * 100, 1)

    # Scoring
    beat_rate = metrics.get("beat_rate")
    if beat_rate is not None:
        if beat_rate >= 80:
            score += 2
            reasons.append(f"Excellent beat rate ({beats}/{total} quarters)")
        elif beat_rate >= 60:
            score += 1
            reasons.append(f"Good beat rate ({beats}/{total} quarters)")
        elif beat_rate < 40:
            score -= 1
            reasons.append(f"Poor beat rate ({beats}/{total} quarters)")

    avg_sur = metrics.get("avg_surprise_pct")
    if avg_sur is not None:
        if avg_sur > 5:
            score += 1
            reasons.append(f"Strong avg surprise (+{avg_sur:.1f}%)")
        elif avg_sur < -5:
            score -= 1
            reasons.append(f"Negative avg surprise ({avg_sur:.1f}%)")

    rating = "excellent" if score >= 3 else "reliable" if score >= 1 else "mixed" if score >= -1 else "unreliable"

    return {"metrics": metrics, "rating": rating, "score": score, "reasons": reasons}


# ── Silo 6: Ownership ───────────────────────────────────────────────────────

def analyze_ownership(insider_txns: List[Dict], institutional: Dict) -> Dict[str, Any]:
    metrics = {}
    score = 0
    reasons = []

    # Insider transactions — look at recent buys vs sells
    net_buys = 0
    net_sells = 0
    net_shares = 0
    recent_txns = []

    for txn in (insider_txns or [])[:20]:
        acq_disp = txn.get("acquisition_or_disposal", "").upper()
        shares = _safe_int(txn.get("shares"))
        if shares is None:
            continue

        entry = {
            "owner": txn.get("owner_name", "Unknown"),
            "type": "buy" if acq_disp == "A" else "sell" if acq_disp == "D" else acq_disp,
            "shares": shares,
            "date": txn.get("transaction_date", ""),
        }
        recent_txns.append(entry)

        if acq_disp == "A":
            net_buys += 1
            net_shares += shares
        elif acq_disp == "D":
            net_sells += 1
            net_shares -= shares

    metrics["insider_buys"] = net_buys
    metrics["insider_sells"] = net_sells
    metrics["insider_net_shares"] = net_shares
    metrics["insider_signal"] = "net buying" if net_shares > 0 else "net selling" if net_shares < 0 else "neutral"
    metrics["recent_transactions"] = recent_txns[:10]

    # Institutional holdings
    holdings = institutional.get("holdings", []) if institutional else []
    if holdings:
        metrics["top_holders"] = []
        total_shares_held = 0
        for h in holdings[:10]:
            name = h.get("investor", h.get("name", "Unknown"))
            shares = _safe_int(h.get("shares", h.get("currentShares")))
            change = _safe_int(h.get("shares_changed", h.get("changeInShares")))
            entry = {"name": name}
            if shares is not None:
                entry["shares"] = shares
                total_shares_held += shares
            if change is not None:
                entry["change"] = change
            metrics["top_holders"].append(entry)
        metrics["institutional_holders_shown"] = len(metrics["top_holders"])

    # Scoring
    if net_buys > net_sells and net_buys >= 2:
        score += 2
        reasons.append(f"Insider net buying ({net_buys} buys vs {net_sells} sells)")
    elif net_buys > net_sells:
        score += 1
        reasons.append(f"Slight insider buying ({net_buys} buys vs {net_sells} sells)")
    elif net_sells > net_buys + 3:
        score -= 1
        reasons.append(f"Heavy insider selling ({net_sells} sells vs {net_buys} buys)")

    rating = "bullish" if score >= 2 else "positive" if score >= 1 else "neutral" if score >= 0 else "cautious"

    return {"metrics": metrics, "rating": rating, "score": score, "reasons": reasons}


# ── Silo 7: Dividend ────────────────────────────────────────────────────────

def analyze_dividend(overview: Dict, cash_flow: Dict, income: Dict) -> Dict[str, Any]:
    metrics = {}
    score = 0
    reasons = []

    div_yield = _pct(overview.get("dividend_yield"))
    div_per_share = _safe_float(overview.get("dividend_per_share"))
    eps = _safe_float(overview.get("eps"))
    ex_date = overview.get("ex_dividend_date", "")

    metrics["yield"] = div_yield
    metrics["per_share"] = div_per_share
    metrics["ex_dividend_date"] = ex_date if ex_date and ex_date != "None" else None

    # No dividend
    if not div_per_share or div_per_share <= 0:
        return {
            "metrics": metrics,
            "rating": "no dividend",
            "score": 0,
            "reasons": ["Company does not pay a dividend"],
        }

    # Payout ratio
    if eps and eps > 0 and div_per_share:
        payout = round(div_per_share / eps * 100, 1)
        metrics["payout_ratio"] = payout

    # FCF coverage
    cf = (cash_flow.get("annual") or cash_flow.get("quarterly", [None]))
    latest_cf = cf[0] if cf else {}
    div_paid = _safe_float(latest_cf.get("dividendPayout"))
    operating_cf = _safe_float(latest_cf.get("operatingCashflow"))
    capex = _safe_float(latest_cf.get("capitalExpenditures"))

    if operating_cf and capex and div_paid and div_paid > 0:
        fcf = operating_cf - abs(capex)
        metrics["fcf_coverage"] = round(fcf / abs(div_paid), 2) if abs(div_paid) > 0 else None

    # Scoring
    if div_yield is not None:
        if div_yield > 4:
            score += 1
            reasons.append(f"High yield ({div_yield:.2f}%)")
        elif div_yield > 1.5:
            score += 1
            reasons.append(f"Moderate yield ({div_yield:.2f}%)")
        elif div_yield > 0:
            reasons.append(f"Low yield ({div_yield:.2f}%)")

    payout = metrics.get("payout_ratio")
    if payout is not None:
        if payout < 50:
            score += 1
            reasons.append(f"Sustainable payout ratio ({payout:.0f}%)")
        elif payout > 90:
            score -= 1
            reasons.append(f"Stretched payout ratio ({payout:.0f}%)")

    fcf_cov = metrics.get("fcf_coverage")
    if fcf_cov is not None:
        if fcf_cov > 2:
            score += 1
            reasons.append(f"Strong FCF coverage ({fcf_cov:.1f}x)")
        elif fcf_cov < 1:
            score -= 1
            reasons.append(f"FCF doesn't cover dividend ({fcf_cov:.1f}x)")

    rating = "strong" if score >= 2 else "sustainable" if score >= 1 else "adequate" if score >= 0 else "at risk"

    return {"metrics": metrics, "rating": rating, "score": score, "reasons": reasons}


# ── Main Entry Point ─────────────────────────────────────────────────────────

def run_fundamental_analysis(
    overview: Dict,
    income: Dict,
    balance_sheet: Dict,
    cash_flow: Dict,
    earnings: Dict,
    insider_txns: List,
    institutional: Dict,
    current_price: float,
) -> Dict[str, Any]:
    """
    Run all 7 fundamental analysis silos.

    Returns structured results with metrics, ratings, and reasoning per silo.
    This is standalone analysis — NOT connected to the scoring/signaling system.
    """
    result = {
        "valuation": analyze_valuation(overview, current_price),
        "profitability": analyze_profitability(overview, income),
        "growth": analyze_growth(income, earnings, overview),
        "financial_health": analyze_financial_health(balance_sheet, cash_flow, income),
        "earnings_quality": analyze_earnings_quality(earnings),
        "ownership": analyze_ownership(insider_txns, institutional),
        "dividend": analyze_dividend(overview, cash_flow, income),
        "company": {
            "name": overview.get("name", ""),
            "ticker": overview.get("ticker", ""),
            "sector": overview.get("sector", ""),
            "industry": overview.get("industry", ""),
            "market_cap": overview.get("market_cap", ""),
            "market_cap_fmt": _fmt_large(overview.get("market_cap")),
            "description": overview.get("description", ""),
        },
    }

    # Overall summary score (simple aggregate)
    total_score = sum(
        result[silo]["score"]
        for silo in ["valuation", "profitability", "growth", "financial_health", "earnings_quality", "ownership", "dividend"]
    )
    result["overall_score"] = total_score

    return result


def format_fundamentals_for_llm(analysis: Dict) -> str:
    """Format the fundamental analysis results into text for LLM narration."""
    lines = []

    company = analysis.get("company", {})
    lines.append(f"## {company.get('name', '')} ({company.get('ticker', '')})")
    lines.append(f"Sector: {company.get('sector', '')} | Industry: {company.get('industry', '')}")
    lines.append(f"Market Cap: {company.get('market_cap_fmt', 'N/A')}")
    lines.append("")

    for silo_name, label in [
        ("valuation", "Valuation"),
        ("profitability", "Profitability"),
        ("growth", "Growth"),
        ("financial_health", "Financial Health"),
        ("earnings_quality", "Earnings Quality"),
        ("ownership", "Ownership Signals"),
        ("dividend", "Dividend"),
    ]:
        silo = analysis.get(silo_name, {})
        lines.append(f"### {label} — Rating: {silo.get('rating', 'N/A').upper()}")
        for reason in silo.get("reasons", []):
            lines.append(f"  - {reason}")

        # Key metrics
        metrics = silo.get("metrics", {})
        metric_strs = []
        for k, v in metrics.items():
            if k in ("margin_trend", "history", "recent_transactions", "top_holders", "analyst_ratings"):
                continue
            if v is not None and v != "":
                metric_strs.append(f"{k}: {v}")
        if metric_strs:
            lines.append(f"  Metrics: {', '.join(metric_strs[:8])}")
        lines.append("")

    lines.append(f"Overall Fundamental Score: {analysis.get('overall_score', 0)}")

    return "\n".join(lines)
