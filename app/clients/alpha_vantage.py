"""
Alpha Vantage API client for market data, news sentiment, and fundamentals.

Docs: https://www.alphavantage.co/documentation/
"""

from __future__ import annotations

import logging
from typing import Optional, List, Dict, Any

import requests

from app.config import config

logger = logging.getLogger(__name__)

BASE_URL = "https://www.alphavantage.co/query"


def _request(params: Dict[str, Any]) -> Dict[str, Any]:
    """Make an Alpha Vantage API request."""
    params["apikey"] = config.alpha_vantage_api_key
    try:
        resp = requests.get(BASE_URL, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as e:
        err_msg = str(e)
        if config.alpha_vantage_api_key:
            err_msg = err_msg.replace(config.alpha_vantage_api_key, "***")
        logger.error("Alpha Vantage request failed: %s", err_msg)
        return {}

    if "Error Message" in data:
        logger.error("Alpha Vantage error: %s", data["Error Message"])
        return {}
    if "Note" in data:
        logger.warning("Alpha Vantage rate limit: %s", data["Note"])
        return {}

    return data


# ── News & Sentiment ──────────────────────────────────────────────────────────

def fetch_market_news(
    tickers: Optional[str] = None,
    topics: Optional[str] = None,
    sort: str = "LATEST",
    limit: int = 50,
    time_from: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Fetch market news with sentiment scores.

    Args:
        tickers: Comma-separated tickers (e.g., "AAPL,MSFT")
        topics: Topics filter — technology, finance, manufacturing,
                economy_fiscal, economy_monetary, energy, etc.
        sort: LATEST, EARLIEST, or RELEVANCE
        limit: Max articles (up to 1000)
        time_from: Only return articles published after this time (AV format: YYYYMMDDTHHMM)

    Returns:
        List of articles with sentiment scores per ticker.
    """
    if not config.alpha_vantage_api_key:
        logger.warning("ALPHA_VANTAGE_API_KEY not set — skipping fetch")
        return []

    params = {
        "function": "NEWS_SENTIMENT",
        "sort": sort,
        "limit": limit,
    }
    if tickers:
        params["tickers"] = tickers
    if topics:
        params["topics"] = topics
    if time_from:
        params["time_from"] = time_from

    data = _request(params)
    articles = []

    for raw in data.get("feed", []):
        ticker_sentiments = {}
        for ts in raw.get("ticker_sentiment", []):
            ticker_sentiments[ts["ticker"]] = {
                "relevance_score": float(ts.get("relevance_score", 0)),
                "sentiment_score": float(ts.get("ticker_sentiment_score", 0)),
                "sentiment_label": ts.get("ticker_sentiment_label", ""),
            }

        articles.append({
            "title": raw.get("title", ""),
            "summary": raw.get("summary", ""),
            "source": raw.get("source", ""),
            "authors": raw.get("authors", []),
            "url": raw.get("url", ""),
            "banner_image": raw.get("banner_image", ""),
            "published_at": raw.get("time_published", ""),
            "overall_sentiment_score": float(raw.get("overall_sentiment_score", 0)),
            "overall_sentiment_label": raw.get("overall_sentiment_label", ""),
            "ticker_sentiments": ticker_sentiments,
            "topics": [t.get("topic", "") for t in raw.get("topics", [])],
            "source_api": "alpha_vantage",
        })

    return articles


def get_ticker_sentiment(ticker: str, limit: int = 20) -> Dict[str, Any]:
    """
    Get sentiment analysis for a specific ticker.

    Queries Alpha Vantage NEWS_SENTIMENT filtered by ticker.
    Returns aggregated sentiment stats + individual article sentiments.
    """
    articles = fetch_market_news(tickers=ticker, sort="RELEVANCE", limit=limit)
    if not articles:
        return {"ticker": ticker, "articles_found": 0}

    # Collect all articles with sentiment for this ticker
    all_mentions = []
    for a in articles:
        ts = a.get("ticker_sentiments", {}).get(ticker, {})
        if not ts:
            continue
        relevance = ts.get("relevance_score", 0)
        all_mentions.append({
            "title": a.get("title", "")[:120],
            "sentiment_score": ts.get("sentiment_score", 0),
            "sentiment_label": ts.get("sentiment_label", ""),
            "relevance": relevance,
            "published_at": a.get("published_at", ""),
        })

    # Sort by relevance (most relevant first) and take the top ones
    all_mentions.sort(key=lambda x: x["relevance"], reverse=True)

    # Only count articles with meaningful relevance (top half, min 0.5)
    scores = []
    article_sentiments = []
    for m in all_mentions:
        if m["relevance"] < 0.5:
            continue
        scores.append(m["sentiment_score"])
        article_sentiments.append(m)

    if not scores:
        return {"ticker": ticker, "articles_found": len(articles), "ticker_mentions": 0}

    avg_score = sum(scores) / len(scores)
    bullish_count = sum(1 for s in scores if s > 0.1)
    bearish_count = sum(1 for s in scores if s < -0.1)
    neutral_count = len(scores) - bullish_count - bearish_count

    if avg_score > 0.15:
        overall = "bullish"
    elif avg_score > 0.05:
        overall = "somewhat_bullish"
    elif avg_score < -0.15:
        overall = "bearish"
    elif avg_score < -0.05:
        overall = "somewhat_bearish"
    else:
        overall = "neutral"

    return {
        "ticker": ticker,
        "articles_found": len(articles),
        "ticker_mentions": len(scores),
        "avg_sentiment_score": round(avg_score, 3),
        "overall_sentiment": overall,
        "bullish_articles": bullish_count,
        "bearish_articles": bearish_count,
        "neutral_articles": neutral_count,
        "recent_articles": article_sentiments[:5],
    }


# ── Stock Fundamentals ────────────────────────────────────────────────────────

def get_company_overview(ticker: str) -> Dict[str, Any]:
    """Get company overview — sector, industry, market cap, P/E, EPS, etc."""
    data = _request({"function": "OVERVIEW", "symbol": ticker})
    if not data:
        return {}

    return {
        "ticker": ticker,
        "name": data.get("Name", ""),
        "sector": data.get("Sector", ""),
        "industry": data.get("Industry", ""),
        "market_cap": data.get("MarketCapitalization", ""),
        "pe_ratio": data.get("PERatio", ""),
        "forward_pe": data.get("ForwardPE", ""),
        "eps": data.get("EPS", ""),
        "dividend_yield": data.get("DividendYield", ""),
        "52_week_high": data.get("52WeekHigh", ""),
        "52_week_low": data.get("52WeekLow", ""),
        "50_day_avg": data.get("50DayMovingAverage", ""),
        "200_day_avg": data.get("200DayMovingAverage", ""),
        "beta": data.get("Beta", ""),
        "profit_margin": data.get("ProfitMargin", ""),
        "revenue_growth": data.get("QuarterlyRevenueGrowthYOY", ""),
        "description": data.get("Description", ""),
        # Fundamental analysis fields
        "price_to_book": data.get("PriceToBookRatio", ""),
        "price_to_sales": data.get("PriceToSalesRatioTTM", ""),
        "ev_to_ebitda": data.get("EVToEBITDA", ""),
        "peg_ratio": data.get("PEGRatio", ""),
        "roe": data.get("ReturnOnEquityTTM", ""),
        "roa": data.get("ReturnOnAssetsTTM", ""),
        "operating_margin": data.get("OperatingMarginTTM", ""),
        "gross_profit_ttm": data.get("GrossProfitTTM", ""),
        "revenue_ttm": data.get("RevenueTTM", ""),
        "ebitda": data.get("EBITDA", ""),
        "book_value": data.get("BookValue", ""),
        "shares_outstanding": data.get("SharesOutstanding", ""),
        "dividend_per_share": data.get("DividendPerShare", ""),
        "ex_dividend_date": data.get("ExDividendDate", ""),
        "analyst_target_price": data.get("AnalystTargetPrice", ""),
        "analyst_strong_buy": data.get("AnalystRatingStrongBuy", ""),
        "analyst_buy": data.get("AnalystRatingBuy", ""),
        "analyst_hold": data.get("AnalystRatingHold", ""),
        "analyst_sell": data.get("AnalystRatingSell", ""),
        "analyst_strong_sell": data.get("AnalystRatingStrongSell", ""),
    }


def get_income_statement(ticker: str) -> Dict[str, Any]:
    """Get annual and quarterly income statements."""
    data = _request({"function": "INCOME_STATEMENT", "symbol": ticker})
    return {
        "annual": data.get("annualReports", [])[:4],
        "quarterly": data.get("quarterlyReports", [])[:4],
    }


def get_balance_sheet(ticker: str) -> Dict[str, Any]:
    """Get annual and quarterly balance sheets."""
    data = _request({"function": "BALANCE_SHEET", "symbol": ticker})
    return {
        "annual": data.get("annualReports", [])[:4],
        "quarterly": data.get("quarterlyReports", [])[:4],
    }


def get_cash_flow(ticker: str) -> Dict[str, Any]:
    """Get annual and quarterly cash flow statements."""
    data = _request({"function": "CASH_FLOW", "symbol": ticker})
    return {
        "annual": data.get("annualReports", [])[:4],
        "quarterly": data.get("quarterlyReports", [])[:4],
    }


def get_earnings(ticker: str) -> Dict[str, Any]:
    """Get earnings history and upcoming earnings date."""
    data = _request({"function": "EARNINGS", "symbol": ticker})
    return {
        "annual": data.get("annualEarnings", [])[:4],
        "quarterly": data.get("quarterlyEarnings", [])[:8],
    }


def get_full_stock_profile(ticker: str) -> Dict[str, Any]:
    """
    Build a comprehensive stock profile from multiple Alpha Vantage endpoints.

    Combines: overview + quote + recent prices + income + balance sheet + earnings.
    This is the thorough analysis the LLM needs for stock selection.

    Uses 5 API calls per ticker — be mindful of rate limits.
    """
    profile = {"ticker": ticker}

    # 1. Company overview (valuation, margins, sector)
    overview = get_company_overview(ticker)
    if overview:
        profile["overview"] = overview
    else:
        return profile  # If overview fails, skip the rest

    # 2. Real-time quote (current price action)
    quote = get_stock_quote(ticker)
    if quote:
        profile["quote"] = quote

    # 3. Recent price history (last 20 days for trend)
    prices = get_daily_prices(ticker, compact=True)
    if prices:
        profile["recent_prices"] = prices[:20]
        # Compute simple momentum signals
        if len(prices) >= 5:
            price_5d_ago = prices[4]["close"]
            price_now = prices[0]["close"]
            profile["momentum_5d"] = round((price_now - price_5d_ago) / price_5d_ago * 100, 2)
        if len(prices) >= 20:
            price_20d_ago = prices[19]["close"]
            profile["momentum_20d"] = round((price_now - price_20d_ago) / price_20d_ago * 100, 2)

    # 4. Latest quarterly income statement (revenue, net income trend)
    income = get_income_statement(ticker)
    quarterly_income = income.get("quarterly", [])[:4]
    if quarterly_income:
        profile["quarterly_revenue"] = []
        for q in quarterly_income:
            profile["quarterly_revenue"].append({
                "date": q.get("fiscalDateEnding", ""),
                "revenue": q.get("totalRevenue", ""),
                "net_income": q.get("netIncome", ""),
                "gross_profit": q.get("grossProfit", ""),
            })

    # 5. Latest quarterly balance sheet (debt, cash)
    balance = get_balance_sheet(ticker)
    quarterly_balance = balance.get("quarterly", [])[:1]
    if quarterly_balance:
        latest = quarterly_balance[0]
        profile["balance_sheet"] = {
            "date": latest.get("fiscalDateEnding", ""),
            "total_assets": latest.get("totalAssets", ""),
            "total_debt": latest.get("shortLongTermDebtTotal", latest.get("longTermDebt", "")),
            "cash": latest.get("cashAndCashEquivalentsAtCarryingValue", ""),
            "total_equity": latest.get("totalShareholderEquity", ""),
        }

    # 6. Recent earnings (beats/misses)
    earnings = get_earnings(ticker)
    quarterly_earnings = earnings.get("quarterly", [])[:4]
    if quarterly_earnings:
        profile["recent_earnings"] = []
        for e in quarterly_earnings:
            reported = e.get("reportedEPS", "")
            estimated = e.get("estimatedEPS", "")
            surprise = e.get("surprisePercentage", "")
            profile["recent_earnings"].append({
                "date": e.get("fiscalDateEnding", ""),
                "reported_eps": reported,
                "estimated_eps": estimated,
                "surprise_pct": surprise,
            })

    # 7. Ticker-specific sentiment from financial media
    sentiment = get_ticker_sentiment(ticker, limit=10)
    if sentiment.get("ticker_mentions", 0) > 0:
        profile["sentiment"] = sentiment

    return profile


def format_stock_profile_for_llm(profile: Dict[str, Any]) -> str:
    """Format a full stock profile into text the LLM can reason over."""
    ticker = profile.get("ticker", "?")
    ov = profile.get("overview", {})
    qt = profile.get("quote", {})
    bs = profile.get("balance_sheet", {})

    lines = [
        f"\n{'='*60}",
        f"{ticker} — {ov.get('name', 'Unknown')}",
        f"Sector: {ov.get('sector', 'N/A')} | Industry: {ov.get('industry', 'N/A')}",
        f"{'='*60}",
        "",
        "VALUATION:",
        f"  Market Cap: {ov.get('market_cap', 'N/A')} | P/E: {ov.get('pe_ratio', 'N/A')} | Forward P/E: {ov.get('forward_pe', 'N/A')}",
        f"  EPS: {ov.get('eps', 'N/A')} | Dividend Yield: {ov.get('dividend_yield', 'N/A')}",
        "",
        "PRICE ACTION:",
        f"  Current: ${qt.get('price', 'N/A')} | Change: {qt.get('change_percent', 'N/A')}",
        f"  52W High: {ov.get('52_week_high', 'N/A')} | 52W Low: {ov.get('52_week_low', 'N/A')}",
        f"  50D Avg: {ov.get('50_day_avg', 'N/A')} | 200D Avg: {ov.get('200_day_avg', 'N/A')}",
    ]

    m5 = profile.get("momentum_5d")
    m20 = profile.get("momentum_20d")
    if m5 is not None or m20 is not None:
        lines.append(f"  Momentum: 5-day {m5 if m5 is not None else 'N/A'}% | 20-day {m20 if m20 is not None else 'N/A'}%")

    lines.extend([
        "",
        "FUNDAMENTALS:",
        f"  Beta: {ov.get('beta', 'N/A')} | Profit Margin: {ov.get('profit_margin', 'N/A')} | Rev Growth (QoQ): {ov.get('revenue_growth', 'N/A')}",
    ])

    if bs:
        lines.extend([
            "",
            "BALANCE SHEET (latest quarter):",
            f"  Total Assets: {bs.get('total_assets', 'N/A')} | Total Debt: {bs.get('total_debt', 'N/A')}",
            f"  Cash: {bs.get('cash', 'N/A')} | Equity: {bs.get('total_equity', 'N/A')}",
        ])

    qr = profile.get("quarterly_revenue", [])
    if qr:
        lines.extend(["", "REVENUE TREND (last 4 quarters):"])
        for q in qr:
            lines.append(f"  {q['date']}: Revenue {q['revenue']} | Net Income {q['net_income']}")

    re_ = profile.get("recent_earnings", [])
    if re_:
        lines.extend(["", "EARNINGS HISTORY (last 4 quarters):"])
        for e in re_:
            beat = ""
            try:
                surprise = float(e.get("surprise_pct", 0))
                beat = "BEAT" if surprise > 0 else "MISS" if surprise < 0 else "MET"
                beat = f" [{beat} by {abs(surprise):.1f}%]"
            except (ValueError, TypeError):
                pass
            lines.append(f"  {e['date']}: EPS {e['reported_eps']} vs est {e['estimated_eps']}{beat}")

    # Sentiment from financial media
    sent = profile.get("sentiment", {})
    if sent.get("ticker_mentions", 0) > 0:
        lines.extend([
            "",
            "MEDIA SENTIMENT:",
            f"  Overall: {sent.get('overall_sentiment', 'N/A').upper()} (avg score: {sent.get('avg_sentiment_score', 'N/A')})",
            f"  Articles: {sent.get('bullish_articles', 0)} bullish, {sent.get('bearish_articles', 0)} bearish, {sent.get('neutral_articles', 0)} neutral (from {sent.get('ticker_mentions', 0)} mentions)",
        ])
        for a in sent.get("recent_articles", [])[:3]:
            lines.append(f"  - \"{a.get('title', '')}\" ({a.get('sentiment_label', '')})")

    lines.append(f"\n  Company: {ov.get('description', 'N/A')[:200]}")

    return "\n".join(lines)


# ── Price Data ────────────────────────────────────────────────────────────────

def search_tickers(query: str) -> List[Dict[str, Any]]:
    """Search for ticker symbols using Alpha Vantage SYMBOL_SEARCH."""
    data = _request({"function": "SYMBOL_SEARCH", "keywords": query})
    results = []
    for match in data.get("bestMatches", []):
        results.append({
            "symbol": match.get("1. symbol", ""),
            "name": match.get("2. name", ""),
            "type": match.get("3. type", ""),
            "region": match.get("4. region", ""),
        })
    return results


def get_stock_quote(ticker: str) -> Dict[str, Any]:
    """Get real-time stock quote."""
    data = _request({"function": "GLOBAL_QUOTE", "symbol": ticker})
    quote = data.get("Global Quote", {})
    if not quote:
        return {}

    return {
        "ticker": ticker,
        "price": quote.get("05. price", ""),
        "change": quote.get("09. change", ""),
        "change_percent": quote.get("10. change percent", ""),
        "volume": quote.get("06. volume", ""),
        "previous_close": quote.get("08. previous close", ""),
    }


def get_institutional_holdings(ticker: str) -> Dict[str, Any]:
    """Get institutional ownership data for a ticker."""
    data = _request({"function": "INSTITUTIONAL_HOLDINGS", "symbol": ticker})
    return data


def get_insider_transactions(ticker: str) -> List[Dict[str, Any]]:
    """Get insider transaction history for a ticker."""
    data = _request({"function": "INSIDER_TRANSACTIONS", "symbol": ticker})
    return data.get("data", [])


def get_extended_hours_price(ticker: str) -> Dict[str, Any]:
    """Get the latest pre-market / after-hours price from 1-min intraday data."""
    data = _request({
        "function": "TIME_SERIES_INTRADAY",
        "symbol": ticker,
        "interval": "1min",
        "extended_hours": "true",
        "outputsize": "compact",
    })

    ts = data.get("Time Series (1min)", {})
    if not ts:
        return {}

    # Latest bar is the most recent timestamp
    latest_time = sorted(ts.keys(), reverse=True)[0]
    bar = ts[latest_time]
    price = float(bar["4. close"])

    # Compare with regular session close to get extended hours change
    quote = get_stock_quote(ticker)
    prev_close = float(quote.get("previous_close", 0)) if quote else 0
    reg_price = float(quote.get("price", 0)) if quote else 0

    result = {
        "price": price,
        "timestamp": latest_time,
        "volume": int(bar["5. volume"]),
    }

    # Determine if this is pre-market or after-hours based on time
    # Pre-market: 4:00-9:30 ET, After-hours: 16:00-20:00 ET
    try:
        hour = int(latest_time.split(" ")[1].split(":")[0])
        minute = int(latest_time.split(" ")[1].split(":")[1])
        time_val = hour * 60 + minute
        if time_val < 570:  # before 9:30
            result["session"] = "pre-market"
        elif time_val >= 960:  # after 16:00
            result["session"] = "after-hours"
        else:
            result["session"] = "regular"
    except (IndexError, ValueError):
        result["session"] = "extended"

    # Change vs previous close
    if prev_close > 0:
        change = price - prev_close
        change_pct = (change / prev_close) * 100
        result["change"] = round(change, 4)
        result["change_percent"] = round(change_pct, 4)

    # Change vs regular session close
    if reg_price > 0 and result["session"] != "regular":
        ext_change = price - reg_price
        ext_change_pct = (ext_change / reg_price) * 100
        result["ext_change"] = round(ext_change, 4)
        result["ext_change_percent"] = round(ext_change_pct, 4)

    return result


def get_daily_prices(ticker: str, compact: bool = True) -> List[Dict[str, Any]]:
    """Get split-adjusted daily price history (last 100 days if compact, full history otherwise)."""
    data = _request({
        "function": "TIME_SERIES_DAILY_ADJUSTED",
        "symbol": ticker,
        "outputsize": "compact" if compact else "full",
    })

    prices = []
    for date_str, values in data.get("Time Series (Daily)", {}).items():
        # Use adjusted close for split-accurate pricing
        adj_close = float(values["5. adjusted close"])
        raw_close = float(values["4. close"])
        adj_factor = adj_close / raw_close if raw_close != 0 else 1.0
        prices.append({
            "date": date_str,
            "open": round(float(values["1. open"]) * adj_factor, 4),
            "high": round(float(values["2. high"]) * adj_factor, 4),
            "low": round(float(values["3. low"]) * adj_factor, 4),
            "close": round(adj_close, 4),
            "volume": int(values["6. volume"]),
        })

    return sorted(prices, key=lambda x: x["date"], reverse=True)


def get_weekly_prices(ticker: str) -> List[Dict[str, Any]]:
    """Get split-adjusted weekly price history."""
    data = _request({
        "function": "TIME_SERIES_WEEKLY_ADJUSTED",
        "symbol": ticker,
    })

    prices = []
    for date_str, values in data.get("Weekly Adjusted Time Series", {}).items():
        adj_close = float(values["5. adjusted close"])
        raw_close = float(values["4. close"])
        adj_factor = adj_close / raw_close if raw_close != 0 else 1.0

        adj_open = round(float(values["1. open"]) * adj_factor, 4)
        adj_high = round(float(values["2. high"]) * adj_factor, 4)
        adj_low = round(float(values["3. low"]) * adj_factor, 4)

        # Fix split-week bars: if a split happened mid-week, open/high/low may
        # be pre-split while close is post-split, making adj_factor ~1.0.
        # Detect via open or high being >2x the close and clamp to close.
        if adj_high > adj_close * 2:
            adj_high = adj_close
        if adj_open > adj_close * 2:
            adj_open = adj_close
        if adj_low > adj_close * 2:
            adj_low = adj_close
        # Ensure OHLC consistency
        adj_high = max(adj_high, adj_open, adj_close, adj_low)
        adj_low = min(adj_low, adj_open, adj_close)

        prices.append({
            "date": date_str,
            "open": adj_open,
            "high": adj_high,
            "low": adj_low,
            "close": round(adj_close, 4),
            "volume": int(values["6. volume"]),
        })

    return sorted(prices, key=lambda x: x["date"], reverse=True)


# ── Technical Indicators ─────────────────────────────────────────────────────

def get_rsi(ticker: str, interval: str = "daily", time_period: int = 14) -> Dict[str, Any]:
    """Get RSI (Relative Strength Index)."""
    data = _request({
        "function": "RSI",
        "symbol": ticker,
        "interval": interval,
        "time_period": time_period,
        "series_type": "close",
    })
    points = data.get("Technical Analysis: RSI", {})
    recent = sorted(points.items(), reverse=True)[:100]
    return {
        "ticker": ticker,
        "indicator": "RSI",
        "period": time_period,
        "data": [{"date": d, "value": float(v["RSI"])} for d, v in recent],
    }


def get_macd(ticker: str, interval: str = "daily") -> Dict[str, Any]:
    """Get MACD (Moving Average Convergence Divergence)."""
    data = _request({
        "function": "MACD",
        "symbol": ticker,
        "interval": interval,
        "series_type": "close",
    })
    points = data.get("Technical Analysis: MACD", {})
    recent = sorted(points.items(), reverse=True)[:100]
    return {
        "ticker": ticker,
        "indicator": "MACD",
        "data": [{
            "date": d,
            "macd": float(v["MACD"]),
            "signal": float(v["MACD_Signal"]),
            "histogram": float(v["MACD_Hist"]),
        } for d, v in recent],
    }


# ── Commodities & Economic Indicators ────────────────────────────────────────

def get_commodity_price(commodity: str = "WTI") -> Dict[str, Any]:
    """
    Get commodity prices.
    Supported: WTI, BRENT, NATURAL_GAS, COPPER, ALUMINUM, WHEAT, CORN, COTTON, SUGAR, COFFEE
    """
    data = _request({"function": commodity, "interval": "daily"})
    recent = data.get("data", [])[:5]
    return {
        "commodity": commodity,
        "recent_prices": [{"date": d["date"], "value": d["value"]} for d in recent],
    }


def get_economic_indicator(indicator: str, interval: str | None = None) -> Dict[str, Any]:
    """
    Get economic indicator data.
    Supported: REAL_GDP, CPI, INFLATION, FEDERAL_FUNDS_RATE, UNEMPLOYMENT, NONFARM_PAYROLL, RETAIL_SALES
    Optional interval: 'quarterly' or 'annual' (relevant for REAL_GDP, CPI).
    """
    params: Dict[str, str] = {"function": indicator}
    if interval:
        params["interval"] = interval
    data = _request(params)
    recent = data.get("data", [])[:5]
    return {
        "indicator": indicator,
        "recent": [{"date": d["date"], "value": d["value"]} for d in recent],
    }


def get_treasury_yield(maturity: str = "10year", interval: str = "daily") -> Dict[str, Any]:
    """
    Get US treasury yield data.
    Maturities: 3month, 2year, 5year, 10year, 30year
    """
    data = _request({"function": "TREASURY_YIELD", "interval": interval, "maturity": maturity})
    recent = data.get("data", [])[:5]
    return {
        "maturity": maturity,
        "recent": [{"date": d["date"], "value": d["value"]} for d in recent],
    }


def get_currency_exchange_rate(from_currency: str, to_currency: str) -> Dict[str, Any]:
    """
    Get real-time currency exchange rate.
    Works for fiat (EUR, JPY, GBP) and crypto (BTC, ETH).
    """
    data = _request({
        "function": "CURRENCY_EXCHANGE_RATE",
        "from_currency": from_currency,
        "to_currency": to_currency,
    })
    rate_data = data.get("Realtime Currency Exchange Rate", {})
    if not rate_data:
        return {}
    return {
        "from": from_currency,
        "to": to_currency,
        "rate": rate_data.get("5. Exchange Rate", ""),
        "last_refreshed": rate_data.get("6. Last Refreshed", ""),
        "bid": rate_data.get("8. Bid Price", ""),
        "ask": rate_data.get("9. Ask Price", ""),
    }


# ── Market Movers & Sector Performance ────────────────────────────────────────

def get_market_movers() -> Dict[str, Any]:
    """Get top gainers, losers, and most actively traded stocks."""
    data = _request({"function": "TOP_GAINERS_LOSERS"})
    if not data:
        return {}

    def _extract(items, limit=5):
        return [
            {
                "ticker": i.get("ticker", ""),
                "price": i.get("price", ""),
                "change_pct": i.get("change_percentage", ""),
                "volume": i.get("volume", ""),
            }
            for i in (items or [])[:limit]
        ]

    return {
        "last_updated": data.get("last_updated", ""),
        "top_gainers": _extract(data.get("top_gainers")),
        "top_losers": _extract(data.get("top_losers")),
        "most_active": _extract(data.get("most_actively_traded")),
    }


def get_sector_performance() -> Dict[str, Any]:
    """
    Get sector performance using ETF proxies.

    The SECTOR endpoint is deprecated. We use major sector ETF quotes instead.
    """
    sector_etfs = {
        "Technology": "XLK",
        "Healthcare": "XLV",
        "Financials": "XLF",
        "Energy": "XLE",
        "Consumer Discretionary": "XLY",
        "Consumer Staples": "XLP",
        "Industrials": "XLI",
        "Materials": "XLB",
        "Utilities": "XLU",
        "Real Estate": "XLRE",
        "Communication Services": "XLC",
    }

    realtime = {}
    for sector_name, etf in sector_etfs.items():
        quote = get_stock_quote(etf)
        if quote and quote.get("change_percent"):
            realtime[sector_name] = quote["change_percent"]

    return {"realtime": realtime}
