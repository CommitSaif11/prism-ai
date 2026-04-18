"""
entry_point.py
==============
Step 1 — Find 'value UL-DCCH-Message' in the log file.
Returns: line number, rat-type, and header metadata.
"""

from __future__ import annotations
import re


def extract_metadata(text: str) -> dict:
    meta = {}
    patterns = {
        "pkt_version":      r"Pkt Version\s*=\s*(\S+)",
        "rrc_release":      r"RRC Release Number\.Major\.minor\s*=\s*(\S+)",
        "physical_cell_id": r"Physical Cell ID\s*=\s*(\d+)",
        "freq":             r"Freq\s*=\s*(\d+)",
    }
    for key, pattern in patterns.items():
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            meta[key] = m.group(1)
    return meta


def find_entry_point(text: str) -> dict:
    lines = text.splitlines()
    entry_line = None
    rat_type = None

    for i, line in enumerate(lines):
        if re.search(r'value\s+UL-DCCH-Message', line, re.IGNORECASE):
            entry_line = i + 1
        if entry_line and rat_type is None:
            m = re.search(r'rat-Type\s+(\S+)', line, re.IGNORECASE)
            if m:
                rat_type = m.group(1).strip().lower().rstrip(',')
        if entry_line and rat_type:
            break

    return {
        "entry_line": entry_line,
        "rat_type":   rat_type or "unknown",
        "metadata":   extract_metadata(text),
        "found":      entry_line is not None,
    }


if __name__ == "__main__":
    import sys
    path = sys.argv[1] if len(sys.argv) > 1 else "UE_Capa.txt"
    result = find_entry_point(open(path, errors="replace").read())
    print(f"Entry line : {result['entry_line']}")
    print(f"RAT type   : {result['rat_type']}")
    print(f"Metadata   : {result['metadata']}")
