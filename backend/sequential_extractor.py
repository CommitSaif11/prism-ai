"""
sequential_extractor.py  v5.0  — FINAL
========================================
Key fix in v5: channelBWs-DL bitmask extraction uses REGEX on raw text,
NOT the parsed tree. This bypasses the tokenizer bug where spaces inside
bit strings ('00010111 11'B) cause the parser to split the value incorrectly.

All other key paths verified from real log inspection.
"""

from __future__ import annotations
import re, sys, os
from typing import Any, Dict, List, Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from asn_parser import parse_text, _norm

# ─── Helpers ─────────────────────────────────────────────────────────────────

def _nk(k): return re.sub(r'[^a-z0-9]', '', str(k).lower())
def _to_int(s):
    if s is None: return None
    try: return int(re.sub(r'[^0-9-]', '', str(s).strip().rstrip(',')))
    except: return None
def _to_bool(s):
    if isinstance(s, bool): return s
    v = str(s).lower().strip().rstrip(',')
    if v in ('true','yes','1','supported'): return True
    if v in ('false','no','0','notsupported'): return False
    return None
def _clean(v): return str(v).strip().rstrip(',').strip() if v is not None else ''
def _sv(val): return {"type":"single","value":val} if val is not None else None
def _mimo_to_int(s):
    if not s: return None
    v = _clean(str(s))
    if v.isdigit(): return int(v)
    c = _nk(v)
    return {'onelayer':1,'twolayers':2,'fourlayers':4,'eightlayers':8,
            'one':1,'two':2,'four':4,'eight':8}.get(c)
def _parse_bw_mhz(s):
    if not s: return None
    m = re.search(r'mhz(\d+)', str(s), re.I)
    if m: return int(m.group(1))
    m = re.match(r'^\s*(\d+)\s*$', _clean(str(s)))
    if m: return int(m.group(1))
    return None

# ─── Tree navigation ──────────────────────────────────────────────────────────

def _blocks(node) -> list:
    if node is None: return []
    if isinstance(node, list): return [x for x in node if isinstance(x, dict)]
    if isinstance(node, dict):
        bkeys = sorted([k for k in node if k.startswith('_block_')],
                       key=lambda k: int(k.split('_')[2]) if k.split('_')[2].isdigit() else 0)
        if bkeys:
            result = []
            for k in bkeys:
                v = node[k]
                if isinstance(v, dict): result.append(v)
                elif isinstance(v, list): result.extend(x for x in v if isinstance(x, dict))
            return result
        vals = list(node.values())
        if len(vals) == 1 and isinstance(vals[0], list):
            return [x for x in vals[0] if isinstance(x, dict)]
        return [node]
    return []

def _get(d, *keys):
    if not isinstance(d, dict): return None
    for rk in keys:
        target = _nk(rk)
        for k, v in d.items():
            if _nk(k) == target: return v
    return None

def _find_all(tree, *keys) -> list:
    result = []
    targets = {_nk(k) for k in keys}
    def _walk(node):
        if isinstance(node, dict):
            for k, v in node.items():
                if _nk(k) in targets:
                    if isinstance(v, list): result.extend(v)
                    else: result.append(v)
                _walk(v)
        elif isinstance(node, list):
            for item in node: _walk(item)
    _walk(tree)
    return result

def _unwrap(raw):
    parsed = parse_text(raw)
    eq = parsed.get('=')
    if isinstance(eq, list) and eq and isinstance(eq[0], dict): return eq[0]
    if isinstance(eq, dict): return eq
    return parsed

# ─── Section splitter ─────────────────────────────────────────────────────────

_SEC_PAT = {
    'mrdc':  re.compile(r'value\s+UE-MRDC-Capability(?:-v\w+)?\s*::=', re.IGNORECASE),
    'eutra': re.compile(r'value\s+UE-EUTRA-Capability(?:-v\w+)?\s*::=', re.IGNORECASE),
    'nr':    re.compile(r'value\s+UE-NR-Capability(?:-v\w+)?\s*::=', re.IGNORECASE),
}

