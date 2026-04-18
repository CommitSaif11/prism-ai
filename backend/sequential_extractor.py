"""
sequential_extractor.py  v3.0
==============================
Step 2 — Extract ALL parameters Samsung requires.

ROOT CAUSE FIXES (verified against actual parser output):
  1. Parser treats trailing commas as WORD tokens.
     "},\n{" produces key "," with values being subsequent combo entries.
     _blocks() now collects items from BOTH _block_N keys AND "," keys.

  2. ",_nr" — inside bandList, the nr block's key is ",_nr" (because a comma
     precedes "nr { ... }"). Lookups must check BOTH "eutra"/",_eutra" and "nr"/",_nr".

  3. All values may have trailing commas: "3," → 3. _clean_str() strips them.

  4. featureSetCombination stored as: "," : "featureSetCombination", then index stored
     separately as "1" : True.  Need _extract_fsc_id() to handle this pattern.
"""

from __future__ import annotations
import re, sys, os
from typing import Any, Dict, List, Optional

sys.path.insert(0, os.path.dirname(__file__))
from asn_parser import parse_text, _norm


# ─── Core helpers ─────────────────────────────────────────────────────────────

def _to_int(s) -> Optional[int]:
    if s is None: return None
    try: return int(re.sub(r'[^0-9-]', '', str(s).strip()))
    except: return None

def _to_bool(s) -> Optional[bool]:
    if isinstance(s, bool): return s
    s = str(s).lower().strip().rstrip(',')
    if s in ('true', 'yes', '1', 'supported'): return True
    if s in ('false', 'no', '0', 'notsupported', 'not_supported'): return False
    return None

def _norm_key(k: str) -> str:
    return re.sub(r'[^a-z0-9]', '', str(k).lower())

def _clean_str(v) -> str:
    """Strip whitespace AND trailing commas. Fixes 'A,' → 'A', '3,' → '3'."""
    if v is None: return ''
    return str(v).strip().rstrip(',').strip()

def _sv(val) -> Optional[dict]:
    if val is None: return None
    return {"type": "single", "value": val}

def _mimo_to_int(s) -> Optional[int]:
    if not s: return None
    v = _clean_str(str(s))
    if v.isdigit(): return int(v)
    c = re.sub(r'[^a-z]', '', v.lower())
    return {'onelayer':1,'one':1,'twolayers':2,'two':2,
            'fourlayers':4,'four':4,'eightlayers':8,'eight':8}.get(c)

def _parse_bw(s) -> Optional[int]:
    if not s: return None
    m = re.search(r'mhz(\d+)', str(s), re.I)
    if m: return int(m.group(1))
    m = re.match(r'^\s*(\d+)\s*$', _clean_str(str(s)))
    if m: return int(m.group(1))
    return None


# ─── Tree navigation (parser-aware) ──────────────────────────────────────────

def _blocks(node) -> list:
    """
    CRITICAL FIX: Extract ALL child entries from a container node.

    The parser stores them in two ways:
      - _block_0, _block_1, ...  (anonymous blocks: `{ ... }`)
      - ","                       (entries after a comma: `}, { ... }`)

    Both must be collected to get ALL entries.
    """
    if node is None: return []
    if isinstance(node, list): return node
    if isinstance(node, dict):
        entries = []
        # 1. Collect _block_N entries (sorted by number)
        bkeys = sorted(
            [k for k in node if k.startswith('_block_')],
            key=lambda k: int(k.split('_')[2]) if k.split('_')[2].isdigit() else 0
        )
        for k in bkeys:
            v = node[k]
            if isinstance(v, dict):
                entries.append(v)
            elif isinstance(v, list):
                entries.extend(x for x in v if isinstance(x, dict))

        # 2. Collect comma-separated entries (key is literally ",")
        comma_val = node.get(',')
        if comma_val is not None:
            if isinstance(comma_val, dict):
                entries.append(comma_val)
            elif isinstance(comma_val, list):
                entries.extend(x for x in comma_val if isinstance(x, dict))

        if entries:
            return entries

        # 3. Fallback: single-value dict wrapping a list
        vals = list(node.values())
        if len(vals) == 1 and isinstance(vals[0], list):
            return vals[0]

        # 4. Last resort: the dict itself is the entry
        return [node]
    return []


