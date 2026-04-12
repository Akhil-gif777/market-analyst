"""
Paper trading executor — opens, closes, and updates paper trades.

Supports both long and short positions:
  - Long: buy low, sell high. Stop loss below entry, trailing stop moves UP.
  - Short: sell high, buy low. Stop loss above entry, trailing stop moves DOWN.

Improvements over original:
  - ATR-based stops (adapts to each stock's volatility)
  - Trailing stop (locks in profits, replaces 30-day time limit)
  - R:R-based targets (minimum 1.4:1 risk/reward when no resistance found)
  - Position sizing based on conviction level as % of starting capital
  - Slippage applied at entry and exit for realistic fills
"""
from __future__ import annotations

import logging
import threading
import time
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple

from app.db import database as db
from app.clients.alpha_vantage import get_stock_quote

logger = logging.getLogger(__name__)

# ── Concurrency ───────────────────────────────────────────────────────────────

# Guards check-then-act sequences (cash checks, trade status checks) against
# concurrent access from the background poller, API endpoints, and scanner.
_trade_lock = threading.Lock()

# ── Constants ─────────────────────────────────────────────────────────────────

STARTING_CAPITAL = 100_000.0
SLIPPAGE = 0.001              # 0.1% slippage on entry and exit
STOP_ATR_MULTIPLIER = 2.5     # Stop loss = entry +/- 2.5 * ATR
STOP_FALLBACK_PCT = 0.07      # 7% fallback when no ATR available
TRAILING_ATR_MULTIPLIER = 2.5 # Trailing stop distance = 2.5 * ATR
MAX_POSITIONS = 20            # Maximum concurrent open positions
MAX_SECTOR_POSITIONS = 3      # Maximum positions per sector

# Position sizing: continuous, proportional to score
# score/max_score * MAX_POSITION_PCT, clamped to [MIN, MAX]
MAX_POSITION_PCT = 0.05   # 5% of capital at max score
MIN_POSITION_PCT = 0.01   # 1% of capital at minimum buy threshold


# ── Stop Loss Logic ───────────────────────────────────────────────────────────

def find_structural_stop(
    entry_price: float,
    levels: List[Dict[str, Any]],
    atr: float,
    direction: str = "long",
) -> Tuple[float, str]:
    """
    Find stop loss from structural levels (support/resistance).

    Long: stop at nearest support below entry. If price breaks support, thesis is wrong.
    Short: stop at nearest resistance above entry. If price breaks resistance, thesis is wrong.
    Fallback: ATR-based stop if no structural level found.

    Returns (stop_price, stop_type).
    """
    if direction == "short":
        # Short: stop above entry at nearest resistance
        resistances = sorted(
            [l for l in levels if l.get("type") == "resistance" and l["price"] > entry_price],
            key=lambda l: l["price"],
        )
        if resistances:
            stop = resistances[0]["price"]
            # Add small buffer above resistance (0.5% or 0.5 ATR)
            buffer = min(atr * 0.5, entry_price * 0.005) if atr > 0 else entry_price * 0.005
            return round(stop + buffer, 4), "resistance"
    else:
        # Long: stop below entry at nearest support
        supports = sorted(
            [l for l in levels if l.get("type") == "support" and l["price"] < entry_price],
            key=lambda l: -l["price"],  # nearest first (highest support below entry)
        )
        if supports:
            stop = supports[0]["price"]
            # Subtract small buffer below support
            buffer = min(atr * 0.5, entry_price * 0.005) if atr > 0 else entry_price * 0.005
            return round(stop - buffer, 4), "support"

    # Fallback: ATR-based stop
    if atr > 0:
        if direction == "short":
            return round(entry_price + STOP_ATR_MULTIPLIER * atr, 4), "atr"
        else:
            return round(entry_price - STOP_ATR_MULTIPLIER * atr, 4), "atr"

    # Last resort: percentage
    if direction == "short":
        return round(entry_price * (1 + STOP_FALLBACK_PCT), 4), "pct"
    else:
        return round(entry_price * (1 - STOP_FALLBACK_PCT), 4), "pct"


# ── Open Trade ────────────────────────────────────────────────────────────────