def _split_sections(text):
    lines = text.splitlines(keepends=True)
    hits = {}
    for i, line in enumerate(lines):
        for name, pat in _SEC_PAT.items():
            if pat.search(line) and name not in hits: hits[name] = i
    if not hits: return {}
    ordered = sorted(hits.items(), key=lambda x: x[1])
    result = {}
    for idx, (name, start) in enumerate(ordered):
        end = ordered[idx+1][1] if idx+1 < len(ordered) else len(lines)
        result[name] = ''.join(lines[start:end])
    return result

# ─── BW bitmask tables ────────────────────────────────────────────────────────

_BW_TABLES = {
    15:  [5, 10, 15, 20, 25, 30, 40, 50],
    30:  [5, 10, 15, 20, 25, 40, 50, 60, 80, 100],
    60:  [10, 15, 20, 25, 40, 50, 60, 80, 100],
    120: [50, 100, 200, 400],
    240: [400],
}

def _decode_bitmask(bits_str, scs):
    clean = re.sub(r'[^01]', '', str(bits_str))
    table = _BW_TABLES.get(scs, [])
    return [table[i] for i, bit in enumerate(clean) if bit == '1' and i < len(table)]

# ─── CRITICAL: Raw-text BW extraction ────────────────────────────────────────
# Bypasses the parser entirely for channelBWs bitmasks.
# Reason: the parser tokenizer splits '00010111 11'B on the space,
#         producing broken key fragments. Regex on raw text is reliable.

def _extract_bws_from_raw(raw_nr_text, band_num) -> List[dict]:
    """
    Extract channelBWs-DL for one NR band from raw NR section text.
    Handles spaces inside bit strings correctly.
    """
    m = re.search(rf'bandNR\s+{band_num}\b', raw_nr_text, re.IGNORECASE)
    if not m: return []

    rest = raw_nr_text[m.start():]
    next_band = re.search(r'bandNR\s+\d+\b', rest[10:], re.IGNORECASE)
    chunk = rest[:next_band.start()+10] if next_band else rest[:6000]

    # Match: channelBWs-DL fr1 : { scs-30kHz '...'B, ... }
    bw_pattern = r'channelBWs-DL\s+\w+\s*:\s*\{([^}]+)\}'
    bw_match   = re.search(bw_pattern, chunk, re.IGNORECASE | re.DOTALL)
    if not bw_match: return []

    bw_block = bw_match.group(1)
    bws = []

    # scs-30kHz '00010111 11'B  (note: space inside the bit string is valid)
    scs_pat = r"scs[-_](\d+)kHz\s+'([01][01\s]*)'\s*[Bb]"
    for scs_m in re.finditer(scs_pat, bw_block, re.IGNORECASE):
        scs_val = int(scs_m.group(1))
        decoded = _decode_bitmask(scs_m.group(2), scs_val)
        if decoded:
            bws.append({"scs": scs_val, "bandwidthsDl": decoded, "bandwidthsUl": decoded})

    return bws

def _build_band_bw_map(raw_nr_text, band_nums) -> dict:
    """Build {band_num: [bw_entries]} for all NR bands using raw text."""
    return {bn: _extract_bws_from_raw(raw_nr_text, bn) for bn in band_nums}

# ─── featureSet tables ────────────────────────────────────────────────────────

