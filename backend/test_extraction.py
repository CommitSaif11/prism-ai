"""
Verify extraction against known inputs.
Tests the three root cause fixes.
"""
import json, sys, os
sys.path.insert(0, os.path.dirname(__file__))
from sequential_extractor import extract_all

# ── Test 1: MRDC with 3 combos ───────────────────────────────────────────────
MRDC_3 = """
value UE-MRDC-Capability ::= {
    supportedBandCombinationList {
        {
            bandList {
                eutra {
                    bandEUTRA 3,
                    ca-BandwidthClassDL-r10 a
                },
                nr {
                    bandNR 78,
                    ca-BandwidthClassDL a
                }
            },
            featureSetCombination 1,
            dynamicPowerSharingENDC supported
        },
        {
            bandList {
                eutra {
                    bandEUTRA 1,
                    ca-BandwidthClassDL-r10 a
                },
                nr {
                    bandNR 28,
                    ca-BandwidthClassDL a
                }
            },
            featureSetCombination 2
        },
        {
            bandList {
                eutra {
                    bandEUTRA 7,
                    ca-BandwidthClassDL-r10 a
                },
                nr {
                    bandNR 77,
                    ca-BandwidthClassDL a
                }
            },
            featureSetCombination 3
        }
    }
}
"""

# ── Test 2: Multi-component MRDC combo ────────────────────────────────────────
MRDC_MULTI = """
value UE-MRDC-Capability ::= {
    supportedBandCombinationList {
        {
            bandList {
                eutra {
                    bandEUTRA 3,
                    ca-BandwidthClassDL-r10 a
                },
                eutra {
                    bandEUTRA 7,
                    ca-BandwidthClassDL-r10 a
                },
                nr {
                    bandNR 78,
                    ca-BandwidthClassDL a
                },
                nr {
                    bandNR 257,
                    ca-BandwidthClassDL a
                }
            },
            featureSetCombination 1
        }
    }
}
"""

# ── Test 3: NR bands ─────────────────────────────────────────────────────────
NR_BANDS = """
value UE-NR-Capability ::= {
    rf-Parameters {
        supportedBandListNR {
            {
                bandNR 41,
                maxNumberMIMO-LayersPDSCH fourLayers
            },
            {
                bandNR 66,
                maxNumberMIMO-LayersPDSCH twoLayers
            },
            {
                bandNR 78,
                maxNumberMIMO-LayersPDSCH fourLayers
            },
            {
                bandNR 257
            }
        }
    }
}
"""

# ── Test 4: Full combined file ────────────────────────────────────────────────
FULL = """
value UE-EUTRA-Capability ::= {
    rf-Parameters {
        supportedBandListEUTRA {
            {
                bandEUTRA 1
            },
            {
                bandEUTRA 3
            },
            {
                bandEUTRA 7
            },
            {
                bandEUTRA 28
            }
        }
    },
    supportedBandCombination-r10 {
        {
            {
                bandEUTRA-r10 1,
                ca-BandwidthClassDL-r10 a
            },
            {
                bandEUTRA-r10 3,
                ca-BandwidthClassDL-r10 a
            }
        },
        {
            {
                bandEUTRA-r10 7,
                ca-BandwidthClassDL-r10 c
            }
        }
    }
}

value UE-NR-Capability ::= {
    rf-Parameters {
        supportedBandListNR {
            {
                bandNR 41,
                maxNumberMIMO-LayersPDSCH fourLayers
            },
            {
                bandNR 66,
                maxNumberMIMO-LayersPDSCH twoLayers
            },
            {
                bandNR 78
            },
            {
                bandNR 257
            },
            {
                bandNR 260
            }
        }
    }
}

value UE-MRDC-Capability ::= {
    supportedBandCombinationList {
        {
            bandList {
                eutra {
                    bandEUTRA 1,
                    ca-BandwidthClassDL-r10 a
                },
                nr {
                    bandNR 78,
                    ca-BandwidthClassDL a
                }
            },
            featureSetCombination 1,
            dynamicPowerSharingENDC supported
        },
        {
            bandList {
                eutra {
                    bandEUTRA 3,
                    ca-BandwidthClassDL-r10 a
                },
                nr {
                    bandNR 78,
                    ca-BandwidthClassDL a
                }
            },
            featureSetCombination 2
        },
        {
            bandList {
                eutra {
                    bandEUTRA 7,
                    ca-BandwidthClassDL-r10 a
                },
                nr {
                    bandNR 77,
                    ca-BandwidthClassDL a
                }
            },
            featureSetCombination 3
        },
        {
            bandList {
                eutra {
                    bandEUTRA 28,
                    ca-BandwidthClassDL-r10 a
                },
                nr {
                    bandNR 257,
                    ca-BandwidthClassDL a
                }
            },
            featureSetCombination 4
        },
        {
            bandList {
                eutra {
                    bandEUTRA 1,
                    ca-BandwidthClassDL-r10 a
                },
                eutra {
                    bandEUTRA 3,
                    ca-BandwidthClassDL-r10 a
                },
                nr {
                    bandNR 78,
                    ca-BandwidthClassDL a
                }
            },
            featureSetCombination 5
        }
    }
}
"""