def open_trade(
    ticker: str,
    sector: str,
    strategy: str,
    signal_price: float,
    conviction_score: float,
    max_score: float,
    levels: List[Dict[str, Any]],
    sentiment_score: Optional[float] = None,
    atr: float = 0.0,
    analysis_snapshot: Optional[Dict[str, Any]] = None,
    direction: str = "long",
) -> Optional[Dict[str, Any]]:
    """
    Open a new paper trade (long or short).

    Uses ATR-based stops and R:R-based targets. Falls back to percentage-based
    if ATR is not available.

    For long trades: buy at signal_price + slippage, stop below entry.
    For short trades: sell at signal_price - slippage, stop above entry.
    """
    is_short = direction == "short"

    with _trade_lock:
        # Ensure portfolio exists
        portfolio = db.get_paper_portfolio()
        if not portfolio:
            db.init_paper_portfolio()
            portfolio = db.get_paper_portfolio()

        # Check global position limit
        open_trades = db.get_paper_trades(status="open")
        if len(open_trades) >= MAX_POSITIONS:
            logger.info("[EXECUTOR] Max positions (%d) reached -- skipping %s", MAX_POSITIONS, ticker)
            return None

        # Check sector position limit
        sector_count = sum(1 for t in open_trades if t["sector"] == sector)
        if sector_count >= MAX_SECTOR_POSITIONS:
            logger.info("[EXECUTOR] Max sector positions (%d) for %s reached -- skipping %s",
                        MAX_SECTOR_POSITIONS, sector, ticker)
            return None

        # Continuous position sizing: proportional to score
        score_ratio = conviction_score / max_score if max_score > 0 else 0
        position_pct = MIN_POSITION_PCT + score_ratio * (MAX_POSITION_PCT - MIN_POSITION_PCT)
        position_pct = max(MIN_POSITION_PCT, min(MAX_POSITION_PCT, position_pct))
        position_value = round(STARTING_CAPITAL * position_pct, 2)

        # Check sufficient cash
        if portfolio["current_cash"] < position_value:
            logger.info("[EXECUTOR] Insufficient cash ($%.2f) for %s position ($%.2f)",
                        portfolio["current_cash"], ticker, position_value)
            return None

        # Apply slippage
        if is_short:
            # Short entry: sell at slightly less than signal (slippage works against you)
            entry_price = round(signal_price * (1 - SLIPPAGE), 4)
        else:
            # Long entry: buy at slightly more than signal (slippage works against you)
            entry_price = round(signal_price * (1 + SLIPPAGE), 4)
        shares = round(position_value / entry_price, 6)
        actual_position_value = round(entry_price * shares, 2)

        # Structural stop loss: nearest support (long) or resistance (short)
        stop_loss_price, stop_type = find_structural_stop(entry_price, levels, atr, direction)
        if is_short:
            stop_distance = stop_loss_price - entry_price
        else:
            stop_distance = entry_price - stop_loss_price

        # No hard take profit target — trailing stop manages all exits.
        # Score says buy → we buy. Support breaks → we sell.
        take_profit_type = "trailing"
        if is_short:
            take_profit_price = 0.0001  # sentinel — trailing stop handles exit
        else:
            take_profit_price = round(entry_price * 10, 4)  # sentinel — trailing stop handles exit

        # Serialize analysis snapshot as JSON
        import json
        snapshot_json = json.dumps(analysis_snapshot) if analysis_snapshot else None

        # Derive conviction label for display (informational only -- sizing uses score directly)
        conviction_label = "high" if score_ratio >= 0.37 else "medium" if score_ratio >= 0.26 else "low"

        # Open the trade in DB
        trade_id = db.open_paper_trade(
            ticker=ticker,
            sector=sector,
            strategy=strategy,
            direction=direction,
            conviction=conviction_label,
            conviction_score=conviction_score,
            sentiment_score=sentiment_score,
            signal_price=signal_price,
            entry_price=entry_price,
            shares=shares,
            position_value=actual_position_value,
            stop_loss_price=stop_loss_price,
            trailing_stop_price=stop_loss_price,  # starts same as initial stop
            atr=atr if atr > 0 else None,
            take_profit_price=take_profit_price,
            take_profit_type=take_profit_type,
            analysis_snapshot=snapshot_json,
        )

        # Deduct cash
        db.deduct_cash(actual_position_value)

    # Log the open event (outside lock — no state mutation)
    dir_label = "SHORT" if is_short else "LONG"
    atr_str = f", ATR=${atr:.2f}" if atr > 0 else ""
    db.log_trade_event(
        trade_id,
        "open",
        f"Opened {dir_label} {strategy} trade at ${entry_price:.2f} "
        f"(score {conviction_score}/{max_score}, size ${actual_position_value:.0f} [{position_pct*100:.1f}%], "
        f"stop=${stop_loss_price:.2f} [{stop_type}], trailing stop manages exit{atr_str})",
        entry_price,
    )

    trade = db.get_paper_trade(trade_id)
    logger.info("[EXECUTOR] Opened %s %s | score=%d/%d | size=$%.0f [%.1f%%] | entry=$%.2f | stop=$%.2f [%s] | trailing",
                dir_label, ticker, conviction_score, max_score, actual_position_value, position_pct*100,
                entry_price, stop_loss_price, stop_type)
    return trade