def _build_fs_tables(nr_tree):
    tables = {'dl_list': [], 'dl_per_cc': [], 'ul_list': [], 'ul_per_cc': []}
    fs = _get(nr_tree, 'featureSets', 'featuresets')
    if not fs or not isinstance(fs, dict): return tables

    def _ordered(node):
        if isinstance(node, list): return [e for e in node if isinstance(e, dict)]
        if isinstance(node, dict):
            bkeys = [(k, v) for k, v in node.items() if re.match(r'_block_\d+$', k)]
            if bkeys:
                return [v for _, v in sorted(bkeys, key=lambda x: int(x[0].split('_')[2]))]
            return [node]
        return []

    for k, v in fs.items():
        nk = _nk(k)
        if   nk == 'featuresetsdownlink':        tables['dl_list']   = _ordered(v)
        elif nk == 'featuresetsdownlinkpercc':   tables['dl_per_cc'] = _ordered(v)
        elif nk == 'featuresetsuplink':          tables['ul_list']   = _ordered(v)
        elif nk == 'featuresetsuplinkpercc':     tables['ul_per_cc'] = _ordered(v)
    return tables

def _resolve_percc(dl_id, dl_list, percc_list):
    if dl_id < 1 or dl_id > len(dl_list): return {}
    dl_entry = dl_list[dl_id - 1]
    if not isinstance(dl_entry, dict): return {}

    per_cc_id = None
    for k, v in dl_entry.items():
        if 'featuresetlistperdownlinkcc' in _nk(k):
            if isinstance(v, dict):
                first_key = next(iter(v.keys()), None)
                try: per_cc_id = int(_clean(first_key)) if first_key else None
                except: per_cc_id = None
            else:
                try: per_cc_id = int(_clean(str(v)))
                except: per_cc_id = None
            break

    if not per_cc_id or per_cc_id < 1 or per_cc_id > len(percc_list): return {}
    percc = percc_list[per_cc_id - 1]
    if not isinstance(percc, dict): return {}

    result = {}
    for k, v in percc.items():
        nk = _nk(k); val = _clean(v)
        if   nk == 'maxnumbermimolayerspdsch':   result['mimo']   = _mimo_to_int(val)
        elif nk == 'supportedmodulationorderdl': result['mod_dl'] = val.lower()
        elif nk == 'supportedbandwidthdl':       result['bw_mhz'] = _parse_bw_mhz(val)
        elif nk == 'supportedsubcarrierspacingdl': result['scs']  = val
    return result

def _get_all_dl_ids(fsc_entry):
    ids = []
    def _walk(node):
        if isinstance(node, dict):
            for k, v in node.items():
                if _nk(k) == 'downlinksetnr':
                    i = _to_int(v)
                    if i: ids.append(i)
                else: _walk(v)
        elif isinstance(node, list):
            for item in node: _walk(item)
    _walk(fsc_entry)
    return ids

# ─── LTE: build caps from CA combos ──────────────────────────────────────────

def _build_lte_band_caps_from_ca(eutra_tree):
    band_caps = {}
    for container in _find_all(eutra_tree, 'supportedbandcombination_r10',
                               'supportedbandcombinationr10'):
        for combo_block in _blocks(container):
            for cc_block in _blocks(combo_block):
                if not isinstance(cc_block, dict): continue
                bn = _to_int(_clean(_get(cc_block, 'bandeutra_r10', 'bandeutra') or ''))
                if bn is None: continue
                dl_params = _get(cc_block, 'bandparametersdl_r10', 'bandparametersdl')
                dl_entry  = _blocks(dl_params)[0] if dl_params and _blocks(dl_params) else {}
                mimo_dl   = _mimo_to_int(_clean(
                    _get(dl_entry, 'supportedmimo_capabilitydl_r10', 'supportedmimocapabilitydl') or ''))
                if bn not in band_caps:
                    band_caps[bn] = {'mimo_dl': mimo_dl, 'mimo_ul': 1}
                elif mimo_dl and mimo_dl > (band_caps[bn].get('mimo_dl') or 0):
                    band_caps[bn]['mimo_dl'] = mimo_dl
    return band_caps

