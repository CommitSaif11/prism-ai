"""
ai_assist_parser.py
===================
Gap-filling AI layer for UE Capability parsing.
Runs AFTER the rule-based parser but BEFORE output formatting.
"""

import json
import logging
import re
from typing import Dict, Any, List

# Re-use our robust AI caller from ai_processor
from ai_processor import _call_ai, _extract_json_block

log = logging.getLogger(__name__)

SYSTEM_ASSIST_PROMPT = """You are a 3GPP UE capability extraction assistant.
You will be provided with a raw UE capability text chunk, and a specific context explaining what parsed data is missing.
Your task is to locate the missing data within the raw text and return it as a strictly formatted JSON object matching the requested schema.
Rules:
- DO NOT hallucinate. If you cannot find the requested parameter in the provided text, return an empty JSON object {}.
- Output ONLY the raw JSON object. No explanation, no markdown ticks."""

def detect_unknown_structures(parsed_json: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Find gaps in the parsed data (empty lists, missing values in expected pairs).
    Returns a list of 'gap contexts'.
    """
    gaps = []

    # 1. MRDC Gaps (most common area for nested parser failure)
    for i, combo in enumerate(parsed_json.get("mrdc", [])):
        lte_comps = combo.get("componentsLte", [])
        nr_comps = combo.get("componentsNr", [])

        if len(lte_comps) > 0 and len(nr_comps) == 0:
            gaps.append({
                "type": "mrdc_missing_nr",
                "path": ["mrdc", i],
                "description": f"MRDC combo {i} has LTE bands but missing NR bands",
                "target_key": "componentsNr",
                "combo_data": combo
            })
        elif len(nr_comps) > 0 and len(lte_comps) == 0:
            gaps.append({
                "type": "mrdc_missing_lte",
                "path": ["mrdc", i],
                "description": f"MRDC combo {i} has NR bands but missing LTE bands",
                "target_key": "componentsLte",
                "combo_data": combo
            })

    return gaps

def _get_relevant_raw_chunk(raw_text: str, combo_data: Dict) -> str:
    """
    Naively attempt to scope the raw text down to something manageable
    based on the bands we already know about.
    """
    match = re.search(r'(value\s+UE-MRDC-Capability.+)', raw_text, re.IGNORECASE | re.DOTALL)
    segment = match.group(1) if match else raw_text
    
    # Cap size to avoid overwhelming context window
    if len(segment) > 8000:
        segment = segment[:8000] + "\n...[TRUNCATED]"
    return segment

def ai_extract_missing(raw_text: str, context: Dict[str, Any]) -> Dict[str, Any]:
    """ Prompts the AI to find exactly what is missing based on the gap context. """
    chunk = _get_relevant_raw_chunk(raw_text, context["combo_data"])
    
    user_prompt = f"""MISSING DATA CONTEXT:
{context['description']}

CURRENT PARTIAL COMBO:
{json.dumps(context['combo_data'], indent=2)}

TARGET SCHEMA TO RETURN:
Please return a JSON object with the key `{context['target_key']}` containing a list of the extracted band components.
Example structure for a band component:
{{
  "{context['target_key']}": [
    {{
      "band": 78,
      "mimoDl": {{"type": "single", "value": 4}},
      "mimoUl": {{"type": "single", "value": 1}}
    }}
  ]
}}

RAW TEXT TO SEARCH:
{chunk}
"""
    raw_response = _call_ai(SYSTEM_ASSIST_PROMPT, user_prompt, max_tokens=500, temperature=0.1)
    if not raw_response:
        return {}
        
    ai_data = _extract_json_block(raw_response)
    return ai_data if ai_data else {}

def normalize_with_ai(fragment: Dict[str, Any], target_key: str) -> List[Dict[str, Any]]:
    """ Ensure the AI output matches our strict schema expectations. """
    items = fragment.get(target_key, [])
    if not isinstance(items, list):
        return []

    normalized = []
    for item in items:
        if not isinstance(item, dict): continue
        if "band" not in item: continue
        
        # Enforce band identity as integer
        try:
            band_val = int(str(item["band"]).lstrip("n"))
        except:
            continue
            
        norm = {
            "band": band_val,
            "mimoDl": item.get("mimoDl"),
            "mimoUl": item.get("mimoUl", {"type": "single", "value": 1}),
            "bwClassDl": item.get("bwClassDl"),
            "bwClassUl": item.get("bwClassUl")
        }
        normalized.append(norm)
        
    return normalized

def validate_ai_output(normalized_data: List[Dict], existing_comps: List[Dict]) -> bool:
    """ Ensure the AI hallucinated nothing dangerous. """
    if not normalized_data:
        return False
        
    existing_bands = {c.get("band") for c in existing_comps if "band" in c}
    
    for comp in normalized_data:
        b = comp.get("band")
        # Validate 3GPP integer compliance limits (strictly 1 to 300 roughly)
        if not isinstance(b, int) or b < 1 or b > 300:
            log.warning(f"[AI Assist] Rejecting invalid band value: {b}")
            return False
            
    return True

def run_hybrid_assist(raw_text: str, parsed_json: Dict[str, Any]) -> Dict[str, Any]:
    """ Main entrypoint: mutates parsed_json IN-PLACE filling detected gaps. """
    gaps = detect_unknown_structures(parsed_json)
    filled_fields = []
    warnings = []
    
    if not gaps:
        parsed_json["ai_notes"] = {"filled_fields": [], "confidence": 1.0, "warnings": ["No gaps detected. Pure extraction."]}
        return parsed_json
    
    for gap in gaps:
        ai_raw_data = ai_extract_missing(raw_text, gap)
        
        if not ai_raw_data or gap["target_key"] not in ai_raw_data:
            warnings.append(f"AI failed to extract {gap['target_key']} for combo {gap['path'][1]}")
            continue
            
        # Normalize/Validate
        norm_data = normalize_with_ai(ai_raw_data, gap["target_key"])
        section, idx = gap["path"][0], gap["path"][1]
        target_combo = parsed_json[section][idx]
        existing_target_list = target_combo.get(gap["target_key"], [])
        
        # Merge exactly inside logic rule: ONLY fill if strictly empty
        if len(existing_target_list) == 0 and validate_ai_output(norm_data, target_combo.get("componentsLte", []) + target_combo.get("componentsNr", [])):
            parsed_json[section][idx][gap["target_key"]] = norm_data
            filled_fields.append(f"Added {len(norm_data)} bands to {section}[{idx}].{gap['target_key']}")
        else:
            warnings.append(f"Rejected data merge for {section}[{idx}].{gap['target_key']} (invalid formats or conflict found)")

    parsed_json["ai_notes"] = {
        "filled_fields": filled_fields,
        "confidence": 0.85 if filled_fields else 1.0,
        "warnings": warnings
    }
    
    return parsed_json
