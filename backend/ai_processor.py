"""
ai_processor.py — Samsung PRISM AI Intelligence Layer
======================================================
Stage 3 in the pipeline: Parser → Formatter → [AI PROCESSOR] → Store

Rules:
  - Parser output is TRUTH, AI is additive (explain + validate)
  - ONE AI call for whole dataset at upload time (fast, consistent)
  - Per-combo enrichment is a FALLBACK — only if data is missing
  - Results are cached in the enriched JSON — never re-enrich blindly

Two public functions:
  enrich_output(full_json)       → called on upload, enriches all combos at once
  enrich_single_combo(combo)     → called on detail view if ai_confidence missing
"""

from __future__ import annotations
import json, re, sys, os
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import HF_TOKEN, HF_MODEL, SYSTEM_ENRICH_PROMPT, SYSTEM_COMBO_PROMPT

import requests

_HF_ENDPOINT = "https://api-inference.huggingface.co/v1/chat/completions"

_HEADERS = {
    "Authorization": f"Bearer {HF_TOKEN}",
    "Content-Type":  "application/json",
}


# ─── Internal AI caller ───────────────────────────────────────────────────────

def _call_ai(system: str, user_content: str, max_tokens: int = 600, temperature: float = 0.2) -> Optional[str]:
    """
    Single point-of-truth for all AI calls in this module.
    Returns raw text response or None on failure.
    Low temperature for deterministic, structured output.
    """
    payload = {
        "model":      HF_MODEL,
        "messages": [
            {"role": "system",  "content": system},
            {"role": "user",    "content": user_content},
        ],
        "max_tokens":  max_tokens,
        "temperature": temperature,
    }
    try:
        r = requests.post(_HF_ENDPOINT, headers=_HEADERS, json=payload, timeout=90)
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"].strip()
    except requests.exceptions.Timeout:
        return None
    except Exception:
        return None


def _extract_json_block(text: str) -> Optional[dict]:
    """
    Safely extract the first JSON object from an AI response.
    Handles markdown code fences, leading/trailing noise.
    """
    if not text:
        return None
    # Strip markdown code fences
    text = re.sub(r"```(?:json)?", "", text).strip()
    # Find first { ... }
    start = text.find("{")
    end   = text.rfind("}")
    if start == -1 or end == -1:
        return None
    try:
        return json.loads(text[start:end + 1])
    except json.JSONDecodeError:
        return None


def _default_ai_fields() -> dict:
    """Returns safe defaults when AI is unavailable."""
    return {
        "ai_summary":         "AI enrichment unavailable.",
        "ai_confidence":      None,
        "anomalies":          [],
        "validation_status":  "UNKNOWN",
        "spec_refs":          [],
    }


# ─── Prompt builder ───────────────────────────────────────────────────────────

def _build_summary_payload(full_json: dict) -> str:
    """
    Build a compact representation of the full parsed result for the AI.
    We summarize counts and send a sample of combos — not the entire JSON.
    This avoids hitting rate limits / context window on large files.
    """
    lte_bands = full_json.get("lteBands", [])
    nr_bands  = full_json.get("nrBands",  [])
    lteca     = full_json.get("lteca",    [])
    nrca      = full_json.get("nrca",     [])
    mrdc      = full_json.get("mrdc",     [])

    # Pick at most 3 of each combo type as examples
    sample = {
        "summary": {
            "lte_band_count": len(lte_bands),
            "nr_band_count":  len(nr_bands),
            "lte_ca_count":   len(lteca),
            "nr_ca_count":    len(nrca),
            "mrdc_count":     len(mrdc),
            "metadata":       full_json.get("metadata", {}),
        },
        "lte_bands_sample": lte_bands[:5],
        "nr_bands_sample":  nr_bands[:5],
        "lteca_sample":     lteca[:3],
        "nrca_sample":      nrca[:3],
        "mrdc_sample":      mrdc[:3],
    }
    return json.dumps(sample, indent=2, default=str)[:3000]


def _build_combo_payload(combo: dict) -> str:
    """Build a compact payload for a single combo enrichment."""
    return json.dumps(combo, indent=2, default=str)[:2000]


# ─── Main enrichment functions ────────────────────────────────────────────────

def enrich_output(full_json: dict) -> dict:
    """
    Called ONCE at upload time on the complete formatted output.

    Strategy:
      1. Send compact summary to Mistral-7B
      2. AI returns: ai_summary, ai_confidence, anomalies, validation_status, spec_refs
      3. Inject these fields into full_json["ai_enrichment"]
      4. Distribute per-combo ai data from the per-combo combos section

    Parser output (lteBands, nrBands, lteca, nrca, mrdc) is NEVER modified.
    AI data is additive — stored in separate keys.
    """
    payload = _build_summary_payload(full_json)
    raw_response = _call_ai(SYSTEM_ENRICH_PROMPT, payload, max_tokens=600)
    ai_data = _extract_json_block(raw_response) if raw_response else None

    if not ai_data:
        ai_data = _default_ai_fields()
        ai_data["ai_summary"] = "AI enrichment could not be completed. Parser data is authoritative."

    # Ensure required keys exist with safe defaults
    ai_data.setdefault("ai_summary",        "No summary generated.")
    ai_data.setdefault("ai_confidence",     None)
    ai_data.setdefault("anomalies",         [])
    ai_data.setdefault("validation_status", "UNKNOWN")
    ai_data.setdefault("spec_refs",         [])

    # Inject AI enrichment block into output (additive, parser data untouched)
    full_json["ai_enrichment"] = ai_data

    # Propagate top-level confidence to metadata for dashboard display
    if "metadata" not in full_json:
        full_json["metadata"] = {}
    full_json["metadata"]["ai_confidence"]      = ai_data["ai_confidence"]
    full_json["metadata"]["ai_validation"]      = ai_data["validation_status"]
    full_json["metadata"]["extraction_method"]  = "rule-based + mistral-7b"

    return full_json


def enrich_single_combo(combo: dict) -> dict:
    """
    Fallback enrichment for a single combination — only called if:
      - combo is missing ai_confidence (wasn't pre-enriched)
      - user clicked detail view on an un-enriched combo

    IMPORTANT: If combo already has ai_confidence, return it as-is (no re-call).
    """
    if combo.get("ai_confidence") is not None:
        return combo   # already enriched — cache hit

    payload = _build_combo_payload(combo)
    raw_response = _call_ai(SYSTEM_COMBO_PROMPT, payload, max_tokens=400)
    ai_data = _extract_json_block(raw_response) if raw_response else None

    if not ai_data:
        ai_data = _default_ai_fields()

    # Merge AI fields into combo (additive only)
    combo["ai_summary"]        = ai_data.get("ai_summary",        "No summary available.")
    combo["ai_confidence"]     = ai_data.get("ai_confidence",     None)
    combo["anomalies"]         = ai_data.get("anomalies",         [])
    combo["validation_status"] = ai_data.get("validation_status", "UNKNOWN")
    combo["spec_refs"]         = ai_data.get("spec_refs",         [])

    return combo