def run_test(name, text, expected):
    print(f"\n{'='*60}")
    print(f"  TEST: {name}")
    print(f"{'='*60}")
    data = extract_all(text)
    counts = {
        "lteBands": len(data["lteBands"]),
        "nrBands": len(data["nrBands"]),
        "lteca": len(data["lteca"]),
        "nrca": len(data["nrca"]),
        "mrdc": len(data["mrdc"]),
    }
    print(f"  Counts: {json.dumps(counts)}")

    # Check MRDC component details
    for i, combo in enumerate(data.get("mrdc", [])):
        lte = [c["band"] for c in combo.get("componentsLte", [])]
        nr = [c["band"] for c in combo.get("componentsNr", [])]
        bw = combo.get("componentsLte", [{}])[0].get("bwClassDl") if combo.get("componentsLte") else None
        print(f"  MRDC[{i}]: LTE={lte} NR={nr} bwClassDl={bw}")

    # Check NR bands
    nr_bands = [b["band"] for b in data.get("nrBands", [])]
    print(f"  NR bands: {nr_bands}")

    # Assertions
    passed = True
    for key, exp_val in expected.items():
        actual = counts.get(key, 0)
        status = "PASS" if actual == exp_val else "FAIL"
        if status == "FAIL":
            passed = False
        print(f"  [{status}] {key}: expected={exp_val}, actual={actual}")

    # Check no trailing commas in bwClassDl
    for combo_type in ["lteca", "mrdc"]:
        for combo in data.get(combo_type, []):
            for comp_key in ["components", "componentsLte"]:
                for comp in combo.get(comp_key, []):
                    bw = comp.get("bwClassDl", "")
                    if bw and "," in str(bw):
                        print(f"  [FAIL] Trailing comma in bwClassDl: {bw!r}")
                        passed = False

    if passed:
        print(f"  >>> ALL CHECKS PASSED")
    else:
        print(f"  >>> SOME CHECKS FAILED")
    return passed

all_pass = True
all_pass &= run_test("MRDC 3 combos", MRDC_3, {"mrdc": 3})
all_pass &= run_test("MRDC multi-component", MRDC_MULTI, {"mrdc": 1})
all_pass &= run_test("NR 4 bands", NR_BANDS, {"nrBands": 4})
all_pass &= run_test("Full combined file", FULL, {
    "lteBands": 4, "nrBands": 5, "lteca": 2, "mrdc": 5
})

print(f"\n{'='*60}")
if all_pass:
    print("  ALL TESTS PASSED")
else:
    print("  SOME TESTS FAILED")
print(f"{'='*60}")
