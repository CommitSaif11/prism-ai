"""
inference.py
============
Main orchestrator. Run this file.

Usage:
    python inference.py --input UE_Capa.txt --output result.json
"""

from __future__ import annotations
import argparse, json, os, sys, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from entry_point        import find_entry_point
from sequential_extractor import extract_all
from output_formatter   import format_output, validate_output
from confidence_engine  import score_output


def run(input_path: str, output_path: str = "result.json", force_llm: bool = False) -> dict:
    print(f"\n{'='*55}")
    print(f"  Samsung PRISM — UE Capability Parser")
    print(f"  Input : {input_path}")
    print(f"{'='*55}\n")

    # ── Read file ──────────────────────────────────────────────
    if not os.path.exists(input_path):
        print(f"[ERROR] File not found: {input_path}")
        sys.exit(1)

    t_read = time.perf_counter()
    text = open(input_path, errors="replace").read()
    source_file = os.path.basename(input_path)
    print(f"[TIME] File Read:          {time.perf_counter() - t_read:.4f}s")
    print(f"[DEBUG] File size:         {len(text)} chars  ({len(text.encode())} bytes)")

    # ── Grand-total clock starts here ──────────────────────────
    start_total = time.perf_counter()

    # ── Step 1: Entry point ────────────────────────────────────
    print("\n[1/4] Locating UL-DCCH-Message entry point...")
    t = time.perf_counter()
    entry_info = find_entry_point(text)
    print(f"[TIME] Entry Point:        {time.perf_counter() - t:.4f}s")

    if not entry_info["found"]:
        print("[WARN] UL-DCCH-Message not found. Attempting full parse.")
    else:
        print(f"      Entry line : {entry_info['entry_line']}")
        print(f"      RAT type   : {entry_info['rat_type']}")
        print(f"      Metadata   : {entry_info['metadata']}")

    # ── Step 2: Sequential extraction ─────────────────────────
    print("\n[2/4] Extracting all parameters (rule-based)...")
    t = time.perf_counter()
    extracted = extract_all(text)
    print(f"[TIME] Rule-Based Parser:  {time.perf_counter() - t:.4f}s")
    print(f"      LTE bands  : {len(extracted['lteBands'])}")
    print(f"      NR bands   : {len(extracted['nrBands'])}")
    print(f"      LTE CA     : {len(extracted['lteca'])}")
    print(f"      NR CA      : {len(extracted['nrca'])}")
    print(f"      MRDC       : {len(extracted['mrdc'])}")
    print(f"[DEBUG] NR bands count :   {len(extracted['nrBands'])}")
    print(f"[DEBUG] NR CA combos   :   {len(extracted['nrca'])}")
    print(f"[DEBUG] MRDC combos    :   {len(extracted['mrdc'])}")

    # ── Step 2b: AI Gap-Fill (bandwidth only, controlled, batched per band) ──
    from ai_assist import ai_fill_gaps
    t = time.perf_counter()
    extracted = ai_fill_gaps(text, extracted)
    print(f"[TIME] AI Gap-Fill:        {time.perf_counter() - t:.4f}s")

    # ── Step 3: Format output ──────────────────────────────────
    print("\n[3/4] Formatting output...")
    t = time.perf_counter()
    output = format_output(extracted, entry_info, source_file)
    print(f"[TIME] Format Output:      {time.perf_counter() - t:.4f}s")

    # ── Confidence scoring ─────────────────────────────────────
    t = time.perf_counter()
    confidence = score_output(output)
    output["metadata"]["confidence_score"]    = confidence["score"]
    output["metadata"]["confidence_decision"] = confidence["decision"]
    output["validation"] = confidence
    print(f"[TIME] Confidence Score:   {time.perf_counter() - t:.4f}s")

    print(f"      Confidence : {confidence['score']} ({confidence['decision']})")
    if confidence["flags"]:
        for flag in confidence["flags"]:
            print(f"      ⚠  {flag}")

    # ── Step 4: LLM Fallback if needed ────────────────────────
    if force_llm or confidence["decision"] == "retry":
        print("\n[4/4] Rule-based confidence low. Activating LLM fallback (Mistral-7B)...")
        t = time.perf_counter()
        from llm_fallback import run_llm_fallback
        llm_result = run_llm_fallback(text)
        print(f"[TIME] LLM Fallback:       {time.perf_counter() - t:.4f}s")

        if llm_result:
            # Merge: use LLM result but keep metadata from rule-based
            meta = output["metadata"]
            output = llm_result
            output["metadata"] = meta
            output["metadata"]["extraction_method"] = "llm-mistral-7b"

            # Re-score
            t = time.perf_counter()
            confidence = score_output(output)
            output["metadata"]["confidence_score"] = confidence["score"]
            output["validation"] = confidence
            print(f"[TIME] Re-score after LLM: {time.perf_counter() - t:.4f}s")
            print(f"      LLM confidence: {confidence['score']} ({confidence['decision']})")
        else:
            print("      LLM fallback failed. Keeping rule-based output.")
    else:
        print("\n[4/4] Rule-based extraction accepted (no LLM needed).")

    # ── Write result ───────────────────────────────────────────
    t = time.perf_counter()
    with open(output_path, "w") as f:
        json.dump(output, f, indent=2, default=str)
    serialized = json.dumps(output, default=str)
    print(f"[TIME] JSON Serialize+Write:{time.perf_counter() - t:.4f}s")
    print(f"[DEBUG] Response size:     {len(serialized)} bytes")

    # ── AI call summary ────────────────────────────────────────
    try:
        from ai_processor import ai_call_count
        print(f"[AI]   Total AI calls:     {ai_call_count}")
    except Exception:
        pass

    elapsed = round(time.perf_counter() - start_total, 4)
    print(f"\n{'='*55}")
    print(f"  ✅  Done in {elapsed}s  →  {output_path}")
    print(f"  [TOTAL] Request time: {elapsed}s")
    print(f"{'='*55}\n")

    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Samsung PRISM UE Capability Parser")
    parser.add_argument("--input",  default="UE_Capa.txt", help="Input log file")
    parser.add_argument("--output", default="result.json",  help="Output JSON file")
    parser.add_argument("--llm",    action="store_true",    help="Force LLM fallback")
    args = parser.parse_args()
    run(args.input, args.output, force_llm=args.llm)
