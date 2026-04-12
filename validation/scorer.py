"""
Scoring engine that compares LLM predictions against known historical outcomes.
"""


def score_analysis(prediction: dict, known_outcomes: dict) -> dict:
    """
    Score an LLM analysis against known outcomes.

    Returns a detailed scorecard with:
        - sector_score: how well it identified affected sectors and their direction
        - stock_score: how well it picked the right stocks
        - chain_score: basic assessment of causal chain quality
        - overall_score: weighted composite
    """
    sector_result = _score_sectors(
        prediction.get("sectors", []),
        known_outcomes.get("sectors", {}),
    )
    stock_result = _score_stocks(
        prediction.get("stocks", {}),
        known_outcomes.get("stocks", {}),
    )
    chain_result = _score_chains(
        prediction.get("causal_chains", []),
        known_outcomes.get("causal_chains", []),
    )

    # Weighted overall: sectors 35%, stocks 40%, chains 25%
    overall = (
        sector_result["score"] * 0.35
        + stock_result["score"] * 0.40
        + chain_result["score"] * 0.25
    )

    return {
        "sectors": sector_result,
        "stocks": stock_result,
        "chains": chain_result,
        "overall_score": round(overall, 2),
    }


def _score_sectors(predicted: list[dict], known: dict) -> dict:
    """
    Score sector predictions.

    Checks:
    - Did the LLM identify the right sectors? (recall)
    - Are the directions correct? (accuracy)
    """
    known_sectors = {}
    for name, info in known.items():
        known_sectors[name.lower()] = info["direction"]

    matched = 0
    direction_correct = 0
    direction_wrong = 0
    details = []

    predicted_names = set()
    for pred in predicted:
        pred_name = pred.get("name", "").lower().replace(" ", "_")
        pred_dir = pred.get("direction", "").lower()
        predicted_names.add(pred_name)

        # Try to match against known sectors (fuzzy: check if any known key is contained in predicted or vice versa)
        match_found = False
        for known_name, known_dir in known_sectors.items():
            if _sector_match(pred_name, known_name):
                matched += 1
                match_found = True
                if pred_dir == known_dir or known_dir == "mixed":
                    direction_correct += 1
                    details.append(
                        f"  [CORRECT] {pred_name} → {pred_dir} (expected: {known_dir})"
                    )
                else:
                    direction_wrong += 1
                    details.append(
                        f"  [WRONG]   {pred_name} → {pred_dir} (expected: {known_dir})"
                    )
                break

        if not match_found:
            details.append(f"  [EXTRA]   {pred_name} → {pred_dir} (not in known outcomes)")

    # Check for missed sectors
    for known_name in known_sectors:
        found = any(_sector_match(p, known_name) for p in predicted_names)
        if not found:
            details.append(f"  [MISSED]  {known_name} (not predicted)")

    total_known = len(known_sectors)
    recall = matched / total_known if total_known > 0 else 0
    precision = direction_correct / matched if matched > 0 else 0
    score = (recall * 0.5 + precision * 0.5) * 100

    return {
        "score": round(score, 1),
        "matched": matched,
        "direction_correct": direction_correct,
        "direction_wrong": direction_wrong,
        "total_known": total_known,
        "total_predicted": len(predicted),
        "recall": round(recall * 100, 1),
        "direction_accuracy": round(precision * 100, 1),
        "details": details,
    }


