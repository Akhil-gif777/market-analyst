"""
Ollama LLM client with prompt templates for market analysis.
"""

from __future__ import annotations

import json
import re
import logging
import time
from typing import Optional, Tuple, Dict, Any, List

import requests

from app.config import config

logger = logging.getLogger(__name__)


def check_available() -> bool:
    """Check if Ollama is running."""
    try:
        resp = requests.get(f"{config.ollama_base_url}/api/tags", timeout=5)
        return resp.status_code == 200
    except requests.ConnectionError:
        return False


def generate(prompt: str, model: Optional[str] = None) -> Dict[str, Any]:
    """
    Send a prompt to Ollama and return the raw response.

    Returns dict with: response (str), duration_seconds (float), error (str|None)
    """
    model = model or config.ollama_model
    start = time.time()

    try:
        resp = requests.post(
            f"{config.ollama_base_url}/api/generate",
            json={
                "model": model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": config.ollama_temperature,
                    "num_predict": 8192,
                },
            },
            timeout=config.ollama_timeout,
        )
        resp.raise_for_status()
    except requests.exceptions.ReadTimeout:
        return {"response": "", "duration_seconds": time.time() - start, "error": "timeout"}
    except requests.exceptions.RequestException as e:
        return {"response": "", "duration_seconds": time.time() - start, "error": str(e)}

    duration = time.time() - start
    return {
        "response": resp.json().get("response", ""),
        "duration_seconds": round(duration, 1),
        "error": None,
    }


def generate_json(prompt: str, model: Optional[str] = None) -> Dict[str, Any]:
    """
    Send a prompt and parse the response as JSON.

    Returns dict with: data (dict|None), raw (str), duration_seconds (float), error (str|None)
    """
    result = generate(prompt, model)
    if result["error"]:
        return {"data": None, "raw": "", "duration_seconds": result["duration_seconds"], "error": result["error"]}

    parsed, parse_err = _extract_json(result["response"])
    return {
        "data": parsed,
        "raw": result["response"],
        "duration_seconds": result["duration_seconds"],
        "error": parse_err,
    }


def _extract_json(text: str) -> Tuple[Optional[dict], Optional[str]]:
    """Extract JSON from LLM response, handling code fences and extra text."""
    # Direct parse
    try:
        return json.loads(text.strip()), None
    except json.JSONDecodeError:
        pass

    # Code fence extraction
    fence_match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
    if fence_match:
        try:
            return json.loads(fence_match.group(1).strip()), None
        except json.JSONDecodeError:
            pass

    # Brace matching
    brace_start = text.find("{")
    if brace_start != -1:
        depth = 0
        for i in range(brace_start, len(text)):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[brace_start:i + 1]), None
                    except json.JSONDecodeError:
                        break

    return None, "Failed to parse JSON from LLM response"


# ── Prompt Templates ──────────────────────────────────────────────────────────

EVENT_EXTRACTION_PROMPT = """You are a senior market analyst. Analyze the following news articles and extract market-moving events.

Each article includes sentiment data and tagged tickers from Alpha Vantage.

## News Articles
{articles}

## Task
Group these articles into distinct market-moving events. For each event:
1. What happened (clear, concise summary)
2. Event category (geopolitical, trade_policy, monetary_policy, conflict, regulation, natural_disaster, corporate, technology)
3. Severity (high, medium, low)
4. Which geographic regions are affected
5. Which tickers were tagged in the source articles (carry them over — do NOT invent new ones)

Respond with JSON only. No other text.

{{
    "events": [
        {{
            "title": "<concise event title>",
            "summary": "<1-2 sentence description>",
            "category": "<category>",
            "severity": "<high|medium|low>",
            "regions": ["<region1>", "<region2>"],
            "source_headlines": ["<headline that sourced this event>"],
            "related_tickers": ["<tickers from the source articles — do NOT guess>"]
        }}
    ]
}}"""