def _extract_lte_bands(eutra_tree):
    bands, seen = [], set()
    rf = _get(eutra_tree, 'rf_parameters', 'rfparameters')
    band_list_node = (_get(rf, 'supportedbandlisteutra') if rf else None) or \
                     ((_find_all(eutra_tree, 'supportedbandlisteutra') or [None])[0])

    band_caps    = _build_lte_band_caps_from_ca(eutra_tree)
    global_dl256 = any(_to_bool(_clean(str(v))) for v in
                       _find_all(eutra_tree, 'dl_256qam_r12', 'dl256qamr12'))
    global_ul64  = any(_to_bool(_clean(str(v))) for v in
                       _find_all(eutra_tree, 'ul_64qam_r12', 'ul64qamr12'))

    def _add(bn, hd=None):
        if bn in seen: return
        seen.add(bn)
        caps = band_caps.get(bn, {})
        bands.append({
            "band":         bn,
            "mimoDl":       _sv(caps.get('mimo_dl')) if caps.get('mimo_dl') else None,
            "mimoUl":       _sv(caps.get('mimo_ul', 1)),
            "modulationDl": _sv("qam256") if global_dl256 else None,
            "modulationUl": _sv("qam64")  if global_ul64  else None,
            "powerClass":   None,
            "extras": {
                "bandEUTRA":           bn,
                "halfDuplex":          hd if hd is not None else False,
                "v1250_dl-256QAM-r12": "supported" if global_dl256 else "",
                "v1250_ul-64QAM-r12":  "supported" if global_ul64  else "",
            }
        })

    if band_list_node:
        for entry in _blocks(band_list_node):
            if not isinstance(entry, dict): continue
            bn = _to_int(_clean(_get(entry, 'bandeutra', 'bandeutra_r10') or ''))
            if bn is None: continue
            hd = _to_bool(_clean(_get(entry, 'halfduplex', 'half_duplex') or ''))
            _add(bn, hd)

    # DFS fallback for any missed bands
    for v in _find_all(eutra_tree, 'bandeutra', 'bandeutra_r10'):
        bn = _to_int(_clean(str(v)))
        if bn and 1 <= bn <= 700: _add(bn)

    return bands

# ─── NR: build caps from featureSet chain ────────────────────────────────────

def _build_nr_band_caps(nr_tree, fsc_list, fs_tables):
    band_best = {}
    dl_list, per_cc = fs_tables.get('dl_list',[]), fs_tables.get('dl_per_cc',[])

    rf = _get(nr_tree, 'rf_parameters', 'rfparameters')
    containers = ([_get(rf, 'supportedbandcombinationlist')] if rf and
                  _get(rf, 'supportedbandcombinationlist') else []) or \
                 _find_all(nr_tree, 'supportedbandcombinationlist')

    for container in containers:
        for entry in _blocks(container):
            if not isinstance(entry, dict): continue
            fsc_id = _to_int(_clean(_get(entry, 'featuresetcombination') or ''))
            if not fsc_id or fsc_id < 1 or fsc_id > len(fsc_list): continue

            dl_ids = _get_all_dl_ids(fsc_list[fsc_id - 1])
            bl = _get(entry, 'bandlist', 'band_list')
            nr_bands = []
            if isinstance(bl, dict):
                nr_node = _get(bl, 'nr')
                for item in ([nr_node] if isinstance(nr_node, dict) else
                             (nr_node if isinstance(nr_node, list) else [])):
                    bn = _to_int(_clean(_get(item, 'bandnr') or '')) if isinstance(item, dict) else None
                    if bn: nr_bands.append(bn)
            if not nr_bands:
                for bnode in _find_all(entry, 'bandnr'):
                    bn = _to_int(_clean(str(bnode)))
                    if bn: nr_bands.append(bn)

            valid_caps = [c for c in [_resolve_percc(d, dl_list, per_cc) for d in dl_ids] if c]
            if not valid_caps: continue
            primary = max(valid_caps, key=lambda c: c.get('bw_mhz') or 0)

            for bn in nr_bands:
                b = band_best.setdefault(bn, {'mimo':0,'mod_dl':None,'bw_mhz':0})
                bw = primary.get('bw_mhz') or 0
                if bw > b['bw_mhz']:
                    b.update({'bw_mhz': bw,
                              'mimo':   primary.get('mimo') or b['mimo'],
                              'mod_dl': primary.get('mod_dl') or b['mod_dl']})
                elif primary.get('mimo') and primary['mimo'] > b['mimo']:
                    b['mimo'] = primary['mimo']
    return band_best

