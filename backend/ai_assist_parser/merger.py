"""
merger.py — Safe Merge (Task 6)
================================
Merges validated AI data into parser output with one absolute rule:
NEVER overwrite existing valid values — only fill empty/missing fields.

Parser output is the SOURCE OF TRUTH. AI data is supplementary.
"""

from __future__ import annotations
import copy
import logging
import re
from typing import Any, Dict, List, Tuple

log = logging.getLogger(__name__)


def safe_merge(
    parsed_json: Dict[str, Any],
    validated_fills: Dict[str, Any],
) -> Tuple[Dict[str, Any], List[str]]:
    """
    Merge validated AI fills into parsed_json IN-PLACE.
    Only fills empty/missing fields. Never overwrites existing data.

    Args:
        parsed_json: the parser's output (source of truth)
        validated_fills: dict of {gap_path: value} from validator

    Returns:
        (merged_json, filled_fields) where filled_fields is a list
        of path strings that were actually filled by AI.
    """
    filled_fields = []

    for path_str, value in validated_fills.items():
        success = _apply_fill(parsed_json, path_str, value)
        if success:
            filled_fields.append(path_str)
            log.info(f"[Merger] Filled: {path_str}")
        else:
            log.info(f"[Merger] Skipped: {path_str} (already has data or invalid path)")

    return parsed_json, filled_fields


def _apply_fill(data: Dict, path_str: str, value: Any) -> bool:
    """
    Navigate to the target location and fill it ONLY if empty/missing.

    Path format: "section[idx].key" or "section[idx].subkey[idx2].field"
    Examples:
        "mrdc[0].componentsNr"
        "nrBands[3].bandwidths"
        "lteca[5].components[1].bwClassDl"
    """
    parts = _parse_path(path_str)
    if not parts:
        log.warning(f"[Merger] Could not parse path: {path_str}")
        return False

    # Navigate to the parent container
    current = data
    for part in parts[:-1]:
        current = _navigate(current, part)
        if current is None:
            log.warning(f"[Merger] Navigation failed at '{part}' in path: {path_str}")
            return False

    # Apply the fill to the final key
    final_key = parts[-1]
    return _fill_if_empty(current, final_key, value)


def _parse_path(path_str: str) -> List:
    """
    Parse a path string into navigation tokens.

    "mrdc[0].componentsNr" → ["mrdc", 0, "componentsNr"]
    "nrBands[3].bandwidths" → ["nrBands", 3, "bandwidths"]
    """
    tokens = []
    # Split on dots, then handle array indices
    for segment in path_str.split("."):
        match = re.match(r'^(\w+)\[(\d+)\]$', segment)
        if match:
            tokens.append(match.group(1))
            tokens.append(int(match.group(2)))
        else:
            tokens.append(segment)
    return tokens


def _navigate(current: Any, key: Any) -> Any:
    """Navigate one level deeper using a key (str) or index (int)."""
    if isinstance(key, int):
        if isinstance(current, list) and 0 <= key < len(current):
            return current[key]
        return None
    if isinstance(key, str):
        if isinstance(current, dict):
            return current.get(key)
        return None
    return None


def _fill_if_empty(container: Any, key: Any, value: Any) -> bool:
    """
    Fill a field ONLY if it's currently empty/missing/None.

    Rules:
    - dict key missing or None → fill
    - dict key is empty list [] → fill
    - dict key is empty string "" → fill
    - dict key already has data → SKIP (parser truth preserved)
    - list index → SKIP (we don't replace list items)
    """
    if isinstance(container, dict) and isinstance(key, str):
        existing = container.get(key)

        # Case 1: key doesn't exist or is None → fill
        if existing is None:
            container[key] = value
            return True

        # Case 2: empty list → fill
        if isinstance(existing, list) and len(existing) == 0:
            container[key] = value
            return True

        # Case 3: empty string → fill
        if isinstance(existing, str) and existing.strip() == "":
            container[key] = value
            return True

        # Case 4: existing data → DO NOT overwrite
        log.debug(f"[Merger] Preserving existing value for '{key}': "
                  f"{type(existing).__name__} with {_data_size(existing)} items/chars")
        return False

    # Integer keys (list indices) — we never replace list items
    if isinstance(container, list) and isinstance(key, int):
        log.debug(f"[Merger] Skipping list item replacement at index {key}")
        return False

    return False


def _data_size(value: Any) -> int:
    """Get a rough size indicator for a value."""
    if isinstance(value, (list, dict)):
        return len(value)
    return len(str(value))
