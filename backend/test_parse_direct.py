import json
from pprint import pprint
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))
from asn_parser import parse_text

TEST_1_MRDC = """
value UE-MRDC-Capability ::= {
    supportedBandCombinationList {
        {
            bandList { eutra { bandEUTRA 3 }, nr { bandNR 78 } }
        },
        {
            bandList { eutra { bandEUTRA 1 }, nr { bandNR 28 } }
        }
    }
}
"""

print(json.dumps(parse_text(TEST_1_MRDC), indent=2))
