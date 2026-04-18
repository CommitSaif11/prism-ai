"""
gap_detector.py — Pattern-Based Gap Detection Engine (Tasks 2 + 3)
===================================================================
Uses pattern rules to detect structural gaps in parser output.
Pattern rules are ONLY used for gap detection and unknown-structure
handling — the parser's extraction logic is NEVER modified.

Returns a structured gap report with exact paths, severity levels,
and context for the AI assist layer.
"""

from __future__ import annotations
import re
from typing import Any, Dict, List

from .walker import walk, collect_by_pattern


# ─── Pattern Rules (Task 2) ─────────────────────────────────────────────────
# Used ONLY for gap detection — NOT for data extraction.
# The parser handles extraction; these identify what's missing.

PATTERN_RULES = {
    "band":       lambda k, v: "band" in k.lower() and isinstance(v, (int, str)),
    "mimo":       lambda k, v: "mimo" in k.lower(),
    "bw":         lambda k, v: ("bw" in k.lower() or "bandwidth" in k.lower()),
    "modulation": lambda k, v: ("modulation" in k.lower() or "qam" in k.lower()),
    "scs":        lambda k, v: "scs" in k.lower() or "subcarrierspacing" in k.lower().replace("-", "").replace("_", ""),
    "powerclass": lambda k, v: "power" in k.lower() and "class" in k.lower(),
    "bwclass":    lambda k, v: "bwclass" in k.lower().replace("-", "").replace("_", ""),
}

# Severity weights for confidence calculation
SEVERITY = {
    "critical":  0.3,   # Empty component lists, missing band IDs
    "major":     0.15,  # Missing bandwidth/MIMO on bands
    "minor":     0.05,  # Missing optional fields like powerClass
}


def detect_gaps(parsed_json: Dict[str, Any]) -> Dict[str, Any]:
    """
    Scan all sections of parsed output for structural gaps.

    Returns:
        {
            "gaps": [list of gap descriptors],
            "gap_count": int,
            "has_critical": bool,
            "sections_scanned": [list of section names],
        }
    """
    gaps: List[Dict] = []

    # ── 1. MRDC gaps (highest priority) ────────────────────────────────
    gaps.extend(_scan_mrdc_gaps(parsed_json.get("mrdc", [])))

    # ── 2. LTE band gaps ──────────────────────────────────────────────
    gaps.extend(_scan_band_gaps(parsed_json.get("lteBands", []), "lteBands", "LTE"))

    # ── 3. NR band gaps ───────────────────────────────────────────────
    gaps.extend(_scan_band_gaps(parsed_json.get("nrBands", []), "nrBands", "NR"))

    # ── 4. LTE CA gaps ────────────────────────────────────────────────
    gaps.extend(_scan_ca_gaps(parsed_json.get("lteca", []), "lteca", "LTE-CA"))

    # ── 5. NR CA gaps ─────────────────────────────────────────────────
    gaps.extend(_scan_ca_gaps(parsed_json.get("nrca", []), "nrca", "NR-CA"))

    # ── 6. Unknown/unrecognized blocks ─────────────────────────────────
    gaps.extend(_scan_unknown_blocks(parsed_json))

    has_critical = any(g["severity"] == "critical" for g in gaps)

    return {
        "gaps": gaps,
        "gap_count": len(gaps),
        "has_critical": has_critical,
        "sections_scanned": ["lteBands", "nrBands", "lteca", "nrca", "mrdc"],
    }


# ─── MRDC-specific gap detection ────────────────────────────────────────────