# ── Close Trade ───────────────────────────────────────────────────────────────

def close_trade(trade_id: int, current_price: float, reason: str) -> Dict[str, Any]:
    """
    Close an open paper trade (long or short).

    Applies exit slippage, computes realized P&L, returns cash to portfolio.
    For longs: sell at slightly less (slippage).
    For shorts: buy back at slightly more (slippage).
    """
    with _trade_lock:
        trade = db.get_paper_trade(trade_id)
        if not trade:
            raise ValueError(f"Trade {trade_id} not found")
        if trade["status"] != "open":
            raise ValueError(f"Trade {trade_id} is already closed")

        direction = trade.get("direction", "long")
        is_short = direction == "short"
        shares = trade["shares"]
        entry_price = trade["entry_price"]

        # Apply exit slippage
        if is_short:
            # Short exit: buy back at slightly more (slippage works against you)
            exit_price = round(current_price * (1 + SLIPPAGE), 4)
        else:
            # Long exit: sell at slightly less (slippage works against you)
            exit_price = round(current_price * (1 - SLIPPAGE), 4)

        # Compute realized P&L
        if is_short:
            realized_pnl = round((entry_price - exit_price) * shares, 2)
            realized_pnl_pct = round((entry_price - exit_price) / entry_price * 100, 2)
        else:
            realized_pnl = round((exit_price - entry_price) * shares, 2)
            realized_pnl_pct = round((exit_price - entry_price) / entry_price * 100, 2)

        # Compute days held
        created_at_str = trade.get("created_at", "")
        try:
            created_dt = datetime.fromisoformat(created_at_str.replace("Z", "+00:00"))
            now_dt = datetime.now(timezone.utc)
            days_held = (now_dt - created_dt).days
        except Exception:
            days_held = trade.get("days_held", 0)

        # Update trade in DB
        db.close_paper_trade(
            trade_id=trade_id,
            exit_price=exit_price,
            exit_reason=reason,
            realized_pnl=realized_pnl,
            realized_pnl_pct=realized_pnl_pct,
            days_held=days_held,
        )

        # Return cash (position value + P&L)
        # For both long and short: we reserved position_value at open.
        # Now we get back position_value + realized_pnl.
        proceeds = round(trade["position_value"] + realized_pnl, 2)
        db.return_cash(proceeds)

    # Log close event (outside lock — no state mutation)
    dir_label = "SHORT" if is_short else "LONG"
    pnl_sign = "+" if realized_pnl >= 0 else ""
    db.log_trade_event(
        trade_id,
        "close",
        f"Closed {dir_label} at ${exit_price:.2f} | reason={reason} | P&L={pnl_sign}${realized_pnl:.2f} ({pnl_sign}{realized_pnl_pct:.2f}%)",
        exit_price,
    )

    logger.info("[EXECUTOR] Closed %s trade %d (%s) | reason=%s | exit=$%.2f | pnl=%s$%.2f (%.2f%%)",
                dir_label, trade_id, trade["ticker"], reason, exit_price, pnl_sign, abs(realized_pnl), realized_pnl_pct)

    return db.get_paper_trade(trade_id)


# ── Update Open Positions ─────────────────────────────────────────────────────

