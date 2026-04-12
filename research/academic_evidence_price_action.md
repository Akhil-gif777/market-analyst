# Academic & Empirical Evidence: Price Action Trading Signals

> Compiled 2026-04-04. Focus: peer-reviewed studies, specific statistics, win rates, and separation of proven edge from market folklore.

---

## Table of Contents

1. [Candlestick Pattern Reliability](#1-candlestick-pattern-reliability)
2. [Support & Resistance Effectiveness](#2-support--resistance-effectiveness)
3. [Market Structure (HH/HL/LH/LL) — Dow Theory](#3-market-structure-hhhllhll--dow-theory)
4. [Volume Confirmation](#4-volume-confirmation)
5. [RSI and MACD Effectiveness](#5-rsi-and-macd-effectiveness)
6. [Multi-Timeframe Analysis](#6-multi-timeframe-analysis)
7. [Mean Reversion vs Momentum](#7-mean-reversion-vs-momentum)
8. [Insider Trading Signals & PEAD](#8-insider-trading-signals--pead)
9. [Confluence / Multi-Factor Scoring](#9-confluence--multi-factor-scoring)
10. [Summary: What's Proven vs Folklore](#10-summary-whats-proven-vs-folklore)

---

## 1. Candlestick Pattern Reliability

### Academic Verdict: WEAK — Mostly folklore. Marginal edge at best, context-dependent.

### Key Studies

**Duvinage et al. (2013)** — Examined candlestick predictive power at 5-minute intervals for all 30 DJIA constituents. Found **no evidence** that candlesticks outperform buy-and-hold. Concluded candlestick charting methods had no value for trading individual stocks.

**Fock et al. (2005)** — Used mathematical definitions to examine intra-day market performance. Results were **not significantly better than randomized transactions**.

**Tharavanij, Siraprapasiri & Rajchamaha (2017)** — Published in SAGE Open. Tested candlestick patterns on Stock Exchange of Thailand. Found that **most candlestick reversal patterns do not generate statistically significant mean returns**. Binomial tests confirmed most patterns cannot reliably predict market directions.

**Lo, Mamaysky & Wang (2000)** — "Foundations of Technical Analysis" published in the Journal of Finance. Applied nonparametric kernel regression to US stocks 1962-1996. Found that **several technical patterns provided statistically significant results**, especially for small-cap stocks, but the effect was modest and diminishing.

### Specific Win Rates from Backtests

| Pattern | Win Rate | Notes |
|---------|----------|-------|
| Bullish Engulfing | 55-65% | Huge variability (16-75%) depending on trend quality and volume |
| Bearish Engulfing (traded long on ES) | 75.76% | Profit factor 2.73 — pattern performed opposite to traditional interpretation |
| Morning Star | 50-60% baseline, 60-75% with filters | Requires preceding downtrend + volume spike on 3rd candle |
| Hammer | ~55% | Works best in volatile markets, fails in sideways |
| Inverted Hammer | ~60% | ~1% avg return per trade on US equities |
| Harami (2-day) | 72.85% | NIFTY IT sector study — likely market-specific |
| Three White Soldiers / Three Black Crows | 75%+ | Only after pronounced trends with strong volume |

### Key Takeaway

Even the most "reliable" patterns show 55-65% win rates at best — barely enough to overcome transaction costs. Patterns gain marginal edge ONLY when combined with:
- Trend filters (e.g., only bullish patterns in uptrends)
- Volume confirmation
- Support/resistance zones
- The counterintuitive finding (Bearish Engulfing performing as a bullish signal) underscores that **traditional candlestick interpretations may be wrong**.

---

## 2. Support & Resistance Effectiveness

### Academic Verdict: MODERATE — Statistically detectable, but profitability after costs is questionable.

### Key Studies

**Osler (2000)** — Federal Reserve Bank of New York. "Support for Resistance: Technical Analysis and Intraday Exchange Rates." Tested S/R levels provided by six FX firms against actual price behavior. Key findings:
- Published S/R levels predicted intraday trend interruptions significantly better than random levels
- **Bounce frequency: 60.8% for published levels vs. 56.2% for arbitrary levels**
- Edge varied by currency: +4.2% for DEM, +5.6% for JPY, +4.0% for GBP
- Predictive power lasted at least 5 business days
- **Over 70% of S/R levels ended in round numbers** — confirming psychological clustering

**Zapranis & Tsinaslanidis (2012)** — "Identifying and evaluating horizontal support and resistance levels: An empirical study on US stock markets." Found that discovered S/R levels **reverse price trends with statistical significance**. Levels with higher numbers of previous bounces are more likely to bounce again — a self-reinforcing effect.

**Arxiv (2021)** — "Evidence and Behaviour of Support and Resistance Levels in Financial Time Series." Documented that prices are more likely to bounce than cross S/R values. Provided quantitative evidence of the **self-fulfilling prophecy** — self-reinforcement of agents' beliefs about future prices.

### Moving Average S/R (50-day / 200-day)

**Golden Cross / Death Cross Backtest (S&P 500, 1960-present):**
- Only 33 signals in 66 years
- **79% win rate**, average trade gain 15.8%
- Annual return: 6.8% vs. buy-and-hold 7.2% — does NOT beat passive
- Risk-adjusted return: 9.6% (invested only 70% of the time)
- **Max drawdown: 33% vs. 56% for buy-and-hold** — the real value is risk reduction, not return enhancement
- Combining MACD crossovers with MA crossovers increased win rates by 10-15%

### Psychological Levels

Round numbers ($50, $100, $200) act as magnets and barriers due to order clustering. Osler's study confirmed this empirically in FX markets.

### Key Takeaway

S/R is **statistically real** — not folklore. The mechanism is behavioral (order clustering, self-fulfilling prophecy). However, the edge is small (4-6% above random), and profitability after transaction costs is unproven for most implementations. Moving averages as S/R provide value primarily through **risk reduction** (lower drawdowns) rather than higher returns.

---

## 3. Market Structure (HH/HL/LH/LL) — Dow Theory

### Academic Verdict: MODERATE — Trend persistence is real but modest. ~60% continuation probability on monthly timeframes.

### Key Studies

**Goetzmann, Brown & Kumar** — Tested Hamilton's application of Dow Theory (1902-1929). Found the Dow Theory portfolio produced **higher risk-adjusted returns** despite lower absolute returns than buy-and-hold, suggesting value in trend identification for risk management.

**Moskowitz, Ooi & Pedersen (2012)** — "Time Series Momentum." Published in Journal of Financial Economics. Found that each security's own past return predicts future returns. Strategies earned **0.71% per month excess returns** using a six-factor model.

### Trend Continuation Probabilities

**Historical data (1835-1935, 1200 monthly observations):**
- 748 sequences vs. 450 reversals
- **Probability of continuation: 62.5%** — if the market rose in a given month, 62.5% chance it rises the next month (and vice versa for declines)

**Modern research consensus:**
- Momentum persistence is significant for **1-12 month horizons**
- Effect gradually weakens and **reverses beyond 12 months**
- Trend following has been documented across **200+ years of data** as a persistent (though weak) anomaly

### Key Takeaway

Dow Theory's core insight — trends tend to persist — is validated by academic research. The **62.5% continuation probability** is modest but real. The primary value is in **risk management** (staying with trends, avoiding counter-trend trades) rather than generating alpha from market structure alone.

---

## 4. Volume Confirmation

### Academic Verdict: MIXED — Volume-price correlation exists but predictive power for future returns is inconsistent.

### Key Studies

**Karpoff (1987)** — "The Relation Between Price Changes and Trading Volume: A Survey." Published in the Journal of Financial and Quantitative Analysis. Foundational survey establishing:
- Volume is **positively related to the magnitude of price changes**
- In equity markets, volume is positively related to the **price change itself** (not just magnitude)
- However, results were **mixed and not strongly significant** for predicting future returns

Four reasons the relationship matters:
1. Provides insight into market structure
2. Critical for event studies
3. Helps understand the empirical distribution of speculative prices
4. Implications for futures market research

### Volume-Price Divergence

Academic evidence on divergence as a signal:
- If volume stays constant during a price increase, it **suggests weak price movement** with higher reversal probability
- Regular divergence (price up, volume down) indicates **potential trend reversal**
- Hidden divergence (price retraces, volume spikes) suggests **trend continuation**
- However, the **causal relationship from volume to future returns remains a puzzle** — some models predict volume should have predictive power, others suggest no link should exist

### Key Takeaway

Volume confirms **contemporaneous** price moves (big moves come with big volume) — this is well-established. Volume as a **predictor** of future moves is much weaker and inconsistent. The strongest use case is as a **filter** (rejecting low-volume breakouts) rather than as a standalone signal.

---

## 5. RSI and MACD Effectiveness

### Academic Verdict: MODERATE — RSI shows more promise than MACD. Both work best as confirmation tools with filters.

### Key Studies

**Journal of Risk and Financial Management (2014)** — "Revisiting the Performance of MACD and RSI Oscillators." Found:
- MACD(12,26,0) and RSI(21,50) rules generated **significant abnormal returns** in Milan and S&P/TSX indices
- RSI(14,30/70) was also profitable in the DJIA
- However, Australian stock market analysis (1996-2014) found MACD **generally performs poorly**

**Cross-market study (~26 stocks, 7 markets):**
- MACD predicted price direction correctly **56% of the time**
- RSI predicted price direction correctly **81% of the time**

**MACD alone:**
- Win rate **below 50%** when used as sole indicator
- Win rate improves significantly when combined with RSI or other momentum indicators

### Specific Backtest Results

| Strategy | Win Rate | Notes |
|----------|----------|-------|
| RSI oversold (< 30) buy signals | ~55-60% | Without trend filter |
| RSI + trend filter (200 MA) | 60-70% | 15-25% improvement over RSI alone |
| RSI divergence (forex) | 57.9% | |
| Multi-timeframe RSI | 65-75% | |
| MACD alone | < 50% | Not profitable standalone |
| MACD + RSI combined | 73% | Per QuantifiedStrategies backtest |
| RSI + MACD together (R-squared) | 98.45% explained | 2024 study — explains price movements, not necessarily profitable |

### Key Takeaway

RSI is the more useful indicator of the two. MACD alone is essentially noise — it becomes useful only in combination. Both indicators work best when:
- Combined with trend filters (200-day MA)
- Used for confirmation rather than primary signals
- Applied in less-efficient markets (emerging markets show stronger results)
- Used at non-standard settings (RSI at 21-period, 50-level outperforms traditional 14/30/70)

---

## 6. Multi-Timeframe Analysis

### Academic Verdict: PROMISING — Limited formal academic research, but practitioner evidence and backtests show meaningful improvement.

### Evidence

Practitioner backtests consistently report:
- **Single timeframe: ~45% win rate**
- **Multi-timeframe aligned: 58-60% win rate**
- **Overall improvement: 18% better win rates** when weekly + daily alignment is used
- **Risk-adjusted returns improve by 23%**
- **Average holding time increases by 45%** (traders stay in trends longer)

### The Alignment Effect

When signals from the higher timeframe (weekly) and lower timeframe (daily) agree:
- **58% win rate for aligned trades vs. 39% for non-aligned trades**
- This ~19 percentage point gap is one of the largest improvements from any single technique

### Key Takeaway

While formal peer-reviewed evidence is thin, the practitioner data is compelling. Multi-timeframe alignment acts as a **noise filter** — the higher timeframe prevents taking trades against the dominant trend. This is consistent with the momentum research (trends persist), applied hierarchically. The improvement likely comes from **avoiding counter-trend trades** rather than from the timeframe analysis itself being magical.

---

## 7. Mean Reversion vs Momentum

### Academic Verdict: BOTH ARE REAL — Momentum dominates at 1-12 months. Mean reversion dominates at 3-5 years. Combined strategies outperform either alone.

### Momentum Evidence (STRONG)

**Jegadeesh & Titman (1993)** — Seminal paper in the Journal of Finance. "Returns to Buying Winners and Selling Losers."
- Long winners / short losers yields ~**1.5% monthly**
- Six-month strategy earned **~1% per month** abnormal returns (t-stat = 3.07)
- Sample period: 1965-1989
- Profits are **robust to Fama-French three-factor adjustments** — a genuine anomaly, not risk compensation
- Effective over **3 to 12 month holding periods**

**Moskowitz, Ooi & Pedersen (2012)** — Time Series Momentum. Extended to 58 liquid instruments across equity, currency, commodity, and bond markets. Confirmed momentum is **pervasive across asset classes**.

### Mean Reversion Evidence (MODERATE)

**De Bondt & Thaler (1985)** — "Does the Stock Market Overreact?" in the Journal of Finance.
- Past 3-5 year losers outperform past winners over the subsequent 3-5 years
- Sample: US stocks, 1926-1982
- "Loser" portfolios (35 worst-performing stocks) beat "winner" portfolios over next 36 months
- **January effect is pronounced** — losers experience exceptionally large January returns up to 5 years post-formation

### The Interaction

| Time Horizon | Dominant Effect | Approximate Edge |
|-------------|----------------|------------------|
| 1-4 weeks | Short-term reversal (microstructure) | Small |
| 1-12 months | **Momentum** | ~1% per month |
| 12-36 months | Transition / weakening | Uncertain |
| 3-5 years | **Mean reversion** | Significant but slow |

### Combined Strategies

Strategies combining momentum and mean reversion yield **excess returns of 1.1-1.7% per month** and generally **outperform pure momentum or pure mean reversion** strategies.

### Key Takeaway

Momentum is the **strongest anomaly in finance** — it has survived 30+ years of scrutiny, works across markets and asset classes, and cannot be explained by known risk factors. Mean reversion is real but operates on much longer timescales. For a trading system operating on daily/weekly timeframes, **momentum is the more actionable signal**. The ideal approach uses momentum for 1-12 month trades and mean reversion for identifying long-term entry points in oversold names.

---

## 8. Insider Trading Signals & PEAD

### Academic Verdict: STRONG — Two of the most robust anomalies in finance.

### Post-Earnings Announcement Drift (PEAD)

**Bernard & Thomas (1989)** — Established PEAD as one of the most solidly documented pricing anomalies. Key findings:
- Stocks reporting good earnings news drift upward for **at least 60 days**
- Stocks reporting bad earnings news drift downward similarly
- About **6% abnormal 60-day returns** (Dechow et al., 2013)
- Approximately **one-third of the total market response to earnings is delayed**
- The total market reaction around earnings (60 days before to 60 days after) is estimated at **~18%**

**Annual Returns to PEAD Strategy:**
| Study | Annual PEAD Returns |
|-------|-------------------|
| Sadka (2006) | 8.76% |
| Battalio & Mendenhall (2007) | 43.08% |
| Bernard & Thomas (1989) | ~18% annualized abnormal returns |

**PEAD.txt (Philadelphia Fed, 2021)** — Text-based PEAD using NLP analysis of earnings calls. Found that text-based drift is **much larger than classic SUE-based PEAD** in the 2010-2019 period, suggesting investor underreaction goes far beyond headline numbers.

**Important caveat:** PEAD magnitude has been **declining over time** in US markets, from ~18% annualized (1989) toward insignificance in some recent samples, likely due to increased algorithmic trading.

### Insider Trading Signals

**Lakonishok & Lee (2001)** — Review of Financial Studies. Found stocks with heavy insider buying outperformed the market by **4.8% over the following 12 months**.

**Cohen, Malloy & Pomorski (2012)** — Journal of Finance. Distinguished between:
- **"Routine" trades:** Predictable, calendar-based patterns — weak signal
- **"Opportunistic" trades:** Irregular timing, often preceding material news — **6-month alpha of ~5.2%**

**Jeng, Metrick & Zeckhauser (2003)** — Estimated insider purchases earn **~6% per year abnormal returns** above benchmark.

### Cluster Detection

Insider purchasing clusters (multiple insiders buying within a short window) are particularly powerful:
- Multiple independent actors converging on the same conclusion provides stronger statistical power
- **Confirmatory insider trades** (insiders buying after positive earnings) are associated with significantly stronger PEAD

### Key Takeaway

PEAD and insider buying are **among the most well-documented anomalies in finance**. PEAD is weakening in US large caps but remains significant in smaller stocks and when using NLP-enhanced measures. Insider buying (especially opportunistic, clustered purchases) generates meaningful alpha. These signals are **directly implementable** using SEC Form 4 filings and earnings data.

---

## 9. Confluence / Multi-Factor Scoring

### Academic Verdict: SUPPORTED — Combining weak signals into composite scores is well-validated in factor investing literature.

### Evidence

**Multi-Factor Literature:**
- Combining multiple predictors into a composite measure produces **higher signal-to-noise ratios** compared to individual factors
- The **mutual diversification benefit** of combining carry, value, and momentum factors has been repeatedly confirmed
- Such factors "meaningfully expand the investment opportunity set"

**Goldman Sachs Asset Management research** — "How to Combine Investment Signals in Long/Short Strategies." Found that signal combination improves risk-adjusted returns, though the optimal combination method matters.

**Factor Zoo Research (PMC, 2021)** — "Navigating the factor zoo around the world." Evaluated hundreds of proposed factors and found that while many individual factors are weak or spurious, **robust multi-factor combinations** survive out-of-sample testing.

### Machine Learning Confirmation

**ArXiv (2024)** — "Assessing the Impact of Technical Indicators on Machine Learning Models for Stock Price Prediction." Found that combining technical indicators in ML models improves prediction accuracy, suggesting that the **information content of multiple weak signals is complementary, not redundant**.

### The Principle

The statistical basis is straightforward:
- If Signal A has 55% accuracy independently, and Signal B has 55% accuracy independently, and they are **not perfectly correlated**, then their conjunction has higher accuracy
- The key requirement is **independence** — stacking correlated signals (e.g., RSI + Stochastic, which measure essentially the same thing) provides minimal improvement
- Optimal confluence uses **2-4 complementary signals** from different categories (trend, momentum, volume, fundamental)

### Key Takeaway

Signal stacking works, and is well-supported academically. The optimal approach:
1. Select signals from **different categories** (not correlated indicators)
2. Use **2-4 signals** (more leads to overfitting and conflicting signals)
3. Weight signals based on their **individual evidence base** (momentum > candlestick patterns)
4. The improvement is from **noise reduction**, not from discovering a hidden edge

---

## 10. Summary: What's Proven vs Folklore

### TIER 1 — Strong Academic Evidence (Implement with confidence)

| Signal | Evidence Level | Key Stat | Primary Source |
|--------|---------------|----------|---------------|
| **Cross-sectional Momentum** (1-12 month) | Very Strong | ~1% monthly alpha | Jegadeesh & Titman (1993) |
| **PEAD** (post-earnings drift) | Very Strong | 6-18% annualized abnormal returns | Bernard & Thomas (1989) |
| **Insider Buying** (opportunistic) | Strong | 4.8-6% annual excess returns | Lakonishok & Lee (2001), Cohen et al. (2012) |
| **Mean Reversion** (3-5 year) | Strong | Losers outperform winners | De Bondt & Thaler (1985) |
| **Multi-Factor Combination** | Strong | Higher Sharpe than individual signals | Broad factor literature |

### TIER 2 — Moderate Evidence (Useful as confirmation/filters)

| Signal | Evidence Level | Key Stat | Primary Source |
|--------|---------------|----------|---------------|
| **Support/Resistance** | Moderate | 60.8% bounce rate vs 56.2% random | Osler (2000, NY Fed) |
| **Trend Continuation** (Dow Theory) | Moderate | 62.5% monthly continuation probability | Time Series Momentum lit |
| **RSI** (with trend filter) | Moderate | 60-75% win rate with filters | Multiple backtests |
| **Multi-Timeframe Alignment** | Moderate | 58% aligned vs 39% non-aligned | Practitioner evidence |
| **Moving Average Crossovers** | Moderate | 79% win rate but doesn't beat B&H | S&P 500 backtest |

### TIER 3 — Weak Evidence (Likely folklore or marginal)

| Signal | Evidence Level | Key Stat | Primary Source |
|--------|---------------|----------|---------------|
| **Candlestick Patterns** (standalone) | Weak | 55-65% at best, not significant | Duvinage et al. (2013) |
| **MACD** (standalone) | Weak | <50% win rate alone | Multiple studies |
| **Volume as Predictor** | Weak | Contemporaneous correlation, not predictive | Karpoff (1987) |
| **Volume-Price Divergence** | Weak | Theoretically sound, empirically mixed | Academic consensus |

### Implementation Priority for Market Analyst System

Based on evidence strength, the recommended priority for implementation:

1. **Momentum scoring** — strongest academic backing, works across assets and timeframes
2. **PEAD detection** — parse earnings surprises, track 60-day post-announcement drift
3. **Insider buying clusters** — monitor SEC Form 4 filings for opportunistic purchase clusters
4. **Multi-factor confluence scoring** — combine 3-4 uncorrelated signals with evidence-weighted scoring
5. **Multi-timeframe trend alignment** — use weekly trend to filter daily signals
6. **RSI as confirmation** — not primary signal, but useful filter with trend context
7. **Support/resistance zones** — use for entry/exit refinement, not signal generation
8. **Candlestick patterns** — lowest priority; only useful when multiple other factors align

---

## Sources

### Peer-Reviewed Papers
- [Jegadeesh & Titman (1993) — Returns to Buying Winners and Selling Losers](https://www.bauer.uh.edu/rsusmel/phd/jegadeesh-titman93.pdf)
- [Jegadeesh & Titman — Momentum: Evidence and Insights 30 Years Later](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4602426)
- [De Bondt & Thaler (1985) — Does the Stock Market Overreact?](https://onlinelibrary.wiley.com/doi/10.1111/j.1540-6261.1985.tb05004.x)
- [Lo, Mamaysky & Wang (2000) — Foundations of Technical Analysis](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=228099)
- [Tharavanij et al. (2017) — Profitability of Candlestick Charting Patterns](https://journals.sagepub.com/doi/full/10.1177/2158244017736799)
- [Moskowitz, Ooi & Pedersen (2012) — Time Series Momentum](https://www.sciencedirect.com/science/article/pii/S0304405X11002613)
- [Revisiting the Performance of MACD and RSI Oscillators](https://www.mdpi.com/1911-8074/7/1/1)
- [Cohen, Malloy & Pomorski (2012) — Insider Trading](https://clsbluesky.law.columbia.edu/2018/06/05/post-earnings-announcement-drift-and-corporate-insider-trading/)
- [PEAD.txt — Philadelphia Fed Working Paper](https://www.philadelphiafed.org/-/media/frbp/assets/working-papers/2021/wp21-07.pdf)
- [Bernard & Thomas — Post-Earnings Announcement Drift](https://iangow.github.io/far_book/pead.html)

### Federal Reserve / Institutional Research
- [Osler (2000) — Support for Resistance: Technical Analysis and Intraday Exchange Rates (NY Fed)](https://www.newyorkfed.org/research/epr/00v06n2/0007osle.html)
- [Goldman Sachs — How to Combine Investment Signals](https://www.gsam.com/content/dam/gsam/pdfs/institutions/en/articles/2018/Combining_Investment_Signals_in_LongShort_Strategies.pdf)

### Surveys & Meta-Analyses
- [Karpoff (1987) — The Relation Between Price Changes and Trading Volume](https://www.semanticscholar.org/paper/The-Relation-between-Price-Changes-and-Trading-A-Karpoff/88041d631777a162f23599fe5177e06c7558e86b)
- [Momentum Research Summary — Alpha Architect](https://alphaarchitect.com/momentum-research-summary/)
- [50 Years in PEAD Research — Quantpedia](https://quantpedia.com/50-years-in-pead-research/)
- [Navigating the Factor Zoo — PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC8074275/)

### Backtest & Quantitative Sources
- [Candlestick Pattern Success Rates — QuantifiedStrategies](https://www.quantifiedstrategies.com/success-rate-candlestick-patterns/)
- [Golden Cross Trading Strategy Backtest — QuantifiedStrategies](https://www.quantifiedstrategies.com/golden-cross-trading-strategy/)
- [RSI Trading Strategy Backtest — QuantifiedStrategies](https://www.quantifiedstrategies.com/rsi-trading-strategy/)
- [MACD and RSI Strategy — QuantifiedStrategies](https://www.quantifiedstrategies.com/macd-and-rsi-strategy/)
- [Candle Patterns Backtested — Liberated Stock Trader](https://www.liberatedstocktrader.com/candle-patterns-reliable-profitable/)
- [Evidence and Behaviour of S/R Levels — ArXiv](https://arxiv.org/abs/2101.07410)
- [S/R Levels Empirical Study — ResearchGate](https://www.researchgate.net/publication/233852842_Identifying_and_evaluating_horizontal_support_and_resistance_levels_An_empirical_study_on_US_stock_markets)