def _get_val(d: dict, *raw_keys) -> Any:
    """
    Look up a value in dict, trying:
      1. Exact key
      2. Parser-normalized key (_norm)
      3. Comma-prefixed key (",_<key>") — parser artifact from trailing commas
      4. _norm_key match (strips all separators)

    This handles all parser output variants.
    """
    if not isinstance(d, dict): return None
    for rk in raw_keys:
        # exact
        if rk in d: return d[rk]
        # parser-normed
        normed = _norm(rk)
        if normed in d: return d[normed]
        # comma-prefixed (parser artifact)
        comma_key = f",_{normed}"
        if comma_key in d: return d[comma_key]
        comma_key2 = f",_{rk.lower()}"
        if comma_key2 in d: return d[comma_key2]

    # full _norm_key sweep (strip everything)
    target_set = {_norm_key(k) for k in raw_keys}
    for k, v in d.items():
        if _norm_key(k) in target_set:
            return v
    return None


def _find(tree, keys):
    """DFS — collect all values at matching keys."""
    result = []
    keys_norm = {_norm_key(k) for k in keys}
    def _walk(node):
        if isinstance(node, dict):
            for k, v in node.items():
                nk = _norm_key(k)
                if nk in keys_norm:
                    if isinstance(v, list): result.extend(v)
                    else: result.append(v)
                _walk(v)  # ALWAYS recurse (even into matched values)
        elif isinstance(node, list):
            for item in node: _walk(item)
    _walk(tree)
    return result


def _collect(tree, keys):
    """Recursive collect — returns {norm_key: [all_values]} from entire subtree."""
    r = {}
    keys_norm = {_norm_key(k) for k in keys}
    def _walk(node):
        if isinstance(node, dict):
            for k, v in node.items():
                nk = _norm_key(k)
                if nk in keys_norm:
                    r.setdefault(nk, [])
                    if isinstance(v, list): r[nk].extend(v)
                    else: r[nk].append(v)
                _walk(v)
        elif isinstance(node, list):
            for item in node: _walk(item)
    _walk(tree)
    return r


def _first(collected, *keys):
    for k in keys:
        vals = collected.get(_norm_key(k))
        if vals: return vals[0]
    return None


def _find_entries_with(tree, key_names):
    """Find ALL dicts in the tree that contain at least one of the given keys."""
    result = []
    keys_norm = {_norm_key(k) for k in key_names}
    def _walk(node):
        if isinstance(node, dict):
            has = any(_norm_key(k) in keys_norm for k in node.keys())
            if has:
                result.append(node)
            for v in node.values():
                _walk(v)
        elif isinstance(node, list):
            for item in node: _walk(item)
    _walk(tree)
    return result


def _all_child_dicts(node) -> list:
    """
    Get ALL dict children from a node — handles named keys, lists,
    _block_N keys, AND comma-prefixed keys.
    """
    if isinstance(node, list):
        return [x for x in node if isinstance(x, dict)]
    if isinstance(node, dict):
        result = []
        for k, v in node.items():
            if k == '__type__': continue
            if isinstance(v, dict):
                result.append(v)
            elif isinstance(v, list):
                result.extend(x for x in v if isinstance(x, dict))
        return result
    return []


def _extract_fsc_id(entry: dict) -> Optional[int]:
    """
    Extract featureSetCombination ID from an entry.
    Parser stores this weirdly:
      "," : "featureSetCombination"   (comma key stores the name)
      "1" : True                     (the actual ID is stored as a key)

    OR sometimes:
      "featuresetcombination" : "1"
    """
    # Direct key
    for k, v in entry.items():
        if _norm_key(k) == 'featuresetcombination':
            i = _to_int(v)
            if i is not None: return i

    # Parser-artifact pattern: comma stores name, next key is the ID
    comma_val = entry.get(',')
    if isinstance(comma_val, str) and _norm_key(comma_val) == 'featuresetcombination':
        # Look for the numeric key that follows
        for k in entry.keys():
            clean_k = _clean_str(k)
            if clean_k.isdigit():
                return int(clean_k)

    return None


def _unwrap(raw: str) -> dict:
    parsed = parse_text(raw)
    eq = parsed.get('=')
    if isinstance(eq, list) and eq and isinstance(eq[0], dict): return eq[0]
    if isinstance(eq, dict): return eq
    return parsed


# ─── Section boundaries ──────────────────────────────────────────────────────

