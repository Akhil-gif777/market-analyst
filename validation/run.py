#!/usr/bin/env python3
"""
Validation harness for market analysis LLM approach.

Runs historical test cases through one or more Ollama models,
scores the predictions against known outcomes, and produces
a comparative scorecard.

Usage:
    python -m validation.run                          # Run all cases on all models
    python -m validation.run --model deepseek-r1:32b  # Run on a specific model
    python -m validation.run --case svb               # Run a specific case (substring match)
    python -m validation.run --verbose                 # Show detailed per-case output
"""

import argparse
import json
import sys
from pathlib import Path

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich import box

from validation.cases import HISTORICAL_CASES
from validation.prompts import format_prompt
from validation.llm import check_ollama_available, list_models, run_analysis
from validation.scorer import score_analysis

console = Console()

DEFAULT_MODELS = ["deepseek-r1:32b", "qwen2.5:72b"]
RESULTS_DIR = Path("validation/results")


def run_single_case(model: str, case: dict, verbose: bool = False) -> dict:
    """Run a single test case through a model and score it."""
    console.print(f"\n  [dim]Analyzing:[/dim] {case['name']} ({case['date']})")

    prompt = format_prompt(case)
    result = run_analysis(model, prompt)

    if result["parse_error"]:
        console.print(f"  [red]Parse error:[/red] {result['parse_error']}")
        if verbose:
            console.print(f"  [dim]Raw response (first 500 chars):[/dim]")
            console.print(f"  {result['raw'][:500]}")
        return {
            "case_id": case["id"],
            "case_name": case["name"],
            "model": model,
            "success": False,
            "error": result["parse_error"],
            "duration_seconds": result["duration_seconds"],
            "scores": None,
        }

    scores = score_analysis(result["response"], case["known_outcomes"])

    console.print(
        f"  [green]Done[/green] in {result['duration_seconds']}s — "
        f"Overall: [bold]{scores['overall_score']}%[/bold]  "
        f"(Sectors: {scores['sectors']['score']}% | "
        f"Stocks: {scores['stocks']['score']}% | "
        f"Chains: {scores['chains']['score']}%)"
    )

    if verbose:
        _print_verbose(result["response"], scores)

    return {
        "case_id": case["id"],
        "case_name": case["name"],
        "model": model,
        "success": True,
        "duration_seconds": result["duration_seconds"],
        "scores": scores,
        "prediction": result["response"],
        "raw": result["raw"],
    }


def _print_verbose(prediction: dict, scores: dict):
    """Print detailed scoring breakdown."""
    console.print("\n  [bold underline]Sector Details:[/bold underline]")
    for line in scores["sectors"]["details"]:
        color = "green" if "CORRECT" in line else "red" if "WRONG" in line else "yellow" if "MISSED" in line else "dim"
        console.print(f"  [{color}]{line}[/{color}]")

    console.print("\n  [bold underline]Stock Details:[/bold underline]")
    for line in scores["stocks"]["details"]:
        color = "green" if "CORRECT" in line else "red" if "WRONG" in line else "yellow" if "MISSED" in line else "cyan"
        console.print(f"  [{color}]{line}[/{color}]")

    console.print("\n  [bold underline]Causal Chain Details:[/bold underline]")
    for line in scores["chains"]["details"]:
        console.print(f"  [dim]{line}[/dim]")

    if prediction.get("causal_chains"):
        console.print("\n  [bold underline]Predicted Chains:[/bold underline]")
        for chain in prediction["causal_chains"][:6]:
            console.print(f"  [cyan]→ {chain}[/cyan]")


def print_summary_table(all_results: list[dict]):
    """Print a comparative summary table across all models and cases."""
    console.print("\n")

    # Group by model
    models = {}
    for r in all_results:
        models.setdefault(r["model"], []).append(r)

    table = Table(
        title="Validation Scorecard",
        box=box.ROUNDED,
        show_lines=True,
    )
    table.add_column("Test Case", style="bold")

    for model_name in models:
        short_name = model_name.split(":")[0]
        table.add_column(f"{short_name}\nOverall", justify="center")
        table.add_column(f"{short_name}\nSectors", justify="center")
        table.add_column(f"{short_name}\nStocks", justify="center")
        table.add_column(f"{short_name}\nChains", justify="center")
        table.add_column(f"{short_name}\nTime", justify="center")

    # Build rows by case
    case_ids = list(dict.fromkeys(r["case_id"] for r in all_results))
    for case_id in case_ids:
        row = []
        case_name = next(r["case_name"] for r in all_results if r["case_id"] == case_id)
        row.append(case_name)

        for model_name in models:
            result = next(
                (r for r in all_results if r["case_id"] == case_id and r["model"] == model_name),
                None,
            )
            if result is None or not result["success"]:
                row.extend(["ERR", "-", "-", "-", "-"])
            else:
                s = result["scores"]
                row.append(_color_score(s["overall_score"]))
                row.append(_color_score(s["sectors"]["score"]))
                row.append(_color_score(s["stocks"]["score"]))
                row.append(_color_score(s["chains"]["score"]))
                row.append(f"{result['duration_seconds']}s")

        table.add_row(*row)

    # Add average row
    avg_row = ["[bold]AVERAGE[/bold]"]
    for model_name in models:
        model_results = [r for r in models[model_name] if r["success"] and r["scores"]]
        if model_results:
            avg_overall = sum(r["scores"]["overall_score"] for r in model_results) / len(model_results)
            avg_sectors = sum(r["scores"]["sectors"]["score"] for r in model_results) / len(model_results)
            avg_stocks = sum(r["scores"]["stocks"]["score"] for r in model_results) / len(model_results)
            avg_chains = sum(r["scores"]["chains"]["score"] for r in model_results) / len(model_results)
            avg_time = sum(r["duration_seconds"] for r in model_results) / len(model_results)
            avg_row.append(_color_score(round(avg_overall, 1)))
            avg_row.append(_color_score(round(avg_sectors, 1)))
            avg_row.append(_color_score(round(avg_stocks, 1)))
            avg_row.append(_color_score(round(avg_chains, 1)))
            avg_row.append(f"{avg_time:.0f}s")
        else:
            avg_row.extend(["-", "-", "-", "-", "-"])

    table.add_row(*avg_row)
    console.print(table)


