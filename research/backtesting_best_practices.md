# Backtesting Best Practices for Confluence Scoring Systems

> Research compiled 2026-04-04. Focused on multi-factor rule-based signal validation,
> not ML-specific techniques. All recommendations are actionable for a price-action
> confluence scoring system.

---

## Table of Contents

1. [Common Backtesting Pitfalls](#1-common-backtesting-pitfalls)
2. [Walk-Forward Analysis](#2-walk-forward-analysis)
3. [Proper Backtesting Metrics](#3-proper-backtesting-metrics)
4. [Position Sizing and Risk Management](#4-position-sizing-and-risk-management)
5. [Confluence Scoring System Validation](#5-confluence-scoring-system-validation)
6. [Transaction Costs and Slippage](#6-transaction-costs-and-slippage)
7. [Regime-Aware Backtesting](#7-regime-aware-backtesting)
8. [Statistical Significance](#8-statistical-significance)
9. [Out-of-Sample Testing](#9-out-of-sample-testing)
10. [Implementation Checklist](#10-implementation-checklist)

---

## 1. Common Backtesting Pitfalls

### 1.1 Lookahead Bias

Using information that would not have been available at the time of the simulated trade.

**Common forms:**
- **Reporting lag**: Using financial data before its actual publication date. Earnings
  reported on Feb 15 should not inform a trade simulated on Feb 10.
- **Data revisions**: Macro data (GDP, jobs) and financial statements get revised.
  The backtest must use the *point-in-time* value, not the final revised value.
- **Indicator calculation**: Using a full bar's high/low/close to make a decision that
  would have been made mid-bar. If your signal fires on a daily close, you cannot
  execute at that day's open.
- **Future information in features**: If any feature uses data from time t+1 to make a
  decision at time t, the backtest is invalid.

**How to prevent:**
- Enforce strict time-indexing: every data point must carry a "known-as-of" timestamp.
- Shift all indicator values by one period before comparing to price.
- Use point-in-time databases for fundamental data.
- Code review specifically for temporal leakage (search for any forward indexing).

### 1.2 Survivorship Bias

Backtesting only on securities that currently exist, ignoring delisted, bankrupt, or
acquired companies.

**Impact**: Inflates annual returns by 1-4% with compounding effects over time. A
strategy that looks profitable may have been buying stocks that later went to zero---
stocks absent from a survivorship-biased dataset.

**How to prevent:**
- Use survivorship-bias-free datasets that include all historical constituents.
- For index-based strategies, use historical index membership lists, not current ones.
- When testing on a stock universe, include delisted tickers and their terminal returns.

### 1.3 Overfitting (Curve Fitting)

A strategy becomes over-specialized to historical patterns, capturing noise rather than
genuine signal. The strategy looks spectacular in-sample but fails out-of-sample.

**Red flags for overfitting:**
- Profit Factor above 3.0 (realistic sustainable range: 1.5-2.0)
- Sharpe Ratio above 3.0 (extremely rare in practice)
- Strategy requires many precise parameter values to work
- Small parameter changes cause large performance swings
- Strategy only works on one specific instrument or time period

**How to prevent:**
- Keep rules simple: fewer parameters = less room to overfit.
- Test parameter sensitivity---a robust strategy works across a *range* of parameter
  values, not just one magic number.
- Require an economic rationale *before* backtesting (hypothesis first, test second).
- Use walk-forward analysis (Section 2) instead of single in-sample optimization.

### 1.4 Data Snooping (P-Hacking)

Running many backtests and reporting only the best one, or iteratively tweaking rules
until the backtest looks good.

**How to prevent:**
- Record every variation tested. Track the total number of trials.
- Apply the Deflated Sharpe Ratio (DSR) correction from Bailey & Lopez de Prado, which
  adjusts the Sharpe Ratio based on the number of trials, skewness, and kurtosis.
- Use Bonferroni or BHY corrections for multiple hypothesis testing.
- The "haircut" to the Sharpe Ratio is nonlinear: Sharpe < 0.4 needs heavy discounting;
  Sharpe > 1.0 needs at most 25% haircut. The common "50% haircut" rule of thumb is
  wrong for both ends.

### 1.5 Storytelling Bias

Finding a pattern first, then inventing an economic rationale to explain it. The
narrative feels convincing but the pattern is random.

**How to prevent:**
- Formulate the hypothesis and economic logic *before* looking at backtest results.
- Document your hypothesis in writing before running any tests.
- If you discover a pattern unexpectedly, treat it as a hypothesis requiring fresh
  out-of-sample confirmation, not a validated finding.

---

## 2. Walk-Forward Analysis

### 2.1 Why Simple Train/Test Splits Fail for Time Series

A single static split has three problems:
1. **One lucky (or unlucky) test period**: The out-of-sample window may happen to be a
   bull market or a crash, giving a biased view.
2. **No parameter adaptation**: Markets evolve; a strategy optimized on 2010-2018 data
   may be stale by 2019.
3. **Temporal dependence**: Financial returns are not i.i.d. Standard k-fold
   cross-validation shuffles time order, destroying autocorrelation structure and
   creating information leakage.

### 2.2 Walk-Forward Methodology

Walk-forward analysis simulates how a strategy would actually be deployed: optimize on
the past, trade the next unseen period, then roll forward and repeat.

**Steps:**
1. Divide historical data into sequential segments.
2. Use the first N segments as the in-sample (IS) optimization window.
3. Apply the optimized parameters to the next segment (out-of-sample, OOS).
4. Record OOS performance.
5. Slide the window forward by one segment and repeat.
6. Concatenate all OOS segments into one continuous equity curve for evaluation.

**Key parameters:**

| Parameter | Recommendation | Rationale |
|-----------|---------------|-----------|
| IS:OOS ratio | 3:1 to 4:1 (75-80% IS, 20-25% OOS) | Enough IS data to optimize, enough OOS to validate |
| Number of windows | 6-10 minimum | More windows = more robust, but each window is smaller |
| Window type | Rolling (preferred) over Anchored | Rolling adapts to regime changes; anchored dilutes recent data with distant past |
| Step size | Equal to OOS window length | Ensures every data point appears in exactly one OOS window |

### 2.3 Anchored vs. Rolling Windows

- **Anchored (Expanding)**: IS window always starts from the beginning and grows. Good
  when you believe all history is relevant. Risk: distant data dilutes recent regime.
- **Rolling**: IS window is a fixed length that slides forward. Better when recent data
  is more relevant than ancient data. Preferred for most trading applications.

### 2.4 Walk-Forward Efficiency (WFE)

WFE = (Annualized OOS Return) / (Annualized IS Return)

- WFE > 50-60%: Strategy has a good chance of being profitable live.
- WFE < 50%: Strategy is likely overfit to in-sample data.
- WFE near 100% or above: Suspicious---may indicate IS underperformance or data issues.

### 2.5 Meta-Overfitting Warning

You can overfit the walk-forward process itself by adjusting window sizes, fitness
functions, and parameter ranges until WF results look good. This defeats the purpose.

**Mitigation**: Fix your WF parameters (window size, step size, optimization criteria)
*before* running the analysis. Do not iterate on the WF configuration.

---

## 3. Proper Backtesting Metrics

### 3.1 Why Win Rate Alone Is Misleading

A 90% win rate with $10 average wins and $200 average losses is a losing strategy.
Conversely, a 35% win rate with $300 average wins and $50 average losses is highly
profitable. Always evaluate win rate alongside average win/loss ratio.

### 3.2 Core Metrics Suite

**Risk-Adjusted Return Metrics:**

| Metric | Formula | Good Threshold | Notes |
|--------|---------|---------------|-------|
| **Sharpe Ratio** | (Return - Risk-Free) / StdDev(Returns) | > 1.0 (backtest); expect 30-50% degradation live | Most widely used; penalizes all volatility equally |
| **Sortino Ratio** | (Return - Risk-Free) / Downside StdDev | > 2.0 | Only penalizes downside volatility; better for asymmetric strategies |
| **Calmar Ratio** | Annual Return / Max Drawdown | > 1.0 (good), > 3.0 (excellent) | Directly links return to worst-case pain |

**Risk Metrics:**

| Metric | What It Measures | Realistic Planning |
|--------|-----------------|-------------------|
| **Max Drawdown** | Largest peak-to-trough decline | Plan for live drawdowns 1.5-2x worse than backtest |
| **Max Drawdown Duration** | Longest time to recover from a drawdown | Critical for psychological sustainability |
| **Ulcer Index** | Duration-weighted drawdown severity | Captures both depth and duration of drawdowns |

**Profitability Metrics:**

| Metric | Formula | Good Threshold |
|--------|---------|---------------|
| **Profit Factor** | Gross Profit / Gross Loss | > 1.5 (sustainable); > 3.0 is suspect |
| **Expectancy** | (Win% x Avg Win) - (Loss% x Avg Loss) | > 0 (positive edge) |
| **Expectancy per dollar risked** | Expectancy / Avg Risk per Trade | Normalizes across different position sizes |

**Trade Quality Metrics:**

| Metric | What It Measures |
|--------|-----------------|
| **Average Trade Duration** | How long capital is tied up |
| **Trade Frequency** | Number of trades per period; too few = statistically weak |
| **Consecutive Losses (max)** | Psychological stress test; plan for 2x the backtest max |
| **Recovery Factor** | Net Profit / Max Drawdown; how quickly drawdowns are recovered |

### 3.3 Integrated Evaluation

No single metric tells the full story. Evaluate as a system:

- A strategy with Sharpe 1.5 but Max Drawdown 60% may be unacceptable.
- A strategy with low Sharpe 0.5 but Calmar 2.0 and Max Drawdown 8% may be excellent
  for capital preservation.
- Always report metrics *with* sample size and regime coverage.

### 3.4 Degradation Expectations (Backtest vs. Live)

| Metric | Expected Live Degradation |
|--------|--------------------------|
| Sharpe Ratio | 30-50% lower |
| Max Drawdown | 1.5-2x worse |
| Win Rate | 5-10% lower |
| Profit Factor | 20-30% lower |
| Consecutive Losses | Up to 2x more |

Build these degradation factors into your go/no-go criteria. If the strategy does not
survive these haircuts, it is not robust enough for live trading.

---

## 4. Position Sizing and Risk Management

### 4.1 Fixed Fractional Sizing

Risk a fixed percentage of account equity per trade (typically 1-2%).

```
Position Size = (Account Equity x Risk%) / (Entry Price - Stop Price)
```

**Pros**: Simple, automatically reduces size during drawdowns, increases during growth.
**Cons**: Can be too conservative for high-confidence setups.

### 4.2 Kelly Criterion

Calculates the theoretically optimal bet size to maximize long-term geometric growth:

```
Kelly% = W - [(1 - W) / R]

Where:
  W = Win probability
  R = Win/Loss ratio (average win / average loss)
```

**Critical caveats:**
- Full Kelly is *extremely* aggressive---can produce 50-70% drawdowns.
- Full Kelly assumes perfect knowledge of W and R, which are only estimates.
- **Always use Fractional Kelly** (typically Half-Kelly or Quarter-Kelly):
  - Half-Kelly: 75% of Kelly's growth rate with dramatically lower drawdowns.
  - Quarter-Kelly: Very conservative, but robust to parameter estimation error.

**For a confluence scoring system**: Use Kelly to *inform* relative sizing across signal
strength tiers, not as an absolute position sizer:
- High-confluence signal (e.g., 8/10 score): Size at Half-Kelly.
- Medium-confluence signal (e.g., 6/10 score): Size at Quarter-Kelly.
- Low-confluence signal (e.g., 4/10 score): Minimum size or skip.

### 4.3 Volatility-Based Sizing

Normalize position sizes by recent volatility (e.g., ATR):

```
Position Size = (Account Equity x Risk%) / (N x ATR)

Where N is a multiplier (e.g., 2x ATR for stop distance)
```

This automatically trades smaller in volatile markets and larger in calm markets.

### 4.4 Risk Management in Backtests

**Must-include rules:**
- Maximum portfolio heat (total open risk): typically 6-10% of equity.
- Maximum correlated positions: limit exposure to any single sector/theme.
- Maximum drawdown circuit breaker: if drawdown exceeds X%, reduce size or stop trading
  until recovery.
- Risk per trade should not exceed 1-2% for backtesting validation.

---

## 5. Confluence Scoring System Validation

### 5.1 Validating Individual Factors

Before testing the combined scoring system, validate each factor independently:

1. **Isolate each factor**: Test each signal component (e.g., RSI divergence, support/
   resistance confluence, volume confirmation) as a standalone entry criterion.
2. **Measure standalone edge**: Does the factor alone produce a positive expectancy?
   It does not need to be highly profitable alone, but it should show *some* directional
   edge (better than random).
3. **Measure marginal contribution**: Add each factor incrementally to the base system
   and measure the *improvement* in key metrics (Sharpe, Profit Factor, Max Drawdown).
   A factor that does not improve the system should be removed.
4. **Test for redundancy**: If two factors always agree (correlation > 0.8), one is
   redundant. Keeping both inflates your confluence score without adding information.

### 5.2 Weight Calibration

Assign weights based on empirical reliability, not intuition:

**Recommended approach:**
1. Backtest each factor independently and rank by standalone Sharpe Ratio.
2. Assign initial weights proportional to standalone performance.
3. Run combinatorial tests to find the weight set that maximizes OOS Sharpe (using
   walk-forward analysis to avoid overfitting the weights themselves).
4. Validate that the weight ranking makes economic sense.

**Example weight hierarchy (from research on confluence systems):**
- Core signal (e.g., key level + price action pattern): 30 points
- Volume/momentum confirmation: 25 points
- Trend alignment (multi-timeframe): 20 points
- Volatility regime filter: 15 points
- Secondary confirmation (e.g., RSI extreme): 10 points
- Total: 100 points. Signal threshold: 60+ to trigger trade.

### 5.3 Threshold Sensitivity Analysis

The signal threshold (minimum score to trigger a trade) is a critical parameter that
must be tested for robustness:

1. Test thresholds from 30 to 90 in increments of 5.
2. Plot Sharpe Ratio, Profit Factor, and Trade Count vs. threshold.
3. The optimal threshold should sit on a *plateau*, not a spike. If performance is only
   good at exactly threshold = 65 but collapses at 60 and 70, the system is overfit.
4. Choose a threshold in the middle of the plateau, not at the peak.

### 5.4 Factor Stability Testing

Test that factor performance is stable across:
- Different time periods (2015-2018 vs 2019-2022 vs 2023-2025)
- Different market regimes (bull, bear, sideways, high-vol, low-vol)
- Different instruments within the same asset class
- Different timeframes (if applicable)

A factor that works only in one regime or one period is unreliable.

### 5.5 Correlation and Interaction Effects

- Compute pairwise correlation between all factor signals.
- Test for interaction effects: do certain factor *combinations* produce outsized
  returns (positive interaction) or cancel each other out (negative interaction)?
- Beware of "phantom confluence"---factors that are mathematically derived from the same
  underlying data (e.g., RSI and Stochastic both derive from price) do not provide
  truly independent confirmation.

---

## 6. Transaction Costs and Slippage

### 6.1 Cost Components

| Component | Description | Typical Range (Equities) |
|-----------|-------------|------------------------|
| Commission | Broker fees per trade | $0-5 per trade (most now $0 for retail) |
| Bid-Ask Spread | Cost of crossing the spread | 1-10 bps for large-caps; 10-50+ bps for small-caps |
| Slippage | Difference between expected and actual fill price | 1-15 bps depending on liquidity |
| Market Impact | Price movement caused by your order | Negligible for retail; significant for institutional |

### 6.2 Cost Models

**For a retail-scale confluence scoring system, use the Piecewise-Linear model:**

```
Total Cost Per Trade = Commission + Spread_Cost + Slippage

Where:
  Spread_Cost = 0.5 x Typical_Bid_Ask_Spread
  Slippage    = f(volatility, liquidity, order_size)
```

**Practical defaults for backtesting (conservative):**
- Large-cap equities / major ETFs: 5-10 bps round-trip (combined spread + slippage)
- Mid-cap equities: 15-25 bps round-trip
- Small-cap equities: 30-50+ bps round-trip

### 6.3 Four Transaction Cost Models (Increasing Realism)

| Model | When to Use |
|-------|-------------|
| **Flat** (constant per trade) | Quick prototyping only; unrealistic |
| **Linear** (proportional to trade size) | Simple approximation; overestimates small trades |
| **Piecewise-Linear** (different rates for size buckets) | Industry standard; good balance of accuracy and simplicity |
| **Quadratic / Square-Root** (market impact ~ sqrt(order_size)) | Most realistic for larger orders; based on Almgren et al. |

### 6.4 Implementation Rules

1. **Never backtest without costs**. A zero-cost backtest is fiction.
2. **Use conservative estimates**. If unsure, double your cost assumption.
3. **Recalibrate periodically**. Spreads and commissions change over time.
4. **Test cost sensitivity**: Run the backtest at 1x, 2x, and 3x your base cost
   assumption. If the strategy dies at 2x costs, it has a thin edge and is risky.
5. **Account for spread widening**: During volatile periods (exactly when many signals
   fire), spreads widen significantly. Use regime-dependent cost models.
6. **Trend-following suffers more from slippage** than mean-reversion (buying into
   momentum means worse fills). Factor this into your confluence system's cost model
   based on signal type.

---

## 7. Regime-Aware Backtesting

### 7.1 Why Regime Awareness Matters

A strategy that works in a bull market may hemorrhage in a bear market. Aggregate
backtest metrics hide this---a strategy can show a Sharpe of 1.5 overall while losing
money in 3 out of 5 regime types.

### 7.2 Market Regime Classification

**Six primary regimes (2 dimensions: trend x volatility):**

| Regime | Trend | Volatility | Characteristics |
|--------|-------|-----------|-----------------|
| Bull Quiet | Up | Low | Steady grind higher; trend-following excels |
| Bull Volatile | Up | High | Sharp rallies with pullbacks; momentum strategies work |
| Sideways Quiet | Flat | Low | Range-bound; mean-reversion works, trend-following fails |
| Sideways Volatile | Flat | High | Whipsaws; most strategies perform poorly |
| Bear Quiet | Down | Low | Slow decline; short-bias or defensive strategies |
| Bear Volatile | Down | High | Crash / capitulation; most strategies fail |

### 7.3 Regime Detection Methods (Simple, Non-ML)

For a rule-based system, use straightforward indicators:

**Trend detection:**
- Price vs. 200-day SMA (above = bull, below = bear)
- 50/200 SMA crossover (golden cross / death cross)
- ADX > 25 = trending, ADX < 20 = sideways

**Volatility detection:**
- VIX level: < 15 = low vol, 15-25 = normal, > 25 = high vol
- ATR percentile rank over trailing 252 days
- Realized volatility (20-day) vs. its 1-year average

### 7.4 Regime-Stratified Backtest Reporting

**Required**: Break down all metrics by regime:

```
| Metric         | Bull Quiet | Bull Vol | Sideways | Bear Quiet | Bear Vol | All |
|----------------|-----------|----------|----------|------------|----------|-----|
| Trades         |    45     |    22    |    38    |     15     |    12    | 132 |
| Win Rate       |   68%     |   55%    |   42%    |    33%     |   25%    | 52% |
| Profit Factor  |   2.1     |   1.6    |   1.1    |    0.7     |   0.5    | 1.4 |
| Sharpe         |   1.8     |   1.0    |   0.3    |   -0.5     |  -1.2    | 0.8 |
| Max Drawdown   |   -5%     |  -12%    |   -8%    |   -18%     |  -25%    | -25%|
```

This table immediately reveals where the strategy works and where it fails.

### 7.5 Regime-Adaptive Rules

Based on regime-stratified results, consider:
- **Regime filters**: Only trade when the regime is favorable (e.g., skip Sideways
  Volatile and Bear Volatile).
- **Regime-adjusted sizing**: Trade full size in Bull Quiet, half size in Sideways,
  quarter size or flat in Bear Volatile.
- **Regime-adjusted thresholds**: Require higher confluence scores in unfavorable
  regimes (e.g., 70+ in sideways vs. 55+ in bull).

**Caution**: Every regime-adaptive rule adds a parameter. Keep it simple---one or two
regime filters maximum to avoid meta-overfitting.

---

## 8. Statistical Significance

### 8.1 Minimum Sample Size

| Trade Count | Statistical Reliability |
|------------|----------------------|
| < 30 | Unreliable; treat as hypothesis only |
| 30-100 | Preliminary evidence; wide confidence intervals |
| 100-200 | Reasonable for initial validation |
| 200-500 | Good statistical power for most metrics |
| 500+ | Strong evidence; can detect small edges reliably |

**Central Limit Theorem**: ~30 trades allows the distribution of sample means to
approximate normal, which is the *minimum* for any statistical test. But for trading,
aim for 100+ trades as a baseline, 200+ for meaningful regime-stratified analysis.

**Quality matters alongside quantity**: 80 trades across 15 years of mixed conditions
are more robust than 150 trades from a single 6-month bull run.

### 8.2 Hypothesis Testing Framework

**Null hypothesis (H0)**: The strategy has no edge (expected return = 0).
**Alternative hypothesis (H1)**: The strategy has a positive edge.

**Test**: One-sample t-test on per-trade returns.

```
t-statistic = (Mean Return per Trade) / (StdDev of Returns / sqrt(N))

Where N = number of trades
```

- p < 0.05: Statistically significant at 95% confidence.
- p < 0.01: Strong evidence.
- p < 0.001: Very strong evidence.

**Multiple testing correction**: If you tested K strategy variations, use:
- **Bonferroni**: Multiply each p-value by K. Simple but conservative.
- **Holm**: Less conservative; applies decreasing adjustments.
- **BHY (False Discovery Rate)**: Controls the expected proportion of false discoveries.
  Best for large numbers of tests.

### 8.3 Bootstrap Confidence Intervals

When sample size is limited or returns are non-normal:

1. Resample N trades *with replacement* from your trade log.
2. Compute the metric of interest (Sharpe, Profit Factor, etc.) on the resample.
3. Repeat 1,000-10,000 times.
4. The 2.5th and 97.5th percentiles form a 95% confidence interval.

**Block bootstrap**: If trades are autocorrelated (e.g., clustered in time), resample
*blocks* of consecutive trades rather than individual trades. This preserves the
temporal structure.

### 8.4 Monte Carlo Simulation

**Trade reshuffling**: Randomly reorder historical trades 1,000+ times. All reshuffled
equity curves end at the same total P&L, but the *paths* differ. This reveals:
- The distribution of possible max drawdowns.
- Confidence intervals for drawdown expectations.
- The probability of hitting a specific drawdown level.

**Randomized entry/exit test**: Re-trade original entries while randomizing exits (or
vice versa). If results remain profitable, the tested component (entry or exit) likely
contains genuine edge. If profitability disappears when entries are randomized, the
entry signal has real value.

### 8.5 Permutation Test for Edge Detection

1. Take your actual trade returns sequence.
2. Randomly shuffle the sign (long/short assignment) of each trade 10,000 times.
3. Compute the strategy metric on each shuffled version.
4. If your actual metric ranks in the top 5% of shuffled metrics, the edge is
   statistically significant at p < 0.05.

This is distribution-free (no normality assumption) and directly tests whether the
signal's directional calls add value.

---

## 9. Out-of-Sample Testing

### 9.1 The Three-Dataset Paradigm

| Dataset | Purpose | Typical Allocation |
|---------|---------|-------------------|
| **Training (In-Sample)** | Develop and optimize strategy rules/parameters | 60% of data |
| **Validation** | Tune hyperparameters, select between strategy variants | 20% of data |
| **Test (True OOS)** | Final evaluation; touch ONCE | 20% of data |

**Critical rule**: The test set must be used exactly *once*. If you look at test results
and then modify the strategy, the test set is contaminated and becomes in-sample.

### 9.2 Combinatorial Purged Cross-Validation (CPCV)

The gold standard from Lopez de Prado for financial time series:

1. Divide data into S sequential segments.
2. Generate all combinations of train/test splits where each segment appears in the
   test set at least once.
3. **Purge**: Remove training samples that overlap temporally with test samples (prevents
   information leakage from autocorrelation).
4. **Embargo**: Add a buffer period after each purge to further reduce leakage.
5. Average performance across all splits.

**Advantages over simple OOS:**
- Every data point is used for both training and testing across different splits.
- Produces a distribution of OOS performance, not a single point estimate.
- Enables computation of the Probability of Backtest Overfitting (PBO).

### 9.3 Probability of Backtest Overfitting (PBO)

PBO measures the probability that the strategy selected by in-sample optimization will
underperform the median of all tested strategies out-of-sample.

- PBO < 10%: Low overfitting risk.
- PBO 10-30%: Moderate risk; proceed with caution.
- PBO > 30%: High overfitting risk; strategy is likely curve-fit.

### 9.4 Practical OOS Protocol for Confluence Scoring Systems

Since a confluence scoring system has relatively few parameters (weights, threshold),
overfitting risk is lower than for highly parameterized strategies. But it still exists.

**Recommended protocol:**
1. **Design phase** (no data): Define factors and scoring logic based on economic
   rationale and market structure theory.
2. **In-sample development** (60% of data): Test individual factors, calibrate weights,
   set threshold. Use walk-forward analysis within this period.
3. **Validation** (20% of data): Test the complete system without modification. Assess
   regime robustness. Minor threshold adjustments only if strongly justified.
4. **Final test** (20% of data, most recent): Run once. Report results honestly.
   No modifications after this point.
5. **Paper trading**: Forward-test on live data for 3-6 months minimum before committing
   real capital.

### 9.5 Avoiding Overfitting in Rule-Based Systems

Rule-based systems have a specific overfitting risk: adding rules until the backtest
looks perfect. Each added rule is an implicit parameter.

**Guidelines:**
- Cap the total number of rules/factors (5-7 is a practical maximum for a confluence
  system).
- Every rule must have a clear economic rationale independent of the backtest.
- Measure the marginal improvement of each rule; if a rule improves Sharpe by less than
  0.1, it is likely fitting noise.
- Test rule removal: if removing any single rule destroys the strategy, the system is
  fragile and over-dependent on that rule.
- Prefer *continuous scoring* (factors add points) over *binary gating* (all conditions
  must be true). Binary gates are more prone to overfitting.

---

## 10. Implementation Checklist

### Pre-Backtest Checklist

- [ ] Economic hypothesis documented *before* any backtesting
- [ ] Data is survivorship-bias-free
- [ ] Point-in-time data for any fundamental/macro inputs
- [ ] No lookahead bias in indicator calculations (shifted by 1 period)
- [ ] Transaction cost model defined (spread + slippage, conservative)
- [ ] Position sizing rules defined (fixed fractional or volatility-based)
- [ ] Risk management rules defined (max risk per trade, max portfolio heat)
- [ ] Walk-forward parameters fixed *before* running (window size, step, IS:OOS ratio)

### During Backtest

- [ ] Track all strategy variations tested (total trial count)
- [ ] Test each factor independently before combining
- [ ] Run threshold sensitivity analysis (plateau check)
- [ ] Run parameter sensitivity analysis (nearby values should also work)
- [ ] Run cost sensitivity analysis (1x, 2x, 3x base costs)
- [ ] Compute all core metrics (Sharpe, Sortino, Calmar, MDD, Profit Factor, Expectancy)
- [ ] Break down metrics by market regime

### Post-Backtest Validation

- [ ] Walk-forward efficiency > 50%
- [ ] Minimum 100 trades in OOS periods (200+ preferred)
- [ ] p-value < 0.05 on per-trade returns (after multiple testing correction)
- [ ] Bootstrap 95% CI for Sharpe Ratio does not include zero
- [ ] Monte Carlo max drawdown at 95th percentile is acceptable
- [ ] PBO < 30% (if using CPCV)
- [ ] Strategy survives expected live degradation haircuts
- [ ] Regime-stratified analysis shows no catastrophic regime
- [ ] Permutation test confirms directional edge (p < 0.05)

### Go/No-Go Decision Framework

**Green light** (all required):
- OOS Sharpe > 0.5 after haircuts
- OOS Profit Factor > 1.3
- OOS Max Drawdown < 25% (or your personal tolerance)
- Statistical significance p < 0.05
- Positive expectancy in at least 4 of 6 regime types
- WFE > 50%

**Yellow light** (proceed to paper trading with reduced size):
- OOS Sharpe 0.3-0.5 after haircuts
- Mixed regime performance but positive overall
- Marginal statistical significance (p = 0.05-0.10)

**Red light** (do not trade):
- OOS Sharpe < 0.3 after haircuts
- PBO > 30%
- Negative expectancy in 3+ regime types
- Strategy dies at 2x cost assumption
- Fewer than 100 OOS trades

---

## Sources

### Backtesting Pitfalls
- [The Critical Pitfalls of Backtesting Trading Strategies](https://starqube.com/backtesting-investment-strategies/)
- [Backtesting Traps: Common Errors to Avoid - LuxAlgo](https://www.luxalgo.com/blog/backtesting-traps-common-errors-to-avoid/)
- [Problems in Backtesting and Biases in Data - AnalystPrep](https://analystprep.com/study-notes/cfa-level-2/problems-in-backtesting/)
- [Backtesting Biases: How Traders Fool Themselves - FX Replay](https://www.fxreplay.com/learn/backtesting-biases-how-traders-fool-themselves-without-knowing-it)
- [The Seven Sins of Quantitative Investing](https://bookdown.org/palomar/portfoliooptimizationbook/8.2-seven-sins.html)
- [How To Avoid Bias in Backtesting - For Traders](https://www.fortraders.com/blog/how-to-avoid-bias-in-backtesting)

### Walk-Forward Analysis
- [Walk-Forward Analysis: Deep Dive - Interactive Brokers](https://www.interactivebrokers.com/campus/ibkr-quant-news/the-future-of-backtesting-a-deep-dive-into-walk-forward-analysis/)
- [Walk-Forward Optimization: How It Works - QuantInsti](https://blog.quantinsti.com/walk-forward-optimization-introduction/)
- [Walk-Forward Analysis vs. Backtesting - Surmount](https://surmount.ai/blogs/walk-forward-analysis-vs-backtesting-pros-cons-best-practices)
- [Walk Forward Optimization - Wikipedia](https://en.wikipedia.org/wiki/Walk_forward_optimization)
- [How to Use Walk Forward Analysis - Unger Academy](https://ungeracademy.com/posts/how-to-use-walk-forward-analysis-you-may-be-doing-it-wrong)
- [Walk-Forward Validation Framework - arxiv](https://arxiv.org/html/2512.12924v1)

### Backtesting Metrics
- [Top 7 Metrics for Backtesting Results - LuxAlgo](https://www.luxalgo.com/blog/top-7-metrics-for-backtesting-results/)
- [How to Evaluate a Trading Strategy Like a Quant](https://medium.com/@yavuzakbay/how-to-evaluate-a-trading-strategy-like-a-quant-fc903e093015)
- [Advanced Trading Metrics: Sharpe, Sortino, Calmar, SQN](https://algostrategyanalyzer.com/en/blog/advanced-trading-metrics/)
- [Trading Performance: Strategy Metrics - Quantified Strategies](https://www.quantifiedstrategies.com/trading-performance/)
- [Backtesting Metrics Explained - HorizonAI](https://www.horizontrading.ai/learn/backtesting-metrics-explained)

### Position Sizing
- [How to Size Your Trades: Fixed, Percent, Fractional, and Kelly](https://pyquantlab.medium.com/how-to-size-your-trades-fixed-percent-fractional-and-kelly-position-sizing-explained-3695b443ecfc)
- [Kelly Criterion - Wikipedia](https://en.wikipedia.org/wiki/Kelly_criterion)
- [Kelly Criterion for Stock Trading - Zerodha Varsity](https://zerodha.com/varsity/chapter/kellys-criterion/)
- [Analysis of The Kelly Criterion in Practice - Alpha Theory](https://www.alphatheory.com/blog/kelly-criterion-in-practice-1)

### Transaction Costs and Slippage
- [Transaction Cost Modelling - BSIC Bocconi](https://bsic.it/backtesting-series-episode-5-transaction-cost-modelling/)
- [Successful Backtesting Part II - QuantStart](https://www.quantstart.com/articles/Successful-Backtesting-of-Algorithmic-Trading-Strategies-Part-II/)
- [Realistic Backtesting: Transaction Costs and Slippage - Hyper Quant](https://www.hyper-quant.tech/research/realistic-backtesting-methodology)
- [Impact of Transaction Costs and Slippage - ResearchGate](https://www.researchgate.net/publication/384458498_The_impact_of_transactions_costs_and_slippage_on_algorithmic_trading_performance)

### Regime-Aware Backtesting
- [Market Regimes Explained - LuxAlgo](https://www.luxalgo.com/blog/market-regimes-explained-build-winning-trading-strategies/)
- [Classifying Market Regimes - Macrosynergy](https://macrosynergy.com/research/classifying-market-regimes/)
- [Mastering Market Regimes - StatOasis](https://statoasis.com/post/mastering-market-regimes-when-to-trade-and-when-to-stay-out)
- [Regime-Switching Factor Investing with HMMs - MDPI](https://www.mdpi.com/1911-8074/13/12/311)

### Statistical Significance
- [How Many Trades Are Enough? Statistical Significance in Backtesting](https://medium.com/@trading.dude/how-many-trades-are-enough-a-guide-to-statistical-significance-in-backtesting-093c2eac6f05)
- [Is Your Strategy Just Lucky? Statistical Validation](https://medium.com/@trading.dude/is-your-strategy-just-lucky-how-to-statistically-validate-your-backtest-37ed5429a031)
- [Monte Carlo Simulations: Strategy Validation - QuantProof](https://quantproof.io/blog/monte-carlo-simulations-trading-strategy-validation)
- [5 Monte Carlo Methods - StrategyQuant](https://strategyquant.com/blog/new-robustness-tests-on-the-strategyquant-codebase-5-monte-carlo-methods-to-bulletproof-your-trading-strategies/)
- [Monte Carlo Simulation - Build Alpha](https://www.buildalpha.com/monte-carlo-simulation/)
- [Hypothesis Testing In Trading - QuantInsti](https://blog.quantinsti.com/hypothesis-testing-trading-guide/)

### Out-of-Sample Testing and Overfitting Prevention
- [The Deflated Sharpe Ratio - Bailey & Lopez de Prado (PDF)](https://www.davidhbailey.com/dhbpapers/deflated-sharpe.pdf)
- [Probability of Backtest Overfitting - Bailey et al.](https://www.researchgate.net/publication/318600389_The_probability_of_backtest_overfitting)
- [Combinatorial Purged Cross-Validation - QuantInsti](https://blog.quantinsti.com/cross-validation-embargo-purging-combinatorial/)
- [Traditional Backtesting is Outdated: Use CPCV](https://www.insightbig.com/post/traditional-backtesting-is-outdated-use-cpcv-instead)
- [Backtesting - Harvey & Liu (2015)](https://alphaarchitect.com/backtesting-strategies-based-multiple-signals-beware-overfitting-biases/)
- [Backtest Overfitting Comparison of OOS Methods](https://www.sciencedirect.com/science/article/abs/pii/S0950705124011110)
- [Developing & Backtesting Systematic Trading Strategies - Peterson](https://www.researchgate.net/publication/319298448_Developing_Backtesting_Systematic_Trading_Strategies)