_SEC_PAT = {
    'mrdc':  re.compile(r'value\s+UE-MRDC-Capability(?:-v\w+)?\s*::=', re.IGNORECASE),
    'eutra': re.compile(r'value\s+UE-EUTRA-Capability(?:-v\w+)?\s*::=', re.IGNORECASE),
    'nr':    re.compile(r'value\s+UE-NR-Capability(?:-v\w+)?\s*::=', re.IGNORECASE),
}

def _split_sections(text: str) -> dict:
    lines = text.splitlines(keepends=True)
    hits = {}
    for i, line in enumerate(lines):
        for name, pat in _SEC_PAT.items():
            if pat.search(line) and name not in hits:
                hits[name] = i
    if not hits: return {}
    ordered = sorted(hits.items(), key=lambda x: x[1])
    result = {}
    for idx, (name, start) in enumerate(ordered):
        end = ordered[idx+1][1] if idx+1 < len(ordered) else len(lines)
        result[name] = ''.join(lines[start:end])
    return result


# ─── LTE Band extraction ──────────────────────────────────────────────────────

def _extract_lte_bands(eutra_tree: dict) -> list:
    bands = []
    seen = set()

    # Find all dicts that contain bandeutra — these are band entries
    entries = _find_entries_with(eutra_tree, {'bandEUTRA', 'bandeutra', 'band_eutra'})

    # Filter: only entries from supportedBandListEUTRA context (not CA combos)
    # We use _find to get the container, then _blocks + _all_child_dicts
    containers = _find(eutra_tree, {
        'supportedbandlisteutra', 'supported_band_list_eutra',
    })

    band_entries = []
    for container in containers:
        for entry in _blocks(container):
            if isinstance(entry, dict):
                band_entries.append(entry)

    # If structured search found entries, use those. Otherwise fall back to DFS.
    if not band_entries:
        band_entries = entries

    for entry in band_entries:
        if not isinstance(entry, dict): continue
        c = _collect(entry, {
            'bandEUTRA', 'bandEUTRA_r10', 'bandeutra',
            'halfDuplex', 'half_duplex',
            'maxNumberMIMO-LayersDL', 'maxnumbermimolayersdl',
            'supportedMIMO-CapabilityDL-r10', 'supportedmimocapabilitydlr10',
            'dl-256QAM-r12', 'dl_256qam_r12',
            'ul-64QAM-r12', 'ul_64qam_r12',
            'powerClass', 'power_class',
        })

        bn = _to_int(_first(c, 'bandeutra', 'bandeutra_r10'))
        if bn is None or bn in seen: continue
        seen.add(bn)

        mimo = _mimo_to_int(_first(c, 'supportedmimocapabilitydlr10', 'maxnumbermimolayersdl'))
        dl256 = _to_bool(str(_first(c, 'dl256qamr12') or ''))
        ul64 = _to_bool(str(_first(c, 'ul64qamr12') or ''))
        hd = _to_bool(str(_first(c, 'halfduplex') or ''))

        bands.append({
            "band": bn,
            "mimoDl": _sv(mimo) if mimo else None,
            "mimoUl": None,
            "modulationDl": _sv("qam256") if dl256 else None,
            "modulationUl": _sv("qam64") if ul64 else None,
            "powerClass": _clean_str(_first(c, 'powerclass') or '') or None,
            "extras": {
                "bandEUTRA": bn,
                "halfDuplex": hd if hd is not None else False,
            }
        })

    return bands


# ─── NR Band extraction ──────────────────────────────────────────────────────

_BW_TABLES = {
    15:  [5,10,15,20,25,30,40,50],
    30:  [5,10,15,20,25,40,50,60,80,100],
    60:  [10,15,20,25,40,50,60,80,100],
    120: [50,100,200,400],
    240: [400],
}

def _parse_bitmask(bitmask_str: str, scs: int) -> list:
    clean = re.sub(r'[^01]', '', str(bitmask_str))
    table = _BW_TABLES.get(scs, [])
    return [table[i] for i, bit in enumerate(clean) if bit == '1' and i < len(table)]


