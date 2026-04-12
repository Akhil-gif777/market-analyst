"""
Prompt templates for the market analysis LLM.
"""

ANALYSIS_PROMPT = """You are a senior market analyst. Given the following news headlines and market context, produce a detailed market analysis.

## Date
{date}

## News Headlines
{headlines}

## Current Market Context
{market_context}

## Your Task

Analyze these events and produce a structured analysis with:

1. **Affected Sectors**: Which market sectors are impacted and in which direction (bullish/bearish)?
2. **Stock Picks**: Specific stocks that would benefit or suffer, with reasoning.
3. **Causal Chains**: Multi-order cause-and-effect chains showing how the event ripples through markets.

## Output Format

You MUST respond with valid JSON only. No markdown, no commentary, no code fences. Just the JSON object.

The JSON must follow this exact structure:
{{
    "sectors": [
        {{
            "name": "<sector name, lowercase_with_underscores>",
            "direction": "<bullish|bearish|mixed>",
            "reason": "<one sentence explanation>"
        }}
    ],
    "stocks": {{
        "bullish": [
            {{
                "ticker": "<TICKER>",
                "reason": "<why this stock benefits>"
            }}
        ],
        "bearish": [
            {{
                "ticker": "<TICKER>",
                "reason": "<why this stock suffers>"
            }}
        ]
    }},
    "causal_chains": [
        "<event → first order effect → second order effect → market impact>"
    ]
}}

Important:
- Be specific with stock tickers (use US exchange tickers).
- Include at least 5 sectors, 5 bullish stocks, and 3 bearish stocks.
- Include at least 4 causal chains showing multi-order thinking.
- Focus on the most significant and highest-confidence impacts.
- Respond with the JSON object ONLY. No other text.
"""


def format_prompt(case: dict) -> str:
    """Format the analysis prompt with a specific test case."""
    headlines_text = "\n".join(f"- {h}" for h in case["headlines"])
    return ANALYSIS_PROMPT.format(
        date=case["date"],
        headlines=headlines_text,
        market_context=case["market_context"],
    )
