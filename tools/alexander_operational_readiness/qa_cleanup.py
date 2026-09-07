# ruff: noqa
"""Limpia SOLO data QA 100% trazable. No toca lote de apertura. No envía mail/DGII."""

import json
from pathlib import Path

OUT = "/tmp/op_ready_qa_cleanup.json"
BATCH = "ALEXANDER_OPENING_2026-09-04"
CTX = {
    "mail_create_nosubscribe": True,
    "mail_notrack": True,
    "tracking_disable": True,
    "tracking_disable_onwrite": True,
}


def _safe(env, rec, method, *args, **kwargs):
    try:
        getattr(rec.with_context(**CTX), method)(*args, **kwargs)
        return True, ""
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)


def run(env):
    report = {
        "errors": [],
        "cancelled_payments": [],
        "cancelled_moves": [],
        "cancelled_pickings": [],
        "cancelled_so": [],
        "cancelled_po": [],
        "archived_partners": [],
        "archived_products": [],
        "deactivated_users": [],
        "quants_zeroed": [],
        "skipped_opening": [],
        "MAIL_SENT": 0,
        "DGII_SENT": 0,
        "ECF_SENT": 0,
    }
    opening_ids = set(env["account.move"].search([("invoice_origin", "=", BATCH)]).ids)

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
    moves = moves.filtered(lambda m: m.id not in opening_ids)
    payments = env["account.payment"].search([("partner_id", "in", partners.ids)])

    # 1) exclude from DGII
    for m in moves:
        if m.id in opening_ids:
            report["skipped_opening"].append(m.id)
            continue
        vals = {}
        if "justech_do_include_in_dgii" in m._fields:
            vals["justech_do_include_in_dgii"] = False
        if "justech_do_dgii_exclusion_reason" in m._fields:
            vals["justech_do_dgii_exclusion_reason"] = (
                "QA_CLEANUP_AUTHORIZED 2026-09-07 DX TEST / 9910 — no fiscal real"
            )
        if "justech_do_dgii_fiscal_state" in m._fields:
            vals["justech_do_dgii_fiscal_state"] = "excluded"
        if vals:
            m.with_context(**CTX, justech_ncf_engine=True).write(vals)

    # 2) unreconcile
    lines = moves.mapped("line_ids").filtered("reconciled")
    lines |= payments.mapped("move_id.line_ids").filtered("reconciled")
    if lines:
        try:
            lines.with_context(**CTX).remove_move_reconcile()
        except Exception as exc:  # noqa: BLE001
            report["errors"].append({"step": "unreconcile", "error": str(exc)})

    # 3) cancel payments
    for p in payments:
        ok = False
        for meth in ("action_cancel", "action_draft"):
            good, err = _safe(env, p, meth)
            if good:
                ok = True
                if meth == "action_draft" and p.state == "draft":
                    _safe(env, p, "action_cancel")
                break
            last = err
        if ok:
            report["cancelled_payments"].append(
                {"id": p.id, "name": p.name, "state": p.state}
            )
        else:
            report["errors"].append({"payment": p.id, "error": last})

    # 4) draft + cancel moves
    for m in moves.sorted(key=lambda r: r.id, reverse=True):
        if m.id in opening_ids:
            continue
        if m.state == "posted":
            good, err = _safe(env, m, "button_draft")
            if not good:
                report["errors"].append({"move": m.id, "name": m.name, "error": err})
                continue
        if m.state in ("draft", "posted"):
            good, err = _safe(env, m, "button_cancel")
            if not good:
                report["errors"].append(
                    {"move_cancel": m.id, "name": m.name, "error": err}
                )
                continue
        report["cancelled_moves"].append(
            {"id": m.id, "name": m.name, "state": m.state, "ncf": m.justech_do_ncf}
        )

    # 5) pickings
    picks = env["stock.picking"].search(
        ["|", ("partner_id", "in", partners.ids), ("origin", "ilike", "DXQA")]
    )
    for p in picks:
        if p.state == "cancel":
            report["cancelled_pickings"].append(
                {"id": p.id, "name": p.name, "state": p.state}
            )
            continue
        if p.state in ("assigned", "confirmed", "waiting", "draft"):
            good, err = _safe(env, p, "action_cancel")
            if good:
                report["cancelled_pickings"].append(
                    {"id": p.id, "name": p.name, "state": p.state}
                )
            else:
                report["errors"].append({"picking": p.id, "error": err})
        elif p.state == "done":
            report["cancelled_pickings"].append(
                {"id": p.id, "name": p.name, "state": "done_left_for_quant_zero"}
            )

    # 6) SO / PO
    for so in env["sale.order"].search([("partner_id", "in", partners.ids)]):
        if so.state == "cancel":
            report["cancelled_so"].append(
                {"id": so.id, "name": so.name, "state": so.state}
            )
            continue
        good, err = _safe(env, so, "action_cancel")
        if good:
            report["cancelled_so"].append(
                {"id": so.id, "name": so.name, "state": so.state}
            )
        else:
            report["errors"].append({"so": so.id, "error": err})
    for po in env["purchase.order"].search([("partner_id", "in", partners.ids)]):
        if po.state == "cancel":
            report["cancelled_po"].append(
                {"id": po.id, "name": po.name, "state": po.state}
            )
            continue
        good, err = _safe(env, po, "button_cancel")
        if good:
            report["cancelled_po"].append(
                {"id": po.id, "name": po.name, "state": po.state}
            )
        else:
            report["errors"].append({"po": po.id, "error": err})

    # 7) zero QA stock
    quants = env["stock.quant"].search(
        [("product_id", "in", products.ids), ("quantity", "!=", 0)]
    )
    for q in quants:
        try:
            if "inventory_quantity" in q._fields:
                q.with_context(**CTX, inventory_mode=True).write(
                    {"inventory_quantity": 0.0}
                )
                if hasattr(q, "action_apply_inventory"):
                    q.with_context(**CTX).action_apply_inventory()
            else:
                q.sudo().write({"quantity": 0.0})
            report["quants_zeroed"].append(
                {
                    "id": q.id,
                    "product": q.product_id.display_name,
                    "location": q.location_id.complete_name,
                    "qty_after": float(q.quantity),
                }
            )
        except Exception as exc:  # noqa: BLE001
            report["errors"].append({"quant": q.id, "error": str(exc)})

    # 8) deactivate QA users first (blocks partner archive)
    users = (
        env["res.users"]
        .with_context(active_test=False)
        .search(["|", ("login", "ilike", "dx.test"), ("name", "ilike", "DX TEST")])
    )
    for u in users:
        u.with_context(**CTX).write({"active": False})
        report["deactivated_users"].append({"id": u.id, "login": u.login})

    # 9) archive masters
    for p in products:
        p.with_context(**CTX).write(
            {"active": False, "sale_ok": False, "purchase_ok": False}
        )
        report["archived_products"].append({"id": p.id, "name": p.display_name})
    for p in partners:
        try:
            p.with_context(**CTX).write({"active": False})
            report["archived_partners"].append({"id": p.id, "name": p.name})
        except Exception as exc:  # noqa: BLE001
            report["errors"].append({"partner_archive": p.id, "error": str(exc)})

    # guard
    opening = env["account.move"].search(
        [
            ("invoice_origin", "=", BATCH),
            ("move_type", "=", "out_invoice"),
            ("state", "=", "posted"),
        ]
    )
    report["opening_after"] = {
        "count": len(opening),
        "0150": next(
            (
                float(m.amount_total)
                for m in opening
                if m.justech_do_ncf == "B1500000150"
            ),
            None,
        ),
        "qweb": env["ir.ui.view"].search_count(
            [("key", "like", "justech_alexander%"), ("type", "=", "qweb")]
        ),
    }
    env.cr.commit()
    Path(OUT).write_text(
        json.dumps(report, indent=2, ensure_ascii=False, default=str), encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "cancelled_payments": len(report["cancelled_payments"]),
                "cancelled_moves": len(report["cancelled_moves"]),
                "cancelled_so": len(report["cancelled_so"]),
                "cancelled_po": len(report["cancelled_po"]),
                "archived_partners": len(report["archived_partners"]),
                "archived_products": len(report["archived_products"]),
                "users": report["deactivated_users"],
                "quants": report["quants_zeroed"],
                "errors": report["errors"],
                "opening_after": report["opening_after"],
                "MAIL_SENT": 0,
            },
            indent=2,
            default=str,
        )
    )


if "env" in globals():
    run(env)
