# ruff: noqa
"""QA after Grava 3/4 duplicate archive. Read-only."""

import json

CANONICAL_NAME = "Agregado grueso (grava) 3/4"
NAME_A = "(AGREGADO GRUESO) GRAVA 3/4"
NAME_B = "AGREGADO GRUESO (GRAVA) 3/4"

Template = env["product.template"].sudo().with_context(active_test=False)
active = Template.search(
    [("name", "in", [NAME_A, NAME_B, CANONICAL_NAME]), ("active", "=", True)]
)
archived = Template.search(
    [("name", "in", [NAME_A, NAME_B, CANONICAL_NAME]), ("active", "=", False)]
)
can = Template.search([("name", "=", CANONICAL_NAME), ("active", "=", True)], limit=1)

# Historical invoices still resolve
posted = 0
broken = 0
Line = env["account.move.line"].sudo()
for tmpl in Template.search([("name", "in", [NAME_A, NAME_B, CANONICAL_NAME])]):
    for line in Line.search([("product_id", "in", tmpl.product_variant_ids.ids)]):
        try:
            _ = line.move_id.name, line.product_id.display_name, line.price_unit
            if line.move_id.state == "posted":
                posted += 1
        except Exception:
            broken += 1

# Search as a salesperson would (active only)
visible = (
    env["product.template"]
    .sudo()
    .search([("name", "ilike", "agregado grueso"), ("name", "ilike", "grava")])
)

report = {
    "ACTIVE_GRAVA_3_4_PRODUCTS": len(active),
    "ACTIVE_NAMES": [t.name for t in active],
    "ARCHIVED_NAMES": [t.name for t in archived],
    "CANONICAL_ID": can.id if can else None,
    "CANONICAL_LIST_PRICE": float(can.list_price) if can else None,
    "CANONICAL_SALE_OK": bool(can.sale_ok) if can else None,
    "CANONICAL_PURCHASE_OK": bool(can.purchase_ok) if can else None,
    "POSTED_LINES_STILL_READABLE": posted,
    "BROKEN_RELATIONS": broken,
    "VISIBLE_AGREGADO_GRUESO_GRAVA": [{"id": t.id, "name": t.name} for t in visible],
    "POSTED_INVOICES": env["account.move"]
    .sudo()
    .search_count([("move_type", "=", "out_invoice"), ("state", "=", "posted")]),
    "CRITICAL_ERRORS": 0,
    "HIGH_ERRORS": 0,
}
if len(active) != 1 or not can or broken:
    report["HIGH_ERRORS"] = 1
if report["POSTED_INVOICES"] != 27:
    report["CRITICAL_ERRORS"] = 1
if can and abs(float(can.list_price) - 2054.91) > 0.009:
    report["HIGH_ERRORS"] = 1
report["QA"] = (
    "PASS" if not report["CRITICAL_ERRORS"] and not report["HIGH_ERRORS"] else "FAIL"
)
print("GRAVA_QA_BEGIN")
print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
print("GRAVA_QA_END")
