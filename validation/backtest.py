#!/usr/bin/env python3
"""
Multi-strategy backtest harness for price action strategies.

Runs 6 strategies (including the baseline confluence scorer) across
historical data for multiple tickers, measures forward returns per
strategy, and produces a comparative statistical report.

Usage:
    python -m validation.backtest
    python -m validation.backtest --tickers AAPL MSFT GOOGL
    python -m validation.backtest --start 2020-01-01 --end 2025-12-31
    python -m validation.backtest --horizons 5 10 20
    python -m validation.backtest --strategies confluence_score mean_reversion
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from pathlib import Path
from typing import List, Dict, Any, Optional

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, MofNCompleteColumn
from rich import box

from scipy import stats

from validation.data_loader import download_ticker, resample_weekly, df_to_ohlcv_list
from validation.indicators import compute_rsi, compute_macd, compute_atr
from validation import metrics
from validation.strategies import ALL_STRATEGIES

from app.analysis.price_action import (
    detect_swing_points,
    classify_market_structure,
    find_support_resistance,
    detect_candlestick_patterns,
    analyze_volume,
    compute_confluence_score,
    compute_sma,
    compute_ema,
    compute_ma_signals,
)

console = Console()

DEFAULT_TICKERS = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA",
    "JPM", "XOM", "UNH", "PG", "TSLA",
]
DEFAULT_START = "2019-01-01"
DEFAULT_END = "2026-01-01"
DEFAULT_HORIZONS = [5, 10, 20]
DEFAULT_WARMUP = 252  # 1 trading year

RESULTS_DIR = Path("validation/results")


def run_backtest(
    tickers: List[str],
    start: str,
    end: str,
    warmup: int = DEFAULT_WARMUP,
    horizons: List[int] = None,
    strategy_names: List[str] = None,
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Run multiple price action strategies across historical data.

    For each ticker and each trading day (after warmup), computes all
    indicators once, then calls each strategy function. Strategies that
    return a signal get a record stored; None means "no opinion" (skipped).

    Returns dict of {strategy_name: [signal_records]}.
    """
    horizons = horizons or DEFAULT_HORIZONS
    strategies_to_run = {
        k: v for k, v in ALL_STRATEGIES.items()
        if strategy_names is None or k in strategy_names
    }

    # Per-strategy signal lists
    strategy_signals: Dict[str, List[Dict[str, Any]]] = {
        name: [] for name in strategies_to_run
    }
    daily_prices_map: Dict[str, List[Dict[str, Any]]] = {}

    # ── Phase 1: Download data ──
    console.print("\n[bold]Phase 1: Downloading data[/bold]")
    ticker_data = {}

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Downloading...", total=len(tickers))

        for ticker in tickers:
            progress.update(task, description=f"Downloading {ticker}...")
            try:
                daily_df = download_ticker(ticker, start, end)
                weekly_df = resample_weekly(daily_df)
                daily_list = df_to_ohlcv_list(daily_df)
                weekly_list = df_to_ohlcv_list(weekly_df)

                ticker_data[ticker] = {
                    "daily": daily_list,
                    "weekly": weekly_list,
                }
                daily_prices_map[ticker] = daily_list

                console.print(
                    f"  {ticker}: {len(daily_list)} daily bars, "
                    f"{len(weekly_list)} weekly bars"
                )
            except Exception as e:
                console.print(f"  [red]{ticker}: Failed — {e}[/red]")

            progress.advance(task)

    if not ticker_data:
        console.print("[red]No data downloaded. Aborting.[/red]")
        return {}

    # ── Phase 2: Run all strategies ──
    n_strats = len(strategies_to_run)
    console.print(f"\n[bold]Phase 2: Running {n_strats} strategies[/bold]")
    for name, info in strategies_to_run.items():
        console.print(f"  [{name}] {info['name']}: {info['description']}")

    total_iterations = sum(
        max(0, len(td["daily"]) - warmup)
        for td in ticker_data.values()
    )

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Scoring...", total=total_iterations)

        for ticker, data in ticker_data.items():
            daily = data["daily"]
            weekly = data["weekly"]
            strat_counts = {name: 0 for name in strategies_to_run}
            t_start = time.time()

            progress.update(task, description=f"Scoring {ticker}...")

            for t in range(warmup, len(daily)):
                # Point-in-time: only use data up to index t
                d_start = max(0, t - 249)
                d_slice = daily[d_start:t + 1]

                # Weekly: all bars with date <= current date
                current_date = daily[t]["date"]
                w_slice = [w for w in weekly if w["date"] <= current_date]
                w_slice = w_slice[-104:]  # last 2 years

                if len(d_slice) < 50 or len(w_slice) < 10:
                    progress.advance(task)
                    continue

                # ── Compute indicators once (shared by all strategies) ──
                rsi = compute_rsi(d_slice, period=14)
                macd_data = compute_macd(d_slice)
                atr = compute_atr(d_slice, period=14)

                ema_21_series = compute_ema(d_slice, 21)
                sma_50_series = compute_sma(d_slice, 50)
                sma_200_series = compute_sma(d_slice, 200)
                ema_21 = ema_21_series[-1]["value"] if ema_21_series else None
                ma_50 = sma_50_series[-1]["value"] if sma_50_series else None
                ma_200 = sma_200_series[-1]["value"] if sma_200_series else None

                daily_swings = detect_swing_points(d_slice, lookback=3)
                weekly_swings = detect_swing_points(w_slice, lookback=3)
                daily_structure = classify_market_structure(daily_swings)
                weekly_structure = classify_market_structure(weekly_swings)

                current_price = d_slice[-1]["close"]
                levels = find_support_resistance(
                    daily_swings, weekly_swings, current_price, ma_50, ma_200, ema_21=ema_21
                )
                patterns = detect_candlestick_patterns(d_slice, levels)
                volume = analyze_volume(d_slice)
                ma_signals = compute_ma_signals(
                    sma_50_series, sma_200_series, current_price,
                    ema_21_series=ema_21_series,
                )

                score_result = compute_confluence_score(
                    weekly_structure, daily_structure, levels, patterns, volume,
                    current_price,
                    rsi_data=rsi, macd_data=macd_data,
                    ma_signals=ma_signals,
                    atr=atr, daily_prices=d_slice,
                )

                # ── Build shared kwargs for all strategy functions ──
                shared_kwargs = {
                    "daily_prices": d_slice,
                    "weekly_prices": w_slice,
                    "daily_swings": daily_swings,
                    "weekly_swings": weekly_swings,
                    "daily_structure": daily_structure,
                    "weekly_structure": weekly_structure,
                    "levels": levels,
                    "patterns": patterns,
                    "volume": volume,
                    "current_price": current_price,
                    "rsi": rsi,
                    "macd": macd_data,
                    "atr": atr,
                    "score_result": score_result,
                    "ma_50": ma_50,
                    "ma_200": ma_200,
                }

                # ── Call each strategy ──
                for strat_name, strat_info in strategies_to_run.items():
                    signal = strat_info["fn"](**shared_kwargs)

                    if signal is not None:  # None = no opinion, skip
                        strategy_signals[strat_name].append({
                            "ticker": ticker,
                            "date": current_date,
                            "price": current_price,
                            "signal": signal,
                            "atr": atr,
                            # Include score for the baseline strategy's monotonicity test
                            "score": score_result["total_score"] if strat_name == "confluence_score" else 0,
                            "layers": score_result["layers"] if strat_name == "confluence_score" else [],
                            "weekly_trend": weekly_structure.get("trend", ""),
                            "daily_trend": daily_structure.get("trend", ""),
                        })
                        strat_counts[strat_name] += 1

                progress.advance(task)

            elapsed = time.time() - t_start
            parts = ", ".join(f"{n}={c}" for n, c in strat_counts.items() if c > 0)
            console.print(f"  {ticker} ({elapsed:.1f}s): {parts}")

    # ── Phase 3: Download benchmark (SPY) and compute forward returns ──
    console.print("\n[bold]Phase 3: Computing forward returns (with SPY benchmark)[/bold]")

    benchmark_prices = None
    try:
        spy_df = download_ticker("SPY", start, end)
        benchmark_prices = df_to_ohlcv_list(spy_df)
        console.print(f"  SPY benchmark: {len(benchmark_prices)} bars")
    except Exception as e:
        console.print(f"  [yellow]SPY download failed ({e}) — excess returns unavailable[/yellow]")

    for strat_name, sigs in strategy_signals.items():
        metrics.attach_forward_returns(sigs, daily_prices_map, horizons, benchmark_prices)
        # Apply transaction costs
        metrics.attach_transaction_costs(sigs, horizons, cost_bps=15.0)
        valid = sum(1 for s in sigs if s.get(f"fwd_{horizons[0]}d") is not None)
        console.print(f"  {strat_name}: {valid}/{len(sigs)} signals have forward returns")

    # ── Phase 3.5: Tag market regimes ──
    console.print("\n[bold]Phase 3.5: Tagging market regimes[/bold]")
    if benchmark_prices:
        for strat_name, sigs in strategy_signals.items():
            metrics.tag_signal_regimes(sigs, benchmark_prices)
        # Count regime distribution
        regime_counts = {}
        for sigs in strategy_signals.values():
            for sig in sigs:
                r = sig.get("regime", "unknown")
                regime_counts[r] = regime_counts.get(r, 0) + 1
            break  # same for all strategies since same dates
        for r, c in sorted(regime_counts.items()):
            console.print(f"  {r}: {c} signals")

    return strategy_signals