def _extract_nr_bands(nr_tree, fsc_list, fs_tables, raw_nr_text=''):
    bands, seen = [], set()
    band_best = _build_nr_band_caps(nr_tree, fsc_list, fs_tables)

    containers = _find_all(nr_tree, 'supportedbandlistnr', 'bandlist')
    entries = []
    for c in containers: entries.extend(_blocks(c))

    # Build BW map from raw text (bypasses tokenizer bug)
    all_band_nums = []
    for entry in entries:
        if isinstance(entry, dict):
            bn = _to_int(_clean(_get(entry, 'bandnr', 'band_nr') or ''))
            if bn: all_band_nums.append(bn)
    bw_map = _build_band_bw_map(raw_nr_text, all_band_nums) if raw_nr_text else {}

    for entry in entries:
        if not isinstance(entry, dict): continue
        bn = _to_int(_clean(_get(entry, 'bandnr', 'band_nr') or ''))
        if bn is None or bn in seen: continue
        seen.add(bn)

        mimo_params = _get(entry, 'mimo_parametersperband', 'mimoparametersperband') or {}
        pc        = _clean(_get(mimo_params, 'ue_powerclass', 'uepowerclass') or '') or \
                    _clean(_get(entry,        'ue_powerclass', 'uepowerclass') or '') or None
        multi_tci = _clean(_get(mimo_params, 'multipletci') or '') or \
                    _clean(_get(entry,        'multipletci') or '') or None
        rate_match= _to_bool(_clean(_get(entry, 'ratematchingltecrs') or ''))
        pusch_256 = _clean(_get(entry, 'pusch_256qam', 'pusch256qam') or '') or None

        caps = band_best.get(bn, {})
        bws  = bw_map.get(bn, [])

        bands.append({
            "band":               bn,
            "mimoDl":             _sv(caps.get('mimo'))   if caps.get('mimo')   else None,
            "mimoUl":             None,
            "modulationDl":       _sv(caps.get('mod_dl')) if caps.get('mod_dl') else None,
            "modulationUl":       _sv("qam256"),
            "powerClass":         pc,
            "bandwidths":         bws,
            "rateMatchingLteCrs": rate_match,
            "extras": {
                "bandNR":                     bn,
                "multipleTCI":                multi_tci,
                "pusch-256QAM":               pusch_256,
                "pucch-SpatialRelInfoMAC-CE":  _clean(_get(entry,'pucchspatialrelinfomacce') or '') or None,
            }
        })
    return bands

# ─── LTE CA ───────────────────────────────────────────────────────────────────

