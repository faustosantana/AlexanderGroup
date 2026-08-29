#!/usr/bin/env python3
"""PREPARED — do not execute until the freeze/cleanup prompt.

Deletes ONLY records listed in docs/production_360_qa/qa_catalog.json
(exact IDs from the 360 audit). No generic name searches.

Usage on the server (after explicit authorization):

    CONFIRM=yes python3 tools/production_360_qa/cleanup_production_qa.py

This file is the procedure. Running it here without CONFIRM=yes is a no-op.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

CATALOG = Path(__file__).resolve().parents[2] / "docs/production_360_qa/qa_catalog.json"

ORDER = [
    "warranties",
    "crm_leads",
    "account_payments",
    "stock_pickings",
    "account_moves",
    "purchase_orders",
    "sale_orders",
    "products",
    "partners",
    "users",
]


def main() -> int:
    if os.environ.get("CONFIRM") != "yes":
        print("QA CLEANUP PREPARED = YES · EXECUTED = NO")
        print("Set CONFIRM=yes to run. Catalog:", CATALOG)
        return 2
    data = json.loads(CATALOG.read_text())
    print("Would unlink IDs from", CATALOG)
    for key in ORDER:
        ids = [row["id"] for row in data.get(key, [])]
        print(key, ids)
    print("ncf_ranges are handled by remove_test_ncf_configuration.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
