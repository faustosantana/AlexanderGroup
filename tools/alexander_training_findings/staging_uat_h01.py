import json, traceback

assert env.cr.dbname == "doralex_ent_staging"
c11 = env["res.company"].browse(11)
e = env(context=dict(env.context, allowed_company_ids=[11], justech_approval_skip=True))
tax16 = e["account.tax"].browse(464)
ptn = e["res.partner"].search([("name", "=", "DXUAT CLIENTE PAGOS")], limit=1)
if not ptn:
    ptn = e["res.partner"].create(
        {
            "name": "DXUAT CLIENTE PAGOS",
            "company_id": 11,
            "vat": "131000002",
            "is_company": True,
            "customer_rank": 1,
            "country_id": env.ref("base.do").id,
        }
    )
if "justech_do_rnc_status" in ptn._fields:
    ptn.write(
        {
            "justech_do_rnc_status": "valid",
            "justech_do_fiscal_config_state": "validated_padron",
        }
    )
prod = e["product.product"].search([("default_code", "=", "DXUAT-ITBIS16-SVC")], limit=1)
vals = {
    "name": "Producto TEST ITBIS 16",
    "default_code": "DXUAT-ITBIS16-SVC",
    "list_price": 1000,
    "type": "service",
    "company_id": 11,
    "taxes_id": [(6, 0, tax16.ids)],
}
if "is_storable" in e["product.product"]._fields:
    vals["is_storable"] = False
prod = prod or e["product.product"].create(vals)
if prod:
    prod.write({"type": "service", "taxes_id": [(6, 0, tax16.ids)], "is_storable": False})
try:
    so = e["sale.order"].create(
        {
            "partner_id": ptn.id,
            "company_id": 11,
            "client_order_ref": "PO-TEST-001",
            "order_line": [(0, 0, {"product_id": prod.id, "product_uom_qty": 1, "price_unit": 1000, "tax_ids": [(6, 0, tax16.ids)]})],
        }
    )
    print("SO", so.name, so.amount_untaxed, so.amount_tax, so.amount_total)
    so.action_confirm()
    inv = so._create_invoices()[0]
    print("INV draft", inv.name, inv.state, inv.amount_tax, inv.amount_total)
    inv.action_post()
    inv.invalidate_recordset()
    print("INV posted", inv.name, inv.state, getattr(inv, "justech_do_ncf", None), getattr(inv, "l10n_latam_document_number", None))
    lines = []
    for l in inv.line_ids:
        lines.append({"code": l.account_id.code, "acc": l.account_id.name, "debit": l.debit, "credit": l.credit, "tax": l.tax_line_id.name or False})
        print("AML", l.account_id.code, l.account_id.name, l.debit, l.credit, l.tax_line_id.name or "")
    # credit note attempt
    cn = None
    try:
        W = e["account.move.reversal"].with_context(active_model="account.move", active_ids=inv.ids)
        wiz = W.create({"reason": "DXUAT 16 credit", "journal_id": inv.journal_id.id})
        act = wiz.refund_moves() if hasattr(wiz, "refund_moves") else wiz.reverse_moves()
        if isinstance(act, dict) and act.get("res_id"):
            cn = e["account.move"].browse(act["res_id"])
        print("CN", cn.name if cn else act, cn.amount_tax if cn else None, cn.state if cn else None)
    except Exception as exc:
        print("CN_ERR", type(exc).__name__, exc)
    tags = [l.tag_ids.mapped("name") for l in tax16.invoice_repartition_line_ids]
    open("/tmp/h01_flow.json", "w").write(
        json.dumps(
            {
                "so": so.name,
                "untaxed": so.amount_untaxed,
                "tax": so.amount_tax,
                "total": so.amount_total,
                "invoice": inv.name,
                "state": inv.state,
                "ncf": getattr(inv, "justech_do_ncf", None) or getattr(inv, "l10n_latam_document_number", None),
                "lines": lines,
                "tags": tags,
                "cn": cn.name if cn else None,
            },
            indent=2,
            default=str,
        )
    )
    print("H01_PASS", inv.state == "posted" and abs(so.amount_tax - 160) < 0.02)
except Exception:
    traceback.print_exc()