def _extract_lte_ca(eutra_tree):
    combos = []
    for container in _find_all(eutra_tree, 'supportedbandcombination_r10',
                               'supportedbandcombinationr10', 'supportedbandcombinationlist'):
        for combo_block in _blocks(container):
            if not isinstance(combo_block, dict): continue
            components = []
            for cc_block in _blocks(combo_block):
                if not isinstance(cc_block, dict): continue
                bn = _to_int(_clean(_get(cc_block, 'bandeutra_r10', 'bandeutra') or ''))
                if bn is None: continue

                dl_params = _get(cc_block, 'bandparametersdl_r10', 'bandparametersdl')
                dl_entry  = (_blocks(dl_params)[0] if dl_params and _blocks(dl_params)
                             else (dl_params if isinstance(dl_params,dict) else {}))
                bw_dl   = _clean(_get(dl_entry, 'ca_bandwidthclassdl_r10', 'cabandwidthclassdl') or '').upper() or None
                mimo_dl = _mimo_to_int(_get(dl_entry, 'supportedmimo_capabilitydl_r10', 'supportedmimocapabilitydl'))

                ul_params = _get(cc_block, 'bandparametersul_r10', 'bandparametersul')
                ul_entry  = (_blocks(ul_params)[0] if ul_params and _blocks(ul_params)
                             else (ul_params if isinstance(ul_params,dict) else {}))
                bw_ul = _clean(_get(ul_entry, 'ca_bandwidthclassul_r10', 'cabandwidthclassul') or '').upper() or None

                components.append({
                    "band":         bn,
                    "bwClassDl":    bw_dl,
                    "bwClassUl":    bw_ul,
                    "mimoDl":       _sv(mimo_dl) if mimo_dl else None,
                    "mimoUl":       _sv(1),
                    "modulationDl": _sv("qam256"),
                    "modulationUl": _sv("qam64"),
                })
            if components:
                combos.append({"components": components, "bcs": _sv(0)})
    return combos

# ─── NR CA ────────────────────────────────────────────────────────────────────

def _extract_nr_ca(nr_tree, fsc_list, fs_tables):
    combos = []
    dl_list, per_cc = fs_tables.get('dl_list',[]), fs_tables.get('dl_per_cc',[])

    rf = _get(nr_tree, 'rf_parameters', 'rfparameters')
    containers = ([_get(rf,'supportedbandcombinationlist')] if rf and
                  _get(rf,'supportedbandcombinationlist') else []) or \
                 _find_all(nr_tree, 'supportedbandcombinationlist')

    for container in containers:
        for entry in _blocks(container):
            if not isinstance(entry, dict): continue
            fsc_id = _to_int(_clean(_get(entry,'featuresetcombination') or ''))
            bl = _get(entry, 'bandlist', 'band_list')
            if bl is None: continue

            nr_components = []
            nr_node = _get(bl, 'nr')
            for item in ([nr_node] if isinstance(nr_node,dict) else
                         (nr_node if isinstance(nr_node,list) else [])):
                if not isinstance(item, dict): continue
                bn    = _to_int(_clean(_get(item,'bandnr','band_nr') or ''))
                bw_dl = _clean(_get(item,'ca_bandwidthclassdl_nr','ca_bandwidthclassdl') or '').upper() or None
                bw_ul = _clean(_get(item,'ca_bandwidthclassul_nr','ca_bandwidthclassul') or '').upper() or None
                if bn: nr_components.append({"band":bn,"bwClassDl":bw_dl,"bwClassUl":bw_ul})

            if not nr_components: continue

            caps = {}
            if fsc_id and 0 < fsc_id <= len(fsc_list):
                valid = [c for c in [_resolve_percc(d,dl_list,per_cc)
                                     for d in _get_all_dl_ids(fsc_list[fsc_id-1])] if c]
                if valid: caps = max(valid, key=lambda c: c.get('bw_mhz') or 0)

            scs_int = (int(re.search(r'(\d+)', caps['scs']).group(1))
                       if caps.get('scs') and re.search(r'(\d+)', caps.get('scs','')) else None)

            combos.append({
                "components": [{
                    "band":         c["band"],
                    "bwClassDl":    c["bwClassDl"],
                    "bwClassUl":    c["bwClassUl"],
                    "mimoDl":       _sv(caps.get('mimo'))   if caps.get('mimo')   else None,
                    "mimoUl":       _sv(1),
                    "modulationDl": _sv(caps.get('mod_dl')) if caps.get('mod_dl') else None,
                    "modulationUl": _sv("qam256"),
                    "maxScs":       scs_int,
                    "maxBwDl":      _sv(caps.get('bw_mhz')) if caps.get('bw_mhz') else None,
                    "maxBwUl":      _sv(caps.get('bw_mhz')) if caps.get('bw_mhz') else None,
                } for c in nr_components],
                "bcs":        _sv(0),
                "customData": [{"bandList": ",".join(str(c["band"]) for c in nr_components),
                                "featureSetCombination": fsc_id}],
            })
    return combos

