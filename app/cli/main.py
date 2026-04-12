#!/usr/bin/env python3
"""
CLI interface for Market Analyst.

Usage:
    uv run cli scan                 # Scan news → list events (fast)
    uv run cli deep <event_id>      # Deep-analyze a scanned event
    uv run cli analyze              # Full pipeline (scan + analyze all)
    uv run cli report               # Show latest report
    uv run cli events               # List recent events
    uv run cli chain <event_id>     # Show causal chain for an event
    uv run cli sectors              # Show sector outlook
"""

from __future__ import annotations

import argparse
import json
import logging
import sys

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.tree import Tree
from rich import box

from app.clients import ollama

console = Console()


def cmd_scan(args):
    """Scan news and list detected market-moving events."""
    if not ollama.check_available():
        console.print("[red]Error: Ollama is not running. Start it with 'ollama serve'[/red]")
        sys.exit(1)

    console.print(Panel("[bold]Scanning news for market-moving events...[/bold]", box=box.ROUNDED))

    from app.analysis.pipeline import scan_news
    result = scan_news()

    if result.get("error"):
        console.print(f"[red]Error: {result['error']}[/red]")
        sys.exit(1)

    events = result.get("events", [])
    if not events:
        console.print("[yellow]No market-moving events detected.[/yellow]")
        return

    console.print(f"\n[green]Found {len(events)} events[/green] from {result.get('articles_fetched', '?')} articles in {result.get('duration_seconds', '?')}s\n")

    table = Table(title="Detected Events", box=box.ROUNDED, show_lines=True)
    table.add_column("ID", style="bold cyan", width=4)
    table.add_column("Event", style="bold", max_width=25)
    table.add_column("Cat.")
    table.add_column("Sev.")
    table.add_column("Tickers", style="cyan", max_width=20)
    table.add_column("Summary", max_width=45)

    for e in events:
        tickers = ", ".join(e.get("related_tickers", [])[:5])
        table.add_row(
            str(e["event_id"]),
            e["title"],
            e.get("category", ""),
            _severity_color(e.get("severity", "")),
            tickers or "[dim]none[/dim]",
            e.get("summary", "")[:100],
        )

    console.print(table)
    console.print("\n[dim]To analyze an event in depth:[/dim]  python -m app.cli.main deep <event_id>")
    console.print("[dim]To analyze all events at once:[/dim]  python -m app.cli.main analyze")


def cmd_deep(args):
    """Run deep two-source analysis on a scanned event."""
    if not ollama.check_available():
        console.print("[red]Error: Ollama is not running. Start it with 'ollama serve'[/red]")
        sys.exit(1)

    console.print(f"[bold]Running deep analysis on event #{args.event_id}...[/bold]")

    from app.analysis.pipeline import analyze_event_by_id
    result = analyze_event_by_id(args.event_id)

    if result.get("error"):
        console.print(f"[red]Error: {result['error']}[/red]")
        sys.exit(1)

    console.print(f"[green]Done in {result.get('duration_seconds', '?')}s[/green]\n")

    # Show causal chains
    data = result.get("analysis", {})
    if data.get("causal_chains"):
        tree = Tree(f"[bold]{result['event']['title']}[/bold]")
        for chain in data["causal_chains"]:
            confidence = chain.get("confidence", "")
            conf_color = "green" if confidence == "high" else "yellow" if confidence == "medium" else "red"
            tree.add(f"[{conf_color}]{chain.get('chain', '')}[/{conf_color}]  [dim]({confidence})[/dim]")
        console.print(tree)

    # Sector impacts
    if data.get("sectors"):
        console.print("\n[bold underline]Sector Impacts:[/bold underline]")
        for s in data["sectors"]:
            arrow = "↑" if s["direction"] == "bullish" else "↓" if s["direction"] == "bearish" else "~"
            color = "green" if s["direction"] == "bullish" else "red" if s["direction"] == "bearish" else "yellow"
            console.print(f"  [{color}]{arrow} {s['name']}[/{color}] — {s.get('reason', '')}")

    # Refined stock picks (from Phase 4)
    if data.get("top_picks"):
        console.print("\n[bold underline]Top Picks (fundamentals-refined):[/bold underline]")
        for p in data["top_picks"]:
            action = p.get("action", "")
            color = "green" if action in ("strong_buy", "buy") else "red" if action in ("sell", "strong_sell") else "yellow"
            console.print(f"  [{color}]{p.get('ticker', '')} — {action.upper()}[/{color}]")
            console.print(f"    {p.get('reason', '')}")
            if p.get("risk"):
                console.print(f"    [dim]Risk: {p['risk']}[/dim]")

    if data.get("avoid"):
        console.print("\n[bold underline]Avoid:[/bold underline]")
        for a in data["avoid"]:
            console.print(f"  [red]{a.get('ticker', '')}[/red] — {a.get('reason', '')}")

    # Show AV-sourced ticker data if no refined picks
    ticker_data = result.get("ticker_data", {})
    if not data.get("top_picks") and ticker_data:
        console.print("\n[bold underline]Tickers From News (Alpha Vantage):[/bold underline]")
        for ticker, td in list(ticker_data.items())[:8]:
            color = "green" if td["sentiment_label"] == "bullish" else "red" if td["sentiment_label"] == "bearish" else "yellow"
            console.print(f"  [{color}]{ticker}[/{color}] — {td['sentiment_label'].upper()} (score: {td['avg_sentiment']}, {td['mentions']} mentions)")


