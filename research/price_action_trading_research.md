# Price Action Trading: Comprehensive Research Document

> Compiled for programmatic implementation and backtesting purposes.
> Focus: codifiable rules, quantitative evidence, and algorithmic detection.

---

## Table of Contents

1. [Core Price Action Concepts & Methodology](#1-core-price-action-concepts--methodology)
2. [Popular Price Action Strategies](#2-popular-price-action-strategies)
3. [Key Books](#3-key-books)
4. [Multi-Timeframe Analysis Best Practices](#4-multi-timeframe-analysis-best-practices)
5. [What Makes a High-Probability Setup](#5-what-makes-a-high-probability-price-action-setup)
6. [Quantitative/Testable Price Action Rules](#6-quantitativetestable-price-action-rules)

---

## 1. Core Price Action Concepts & Methodology

### 1.1 Market Structure (HH/HL/LH/LL, BOS, CHoCH)

**Definitions:**

- **Higher High (HH):** A swing high that exceeds the previous swing high. Confirms bullish continuation.
- **Higher Low (HL):** A swing low that holds above the previous swing low. Confirms bullish structure.
- **Lower High (LH):** A swing high that fails to reach the previous swing high. Confirms bearish continuation.
- **Lower Low (LL):** A swing low that breaks below the previous swing low. Confirms bearish structure.
- **Uptrend:** Series of HH + HL. **Downtrend:** Series of LH + LL. **Range:** No clear sequence.

**Break of Structure (BOS):**
A BOS occurs when price closes beyond a prior swing point in the direction of the prevailing trend. Specifically:
- **Bullish BOS:** Price breaks above a prior swing high during an uptrend, forming a new HH.
- **Bearish BOS:** Price breaks below a prior swing low during a downtrend, forming a new LL.
- BOS confirms trend continuation and tells you which side (buyers/sellers) is in control.

**Change of Character (CHoCH):**
Also called "Market Structure Shift" (MSS). A CHoCH signals potential reversal:
- **Bearish CHoCH:** Price breaks below a prior swing low during an uptrend (first sign the uptrend may end).
- **Bullish CHoCH:** Price breaks above a prior swing high during a downtrend (first sign the downtrend may end).
- A CHoCH is the first sign of potential reversal; a subsequent BOS in the new direction is confirmation.

**Codifiable Detection Rules:**
1. Identify swing highs/lows using a lookback window (e.g., a bar is a swing high if its high is the highest among N bars on each side).
2. Track the sequence: if each new swing high > previous swing high AND each new swing low > previous swing low, market is in uptrend.
3. BOS = price close beyond the most recent swing point in trend direction.
4. CHoCH = price close beyond the most recent swing point AGAINST trend direction.
5. Use `barstate.isconfirmed` (closed bars only) to avoid false signals from wicks.

**Python Library:** `smartmoneyconcepts` package provides `smc.bos_choch(ohlc, swing_highs_lows, close_break=True)` returning BOS/CHoCH signals with direction (+1/-1), level, and broken index.

---

### 1.2 Supply and Demand Zones vs Traditional S/R

**Traditional Support/Resistance (S/R):**
- Drawn as horizontal lines connecting repeated highs-to-highs or lows-to-lows.
- Strengthens with repeated testing (more touches = stronger level).
- Based on visible price reaction points.

**Supply and Demand (S/D) Zones:**
- Drawn as rectangular zones (not single lines) between the base candle and the first momentum candle.
- Weaken with each test (unfilled institutional orders get consumed).
- Based on where institutional order flow created explosive moves.
- A **supply zone** forms at the origin of a strong downward move (sellers entered aggressively).
- A **demand zone** forms at the origin of a strong upward move (buyers entered aggressively).

**Zone Formation Patterns:**
- **Rally-Base-Rally (RBR):** Continuation demand zone. Price rallies, consolidates briefly (1-2 candles), then rallies again. The base is the demand zone.
- **Drop-Base-Drop (DBD):** Continuation supply zone. Price drops, consolidates briefly, then drops again. The base is the supply zone.
- **Rally-Base-Drop (RBD):** Reversal supply zone. Price rallies, pauses, then drops sharply. The pause area is supply.
- **Drop-Base-Rally (DBR):** Reversal demand zone. Price drops, pauses, then rallies sharply. The pause area is demand.

**Key Differences from S/R:**
| Feature | S/R | S/D Zones |
|---|---|---|
| Representation | Lines | Rectangles (zones) |
| Strength over time | Stronger with more touches | Weaker with each touch (orders consumed) |
| Origin | Repeated reaction points | Institutional order placement areas |
| Fresh vs tested | No concept of "freshness" | Fresh (untested) zones are strongest |

**Sam Seiden's Contribution (Origin: Chicago Mercantile Exchange floor):**
Seiden observed institutional traders placing large pending orders at specific price levels. His key insight: unfilled institutional orders remain at price levels and act as supply/demand zones when price revisits. The departure speed (how fast price left the zone) indicates zone strength. Zones with explosive departures contain more unfilled orders.

**Codifiable Detection Rules:**
1. Identify consolidation areas (narrow-range candles, typically 1-3 bars) followed by explosive moves (large-body candles with significant displacement).
2. The zone boundaries = high/low of the consolidation candles (the "base").
3. Zone quality scoring: departure strength (ATR multiple of the move away), number of base candles (fewer = stronger), zone freshness (untested = highest quality), time in force.
4. Zone degradation: reduce quality score with each revisit.

---

### 1.3 Order Blocks and Fair Value Gaps (ICT Concepts)

**Order Blocks (OB):**
An order block is the last opposing candle before a strong directional move, marking where institutional traders placed significant orders.
- **Bullish OB:** The last bearish (red) candle before a strong upward move. Institutions were accumulating buy orders in this area.
- **Bearish OB:** The last bullish (green) candle before a strong downward move. Institutions were distributing sell orders in this area.
- When price returns to an OB, it often reacts (bounces for bullish OB, rejects for bearish OB).
- **Mitigation:** An OB is "mitigated" when price fully trades through it, invalidating the zone.

**Codifiable OB Detection:**
```
Bullish OB:
1. Find a swing low followed by a strong upward BOS.
2. The OB = the last bearish candle before the move up.
3. OB top = high of that candle; OB bottom = low of that candle.
4. Valid until price closes below the OB bottom (mitigated).

Bearish OB:
1. Find a swing high followed by a strong downward BOS.
2. The OB = the last bullish candle before the move down.
3. OB top = high of that candle; OB bottom = low of that candle.
4. Valid until price closes above the OB top (mitigated).
```

**Python Library:** `smc.ob(ohlc, swing_highs_lows, close_mitigation=False)` returns OB direction, top/bottom levels, volume, and a percentage strength metric calculated as `min(highVolume, lowVolume) / max(highVolume, lowVolume)`.

**Fair Value Gaps (FVG):**
An FVG is a three-candle pattern where the middle candle's move is so aggressive that a gap exists between the wicks of candles 1 and 3:
- **Bullish FVG:** Candle 1's high < Candle 3's low. The gap between them is the FVG.
- **Bearish FVG:** Candle 1's low > Candle 3's high. The gap between them is the FVG.
- FVGs represent price imbalance -- the market moved so fast that not all orders were filled.
- Price tends to "fill" (retrace into) FVGs before continuing the trend.

**Codifiable FVG Detection:**
```
Bullish FVG (at index i, referencing candles i-2, i-1, i):
  if candle[i-2].high < candle[i].low:
    FVG_top = candle[i].low
    FVG_bottom = candle[i-2].high
    FVG exists as the gap between these levels

Bearish FVG:
  if candle[i-2].low > candle[i].high:
    FVG_top = candle[i-2].low
    FVG_bottom = candle[i].high
```

**Python Library:** `smc.fvg(ohlc, join_consecutive=False)` returns FVG direction, top/bottom boundaries, and mitigation index.

**Backtest Evidence for FVGs:**
- One study found 60.71% of bullish FVGs and 63.2% of bearish FVGs remain unfilled, contradicting the common assumption that "all gaps fill."
- Qi's FVG analysis on Euro Stoxx 600: long-only FVG signals profitable 66.3% of the time with average return per trade of 1.5%, but losing trades averaged -7.4% (large asymmetric losses).
- FVGs combined with confluence (OB + S/D zone + trend direction) reportedly achieve 70%+ win rates.

---

### 1.4 Liquidity Concepts (Sweeps, Stop Hunts)

**Core Principle:** Liquidity is where resting orders cluster. Markets move toward liquidity to fill institutional orders.

**Buy-Side Liquidity (BSL):**
- Resting above price: stop-losses from short positions, breakout buy orders.
- Commonly found above equal highs, prior swing highs, session highs, round numbers.
- When institutions need to sell large positions, they drive price up into BSL to match their sell orders against the triggered buy stops.

**Sell-Side Liquidity (SSL):**
- Resting below price: stop-losses from long positions, breakout sell orders.
- Commonly found below equal lows, prior swing lows, session lows, round numbers.
- When institutions need to buy large positions, they drive price down into SSL to match buy orders against triggered sell stops.

**Liquidity Sweep:**
A sweep occurs when price temporarily spikes beyond a liquidity level, triggers the resting orders, then quickly reverses. It is the mechanical event of stops being triggered.

**Equal Highs/Lows:**
Multiple swing highs (or lows) at approximately the same price level create a "magnet" for price. Retail traders place stops just beyond these levels, creating predictable liquidity pools. Institutions target these levels.

**Codifiable Detection:**
```
Equal Highs Detection:
1. Collect all swing highs within a lookback period.
2. If two or more swing highs are within a small range (e.g., 0.1% of price), flag as equal highs.
3. The level just above the highest = BSL target.

Liquidity Sweep Detection:
1. Price exceeds a known liquidity level (equal highs/lows, session extremes).
2. Price then closes back below that level within 1-3 candles.
3. Flag as a liquidity sweep event.
```

**Python Library:** `smc.liquidity(ohlc, swing_highs_lows, range_percent=0.01)` identifies liquidity zones where multiple highs/lows cluster within `range_percent` of each other. Returns liquidity direction, level, end index, and swept index.

---

### 1.5 Institutional Order Flow Concepts

**Core Thesis:** Large institutions (banks, hedge funds, market makers) cannot execute massive orders at once without moving the market against themselves. They use specific strategies:

1. **Accumulation:** Quietly building a position during a range. Absorbing supply without pushing price up.
2. **Manipulation:** Engineered moves (stop hunts, false breakouts) to trigger retail orders and generate liquidity for institutional fills.
3. **Distribution:** Offloading positions into retail demand created by the markup phase.

**The "AMD" Model (Accumulation-Manipulation-Distribution):**
- Phase 1: Accumulation in a range (often during Asian session for forex).
- Phase 2: Manipulation -- a false move (often during London open) that sweeps liquidity.
- Phase 3: Distribution -- the real move in the intended direction (often continuing through NY session).

**Displacement:**
A strong, impulsive candle (or series of candles) that shows clear institutional intent. Characterized by:
- Large body relative to recent ATR.
- Closes near its extreme (near high for bullish, near low for bearish).
- Often leaves FVGs in its wake.

---

## 2. Popular Price Action Strategies

### 2.1 Al Brooks Price Action Methodology

**Core Philosophy:** Read price charts bar by bar to identify what institutions are doing, then piggyback their trades.

**Three Market States:**
1. **Trends:** Series of HH/HL (bull) or LH/LL (bear). Trade with the trend using pullback entries.
2. **Trading Ranges:** No clear HH/HL or LH/LL sequence. Fade moves at range extremes.
3. **Transitions:** Reversals from trend to range, range to trend, or trend to opposite trend.

**Key Concepts:**

- **Always In Direction:** If forced to hold a position 24/7, which direction would you be? Above a rising 20 EMA = always in long. Below a falling 20 EMA = always in short. Only take trades in the "always in" direction.
- **Signal Bars:** A bar that triggers an entry on the next bar. For longs: a bull bar (close > open) at a pullback low. For shorts: a bear bar (close < open) at a pullback high.
- **Entry Bars:** The bar that fills the entry order. A good entry bar closes in the entry direction (for a buy, it closes above the signal bar high).
- **Follow-Through:** A breakout bar means nothing without confirmation. The bar after a breakout must continue in the breakout direction.
- **Measured Moves:** Price often moves approximately the same distance as the prior swing. Calculate: target = breakout point + (prior swing high - prior swing low).
- **Two-Legged Pullbacks:** Most pullbacks in a trend have two legs (an ABC correction). The end of leg 2 is the high-probability entry point.
- **Breakout Pullback:** After a breakout of a range, price often pulls back to the breakout point. This is the "breakout pullback" entry -- a lower-risk entry than the breakout itself.
- **Failed Breakouts:** When a breakout fails (reverses back into range), it often leads to a sharp move to the opposite side. Trade the failure, not the breakout.

**Codifiable Rules:**
- Trend identification: use 20 EMA slope + HH/HL or LH/LL sequence.
- Signal bar: bar with close in trend direction, occurring at a pullback in the trend.
- Entry: buy stop 1 tick above signal bar high (for long), or sell stop 1 tick below signal bar low (for short).
- Stop: Beyond the signal bar extreme (opposite side of entry).
- Target: Measured move or prior swing extreme.

---

### 2.2 ICT (Inner Circle Trader) -- Smart Money Concepts

**Creator:** Michael Huddleston (ICT). Built on the premise that institutions (smart money) engineer price movements to capture retail liquidity.

**Core Framework (The ICT 2022 Model):**
1. **Identify the higher-timeframe draw on liquidity (DOL):** Where is price likely heading? Previous day high/low, weekly high/low, or significant equal highs/lows.
2. **Wait for a liquidity sweep:** Price sweeps a known liquidity level (e.g., previous session low).
3. **Look for displacement:** After the sweep, a strong impulsive candle confirms institutional involvement.
4. **Identify the order block / FVG:** Mark the last opposing candle before displacement, or the gap left by the impulsive move.
5. **Enter on retracement to OB or FVG:** Wait for price to retrace into the OB or FVG zone.
6. **Target the opposite liquidity pool:** Take profit at the DOL on the other side of the range.

**Key ICT Concepts:**

- **Optimal Trade Entry (OTE):** The 62-79% Fibonacci retracement zone of an impulse move. ICT's preferred entry zone when combined with an OB or FVG.
- **Kill Zones:** Specific times when institutional activity is highest:
  - London Open: 02:00-05:00 EST
  - New York Open: 07:00-10:00 EST
  - London Close: 10:00-12:00 EST
- **Power of Three (PO3):** Every candle has three phases: accumulation (open), manipulation (false move), distribution (real move/close). Applies at all timeframes.
- **Breaker Block:** A failed order block. When an OB is broken through (mitigated), it becomes a breaker block on the other side. A broken bullish OB becomes a bearish breaker (resistance).
- **Mitigation Block:** Similar to breaker -- a former S/D zone that has been traded through and now acts as opposition.

**Codifiable Elements:**
- FVG detection: purely algorithmic (3-candle gap pattern).
- OB detection: algorithmic (last opposing candle before BOS).
- Liquidity levels: algorithmic (equal highs/lows, session extremes).
- Displacement: candle body > 1.5-2x ATR.
- Kill zone filtering: time-based filter (trivially codifiable).
- OTE zone: Fibonacci 0.62-0.79 of impulse (standard Fibonacci calculation).

**Available Python Implementation:** `smartmoneyconcepts` PyPI package implements FVG, OB, BOS/CHoCH, liquidity, swing points, sessions, and retracements.

---

### 2.3 Sam Seiden Supply and Demand

**Origin:** Developed from observing institutional order flow on the Chicago Mercantile Exchange floor.

**Core Rules:**
1. **Identify zones:** Look for explosive departures from narrow consolidation areas. The consolidation = the zone.
2. **Zone strength criteria:**
   - **Strength of departure:** The more explosive the move away from the zone, the more unfilled orders remain. Measure in ATR multiples.
   - **Time at level:** The less time price spent in the zone (fewer base candles), the stronger the zone. Ideally 1-3 candles.
   - **Freshness:** An untested zone (price has not returned to it) is strongest. Each revisit degrades the zone.
   - **Big picture context:** The zone should align with the HTF trend.
3. **Entry:** Place a limit order at the zone boundary (demand zone high for longs, supply zone low for shorts).
4. **Stop loss:** Beyond the opposite edge of the zone + buffer.
5. **Take profit:** At the nearest opposing zone, or at a measured distance of at least 3:1 R:R.

**Codifiable Rules:**
```
Zone Detection:
1. Scan for N consecutive bars with ATR < threshold (the "base").
2. The bar after the base must have body > X * ATR (the "departure").
3. Zone boundaries = high/low of the base candles.
4. Zone type: if departure is upward = demand zone; if downward = supply zone.

Zone Scoring:
- departure_strength = abs(departure_close - zone_midpoint) / ATR
- base_candle_count (fewer = better)
- freshness = 0 revisits > 1 revisit > 2+ revisits
- htf_alignment = +1 if zone direction matches HTF trend, 0 if range, -1 if against
```

---

### 2.4 Nial Fuller's "Naked" Price Action

**Philosophy:** Trade with "naked" charts (no indicators). Focus on daily and weekly timeframes only. Simplicity over complexity.

**Three Core Setups:**

1. **Pin Bar (Pinocchio Bar):**
   - A candle with a long tail/wick (at least 2/3 of total candle range) and a small body (1/3 or less).
   - Bullish pin bar: long lower wick, small body near the top, at a support/demand zone.
   - Bearish pin bar: long upper wick, small body near the bottom, at a resistance/supply zone.
   - **Codifiable rule:** `tail_length / total_range >= 0.67` AND `body_size / total_range <= 0.33`.

2. **Inside Bar:**
   - A bar whose high and low are completely contained within the prior bar's high and low.
   - Represents consolidation/indecision. Traded as a breakout setup.
   - **Codifiable rule:** `current_high < previous_high AND current_low > previous_low`.
   - Entry: buy stop above inside bar high or sell stop below inside bar low.

3. **Fakey (False Break of Inside Bar):**
   - An inside bar pattern where the breakout fails and reverses.
   - Step 1: Inside bar forms.
   - Step 2: Price breaks beyond the inside bar range (either direction).
   - Step 3: Price quickly reverses and closes back inside the mother bar range.
   - This is a failed breakout and signals a move in the opposite direction.
   - **Codifiable rule:** Inside bar detected, then breakout bar exceeds range, then reversal bar closes back within mother bar range.

**Trade Management:**
- Entry: On close of signal bar, or on break of signal bar extreme.
- Stop loss: Beyond the opposite side of the signal bar (for pin bar: beyond the tail tip).
- Take profit: 2:1 or 3:1 risk-reward minimum. Or at nearest key S/R level.
- Timeframe: Daily charts preferred. Weekly for swing trades.

---

### 2.5 Steve Nison Candlestick Patterns

Steve Nison introduced Japanese candlestick charting to the Western world. His patterns are the foundation of candlestick-based price action analysis.

**Key Reversal Patterns (Codifiable):**

| Pattern | Structure | Signal | Codifiable Rule |
|---|---|---|---|
| **Hammer** | Small body at top, long lower shadow (2x+ body), little/no upper shadow | Bullish reversal at support | `lower_shadow >= 2 * body AND upper_shadow <= body * 0.1` at swing low |
| **Shooting Star** | Small body at bottom, long upper shadow (2x+ body), little/no lower shadow | Bearish reversal at resistance | `upper_shadow >= 2 * body AND lower_shadow <= body * 0.1` at swing high |
| **Bullish Engulfing** | Bear candle followed by bull candle whose body fully engulfs prior body | Bullish reversal | `prev_close < prev_open AND curr_close > prev_open AND curr_open < prev_close` |
| **Bearish Engulfing** | Bull candle followed by bear candle whose body fully engulfs prior body | Bearish reversal | `prev_close > prev_open AND curr_close < prev_open AND curr_open > prev_close` |
| **Morning Star** | Bear candle, small-body candle (doji/spinning top), bull candle | Bullish reversal | Three-candle sequence: large bear, small body, large bull. Bull close > midpoint of first bear candle. |
| **Evening Star** | Bull candle, small-body candle, bear candle | Bearish reversal | Three-candle sequence: large bull, small body, large bear. Bear close < midpoint of first bull candle. |
| **Doji** | Open and close nearly equal (< 10% of range) | Indecision/potential reversal | `abs(open - close) / (high - low) < 0.1` |
| **Dark Cloud Cover** | Bull candle, then bear candle that opens above prior high and closes below prior midpoint | Bearish reversal | `curr_open > prev_high AND curr_close < (prev_open + prev_close) / 2 AND curr_close > prev_open` |
| **Piercing Line** | Bear candle, then bull candle that opens below prior low and closes above prior midpoint | Bullish reversal | `curr_open < prev_low AND curr_close > (prev_open + prev_close) / 2 AND curr_close < prev_open` |
| **Three White Soldiers** | Three consecutive bull candles, each opening within prior body and closing near high | Strong bullish continuation | Three consecutive bull candles with progressively higher closes, each opening within prior candle's body. |
| **Three Black Crows** | Three consecutive bear candles, each opening within prior body and closing near low | Strong bearish continuation | Three consecutive bear candles with progressively lower closes, each opening within prior candle's body. |

**Continuation Patterns:**
- Rising/Falling Three Methods: Trend candle, 2-3 small counter-trend candles (staying within first candle range), then another trend candle.
- Tasuki Gap: Gap in trend direction, small counter-trend candle that doesn't fill gap, then trend continuation.

---

### 2.6 VSA (Volume Spread Analysis) by Tom Williams

**Foundation:** Based on Richard Wyckoff's work. Analyzes the relationship between three variables: volume, spread (bar range), and close position within the bar.

**Core Principle:** Smart money (institutions) leaves footprints in volume data. Their activity creates specific volume-spread-close combinations that signal accumulation or distribution.

**Key VSA Signals (All Codifiable):**

| Signal | Volume | Spread | Close Position | Meaning |
|---|---|---|---|---|
| **No Demand** | Lower than previous 2 bars | Narrow | Mid or low of bar, bar closes up | No institutional buying. Expect down move. |
| **No Supply** | Lower than previous 2 bars | Narrow | Mid or high of bar, bar closes down | No institutional selling. Expect up move. |
| **Stopping Volume** | Very high | Narrow | Near middle | Strong buying absorbing selling pressure. Potential reversal up. |
| **Climactic Action (Selling Climax)** | Extremely high | Very wide | Near the low | Panic selling being absorbed by institutions. Bottom forming. |
| **Climactic Action (Buying Climax)** | Extremely high | Very wide | Near the high | Euphoric buying being sold into by institutions. Top forming. |
| **Upthrust** | High | Wide | Near the low (closes down after going up) | False breakout above resistance. Bearish trap. |
| **Spring (Test)** | Low | Can vary | Bar dips below support then closes above | Test of supply below. If volume is low, supply exhausted. Bullish. |
| **Effort vs Result (No Result on Effort)** | High | Narrow | Near middle | Despite effort (volume), no result (narrow spread). Opposing force absorbing. |
| **Effort vs Result (Result on No Effort)** | Low | Wide | Near extreme | Large move on little volume. Vacuum/lack of opposition. |

**Codifiable Rules:**
```python
# No Demand
def no_demand(volume, spread, close_pos, prev_volumes, bar_direction):
    return (bar_direction == "up" and
            volume < min(prev_volumes[-2:]) and
            spread < avg_spread * 0.75 and
            close_pos < 0.5)  # close_pos: 0=low, 1=high

# No Supply
def no_supply(volume, spread, close_pos, prev_volumes, bar_direction):
    return (bar_direction == "down" and
            volume < min(prev_volumes[-2:]) and
            spread < avg_spread * 0.75 and
            close_pos > 0.5)

# Stopping Volume
def stopping_volume(volume, spread, close_pos, avg_volume, avg_spread):
    return (volume > avg_volume * 2.0 and
            spread < avg_spread * 0.75 and
            0.3 < close_pos < 0.7)

# Upthrust
def upthrust(volume, spread, close_pos, prev_high, current_high, avg_volume):
    return (current_high > prev_high and  # broke above prior high
            close_pos < 0.3 and           # closed near low
            volume > avg_volume * 1.5 and
            spread > avg_spread * 1.0)
```

**Effort vs Result Principle (Quantifiable):**
Compare volume (effort) to the resulting price change (result). When they diverge (high effort, little result OR low effort, big result), it signals institutional activity opposing the visible move.

---

### 2.7 Wyckoff Method (Accumulation/Distribution Phases)

**Creator:** Richard Wyckoff (1920s). Foundation for VSA and many modern price action methodologies.

**The Composite Man:** Wyckoff's abstraction of all institutional participants acting as a single entity that plans, executes, and concludes market campaigns.

**Four-Phase Market Cycle:**
1. **Accumulation:** Institutions buy quietly in a range (preparing for markup).
2. **Markup:** Uptrend. Demand exceeds supply. Public joins in.
3. **Distribution:** Institutions sell quietly into public buying in a range.
4. **Markdown:** Downtrend. Supply exceeds demand. Public panics.

**Accumulation Schematic (5 Phases A-E):**

| Phase | Events | Characteristics | Codifiable Signals |
|---|---|---|---|
| **A** | PS (Preliminary Support), SC (Selling Climax), AR (Automatic Rally), ST (Secondary Test) | Downtrend stops. High-volume capitulation. Bounce. Retest of low on lower volume. | SC: Extremely high volume + wide spread + close near low. ST: Retest of SC low on declining volume. |
| **B** | Multiple STs, UTs (Upthrusts within range) | Building cause. Range-bound. Volume tests supply/demand. | Price oscillates between SC low and AR high. Volume decreases over time. |
| **C** | Spring or Shakeout | Price drops below range support, quickly reverses back. Final trap of weak holders. | Price breaks below range low, then closes back above within 1-3 bars. Volume on spring should be low (supply exhausted). |
| **D** | SOS (Sign of Strength), LPS (Last Point of Support) | Price breaks above range resistance on high volume. Pullbacks are shallow and on low volume. | SOS: Break above AR high on volume > average. LPS: Pullback that holds above prior resistance (now support) on declining volume. |
| **E** | Markup begins | Higher highs and higher lows. Increasing volume on advances. | Trend confirmation: HH/HL sequence with volume expanding on up-moves. |

**Distribution Schematic (Mirror of Accumulation):**
- PSY (Preliminary Supply) -> BC (Buying Climax) -> AR (Automatic Reaction) -> ST -> UTAD (Upthrust After Distribution) -> SOW (Sign of Weakness) -> LPSY (Last Point of Supply) -> Markdown.

**Key Patterns:**
- **Spring:** Sudden dip below range support that quickly reverses. Tests whether selling pressure remains. Low volume = supply exhausted = bullish.
- **Upthrust (UT):** Sharp spike above range resistance that quickly reverses. Tests whether buying pressure remains. Can occur in accumulation (Phase B test) or distribution (UTAD).
- **Sign of Strength (SOS):** Impulsive move up on expanding volume that breaks out of the range.
- **Last Point of Support (LPS):** Higher-low pullback after SOS on contracting volume. The final entry point before markup.

**Codifiable Detection (Simplified):**
```
1. Range Detection: Identify extended periods (20+ bars) where price oscillates
   between a defined high and low with contracting volatility.
2. Climax Detection: Within the range, find bars with volume > 3x average
   AND wide spread AND close near the extreme.
3. Spring Detection: Price breaks below range low, then closes back above
   range low within 1-3 bars. Volume on the spring bar < average.
4. SOS Detection: Breakout above range high with volume > 1.5x average.
5. LPS Detection: After SOS, pullback that holds above range high (now support)
   with volume < average.
```

---

### 2.8 RTM (Read The Market) / IF (Institutional Forex)

**Creator:** IF Myante (Institutional Forex community). An advanced price action methodology that reads raw price behavior based on market structure, liquidity, and order flow.

**Core Principles:**
- No indicators, only raw price.
- Focus on where institutional traders enter/exit.
- Identify zones where orders rest and where they have been consumed.

**Key RTM Patterns:**

**Flag Limit (FL):**
The most highly regarded RTM pattern. A "decision zone" where price pauses briefly (1-2 candles) during a strong move, creating the base of an RBR or DBD pattern. This is where institutions added to positions. When price returns to this zone, it often reacts.
- **Entry:** Limit order at the flag limit zone.
- **Codifiable:** Identify 1-2 bar consolidation between two strong directional moves in the same direction.

**FTR (Failure to Return):**
Price breaks a significant S/R level, retraces toward it, but fails to reach the broken level. The point where the retracement ends = the FTR zone. This indicates strong demand/supply preventing price from reaching the old level.
- **Codifiable:** After a BOS, measure the retracement. If price reverses before reaching the broken level (leaving a gap), mark the reversal point as the FTR zone.

**Compression (CP):**
A series of small counter-trend candles approaching a zone. It indicates that the opposing force is getting weaker as it approaches the zone, which paradoxically weakens the zone. Zigzag compression (price making smaller and smaller swings) approaching a zone signals the zone may fail.
- **Codifiable:** Detect decreasing swing amplitudes approaching a known zone.

**Quasimodo Pattern (QM) / Over & Under:**
An advanced reversal pattern combining structural break with false breakout:
1. In an uptrend: Price makes HH, then HL, then fails to make a new HH (creates a LH).
2. Price then breaks below the HL (BOS), but the key is the "shoulder" level (the HL before the LH).
3. Entry at the level of the left shoulder (the demand that created the last HL).
- Resembles head-and-shoulders but uses structural analysis rather than visual pattern matching.
- **Codifiable:** Detect the sequence HH -> HL -> LH -> LL (for bearish QM) or LL -> LH -> HL -> HH (for bullish QM). Entry zone = the "shoulder" (second pivot from the extreme).

---

## 3. Key Books

### Essential Reading List

| Book | Author | Focus | Key Teachings |
|---|---|---|---|
| **Trading Price Action Trends** | Al Brooks | Trend identification & trading | Bar-by-bar analysis. HH/HL, LH/LL identification. "Always in" direction. Signal bars and entry bars. Follow-through assessment. 20 EMA as trend gauge. |
| **Trading Price Action Trading Ranges** | Al Brooks | Range-bound markets | Range identification. Breakout assessment. Failed breakout trading. Range boundary fading. Transition detection (range -> trend). |
| **Trading Price Action Reversals** | Al Brooks | Reversals & transitions | Climax patterns. Exhaustion signals. Major trend reversal detection. Two-legged corrections. Measured move failures. |
| **Japanese Candlestick Charting Techniques** (2nd ed.) | Steve Nison | Candlestick pattern recognition | All major single, double, and triple candlestick patterns. Pattern confirmation rules. Combining candlesticks with Western TA. First book to bring candlesticks to the West. |
| **Technical Analysis of the Financial Markets** | John Murphy | Comprehensive TA reference | Complete coverage: trends, S/R, chart patterns, volume, moving averages, oscillators, intermarket analysis. The "bible" of technical analysis. |
| **Trading in the Zone** | Mark Douglas | Trading psychology | Five trading truths. Probability-based thinking. Emotional discipline. Why trading success is 80% psychology, 20% strategy. Treating each trade as an independent event. Eliminating fear and overconfidence. |
| **Forex Price Action Scalping** | Bob Volman | 5-minute scalping | Pure price action on 5-minute charts. Tipping point entries. Buildup patterns. 70-tick charts. Extremely practical with real chart examples. |
| **Understanding Price Action** | Bob Volman | 5-minute practical analysis | Continuation of his scalping methodology with deeper practical analysis. Step-by-step examples from real markets. |
| **Price Action Breakdown** | Laurentiu Damir | Simplified price action | Distilled, beginner-friendly approach to price action. Focus on key levels, momentum, and simple entry rules. Translated into 6+ languages. |
| **Naked Forex** | Alex Nekritin & Walter Peters | Indicator-free forex trading | High-probability setups without indicators. Kangaroo tails (pin bars). Big shadow (engulfing). Inside bars. Last-kiss trades (breakout pullbacks). Zone-based trading. |
| **Master the Markets** | Tom Williams | VSA methodology | Complete VSA framework. Reading volume-spread relationships. Smart money detection. No demand/no supply signals. Stopping volume. Climactic actions. |
| **Trades About to Happen** | David Weis | Modern Wyckoff | Updated Wyckoff methodology for modern markets. Effort vs result analysis. Wave analysis with volume. Practical Wyckoff application. |
| **Studies in Tape Reading** | Richard Wyckoff | Original Wyckoff method | The original source material for understanding institutional order flow through price and volume analysis. Historical but foundational. |
| **Martin Pring on Price Patterns** | Martin Pring | Chart pattern analysis | Head and shoulders, triangles, flags, double tops/bottoms. Volume confirmation rules. Breakout analysis. Support and resistance identification. |
| **The Art and Science of Technical Analysis** | Adam Grimes | Evidence-based TA | Quantitative approach to technical analysis. Statistical testing of patterns. One of the few books that combines TA practice with statistical rigor. |

---

## 4. Multi-Timeframe Analysis Best Practices

### 4.1 The Top-Down Approach

The professional methodology is hierarchical: start with the highest relevant timeframe for overall bias, then drill down for precision entry.

**Three-Tier Framework:**
1. **HTF (Higher Timeframe) -- Directional Bias:** Determines the overall trend direction. You only take trades in this direction.
2. **MTF (Middle Timeframe) -- Structure/Zone:** Identifies the specific zones (S/D, OB, FVG, S/R) where trades should be executed.
3. **LTF (Lower Timeframe) -- Entry Trigger:** Provides the precise entry signal (candlestick pattern, BOS, CHoCH) within the zone identified on the MTF.

**Alignment Rule:** When all three timeframes point in the same direction, you have a high-quality opportunity. If any timeframe conflicts, reduce position size or skip the trade.

### 4.2 Common Timeframe Combinations

| Trading Style | HTF (Bias) | MTF (Structure) | LTF (Entry) |
|---|---|---|---|
| Position Trading | Monthly | Weekly | Daily |
| Swing Trading | Weekly | Daily | 4H |
| Intraday Swing | Daily | 4H | 1H or 30M |
| Day Trading | 4H or Daily | 1H | 15M or 5M |
| Scalping | 1H | 15M | 5M or 1M |

### 4.3 The Rule of 4-6

Each subsequent timeframe should be approximately 4 to 6 times the one below it. This provides enough separation for distinct structural information while maintaining analytical coherence.

Examples: Monthly(1)/Weekly(4x) | Weekly(1)/Daily(5x) | Daily(1)/4H(6x) | 4H(1)/1H(4x) | 1H(1)/15M(4x)

### 4.4 Practical Application

**Step-by-Step Process:**

1. **HTF Analysis:**
   - Identify the trend (HH/HL or LH/LL).
   - Mark major S/D zones, order blocks, or key S/R levels.
   - Determine directional bias (long or short only).

2. **MTF Analysis:**
   - Within the HTF bias, identify the specific zone price is approaching.
   - Check if the zone is fresh, if there is confluence (FVG + OB + S/D overlap).
   - Confirm the MTF structure supports the HTF bias (e.g., MTF is also making HH/HL in an HTF uptrend).

3. **LTF Analysis:**
   - Wait for price to reach the MTF zone.
   - Look for a LTF CHoCH (change of character) confirming a micro-reversal into the HTF bias direction.
   - Enter on the LTF signal (pin bar, engulfing, BOS, displacement).
   - Place stop loss beyond the zone or beyond the LTF swing point.
   - Target the next HTF/MTF zone on the opposite side.

**ICT-Specific MTF Approach:**
- HTF: Identify the "draw on liquidity" -- where is price likely heading? (Previous day/week high or low, equal highs/lows)
- MTF: Wait for a session (London/NY) where price sweeps one side of liquidity.
- LTF: After the sweep, look for displacement + FVG/OB. Enter on retracement to FVG/OB. Target the opposite liquidity pool.

---

## 5. What Makes a High-Probability Price Action Setup?

### 5.1 Confluence Factors (Ranked by Importance)

Professional traders look for multiple independent factors aligning at the same price level. The "sweet spot" is 3-4 confluence factors.

| Rank | Factor | Description | Weight |
|---|---|---|---|
| 1 | **HTF Trend Alignment** | Trading in the direction of the higher-timeframe trend | Critical (filter, not just weight) |
| 2 | **Key Level / Zone** | Price is at a significant S/D zone, OB, or institutional level | High |
| 3 | **Liquidity Sweep** | Price has just swept a liquidity pool (stop hunt) and reversed | High |
| 4 | **Displacement / Momentum** | Strong impulsive candle confirming institutional intent | High |
| 5 | **FVG or Imbalance** | Price is filling a fair value gap, offering entry with defined risk | Medium-High |
| 6 | **Candlestick Confirmation** | Pin bar, engulfing, or other reversal pattern at the zone | Medium |
| 7 | **Volume Confirmation** | VSA signals (no demand/supply, stopping volume) supporting the trade | Medium |
| 8 | **Time/Session** | Trade occurs during a kill zone (London/NY open) | Medium |
| 9 | **Fibonacci Confluence** | Price is at a key Fibonacci level (0.618, 0.786) overlapping with a zone | Low-Medium |
| 10 | **Round Number** | Price is at a psychological round number (e.g., 1.2000, 50.00) | Low |

### 5.2 How to Weight Signals

**Scoring Model (Example):**
```
Score = (HTF_alignment * 3) + (key_level * 2) + (liquidity_sweep * 2) +
        (displacement * 2) + (fvg * 1.5) + (candle_pattern * 1) +
        (volume_confirm * 1) + (session * 1) + (fib * 0.5) + (round_number * 0.5)

Threshold for trade entry: Score >= 7
```

Each factor is binary (present=1, absent=0) multiplied by its weight. A total score above a threshold triggers the trade. This is highly codifiable for backtesting.

### 5.3 Common Mistakes / False Signals to Avoid

1. **Trading against HTF trend:** The single most common mistake. Counter-trend setups have much lower success rates.
2. **Over-reliance on single patterns:** Candlestick patterns alone have poor reliability (many near 50% win rate in isolation). Always require confluence.
3. **Ignoring volume:** A breakout on low or declining volume is likely a fakeout. Weak volume lowers conviction and increases failure rates.
4. **Trading tested zones:** Supply/demand zones weaken with each touch. Fresh zones outperform retested zones.
5. **Premature entry:** Entering before confirmation (e.g., entering on the breakout candle instead of waiting for follow-through or a pullback entry).
6. **Over-complicating analysis:** Using too many indicators or looking for too many patterns leads to analysis paralysis and contradictory signals.
7. **Wrong timeframe:** Lower timeframes produce more noise and higher failure rates. Patterns on daily/weekly charts are more reliable than on 5M/15M charts.
8. **Ignoring market context:** A beautiful pin bar in the middle of a choppy range is meaningless. Context (trend, level, session) matters more than the pattern itself.
9. **Chasing breakouts:** Most breakouts fail. The breakout pullback (retest) is statistically a higher-probability entry than the initial breakout.
10. **Not accounting for spread and slippage:** In backtests, unrealistic fills at exact levels inflate performance.

### 5.4 Entry, Stop Loss, and Take Profit Placement

**Entry Methods (Ordered by Aggressiveness):**
1. **Limit order at zone edge:** Most aggressive. Enter as soon as price touches a zone. Higher R:R but lower win rate.
2. **Candlestick confirmation at zone:** Wait for a reversal pattern (pin bar, engulfing) at the zone. Moderate R:R and win rate.
3. **LTF BOS/CHoCH within zone:** Wait for a lower-timeframe structural shift confirming reversal from the zone. Most conservative. Lower R:R but highest win rate.

**Stop Loss Placement:**
- **Structure-based:** Place SL beyond the most recent swing high/low that would invalidate the trade thesis. Most common method.
- **Zone-based:** Place SL beyond the opposite edge of the S/D zone, OB, or FVG being traded.
- **ATR-based:** Place SL at entry +/- (ATR * multiplier). Day traders: 1.5-2x ATR. Swing traders: 2-3x ATR. Position traders: 3-4x ATR.
- **Combined:** Use the structural level (e.g., beyond the swing low) and add an ATR buffer for breathing room. Formula: `SL = swing_low - (ATR * 0.5)`.

**Take Profit Placement:**
- **Opposing zone:** Target the next S/D zone, OB, or key S/R level on the other side.
- **Opposing liquidity:** Target the next pool of liquidity (equal highs/lows, session extremes).
- **Measured move:** Target = entry point + distance of the prior swing (same magnitude as the setup's impulse move).
- **Risk-reward multiple:** Minimum 2:1 R:R. Ideal: 3:1+. Walk the stop to breakeven after 1R profit.
- **Fibonacci extensions:** 1.0, 1.618, 2.0, 2.618 extensions of the prior swing as targets.

---

## 6. Quantitative/Testable Price Action Rules

### 6.1 Concepts That Can Be Codified into Rules

| Concept | Codifiability | Difficulty | Notes |
|---|---|---|---|
| Swing High/Low Detection | Fully codifiable | Easy | Lookback window comparison. Standard in all TA libraries. |
| BOS / CHoCH | Fully codifiable | Easy-Medium | Compare swing points to prior swing points. Available in `smartmoneyconcepts`. |
| Fair Value Gap | Fully codifiable | Easy | 3-candle gap pattern. Pure arithmetic. |
| Order Block | Fully codifiable | Medium | Last opposing candle before BOS. Requires swing/BOS detection first. |
| Candlestick Patterns | Fully codifiable | Easy | All patterns are mathematically defined (body %, shadow %, close position). |
| Support/Resistance Levels | Fully codifiable | Medium | Cluster swing points. Use kernel density estimation or simple grouping. |
| Supply/Demand Zones | Fully codifiable | Medium | Detect consolidation -> explosion patterns. Score by departure strength. |
| VSA Signals | Fully codifiable | Medium | Volume/spread/close-position rules. All mechanically defined. |
| Liquidity Levels (Equal H/L) | Fully codifiable | Easy | Group nearby swing highs/lows. |
| Liquidity Sweeps | Fully codifiable | Easy-Medium | Price exceeds level then closes back inside. |
| ATR-based Stops/Targets | Fully codifiable | Easy | Standard ATR calculation with multiplier. |
| Multi-Timeframe Alignment | Fully codifiable | Medium | Run same logic on multiple resampled timeframes. Compare signals. |
| Kill Zone (Time Filter) | Fully codifiable | Trivial | Simple time-of-day filter. |
| Wyckoff Phases | Partially codifiable | Hard | Range detection + volume profile analysis. Spring is codifiable. Full schematic detection is complex and somewhat subjective. |
| RTM Patterns (FL, FTR, QM) | Partially codifiable | Hard | Require nuanced structural analysis. QM is codifiable; compression is harder. |
| ICT OTE | Fully codifiable | Easy | Fibonacci 0.618-0.786 of impulse move. Standard math. |
| Displacement Detection | Fully codifiable | Easy | Candle body > N * ATR (typical N = 1.5-2.0). |

### 6.2 What Has Been Successfully Backtested

**Backtested with Positive Results:**

1. **Mean-reversion candlestick strategies on equities (daily):**
   - Three consecutive lower lows and lower highs: 80% win rate, 298 trades, 1.1% avg gain on Pepsi-Cola (1985-present). CAGR 8.8%, max drawdown 21%.
   - Bearish engulfing (buying weakness, mean-reversion): 274 trades, 0.57% avg gain, profit factor 2.7, max drawdown 16%.
   - Key insight: In equities, buying bearish patterns (mean reversion) outperforms buying bullish patterns, because "you get paid to take on risk."

2. **Candlestick pattern universe on S&P 500:**
   - 75 patterns backtested. 66% (50 of 75) outperformed S&P 500 buy-and-hold over their holding period (de-trended).
   - Best performers: Bullish Piercing Line (highest win rate), Three Outside Down (highest avg gain at 0.73% per trade).
   - Three White Soldiers + RSI filter: 83.33% win rate, 2.68 profit factor on ES futures.

3. **Support and resistance levels (academic):**
   - Federal Reserve working paper found S/R levels help predict intraday trend interruptions in FX.
   - S/R levels as features in ML models increased profitability by 65% across 8 currency pairs.
   - Research found S/R levels with more prior bounces have higher probability of bouncing again, which is statistically significant.

4. **Lo, Mamaysky & Wang (2000) -- Journal of Finance:**
   - Landmark academic study using nonparametric kernel regression to detect head-and-shoulders, double tops/bottoms, and other patterns across US stocks (1962-1996).
   - Found several technical indicators provide incremental predictive information, especially for smaller (less efficient) stocks.

5. **Pin bar system (daily, AUDJPY):**
   - 74% win rate over ~14 years. But only ~20 trades, and total return of ~20% was modest.
   - Small sample size limits statistical confidence.

**Backtested with Negative/Mixed Results:**

1. **Most individual candlestick patterns in isolation:**
   - Academic research (multiple studies across S&P 500, FTSE 100, Stock Exchange of Thailand) shows most candlestick reversal patterns do NOT generate statistically significant mean returns.
   - Even patterns with significant mean returns have very high standard deviations.
   - Binomial tests confirm most patterns cannot reliably predict direction.
   - On FTSE 100 (1-minute data): not a single pattern showed even a 1% gain net of spread.

2. **Chart pattern failure rates have increased over time:**
   - Head and shoulders, pennants: failure rates surged to ~50% in the 2000s (vs ~26% in the 1990s).
   - Rectangle bottom failure rate: 28% (up from 14% in 1990s).
   - Pennant success rate: below 70%.
   - Double bottom: 88% success in bull markets with volume confirmation (one of the few high-success patterns).

3. **FVG (Fair Value Gap) as standalone:**
   - 60-63% of FVGs remain unfilled, contradicting the "all gaps fill" assumption.
   - Qi study (Euro Stoxx 600): 66.3% of long FVG signals profitable, BUT losing trades averaged -7.4% (severe asymmetric risk).

### 6.3 Academic Research Summary

| Study | Year | Findings |
|---|---|---|
| **Lo, Mamaysky & Wang** | 2000 | Computational pattern recognition found incremental information in technical patterns, especially for small-cap stocks. Published in *Journal of Finance*. |
| **Caginalp & Laurent** | 1998 | Some 3-day candlestick patterns had short-term predictive power on S&P 500 stocks. |
| **Bulkowski** | 2008 | Large-bodied candles with minimal wicks had higher continuation probability. Extensive pattern statistics in *Encyclopedia of Candlestick Charts*. |
| **Tharavanij et al.** | 2017 | Study on Stock Exchange of Thailand: most candlestick patterns do not generate significant returns. Patterns with significant returns have high risk. Published in *SAGE Open*. |
| **Federal Reserve** | Various | S/R levels in short-term FX have predictive power for intraday trend interruptions, though power varies by exchange rate and firm. |
| **Osler (2000, 2003)** | 2000-2003 | Federal Reserve researcher. Found that stop-loss and take-profit orders cluster at round numbers, and these clusters affect FX price dynamics. Supports liquidity sweep concepts. |
| **IJRPR (2024)** | 2024 | Systematic review: pattern-based trades incorporating volume and RSI confirmation demonstrate 62% average success rate across 8,000+ chart setups (2020-2023). |

### 6.4 Known Issues with Pattern Recognition

1. **Subjectivity:** Different traders draw different zones, identify different swings. Algorithmic detection removes this but introduces parameter sensitivity (e.g., swing lookback length).
2. **Data-snooping bias:** With dozens of patterns and parameter combinations, some will appear profitable by chance. Require out-of-sample testing.
3. **Survivorship bias:** Backtests on indices like S&P 500 benefit from index survivorship (failed companies are removed).
4. **Regime dependency:** Patterns that work in trending markets fail in ranging markets, and vice versa. Strategies need regime detection.
5. **Timeframe dependency:** Higher timeframes (daily, weekly) produce more reliable signals but fewer trades. Lower timeframes produce more noise.
6. **Mean reversion vs momentum conflict:** In equities, mean-reversion dominates on daily timeframes (buy weakness). In forex, momentum patterns may perform differently.
7. **Transaction costs:** Many patterns show marginal edge that disappears after accounting for spread, commission, and slippage.
8. **Pattern degradation over time:** As patterns become widely known and automated, their edge diminishes (market efficiency adapts). This explains rising failure rates for classic chart patterns.
9. **Confirmation bias in manual testing:** Traders remember successes and forget failures. Only rigorous backtesting reveals true performance.

### 6.5 Recommended Backtesting Framework

**Tools:**
- `backtesting.py` (Python): Lightweight, flexible backtesting framework for daily/intraday data.
- `smartmoneyconcepts` (Python): Detects FVG, OB, BOS/CHoCH, liquidity, swing points, sessions.
- `pandas-ta` or `ta-lib`: Standard technical indicators (ATR, EMA, RSI, Fibonacci).
- `yfinance`: Historical OHLCV data retrieval.

**Testing Protocol:**
1. Define rules with zero ambiguity (all conditions are mathematical/boolean).
2. Split data: in-sample (training, 60%), out-of-sample (validation, 20%), hold-out (final test, 20%).
3. Test across multiple instruments and market regimes (bull, bear, range).
4. Account for realistic transaction costs (spread + commission + slippage).
5. Measure: win rate, profit factor, max drawdown, Sharpe ratio, number of trades.
6. Apply detrending for equity indices to isolate strategy alpha from market beta.
7. Use Monte Carlo simulation to assess robustness (randomize trade sequence).
8. Watch for overfitting: if strategy requires >3 parameters, test each parameter's sensitivity.

---

## Sources

### Market Structure & Core Concepts
- [Market Structure Breaks - Drift Learn](https://www.drift.trade/learn/market-structure-breaks)
- [SMC Market Structure: BoS And CHoCH - Daily Price Action](https://dailypriceaction.com/blog/smc-market-structure/)
- [Market Structure Trading Guide - Mind Math Money](https://www.mindmathmoney.com/articles/mastering-market-structure-trading-the-ultimate-guide-2025)
- [Break of Structure - FXOpen](https://fxopen.com/blog/en/what-is-a-break-of-structure/)
- [Market Structure - LuxAlgo Docs](https://docs.luxalgo.com/docs/algos/price-action-concepts/market-structures)
- [BOS in Trading - XS](https://www.xs.com/en/blog/break-of-structure/)

### ICT / Smart Money Concepts
- [Inner Circle Trading Concepts - FXOpen](https://fxopen.com/blog/en/what-are-the-inner-circle-trading-concepts/)
- [ICT Trading Guide - XS](https://www.xs.com/en/blog/ict-trading/)
- [Key ICT Concepts - TradeZella](https://www.tradezella.com/learning-items/key-ict-concepts)
- [ICT Order Blocks Explained - LuxAlgo](https://www.luxalgo.com/blog/ict-trader-concepts-order-blocks-unpacked/)
- [Smart Money Concepts Guide - Medium](https://medium.com/@daolien906118/a-strategists-guide-to-smart-money-concepts-smc-trading-with-the-institutional-flow-4ae3fce50174)
- [Buy Side & Sell Side Liquidity - B2Broker](https://b2broker.com/news/buy-side-liquidity-and-sell-side-liquidity-in-ict-trading-how-does-it-work/)

### Supply & Demand
- [Supply and Demand Guide - PriceActionNinja](https://priceactionninja.com/the-ultimate-guide-to-trading-supply-and-demand-zones/)
- [Sam Seiden Supply & Demand Critique - PriceActionNinja](https://priceactionninja.com/sam-seiden-supply-and-demand/)
- [Supply and Demand Strategy Backtest - QuantifiedStrategies](https://www.quantifiedstrategies.com/supply-and-demand-trading-strategy/)
- [Supply & Demand Zones - LuxAlgo](https://www.luxalgo.com/blog/supply-and-demand-zones-identifying-critical-areas-for-trading-success-2/)

### Al Brooks
- [Al Brooks Price Action Lessons - Trasignal](https://trasignal.com/blog/forex/price-action-trends-by-al-brooks/)
- [Trading Price Action Trends - Amazon](https://www.amazon.com/Trading-Price-Action-Trends-Technical/dp/1118066510)
- [Price Action Trading Books - Brooks Trading Course](https://www.brookstradingcourse.com/price-action-trading-books/)

### Wyckoff Method
- [Wyckoff Method - Wyckoff Analytics](https://www.wyckoffanalytics.com/wyckoff-method/)
- [Wyckoff Accumulation Guide - TrendSpider](https://trendspider.com/learning-center/chart-patterns-wyckoff-accumulation/)
- [Wyckoff Tutorial - StockCharts](https://chartschool.stockcharts.com/table-of-contents/market-analysis/wyckoff-analysis-articles/the-wyckoff-method-a-tutorial)
- [Wyckoff Trading Strategy Backtest - QuantifiedStrategies](https://www.quantifiedstrategies.com/wyckoff-trading-strategy/)

### VSA
- [VSA Guide - Trading Setups Review](https://www.tradingsetupsreview.com/guide-volume-spread-analysis-vsa/)
- [VSA No Demand No Supply - ATAS](https://atas.net/volume-analysis/basics-of-volume-analysis/vsa-and-cluster-analysis-no-demand-and-no-supply/)
- [VSA Methodology - Volume Spread Analysis](https://www.volumespreadanalysis.com/methodology.asp)

### RTM / Institutional Forex
- [RTM Price Action - TradingFinder](https://tradingfinder.com/education/forex/rtm/)
- [RTM Style Guide - TradingFinder](https://tradingfinder.com/education/forex/what-is-rtm/)
- [Flag Limit Pattern - HoneyPips](https://honeypips.com/flag-limit-forex-pattern/)
- [Quasimodo Pattern - Forex Factory](https://www.forexfactory.com/thread/1344230-quasimodo-qm-pattern-explained-in-rtm-methodology)
- [Quasimodo Pattern Guide - HoneyPips](https://honeypips.com/quasimodo-pattern-in-forex/)

### Nial Fuller
- [Price Action Setups - Learn to Trade the Market](https://www.learntotradethemarket.com/forex-trading-strategies/price-action-setups-pin-bars-fakeys-inside-bars)
- [Fakey Strategy - Learn to Trade the Market](https://www.learntotradethemarket.com/trading-videos/trading-price-action-forex-fakey-forex-strategy)

### Multi-Timeframe Analysis
- [Multi-Timeframe Confluence - Oboe](https://oboe.com/learn/advanced-technical-analysis-optimization-8cwkmy/multi-timeframe-confluence-58jtci)
- [Multi-Timeframe Analysis - TradeCiety](https://tradeciety.com/how-to-perform-a-multiple-time-frame-analysis)
- [MTF in Smart Money Concepts - ACY](https://acy.com/en/market-news/education/power-of-multi-timeframe-analysis-in-smart-money-concepts-j-o-134004/)
- [ICT Time Frame Guide - TradingFinder](https://tradingfinder.com/education/forex/ict-time-frame/)

### Confluence & High-Probability Setups
- [Trading Confluence - Learn to Trade the Market](https://www.learntotradethemarket.com/forex-trading-strategies/trading-confluence-price-action)
- [3 Types of Confluence - PriceActionNinja](https://priceactionninja.com/3-golden-types-of-confluence-for-high-profit-trade-setups/)
- [Chart Pattern Failure Rates - LuxAlgo](https://www.luxalgo.com/blog/chart-patterns-with-highest-failure-rates/)
- [7 Best Price Action Patterns by Reliability - Samurai Trading Academy](https://samuraitradingacademy.com/7-best-price-action-patterns/)

### Quantitative Research & Backtesting
- [Price Action Strategies Backtested - QuantifiedStrategies](https://www.quantifiedstrategies.com/price-action-trading-strategies/)
- [Engulfing Pattern Backtest - QuantifiedStrategies](https://www.quantifiedstrategies.com/engulfing-trading-candlestick-pattern/)
- [Candlestick Pattern Success Rates - QuantifiedStrategies](https://www.quantifiedstrategies.com/success-rate-candlestick-patterns/)
- [ATR Stop Loss Strategies - LuxAlgo](https://www.luxalgo.com/blog/5-atr-stop-loss-strategies-for-risk-control/)
- [Fair Value Gap Strategy - Edgeful](https://www.edgeful.com/blog/posts/fair-value-gap-best-practices-guide)

### Academic Papers
- [Foundations of Technical Analysis - Lo, Mamaysky, Wang (2000)](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=228099)
- [Profitability of Candlestick Patterns (Thailand) - SAGE](https://journals.sagepub.com/doi/10.1177/2158244017736799)
- [S/R Levels in Algorithmic Trading - MDPI](https://www.mdpi.com/2227-7390/10/20/3888)
- [Evidence of S/R Levels - arXiv](https://arxiv.org/abs/2101.07410)
- [Predictive Power of Candlestick Patterns - Lund University](https://lup.lub.lu.se/luur/download?func=downloadFile&recordOId=8877738&fileOId=8877838)

### Python Libraries & Code
- [Smart Money Concepts Python Package - GitHub](https://github.com/joshyattridge/smart-money-concepts)
- [Smart Money Concepts - PyPI](https://pypi.org/project/smartmoneyconcepts/0.0.12/)
- [Automating FVG in Python - Medium](https://medium.com/@ziad.francis/automating-fair-value-gaps-fvg-in-python-0768d3f382e6)
- [Automating ICT 2022 Model - Medium](https://medium.com/@farnamrami/automating-ict-2022-model-trading-setups-with-python-and-artificial-intelligence-35936531259b)
- [Demand-Supply Identification Python - GitHub](https://github.com/rbhatia46/Demand-Supply-Identification-Python/)
- [Market Structure Strategy with ATR Stops - Medium](https://pyquantlab.medium.com/breaking-market-structure-a-price-action-trading-strategy-with-swing-points-and-atr-stops-cecab2dc2dde)
- [BOS Strategy Implementation - MQL5](https://www.mql5.com/en/articles/15017)

### Books
- [Price Action Trading Books - Elearnmarkets](https://blog.elearnmarkets.com/top-9-price-action-trading-books/)
- [Top 10 Price Action Books - Trading Setups Review](https://www.tradingsetupsreview.com/top-10-price-action-trading-books/)
- [Comparing Price Action Books - Financial Analyst Insider](https://financialanalystinsider.com/comparing-the-best-price-action-trading-books/)
