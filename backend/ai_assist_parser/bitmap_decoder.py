import re
from typing import Any, Dict, List

def extract_all_bandwidth_sources(raw_text: str) -> Dict[str, str]:
    bitmaps = {}
    pattern_scs = r"(scs-\d+kHz)\s*'([01\s]+)'B"
    for match in re.finditer(pattern_scs, raw_text, re.IGNORECASE):
        bitmaps[match.group(1).lower()] = match.group(2)
        
    pattern_generic = r"(supportedBandwidthCombinationSet)\s*'([01\s]+)'B"
    for match in re.finditer(pattern_generic, raw_text, re.IGNORECASE):
        bitmaps["merged_fallback"] = match.group(2)
        
    return bitmaps

def decode_bitmap_int(bitmap_int: int) -> List[str]:
    bandwidths = []
    if bitmap_int & 1: bandwidths.append("5MHz")
    if bitmap_int & 2: bandwidths.append("10MHz")
    if bitmap_int & 4: bandwidths.append("15MHz")
    if bitmap_int & 8: bandwidths.append("20MHz")
    if bitmap_int & 16: bandwidths.append("25MHz")
    if bitmap_int & 32: bandwidths.append("30MHz")
    if bitmap_int & 64: bandwidths.append("40MHz")
    if bitmap_int & 128: bandwidths.append("50MHz")
    if bitmap_int & 256: bandwidths.append("60MHz")
    if bitmap_int & 512: bandwidths.append("80MHz")
    if bitmap_int & 1024: bandwidths.append("100MHz")
    return bandwidths

def decode_bitmap(bitmap_str: str) -> List[str]:
    cleaned_binary = bitmap_str.replace(" ", "").replace("'", "").replace("B", "")
    if not cleaned_binary: return []
    try:
        bitmap_int = int(cleaned_binary, 2)
    except ValueError:
        return []
    return decode_bitmap_int(bitmap_int)

def refine_bandwidths(band: int, bw_list: List[str]) -> List[str]:
    # Light band filtering based on rules
    if band <= 20: 
        return [bw for bw in bw_list if bw in ["5MHz","10MHz","15MHz","20MHz"]]
    elif band <= 100: 
        return bw_list
    else: 
        # Ensure FR2 retains significant bandwidth potentials up to 400MHz
        return [bw for bw in bw_list if bw in ["50MHz","100MHz","200MHz", "400MHz"]]


def clean_ca_combinations(parsed_json: Dict[str, Any]):
    """Fix NR CA and MRDC duplicates, and mark invalid combos."""
    for ca_key in ["nrca", "lteca", "mrdc"]:
        for combo in parsed_json.get(ca_key, []):
            for cc_key in ["components", "componentsNr", "componentsLte"]:
                comps = combo.get(cc_key, [])
                if not comps: continue
                
                # Check for validity
                for comp in comps:
                    if not comp.get("bwClassDl") and not comp.get("bwClassUl"):
                        comp["_invalid_bw"] = True

                # Remove identical band duplicates preserving order
                seen = set()
                new_comps = []
                for comp in comps:
                    bn = comp.get("band")
                    bclass_dl = comp.get("bwClassDl")
                    identifier = f"{bn}_{bclass_dl}"
                    if identifier not in seen:
                        seen.add(identifier)
                        new_comps.append(comp)
                combo[cc_key] = new_comps


def fill_nr_bandwidths(parsed_json: Dict[str, Any], raw_text: str) -> Dict[str, Any]:
    sources = extract_all_bandwidth_sources(raw_text)
    
    decoded_map = {}
    for scs, bits in sources.items():
        decoded = decode_bitmap(bits)
        if decoded:
            decoded_map[scs] = decoded
            
    # Build global fallback pool
    global_pool_set = set()
    for bws in decoded_map.values(): global_pool_set.update(bws)
    
    def parse_mhz(x):
        try: return int(x.replace("MHz", ""))
        except: return 0
    global_pool = sorted(list(global_pool_set), key=parse_mhz)

    for band in parsed_json.get("nrBands", []):
        bn = band.get("band", 0)
        existing_bws = band.get("bandwidths", [])
        
        # 1. Band-specific exists from core parser? Flatten it dynamically.
        flattened_specific = []
        if existing_bws and isinstance(existing_bws, list):
            for item in existing_bws:
                if isinstance(item, str):
                    flattened_specific.append(item)
                elif isinstance(item, dict):
                    dl = item.get("bandwidthsDl", [])
                    if isinstance(dl, list): flattened_specific.extend(dl)
                    ul = item.get("bandwidthsUl", [])
                    if isinstance(ul, list): flattened_specific.extend(ul)
                    
        # Dedup preserving order
        unique_specific = []
        for x in flattened_specific:
            if x not in unique_specific: unique_specific.append(x)
            
        if unique_specific:
            band["bandwidths"] = refine_bandwidths(bn, unique_specific)
            band["bandwidth_source"] = "band_specific_bitmap"
            continue
            
        # 2. Try SCS-specific decoded map
        scs_based = []
        if bn < 100:
            scs_based = decoded_map.get("scs-15khz") or decoded_map.get("scs-30khz") or []
        else:
            scs_based = decoded_map.get("scs-60khz") or decoded_map.get("scs-120khz") or decoded_map.get("scs-240khz") or []
            
        if scs_based:
            filtered = refine_bandwidths(bn, scs_based)
            if filtered:
                band["bandwidths"] = filtered
                band["bandwidth_source"] = "scs_decoded"
                continue
                
        # 3. Try global merged pool
        if global_pool:
            filtered = refine_bandwidths(bn, global_pool)
            if filtered:
                band["bandwidths"] = filtered
                band["bandwidth_source"] = "merged_bitmap"
                continue
                
        # 4. Unknown (let AI assist flag handle it)
        band["bandwidths"] = []
        band["bandwidth_source"] = "unknown"
                
    clean_ca_combinations(parsed_json)
    return parsed_json