def _color_score(score: float) -> str:
    """Color a score based on quality thresholds."""
    if score >= 70:
        return f"[bold green]{score}%[/bold green]"
    elif score >= 45:
        return f"[yellow]{score}%[/yellow]"
    else:
        return f"[red]{score}%[/red]"


def save_results(all_results: list[dict]):
    """Save raw results to JSON for later analysis."""
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    # Strip raw LLM text to keep file size reasonable
    clean = []
    for r in all_results:
        entry = {k: v for k, v in r.items() if k != "raw"}
        clean.append(entry)

    output_path = RESULTS_DIR / "validation_results.json"
    with open(output_path, "w") as f:
        json.dump(clean, f, indent=2)
    console.print(f"\n[dim]Results saved to {output_path}[/dim]")


def main():
    parser = argparse.ArgumentParser(description="Market Analysis Validation Harness")
    parser.add_argument(
        "--model",
        nargs="+",
        help="Ollama model(s) to test (default: deepseek-r1:32b qwen2.5:72b)",
    )
    parser.add_argument(
        "--case",
        help="Run only cases matching this substring",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show detailed per-case scoring breakdown",
    )
    args = parser.parse_args()

    # Check Ollama
    if not check_ollama_available():
        console.print("[red]Error: Ollama is not running. Start it with 'ollama serve'[/red]")
        sys.exit(1)

    available_models = list_models()
    console.print(f"[dim]Ollama models available: {', '.join(available_models)}[/dim]")

    # Determine models to test
    models_to_test = args.model or DEFAULT_MODELS
    for m in models_to_test:
        if m not in available_models:
            console.print(f"[red]Error: Model '{m}' not found. Available: {', '.join(available_models)}[/red]")
            sys.exit(1)

    # Filter cases if requested
    cases = HISTORICAL_CASES
    if args.case:
        cases = [c for c in cases if args.case.lower() in c["id"].lower() or args.case.lower() in c["name"].lower()]
        if not cases:
            console.print(f"[red]No cases matching '{args.case}'[/red]")
            sys.exit(1)

    console.print(
        Panel(
            f"[bold]Market Analysis Validation Harness[/bold]\n\n"
            f"Models: {', '.join(models_to_test)}\n"
            f"Cases:  {len(cases)} historical events\n"
            f"Verbose: {'yes' if args.verbose else 'no'}",
            title="Configuration",
            box=box.ROUNDED,
        )
    )

    all_results = []
    for model in models_to_test:
        console.print(f"\n[bold blue]{'='*60}[/bold blue]")
        console.print(f"[bold blue]Model: {model}[/bold blue]")
        console.print(f"[bold blue]{'='*60}[/bold blue]")

        for case in cases:
            result = run_single_case(model, case, verbose=args.verbose)
            all_results.append(result)

    print_summary_table(all_results)
    save_results(all_results)

    # Final verdict
    console.print("\n")
    successful = [r for r in all_results if r["success"] and r["scores"]]
    if successful:
        avg = sum(r["scores"]["overall_score"] for r in successful) / len(successful)
        if avg >= 60:
            console.print(
                Panel(
                    f"[bold green]Average score: {avg:.1f}% — Approach is viable![/bold green]\n"
                    "The LLM demonstrates useful market reasoning capability.\n"
                    "Proceed to build the full pipeline.",
                    title="VERDICT",
                    box=box.DOUBLE,
                )
            )
        elif avg >= 40:
            console.print(
                Panel(
                    f"[bold yellow]Average score: {avg:.1f}% — Promising but needs work[/bold yellow]\n"
                    "The LLM shows partial capability. Consider:\n"
                    "- Better prompting (more context, few-shot examples)\n"
                    "- Supplementing with quantitative data\n"
                    "- Using a larger model",
                    title="VERDICT",
                    box=box.DOUBLE,
                )
            )
        else:
            console.print(
                Panel(
                    f"[bold red]Average score: {avg:.1f}% — Approach needs rethinking[/bold red]\n"
                    "The LLM struggles with market analysis at this level.\n"
                    "Consider RAG, fine-tuning, or hybrid quant+LLM approach.",
                    title="VERDICT",
                    box=box.DOUBLE,
                )
            )


if __name__ == "__main__":
    main()