# ─── MRDC ─────────────────────────────────────────────────────────────────────

def _extract_mrdc(mrdc_tree, nr_fsc_list, fs_tables):
    combos = []
    dl_list, per_cc = fs_tables.get('dl_list',[]), fs_tables.get('dl_per_cc',[])

    mrdc_fsc_raw  = _get(mrdc_tree, 'featuresetcombinations', 'featureSetCombinations')
    mrdc_fsc_list = _blocks(mrdc_fsc_raw) if mrdc_fsc_raw else []

    for container in _find_all(mrdc_tree, 'supportedbandcombinationlist'):
        for entry in _blocks(container):
            if not isinstance(entry, dict): continue
            fsc_id = _to_int(_clean(_get(entry,'featuresetcombination') or ''))
            bl = _get(entry, 'bandlist', 'band_list')
            if bl is None: continue

            # LTE components
            lte_comps = []
            eutra_node = _get(bl, 'eutra')
            for item in ([eutra_node] if isinstance(eutra_node,dict) else
                         (eutra_node if isinstance(eutra_node,list) else [])):
                if not isinstance(item, dict): continue
                bn    = _to_int(_clean(_get(item,'bandeutra','bandeutra_r10') or ''))
                if bn is None: continue
                bw_dl = _clean(_get(item,'ca_bandwidthclassdl_eutra','ca_bandwidthclassdl') or '').upper() or None
                bw_ul = _clean(_get(item,'ca_bandwidthclassul_eutra','ca_bandwidthclassul') or '').upper() or None
                lte_comps.append({"band":bn,"bwClassDl":bw_dl,"bwClassUl":bw_ul,
                                   "mimoDl":_sv(2),"mimoUl":_sv(1),
                                   "modulationDl":_sv("qam256"),"modulationUl":_sv("qam64")})

            # NR components
            nr_comps = []
            nr_node = _get(bl, 'nr')
            for item in ([nr_node] if isinstance(nr_node,dict) else
                         (nr_node if isinstance(nr_node,list) else [])):
                if not isinstance(item, dict): continue
                bn    = _to_int(_clean(_get(item,'bandnr','band_nr') or ''))
                if bn is None: continue
                bw_dl = _clean(_get(item,'ca_bandwidthclassdl_nr','ca_bandwidthclassdl') or '').upper() or None
                bw_ul = _clean(_get(item,'ca_bandwidthclassul_nr','ca_bandwidthclassul') or '').upper() or None

                caps = {}
                fsc_list_use = mrdc_fsc_list if mrdc_fsc_list else nr_fsc_list
                if fsc_id and 0 < fsc_id <= len(fsc_list_use):
                    is_mmwave = bn >= 257
                    valid = [c for c in [_resolve_percc(d,dl_list,per_cc)
                                         for d in _get_all_dl_ids(fsc_list_use[fsc_id-1])] if c]
                    if valid:
                        valid = ([c for c in valid if 'khz120' in _nk(c.get('scs','')) or
                                   'khz240' in _nk(c.get('scs',''))] if is_mmwave else
                                 [c for c in valid if 'khz120' not in _nk(c.get('scs',''))])
                        if valid:
                            caps = max(valid, key=lambda c: c.get('bw_mhz') or 0)

                scs_int = (int(re.search(r'(\d+)',caps['scs']).group(1))
                           if caps.get('scs') and re.search(r'(\d+)',caps.get('scs','')) else None)
                nr_comps.append({"band":bn,"bwClassDl":bw_dl,"bwClassUl":bw_ul,
                                  "mimoDl":_sv(caps.get('mimo')) if caps.get('mimo') else None,
                                  "mimoUl":_sv(1),
                                  "modulationDl":_sv(caps.get('mod_dl')) if caps.get('mod_dl') else None,
                                  "modulationUl":_sv("qam256"),
                                  "maxScs":scs_int,
                                  "maxBwDl":_sv(caps.get('bw_mhz')) if caps.get('bw_mhz') else None,
                                  "maxBwUl":_sv(caps.get('bw_mhz')) if caps.get('bw_mhz') else None})

            if not lte_comps and not nr_comps: continue

            mrdc_params = _get(entry, 'mrdc_parameters', 'mrdcparameters') or {}
            dps  = _clean(_get(mrdc_params,'dynamicpowersharingendc') or '') or None
            srxt = _clean(_get(mrdc_params,'simultaneousrxtxinterbandendc') or '') or None

            combos.append({
                "componentsLte": lte_comps,
                "componentsNr":  nr_comps,
                "bcsNr":         _sv(0),
                "bcsEutra":      _sv(0),
                "customData": [{
                    "bandList": f"{','.join(str(c['band']) for c in lte_comps)},"
                                f"{','.join(str(c['band']) for c in nr_comps)}".strip(','),
                    "featureSetCombination":         fsc_id,
                    "dynamicPowerSharingENDC":        dps,
                    "simultaneousRxTxInterBandENDC":  srxt,
                }],
            })
    return combos

