"""
ai_processor.py — Samsung PRISM AI Intelligence Layer
======================================================
Stage 3 in the pipeline: Parser → Formatter → [AI PROCESSOR] → Store

Reads HF_TOKEN from .env file and uses HuggingFace Inference API.
"""

from __future__ import annotations
import json, re, sys, os, time, inspect
from typing import Optional

import requests
from dotenv import load_dotenv

# Load .env — search backend dir then project root
_here = os.path.dirname(os.path.abspath(__file__))
for _env_path in [os.path.join(_here, ".env"), os.path.join(_here, "..", ".env")]:
    if os.path.isfile(_env_path):
        load_dotenv(_env_path)
        print(f"[ENV] Loaded .env from: {_env_path}")
        break
else:
    load_dotenv()

# Get HuggingFace credentials from environment
HF_TOKEN = os.getenv("HF_TOKEN", "")
HF_MODEL = os.getenv("HF_MODEL", "mistralai/Mistral-7B-v0.1")

if not HF_TOKEN:
    print("[WARNING] HF_TOKEN not found in .env file. AI will be disabled.")
    print("[INFO] Create a .env file with: HF_TOKEN=hf_your_token_here")
else:
    print("[ENV] HF_TOKEN loaded successfully")

sys.path.insert(0, _here)
from config import SYSTEM_ENRICH_PROMPT, SYSTEM_COMBO_PROMPT

# ── Global AI call counter (importable for profiling) ──────────────────────────────
ai_call_count: int = 0

_HF_ENDPOINT = f"https://api-inference.huggingface.co/models/{HF_MODEL}"

# ── AI control switches ───────────────────────────────────────────────────────
AI_ENABLED   = bool(HF_TOKEN)   # Only enable if HF_TOKEN exists
MAX_AI_CALLS = 4                # 1 gap-detect + 1 gap-fill + 1 enrich + 1 validate

from config import SYSTEM_GAP_FILL_PROMPT, SYSTEM_GAP_DETECT_PROMPT, SYSTEM_ENRICH_PROMPT, SYSTEM_VALIDATE_PROMPT, SYSTEM_COMBO_PROMPT

# ── Confidence gate: rule-based gap detection ─────────
def should_fill_gaps_rule_based(data: dict, rat_type: str) -> bool:
    """Return True ONLY when the rule-based parser detects gaps based on RAT TYPE."""
    rat = rat_type.lower()
    if rat == "nr":
        return not data.get("nrBands")
    elif rat == "eutra":
        return not data.get("lteBands")
    elif rat == "mrdc":
        return not data.get("lteBands") or not data.get("nrBands") or not data.get("mrdc")
    
    # fallback
    return not data.get("lteBands") and not data.get("nrBands")

# ─── Internal AI caller ───────────────────────────────────────────────────────

def _call_ai(system: str, user_content: str, max_tokens: int = 400, temperature: float = 0.1) -> Optional[str]:
    """
    Single point-of-truth for all AI calls.
    Reads HF_TOKEN from environment and sends it in Authorization header.
    """
    global AI_ENABLED, ai_call_count

    if not AI_ENABLED:
        print("[AI SKIPPED] AI disabled — rule-based parser is the sole engine")
        return None

    if not HF_TOKEN:
        print("[AI SKIPPED] HF_TOKEN not configured in .env")
        return None

    if ai_call_count >= MAX_AI_CALLS:
        print(f"[AI SKIPPED] MAX_AI_CALLS cap reached ({MAX_AI_CALLS})")
        return None
    ai_call_count += 1

    caller = inspect.stack()[1].function
    if ai_call_count > 4:
        print(f"[WARNING] AI called multiple times! Possible loop! Caller: {caller}")

    start_time = time.perf_counter()
    prompt = f"{system}\n\n{user_content}".strip()
    print(f"\n[AI] Call {ai_call_count} started. Prompt length: {len(prompt)} chars. Caller: {caller}")
    print("[AI URL]", _HF_ENDPOINT)

    try:
        headers = {
            "Authorization": f"Bearer {HF_TOKEN}",
            "Content-Type":  "application/json",
        }
        payload = {
            "inputs": prompt,
            "parameters": {
                "temperature":      temperature,
                "max_new_tokens":   max_tokens,
                "return_full_text": False,
            }
        }

        r = requests.post(_HF_ENDPOINT, headers=headers, json=payload, timeout=90)
        elapsed = time.perf_counter() - start_time

        if r.status_code == 404:
            print("[AI DISABLED] Invalid model endpoint — disabling AI for this session")
            AI_ENABLED = False
            return None
        if r.status_code != 200:
            print(f"[AI ERROR] Status {r.status_code}: {r.text[:300]}")
            return None

        output = r.json()

        if isinstance(output, list) and len(output) > 0 and "generated_text" in output[0]:
            resp = output[0]["generated_text"].strip()
            print(f"[AI] Response received: {len(resp)} chars in {elapsed:.2f}s\n")
            return resp
        else:
            print(f"[AI ERROR] Unexpected response format: {output}")
            return None

    except requests.exceptions.Timeout:
        print("[AI ERROR] Request timed out (90s)")
        return None
    except Exception as e:
        elapsed = time.perf_counter() - start_time
        print(f"[AI ERROR] Call failed after {elapsed:.2f}s: {e}")
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