CAUSAL_ANALYSIS_PROMPT = """You are a senior market analyst. Analyze the following event using ONLY the real market data provided below.

IMPORTANT: Do NOT invent or guess ticker symbols. Your job is to explain WHY things are moving, not to guess WHAT is moving — the market data already tells us what's moving.

## Event
{event}

## Current Market Snapshot
{market_snapshot}

## Tickers Tagged in Related News (real Alpha Vantage sentiment data)
{ticker_data}

## Task
Using the real market data above, analyze this event's causal impact:
1. Build causal chains: what are the 1st, 2nd, and 3rd order effects?
2. Which sectors are impacted and why? (reference the sector ETF data)
3. Classify the signal using actual market movement data:
   - EARLY: news detected but market hasn't moved in the expected direction yet
   - CONFIRMED: market movement aligns with expected impact from the event
   - DIVERGENT: market is moving opposite to what the event implies
   - PRICED_IN: market has already moved significantly in the expected direction

Respond with JSON only. No other text.

{{
    "event_title": "<title>",
    "signal_type": "<EARLY|CONFIRMED|DIVERGENT|PRICED_IN>",
    "signal_reasoning": "<why, referencing actual market data provided above>",
    "causal_chains": [
        {{
            "chain": "<cause → effect → effect → market impact>",
            "order": <1|2|3>,
            "confidence": "<high|medium|low>"
        }}
    ],
    "sectors": [
        {{
            "name": "<sector>",
            "direction": "<bullish|bearish|mixed>",
            "reason": "<why, citing real data from above>",
            "confidence": "<high|medium|low>"
        }}
    ]
}}"""


STOCK_SELECTION_PROMPT = """You are a senior equity analyst. Given the macro analysis and fundamental data below, evaluate the candidate stocks.

IMPORTANT: Only evaluate stocks listed below. Do NOT suggest any tickers not present in the candidate list.

## Macro Analysis (from current market events)
{macro_analysis}

## Candidate Stocks with Fundamentals (from Alpha Vantage data)
{fundamentals}

## Current Sector Performance
{sector_performance}

## Task
Evaluate each candidate stock against the macro thesis:
1. Is the macro thesis priced in already? (check price vs 50/200-day moving averages)
2. Are fundamentals strong enough to benefit? (P/E, margins, growth)
3. How exposed is this company to the specific catalyst?

Respond with JSON only. No other text.

{{
    "top_picks": [
        {{
            "ticker": "<TICKER from candidates above>",
            "action": "<strong_buy|buy|hold|sell|strong_sell>",
            "reason": "<2-3 sentence thesis combining macro + fundamentals>",
            "risk": "<key risk to this pick>",
            "confidence": "<high|medium|low>"
        }}
    ],
    "avoid": [
        {{
            "ticker": "<TICKER from candidates above>",
            "reason": "<why to avoid>"
        }}
    ]
}}"""


SYNTHESIS_PROMPT = """You are a chief market strategist. Synthesize the following individual event analyses into one holistic market outlook.

IMPORTANT: Only reference tickers that appear in the data below. Do NOT invent new ticker symbols.

## Individual Event Analyses
{event_analyses}

## Stock Evaluations (from fundamental analysis)
{stock_evaluations}

## Current Economic Indicators
{economic_indicators}

## Current Sector Performance
{sector_performance}

## Task
Combine all active events into a unified market view:
1. What is the overall market sentiment?
2. Which themes are reinforcing each other?
3. Which signals are conflicting?
4. What is the net sector outlook?
5. From the evaluated stocks, which are the top picks across all events?
6. What should investors watch next?

## Reconciling Conflicting Stock Evaluations
A ticker may appear in multiple event evaluations with different actions. When this happens:
- Weigh each evaluation by the event's severity (high > medium > low) and signal confidence
- The final action should reflect the NET effect across all events, not just the strongest single signal
- Include BOTH the bull and bear case in the thesis so the user understands the tension
- Add the conflict to the conflicting_signals list (e.g. "XOM: bullish from energy policy but bearish from trade war")
- If the net effect is genuinely unclear, use "hold" and explain why in the thesis

Respond with JSON only. No other text.

{{
    "overall_sentiment": "<strongly_bullish|bullish|cautious_bullish|neutral|cautious_bearish|bearish|strongly_bearish>",
    "confidence": "<high|medium|low>",
    "key_themes": [
        {{
            "theme": "<theme title>",
            "impact": "<high|medium|low>",
            "description": "<how this theme affects markets>"
        }}
    ],
    "sector_outlook": [
        {{
            "sector": "<sector>",
            "signal": "<bullish|bearish|neutral|mixed>",
            "reason": "<why, referencing specific events>"
        }}
    ],
    "conflicting_signals": [
        "<description of conflicting signals>"
    ],
    "reinforcing_signals": [
        "<description of reinforcing signals>"
    ],
    "top_picks": [
        {{
            "ticker": "<TICKER from evaluated stocks>",
            "action": "<strong_buy|buy|hold|sell|strong_sell>",
            "thesis": "<complete thesis tying macro to stock>"
        }}
    ],
    "watchlist": [
        "<specific event or data point to watch, with why>"
    ]
}}"""


