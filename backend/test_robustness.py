import json
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))
from sequential_extractor import extract_all
from ai_assist import ai_fill_gaps

# ── Test 1: Complex MRDC Input (No explicit band list, just combos) ─────────
TEST_1_MRDC = """
value UE-MRDC-Capability ::= {
    supportedBandCombinationList {
        {
            bandList { eutra { bandEUTRA 3 }, nr { bandNR 78 } }
        },
        {
            bandList { eutra { bandEUTRA 1 }, nr { bandNR 28 } }
        },
        {
            bandList { eutra { bandEUTRA 20 }, nr { bandNR 77 } }
        },
        {
            bandList { eutra { bandEUTRA 7 }, nr { bandNR 78 } }
        },
        {
            bandList { eutra { bandEUTRA 8 }, nr { bandNR 78 } }
        },
        {
            bandList { eutra { bandEUTRA 3 }, eutra { bandEUTRA 7 }, nr { bandNR 78 }, nr { bandNR 257 } }
        },
        {
            bandList { eutra { bandEUTRA 1 }, eutra { bandEUTRA 3 }, nr { bandNR 78 } }
        },
        {
            bandList { eutra { bandEUTRA 3 }, nr { bandNR 41 } }
        },
        {
            bandList { eutra { bandEUTRA 41 }, nr { bandNR 41 } }
        },
        {
            bandList { eutra { bandEUTRA 41 }, nr { bandNR 79 } }
        }
    }
}
"""

# ── Test 2: Mixed Structure Input (Scattered band dicts) ────────────────────
TEST_2_MIXED = """
value UE-NR-Capability ::= {
    rf-Parameters {
        supportedBandListNR {
            { bandNR 1 }, { bandNR 3 }, { bandNR 5 }, { bandNR 7 },
            { bandNR 8 }, { bandNR 20 }, { bandNR 28 }, { bandNR 41 },
            { bandNR 77 }, { bandNR 78 }, { bandNR 79 }, { bandNR 257 }
        }
    }
}
value UE-EUTRA-Capability ::= {
    supportedBandCombination-r10 {
        { { bandEUTRA-r10 3 }, { bandEUTRA-r10 7 } }
    }
}
"""

# ── Test 3: Minimal Input (1 LTE, 1 NR) ─────────────────────────────────────
TEST_3_MINIMAL = """
value UE-EUTRA-Capability ::= { rf-Parameters { supportedBandListEUTRA { { bandEUTRA 3 } } } }
value UE-NR-Capability ::= { rf-Parameters { supportedBandListNR { { bandNR 78 } } } }
"""

def run_tests():
    tests = [
        ("Test 1: Complex MRDC", TEST_1_MRDC, {"nrBands": 10, "lteBands": 5, "mrdc": 10}), # Just approx targets
        ("Test 2: Mixed Structure", TEST_2_MIXED, {"nrBands": 8}),
        ("Test 3: Minimal", TEST_3_MINIMAL, {"lteBands": 1, "nrBands": 1}),
    ]

    all_passed = True

    for name, text, expected in tests:
        print(f"\n{'='*50}\n  {name}\n{'='*50}")
        # Run Rule-based extractor
        parsed = extract_all(text)

        # Run AI Assist (gap filling)
        parsed = ai_fill_gaps(text, parsed)

        results = {
            "nrBands": len(parsed.get("nrBands", [])),
            "lteBands": len(parsed.get("lteBands", [])),
            "mrdc": len(parsed.get("mrdc", [])),
            "lteca": len(parsed.get("lteca", [])),
        }

        print(f"Extraction Results: {json.dumps(results)}")
        
        passed = True
        for k, v in expected.items():
            if results[k] < v:
                print(f"  [FAIL] {k}: expected >={v}, got {results[k]}")
                passed = False
            else:
                print(f"  [PASS] {k}: expected >={v}, got {results[k]}")
        
        if not passed:
            all_passed = False

    print(f"\nFinal Result: {'ALL PASSED' if all_passed else 'SOME FAILED'}")

if __name__ == "__main__":
    run_tests()
