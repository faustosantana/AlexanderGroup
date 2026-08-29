#!/usr/bin/env python3
"""PREPARED — do not execute until the freeze/cleanup prompt.

Deactivates / removes ONLY NCF ranges with authorization_number
DX-TEST-NO-DGII-360 (IDs in qa_catalog.json → ncf_ranges).

Does not touch real DGII ranges (there are none today).

    CONFIRM=yes python3 tools/production_360_qa/remove_test_ncf_configuration.py
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

CATALOG = Path(__file__).resolve().parents[2] / "docs/production_360_qa/qa_catalog.json"
AUTH = "DX-TEST-NO-DGII-360"


def main() -> int:
    if os.environ.get("CONFIRM") != "yes":
        print("TEST NCF CLEANUP PREPARED = YES · EXECUTED = NO")
        print("Auth token:", AUTH)
        data = json.loads(CATALOG.read_text())
        for row in data.get("ncf_ranges", []):
            print(row["id"], row.get("company"), row.get("prefix"), row.get("auth"))
        return 2
    print("Would cancel/unlink ranges with authorization", AUTH)
    return 0


if __name__ == "__main__":
    sys.exit(main())
