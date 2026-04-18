"""
Structural test: feed the parser a realistic MRDC input and print
exactly what tree it produces. This tells us what keys the extractor
must look for.
"""
import json, sys, os
sys.path.insert(0, os.path.dirname(__file__))
from asn_parser import parse_text, _norm

# ── Minimal realistic MRDC input ──────────────────────────────────────────────
SAMPLE_MRDC = """
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

# ── Also test a multi-LTE + multi-NR MRDC combo  ─────────────────────────────
SAMPLE_MULTI = """
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

# ── NR band list test ─────────────────────────────────────────────────────────
SAMPLE_NR = """
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

def dump(label, text):
    tree = parse_text(text)
    print(f"\n{'='*60}")
    print(f"  {label}")
    print(f"{'='*60}")
    print(json.dumps(tree, indent=2, default=str)[:3000])
    print()

    # Show all keys recursively
    def show_keys(node, prefix=""):
        if isinstance(node, dict):
            for k in sorted(node.keys()):
                print(f"  {prefix}{k}: {type(node[k]).__name__}", end="")
                if isinstance(node[k], (str, int, bool)):
                    print(f" = {node[k]!r}")
                elif isinstance(node[k], list):
                    print(f" [{len(node[k])} items]")
                else:
                    print()
                if isinstance(node[k], (dict, list)):
                    show_keys(node[k], prefix + "  ")
        elif isinstance(node, list):
            for i, item in enumerate(node):
                print(f"  {prefix}[{i}]: {type(item).__name__}")
                show_keys(item, prefix + "  ")

    print("KEY TREE:")
    show_keys(tree)

dump("MRDC - 3 combos", SAMPLE_MRDC)
dump("MRDC - multi-component combo", SAMPLE_MULTI)
dump("NR - 4 bands", SAMPLE_NR)