MARKET_OVERVIEW_PROMPT = """You are a chief market strategist delivering a real-time market briefing. Using ONLY the data provided below, write a concise, data-driven market overview.

## Important Notes
- VIXY is an ETF proxy for volatility, NOT the VIX index. Its dollar price is meaningless — only use its % change to assess whether fear is rising or falling today.
- The MARKET REGIME section at the top is a programmatic classification. Your analysis should be CONSISTENT with it. If the regime says "Risk-Off" and defensive sectors are leading, do not say the market is "improving" or "risk appetite is returning" unless other data clearly contradicts it.
- Be honest about conflicting signals. If growth sectors are down but gold is also falling, say the signals are mixed — don't force a narrative.

## Market Data
{snapshot}

## Task
Analyze all the data above — including the recent news headlines and their sentiment — and produce a structured market briefing. Be specific — cite actual numbers, percentages, and prices from the data. Incorporate key news themes (geopolitical events, policy changes, earnings, etc.) to explain WHY the market is moving the way it is.

Write for someone who is learning about markets — avoid unexplained jargon. If you mention a concept like "risk-off rotation" or "yield curve inversion", briefly explain what it means in plain language.

Respond with JSON only. No other text.

{{
    "one_liner": "<single sentence market summary suitable for a headline>",
    "market_pulse": "<2-3 sentences: how are indices performing? is volatility rising or falling today (use VIXY % change, not price)? overall market direction>",
    "key_movers": "<2-3 sentences: what's driving the biggest gains and losses today? any sector rotation visible? explain what that rotation means>",
    "news_and_events": "<2-3 sentences: what are the dominant news themes right now? any geopolitical, policy, or macro events driving sentiment? cite specific headlines>",
    "macro_landscape": "<2-3 sentences: what do treasury yields (yield curve shape), forex (dollar strength), and economic indicators suggest about the economy?>",
    "commodities_crypto": "<2-3 sentences: notable moves in energy, metals, or crypto — and what they signal>",
    "risk_assessment": "<2-3 sentences: key risks investors should watch — cite specific data points or news developments that look concerning>",
    "outlook": "<1-2 sentences: near-term outlook based on the data and news sentiment>"
}}"""


PRICE_ACTION_NARRATIVE_PROMPT = """You are a senior technical analyst. A rule-based scoring engine has already produced a confluence score and signal for a stock. Your job is to EXPLAIN the score — not override it. Use ONLY the data provided below.

## Stock Price Action Data
{technical_data}

## Computed Score & Breakdown
{score_breakdown}

## Task
Explain the computed signal in plain English. Be specific — cite actual prices, indicator values, and pattern names from the data. Do not contradict the computed signal.

Respond with JSON only. No other text.

{{
    "headline": "<one-line summary of the setup, e.g. 'AAPL holding weekly uptrend, bullish engulfing at $181 support'>",
    "structure_analysis": "<2-3 sentences: what the weekly + daily market structure shows — reference the HH/HL/LH/LL labels>",
    "pattern_context": "<1-2 sentences: what the detected candlestick patterns mean at this price location>",
    "level_analysis": "<2-3 sentences: key S/R levels and what happens if they break — cite specific prices>",
    "volume_read": "<1-2 sentences: what volume is telling us — confirm or contradict?>",
    "risk_factors": ["<specific risk citing data>", "<another risk>"],
    "watch_for": ["<what would strengthen the signal>", "<what would invalidate it>"]
}}"""


def _format_article_for_extraction(a: Dict[str, Any]) -> str:
    """Format a single article with its AV sentiment data for event extraction."""
    desc = a.get('description') or a.get('summary', 'No description')
    parts = [
        f"**{a.get('title', 'No title')}**",
        desc[:200],
        f"Source: {a.get('source', 'unknown')} | Sentiment: {a.get('overall_sentiment_label', 'N/A')}",
    ]
    tickers = a.get("ticker_sentiments", {})
    if tickers:
        top = sorted(tickers.items(), key=lambda x: -x[1].get("relevance_score", 0))[:3]
        ticker_str = ", ".join(f"{t}({s.get('sentiment_label', '?')})" for t, s in top)
        parts.append(f"Tickers: {ticker_str}")
    return "\n".join(parts)