def _extract_nr_bands(nr_tree: dict) -> list:
    bands = []
    seen = set()

    # Find supportedBandListNR containers
    containers = _find(nr_tree, {
        'supportedbandlistnr', 'supported_band_list_nr',
    })

    band_entries = []
    for container in containers:
        for entry in _blocks(container):
            if isinstance(entry, dict):
                band_entries.append(entry)

    # Fallback: DFS for ALL dicts containing bandNR
    if not band_entries:
        band_entries = _find_entries_with(nr_tree, {'bandNR', 'bandnr', 'band_nr'})

    for entry in band_entries:
        if not isinstance(entry, dict): continue
        c = _collect(entry, {
            'bandNR', 'band_nr', 'bandnr',
            'maxNumberMIMO-LayersPDSCH', 'maxnumbermimolayerspdsch',
            'maxNumberMIMO-LayersCB-PUSCH', 'maxnumbermimolayerscbpusch',
            'modulationOrderDL', 'modulationorderdl',
            'modulationOrderUL', 'modulationorderul',
            'pusch-256QAM', 'pusch256qam',
            'ue-PowerClass', 'uepowerclass',
            'multipleTCI', 'multipletci',
            'rateMatchingLTE-CRS', 'ratematchingltecrs',
        })

        bn = _to_int(_first(c, 'bandnr', 'band_nr'))
        if bn is None or bn in seen: continue
        seen.add(bn)

        mimo_dl = _mimo_to_int(_first(c, 'maxnumbermimolayerspdsch'))
        mimo_ul = _mimo_to_int(_first(c, 'maxnumbermimolayerscbpusch'))
        mod_dl = _clean_str(_first(c, 'modulationorderdl') or '') or None
        mod_ul = _clean_str(_first(c, 'modulationorderul') or '') or None
        pc = _clean_str(_first(c, 'uepowerclass') or '') or None

        # Parse channelBWs bitmasks
        bws = []
        def _walk_bws(node):
            if isinstance(node, dict):
                for k, v in node.items():
                    nk = _norm_key(k)
                    if 'channelbw' in nk and 'dl' in nk and 'ul' not in nk:
                        if isinstance(v, dict):
                            for scs_k, bitmask in v.items():
                                d = re.search(r'(\d+)', scs_k)
                                if d:
                                    scs_val = int(d.group(1))
                                    bw_list = _parse_bitmask(str(bitmask), scs_val)
                                    if bw_list:
                                        bws.append({"scs": scs_val, "bandwidthsDl": bw_list, "bandwidthsUl": bw_list})
                    _walk_bws(v)
            elif isinstance(node, list):
                for item in node: _walk_bws(item)
        _walk_bws(entry)

        bands.append({
            "band": bn,
            "mimoDl": _sv(mimo_dl) if mimo_dl else None,
            "mimoUl": _sv(mimo_ul) if mimo_ul else None,
            "modulationDl": _sv(mod_dl) if mod_dl else None,
            "modulationUl": _sv(mod_ul) if mod_ul else None,
            "powerClass": pc,
            "bandwidths": bws,
            "rateMatchingLteCrs": _to_bool(str(_first(c, 'ratematchingltecrs') or '')),
            "extras": {"bandNR": bn}
        })

    return bands


# ─── Classify bandList components ─────────────────────────────────────────────