# ─── Main ─────────────────────────────────────────────────────────────────────

def extract_all(text: str) -> dict:
    sections = _split_sections(text)
    eutra_tree = _unwrap(sections['eutra']) if 'eutra' in sections else {}
    mrdc_tree  = _unwrap(sections['mrdc'])  if 'mrdc'  in sections else {}
    nr_tree    = _unwrap(sections['nr'])    if 'nr'    in sections else {}

    if not eutra_tree and not mrdc_tree and not nr_tree:
        whole = parse_text(text)
        eutra_tree = mrdc_tree = nr_tree = whole

    fs_tables = _build_fs_tables(nr_tree)
    fsc_raw   = _get(nr_tree, 'featuresetcombinations', 'featureSetCombinations')
    fsc_list  = _blocks(fsc_raw) if fsc_raw else []

    # Raw NR section text for bitmask extraction (bypasses tokenizer bug)
    raw_nr_text = sections.get('nr', text)

    result = {
        "lteBands": _extract_lte_bands(eutra_tree),
        "nrBands":  _extract_nr_bands(nr_tree, fsc_list, fs_tables, raw_nr_text),
        "lteca":    _extract_lte_ca(eutra_tree),
        "nrca":     _extract_nr_ca(nr_tree, fsc_list, fs_tables),
        "mrdc":     _extract_mrdc(mrdc_tree, fsc_list, fs_tables),
    }

    print(f"[EXTRACT] LTE={len(result['lteBands'])} NR={len(result['nrBands'])} "
          f"LTECA={len(result['lteca'])} NRCA={len(result['nrca'])} MRDC={len(result['mrdc'])}",
          file=sys.stderr)
    return result

if __name__ == "__main__":
    import json
    path = sys.argv[1] if len(sys.argv) > 1 else "UE_Capa.txt"
    data = extract_all(open(path, errors='replace').read())
    print(json.dumps({k: len(v) for k, v in data.items()}, indent=2))
    if data['lteBands']: print("\nLTE B0:", json.dumps(data['lteBands'][0],  indent=2))
    if data['nrBands']:  print("\nNR B0:",  json.dumps(data['nrBands'][0],   indent=2))
    if data['lteca']:    print("\nCA0:",    json.dumps(data['lteca'][0],     indent=2))
    if data['mrdc']:     print("\nMRDC0:",  json.dumps(data['mrdc'][0],      indent=2))