# ─── Main pipeline functions ──────────────────────────────────────────────────

def fill_gaps_ai(extracted: dict, rat_type: str) -> dict:
    """
    STAGE 1: Gap-Fill (Called on raw extracted data before formatting)
    1. Rule-based fast filter.
    2. AI Smart Confirmation (GAP DETECT).
    3. AI Fill (GAP FILL) only if BOTH agree.
    """
    if not should_fill_gaps_rule_based(extracted, rat_type):
        print(f"[AI] Rule-based filter passed (RAT={rat_type}) — skipping GAP-FILL.")
        return extracted
        
    print(f"[AI] Rule-based gaps suspected (RAT={rat_type}). Calling GAP-DETECT...")
    
    # Send a compact version of the extracted JSON to avoid context overflow
    small_extracted = {
        "lteBands": extracted.get("lteBands", [])[:10],
        "nrBands":  extracted.get("nrBands", [])[:10],
        "lteca":    extracted.get("lteca", [])[:5],
        "nrca":     extracted.get("nrca", [])[:5],
        "mrdc":     extracted.get("mrdc", [])[:5]
    }
    payload = json.dumps(small_extracted, default=str)
    
    # ── AI Smart Confirmation ──
    user_msg_detect = f"Detected RAT TYPE: {rat_type}\n<INPUT_JSON>\n{payload}\n</INPUT_JSON>"
    raw_detect_resp = _call_ai(SYSTEM_GAP_DETECT_PROMPT, user_msg_detect, max_tokens=300)
    ai_detect = _extract_json_block(raw_detect_resp) if raw_detect_resp else None
    
    if not ai_detect or not ai_detect.get("has_gaps"):
        print(f"[AI] AI Confirmation passed — ignoring rule-based gaps for RAT={rat_type}.")
        return extracted
        
    print(f"[AI] AI Confirmation agreed (Gaps={ai_detect.get('missing_required_sections')}). Calling GAP-FILL...")
    
    # ── AI Gap-Fill ──
    user_msg_fill = f"<INPUT_JSON>\n{payload}\n</INPUT_JSON>"
    raw_response = _call_ai(SYSTEM_GAP_FILL_PROMPT, user_msg_fill, max_tokens=800)
    ai_out = _extract_json_block(raw_response) if raw_response else None
    
    if ai_out and isinstance(ai_out, dict):
        print("[AI] Gap-fill successful, applying merged data.")
        # Only merge missing elements that AI securely identified
        for key in ["lteBands", "nrBands", "lteca", "nrca", "mrdc"]:
            if not extracted.get(key) and ai_out.get(key):
                extracted[key] = ai_out[key]
    else:
        print("[AI] Gap-fill failed or none applied.")
        
    return extracted


