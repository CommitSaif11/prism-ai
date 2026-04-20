"""
pipeline.py — Pipeline Orchestration + Confidence (Tasks 8, 9, 10)
====================================================================
Orchestrates the full hybrid pipeline:
  Rule Parser → Gap Detection → AI Assist → Validation → Safe Merge
  → AI Enrichment → Final JSON with Provenance + Confidence

Performance rules (Task 8):
  - NO AI calls in loops
  - NO AI per combination
  - ONLY: gap-based AI assist (one call) + global enrichment (one call)

Confidence system (Task 9):
  - Severity-based deductions, not just existence-based

Final output (Task 10):
  - Structured JSON with metadata, bands, combos, validation,
    ai_enrichment, and ai_notes
"""

from __future__ import annotations
import copy
import logging
import time
from typing import Any, Dict, List

from .gap_detector import detect_gaps, SEVERITY
from .ai_assist import ai_fill_gaps
from .validator import validate_ai_output
from .merger import safe_merge
from .enrichment import ai_enrich_global

log = logging.getLogger(__name__)


def run_hybrid_pipeline(raw_text: str, parsed_json: Dict[str, Any]) -> Dict[str, Any]:
    """
    Main entry point for the hybrid AI-assisted pipeline.
    Mutates parsed_json IN-PLACE with gap fills and enrichment.

    Pipeline:
      1. Snapshot counts (for before/after verification)
      2. Detect gaps
      3. AI assist (ONE batched call, only if gaps exist)
      4. Validate AI output
      5. Safe merge (fill-only)
      6. Compute confidence
      7. AI enrichment (ONE global call)
      8. Attach provenance + confidence to output

    Args:
        raw_text: original UE capability text
        parsed_json: output from sequential_extractor.extract_all()

    Returns:
        parsed_json with ai_notes and ai_enrichment attached
    """
    start = time.time()

    # ── Step 0: Deterministic Decoder Hook ────────────────────────────────
    start_step = time.perf_counter()
    # Decode bitmap NR bandwidths strictly before any GAP detection or AI runs
    from .bitmap_decoder import fill_nr_bandwidths
    parsed_json = fill_nr_bandwidths(parsed_json, raw_text)
    print(f"[TIME] Bitmap Extraction + Decode: {time.perf_counter() - start_step:.4f}s")

    # ── Step 1: Snapshot pre-pipeline counts ───────────────────────────────
    pre_counts = _snapshot_counts(parsed_json)
    log.info(f"[Pipeline] Pre-pipeline: {pre_counts}")

    # ── Step 2: Gap detection ─────────────────────────────────────────────
    start_step = time.perf_counter()
    gap_report = detect_gaps(parsed_json)
    gaps = gap_report["gaps"]
    print(f"[TIME] Gap Detection: {time.perf_counter() - start_step:.4f}s")
    log.info(f"[Pipeline] Detected {gap_report['gap_count']} gap(s) "
             f"(critical: {gap_report['has_critical']})")

    # Track pipeline state
    ai_called = False
    ai_accepted = 0
    ai_rejected = 0
    filled_fields: List[str] = []
    warnings: List[str] = []
    rejection_reasons: List[str] = []

    # ── Step 3: AI Assist (only if gaps exist) ────────────────────────────
    if gaps:
        start_step = time.perf_counter()
        ai_result = ai_fill_gaps(raw_text, gaps)
        print(f"[TIME] AI Assist: {time.perf_counter() - start_step:.4f}s")
        ai_called = ai_result["ai_called"]

        if ai_called and ai_result["fills"]:
            # ── Step 4: Validate AI output ─────────────────────────────────
            start_step = time.perf_counter()
            validated_fills, rejections = validate_ai_output(ai_result["fills"], gaps)
            rejection_reasons = rejections
            ai_rejected = len(rejections)

            if validated_fills:
                # ── Step 5: Safe merge ─────────────────────────────────────
                parsed_json, filled_fields = safe_merge(parsed_json, validated_fills)
                ai_accepted = len(filled_fields)
                print(f"[TIME] Validation + Merge: {time.perf_counter() - start_step:.4f}s")
                log.info(f"[Pipeline] Merged {ai_accepted} AI fill(s)")
            else:
                warnings.append("AI returned data but none passed validation")
        elif ai_called:
            warnings.append("AI call made but returned no usable fills")
    else:
        log.info("[Pipeline] No gaps detected — pure rule-based extraction")

    # ── Step 6: Compute confidence ────────────────────────────────────────
    confidence = compute_confidence(
        gaps=gaps,
        ai_called=ai_called,
        ai_accepted=ai_accepted,
        ai_rejected=ai_rejected,
    )

    # ── Step 7: Post-pipeline count verification ──────────────────────────
    post_counts = _snapshot_counts(parsed_json)
    verification = _verify_counts(pre_counts, post_counts)
    if verification["issues"]:
        warnings.extend(verification["issues"])
        log.warning(f"[Pipeline] Count verification issues: {verification['issues']}")

    # ── Step 8: AI Enrichment (ONE global call) ───────────────────────────
    start_step = time.perf_counter()
    enrichment = ai_enrich_global(parsed_json)
    print(f"[TIME] AI Enrichment: {time.perf_counter() - start_step:.4f}s")

    # ── Step 9: Attach provenance + enrichment to output ──────────────────
    elapsed = round(time.time() - start, 3)

    parsed_json["ai_notes"] = {
        "filled_fields": filled_fields,
        "confidence": confidence,
        "gaps_detected": gap_report["gap_count"],
        "gaps_critical": gap_report["has_critical"],
        "ai_called": ai_called,
        "ai_fills_accepted": ai_accepted,
        "ai_fills_rejected": ai_rejected,
        "rejection_reasons": rejection_reasons,
        "warnings": warnings,
        "pipeline_elapsed_seconds": elapsed,
        "verification": verification,
    }

    parsed_json["ai_enrichment"] = enrichment

    log.info(f"[Pipeline] Complete in {elapsed}s — confidence: {confidence}")

    return parsed_json