def _scan_mrdc_gaps(mrdc_combos: list) -> List[Dict]:
    """Detect gaps in MRDC combinations."""
    gaps = []

    for i, combo in enumerate(mrdc_combos):
        if not isinstance(combo, dict):
            continue

        lte_comps = combo.get("componentsLte", [])
        nr_comps = combo.get("componentsNr", [])

        # Critical: MRDC combo with only one side populated
        if len(lte_comps) > 0 and len(nr_comps) == 0:
            gaps.append({
                "type": "mrdc_missing_nr",
                "section": "mrdc",
                "index": i,
                "path": f"mrdc[{i}].componentsNr",
                "severity": "critical",
                "description": f"MRDC combo {i} has {len(lte_comps)} LTE component(s) but 0 NR components",
                "target_key": "componentsNr",
                "context": {"lte_bands": [c.get("band") for c in lte_comps]},
            })
        elif len(nr_comps) > 0 and len(lte_comps) == 0:
            gaps.append({
                "type": "mrdc_missing_lte",
                "section": "mrdc",
                "index": i,
                "path": f"mrdc[{i}].componentsLte",
                "severity": "critical",
                "target_key": "componentsLte",
                "description": f"MRDC combo {i} has {len(nr_comps)} NR component(s) but 0 LTE components",
                "context": {"nr_bands": [c.get("band") for c in nr_comps]},
            })

        # Major: components exist but are missing key fields
        for j, comp in enumerate(lte_comps):
            _check_component_completeness(gaps, comp, f"mrdc[{i}].componentsLte[{j}]", "mrdc", i)
        for j, comp in enumerate(nr_comps):
            _check_component_completeness(gaps, comp, f"mrdc[{i}].componentsNr[{j}]", "mrdc", i)

    return gaps


# ─── Band gap detection ─────────────────────────────────────────────────────

def _scan_band_gaps(bands: list, section: str, rat: str) -> List[Dict]:
    """Detect gaps in standalone band entries."""
    gaps = []

    for i, band in enumerate(bands):
        if not isinstance(band, dict):
            continue

        bn = band.get("band")

        # NR bands should have bandwidth tables
        if rat == "NR" and not band.get("bandwidths"):
            gaps.append({
                "type": "missing_bandwidths",
                "section": section,
                "index": i,
                "path": f"{section}[{i}].bandwidths",
                "severity": "major",
                "description": f"NR band {bn} has no bandwidth table",
                "target_key": "bandwidths",
                "context": {"band": bn},
            })

    return gaps


# ─── CA combo gap detection ─────────────────────────────────────────────────

def _scan_ca_gaps(combos: list, section: str, rat: str) -> List[Dict]:
    """Detect gaps in CA combinations."""
    gaps = []

    for i, combo in enumerate(combos):
        if not isinstance(combo, dict):
            continue

        components = combo.get("components", [])
        if not components:
            gaps.append({
                "type": "empty_ca_combo",
                "section": section,
                "index": i,
                "path": f"{section}[{i}].components",
                "severity": "critical",
                "description": f"{rat} combo {i} has empty components list",
                "target_key": "components",
                "context": {},
            })
            continue

        for j, comp in enumerate(components):
            _check_component_completeness(gaps, comp, f"{section}[{i}].components[{j}]", section, i)

    return gaps


# ─── Unknown block detection ─────────────────────────────────────────────────

def _scan_unknown_blocks(parsed_json: Dict) -> List[Dict]:
    """
    Detect unexpected top-level keys that might contain unprocessed data.
    """
    known_keys = {"lteBands", "nrBands", "lteca", "nrca", "mrdc",
                  "metadata", "validation", "ai_enrichment", "ai_notes"}
    gaps = []

    for key in parsed_json:
        if key not in known_keys and not key.startswith("_"):
            value = parsed_json[key]
            # Only flag if it looks like substantive data
            if isinstance(value, (dict, list)) and len(str(value)) > 50:
                gaps.append({
                    "type": "unknown_block",
                    "section": "root",
                    "index": None,
                    "path": key,
                    "severity": "minor",
                    "description": f"Unrecognized top-level key '{key}' with substantive data",
                    "target_key": key,
                    "context": {"key": key, "type": type(value).__name__},
                })

    return gaps


# ─── Component completeness check (shared) ──────────────────────────────────

def _check_component_completeness(gaps: list, comp: dict, path: str, section: str, combo_idx: int):
    """Check a single band component for missing fields."""
    if not isinstance(comp, dict):
        return

    bn = comp.get("band")

    # Removed bwClassDl check because it's technically optional and creates false positive gaps
    return