def extract_events(articles: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Extract market-moving events from news articles."""
    articles_text = "\n\n".join(
        _format_article_for_extraction(a) for a in articles
    )
    prompt = EVENT_EXTRACTION_PROMPT.format(articles=articles_text)
    return generate_json(prompt)


def analyze_event(event: Dict[str, Any], market_snapshot: str, ticker_data: str) -> Dict[str, Any]:
    """Build causal chain analysis using real market data."""
    event_text = (
        f"**{event.get('title', '')}**\n{event.get('summary', '')}\n"
        f"Category: {event.get('category', '')}\nSeverity: {event.get('severity', '')}"
    )
    prompt = CAUSAL_ANALYSIS_PROMPT.format(
        event=event_text,
        market_snapshot=market_snapshot,
        ticker_data=ticker_data or "No ticker data available for this event.",
    )
    return generate_json(prompt)


def select_stocks(macro_analysis: str, fundamentals: str, sector_performance: str) -> Dict[str, Any]:
    """Evaluate candidate stocks using macro thesis and fundamentals."""
    prompt = STOCK_SELECTION_PROMPT.format(
        macro_analysis=macro_analysis,
        fundamentals=fundamentals,
        sector_performance=sector_performance,
    )
    return generate_json(prompt)


def synthesize(event_analyses: str, stock_evaluations: str, economic_indicators: str, sector_performance: str) -> Dict[str, Any]:
    """Synthesize all event analyses into a holistic market outlook."""
    prompt = SYNTHESIS_PROMPT.format(
        event_analyses=event_analyses,
        stock_evaluations=stock_evaluations or "No stock evaluations available.",
        economic_indicators=economic_indicators,
        sector_performance=sector_performance,
    )
    return generate_json(prompt)


def generate_market_overview(snapshot_text: str) -> Dict[str, Any]:
    """Generate an LLM-powered market overview from formatted snapshot data."""
    prompt = MARKET_OVERVIEW_PROMPT.format(snapshot=snapshot_text)
    return generate_json(prompt)


def narrate_price_action(technical_data_text: str, score_breakdown_text: str) -> Dict[str, Any]:
    """Generate a narrative explaining the price action score."""
    prompt = PRICE_ACTION_NARRATIVE_PROMPT.format(
        technical_data=technical_data_text,
        score_breakdown=score_breakdown_text,
    )
    return generate_json(prompt)


# ── Fundamental Analysis Narrative ───────────────────────────────────────────

FUNDAMENTAL_ANALYSIS_PROMPT = """You are a fundamental equity analyst. Analyze the following company using ONLY the data provided below. This is standalone fundamental analysis — do NOT make buy/sell recommendations or reference any technical/price action signals.

## Fundamental Data
{fundamental_data}

## Task
Write a clear, specific fundamental analysis. Reference actual numbers from the data. Cover each category briefly. Identify the 2-3 strongest aspects and 2-3 biggest concerns or risks.

Respond with JSON only. No other text.

{{
    "summary": "<3-4 sentence overall fundamental assessment — is this a fundamentally strong company? what stands out?>",
    "strengths": ["<plain string: specific strength with numbers>", "<plain string: another strength>"],
    "concerns": ["<plain string: specific concern with numbers>", "<plain string: another concern>"],
    "valuation_take": "<1-2 sentences: is the stock fairly valued? cite P/E, PEG, or P/B>",
    "profitability_take": "<1-2 sentences: how profitable is the business? cite margins>",
    "growth_take": "<1-2 sentences: revenue and earnings trajectory — growing, stable, or declining?>",
    "health_take": "<1-2 sentences: can the company weather a downturn? cite debt and cash>",
    "earnings_take": "<1-2 sentences: does management deliver on estimates? cite beat rate>",
    "ownership_take": "<1-2 sentences: what are insiders and institutions signaling?>",
    "dividend_take": "<1-2 sentences: dividend assessment or 'N/A — no dividend' if none>"
}}"""


def narrate_fundamentals(fundamental_data_text: str) -> Dict[str, Any]:
    """Generate a narrative for the fundamental analysis."""
    prompt = FUNDAMENTAL_ANALYSIS_PROMPT.format(
        fundamental_data=fundamental_data_text,
    )
    return generate_json(prompt)
