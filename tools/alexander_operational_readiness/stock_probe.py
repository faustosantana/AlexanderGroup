# ruff: noqa
"""Read-only stock quant snapshot. No writes."""

import json
from pathlib import Path

OUT = "/tmp/op_ready_stock.json"


def run(env):
    out = {"quants": [], "by_company": []}
    Quant = env["stock.quant"]
    for c in env["res.company"].search([("id", "!=", 1)], order="id"):
        qs = Quant.search([("company_id", "=", c.id), ("quantity", "!=", 0)])
        recs = []
        qty = 0.0
        for q in qs:
            recs.append(
                {
                    "product": q.product_id.display_name,
                    "location": q.location_id.complete_name,
                    "qty": float(q.quantity),
                    "reserved": float(q.reserved_quantity),
                }
            )
            qty += float(q.quantity)
        out["by_company"].append(
            {
                "company": c.name,
                "nonzero_quants": len(qs),
                "qty_sum": qty,
                "sample": recs[:15],
            }
        )
    Path(OUT).write_text(json.dumps(out, indent=2, ensure_ascii=False, default=str))
    print(json.dumps(out, indent=2, ensure_ascii=False, default=str))


if "env" in globals():
    run(env)