def enrich_output(full_json: dict, rat_type: str) -> dict:
    """
    STAGE 2: Enrichment (Called to generate technical summary after formatting)
    """
    if not should_fill_gaps_rule_based(full_json, rat_type):
        print(f"[AI SKIPPED] Enrichment not required (Rule-based check passed for RAT={rat_type})")
        ai_data = {
            "skip": True,
            "ai_summary": "Data is complete and structurally sound. No AI summary needed.",
            "ai_confidence": 1.0,
            "anomalies": [],
            "validation_status": "PASSED"
        }
    else:
        payload = _build_summary_payload(full_json)
        user_msg = f"Detected RAT TYPE: {rat_type}\n<INPUT_JSON>\n{payload}\n</INPUT_JSON>"
        
        raw_response = _call_ai(SYSTEM_ENRICH_PROMPT, user_msg, max_tokens=400)
        ai_data = _extract_json_block(raw_response) if raw_response else None

        if not ai_data:
            ai_data = _default_ai_fields()

        # Handle {"skip": true}
        if ai_data.get("skip"):
            print(f"[AI SKIPPED] Enrichment not required (AI decision)")
            ai_data = {
                "ai_summary": "AI confirmed data is complete and structurally sound. No summary needed.",
                "ai_confidence": 1.0,
                "anomalies": [],
                "validation_status": "PASSED"
            }

    # Ensure required keys exist with safe defaults
    ai_data.setdefault("ai_summary",        "No summary generated.")
    ai_data.setdefault("ai_confidence",     None)
    ai_data.setdefault("anomalies",         [])

    # Inject AI enrichment block into output
    if "ai_enrichment" not in full_json:
        full_json["ai_enrichment"] = {}
    
    full_json["ai_enrichment"].update(ai_data)

    if "metadata" not in full_json:
        full_json["metadata"] = {}
    full_json["metadata"]["ai_confidence"] = ai_data["ai_confidence"]
    full_json["metadata"]["extraction_method"] = "rule-based + mistral-7b"

    return full_json


def validate_output_ai(full_json: dict, rat_type: str) -> dict:
    """
    STAGE 3: Validation (RAT-aware checking of completeness)
    """
    if not should_fill_gaps_rule_based(full_json, rat_type):
        print(f"[AI SKIPPED] Validation not required (Rule-based check passed for RAT={rat_type})")
        ai_out = {
            "status": "PASSED",
            "confidence": 1.0,
            "summary": "Rule-based check fully passed. Data is complete.",
            "missing_sections": [],
            "notes": []
        }
    else:
        print(f"[AI] Calling VALIDATION for RAT: {rat_type}...")
        payload = _build_summary_payload(full_json)
        
        user_msg = f"Detected RAT TYPE: {rat_type}\n<INPUT_JSON>\n{payload}\n</INPUT_JSON>"
        raw_response = _call_ai(SYSTEM_VALIDATE_PROMPT, user_msg, max_tokens=300)
        ai_data = _extract_json_block(raw_response) if raw_response else None
        
        if not ai_data:
            ai_out = {
                "status": "REVIEW",
                "confidence": 0.0,
                "summary": "AI validation failed or returned invalid format.",
                "missing_sections": [],
                "notes": ["AI timeout or parse error"]
            }
        elif ai_data.get("skip"):
            print("[AI SKIPPED] Validation skipped by AI decision (data complete).")
            ai_out = {
                "status": "PASSED",
                "confidence": 1.0,
                "summary": "AI confirmed data is structurally sound.",
                "missing_sections": [],
                "notes": []
            }
        else:
            print("[AI] Validation executed (issues found).")
            ai_out = {
                "status": "REVIEW",
                "confidence": 0.5,
                "summary": ai_data.get("reason", "Validation triggered by AI."),
                "missing_sections": ai_data.get("focus_areas", []),
                "notes": ["Generated from AI validation decision."]
            }
    
    if "ai_validation" not in full_json:
        full_json["ai_validation"] = {}
    full_json["ai_validation"] = ai_out
    
    # Propagate to metadata for dashboard
    if "metadata" not in full_json:
        full_json["metadata"] = {}
    full_json["metadata"]["ai_validation_status"] = ai_out.get("status", "UNKNOWN")
    
    return full_json


def enrich_single_combo(combo: dict) -> dict:
    """Fallback enrichment for a single combination."""
    if combo.get("ai_confidence") is not None:
        return combo

    payload = _build_combo_payload(combo)
    raw_response = _call_ai(SYSTEM_COMBO_PROMPT, payload, max_tokens=400)
    ai_data = _extract_json_block(raw_response) if raw_response else None

    if not ai_data:
        ai_data = _default_ai_fields()

    combo["ai_summary"]        = ai_data.get("ai_summary",        "No summary available.")
    combo["ai_confidence"]     = ai_data.get("ai_confidence",     None)
    combo["anomalies"]         = ai_data.get("anomalies",         [])
    combo["validation_status"] = ai_data.get("validation_status", "UNKNOWN")
    combo["spec_refs"]         = ai_data.get("spec_refs",         [])

    return combo