def cmd_analyze(args):
    """Run full analysis pipeline."""
    if not ollama.check_available():
        console.print("[red]Error: Ollama is not running. Start it with 'ollama serve'[/red]")
        sys.exit(1)

    console.print(Panel(f"[bold]Starting full market analysis...[/bold]\nAnalyzing top {args.max_events} events by severity.", box=box.ROUNDED))

    from app.analysis.pipeline import run_full_analysis
    result = run_full_analysis(max_events=args.max_events)

    if result.get("error"):
        console.print(f"[red]Error: {result['error']}[/red]")
        sys.exit(1)

    _print_report(result)


def cmd_report(args):
    """Show the latest report."""
    from app.db import database as db
    report = db.get_latest_report()
    if not report:
        console.print("[yellow]No reports yet. Run 'analyze' first.[/yellow]")
        return
    _print_report(report)


def cmd_events(args):
    """List recent events."""
    from app.db import database as db
    events = db.get_events(limit=args.limit)

    if not events:
        console.print("[yellow]No events yet. Run 'analyze' first.[/yellow]")
        return

    table = Table(title="Recent Market Events", box=box.ROUNDED, show_lines=True)
    table.add_column("ID", style="dim", width=4)
    table.add_column("Event", style="bold")
    table.add_column("Category")
    table.add_column("Severity")
    table.add_column("Sectors", width=30)
    table.add_column("Date", style="dim")

    for e in events:
        sectors = ", ".join(
            f"{s['sector']} {'↑' if s['direction'] == 'bullish' else '↓' if s['direction'] == 'bearish' else '~'}"
            for s in e.get("sector_impacts", [])[:4]
        )
        table.add_row(
            str(e["id"]),
            e["title"],
            e.get("category", ""),
            _severity_color(e.get("severity", "")),
            sectors,
            e.get("created_at", "")[:16],
        )

    console.print(table)
    console.print(f"[dim]Use 'chain <event_id>' to see causal chains for an event[/dim]")


def cmd_chain(args):
    """Show causal chain for an event."""
    from app.db import database as db
    event = db.get_event(args.event_id)

    if not event:
        console.print(f"[red]Event {args.event_id} not found[/red]")
        return

    console.print(Panel(f"[bold]{event['title']}[/bold]\n{event.get('summary', '')}", title="Event", box=box.ROUNDED))

    # Causal chains as a tree
    tree = Tree(f"[bold]{event['title']}[/bold]")
    for chain in event.get("causal_chains", []):
        confidence = chain.get("confidence", "")
        conf_color = "green" if confidence == "high" else "yellow" if confidence == "medium" else "red"
        tree.add(f"[{conf_color}]{chain.get('chain', '')}[/{conf_color}]  [{conf_color}]({confidence})[/{conf_color}]")

    console.print(tree)

    # Sector impacts
    if event.get("sector_impacts"):
        console.print("\n[bold]Sector Impacts:[/bold]")
        for s in event["sector_impacts"]:
            arrow = "↑" if s["direction"] == "bullish" else "↓" if s["direction"] == "bearish" else "~"
            color = "green" if s["direction"] == "bullish" else "red" if s["direction"] == "bearish" else "yellow"
            console.print(f"  [{color}]{arrow} {s['sector']}[/{color}] — {s.get('reason', '')}")

    # Stock picks
    if event.get("stock_picks"):
        console.print("\n[bold]Stock Picks:[/bold]")
        for p in event["stock_picks"]:
            color = "green" if p["direction"] in ("bullish", "strong_buy", "buy") else "red"
            console.print(f"  [{color}]{p['ticker']}[/{color}] ({p['direction']}) — {p.get('reason', '')}")


def cmd_sectors(args):
    """Show sector outlook from latest report."""
    from app.db import database as db
    report = db.get_latest_report()

    if not report:
        console.print("[yellow]No reports yet. Run 'analyze' first.[/yellow]")
        return

    console.print(f"\n[bold]Overall Sentiment: {_sentiment_display(report.get('overall_sentiment', ''))}[/bold]\n")

    table = Table(title="Sector Outlook", box=box.ROUNDED)
    table.add_column("Sector", style="bold")
    table.add_column("Signal", justify="center")
    table.add_column("Reason")

    for s in report.get("sector_outlook", []):
        signal = s.get("signal", "")
        color = "green" if signal == "bullish" else "red" if signal == "bearish" else "yellow"
        table.add_row(
            s.get("sector", ""),
            f"[{color}]{signal.upper()}[/{color}]",
            s.get("reason", ""),
        )

    console.print(table)



