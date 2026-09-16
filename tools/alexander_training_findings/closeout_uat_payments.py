# -*- coding: utf-8 -*-
"""STAGING H13 payment UAT. Never Prod."""

assert env.cr.dbname == "doralex_ent_staging"
results = []


def rec(name, ok, detail):
    results.append((name, "PASS" if ok else "FAIL", detail))
    print("UAT", name, "PASS" if ok else "FAIL", detail)


ctx = dict(env.context, allowed_company_ids=[11], mail_notrack=True, tracking_disable=True)
e = env(context=ctx)
c11 = e["res.company"].browse(11)
exp = e["justech.do.dgii.expense.type"].search([("code", "=", "02")], limit=1)
Catalog = e["justech.do.withholding.catalog"].sudo()
prof = Catalog.search([("code", "=", "DX-ISR-PROF-PF-15")], limit=1)
it100 = Catalog.search([("code", "=", "DX-ITBIS-100-PF")], limit=1)
it30 = Catalog.search([("code", "=", "DX-ITBIS-30-PJ")], limit=1)
tax18 = e["account.tax"].search(
    [("company_id", "=", 11), ("type_tax_use", "=", "purchase"), ("amount", "=", 18), ("name", "ilike", "ITBIS")],
    limit=1,
)
pf = e["res.partner"].search([("name", "=", "DXUAT PROV PF")], limit=1)
pj = e["res.partner"].search([("name", "=", "DXUAT PROV PJ")], limit=1)
journal = e["account.journal"].search([("company_id", "=", 11), ("type", "=", "purchase")], limit=1)
_ncf_seq = {"n": 990}


def make_bill(partner, price, name):
    _ncf_seq["n"] += 1
    vendor_ncf = "B01%08d" % _ncf_seq["n"]
    vals = {
        "move_type": "in_invoice",
        "partner_id": partner.id,
        "company_id": 11,
        "journal_id": journal.id,
        "invoice_date": "2026-09-16",
        "justech_do_expense_type_id": exp.id,
        "invoice_line_ids": [
            (0, 0, {"name": name, "quantity": 1, "price_unit": price, "tax_ids": [(6, 0, tax18.ids)]})
        ],
    }
    if "justech_do_ncf" in e["account.move"]._fields:
        vals["justech_do_ncf"] = vendor_ncf
    if "l10n_do_origin_ncf" in e["account.move"]._fields:
        vals["l10n_do_origin_ncf"] = vendor_ncf
    bill = e["account.move"].create(vals)
    bill.action_post()
    return bill


try:
    bill_a = make_bill(pf, 100000, "H13 A PF")
    rec("H13_BILL_A", bill_a.state == "posted", "%s total=%s" % (bill_a.name, bill_a.amount_total))
except Exception as exc:  # noqa: BLE001
    rec("H13_BILL_A", False, str(exc)[:200])
    bill_a = False

try:
    bill_b = make_bill(pj, 50000, "H13 B PJ")
    bill_c = make_bill(pj, 25000, "H13 C PJ")
    rec("H13_BILLS_BC", bill_b.state == "posted" and bill_c.state == "posted", "%s %s" % (bill_b.name, bill_c.name))
except Exception as exc:  # noqa: BLE001
    rec("H13_BILLS_BC", False, str(exc)[:200])
    bill_b = bill_c = False

journal_bank = e["account.journal"].search([("company_id", "=", 11), ("type", "=", "bank")], limit=1)
pml = e["account.payment.method.line"].search(
    [("journal_id", "=", journal_bank.id), ("payment_type", "=", "outbound")], limit=1
)
Wiz = e["justech.payment.partner.wizard"]

if bill_a:
    try:
        wiz = Wiz.with_context(
            active_model="account.move",
            active_ids=bill_a.ids,
            justech_preselect_move_ids=bill_a.ids,
            allowed_company_ids=[11],
        ).create(
            {
                "partner_id": pf.id,
                "partner_type": "supplier",
                "journal_id": journal_bank.id,
                "payment_method_line_id": pml.id if pml else False,
                "currency_id": bill_a.currency_id.id,
            }
        )
        line = wiz.line_ids.filtered(lambda l: l.move_id == bill_a)
        line.write(
            {
                "apply": True,
                "amount_to_pay": bill_a.amount_residual,
                "withholding_catalog_ids": [(6, 0, [prof.id, it100.id])],
            }
        )
        line._recompute_line_withholdings()
        rec(
            "H13_WIZARD_PF",
            abs(line.withholding_amount - 33000) < 1 and abs(line.net_after_withholding - 85000) < 1,
            "wh=%s net=%s base/rate=%s" % (
                line.withholding_amount,
                line.net_after_withholding,
                [(d.base_amount, d.rate, d.amount) for d in line.withholding_detail_ids],
            ),
        )
        if hasattr(wiz, "action_register"):
            wiz.action_register()
        else:
            wiz.action_create_payments()
        bill_a.invalidate_recordset()
        rec("H13_PAY_PF", bill_a.amount_residual == 0, "residual=%s state=%s" % (bill_a.amount_residual, bill_a.payment_state))
    except Exception as exc:  # noqa: BLE001
        rec("H13_PAY_PF", False, str(exc)[:240])

if bill_b and bill_c:
    try:
        wiz = Wiz.with_context(
            active_model="account.move",
            active_ids=(bill_b | bill_c).ids,
            justech_preselect_move_ids=(bill_b | bill_c).ids,
            allowed_company_ids=[11],
        ).create(
            {
                "partner_id": pj.id,
                "partner_type": "supplier",
                "journal_id": journal_bank.id,
                "payment_method_line_id": pml.id if pml else False,
                "currency_id": bill_b.currency_id.id,
            }
        )
        for line in wiz.line_ids.filtered(lambda l: l.move_id in (bill_b | bill_c)):
            line.write(
                {
                    "apply": True,
                    "amount_to_pay": line.move_id.amount_residual,
                    "withholding_catalog_ids": [(6, 0, [it30.id])],
                }
            )
            line._recompute_line_withholdings()
        rec(
            "H13_WIZARD_MULTI",
            abs(wiz.withholding_total - 4050) < 2,
            "wh=%s pay=%s net=%s" % (wiz.withholding_total, wiz.payment_total, wiz.amount_after_withholding),
        )
        if hasattr(wiz, "action_register"):
            wiz.action_register()
        else:
            wiz.action_create_payments()
        (bill_b | bill_c).invalidate_recordset()
        rec(
            "H13_PAY_MULTI",
            bill_b.amount_residual == 0 and bill_c.amount_residual == 0,
            "b=%s c=%s" % (bill_b.amount_residual, bill_c.amount_residual),
        )
    except Exception as exc:  # noqa: BLE001
        rec("H13_PAY_MULTI", False, str(exc)[:240])

print("=== MATRIX ===")
for name, status, detail in results:
    print("%s\t%s\t%s" % (name, status, detail))
print("FAILS", [n for n, s, _ in results if s != "PASS"])
env.cr.commit()
print("COMMITTED")
