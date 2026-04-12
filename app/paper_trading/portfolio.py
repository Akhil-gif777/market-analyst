"""Portfolio statistics and summary computation."""
from __future__ import annotations
from typing import Dict, Any
from app.db import database as db
from app.paper_trading.executor import STARTING_CAPITAL


def get_portfolio_summary() -> Dict[str, Any]:
    """Compute full portfolio summary from DB state."""
    portfolio = db.get_paper_portfolio()
    if not portfolio:
        db.init_paper_portfolio()
        portfolio = db.get_paper_portfolio()

    open_trades = db.get_paper_trades(status="open")
    closed_trades = db.get_paper_trades(status="closed")

    # Invested value (sum of position values for open trades)
    invested = sum(t["position_value"] for t in open_trades)

    # Unrealized P&L
    unrealized_pnl = sum((t.get("unrealized_pnl") or 0) for t in open_trades)

    # Realized P&L from closed trades
    realized_pnl = sum((t.get("realized_pnl") or 0) for t in closed_trades)

    # Total portfolio value
    cash = portfolio["current_cash"]
    total_value = cash + invested + unrealized_pnl

    # Win rate from closed trades
    wins = [t for t in closed_trades if (t.get("realized_pnl") or 0) > 0]
    losses = [t for t in closed_trades if (t.get("realized_pnl") or 0) <= 0]
    win_rate = round(len(wins) / len(closed_trades) * 100, 1) if closed_trades else 0

    # Total return
    total_return_pct = round((total_value - STARTING_CAPITAL) / STARTING_CAPITAL * 100, 2)

    # Portfolio risk: sum of max dollar loss per open trade
    total_risk = 0
    for t in open_trades:
        entry = t.get("entry_price", 0)
        stop = t.get("stop_loss_price", 0)
        value = t.get("position_value", 0)
        direction = t.get("direction", "long")
        if entry > 0 and stop > 0 and value > 0:
            if direction == "short":
                risk_pct = (stop - entry) / entry
            else:
                risk_pct = (entry - stop) / entry
            total_risk += value * max(0, risk_pct)

    return {
        "starting_capital": STARTING_CAPITAL,
        "current_cash": round(cash, 2),
        "invested": round(invested, 2),
        "total_value": round(total_value, 2),
        "unrealized_pnl": round(unrealized_pnl, 2),
        "realized_pnl": round(realized_pnl, 2),
        "total_pnl": round(unrealized_pnl + realized_pnl, 2),
        "total_return_pct": total_return_pct,
        "open_positions": len(open_trades),
        "closed_positions": len(closed_trades),
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": win_rate,
        "total_risk": round(total_risk, 2),
        "risk_pct": round(total_risk / STARTING_CAPITAL * 100, 2),
    }
