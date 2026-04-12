"""
Historical test cases with real news headlines and verified market outcomes.

Each case represents a well-known market event where we know:
1. What the news said on day 1
2. What actually happened in markets over the following 1-4 weeks

This lets us objectively score LLM analysis quality.
"""

HISTORICAL_CASES = [
    {
        "id": "russia_ukraine_2022",
        "name": "Russia Invades Ukraine",
        "date": "2022-02-24",
        "headlines": [
            "Russia launches full-scale invasion of Ukraine, explosions reported in Kyiv",
            "Western nations condemn Russian aggression, promise severe sanctions",
            "Oil prices surge past $100 as Russia-Ukraine conflict escalates",
            "European natural gas prices spike on fears of Russian supply disruption",
            "Global stock markets tumble as geopolitical crisis deepens",
            "NATO activates defense plans for the first time in response to Russia",
            "US and EU preparing to cut Russian banks from SWIFT system",
        ],
        "market_context": (
            "Pre-invasion: S&P 500 already down ~8% YTD on inflation/rate fears. "
            "Oil at ~$92/bbl. European gas prices already elevated due to low storage. "
            "Russia supplies ~40% of Europe's natural gas and ~10% of global oil."
        ),
        "known_outcomes": {
            "sectors": {
                "energy": {"direction": "bullish", "reason": "Oil surged to $130, gas prices spiked"},
                "defense": {"direction": "bullish", "reason": "NATO spending commitments drove defense stocks up 15-25%"},
                "agriculture": {"direction": "bullish", "reason": "Ukraine/Russia are major wheat/corn exporters — grain prices spiked"},
                "airlines": {"direction": "bearish", "reason": "Fuel costs + airspace closures"},
                "european_banks": {"direction": "bearish", "reason": "Russian exposure, sanctions uncertainty"},
                "cybersecurity": {"direction": "bullish", "reason": "Cyberwarfare fears drove security spending expectations"},
            },
            "stocks": {
                "bullish": [
                    {"ticker": "XOM", "reason": "Oil major, direct beneficiary of oil price surge"},
                    {"ticker": "CVX", "reason": "Oil major, same thesis"},
                    {"ticker": "LMT", "reason": "Defense contractor, NATO spending increase"},
                    {"ticker": "RTX", "reason": "Defense contractor, missile/air defense demand"},
                    {"ticker": "NOC", "reason": "Defense contractor, surveillance and cyber"},
                    {"ticker": "MOS", "reason": "Fertilizer producer, potash supply disrupted"},
                    {"ticker": "PANW", "reason": "Cybersecurity leader, cyberwarfare fears"},
                ],
                "bearish": [
                    {"ticker": "AAL", "reason": "Airline, fuel cost spike"},
                    {"ticker": "DAL", "reason": "Airline, fuel cost spike + transatlantic disruption"},
                    {"ticker": "EUFN", "reason": "European financials ETF, Russian exposure fears"},
                ],
            },
            "causal_chains": [
                "Russia invades → oil/gas supply risk → energy prices spike → energy stocks rally",
                "Invasion → NATO increases defense budgets → defense contractors benefit",
                "Ukraine/Russia grain exports halted → wheat/corn prices surge → food inflation → fertilizer demand up",
                "Sanctions on Russia → European bank Russian exposure at risk → European financials sell off",
                "Cyberattacks on Ukraine → fear of escalation to Western infrastructure → cybersecurity stocks rally",
                "Oil spike → jet fuel costs surge → airline margins crushed → airline stocks fall",
            ],
        },
    },
    {
        "id": "svb_collapse_2023",
        "name": "Silicon Valley Bank Collapse",
        "date": "2023-03-10",
        "headlines": [
            "Silicon Valley Bank collapses in largest US bank failure since 2008",
            "FDIC seizes SVB after run on deposits; tech startups scramble for cash",
            "Signature Bank shut down by regulators amid contagion fears",
            "Federal Reserve announces emergency lending facility to backstop deposits",
            "Regional bank stocks plunge as investors fear broader banking crisis",
            "Treasury Secretary Yellen says banking system remains resilient",
            "Venture capital firms warn portfolio companies about banking exposure",
        ],
        "market_context": (
            "Fed had been hiking rates aggressively through 2022 into 2023. "
            "SVB held large unrealized losses on long-duration bonds due to rate hikes. "
            "Tech sector was already under pressure from higher rates. "
            "Regional banks had similar duration risk on their balance sheets."
        ),
        "known_outcomes": {
            "sectors": {
                "regional_banks": {"direction": "bearish", "reason": "Contagion fear, deposit flight risk, similar duration exposure"},
                "large_banks": {"direction": "bearish", "reason": "Sympathy selling, but recovered faster — seen as safe haven for deposits"},
                "tech": {"direction": "bullish", "reason": "Counter-intuitive: rate cut expectations rose, benefiting growth stocks"},
                "treasury_bonds": {"direction": "bullish", "reason": "Flight to safety + expectations Fed would pause/cut rates"},
                "gold": {"direction": "bullish", "reason": "Risk-off flows, banking system uncertainty"},
                "crypto": {"direction": "bullish", "reason": "Anti-bank narrative; USDC briefly de-pegged then recovered"},
            },
            "stocks": {
                "bullish": [
                    {"ticker": "JPM", "reason": "Safe haven — deposits flowed from regionals to large banks"},
                    {"ticker": "TLT", "reason": "Long-term bond ETF rallied on rate cut expectations"},
                    {"ticker": "GLD", "reason": "Gold ETF, risk-off buying"},
                    {"ticker": "MSFT", "reason": "Big tech benefited from lower rate expectations"},
                    {"ticker": "AAPL", "reason": "Quality flight within tech"},
                ],
                "bearish": [
                    {"ticker": "FRC", "reason": "First Republic Bank — similar profile to SVB, eventually failed"},
                    {"ticker": "PACW", "reason": "PacWest Bancorp — regional bank with similar risks"},
                    {"ticker": "WAL", "reason": "Western Alliance — regional bank sell-off"},
                    {"ticker": "KRE", "reason": "Regional banking ETF crashed ~30%"},
                    {"ticker": "SCHW", "reason": "Charles Schwab — unrealized bond losses highlighted"},
                ],
            },
            "causal_chains": [
                "Rate hikes → bond portfolio losses at SVB → deposit run → bank failure",
                "SVB fails → contagion fear → regional bank stocks crash → deposit flight to large banks",
                "Banking crisis → Fed expected to pause/cut rates → bond yields drop → tech/growth stocks rally",
                "Bank uncertainty → flight to safety → gold and treasuries rally",
                "SVB failure → crypto-friendly banks (Signature) shut down → brief USDC depeg → crypto initially dips then rallies on anti-bank narrative",
                "Fed emergency lending facility → systemic risk contained → large banks seen as beneficiaries of deposit inflows",
            ],
        },
    },
    {
        "id": "fed_aggressive_hike_2022",
        "name": "Fed 75bp Rate Hike (First Jumbo Hike)",
        "date": "2022-06-15",
        "headlines": [
            "Federal Reserve raises interest rates by 75 basis points, largest hike since 1994",
            "Fed signals more aggressive rate increases ahead to combat 40-year high inflation",
            "CPI hits 8.6% — inflation running far hotter than expected",
            "Powell says 75bp hikes could become more common if inflation doesn't cool",
            "Mortgage rates surge past 6%, highest since 2008",
            "Crypto markets in freefall as risk assets sell off broadly",
            "Dollar strengthens sharply against major currencies",
        ],
        "market_context": (
            "Inflation at 8.6% (May 2022 CPI). Fed had done 25bp in March, 50bp in May. "
            "Market was pricing 50bp but hot CPI forced 75bp. S&P 500 already in bear market territory. "
            "Housing market was booming but mortgage rates rising fast. Crypto had just seen Terra/Luna collapse."
        ),
        "known_outcomes": {
            "sectors": {
                "tech_growth": {"direction": "bearish", "reason": "Higher rates crush growth stock valuations (higher discount rate)"},
                "banks": {"direction": "mixed", "reason": "Higher rates help net interest margins but loan demand falls"},
                "real_estate": {"direction": "bearish", "reason": "Mortgage rates surging, housing demand cooling"},
                "consumer_staples": {"direction": "bullish", "reason": "Defensive rotation, inflation-resilient pricing power"},
                "utilities": {"direction": "bullish", "reason": "Defensive sector, stable dividends attractive"},
                "crypto": {"direction": "bearish", "reason": "Risk-off, liquidity drain, post-Luna fragility"},
                "dollar": {"direction": "bullish", "reason": "Rate differential drives USD strength"},
            },
            "stocks": {
                "bullish": [
                    {"ticker": "UNH", "reason": "Healthcare defensive, pricing power"},
                    {"ticker": "PG", "reason": "Consumer staples, inflation pass-through"},
                    {"ticker": "KO", "reason": "Defensive, global brand with pricing power"},
                    {"ticker": "UUP", "reason": "Dollar bull ETF, USD strengthening"},
                    {"ticker": "XLU", "reason": "Utilities ETF, defensive rotation"},
                ],
                "bearish": [
                    {"ticker": "ARKK", "reason": "High-growth fund crushed by rate hikes"},
                    {"ticker": "SHOP", "reason": "High-multiple growth stock, rate-sensitive"},
                    {"ticker": "COIN", "reason": "Crypto exchange, crypto winter deepening"},
                    {"ticker": "XHB", "reason": "Homebuilders ETF, mortgage rate surge"},
                    {"ticker": "MSTR", "reason": "Bitcoin proxy, crypto crash"},
                ],
            },
            "causal_chains": [
                "Hot CPI → Fed forced to 75bp hike → higher discount rate → growth/tech stocks sell off",
                "Rate hikes → mortgage rates surge → housing demand drops → homebuilders and REITs fall",
                "Higher US rates → dollar strengthens → emerging markets pressured → multinational earnings headwind",
                "Aggressive Fed → risk-off sentiment → crypto sell-off deepens post-Luna",
                "Rate hikes → defensive rotation → staples/utilities/healthcare outperform",
                "Higher rates → bank net interest margins improve BUT loan demand weakens → mixed bank performance",
            ],
        },
    },
    {
        "id": "china_covid_lockdown_2022",
        "name": "Shanghai COVID Lockdown",
        "date": "2022-03-28",
        "headlines": [
            "Shanghai enters full lockdown as China enforces zero-COVID policy on 26 million residents",
            "Major factories shut down across Shanghai including Tesla Gigafactory",
            "Global supply chain disruptions worsen as Chinese ports face massive backlogs",
            "Apple suppliers in Shanghai halt production amid strict lockdown measures",
            "Container shipping rates surge as port congestion spreads across China",
            "China's economic growth forecasts slashed as lockdowns expand",
        ],
        "market_context": (
            "China was enforcing strict zero-COVID while rest of world was reopening. "
            "Global supply chains were already strained from 2021. "
            "Shanghai is China's financial and manufacturing hub — hosts major auto, "
            "semiconductor, and electronics factories. Port of Shanghai is world's busiest."
        ),
        "known_outcomes": {
            "sectors": {
                "shipping": {"direction": "bullish", "reason": "Constrained supply + port backlogs drove shipping rates higher"},
                "auto_manufacturers": {"direction": "bearish", "reason": "Factory shutdowns, parts shortages"},
                "semiconductors": {"direction": "bearish", "reason": "Supply chain disruptions, testing/packaging in Shanghai"},
                "luxury_goods": {"direction": "bearish", "reason": "Chinese consumer spending collapsed during lockdowns"},
                "oil": {"direction": "bearish", "reason": "Chinese demand destruction from lockdowns"},
                "us_retail": {"direction": "bearish", "reason": "Inventory delays, supply chain costs rising"},
            },
            "stocks": {
                "bullish": [
                    {"ticker": "ZIM", "reason": "Container shipping company, rates spiked on congestion"},
                    {"ticker": "MATX", "reason": "Shipping, Pacific trade lane beneficiary"},
                    {"ticker": "DAC", "reason": "Container shipping, supply constraints"},
                ],
                "bearish": [
                    {"ticker": "TSLA", "reason": "Shanghai Gigafactory shut down, production halted"},
                    {"ticker": "AAPL", "reason": "Multiple suppliers in Shanghai halted production"},
                    {"ticker": "NIO", "reason": "Chinese EV maker, factory shutdowns"},
                    {"ticker": "BABA", "reason": "Chinese consumer spending cratered"},
                    {"ticker": "NKE", "reason": "Vietnam/China manufacturing disrupted"},
                ],
            },
            "causal_chains": [
                "Shanghai lockdown → factory shutdowns → auto production halted → TSLA, NIO deliveries hit",
                "Port congestion → shipping rates spike → shipping stocks benefit",
                "Chinese lockdown → demand destruction → oil demand drops → oil prices soften",
                "Apple supplier shutdowns → iPhone production delays → AAPL supply concerns",
                "Zero-COVID → Chinese consumers locked down → luxury/retail spending collapses → BABA, luxury brands hit",
                "Supply chain delays → US retailers face inventory shortages → cost inflation → margin pressure",
            ],
        },
    },
    {
        "id": "ai_boom_2023",
        "name": "ChatGPT / AI Investment Boom",
        "date": "2023-01-30",
        "headlines": [
            "Microsoft announces $10 billion investment in OpenAI, maker of ChatGPT",
            "ChatGPT reaches 100 million users in two months, fastest-growing app ever",
            "Google declares 'code red' over ChatGPT threat, rushes AI announcements",
            "Nvidia reports massive demand surge for AI training chips",
            "Tech giants racing to integrate generative AI into products",
            "AI startups see unprecedented funding as investors chase the next big thing",
            "Enterprise companies scrambling to adopt AI tools for productivity gains",
        ],
        "market_context": (
            "ChatGPT launched Nov 2022, went viral. Tech sector was in a downturn from 2022 rate hikes. "
            "AI narrative emerged as the catalyst to reverse tech pessimism. "
            "Nvidia's data center GPUs were already in demand for ML workloads but AI hype "
            "created a new demand wave. Cloud providers (AWS, Azure, GCP) pivoting to AI services."
        ),
        "known_outcomes": {
            "sectors": {
                "semiconductors": {"direction": "bullish", "reason": "AI training requires massive GPU compute — Nvidia leading"},
                "cloud_infrastructure": {"direction": "bullish", "reason": "AI workloads drive cloud spending"},
                "big_tech": {"direction": "bullish", "reason": "Microsoft, Google, Meta all positioned for AI integration"},
                "traditional_software": {"direction": "mixed", "reason": "AI disruption threat to some; AI integration opportunity for others"},
                "education": {"direction": "bearish", "reason": "Fears of AI replacing tutoring, essay writing, coding bootcamps"},
                "data_centers_reits": {"direction": "bullish", "reason": "AI compute needs physical infrastructure"},
            },
            "stocks": {
                "bullish": [
                    {"ticker": "NVDA", "reason": "AI GPU monopoly, data center revenue exploded"},
                    {"ticker": "MSFT", "reason": "$10B OpenAI investment, Copilot integration across products"},
                    {"ticker": "GOOGL", "reason": "Despite threat narrative, positioned with Bard/Gemini and TPUs"},
                    {"ticker": "AMD", "reason": "Alternative AI chip supplier, MI300 launch"},
                    {"ticker": "META", "reason": "Llama models, AI-driven ad targeting improvements"},
                    {"ticker": "AVGO", "reason": "Custom AI chip demand from hyperscalers"},
                ],
                "bearish": [
                    {"ticker": "CHGG", "reason": "Chegg — AI directly threatens homework help business model"},
                ],
            },
            "causal_chains": [
                "ChatGPT goes viral → enterprise AI adoption accelerates → GPU demand explodes → NVDA revenue surges",
                "Microsoft invests in OpenAI → integrates AI across Office, Azure, Bing → competitive pressure on Google",
                "AI training needs → data center buildout → power/cooling infrastructure demand → utility and REIT stocks benefit",
                "AI threatens existing software models → Chegg, education stocks decline → SaaS companies must integrate AI or face disruption",
                "AI hype → tech sector narrative shifts from rate-fear to AI-growth → tech stocks recover from 2022 bear market",
                "GPU shortage → hyperscalers invest in custom chips → Broadcom, Marvell benefit from ASIC demand",
            ],
        },
    },
]
