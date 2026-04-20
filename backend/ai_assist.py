"""
ai_assist.py  v3.0  — FINAL
============================
Gap detection + controlled AI fill.

v3 fix: bandwidth gaps are now detected AFTER the new sequential_extractor
runs. Since v5 extractor fills bandwidths via raw-text regex, there should
be NO gaps for most logs. AI is called only when gaps genuinely remain.
"""

from __future__ import annotations
import json, re, sys, os, time, logging
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ai_processor import _call_ai, _extract_json_block

log = logging.getLogger(__name__)

MAX_GAPS = 5  # reduced — v5 extractor should leave at most 1-2 gaps

_SYSTEM = """You are a 3GPP NR UE capability expert.
Fill ONLY the bandwidths field for the given NR band.
Return ONLY valid JSON: {"bandwidths": [{"scs": <int>, "bandwidthsDl": [<int MHz>], "bandwidthsUl": [<int MHz>]}]}
Valid MHz: 5,10,15,20,25,30,40,50,60,80,100,200,400. No explanation. No markdown."""


def detect_gaps(parsed: Dict[str, Any]) -> List[Tuple[str, Dict]]:
    """Find NR bands with empty bandwidths."""
    gaps = []
    for band in parsed.get("nrBands", []):
        if not isinstance(band, dict): continue
        bw = band.get("bandwidths", [])
        if not bw:
            gaps.append(("missing_bw", band))
            log.debug(f"[Gap] NR B{band.get('band')}: missing_bw")
    return gaps


def extract_band_block(raw_text: str, band_id: int) -> str:
    """Extract raw text block for a specific NR band."""
    m = re.search(rf'bandNR\s+{band_id}\b', raw_text, re.IGNORECASE)
    if not m: return ""
    rest = raw_text[m.start():]
    next_b = re.search(r'bandNR\s+\d+\b', rest[10:], re.IGNORECASE)
    return rest[:next_b.start()+10].strip() if next_b else rest[:4000].strip()


def validate_ai_output(ai_output: Any) -> bool:
    if not isinstance(ai_output, dict): return False
    bw_list = ai_output.get("bandwidths")
    if not isinstance(bw_list, list) or not bw_list: return False
    valid_mhz = {5,10,15,20,25,30,40,50,60,80,100,200,400}
    for entry in bw_list:
        if not isinstance(entry, dict): return False
        scs = entry.get("scs")
        if not isinstance(scs, int) or scs <= 0: return False
        dl = entry.get("bandwidthsDl", [])
        if not dl or any(not isinstance(v,int) or v not in valid_mhz for v in dl): return False
    return True


def ai_fill_gaps(raw_text: str, parsed: Dict[str, Any]) -> Dict[str, Any]:
    """
    Detect bandwidth gaps, call AI for each (capped at MAX_GAPS).
    Returns parsed_json unchanged if no gaps.
    """
    t0 = time.perf_counter()
    gaps = detect_gaps(parsed)

    if not gaps:
        print("[AI-Assist] No bandwidth gaps — parser output complete. Skipping AI.")
        return parsed

    print(f"[AI-Assist] {len(gaps)} gap(s) detected.")

    if len(gaps) > MAX_GAPS:
        print(f"[AI-Assist] {len(gaps)} gaps exceed MAX_GAPS={MAX_GAPS}. Skipping AI.")
        parsed["ai_assist_meta"] = {"gaps": len(gaps), "ai_calls": 0,
                                     "note": f"Skipped: {len(gaps)} > {MAX_GAPS}"}
        return parsed

    calls = fills = rejected = 0
    for gap_type, band in gaps:
        band_id = band.get("band")
        if band_id is None: continue
        print(f"  [AI-Assist] NR B{band_id}: calling AI for missing bandwidth...")

        raw_block = extract_band_block(raw_text, band_id)
        calls += 1

        user = (f"NR band {band_id} partial JSON:\n{json.dumps(band, indent=2, default=str)[:1000]}\n\n"
                f"Raw capability block:\n{raw_block[:2000]}")
        raw_resp = _call_ai(system=_SYSTEM, user_content=user, max_tokens=300, temperature=0.05)
        ai_out = _extract_json_block(raw_resp) if raw_resp else None

        if not ai_out or not validate_ai_output(ai_out):
            print(f"  [AI-Assist] B{band_id}: rejected")
            rejected += 1
            continue

        band["bandwidths"]       = ai_out["bandwidths"]
        band["bandwidth_source"] = "ai_filled"
        fills += 1
        print(f"  [AI-Assist] B{band_id}: ✓ applied {len(ai_out['bandwidths'])} entries")

    elapsed = round(time.perf_counter() - t0, 3)
    parsed["ai_assist_meta"] = {"gaps": len(gaps), "ai_calls": calls,
                                 "fills_applied": fills, "fills_rejected": rejected,
                                 "elapsed_seconds": elapsed}
    print(f"[AI-Assist] Done {elapsed}s — calls={calls} applied={fills} rejected={rejected}")
    return parsed