def _classify_band_components(bl_dict: dict) -> tuple:
    """
    Given a bandList dict, return (lte_components, nr_components).

    PARSER REALITY: Inside bandList, the parser stores:
      "eutra": { bandeutra: "3,", ... }               ← first eutra entry
      ",_eutra": { bandeutra: "7,", ... }              ← second eutra (after comma)
      ",_nr": { bandnr: "78,", ... }                   ← nr entries (after comma)
      ",_nr": [{ bandnr: "78," }, { bandnr: "257," }]  ← if multiple NR entries

    So we must check ALL keys, not just "eutra" and "nr".
    Strategy: collect ALL child dicts, then classify by content.
    """
    lte_comps = []
    nr_comps = []

    if not isinstance(bl_dict, dict):
        return (lte_comps, nr_comps)

    # Collect ALL dict children from bandList (handles all key patterns)
    all_children = _all_child_dicts(bl_dict)

    for child in all_children:
        if not isinstance(child, dict):
            continue

        # Classify: does it have bandEUTRA or bandNR?
        c = _collect(child, {
            'bandEUTRA', 'bandeutra', 'band_eutra', 'bandeutra_r10',
            'bandNR', 'bandnr', 'band_nr',
            'ca-BandwidthClassDL', 'ca_bandwidthclassdl', 'cabandwidthclassdl',
            'ca-BandwidthClassDL-r10', 'ca_bandwidth_class_dl_r10', 'cabandwidthclassdlr10',
            'ca-BandwidthClassUL', 'ca_bandwidthclassul', 'cabandwidthclassul',
            'ca-BandwidthClassUL-r10', 'ca_bandwidth_class_ul_r10', 'cabandwidthclassulr10',
        })

        bn_lte = _to_int(_first(c, 'bandeutra', 'bandeutra_r10'))
        bn_nr = _to_int(_first(c, 'bandnr', 'band_nr'))

        bw_dl = _clean_str(_first(c, 'cabandwidthclassdl', 'cabandwidthclassdlr10') or '').upper() or None
        bw_ul = _clean_str(_first(c, 'cabandwidthclassul', 'cabandwidthclassulr10') or '').upper() or None

        if bn_lte is not None:
            lte_comps.append({
                "band": bn_lte,
                "bwClassDl": bw_dl,
                "bwClassUl": bw_ul,
                "mimoDl": _sv(2),
                "mimoUl": _sv(1),
                "modulationDl": _sv("qam256"),
                "modulationUl": _sv("qam64"),
            })
        elif bn_nr is not None:
            nr_comps.append({
                "band": bn_nr,
                "bwClassDl": bw_dl,
                "bwClassUl": bw_ul,
                "mimoDl": None,
                "mimoUl": _sv(1),
                "modulationDl": None,
                "modulationUl": _sv("qam256"),
                "maxScs": None,
                "maxBwDl": None,
                "maxBwUl": None,
            })

    return (lte_comps, nr_comps)


# ─── LTE CA extraction ────────────────────────────────────────────────────────

def _extract_lte_ca(eutra_tree: dict) -> list:
    combos = []
    containers = _find(eutra_tree, {
        'supportedbandcombination_r10', 'supportedbandcombinationr10',
        'supportedbandcombinationlist',
    })

    for container in containers:
        for combo_block in _blocks(container):
            if not isinstance(combo_block, dict): continue

            components = []
            # Each inner block is a component carrier
            for cc_block in _blocks(combo_block):
                if not isinstance(cc_block, dict): continue
                c = _collect(cc_block, {
                    'bandEUTRA', 'bandeutra', 'bandeutra_r10',
                    'ca-BandwidthClassDL-r10', 'cabandwidthclassdlr10',
                    'ca-BandwidthClassUL-r10', 'cabandwidthclassulr10',
                    'supportedMIMO-CapabilityDL-r10', 'supportedmimocapabilitydlr10',
                })
                bn = _to_int(_first(c, 'bandeutra', 'bandeutra_r10'))
                if bn is None: continue

                bw_dl = _clean_str(_first(c, 'cabandwidthclassdlr10') or '').upper() or None
                bw_ul = _clean_str(_first(c, 'cabandwidthclassulr10') or '').upper() or None
                mimo = _mimo_to_int(_first(c, 'supportedmimocapabilitydlr10'))

                components.append({
                    "band": bn,
                    "bwClassDl": bw_dl,
                    "bwClassUl": bw_ul,
                    "mimoDl": _sv(mimo) if mimo else None,
                    "mimoUl": _sv(1),
                    "modulationDl": _sv("qam256"),
                    "modulationUl": _sv("qam64"),
                })

            # If inner blocks didn't yield CCs, try the block itself
            if not components:
                c = _collect(combo_block, {
                    'bandeutra', 'bandeutra_r10',
                    'cabandwidthclassdlr10', 'cabandwidthclassulr10',
                    'supportedmimocapabilitydlr10',
                })
                bn = _to_int(_first(c, 'bandeutra', 'bandeutra_r10'))
                if bn is not None:
                    components.append({
                        "band": bn,
                        "bwClassDl": _clean_str(_first(c, 'cabandwidthclassdlr10') or '').upper() or None,
                        "bwClassUl": _clean_str(_first(c, 'cabandwidthclassulr10') or '').upper() or None,
                        "mimoDl": _sv(_mimo_to_int(_first(c, 'supportedmimocapabilitydlr10'))),
                        "mimoUl": _sv(1),
                        "modulationDl": _sv("qam256"),
                        "modulationUl": _sv("qam64"),
                    })

            if components:
                combos.append({"components": components, "bcs": _sv(0)})

    return combos


# ─── NR CA extraction ─────────────────────────────────────────────────────────