def update_open_positions() -> Dict[str, Any]:
    """
    Fetch current quotes for all open positions.

    For each open trade:
      - Checks trailing stop -> closes if breached
      - Checks take profit -> closes if hit
      - Moves trailing stop (up for longs, down for shorts, never against you)
      - Updates unrealized P&L

    No time limit -- trailing stop handles exits for winners and losers.
    """
    open_trades = db.get_paper_trades(status="open")
    if not open_trades:
        return {"updated": 0, "closed": 0, "message": "No open positions"}

    updated = 0
    closed = 0
    closed_trades = []

    for trade in open_trades:
        trade_id = trade["id"]
        ticker = trade["ticker"]
        entry_price = trade["entry_price"]
        shares = trade["shares"]
        current_stop = trade["stop_loss_price"]
        take_profit = trade["take_profit_price"]
        trade_atr = trade.get("atr") or 0
        direction = trade.get("direction", "long")
        is_short = direction == "short"

        # Fetch current quote
        try:
            quote = get_stock_quote(ticker)
            time.sleep(0.2)
        except Exception as e:
            logger.warning("[EXECUTOR] Failed to fetch quote for %s: %s", ticker, e)
            continue

        if not quote or not quote.get("price"):
            logger.warning("[EXECUTOR] Empty quote for %s", ticker)
            continue

        current_price = float(quote["price"])

        # Compute days held
        created_at_str = trade.get("created_at", "")
        try:
            created_dt = datetime.fromisoformat(created_at_str.replace("Z", "+00:00"))
            now_dt = datetime.now(timezone.utc)
            days_held = (now_dt - created_dt).days
        except Exception:
            days_held = trade.get("days_held", 0)

        # ── Check exit conditions ──
        close_reason = None
        if is_short:
            # Short: price going UP is bad. Stop loss is ABOVE entry.
            if current_price >= current_stop:
                close_reason = "trailing_stop" if current_stop < trade.get("trailing_stop_price", float("inf")) else "stop_loss"
            elif current_price <= take_profit and take_profit > 0.001:
                # take_profit for shorts is a low price target (sentinel 0.0001 means trailing)
                close_reason = "take_profit"
        else:
            # Long: price going DOWN is bad. Stop loss is BELOW entry.
            if current_price <= current_stop:
                close_reason = "trailing_stop" if current_stop > trade.get("trailing_stop_price", 0) else "stop_loss"
            elif current_price >= take_profit:
                close_reason = "take_profit"

        if close_reason:
            try:
                close_trade(trade_id, current_price, close_reason)
                closed += 1
                closed_trades.append({"ticker": ticker, "reason": close_reason, "price": current_price})
            except Exception as e:
                logger.error("[EXECUTOR] Failed to close trade %d (%s): %s", trade_id, ticker, e)
            continue

        # ── Structural trailing stop: broken resistance becomes new stop ──
        # When price breaks through a resistance level, that level becomes support.
        # Move the stop up to each broken resistance. Never moves down.
        new_stop = current_stop

        # Get resistance/support levels from analysis snapshot
        import json as _json
        snapshot_str = trade.get("analysis_snapshot")
        snapshot = {}
        if snapshot_str and isinstance(snapshot_str, str):
            try:
                snapshot = _json.loads(snapshot_str)
            except (ValueError, TypeError):
                pass
        levels = snapshot.get("key_levels", [])

        if is_short:
            # Short: price going DOWN is profitable.
            # When price breaks below a support level, that becomes resistance (new stop).
            supports_below = sorted(
                [l["price"] for l in levels if l.get("type") == "support" and l["price"] < entry_price],
                reverse=True,  # highest first
            )
            for level in supports_below:
                if current_price < level and level < current_stop:
                    # Price broke below this support — move stop down to it
                    buffer = min(trade_atr * 0.5, level * 0.005) if trade_atr > 0 else level * 0.005
                    candidate = round(level + buffer, 4)
                    if candidate < new_stop:
                        db.log_trade_event(
                            trade_id, "trailing_stop",
                            f"Broke below support ${level:.2f} — stop lowered: ${current_stop:.2f} → ${candidate:.2f} (price=${current_price:.2f})",
                            current_price,
                        )
                        new_stop = candidate
        else:
            # Long: price going UP is profitable.
            # When price breaks above a resistance level, that becomes support (new stop).
            resistances_above = sorted(
                [l["price"] for l in levels if l.get("type") == "resistance" and l["price"] > entry_price],
            )
            for level in resistances_above:
                if current_price > level:
                    # Price broke above this resistance — move stop up to it
                    buffer = min(trade_atr * 0.5, level * 0.005) if trade_atr > 0 else level * 0.005
                    candidate = round(level - buffer, 4)
                    if candidate > new_stop:
                        db.log_trade_event(
                            trade_id, "trailing_stop",
                            f"Broke above resistance ${level:.2f} — stop raised: ${current_stop:.2f} → ${candidate:.2f} (price=${current_price:.2f})",
                            current_price,
                        )
                        new_stop = candidate

        # Update unrealized P&L (direction-aware)
        if is_short:
            unrealized_pnl = round((entry_price - current_price) * shares, 2)
            unrealized_pnl_pct = round((entry_price - current_price) / entry_price * 100, 2)
        else:
            unrealized_pnl = round((current_price - entry_price) * shares, 2)
            unrealized_pnl_pct = round((current_price - entry_price) / entry_price * 100, 2)

        try:
            db.update_trade_price(
                trade_id=trade_id,
                current_price=current_price,
                unrealized_pnl=unrealized_pnl,
                unrealized_pnl_pct=unrealized_pnl_pct,
                days_held=days_held,
                stop_loss_price=new_stop if new_stop != current_stop else None,
                trailing_stop_price=new_stop if new_stop != current_stop else None,
            )
            updated += 1
        except Exception as e:
            logger.error("[EXECUTOR] Failed to update trade %d (%s): %s", trade_id, ticker, e)

    return {
        "updated": updated,
        "closed": closed,
        "closed_details": closed_trades,
        "total_open": len(open_trades),
    }
