"""
ai_assist.py — Controlled AI Assist (Task 4)
==============================================
Calls AI ONLY when gaps exist, using ONE batched call.
Never calls AI in loops or per-combination.

Reuses the existing ai_processor._call_ai() and _extract_json_block()
for consistency with the rest of the system (same model, same endpoint).
"""

from __future__ import annotations
import json
import logging
import re
import sys
import os
from typing import Any, Dict, List, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ai_processor import _call_ai, _extract_json_block

log = logging.getLogger(__name__)


# ─── System prompt for gap-filling ──────────────────────────────────────────

_GAP_FILL_SYSTEM_PROMPT = """You are a 3GPP UE capability extraction assistant.
You will receive a list of MISSING DATA GAPS detected in parsed UE capability output,
along with relevant raw text context.

Your task is to find the missing data in the raw text and return it as structured JSON.

STRICT RULES:
- Return ONLY a valid JSON object. No explanation, no markdown.
- Each key in the response must match one of the gap paths provided.
- If you cannot find data for a gap, omit that key entirely.
- DO NOT hallucinate values. Only return what you can find in the raw text.
- Band values must be integers (1-300).
- MIMO values must be integers (1, 2, 4, 8).
- Bandwidth class values must be single uppercase letters (A-I).

NR BANDWIDTH DECODING:
If the gap is for missing "bandwidths" within an NR band, you will likely see bitmap encoded capabilities in the text (e.g., scs-15kHz '11111110 00'B). 
- You MUST decode the bandwidth capability from these bitmap values.
- Map them to real bandwidths (e.g., 5MHz, 10MHz, 20MHz, 100MHz) according to 3GPP specs.
- Format the result as an array of objects matching the output schema.

Response format:
{
  "fills": {
    "<gap_path>": <extracted_value>,
    ...
  }
}"""


def ai_fill_gaps(raw_text: str, gaps: List[Dict], max_gaps_per_call: int = 20) -> Dict[str, Any]:
    """
    Batch all gaps into ONE AI call to extract missing data.

    Args:
        raw_text: the original UE capability text
        gaps: list of gap descriptors from gap_detector
        max_gaps_per_call: safety limit to prevent prompt overflow

    Returns:
        {
            "fills": {gap_path: extracted_value, ...},
            "ai_called": True,
            "raw_response": str or None
        }
    """
    if not gaps:
        return {"fills": {}, "ai_called": False, "raw_response": None}

    # Filter to fillable gaps (critical + major only — minor gaps aren't worth AI calls)
    fillable_gaps = [g for g in gaps if g["severity"] in ("critical", "major")]

    if not fillable_gaps:
        log.info("[AI Assist] No critical/major gaps to fill. Skipping AI call.")
        return {"fills": {}, "ai_called": False, "raw_response": None}

    # Cap gaps to prevent prompt explosion
    if len(fillable_gaps) > max_gaps_per_call:
        log.warning(f"[AI Assist] {len(fillable_gaps)} gaps exceed limit {max_gaps_per_call}, "
                    f"processing first {max_gaps_per_call}")
        fillable_gaps = fillable_gaps[:max_gaps_per_call]

    # Build ONE batched prompt
    user_prompt = _build_gap_prompt(raw_text, fillable_gaps)

    # ONE AI call — never in a loop
    log.info(f"[AI Assist] Making ONE batched AI call for {len(fillable_gaps)} gap(s)")
    raw_response = _call_ai(_GAP_FILL_SYSTEM_PROMPT, user_prompt, max_tokens=800, temperature=0.1)

    if not raw_response:
        log.warning("[AI Assist] AI call returned empty response")
        return {"fills": {}, "ai_called": True, "raw_response": None}

    ai_data = _extract_json_block(raw_response)

    if not ai_data or "fills" not in ai_data:
        # Try to interpret the whole response as a fills dict
        if ai_data and isinstance(ai_data, dict):
            return {"fills": ai_data, "ai_called": True, "raw_response": raw_response}
        log.warning("[AI Assist] AI response did not contain valid 'fills' object")
        return {"fills": {}, "ai_called": True, "raw_response": raw_response}

    return {
        "fills": ai_data.get("fills", {}),
        "ai_called": True,
        "raw_response": raw_response,
    }


def _build_gap_prompt(raw_text: str, gaps: List[Dict]) -> str:
    """
    Build a single prompt describing all gaps and providing relevant raw text context.
    """
    # Extract relevant section from raw text (MRDC section is most commonly needed)
    context_text = _extract_context(raw_text)

    gap_descriptions = []
    for i, gap in enumerate(gaps, 1):
        desc = (
            f"  Gap {i}:\n"
            f"    Path: {gap['path']}\n"
            f"    Type: {gap['type']}\n"
            f"    Severity: {gap['severity']}\n"
            f"    Description: {gap['description']}\n"
            f"    Target key: {gap['target_key']}\n"
            f"    Context: {json.dumps(gap.get('context', {}))}"
        )
        gap_descriptions.append(desc)

    return f"""DETECTED GAPS IN PARSED OUTPUT:
{chr(10).join(gap_descriptions)}

RAW UE CAPABILITY TEXT (relevant sections):
{context_text}

Return a JSON object with "fills" mapping each gap path to its extracted value.
For component lists, return the full list structure.
Example: {{"fills": {{"mrdc[0].componentsNr": [{{"band": 78, "mimoDl": {{"type": "single", "value": 4}}}}]}}}}
"""


def _extract_context(raw_text: str) -> str:
    """
    Extract the most relevant portions of raw text for AI context.
    Focuses on capability sections while staying under context limits.
    """
    # Try to find MRDC section first (most common gap source)
    sections = []

    mrdc_match = re.search(
        r'(value\s+UE-MRDC-Capability.+?)(?=value\s+UE-|$)',
        raw_text, re.IGNORECASE | re.DOTALL
    )
    if mrdc_match:
        sections.append(mrdc_match.group(1)[:3000])

    nr_match = re.search(
        r'(value\s+UE-NR-Capability.+?)(?=value\s+UE-|$)',
        raw_text, re.IGNORECASE | re.DOTALL
    )
    if nr_match:
        sections.append(nr_match.group(1)[:3000])

    if sections:
        context = "\n---\n".join(sections)
    else:
        context = raw_text[:6000]

    # Hard cap to prevent token overflow
    if len(context) > 6000:
        context = context[:6000] + "\n...[TRUNCATED]"

    return context
