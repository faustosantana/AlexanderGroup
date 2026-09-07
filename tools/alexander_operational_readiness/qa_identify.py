# ruff: noqa
"""Identifica data QA 100% trazable. No escribe."""

import json
from pathlib import Path

OUT = "/tmp/op_ready_qa_identify.json"
BATCH = "ALEXANDER_OPENING_2026-09-04"


def run(env):
    out = {
        "partners": [],
        "products": [],
        "moves": [],
        "payments": [],
        "sale_orders": [],
        "purchase_orders": [],
        "pickings": [],
        "users": [],
        "quants": [],
        "opening_guard": {},
    }
    opening = env["account.move"].search(
        [("invoice_origin", "=", BATCH), ("state", "=", "posted")]
    )
    out["opening_guard"] = {
        "ids": opening.ids,
        "count": len(opening),
        "ncfs": opening.mapped("justech_do_ncf"),
    }
    protect = set(opening.ids)

    partners = (
        env["res.partner"]
        .with_context(active_test=False)
        .search(
            [
                "|",
                "|",
                "|",
                ("name", "ilike", "DX TEST"),
                ("name", "ilike", "DXQA"),
                ("name", "ilike", "NO FISCAL REAL"),
                ("name", "ilike", "DX-TEST"),
            ]
        )
    )
    for p in partners:
        out["partners"].append(
            {
                "id": p.id,
                "name": p.name,
                "active": p.active,
                "company": p.company_id.name,
            }
        )

    products = (
        env["product.product"]
        .with_context(active_test=False)
        .search(
            [
                "|",
                "|",
                "|",
                ("name", "ilike", "DX TEST"),
                ("name", "ilike", "DXQA"),
                ("default_code", "ilike", "DX-TEST"),
                ("default_code", "ilike", "DXQA"),
            ]
        )
    )
    for p in products:
        out["products"].append(
            {
                "id": p.id,
                "name": p.display_name,
                "active": p.active,
                "company": p.company_id.name,
            }
        )

    moves = env["account.move"].search(
        [
            "|",
            "|",
            "|",
            ("justech_do_ncf", "=like", "%9910%"),
            ("justech_do_ncf", "=like", "%9911%"),
            ("partner_id", "in", partners.ids),
            ("invoice_origin", "ilike", "DXQA"),
        ]
    )
    for m in moves:
        if m.id in protect:
            out.setdefault("blocked_opening_hits", []).append(m.id)
            continue
        out["moves"].append(
            {
                "id": m.id,
                "name": m.name,
                "type": m.move_type,
                "state": m.state,
                "ncf": m.justech_do_ncf,
                "partner": m.partner_id.name,
                "company": m.company_id.name,
                "origin": m.invoice_origin,
                "total": float(m.amount_total),
                "residual": float(m.amount_residual),
                "include_dgii": bool(m.justech_do_include_in_dgii),
            }
        )

    pays = env["account.payment"].search([("partner_id", "in", partners.ids)])
    for p in pays:
        out["payments"].append(
            {
                "id": p.id,
                "name": p.name,
                "state": p.state,
                "partner": p.partner_id.name,
                "company": p.company_id.name,
                "amount": float(p.amount),
            }
        )

    sos = env["sale.order"].search(
        [
            "|",
            "|",
            ("partner_id", "in", partners.ids),
            ("client_order_ref", "ilike", "DXQA"),
            ("name", "ilike", "DXQA"),
        ]
    )
    for s in sos:
        out["sale_orders"].append(
            {
                "id": s.id,
                "name": s.name,
                "state": s.state,
                "partner": s.partner_id.name,
                "company": s.company_id.name,
                "ref": s.client_order_ref,
            }
        )
    pos = env["purchase.order"].search(
        [
            "|",
            "|",
            ("partner_id", "in", partners.ids),
            ("partner_ref", "ilike", "DXQA"),
            ("name", "ilike", "DXQA"),
        ]
    )
    for s in pos:
        out["purchase_orders"].append(
            {
                "id": s.id,
                "name": s.name,
                "state": s.state,
                "partner": s.partner_id.name,
                "company": s.company_id.name,
            }
        )
    picks = env["stock.picking"].search(
        [
            "|",
            ("partner_id", "in", partners.ids),
            ("origin", "ilike", "DXQA"),
        ]
    )
    for p in picks:
        out["pickings"].append(
            {
                "id": p.id,
                "name": p.name,
                "state": p.state,
                "company": p.company_id.name,
            }
        )
    for u in (
        env["res.users"]
        .with_context(active_test=False)
        .search(["|", ("login", "ilike", "dx.test"), ("name", "ilike", "DX TEST")])
    ):
        out["users"].append(
            {"id": u.id, "login": u.login, "active": u.active, "name": u.name}
        )
    for q in env["stock.quant"].search(
        [("product_id", "in", products.ids), ("quantity", "!=", 0)]
    ):
        out["quants"].append(
            {
                "id": q.id,
                "product": q.product_id.display_name,
                "location": q.location_id.complete_name,
                "qty": float(q.quantity),
                "company": q.company_id.name,
            }
        )
    Path(OUT).write_text(
        json.dumps(out, indent=2, ensure_ascii=False, default=str), encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "partners": len(out["partners"]),
                "products": len(out["products"]),
                "moves": len(out["moves"]),
                "payments": len(out["payments"]),
                "so": len(out["sale_orders"]),
                "po": len(out["purchase_orders"]),
                "pickings": len(out["pickings"]),
                "users": out["users"],
                "quants": out["quants"],
                "opening_count": out["opening_guard"]["count"],
                "blocked_opening_hits": out.get("blocked_opening_hits", []),
            },
            indent=2,
            default=str,
        )
    )


if "env" in globals():
    run(env)