def _print_report(report: dict):
    """Pretty-print a synthesis report."""
    sentiment = report.get("overall_sentiment", "unknown")
    console.print(Panel(
        f"[bold]Overall Sentiment: {_sentiment_display(sentiment)}[/bold]\n"
        f"Confidence: {report.get('confidence', 'unknown')}\n"
        f"Events analyzed: {report.get('events_analyzed', '?')}",
        title="Market Analysis Report",
        box=box.DOUBLE,
    ))

    # Key themes
    themes = report.get("key_themes", [])
    if themes:
        console.print("\n[bold underline]Key Themes:[/bold underline]")
        for t in themes:
            impact_color = "red" if t.get("impact") == "high" else "yellow" if t.get("impact") == "medium" else "dim"
            console.print(f"  [{impact_color}][{t.get('impact', '?').upper()}][/{impact_color}] {t.get('theme', '')} — {t.get('description', '')}")

    # Sector outlook
    sectors = report.get("sector_outlook", [])
    if sectors:
        console.print("\n[bold underline]Sector Outlook:[/bold underline]")
        table = Table(box=box.SIMPLE)
        table.add_column("Sector", style="bold")
        table.add_column("Signal", justify="center")
        table.add_column("Reason")
        for s in sectors:
            signal = s.get("signal", "")
            color = "green" if signal == "bullish" else "red" if signal == "bearish" else "yellow"
            table.add_row(s.get("sector", ""), f"[{color}]{signal.upper()}[/{color}]", s.get("reason", ""))
        console.print(table)

    # Reinforcing signals
    reinforcing = report.get("reinforcing_signals", [])
    if reinforcing:
        console.print("\n[bold underline]Reinforcing Signals:[/bold underline]")
        for r in reinforcing:
            console.print(f"  [green]+[/green] {r}")

    # Conflicting signals
    conflicting = report.get("conflicting_signals", [])
    if conflicting:
        console.print("\n[bold underline]Conflicting Signals:[/bold underline]")
        for c in conflicting:
            console.print(f"  [yellow]![/yellow] {c}")

    # Top picks
    picks = report.get("top_picks", [])
    if picks:
        console.print("\n[bold underline]Top Stock Picks:[/bold underline]")
        for p in picks:
            action = p.get("action", "")
            color = "green" if action in ("strong_buy", "buy") else "red" if action in ("sell", "strong_sell") else "yellow"
            console.print(f"  [{color}]{p.get('ticker', '')} — {action.upper()}[/{color}]")
            console.print(f"    {p.get('reason') or p.get('thesis', '')}")
            if p.get("risk"):
                console.print(f"    [dim]Risk: {p['risk']}[/dim]")

    # Watchlist
    watchlist = report.get("watchlist", [])
    if watchlist:
        console.print("\n[bold underline]Watchlist:[/bold underline]")
        for w in watchlist:
            console.print(f"  [cyan]>[/cyan] {w}")


def _sentiment_display(sentiment: str) -> str:
    """Color-code sentiment."""
    colors = {
        "strongly_bullish": "bold green",
        "bullish": "green",
        "cautious_bullish": "green",
        "neutral": "yellow",
        "cautious_bearish": "red",
        "bearish": "red",
        "strongly_bearish": "bold red",
    }
    color = colors.get(sentiment, "white")
    return f"[{color}]{sentiment.upper().replace('_', ' ')}[/{color}]"


def _severity_color(severity: str) -> str:
    """Color-code severity."""
    colors = {"high": "red", "medium": "yellow", "low": "dim"}
    color = colors.get(severity, "white")
    return f"[{color}]{severity}[/{color}]"


def main():
    parser = argparse.ArgumentParser(description="Market Analyst CLI")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # scan (discovery)
    subparsers.add_parser("scan", help="Scan news and list detected events (fast)")

    # deep (analyze a scanned event)
    deep_parser = subparsers.add_parser("deep", help="Deep-analyze a scanned event")
    deep_parser.add_argument("event_id", type=int, help="Event ID from scan")

    # analyze (full pipeline)
    analyze_parser = subparsers.add_parser("analyze", help="Run full market analysis (scan + analyze top events)")
    analyze_parser.add_argument("--max-events", type=int, default=5, help="Max events to deeply analyze (default: 5)")

    # report
    subparsers.add_parser("report", help="Show latest analysis report")

    # events
    events_parser = subparsers.add_parser("events", help="List recent events")
    events_parser.add_argument("--limit", type=int, default=20, help="Max events to show")

    # chain
    chain_parser = subparsers.add_parser("chain", help="Show causal chain for an event")
    chain_parser.add_argument("event_id", type=int, help="Event ID")

    # sectors
    subparsers.add_parser("sectors", help="Show sector outlook")

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    commands = {
        "scan": cmd_scan,
        "deep": cmd_deep,
        "analyze": cmd_analyze,
        "report": cmd_report,
        "events": cmd_events,
        "chain": cmd_chain,
        "sectors": cmd_sectors,
    }

    if args.command in commands:
        commands[args.command](args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