def _score_stocks(predicted: dict, known: dict) -> dict:
    """
    Score stock predictions.

    Checks:
    - Did the LLM pick stocks that were in the known bullish/bearish lists?
    - Did it get the direction right? (bullish stock in bullish list, etc.)
    """
    known_bullish = {s["ticker"].upper() for s in known.get("bullish", [])}
    known_bearish = {s["ticker"].upper() for s in known.get("bearish", [])}
    all_known = known_bullish | known_bearish

    pred_bullish = {s.get("ticker", "").upper() for s in predicted.get("bullish", [])}
    pred_bearish = {s.get("ticker", "").upper() for s in predicted.get("bearish", [])}
    all_predicted = pred_bullish | pred_bearish

    # Correct picks: predicted direction matches known direction
    correct_bullish = pred_bullish & known_bullish
    correct_bearish = pred_bearish & known_bearish
    correct = correct_bullish | correct_bearish

    # Wrong direction: predicted bullish but was bearish, or vice versa
    wrong_dir_bull = pred_bullish & known_bearish  # predicted bullish, actually bearish
    wrong_dir_bear = pred_bearish & known_bullish  # predicted bearish, actually bullish
    wrong_direction = wrong_dir_bull | wrong_dir_bear

    # Overlap: any prediction that matches a known stock regardless of direction
    overlap = all_predicted & all_known

    details = []
    for ticker in sorted(correct_bullish):
        details.append(f"  [CORRECT] {ticker} bullish ✓")
    for ticker in sorted(correct_bearish):
        details.append(f"  [CORRECT] {ticker} bearish ✓")
    for ticker in sorted(wrong_dir_bull):
        details.append(f"  [WRONG DIR] {ticker} predicted bullish, was bearish")
    for ticker in sorted(wrong_dir_bear):
        details.append(f"  [WRONG DIR] {ticker} predicted bearish, was bullish")

    missed_bullish = known_bullish - pred_bullish - pred_bearish
    missed_bearish = known_bearish - pred_bearish - pred_bullish
    for ticker in sorted(missed_bullish):
        details.append(f"  [MISSED] {ticker} (known bullish)")
    for ticker in sorted(missed_bearish):
        details.append(f"  [MISSED] {ticker} (known bearish)")

    novel = all_predicted - all_known
    for ticker in sorted(novel):
        direction = "bullish" if ticker in pred_bullish else "bearish"
        details.append(f"  [NOVEL] {ticker} {direction} (not in known list — needs manual review)")

    # Score: correct picks weighted heavily, wrong direction penalized
    total_known = len(all_known)
    if total_known == 0:
        score = 0.0
    else:
        recall = len(correct) / total_known
        penalty = len(wrong_direction) / max(len(all_predicted), 1)
        score = max(0, (recall - penalty * 0.5)) * 100

    return {
        "score": round(score, 1),
        "correct": len(correct),
        "wrong_direction": len(wrong_direction),
        "total_known": total_known,
        "total_predicted": len(all_predicted),
        "novel_picks": len(novel),
        "details": details,
    }


def _score_chains(predicted: list[str], known: list[str]) -> dict:
    """
    Score causal chains using keyword overlap as a heuristic.

    Causal chains are harder to score automatically. We use a keyword-based
    approach: extract key concepts from known chains and check how many
    appear in predicted chains.
    """
    # Extract key concepts from known chains
    known_concepts = set()
    for chain in known:
        known_concepts.update(_extract_concepts(chain))

    # Check how many known concepts appear in predicted chains
    predicted_text = " ".join(predicted).lower()
    found_concepts = {c for c in known_concepts if c in predicted_text}

    coverage = len(found_concepts) / len(known_concepts) if known_concepts else 0
    score = coverage * 100

    missed = known_concepts - found_concepts

    details = [
        f"  Known concepts: {len(known_concepts)}",
        f"  Found in predictions: {len(found_concepts)}",
        f"  Coverage: {coverage:.0%}",
    ]
    if missed:
        details.append(f"  Missed concepts: {', '.join(sorted(missed)[:10])}")

    return {
        "score": round(score, 1),
        "concept_coverage": round(coverage * 100, 1),
        "known_concepts": len(known_concepts),
        "found_concepts": len(found_concepts),
        "num_chains_predicted": len(predicted),
        "details": details,
    }


def _sector_match(predicted: str, known: str) -> bool:
    """Fuzzy match sector names — handles naming variations."""
    p = predicted.lower().replace("_", " ").replace("-", " ")
    k = known.lower().replace("_", " ").replace("-", " ")

    # Exact match
    if p == k:
        return True

    # One contains the other
    if k in p or p in k:
        return True

    # Key word overlap (at least one significant word matches)
    p_words = set(p.split()) - {"and", "the", "of", "in"}
    k_words = set(k.split()) - {"and", "the", "of", "in"}
    if p_words & k_words:
        return True

    return False


def _extract_concepts(chain: str) -> set[str]:
    """Extract key financial concepts from a causal chain string."""
    concepts = set()
    # Look for key market terms in the chain
    keywords = [
        "oil", "gas", "energy", "defense", "grain", "wheat", "corn",
        "sanctions", "inflation", "rate", "hike", "cut", "fed",
        "bank", "deposit", "bond", "yield", "mortgage", "housing",
        "supply chain", "shipping", "semiconductor", "chip",
        "ai", "gpu", "cloud", "tech", "growth", "crypto",
        "dollar", "gold", "flight to safety", "risk-off",
        "airline", "fuel", "consumer", "retail", "luxury",
        "cybersecurity", "fertilizer", "agriculture",
        "lockdown", "factory", "port", "congestion",
        "margin", "valuation", "discount rate",
    ]
    chain_lower = chain.lower()
    for kw in keywords:
        if kw in chain_lower:
            concepts.add(kw)
    return concepts