def _extract_nr_ca(nr_tree: dict, fsc_list: list, fs_tables: dict) -> list:
    combos = []
    containers = _find(nr_tree, {
        'supportedbandcombinationlist', 'supported_band_combination_list',
    })

    for container in containers:
        for entry in _blocks(container):
            if not isinstance(entry, dict): continue

            fsc_id = _extract_fsc_id(entry)

            # Get bandList, classify components
            bl = _get_val(entry, 'bandList', 'band_list', 'bandlist')
            if bl is None: continue

            # For NR CA, all components should be NR
            _, nr_components = _classify_band_components(bl)

            # Also check for LTE components (some NR CA combos have them)
            lte_components, _ = _classify_band_components(bl)

            # If we have direct NR entries (not via eutra/nr split), collect them
            if not nr_components:
                # bandList might directly contain bandNR entries
                for child in _all_child_dicts(bl):
                    c = _collect(child, {'bandNR', 'bandnr'})
                    bn = _to_int(_first(c, 'bandnr'))
                    if bn is not None:
                        nr_components.append({
                            "band": bn,
                            "bwClassDl": None,
                            "bwClassUl": None,
                            "mimoDl": None,
                            "mimoUl": _sv(1),
                            "modulationDl": None,
                            "modulationUl": _sv("qam256"),
                            "maxScs": None,
                            "maxBwDl": None,
                            "maxBwUl": None,
                        })

            if nr_components:
                band_list_str = ",".join(str(c["band"]) for c in nr_components)
                combos.append({
                    "components": nr_components,
                    "bcs": _sv(0),
                    "customData": [{"bandList": band_list_str, "featureSetCombination": fsc_id}]
                })

    return combos


# ─── MRDC extraction ──────────────────────────────────────────────────────────

def _extract_mrdc(mrdc_tree: dict, nr_fsc_list: list, fs_tables: dict) -> list:
    """
    Extract ALL MRDC/EN-DC band combinations.

    Uses _blocks() which now correctly collects entries from both
    _block_N keys AND comma-separated keys.
    """
    combos = []

    # Find ALL supportedBandCombinationList containers in the tree
    containers = _find(mrdc_tree, {
        'supportedbandcombinationlist', 'supported_band_combination_list',
    })

    print(f"[EXTRACT] MRDC containers found: {len(containers)}", file=sys.stderr)

    total_entries = 0

    for container in containers:
        entries = _blocks(container)
        print(f"[EXTRACT] Container entries: {len(entries)}", file=sys.stderr)
        total_entries += len(entries)

        for entry in entries:
            if not isinstance(entry, dict):
                continue

            fsc_id = _extract_fsc_id(entry)

            # Get bandList
            bl = _get_val(entry, 'bandList', 'band_list', 'bandlist')
            if bl is None:
                continue

            # Classify all children of bandList into LTE and NR components
            lte_comps, nr_comps = _classify_band_components(bl)

            if not lte_comps and not nr_comps:
                continue

            # Collect MRDC-specific parameters from entry
            dps = None
            srxt = None
            for k, v in entry.items():
                nk = _norm_key(k)
                if 'dynamicpowersharingendc' in nk:
                    dps = _clean_str(v)
                elif 'simultaneousrxtxinterbandendc' in nk:
                    srxt = _clean_str(v)

            lte_bands_str = ",".join(str(c["band"]) for c in lte_comps)
            nr_bands_str = ",".join(str(c["band"]) for c in nr_comps)
            band_list_str = f"{lte_bands_str},{nr_bands_str}".strip(',')

            combos.append({
                "componentsLte": lte_comps,
                "componentsNr": nr_comps,
                "bcsNr": _sv(0),
                "bcsEutra": _sv(0),
                "customData": [{
                    "bandList": band_list_str,
                    "featureSetCombination": fsc_id,
                    "dynamicPowerSharingENDC": dps,
                    "simultaneousRxTxInterBandENDC": srxt,
                }]
            })

    print(f"[EXTRACT] MRDC total entries scanned: {total_entries}", file=sys.stderr)
    print(f"[EXTRACT] MRDC combos extracted: {len(combos)}", file=sys.stderr)

    return combos


# ─── FeatureSet resolution ───────────────────────────────────────────────────

