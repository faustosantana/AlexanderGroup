# ruff: noqa
"""Rename default 18% ITBIS to ITBIS venta/compra + empresa. ORM only."""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, "/tmp")
try:
    from labels import EXPECTED_ITBIS_LABELS, RENAMEABLE_NAMES
except ImportError:
    sys.path.insert(0, os.path.dirname(__file__))
    from labels import EXPECTED_ITBIS_LABELS, RENAMEABLE_NAMES

DRY = os.environ.get("TAX_LABEL_DRY", "1") == "1"
OUT = os.environ.get("TAX_LABEL_OUT", "/tmp/tax_labels_apply.json")


def run(env):
    from odoo.addons.justech_alexander_base.models.catalog import (  # noqa: E402
        itbis_display_name,
        operational_companies,
        profile_for_company,
    )

    report = {"db": env.cr.dbname, "DRY": DRY, "writes": [], "skipped": [], "STOP": []}
    for company in operational_companies(env):
        profile = profile_for_company(company)
        if not profile:
            continue
        code = profile["code"]
        expected = EXPECTED_ITBIS_LABELS[code]
        for kind, field_name in (
            ("sale", "account_sale_tax_id"),
            ("purchase", "account_purchase_tax_id"),
        ):
            tax = company[field_name]
            want = expected[kind]
            computed = itbis_display_name(company, kind)
            if computed != want:
                report["STOP"].append("%s_%s_LABEL_MISMATCH" % (code, kind))
                continue
            if not tax:
                report["skipped"].append("%s_%s_MISSING" % (code, kind))
                continue
            if tax.name == want:
                report["skipped"].append("%s_%s_ALREADY" % (code, kind))
                continue
            if tax.name not in RENAMEABLE_NAMES and tax.name != want:
                report["skipped"].append(
                    "%s_%s_KEEP_%s" % (code, kind, tax.name.replace(" ", "_"))
                )
                continue
            row = {
                "code": code,
                "kind": kind,
                "tax_id": tax.id,
                "from": tax.name,
                "to": want,
            }
            if DRY:
                row["dry"] = True
            else:
                tax.sudo().write({"name": want})
                row["after"] = tax.name
            report["writes"].append(row)
    if not DRY:
        env.cr.commit()
    report["PASS"] = not report["STOP"]
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=2)
    print(
        "WROTE",
        OUT,
        "DRY",
        DRY,
        "WRITES",
        len(report["writes"]),
        "STOP",
        report["STOP"],
    )
    return report


run(env)
