"""
enrichment.py — Global AI Enrichment (Task 7)
===============================================
After parsing, gap-filling, and merging — make ONE final AI call
to produce a global summary, confidence assessment, and validation status.

This is additive data only. It never modifies parser output.
"""

from __future__ import annotations
import json
import logging
import sys
import os
from typing import Any, Dict, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ai_processor import _call_ai, _extract_json_block

log = logging.getLogger(__name__)


_ENRICHMENT_SYSTEM_PROMPT = """You are a 3GPP UE capability analysis expert.
You will receive a summary of parsed UE capability data that has been processed through
a hybrid extraction pipeline (rule-based parser + AI-assisted gap filling).

Return a SINGLE valid JSON object with EXACTLY these fields:
{
  "summary": "<2-3 sentence technical summary of what this UE supports>",
  "confidence": <float 0.0 to 1.0>,
  "validation_status": "<VALID | PARTIAL | INVALID>",
  "issues": ["<list of any data quality issues or anomalies>"],
  "spec_refs": ["<list of relevant 3GPP spec references>"]
}

Rules:
- Return ONLY the JSON object. No markdown, no explanation.
- confidence: 0.9+ means complete and consistent. Below 0.5 means critical issues.
- validation_status: VALID = no issues, PARTIAL = minor gaps, INVALID = critical problems.
- Base analysis on 3GPP TS 36.306, TS 38.306, TS 36.331, TS 38.331, TS 37.340."""


def ai_enrich_global(parsed_json: Dict[str, Any]) -> Dict[str, Any]:
    """
    Make ONE global AI enrichment call on the complete parsed result.
    Returns the ai_enrichment block to be attached to the output.

    This function NEVER modifies parsed data — it only produces metadata.
    """
    payload = _build_enrichment_payload(parsed_json)

    log.info("[Enrichment] Making ONE global AI enrichment call")
    raw_response = _call_ai(_ENRICHMENT_SYSTEM_PROMPT, payload, max_tokens=500, temperature=0.2)

    ai_data = _extract_json_block(raw_response) if raw_response else None

    if not ai_data:
        log.warning("[Enrichment] AI enrichment returned no valid data, using defaults")
        return _default_enrichment()

    # Ensure all required fields exist with safe defaults
    enrichment = {
        "summary":           ai_data.get("summary", "AI enrichment completed."),
        "confidence":        _clamp_float(ai_data.get("confidence"), 0.0, 1.0),
        "validation_status": ai_data.get("validation_status", "UNKNOWN"),
        "issues":            ai_data.get("issues", []),
        "spec_refs":         ai_data.get("spec_refs", []),
    }

    # Validate validation_status
    if enrichment["validation_status"] not in ("VALID", "PARTIAL", "INVALID"):
        enrichment["validation_status"] = "UNKNOWN"

    return enrichment


def _build_enrichment_payload(parsed_json: Dict) -> str:
    """
    Build a compact summary for the AI enrichment call.
    Sends counts + samples — NOT the entire JSON.
    """
    lte_bands = parsed_json.get("lteBands", [])
    nr_bands = parsed_json.get("nrBands", [])
    lteca = parsed_json.get("lteca", [])
    nrca = parsed_json.get("nrca", [])
    mrdc = parsed_json.get("mrdc", [])

    summary = {
        "counts": {
            "lte_bands": len(lte_bands),
            "nr_bands": len(nr_bands),
            "lte_ca": len(lteca),
            "nr_ca": len(nrca),
            "mrdc": len(mrdc),
        },
        "metadata": parsed_json.get("metadata", {}),
        "lte_bands_sample": lte_bands[:5],
        "nr_bands_sample": nr_bands[:5],
        "lteca_sample": lteca[:3],
        "nrca_sample": nrca[:3],
        "mrdc_sample": mrdc[:3],
        # Include AI assist provenance if present
        "ai_notes": parsed_json.get("ai_notes", {}),
    }

    return json.dumps(summary, indent=2, default=str)[:3000]


def _default_enrichment() -> Dict[str, Any]:
    """Safe defaults when AI is unavailable."""
    return {
        "summary": "AI enrichment unavailable. Parser data is authoritative.",
        "confidence": None,
        "validation_status": "UNKNOWN",
        "issues": [],
        "spec_refs": [],
    }


def _clamp_float(value: Any, lo: float, hi: float) -> Optional[float]:
    """Clamp a value to [lo, hi] or return None if not a number."""
    if value is None:
        return None
    try:
        v = float(value)
        return max(lo, min(hi, v))
    except (ValueError, TypeError):
        return None