def _resolve_caps(fsc_id: int, fsc_list: list, tables: dict) -> dict:
    if not fsc_id or fsc_id < 1 or fsc_id > len(fsc_list):
        return {}
    fsc_entry = fsc_list[fsc_id - 1]
    dl_ids = []
    def _walk(node):
        if isinstance(node, dict):
            for k, v in node.items():
                if _norm_key(k) == 'downlinksetnr':
                    i = _to_int(v)
                    if i: dl_ids.append(i)
                else: _walk(v)
        elif isinstance(node, list):
            for item in node: _walk(item)
    _walk(fsc_entry)
    dl_list = tables.get('dl_list', [])
    per_cc = tables.get('dl_per_cc', [])
    best = {}
    for dl_id in dl_ids:
        if dl_id < 1 or dl_id > len(dl_list): continue
        fs_dl = dl_list[dl_id - 1]
        if not isinstance(fs_dl, dict): continue
        for k, v in fs_dl.items():
            nk = _norm_key(k)
            val = _clean_str(v) if isinstance(v, str) else ''
            if 'mimolayers' in nk and 'ul' not in nk:
                m = _mimo_to_int(val)
                if m and m > best.get('mimo', 0):
                    best['mimo'] = m
            elif 'modulationorderdl' in nk:
                best['mod'] = val.lower()
    return best


def _extract_fs_tables(nr_tree: dict) -> dict:
    tables = {'dl_list': [], 'dl_per_cc': [], 'ul_list': [], 'ul_per_cc': []}
    fs = _get_val(nr_tree, 'featureSets', 'feature_sets', 'featuresets')
    if not fs or not isinstance(fs, dict): return tables

    def _ordered(node):
        if isinstance(node, list): return [e for e in node if isinstance(e, dict)]
        if isinstance(node, dict):
            entries = []
            for k, v in sorted(node.items()):
                if k.startswith('_block_') and isinstance(v, dict):
                    entries.append(v)
            if entries: return entries
            return _blocks(node)
        return []

    for k, v in fs.items():
        nk = _norm_key(k)
        if nk == 'featuresetsdownlink': tables['dl_list'] = _ordered(v)
        elif nk == 'featuresetsdownlinkpercc': tables['dl_per_cc'] = _ordered(v)
        elif nk == 'featuresetsuplink': tables['ul_list'] = _ordered(v)
        elif nk == 'featuresetsuplinkpercc': tables['ul_per_cc'] = _ordered(v)

    return tables


# ─── Main extraction function ────────────────────────────────────────────────

def extract_all(text: str) -> dict:
    sections = _split_sections(text)

    eutra_tree = _unwrap(sections['eutra']) if 'eutra' in sections else {}
    mrdc_tree = _unwrap(sections['mrdc']) if 'mrdc' in sections else {}
    nr_tree = _unwrap(sections['nr']) if 'nr' in sections else {}

    if not eutra_tree and not mrdc_tree and not nr_tree:
        whole = parse_text(text)
        eutra_tree = whole
        mrdc_tree = whole
        nr_tree = whole

    fs_tables = _extract_fs_tables(nr_tree)
    nr_fsc_raw = _get_val(nr_tree, 'featureSetCombinations', 'featuresetcombinations')
    nr_fsc_list = _blocks(nr_fsc_raw) if nr_fsc_raw else []

    result = {
        "lteBands": _extract_lte_bands(eutra_tree),
        "nrBands": _extract_nr_bands(nr_tree),
        "lteca": _extract_lte_ca(eutra_tree),
        "nrca": _extract_nr_ca(nr_tree, nr_fsc_list, fs_tables),
        "mrdc": _extract_mrdc(mrdc_tree, nr_fsc_list, fs_tables),
    }

    print(f"[EXTRACT] FINAL: LTE bands={len(result['lteBands'])}, "
          f"NR bands={len(result['nrBands'])}, LTE-CA={len(result['lteca'])}, "
          f"NR-CA={len(result['nrca'])}, MRDC={len(result['mrdc'])}",
          file=sys.stderr)

    return result


if __name__ == "__main__":
    import json
    path = sys.argv[1] if len(sys.argv) > 1 else "UE_Capa.txt"
    data = extract_all(open(path, errors="replace").read())
    print(json.dumps({
        "lteBands": len(data["lteBands"]),
        "nrBands": len(data["nrBands"]),
        "lteca": len(data["lteca"]),
        "nrca": len(data["nrca"]),
        "mrdc": len(data["mrdc"]),
    }, indent=2))