def run_walk_forward(
    strategy_signals: Dict[str, List[Dict[str, Any]]],
    horizons: List[int],
    n_windows: int = 6,
    is_oos_ratio: float = 3.0,  # 3:1 in-sample to out-of-sample
) -> Dict[str, Any]:
    """
    Walk-forward analysis: split signals chronologically into rolling IS/OOS windows.

    For each window:
    1. IS (in-sample): compute optimal parameters / measure performance
    2. OOS (out-of-sample): measure performance with IS parameters

    Walk-Forward Efficiency = mean(OOS performance) / mean(IS performance)
    Should be > 0.50 for a robust strategy.
    """
    primary_horizon = horizons[1] if len(horizons) > 1 else horizons[0]

    results = {}
    for strat_name, sigs in strategy_signals.items():
        if not sigs:
            results[strat_name] = {"wfe": 0, "windows": [], "verdict": "NO DATA"}
            continue

        # Sort by date
        sorted_sigs = sorted(sigs, key=lambda s: s["date"])
        n = len(sorted_sigs)

        if n < 50:  # need minimum signals
            results[strat_name] = {"wfe": 0, "windows": [], "verdict": "LOW N"}
            continue

        # Simpler approach: divide into n_windows equal OOS chunks
        # Each OOS chunk uses all prior data as IS
        chunk_size = max(10, n // (n_windows + 1))  # +1 for initial IS window

        windows = []
        for w in range(n_windows):
            oos_start = chunk_size * (w + 1)
            oos_end = min(oos_start + chunk_size, n)
            is_end = oos_start  # IS = everything before OOS

            if oos_end <= oos_start or is_end < 20:
                continue

            is_sigs = sorted_sigs[:is_end]
            oos_sigs = sorted_sigs[oos_start:oos_end]

            # Compute hit rate for IS and OOS
            is_stats = _wf_stats(is_sigs, primary_horizon)
            oos_stats = _wf_stats(oos_sigs, primary_horizon)

            windows.append({
                "window": w + 1,
                "is_period": f"{is_sigs[0]['date']} to {is_sigs[-1]['date']}",
                "oos_period": f"{oos_sigs[0]['date']} to {oos_sigs[-1]['date']}",
                "is_n": len(is_sigs),
                "oos_n": len(oos_sigs),
                "is_hit_rate": is_stats["hit_rate"],
                "oos_hit_rate": oos_stats["hit_rate"],
                "is_mean_return": is_stats["mean_return"],
                "oos_mean_return": oos_stats["mean_return"],
            })

        # Walk-Forward Efficiency
        is_returns = [w["is_mean_return"] for w in windows if w["is_mean_return"] != 0]
        oos_returns = [w["oos_mean_return"] for w in windows]

        if is_returns and sum(abs(r) for r in is_returns) > 0:
            avg_is = sum(is_returns) / len(is_returns)
            avg_oos = sum(oos_returns) / len(oos_returns)
            wfe = (avg_oos / avg_is * 100) if avg_is != 0 else 0
        else:
            avg_is = 0
            avg_oos = 0
            wfe = 0

        if wfe >= 60:
            verdict = "ROBUST"
        elif wfe >= 40:
            verdict = "ACCEPTABLE"
        elif wfe > 0:
            verdict = "WEAK"
        else:
            verdict = "OVERFIT"

        results[strat_name] = {
            "wfe": round(wfe, 1),
            "avg_is_return": round(avg_is * 100, 3) if is_returns else 0,
            "avg_oos_return": round(avg_oos * 100, 3) if oos_returns else 0,
            "windows": windows,
            "verdict": verdict,
        }

    return results


def _wf_stats(sigs: List[Dict[str, Any]], horizon: int) -> Dict[str, float]:
    """Compute basic stats for walk-forward window."""
    buy_rets = []
    sell_rets = []

    for sig in sigs:
        ret = sig.get(f"fwd_{horizon}d")
        if ret is None:
            continue
        if sig["signal"] in ("buy", "strong_buy"):
            buy_rets.append(ret)
        elif sig["signal"] in ("sell", "strong_sell"):
            sell_rets.append(ret)

    all_rets = buy_rets + [-r for r in sell_rets]

    if not all_rets:
        return {"hit_rate": 0, "mean_return": 0}

    hits = sum(1 for r in all_rets if r > 0)
    hit_rate = round(hits / len(all_rets) * 100, 1)
    mean_return = sum(all_rets) / len(all_rets)

    return {"hit_rate": hit_rate, "mean_return": round(mean_return, 6)}


def print_comparative_report(
    strategy_signals: Dict[str, List[Dict[str, Any]]],
    horizons: List[int],
) -> None:
    """Print the multi-strategy comparative backtest report."""
    primary_horizon = horizons[1] if len(horizons) > 1 else horizons[0]

    # ── Overview: Signal counts per strategy ──
    console.print("\n")
    console.print(Panel("[bold]STRATEGY SIGNAL COUNTS[/bold]", box=box.DOUBLE))
    table = Table(box=box.SIMPLE)
    table.add_column("Strategy", style="bold")
    table.add_column("Total Signals", justify="right")
    table.add_column("Buy", justify="right", style="green")
    table.add_column("Sell", justify="right", style="red")
    table.add_column("Buy %", justify="right")

    for name, sigs in strategy_signals.items():
        buys = sum(1 for s in sigs if s["signal"] == "buy")
        sells = sum(1 for s in sigs if s["signal"] == "sell")
        total = len(sigs)
        buy_pct = buys / total * 100 if total > 0 else 0
        label = ALL_STRATEGIES[name]["name"]
        table.add_row(label, str(total), str(buys), str(sells), f"{buy_pct:.0f}%")

    console.print(table)

    # ── Head-to-head comparison table per horizon ──
    for horizon in horizons:
        console.print(f"\n")
        console.print(Panel(
            f"[bold]STRATEGY COMPARISON — {horizon}-DAY FORWARD RETURNS[/bold]",
            box=box.DOUBLE,
        ))

        table = Table(box=box.SIMPLE, show_lines=True)
        table.add_column("Strategy", style="bold")
        table.add_column("Signals", justify="right")
        table.add_column("Buy Hit%", justify="right")
        table.add_column("Buy Mean", justify="right")
        table.add_column("Sell Hit%", justify="right")
        table.add_column("Sell Mean", justify="right")
        table.add_column("Excess Buy", justify="right")
        table.add_column("Excess Sell", justify="right")
        table.add_column("t-stat", justify="right")
        table.add_column("p-value", justify="right")

        for name, sigs in strategy_signals.items():
            label = ALL_STRATEGIES[name]["name"]
            strat_stats = _compute_strategy_stats(sigs, horizon)

            hr_buy_c = "green" if strat_stats["buy_hit_rate"] > 55 else "yellow" if strat_stats["buy_hit_rate"] > 50 else "red"
            hr_sell_c = "green" if strat_stats["sell_hit_rate"] > 55 else "yellow" if strat_stats["sell_hit_rate"] > 50 else "red"
            p_str = "<0.001" if strat_stats["p_value"] < 0.001 else f"{strat_stats['p_value']:.3f}"
            p_color = "green" if strat_stats["p_value"] < 0.05 else "dim"

            table.add_row(
                label,
                str(strat_stats["n_signals"]),
                f"[{hr_buy_c}]{strat_stats['buy_hit_rate']:.1f}%[/{hr_buy_c}]" if strat_stats["buy_count"] > 0 else "[dim]—[/dim]",
                _color_return(strat_stats["buy_mean"]) if strat_stats["buy_count"] > 0 else "[dim]—[/dim]",
                f"[{hr_sell_c}]{strat_stats['sell_hit_rate']:.1f}%[/{hr_sell_c}]" if strat_stats["sell_count"] > 0 else "[dim]—[/dim]",
                _color_return(strat_stats["sell_mean"]) if strat_stats["sell_count"] > 0 else "[dim]—[/dim]",
                _color_return(strat_stats["excess_buy_mean"]) if strat_stats["excess_buy_count"] > 0 else "[dim]—[/dim]",
                _color_return(strat_stats["excess_sell_mean"]) if strat_stats["excess_sell_count"] > 0 else "[dim]—[/dim]",
                f"{strat_stats['t_stat']:.2f}",
                f"[{p_color}]{p_str}[/{p_color}]",
            )

        console.print(table)

    # ── Detailed report per strategy ──
    for name, sigs in strategy_signals.items():
        label = ALL_STRATEGIES[name]["name"]
        console.print(f"\n{'='*70}")
        console.print(Panel(f"[bold]{label}[/bold] ({len(sigs)} signals)", box=box.DOUBLE))

        if not sigs:
            console.print("  [dim]No signals generated.[/dim]")
            continue

        has_excess = any(s.get(f"fwd_{horizons[0]}d_excess") is not None for s in sigs)

        # Returns per direction
        for horizon in horizons:
            if has_excess:
                console.print(f"\n  [bold]Excess Returns vs SPY — {horizon}d:[/bold]")
                _print_direction_stats(sigs, horizon, use_excess=True)
            console.print(f"\n  [bold]Raw Returns — {horizon}d:[/bold]")
            _print_direction_stats(sigs, horizon, use_excess=False)

        # For baseline: also show monotonicity and layer ablation
        if name == "confluence_score":
            console.print(f"\n  [bold]Score Monotonicity:[/bold]")
            for horizon in horizons:
                mono = metrics.excess_score_monotonicity(sigs, horizon) if has_excess else metrics.score_monotonicity(sigs, horizon)
                status = "[green]PASS[/green]" if mono["pass"] else "[red]FAIL[/red]"
                console.print(
                    f"    {horizon}d: Spearman r = {mono['correlation']:+.4f}, "
                    f"p = {mono['p_value']:.6f}, n = {mono['n']}  {status}"
                )

            console.print(f"\n  [bold]Layer Ablation:[/bold]")
            ablation = metrics.layer_ablation(sigs, primary_horizon)
            for entry in ablation:
                drop = entry.get("corr_drop", 0)
                color = "green" if drop > 0.01 else "yellow" if drop > 0 else "red"
                console.print(
                    f"    {entry['layer']}: corr_drop = [{color}]{drop:+.4f}[/{color}]"
                )

        # Regime-stratified performance
        console.print(f"\n  [bold]Performance by Market Regime ({primary_horizon}d):[/bold]")
        regime_stats = metrics.returns_by_regime(sigs, primary_horizon)
        if regime_stats:
            regime_table = Table(box=box.SIMPLE)
            regime_table.add_column("Regime", style="bold")
            regime_table.add_column("Buy N", justify="right")
            regime_table.add_column("Buy Hit%", justify="right")
            regime_table.add_column("Buy Mean", justify="right")
            regime_table.add_column("Sell N", justify="right")
            regime_table.add_column("Sell Hit%", justify="right")
            regime_table.add_column("Sell Mean", justify="right")

            for regime, stats_data in regime_stats.items():
                hr_c = "green" if stats_data["buy_hit_rate"] > 55 else "yellow" if stats_data["buy_hit_rate"] > 50 else "red"
                regime_table.add_row(
                    regime,
                    str(stats_data["buy_count"]),
                    f"[{hr_c}]{stats_data['buy_hit_rate']:.1f}%[/{hr_c}]",
                    _color_return(stats_data["buy_mean"]),
                    str(stats_data["sell_count"]),
                    f"{stats_data['sell_hit_rate']:.1f}%",
                    _color_return(stats_data["sell_mean"]),
                )
            console.print(regime_table)

        # Equity curve metrics
        console.print(f"\n  [bold]Risk-Adjusted Metrics ({primary_horizon}d):[/bold]")
        eq_raw = metrics.compute_equity_curve(sigs, primary_horizon, use_net=False)
        eq_net = metrics.compute_equity_curve(sigs, primary_horizon, use_net=True)
        console.print(f"    Trades: {eq_raw['n_trades']}")
        console.print(f"    Total Return:  raw {eq_raw['total_return']:+.1f}% | net {eq_net['total_return']:+.1f}%")
        console.print(f"    Max Drawdown:  {eq_raw['max_drawdown']:.1f}%")
        console.print(f"    Sharpe:        raw {eq_raw['sharpe']:.3f} | net {eq_net['sharpe']:.3f}")
        console.print(f"    Sortino:       raw {eq_raw['sortino']:.3f} | net {eq_net['sortino']:.3f}")
        console.print(f"    Calmar:        raw {eq_raw['calmar']:.3f} | net {eq_net['calmar']:.3f}")

    # ── Final ranking ──
    console.print(f"\n")
    console.print(Panel(
        f"[bold]STRATEGY RANKING — {primary_horizon}-DAY EXCESS RETURNS[/bold]",
        box=box.DOUBLE,
    ))
    _print_ranking(strategy_signals, primary_horizon)

    # ── Walk-Forward Analysis ──
    console.print(f"\n")
    console.print(Panel("[bold]WALK-FORWARD ANALYSIS[/bold]", box=box.DOUBLE))
    wf_results = run_walk_forward(strategy_signals, horizons)
    for name, wf in wf_results.items():
        label = ALL_STRATEGIES[name]["name"]
        verdict_color = {"ROBUST": "green", "ACCEPTABLE": "yellow", "WEAK": "red", "OVERFIT": "bold red"}.get(wf["verdict"], "dim")
        console.print(f"\n  [bold]{label}[/bold]: WFE = {wf['wfe']:.1f}% [{verdict_color}]{wf['verdict']}[/{verdict_color}]")
        if wf.get("avg_is_return") is not None:
            console.print(f"    Avg IS return: {wf['avg_is_return']:+.3f}%  |  Avg OOS return: {wf['avg_oos_return']:+.3f}%")
        for w in wf.get("windows", []):
            oos_c = "green" if w["oos_mean_return"] > 0 else "red"
            console.print(
                f"    Window {w['window']}: IS {w['is_hit_rate']:.1f}% ({w['is_n']}n) → "
                f"OOS [{oos_c}]{w['oos_hit_rate']:.1f}%[/{oos_c}] ({w['oos_n']}n)"
            )


def _compute_strategy_stats(
    signals: List[Dict[str, Any]],
    horizon: int,
) -> Dict[str, Any]:
    """Compute summary stats for a strategy at a given horizon."""
    buy_returns = []
    sell_returns = []
    excess_buy_returns = []
    excess_sell_returns = []

    for sig in signals:
        ret = sig.get(f"fwd_{horizon}d")
        excess = sig.get(f"fwd_{horizon}d_excess")

        if ret is None:
            continue

        if sig["signal"] in ("buy", "strong_buy"):
            buy_returns.append(ret)
            if excess is not None:
                excess_buy_returns.append(excess)
        elif sig["signal"] in ("sell", "strong_sell"):
            sell_returns.append(ret)
            if excess is not None:
                excess_sell_returns.append(excess)

    buy_hit = sum(1 for r in buy_returns if r > 0) / len(buy_returns) * 100 if buy_returns else 0
    sell_hit = sum(1 for r in sell_returns if r < 0) / len(sell_returns) * 100 if sell_returns else 0

    buy_mean = sum(buy_returns) / len(buy_returns) * 100 if buy_returns else 0
    sell_mean = sum(sell_returns) / len(sell_returns) * 100 if sell_returns else 0

    excess_buy_mean = sum(excess_buy_returns) / len(excess_buy_returns) * 100 if excess_buy_returns else 0
    excess_sell_mean = sum(excess_sell_returns) / len(excess_sell_returns) * 100 if excess_sell_returns else 0

    # Directional t-test: are returns in the expected direction?
    # For buys: is mean return > 0? For sells: is mean return < 0?
    # Combined: flip sell returns and test if all are > 0
    all_directional = buy_returns + [-r for r in sell_returns]
    if len(all_directional) >= 2:
        t_stat, p_value = stats.ttest_1samp(all_directional, 0)
        # One-sided: we want returns > 0
        p_value = p_value / 2 if t_stat > 0 else 1 - p_value / 2
    else:
        t_stat, p_value = 0, 1.0

    return {
        "n_signals": len(buy_returns) + len(sell_returns),
        "buy_count": len(buy_returns),
        "sell_count": len(sell_returns),
        "buy_hit_rate": buy_hit,
        "sell_hit_rate": sell_hit,
        "buy_mean": buy_mean,
        "sell_mean": sell_mean,
        "excess_buy_count": len(excess_buy_returns),
        "excess_sell_count": len(excess_sell_returns),
        "excess_buy_mean": excess_buy_mean,
        "excess_sell_mean": excess_sell_mean,
        "t_stat": t_stat,
        "p_value": p_value,
    }


def _print_direction_stats(
    signals: List[Dict[str, Any]],
    horizon: int,
    use_excess: bool = False,
) -> None:
    """Print buy/sell return stats for a strategy."""
    ret_key = f"fwd_{horizon}d_excess" if use_excess else f"fwd_{horizon}d"

    buy_rets = [s[ret_key] for s in signals if s["signal"] == "buy" and s.get(ret_key) is not None]
    sell_rets = [s[ret_key] for s in signals if s["signal"] == "sell" and s.get(ret_key) is not None]

    for direction, rets in [("Buy", buy_rets), ("Sell", sell_rets)]:
        if not rets:
            console.print(f"    {direction}: no signals")
            continue

        mean_r = sum(rets) / len(rets) * 100
        sorted_r = sorted(rets)
        median_r = sorted_r[len(sorted_r) // 2] * 100

        if direction == "Buy":
            hit_rate = sum(1 for r in rets if r > 0) / len(rets) * 100
        else:
            hit_rate = sum(1 for r in rets if r < 0) / len(rets) * 100

        if len(rets) >= 2:
            t_stat, p_val = stats.ttest_1samp(rets, 0)
        else:
            t_stat, p_val = 0, 1.0

        hr_c = "green" if hit_rate > 55 else "yellow" if hit_rate > 50 else "red"
        p_str = "<0.001" if p_val < 0.001 else f"{p_val:.3f}"
        console.print(
            f"    {direction}: n={len(rets)}, mean={_color_return(mean_r)}, "
            f"median={_color_return(median_r)}, "
            f"hit=[{hr_c}]{hit_rate:.1f}%[/{hr_c}], "
            f"t={t_stat:.2f}, p={p_str}"
        )


def _print_ranking(
    strategy_signals: Dict[str, List[Dict[str, Any]]],
    horizon: int,
) -> None:
    """Print a ranked summary of strategies by predictive power."""
    rows = []
    for name, sigs in strategy_signals.items():
        st = _compute_strategy_stats(sigs, horizon)
        # Use excess returns if available, else raw
        excess_buy_rets = [
            s[f"fwd_{horizon}d_excess"] for s in sigs
            if s["signal"] == "buy" and s.get(f"fwd_{horizon}d_excess") is not None
        ]
        excess_sell_rets = [
            s[f"fwd_{horizon}d_excess"] for s in sigs
            if s["signal"] == "sell" and s.get(f"fwd_{horizon}d_excess") is not None
        ]

        # Combined directional metric using excess returns
        all_directional_excess = excess_buy_rets + [-r for r in excess_sell_rets]
        if len(all_directional_excess) >= 2:
            mean_excess = sum(all_directional_excess) / len(all_directional_excess) * 100
            t_stat, p_val = stats.ttest_1samp(all_directional_excess, 0)
            p_val = p_val / 2 if t_stat > 0 else 1 - p_val / 2
        else:
            mean_excess = 0
            t_stat, p_val = 0, 1.0

        combined_hit = 0
        total_for_hit = 0
        if st["buy_count"] > 0:
            combined_hit += st["buy_hit_rate"] * st["buy_count"]
            total_for_hit += st["buy_count"]
        if st["sell_count"] > 0:
            combined_hit += st["sell_hit_rate"] * st["sell_count"]
            total_for_hit += st["sell_count"]
        combined_hit = combined_hit / total_for_hit if total_for_hit > 0 else 0

        rows.append({
            "name": name,
            "label": ALL_STRATEGIES[name]["name"],
            "n": st["n_signals"],
            "combined_hit": combined_hit,
            "mean_excess": mean_excess,
            "t_stat": t_stat,
            "p_value": p_val,
        })

    # Sort by combined directional accuracy (excess), significant ones first
    rows.sort(key=lambda r: (-int(r["p_value"] < 0.05), -r["mean_excess"]))

    table = Table(box=box.SIMPLE, show_lines=True)
    table.add_column("Rank", justify="center", style="bold")
    table.add_column("Strategy", style="bold")
    table.add_column("Signals", justify="right")
    table.add_column("Hit Rate", justify="right")
    table.add_column("Mean Excess", justify="right")
    table.add_column("t-stat", justify="right")
    table.add_column("p-value", justify="right")
    table.add_column("Verdict", justify="center")

    for i, row in enumerate(rows, 1):
        hr_c = "green" if row["combined_hit"] > 55 else "yellow" if row["combined_hit"] > 50 else "red"
        p_str = "<0.001" if row["p_value"] < 0.001 else f"{row['p_value']:.3f}"
        p_color = "green" if row["p_value"] < 0.05 else "dim"

        if row["p_value"] < 0.05 and row["mean_excess"] > 0:
            verdict = "[green]PROMISING[/green]"
        elif row["p_value"] < 0.10 and row["mean_excess"] > 0:
            verdict = "[yellow]WEAK[/yellow]"
        elif row["n"] < 30:
            verdict = "[dim]LOW N[/dim]"
        else:
            verdict = "[red]NO EDGE[/red]"

        table.add_row(
            str(i),
            row["label"],
            str(row["n"]),
            f"[{hr_c}]{row['combined_hit']:.1f}%[/{hr_c}]",
            _color_return(row["mean_excess"]),
            f"{row['t_stat']:.2f}",
            f"[{p_color}]{p_str}[/{p_color}]",
            verdict,
        )

    console.print(table)


def save_results(
    strategy_signals: Dict[str, List[Dict[str, Any]]],
    horizons: List[int],
) -> Path:
    """Save backtest results to JSON."""
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    output = {}
    for name, sigs in strategy_signals.items():
        clean = []
        for s in sigs:
            entry = {k: v for k, v in s.items() if k != "layers"}
            entry["layer_scores"] = {
                l["name"]: l["score"] for l in s.get("layers", [])
            }
            clean.append(entry)
        output[name] = {
            "signal_count": len(sigs),
            "signals": clean,
        }

    output_path = RESULTS_DIR / "backtest_results.json"
    with open(output_path, "w") as f:
        json.dump({
            "horizons": horizons,
            "strategies": output,
        }, f, indent=2)

    console.print(f"\n[dim]Results saved to {output_path}[/dim]")
    return output_path


def build_backtest_report(
    strategy_signals: Dict[str, List[Dict[str, Any]]],
    horizons: List[int],
    tickers: List[str] = None,
    elapsed: float = 0,
) -> Dict[str, Any]:
    """
    Build a JSON-serializable backtest report from strategy_signals.
    Called by the API endpoint to return structured results to the UI.
    """
    primary_horizon = horizons[1] if len(horizons) > 1 else horizons[0]

    strategies_out = {}
    for name, sigs in strategy_signals.items():
        info = ALL_STRATEGIES[name]
        buy_signals = sum(1 for s in sigs if s["signal"] in ("buy", "strong_buy"))
        sell_signals = sum(1 for s in sigs if s["signal"] in ("sell", "strong_sell"))

        by_horizon = {}
        for h in horizons:
            st = _compute_strategy_stats(sigs, h)
            by_horizon[str(h)] = {k: round(v, 4) if isinstance(v, float) else v for k, v in st.items()}

        # Regime performance and equity metrics
        regime_perf = metrics.returns_by_regime(sigs, primary_horizon)
        eq_raw = metrics.compute_equity_curve(sigs, primary_horizon, use_net=False)
        eq_net = metrics.compute_equity_curve(sigs, primary_horizon, use_net=True)

        strategies_out[name] = {
            "key": name,
            "name": info["name"],
            "description": info["description"],
            "total_signals": len(sigs),
            "buy_signals": buy_signals,
            "sell_signals": sell_signals,
            "by_horizon": by_horizon,
            "regime_performance": regime_perf,
            "equity_raw": eq_raw,
            "equity_net": eq_net,
        }

    # Build ranking using same logic as _print_ranking
    ranking = []
    for name, sigs in strategy_signals.items():
        st = _compute_strategy_stats(sigs, primary_horizon)

        excess_buy = [
            s[f"fwd_{primary_horizon}d_excess"] for s in sigs
            if s["signal"] in ("buy", "strong_buy")
            and s.get(f"fwd_{primary_horizon}d_excess") is not None
        ]
        excess_sell = [
            s[f"fwd_{primary_horizon}d_excess"] for s in sigs
            if s["signal"] in ("sell", "strong_sell")
            and s.get(f"fwd_{primary_horizon}d_excess") is not None
        ]
        all_dir = excess_buy + [-r for r in excess_sell]

        if len(all_dir) >= 2:
            mean_excess = sum(all_dir) / len(all_dir) * 100
            t_stat, p_val = stats.ttest_1samp(all_dir, 0)
            p_val = float(p_val / 2 if t_stat > 0 else 1 - p_val / 2)
        else:
            mean_excess, t_stat, p_val = 0.0, 0.0, 1.0

        combined_hit = 0
        total_for_hit = st["buy_count"] + st["sell_count"]
        if st["buy_count"] > 0:
            combined_hit += st["buy_hit_rate"] * st["buy_count"]
        if st["sell_count"] > 0:
            combined_hit += st["sell_hit_rate"] * st["sell_count"]
        combined_hit = combined_hit / total_for_hit if total_for_hit > 0 else 0

        n = st["n_signals"]
        if p_val < 0.05 and mean_excess > 0:
            verdict = "PROMISING"
        elif p_val < 0.10 and mean_excess > 0:
            verdict = "WEAK"
        elif n < 30:
            verdict = "LOW N"
        else:
            verdict = "NO EDGE"

        ranking.append({
            "key": name,
            "name": ALL_STRATEGIES[name]["name"],
            "n": n,
            "hit_rate": round(combined_hit, 1),
            "mean_excess": round(mean_excess, 3),
            "t_stat": round(float(t_stat), 2),
            "p_value": round(p_val, 4),
            "verdict": verdict,
        })

    ranking.sort(key=lambda r: (-int(r["p_value"] < 0.05), -r["mean_excess"]))
    for i, row in enumerate(ranking, 1):
        row["rank"] = i

    wf_results = run_walk_forward(strategy_signals, horizons)

    return {
        "elapsed": round(elapsed, 1),
        "horizons": horizons,
        "primary_horizon": primary_horizon,
        "tickers": tickers or [],
        "strategies": strategies_out,
        "ranking": ranking,
        "walk_forward": {
            name: {
                "wfe": wf["wfe"],
                "verdict": wf["verdict"],
                "avg_is_return": wf.get("avg_is_return", 0),
                "avg_oos_return": wf.get("avg_oos_return", 0),
            }
            for name, wf in wf_results.items()
        },
    }


def _signal_color(bucket: str) -> str:
    """Get color for a signal bucket."""
    return {
        "strong_buy": "bold green",
        "buy": "green",
        "neutral": "dim",
        "sell": "red",
        "strong_sell": "bold red",
    }.get(bucket, "white")


def _color_return(ret: float) -> str:
    """Color a return percentage."""
    if ret > 0.5:
        return f"[green]{ret:+.3f}%[/green]"
    elif ret < -0.5:
        return f"[red]{ret:+.3f}%[/red]"
    else:
        return f"[dim]{ret:+.3f}%[/dim]"


def main():
    parser = argparse.ArgumentParser(
        description="Multi-strategy price action backtest"
    )
    parser.add_argument(
        "--tickers", nargs="+", default=DEFAULT_TICKERS,
        help=f"Tickers to test (default: {' '.join(DEFAULT_TICKERS)})",
    )
    parser.add_argument(
        "--start", default=DEFAULT_START,
        help=f"Start date (default: {DEFAULT_START})",
    )
    parser.add_argument(
        "--end", default=DEFAULT_END,
        help=f"End date (default: {DEFAULT_END})",
    )
    parser.add_argument(
        "--warmup", type=int, default=DEFAULT_WARMUP,
        help=f"Warmup bars before generating signals (default: {DEFAULT_WARMUP})",
    )
    parser.add_argument(
        "--horizons", nargs="+", type=int, default=DEFAULT_HORIZONS,
        help=f"Forward return horizons in trading days (default: {' '.join(map(str, DEFAULT_HORIZONS))})",
    )
    parser.add_argument(
        "--strategies", nargs="+", default=None,
        help=f"Strategies to run (default: all). Options: {', '.join(ALL_STRATEGIES.keys())}",
    )
    args = parser.parse_args()

    strat_names = args.strategies or list(ALL_STRATEGIES.keys())

    console.print(Panel(
        f"[bold]Multi-Strategy Price Action Backtest[/bold]\n\n"
        f"Tickers:    {', '.join(args.tickers)}\n"
        f"Period:     {args.start} → {args.end}\n"
        f"Warmup:     {args.warmup} bars\n"
        f"Horizons:   {args.horizons} days\n"
        f"Strategies: {', '.join(strat_names)}",
        title="Configuration",
        box=box.ROUNDED,
    ))

    start_time = time.time()

    strategy_signals = run_backtest(
        tickers=args.tickers,
        start=args.start,
        end=args.end,
        warmup=args.warmup,
        horizons=args.horizons,
        strategy_names=strat_names,
    )

    if not strategy_signals or all(len(v) == 0 for v in strategy_signals.values()):
        console.print("[red]No signals generated. Check data availability.[/red]")
        sys.exit(1)

    elapsed = time.time() - start_time
    console.print(f"\n[dim]Backtest completed in {elapsed:.1f}s[/dim]")

    print_comparative_report(strategy_signals, args.horizons)
    save_results(strategy_signals, args.horizons)


if __name__ == "__main__":
    main()
