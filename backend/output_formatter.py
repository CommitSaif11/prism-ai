"""
output_formatter.py
===================
Step 3 — Takes the extracted data dict + metadata → clean JSON
matching Samsung's exact template.
"""

from __future__ import annotations
import json
from typing import Any


def _clean(obj: Any) -> Any:
    """Recursively remove None values from dicts/lists."""
    if isinstance(obj, dict):
        return {k: _clean(v) for k, v in obj.items() if v is not None}
    if isinstance(obj, list):
        return [_clean(i) for i in obj]
    return obj


def format_output(extracted: dict, entry_info: dict, source_file: str = "") -> dict:
    """
    Build the final Samsung-format JSON output.

    Args:
        extracted   : output of sequential_extractor.extract_all()
        entry_info  : output of entry_point.find_entry_point()
        source_file : filename string

    Returns:
        dict matching Samsung's full template
    """
    meta = entry_info.get("metadata", {})

    output = {
        "metadata": {
            "source_file":      source_file,
            "pkt_version":      meta.get("pkt_version"),
            "rrc_release":      meta.get("rrc_release"),
            "physical_cell_id": meta.get("physical_cell_id"),
            "freq":             meta.get("freq"),
            "rat_type":         entry_info.get("rat_type"),
            "entry_line":       entry_info.get("entry_line"),
            "extraction_method": "rule-based-sequential",
            "total_lte_bands":  len(extracted.get("lteBands", [])),
            "total_nr_bands":   len(extracted.get("nrBands", [])),
            "total_lte_ca":     len(extracted.get("lteca", [])),
            "total_nr_ca":      len(extracted.get("nrca", [])),
            "total_mrdc":       len(extracted.get("mrdc", [])),
        },
        "lteBands": extracted.get("lteBands", []),
        "nrBands":  extracted.get("nrBands", []),
        "lteca":    extracted.get("lteca", []),
        "nrca":     extracted.get("nrca", []),
        "mrdc":     extracted.get("mrdc", []),
    }

    if "ai_notes" in extracted:
        output["ai_notes"] = extracted["ai_notes"]
    if "ai_enrichment" in extracted:
        output["ai_enrichment"] = extracted["ai_enrichment"]

    return _clean(output)


def validate_output(output: dict) -> dict:
    """
    Basic validation — checks counts and structure.
    Returns validation report.
    """
    issues = []
    meta = output.get("metadata", {})

    if not output.get("lteBands"):
        issues.append("WARNING: No LTE bands extracted")
    if not output.get("nrBands"):
        issues.append("WARNING: No NR bands extracted")
    if not output.get("lteca"):
        issues.append("WARNING: No LTE CA combos extracted")
    if not output.get("mrdc"):
        issues.append("WARNING: No MRDC combos extracted")

    # Check each LTE band has bwClass in at least one CA combo
    lte_band_nums = {b["band"] for b in output.get("lteBands", [])}
    ca_band_nums = set()
    for combo in output.get("lteca", []):
        for c in combo.get("components", []):
            ca_band_nums.add(c.get("band"))
    missing = lte_band_nums - ca_band_nums
    if missing and len(missing) < 10:
        issues.append(f"INFO: LTE bands {sorted(missing)} not in any CA combo")

    return {
        "valid": len([i for i in issues if i.startswith("WARNING")]) == 0,
        "total_lte_bands": meta.get("total_lte_bands", 0),
        "total_nr_bands":  meta.get("total_nr_bands", 0),
        "total_lte_ca":    meta.get("total_lte_ca", 0),
        "total_nr_ca":     meta.get("total_nr_ca", 0),
        "total_mrdc":      meta.get("total_mrdc", 0),
        "issues": issues,
    }
