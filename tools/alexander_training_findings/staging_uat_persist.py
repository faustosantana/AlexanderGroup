# -*- coding: utf-8 -*-
"""Persist critical STAGING UAT docs. Explicit commit. Never Prod."""

import json

assert env.cr.dbname == "doralex_ent_staging"
ctx = dict(
    env.context,
    allowed_company_ids=[11],
    justech_approval_skip=True,
    mail_notrack=True,
    tracking_disable=True,
    mail_create_nolog=True,
    mail_create_nosubscribe=True,
)
e = env(context=ctx)
c11 = e["res.company"].browse(11)
tax16 = e["account.tax"].browse(464)
tax18 = e["account.tax"].search(
    [
        ("company_id", "=", 11),
        ("type_tax_use", "=", "sale"),
        ("amount", "=", 18),
        ("name", "ilike", "ITBIS"),
    ],
    limit=1,
)
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
            "email": "dxuat.noreply@example.invalid",
        }
    )
ptn.write(
    {
        "justech_do_rnc_status": "valid",
        "justech_do_fiscal_config_state": "validated_padron",
    }
)

p16 = e["product.product"].search([("default_code", "=", "DXUAT-ITBIS16-SVC")], limit=1)
if not p16:
    p16 = e["product.product"].create(
        {
            "name": "Producto TEST ITBIS 16",
            "default_code": "DXUAT-ITBIS16-SVC",
            "type": "service",
            "is_storable": False,
            "list_price": 1000,
            "company_id": 11,
            "taxes_id": [(6, 0, tax16.ids)],
        }
    )
p18 = e["product.product"].search([("default_code", "=", "DXUAT-PAY")], limit=1)
if not p18:
    p18 = e["product.product"].create(
        {
            "name": "UAT Pago",
            "default_code": "DXUAT-PAY",
            "type": "service",
            "is_storable": False,
            "list_price": 1000,
            "company_id": 11,
            "taxes_id": [(6, 0, tax18.ids)],
        }
    )

so16 = e["sale.order"].create(
    {
        "partner_id": ptn.id,
        "company_id": 11,
        "client_order_ref": "PO-TEST-001",
        "order_line": [
            (
                0,
                0,
                {
                    "product_id": p16.id,
                    "product_uom_qty": 1,
                    "price_unit": 1000,
                    "tax_ids": [(6, 0, tax16.ids)],
                },
            )
        ],
    }
)
so16.action_confirm()
inv16 = so16._create_invoices()[0]
inv16.action_post()
inv16.invalidate_recordset()

invoices = []
for price in (1000.0, 2000.0, 3000.0):
    so = e["sale.order"].create(
        {
            "partner_id": ptn.id,
            "company_id": 11,
            "order_line": [
                (
                    0,
                    0,
                    {
                        "product_id": p18.id,
                        "product_uom_qty": 1,
                        "price_unit": price,
                        "tax_ids": [(6, 0, tax18.ids)],
                    },
                )
            ],
        }
    )
    so.action_confirm()
    inv = so._create_invoices()[0]
    inv.action_post()
    invoices.append(inv)

bank = e["account.journal"].search(
    [("company_id", "=", 11), ("type", "=", "bank")], limit=1
)
method = e["account.payment.method.line"].search(
    [("journal_id", "=", bank.id), ("payment_method_id.payment_type", "=", "inbound")],
    limit=1,
)
total = sum(abs(i.amount_residual) for i in invoices)
wiz = (
    e["multi.invoice.manual.payment.wizard"]
    .with_company(c11)
    .create(
        {
            "partner_type": "customer",
            "partner_id": ptn.id,
            "company_id": 11,
            "payment_date": "2026-09-16",
            "journal_id": bank.id,
            "payment_method_line_id": method.id,
            "ref": "DXUAT-MULTI-3",
            "amount_received": total,
            "line_ids": [
                (
                    0,
                    0,
                    {
                        "move_id": i.id,
                        "currency_id": i.currency_id.id,
                        "invoice_date": i.invoice_date,
                        "due_date": i.invoice_date_due,
                        "amount_total": abs(i.amount_total),
                        "amount_residual": abs(i.amount_residual),
                        "amount_to_apply": abs(i.amount_residual),
                    },
                )
                for i in invoices
            ],
        }
    )
)
payment = e["account.payment"].browse(wiz.action_create_payment().get("res_id"))
for i in invoices:
    i.invalidate_recordset()
pdf = env["ir.actions.report"]._render_qweb_pdf(
    "account.action_report_payment_receipt", payment.ids
)[0]
open("/tmp/h13_recibo_persist.pdf", "wb").write(pdf)

out = {
    "h01": {
        "so": so16.name,
        "so_id": so16.id,
        "untaxed": so16.amount_untaxed,
        "tax": so16.amount_tax,
        "total": so16.amount_total,
        "invoice": inv16.name,
        "invoice_id": inv16.id,
        "state": inv16.state,
        "ncf": getattr(inv16, "justech_do_ncf", None)
        or getattr(inv16, "l10n_latam_document_number", None),
        "lines": [
            {
                "code": l.account_id.code,
                "acc": l.account_id.name,
                "debit": l.debit,
                "credit": l.credit,
                "tax": l.tax_line_id.name or False,
            }
            for l in inv16.line_ids
        ],
    },
    "h13": {
        "invoices": [
            {
                "id": i.id,
                "name": i.name,
                "total": i.amount_total,
                "residual": i.amount_residual,
                "ncf": getattr(i, "justech_do_ncf", None),
                "payment_state": i.payment_state,
            }
            for i in invoices
        ],
        "payment": {
            "id": payment.id,
            "name": payment.name,
            "amount": payment.amount,
            "state": payment.state,
            "move": payment.move_id.name,
        },
    },
}
open("/tmp/uat_persist.json", "w").write(json.dumps(out, indent=2, default=str))
env.cr.commit()
print("PERSISTED", json.dumps(out, default=str))
