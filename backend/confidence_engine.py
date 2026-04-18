"""
confidence_engine.py
====================
Scores LLM fallback output 0.0–1.0.
Flags anomalies. Auto-accepts > 0.85. Sends < 0.5 back for retry.
"""

from __future__ import annotations
import re
from typing import Any

# Valid 3GPP NR bands
_VALID_NR_BANDS = {
    1,2,3,5,7,8,12,14,18,20,25,26,28,29,30,34,
    38,39,40,41,46,47,48,53,66,70,71,74,75,76,
    77,78,79,80,81,82,83,84,86,89,90,91,92,93,
    94,95,96,257,258,260,261
}

# Valid 3GPP LTE bands
_VALID_LTE_BANDS = set(range(1, 90))

# Valid BW class values
_VALID_BW_CLASS = {'A','B','C','D','E','F','G','H','I'}


def score_output(output: dict) -> dict:
    """
    Score an output dict. Returns:
    {
        'score': float 0.0-1.0,
        'decision': 'accept' | 'review' | 'retry',
        'flags': [list of issue strings],
        'per_section': { lteBands: float, nrBands: float, ... }
    }
    """
    flags = []
    scores = {}

    # ── LTE Bands ──────────────────────────────────────────────
    lte_bands = output.get("lteBands", [])
    lte_score = 1.0
    for b in lte_bands:
        bn = b.get("band")
        if bn not in _VALID_LTE_BANDS:
            flags.append(f"Invalid LTE band number: {bn}")
            lte_score -= 0.1
        if b.get("mimoDl") is None:
            flags.append(f"LTE B{bn}: missing mimoDl")
            lte_score -= 0.05
    scores["lteBands"] = max(0.0, lte_score)

    # ── NR Bands ───────────────────────────────────────────────
    nr_bands = output.get("nrBands", [])
    nr_score = 1.0
    for b in nr_bands:
        bn = b.get("band")
        if bn not in _VALID_NR_BANDS:
            flags.append(f"Invalid NR band number: {bn}")
            nr_score -= 0.1
        bws = b.get("bandwidths", [])
        if not bws:
            flags.append(f"NR B{bn}: no bandwidth table")
            nr_score -= 0.05
    scores["nrBands"] = max(0.0, nr_score)

    # ── LTE CA ─────────────────────────────────────────────────
    lteca = output.get("lteca", [])
    ca_score = 1.0
    for combo in lteca:
        for comp in combo.get("components", []):
            if not comp.get("bwClassDl") or not comp.get("bwClassUl"):
                flags.append(f"LTE CA B{comp.get('band')}: missing bwClass DL or UL")
                ca_score -= 0.05
            if comp.get("bwClassDl", "").upper() not in _VALID_BW_CLASS and comp.get("bwClassDl"):
                flags.append(f"LTE CA B{comp.get('band')}: invalid bwClassDl '{comp.get('bwClassDl')}'")
                ca_score -= 0.1
    scores["lteca"] = max(0.0, ca_score)

    # ── NR CA ──────────────────────────────────────────────────
    nrca = output.get("nrca", [])
    nrca_score = 1.0
    for combo in nrca:
        for comp in combo.get("components", []):
            if not comp.get("bwClassDl") or not comp.get("bwClassUl"):
                flags.append(f"NR CA B{comp.get('band')}: missing bwClass DL or UL")
                nrca_score -= 0.05
            if comp.get("band") not in _VALID_NR_BANDS:
                flags.append(f"NR CA: invalid band {comp.get('band')}")
                nrca_score -= 0.1
    scores["nrca"] = max(0.0, nrca_score)

    # ── MRDC ───────────────────────────────────────────────────
    mrdc = output.get("mrdc", [])
    mrdc_score = 1.0
    for combo in mrdc:
        for comp in combo.get("componentsNr", []):
            if not comp.get("bwClassDl") or not comp.get("bwClassUl"):
                flags.append(f"MRDC NR B{comp.get('band')}: missing bwClass DL or UL")
                mrdc_score -= 0.05
        for comp in combo.get("componentsLte", []):
            if not comp.get("bwClassDl") or not comp.get("bwClassUl"):
                flags.append(f"MRDC LTE B{comp.get('band')}: missing bwClass DL or UL")
                mrdc_score -= 0.05
    scores["mrdc"] = max(0.0, mrdc_score)

    # ── Overall score ──────────────────────────────────────────
    if not lte_bands: scores["lteBands"] = 0.0; flags.append("No LTE bands")
    if not nr_bands:  scores["nrBands"]  = 0.0; flags.append("No NR bands")
    if not lteca:     scores["lteca"]    = 0.5; flags.append("No LTE CA combos")
    if not mrdc:      scores["mrdc"]     = 0.5; flags.append("No MRDC combos")

    overall = sum(scores.values()) / max(len(scores), 1)

    decision = "accept" if overall >= 0.85 else "review" if overall >= 0.5 else "retry"

    return {
        "score":       round(overall, 3),
        "decision":    decision,
        "flags":       flags,
        "per_section": {k: round(v, 3) for k, v in scores.items()},
    }