def compute_confidence(
    gaps: list,
    ai_called: bool,
    ai_accepted: int,
    ai_rejected: int,
) -> float:
    """
    Compute a severity-based confidence score.

    Task 9 — Severity-weighted, not just existence-based.

    Deductions:
      - Per gap: -0.1 (minor), -0.15 (major), -0.3 (critical)
      - AI called: -0.05
      - AI rejected fills: -0.2 per rejection
      - Clamped to [0.0, 1.0]
    """
    confidence = 1.0

    # Per-gap severity deductions
    for gap in gaps:
        severity = gap.get("severity", "minor")
        confidence -= SEVERITY.get(severity, 0.05)

    # AI usage deduction
    if ai_called:
        confidence -= 0.05

    # AI rejection penalty (AI tried but was wrong = lower trust)
    confidence -= 0.2 * ai_rejected

    # Bonus: AI successfully filled gaps → partial recovery
    confidence += 0.05 * ai_accepted

    return round(max(0.0, min(1.0, confidence)), 3)


def _snapshot_counts(parsed_json: Dict) -> Dict[str, int]:
    """Take a count snapshot for before/after verification."""
    return {
        "lteBands": len(parsed_json.get("lteBands", [])),
        "nrBands": len(parsed_json.get("nrBands", [])),
        "lteca": len(parsed_json.get("lteca", [])),
        "nrca": len(parsed_json.get("nrca", [])),
        "mrdc": len(parsed_json.get("mrdc", [])),
    }


def _verify_counts(pre: Dict[str, int], post: Dict[str, int]) -> Dict[str, Any]:
    """
    Verify that no data was lost during the pipeline.

    Critical rule: counts must stay same or increase, NEVER decrease.
    """
    issues = []
    for key in pre:
        if post.get(key, 0) < pre[key]:
            issues.append(
                f"DATA LOSS: {key} decreased from {pre[key]} to {post.get(key, 0)}"
            )

    return {
        "pre_counts": pre,
        "post_counts": post,
        "issues": issues,
        "passed": len(issues) == 0,
    }
