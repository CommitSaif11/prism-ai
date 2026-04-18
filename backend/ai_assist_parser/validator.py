"""
validator.py — AI Output Validation Layer (Task 5)
====================================================
Validates AI-returned data before it can be merged into parser output.
Ensures bands are in valid 3GPP range, structures match expected schemas,
duplicates are removed, and hallucinated fields are rejected.
"""

from __future__ import annotations
import logging
from typing import Any, Dict, List, Optional, Tuple

log = logging.getLogger(__name__)

# ─── Validation constants ────────────────────────────────────────────────────

_VALID_BAND_RANGE = range(1, 301)           # 3GPP bands: 1–300
_VALID_MIMO_VALUES = {1, 2, 4, 8}           # Valid MIMO layer counts
_VALID_BW_CLASSES = {"A", "B", "C", "D", "E", "F", "G", "H", "I"}
_VALID_MODULATIONS = {"qam16", "qam64", "qam256", "qam1024"}

# Fields that AI is allowed to fill
_ALLOWED_FILL_KEYS = {
    "band", "mimoDl", "mimoUl", "bwClassDl", "bwClassUl",
    "modulationDl", "modulationUl", "bandwidths", "maxScs",
    "maxBwDl", "maxBwUl", "powerClass",
    "componentsLte", "componentsNr", "components",
}


def validate_ai_output(fills: Dict[str, Any], gaps: List[Dict]) -> Tuple[Dict[str, Any], List[str]]:
    """
    Validate AI-returned fills against strict rules.

    Returns:
        (validated_fills, rejection_reasons)
        - validated_fills: only the fills that passed validation
        - rejection_reasons: list of reasons for rejected fills
    """
    validated = {}
    rejections = []

    if not isinstance(fills, dict):
        rejections.append("AI output is not a dict")
        return {}, rejections

    # Build a set of expected gap paths for cross-reference
    expected_paths = {g["path"] for g in gaps}

    for path, value in fills.items():
        # Check 1: path must correspond to an actual gap
        if path not in expected_paths:
            rejections.append(f"Unexpected path '{path}' — not a detected gap")
            continue

        # Find the matching gap descriptor
        gap = next((g for g in gaps if g["path"] == path), None)
        if not gap:
            rejections.append(f"No matching gap for path '{path}'")
            continue

        # Check 2: validate the value based on target key type
        is_valid, reason = _validate_value(value, gap)
        if is_valid:
            validated[path] = value
            log.info(f"[Validator] Accepted AI fill: {path}")
        else:
            rejections.append(f"Rejected {path}: {reason}")
            log.warning(f"[Validator] Rejected AI fill: {path} — {reason}")

    return validated, rejections


def _validate_value(value: Any, gap: Dict) -> Tuple[bool, str]:
    """
    Validate a single AI-produced value based on its gap context.
    Returns (is_valid, reason_if_invalid).
    """
    target_key = gap.get("target_key", "")

    # ── Component lists (componentsLte, componentsNr, components) ──────
    if target_key in ("componentsLte", "componentsNr", "components"):
        return _validate_component_list(value)

    # ── Single band value ──────────────────────────────────────────────
    if target_key == "band":
        return _validate_band(value)

    # ── MIMO ───────────────────────────────────────────────────────────
    if target_key in ("mimoDl", "mimoUl"):
        return _validate_mimo(value)

    # ── Bandwidth class ────────────────────────────────────────────────
    if target_key in ("bwClassDl", "bwClassUl"):
        return _validate_bw_class(value)

    # ── Bandwidth tables ───────────────────────────────────────────────
    if target_key == "bandwidths":
        return _validate_bandwidths(value)

    # Fallback: accept if value is not None
    if value is not None:
        return True, ""
    return False, "Value is None"


def _validate_component_list(value: Any) -> Tuple[bool, str]:
    """Validate a list of band components."""
    if not isinstance(value, list):
        return False, f"Expected list, got {type(value).__name__}"
    if not value:
        return False, "Empty component list"

    for i, comp in enumerate(value):
        if not isinstance(comp, dict):
            return False, f"Component [{i}] is not a dict"
        band = comp.get("band")
        if band is None:
            return False, f"Component [{i}] missing 'band' field"

        # Normalize band: strip leading 'n' for NR bands
        if isinstance(band, str):
            try:
                band = int(band.lstrip("nN"))
            except ValueError:
                return False, f"Component [{i}] invalid band value: {band}"

        if not isinstance(band, int) or band not in _VALID_BAND_RANGE:
            return False, f"Component [{i}] band {band} out of range 1-300"

        # Check for hallucinated keys
        for key in comp:
            if key not in _ALLOWED_FILL_KEYS:
                return False, f"Component [{i}] has unknown key '{key}'"

    # Deduplicate by band number
    seen_bands = set()
    for comp in value:
        b = comp.get("band")
        if isinstance(b, str):
            b = int(b.lstrip("nN"))
        if b in seen_bands:
            return False, f"Duplicate band {b} in component list"
        seen_bands.add(b)

    return True, ""


def _validate_band(value: Any) -> Tuple[bool, str]:
    """Validate a single band number."""
    if isinstance(value, str):
        try:
            value = int(value.lstrip("nN"))
        except ValueError:
            return False, f"Invalid band string: {value}"
    if not isinstance(value, int):
        return False, f"Band must be int, got {type(value).__name__}"
    if value not in _VALID_BAND_RANGE:
        return False, f"Band {value} out of range 1-300"
    return True, ""


def _validate_mimo(value: Any) -> Tuple[bool, str]:
    """Validate a MIMO value (can be raw int or {type, value} dict)."""
    if isinstance(value, dict):
        v = value.get("value")
        if v is None:
            return False, "MIMO dict missing 'value'"
        if not isinstance(v, int) or v not in _VALID_MIMO_VALUES:
            return False, f"MIMO value {v} not in {_VALID_MIMO_VALUES}"
        return True, ""
    if isinstance(value, int):
        if value not in _VALID_MIMO_VALUES:
            return False, f"MIMO value {value} not in {_VALID_MIMO_VALUES}"
        return True, ""
    return False, f"MIMO must be int or dict, got {type(value).__name__}"


def _validate_bw_class(value: Any) -> Tuple[bool, str]:
    """Validate a bandwidth class letter."""
    if not isinstance(value, str):
        return False, f"BW class must be string, got {type(value).__name__}"
    v = value.strip().upper()
    if v not in _VALID_BW_CLASSES:
        return False, f"BW class '{v}' not in {_VALID_BW_CLASSES}"
    return True, ""


def _validate_bandwidths(value: Any) -> Tuple[bool, str]:
    """Validate a bandwidth table."""
    if not isinstance(value, list):
        return False, f"Bandwidths must be list, got {type(value).__name__}"
    for i, entry in enumerate(value):
        if not isinstance(entry, dict):
            return False, f"Bandwidth entry [{i}] is not a dict"
        if "scs" not in entry:
            return False, f"Bandwidth entry [{i}] missing 'scs'"
    return True, ""
