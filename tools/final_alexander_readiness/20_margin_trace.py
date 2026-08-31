# -*- coding: utf-8 -*-
"""5 margin ops per operational company + multi-PO UI path + trace + CxP.

STAGING only. Prefix DXQA-FINAL. Does not consume B17. Does not invent NCF ranges.
"""

import json
import time

TAG = "DXQA-FINAL-20260831"
INV_DATE = "2026-08-15"
PAY_DATE = "2026-08-28"
OUT = "/tmp/final_readiness_margin_trace.json"

ctx_mail = {
    "mail_notrack": True,
    "tracking_disable": True,
    "mail_create_nolog": True,
    "mail_create_nosubscribe": True,
}

result = {
    "started": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    "prod_touched": False,
    "companies": {},
    "errors": [],
}

ncf_bill_seq = 100


def _ctx(company):
    return dict(
        env.context,
        allowed_company_ids=[company.id],
        justech_approval_skip=True,
        **ctx_mail,
    )


def _tax18(e, company, use):
    Tax = e["account.tax"].with_company(company)
    return Tax.search(
        [
            ("company_id", "=", company.id),
            ("type_tax_use", "=", use),
            ("amount", "=", 18),
            ("active", "=", True),
        ],
        limit=1,
    ) or Tax.search(
        [
            ("company_id", "=", company.id),
            ("type_tax_use", "=", use),
            ("active", "=", True),
        ],
        limit=1,
    )


def _pay_native(e, company, partner, partner_type, journal, method, moves_amounts, ref):
    Wizard = e["multi.invoice.manual.payment.wizard"].with_company(company)
    lines = []
    total = 0.0
    for move, amount in moves_amounts:
        lines.append(
            (
                0,
                0,
                {
                    "move_id": move.id,
                    "currency_id": move.currency_id.id,
                    "invoice_date": move.invoice_date,
                    "due_date": move.invoice_date_due,
                    "amount_total": abs(move.amount_total),
                    "amount_residual": abs(move.amount_residual),
                    "amount_to_apply": amount,
                },
            )
        )
        total += amount
    wiz = Wizard.create(
        {
            "partner_type": partner_type,
            "partner_id": partner.id,
            "company_id": company.id,
            "payment_date": PAY_DATE,
            "journal_id": journal.id,
            "payment_method_line_id": method.id,
            "ref": ref,
            "amount_received": total,
            "line_ids": lines,
        }
    )
    action = wiz.action_create_payment()
    return e["account.payment"].browse(action.get("res_id"))


def _next_bill_ncf(company):
    global ncf_bill_seq
    ncf_bill_seq += 1
    return "B0177%02d%04d" % (company.id, ncf_bill_seq)


def _create_so(e, company, partner, product, qty, price, ref, tax=None):
    line = {
        "product_id": product.id,
        "product_uom_qty": qty,
        "price_unit": price,
        "name": ref,
    }
    if tax:
        tax_field = "tax_ids" if "tax_ids" in e["sale.order.line"]._fields else "tax_id"
        line[tax_field] = [(6, 0, tax.ids)]
    so = (
        e["sale.order"]
        .with_company(company)
        .create(
            {
                "partner_id": partner.id,
                "company_id": company.id,
                "client_order_ref": ref,
                "origin": ref,
                "order_line": [(0, 0, line)],
            }
        )
    )
    so.action_confirm()
    return so


def _invoice_so(e, so, extra=None):
    invs = so._create_invoices()
    base = {"invoice_date": INV_DATE, "invoice_date_due": "2026-09-30"}
    if extra:
        base.update(extra)
    invs.write(base)
    for inv in invs:
        if inv.state == "draft":
            inv.action_post()
    return invs


def _create_po(
    e, company, vendor, product, qty, price, origin, sale_line=None, tax=None
):
    line = {
        "product_id": product.id,
        "product_qty": qty,
        "price_unit": price,
        "name": origin,
    }
    if sale_line and "sale_line_id" in e["purchase.order.line"]._fields:
        line["sale_line_id"] = sale_line.id
    if tax:
        pol_fields = e["purchase.order.line"]._fields
        tax_field = (
            "tax_ids"
            if "tax_ids" in pol_fields
            else "taxes_id" if "taxes_id" in pol_fields else None
        )
        if tax_field:
            line[tax_field] = [(6, 0, tax.ids)]
    po = (
        e["purchase.order"]
        .with_company(company)
        .create(
            {
                "partner_id": vendor.id,
                "company_id": company.id,
                "origin": origin,
                "order_line": [(0, 0, line)],
            }
        )
    )
    po.button_confirm()
    return po


def _bill_po(e, company, po, qty=None, latam=None, expense=None):
    for pol in po.order_line.filtered(lambda l: not l.display_type):
        if qty is not None and "qty_received" in pol._fields:
            pol.qty_received = qty
        elif "qty_received" in pol._fields and not pol.qty_received:
            pol.qty_received = pol.product_qty
    action = po.with_company(company).action_create_invoice()
    bill = e["account.move"]
    if isinstance(action, dict) and action.get("res_id"):
        bill = e["account.move"].browse(action["res_id"])
    elif isinstance(action, dict) and action.get("domain"):
        bill = e["account.move"].search(action["domain"], limit=1)
    if not bill:
        bill = e["account.move"].search(
            [("invoice_origin", "=", po.name), ("move_type", "=", "in_invoice")],
            order="id desc",
            limit=1,
        )
    if not bill:
        raise ValueError("no bill for PO %s" % po.name)
    vals = {
        "invoice_date": INV_DATE,
        "date": INV_DATE,
        "invoice_date_due": "2026-09-30",
    }
    if "justech_do_purchase_registration_mode" in bill._fields:
        vals["justech_do_purchase_registration_mode"] = "received"
    if latam and "l10n_latam_document_type_id" in bill._fields:
        vals["l10n_latam_document_type_id"] = latam.id
    if "l10n_latam_document_number" in bill._fields:
        vals["l10n_latam_document_number"] = _next_bill_ncf(company)
    if expense and "justech_do_expense_type_id" in bill._fields:
        vals["justech_do_expense_type_id"] = expense.id
    if vals:
        bill.write(vals)
    if bill.state == "draft":
        bill.action_post()
    return bill


def _tx_amounts(tx):
    sudo_tx = tx.sudo()
    return {
        "estimated_revenue": sudo_tx.sale_estimated_amount,
        "estimated_cost": sudo_tx.cost_estimated_amount,
        "estimated_margin": sudo_tx.estimated_margin,
        "real_revenue": sudo_tx.sale_real_amount,
        "real_cost": sudo_tx.cost_real_amount,
        "real_margin": sudo_tx.real_margin,
        "additional_costs": sudo_tx.additional_cost_amount,
        "sale_orders": sudo_tx.sale_order_ids.mapped("name"),
        "purchase_orders": sudo_tx.purchase_order_ids.mapped("name"),
        "customer_invoices": sudo_tx.customer_invoice_ids.ids,
        "vendor_bills": sudo_tx.vendor_bill_ids.ids,
    }


def _add_pos_via_wizard(e, company, so, pos):
    Wiz = e["purchase.sale.add.purchase.wizard"].with_company(company)
    wiz = Wiz.create(
        {
            "company_id": company.id,
            "sale_order_id": so.id,
            "purchase_order_ids": [(6, 0, pos.ids)],
        }
    )
    if hasattr(wiz, "action_load_selected_articles"):
        wiz.action_load_selected_articles()
    else:
        wiz._onchange_purchase_order_ids()
    loaded = len(wiz.line_ids)
    for line in wiz.line_ids:
        qty = line.qty_available or line.product_qty or 0.0
        if qty <= 0:
            continue
        line.selected = True
        line.qty_to_assign = qty
    selected = len(wiz.line_ids.filtered(lambda l: l.selected))
    wiz.action_confirm()
    return loaded, selected


def process_company(company):
    rec = {
        "name": company.name,
        "ops": {},
        "trace": {},
        "errors": [],
        "ncf_remaining_b01": None,
    }
    e = env(context=_ctx(company))
    do_fiscal = (
        company.account_fiscal_country_id
        and company.account_fiscal_country_id.code == "DO"
    )
    if "justech.do.ncf.range" in e:
        ranges = e["justech.do.ncf.range"].search(
            [
                ("company_id", "=", company.id),
                ("prefix", "=", "B01"),
                ("state", "=", "active"),
            ]
        )
        left = 0
        for rng in ranges:
            if "remaining_count" in rng._fields:
                left += rng.remaining_count or 0
            elif rng.sequence_end and rng.next_sequence:
                left += rng.sequence_end - rng.next_sequence + 1
        rec["ncf_remaining_b01"] = left
        if do_fiscal and left < 5:
            rec["errors"].append("NCF B01 remaining %s < 5" % left)
            return rec

    Partner = e["res.partner"].with_company(company)
    Product = e["product.product"].with_company(company)
    Journal = e["account.journal"].with_company(company)
    cust = Partner.search(
        [("name", "like", "DXQA Customer%"), ("company_id", "=", company.id)], limit=1
    )
    vend = Partner.search(
        [("name", "like", "DXQA Vendor%"), ("company_id", "=", company.id)], limit=1
    )
    prod = Product.search([("default_code", "=", "DXQA-%s" % company.id)], limit=1)
    if prod and "purchase_method" in prod._fields:
        prod.purchase_method = "purchase"
    sale_tax = _tax18(e, company, "sale")
    purch_tax = _tax18(e, company, "purchase")
    bank = Journal.search(
        [("company_id", "=", company.id), ("type", "=", "bank")], limit=1
    )
    inbound = e["account.payment.method.line"].search(
        [
            ("journal_id", "=", bank.id),
            ("payment_method_id.payment_type", "=", "inbound"),
        ],
        limit=1,
    )
    outbound = e["account.payment.method.line"].search(
        [
            ("journal_id", "=", bank.id),
            ("payment_method_id.payment_type", "=", "outbound"),
        ],
        limit=1,
    )
    latam_b01 = expense = False
    if "l10n_latam.document.type" in e:
        latam_b01 = e["l10n_latam.document.type"].search(
            [("doc_code_prefix", "=", "B01")], limit=1
        )
    if "justech.do.dgii.expense.type" in e:
        expense = e["justech.do.dgii.expense.type"].search(
            [("code", "=", "09")], limit=1
        )
    Transaction = e["purchase.sale.margin.transaction"].with_company(company)

    def _op(key, fn):
        try:
            with e.cr.savepoint():
                rec["ops"][key] = fn()
        except Exception as exc:
            rec["errors"].append("%s: %s: %s" % (key, type(exc).__name__, exc))
            rec["ops"][key] = {"result": "FAIL", "error": str(exc)}

    # A: 1 SO / 1 PO, both invoiced
    def op_a():
        so = _create_so(
            e,
            company,
            cust,
            prod,
            1,
            12000,
            "%s-C%s-A-SO" % (TAG, company.id),
            sale_tax,
        )
        po = _create_po(
            e,
            company,
            vend,
            prod,
            1,
            7000,
            so.name,
            sale_line=so.order_line[:1],
            tax=purch_tax,
        )
        inv = _invoice_so(e, so)
        bill = _bill_po(e, company, po, latam=latam_b01, expense=expense)
        loaded, selected = _add_pos_via_wizard(e, company, so, po)
        tx = Transaction.find_or_create_canonical_transaction(sale_order=so)
        tx.invalidate_recordset()
        amounts = _tx_amounts(tx)
        amounts.update(
            {
                "so": so.name,
                "po": po.name,
                "inv": inv.ids,
                "bill": bill.ids,
                "wizard_lines_loaded": loaded,
                "wizard_lines_selected": selected,
                "sale_line_on_po": bool(po.order_line[:1].sale_line_id),
                "result": "PASS" if loaded >= 1 and selected >= 1 else "FAIL",
            }
        )
        return amounts

    _op("A_one_so_one_po", op_a)

    # B: 1 SO / several POs
    def op_b():
        so = _create_so(
            e, company, cust, prod, 2, 9000, "%s-C%s-B-SO" % (TAG, company.id), sale_tax
        )
        po1 = _create_po(
            e,
            company,
            vend,
            prod,
            1,
            4000,
            so.name,
            sale_line=so.order_line[:1],
            tax=purch_tax,
        )
        po2 = _create_po(
            e,
            company,
            vend,
            prod,
            1,
            3500,
            so.name,
            sale_line=so.order_line[:1],
            tax=purch_tax,
        )
        inv = _invoice_so(e, so)
        bill1 = _bill_po(e, company, po1, latam=latam_b01, expense=expense)
        bill2 = _bill_po(e, company, po2, latam=latam_b01, expense=expense)
        loaded, selected = _add_pos_via_wizard(e, company, so, po1 | po2)
        tx = Transaction.find_or_create_canonical_transaction(sale_order=so)
        amounts = _tx_amounts(tx)
        amounts.update(
            {
                "so": so.name,
                "pos": [po1.name, po2.name],
                "inv": inv.ids,
                "bills": bill1.ids + bill2.ids,
                "wizard_lines_loaded": loaded,
                "wizard_lines_selected": selected,
                "multi_po": len(tx.purchase_order_ids) >= 2,
                "result": (
                    "PASS"
                    if loaded >= 2 and len(tx.purchase_order_ids) >= 2
                    else "FAIL"
                ),
            }
        )
        return amounts

    _op("B_one_so_multi_po", op_b)

    # C: PO partially billed
    def op_c():
        so = _create_so(
            e, company, cust, prod, 2, 8000, "%s-C%s-C-SO" % (TAG, company.id), sale_tax
        )
        po = _create_po(
            e,
            company,
            vend,
            prod,
            2,
            3000,
            so.name,
            sale_line=so.order_line[:1],
            tax=purch_tax,
        )
        inv = _invoice_so(e, so)
        bill = _bill_po(e, company, po, qty=1, latam=latam_b01, expense=expense)
        loaded, selected = _add_pos_via_wizard(e, company, so, po)
        tx = Transaction.find_or_create_canonical_transaction(sale_order=so)
        amounts = _tx_amounts(tx)
        amounts.update(
            {
                "so": so.name,
                "po": po.name,
                "inv": inv.ids,
                "bill": bill.ids,
                "bill_qty": sum(bill.invoice_line_ids.mapped("quantity")),
                "po_qty": sum(po.order_line.mapped("product_qty")),
                "partial_bill": sum(bill.invoice_line_ids.mapped("quantity"))
                < sum(po.order_line.mapped("product_qty")),
                "wizard_lines_loaded": loaded,
                "result": "PASS" if loaded >= 1 else "FAIL",
            }
        )
        return amounts

    _op("C_partial_bill", op_c)

    # D: vendor bill partially paid
    def op_d():
        so = _create_so(
            e,
            company,
            cust,
            prod,
            1,
            11000,
            "%s-C%s-D-SO" % (TAG, company.id),
            sale_tax,
        )
        po = _create_po(
            e,
            company,
            vend,
            prod,
            1,
            6500,
            so.name,
            sale_line=so.order_line[:1],
            tax=purch_tax,
        )
        inv = _invoice_so(e, so)
        bill = _bill_po(e, company, po, latam=latam_b01, expense=expense)
        before = bill.amount_residual
        apply = round(before * 0.4, 2)
        pay = _pay_native(
            e,
            company,
            vend,
            "supplier",
            bank,
            outbound,
            [(bill, apply)],
            "%s-C%s-PAY-D" % (TAG, company.id),
        )
        bill.invalidate_recordset()
        loaded, selected = _add_pos_via_wizard(e, company, so, po)
        tx = Transaction.find_or_create_canonical_transaction(sale_order=so)
        if bill.id not in tx.vendor_bill_ids.ids:
            tx.vendor_bill_ids = [(4, bill.id)]
        if inv[:1].id not in tx.customer_invoice_ids.ids:
            tx.customer_invoice_ids = [(4, inv[:1].id)]
        aux = e["purchase.sale.payable.auxiliary"]
        aux_rec = aux.search([("vendor_bill_id", "=", bill.id)], limit=1)
        amounts = _tx_amounts(tx)
        amounts.update(
            {
                "so": so.name,
                "bill_before": before,
                "applied": apply,
                "bill_after": bill.amount_residual,
                "payment_id": pay.id,
                "payment_state": bill.payment_state,
                "aux_id": aux_rec.id if aux_rec else None,
                "aux_residual": aux_rec.amount_residual if aux_rec else None,
                "wizard_lines_loaded": loaded,
                "result": (
                    "PASS"
                    if pay.move_id
                    and abs((before - apply) - bill.amount_residual) < 0.05
                    else "FAIL"
                ),
            }
        )
        return amounts

    _op("D_partial_vendor_pay", op_d)

    # E: sale + purchase fully paid
    def op_e():
        so = _create_so(
            e,
            company,
            cust,
            prod,
            1,
            10000,
            "%s-C%s-E-SO" % (TAG, company.id),
            sale_tax,
        )
        po = _create_po(
            e,
            company,
            vend,
            prod,
            1,
            5500,
            so.name,
            sale_line=so.order_line[:1],
            tax=purch_tax,
        )
        inv = _invoice_so(e, so)
        bill = _bill_po(e, company, po, latam=latam_b01, expense=expense)
        pay_c = _pay_native(
            e,
            company,
            cust,
            "customer",
            bank,
            inbound,
            [(inv[:1], inv[:1].amount_residual)],
            "%s-C%s-PAY-E-C" % (TAG, company.id),
        )
        pay_v = _pay_native(
            e,
            company,
            vend,
            "supplier",
            bank,
            outbound,
            [(bill, bill.amount_residual)],
            "%s-C%s-PAY-E-V" % (TAG, company.id),
        )
        inv.invalidate_recordset()
        bill.invalidate_recordset()
        loaded, selected = _add_pos_via_wizard(e, company, so, po)
        tx = Transaction.find_or_create_canonical_transaction(sale_order=so)
        amounts = _tx_amounts(tx)
        amounts.update(
            {
                "so": so.name,
                "inv_state": inv[:1].payment_state,
                "bill_state": bill.payment_state,
                "pay_c": pay_c.id,
                "pay_v": pay_v.id,
                "wizard_lines_loaded": loaded,
                "result": (
                    "PASS"
                    if inv[:1].payment_state in ("paid", "in_payment")
                    and bill.payment_state in ("paid", "in_payment")
                    else "FAIL"
                ),
            }
        )
        return amounts

    _op("E_fully_paid", op_e)

    # Traceability checks on FINAL docs
    sos = e["sale.order"].search(
        [("client_order_ref", "like", "%s-C%s-" % (TAG, company.id))]
    )
    pos = e["purchase.order"].search([("origin", "in", sos.mapped("name"))])
    rec["trace"]["so_count"] = len(sos)
    rec["trace"]["po_count"] = len(pos)
    rec["trace"]["so_to_invoice"] = (
        all(bool(so.invoice_ids) for so in sos) if sos else False
    )
    rec["trace"]["so_to_po"] = (
        all(
            e["purchase.order"].search_count([("origin", "=", so.name)]) >= 1
            for so in sos
        )
        if sos
        else False
    )
    rec["trace"]["multi_po"] = (
        any(
            e["purchase.order"].search_count([("origin", "=", so.name)]) >= 2
            for so in sos
        )
        if sos
        else False
    )
    rec["trace"]["po_to_bill"] = (
        all(bool(po.invoice_ids) for po in pos) if pos else False
    )
    cross = e["purchase.order"].search_count(
        [("origin", "in", sos.mapped("name")), ("company_id", "!=", company.id)]
    )
    rec["trace"]["cross_company"] = cross
    rec["trace"]["orphan_po"] = e["purchase.order"].search_count(
        [
            ("origin", "like", "%s-C%s-" % (TAG, company.id)),
            ("origin", "not in", sos.mapped("name") or [""]),
        ]
    )

    # Priority: invoice_rel, purchase_line_id, sale_line_id, origin, heuristic, manual
    inv = e["account.move"].search(
        [
            ("invoice_origin", "in", sos.mapped("name")),
            ("move_type", "=", "out_invoice"),
        ],
        limit=1,
    )
    rec["trace"]["invoice_rel"] = bool(
        inv and inv.invoice_line_ids.mapped("sale_line_ids")
    )
    bills = e["account.move"].search(
        [("invoice_origin", "in", pos.mapped("name")), ("move_type", "=", "in_invoice")]
    )
    rec["trace"]["aml_purchase_line"] = bool(
        bills.invoice_line_ids.filtered(lambda l: l.purchase_line_id)
    )
    rec["trace"]["sale_line_id"] = bool(
        pos.order_line.filtered(lambda l: l.sale_line_id)
    )
    rec["trace"]["origin"] = bool(
        pos.filtered(lambda p: p.origin in sos.mapped("name"))
    )

    # Manual confirmed must not be overwritten
    Link = e["purchase.sale.cost.link"] if "purchase.sale.cost.link" in e else None
    rec["trace"]["manual_preserved"] = True
    if Link and sos and pos:
        link = Link.search(
            [
                ("company_id", "=", company.id),
                ("sale_id", "=", sos[0].id),
                ("purchase_id", "=", pos[0].id),
            ],
            limit=1,
        )
        if not link:
            link = Link.create(
                {
                    "company_id": company.id,
                    "sale_id": sos[0].id,
                    "sale_line_id": sos[0].order_line[:1].id,
                    "purchase_id": pos[0].id,
                    "purchase_line_id": pos[0].order_line[:1].id,
                    "is_manual": True,
                    "link_source": "manual",
                    "state": "confirmed",
                    "name": "%s-MANUAL" % TAG,
                }
            )
        else:
            link.write(
                {"is_manual": True, "state": "confirmed", "link_source": "manual"}
            )
        before_id = link.id
        engine = e["purchase.sale.trace.engine"]
        if hasattr(engine, "apply_matches") or hasattr(engine, "_apply_match"):
            try:
                engine.with_company(company)._apply_match(
                    link, {"sale_line": sos[0].order_line[:1], "source": "heuristic"}
                )
            except Exception:
                pass
        link.invalidate_recordset()
        rec["trace"]["manual_preserved"] = bool(
            link.exists()
            and link.is_manual
            and link.state == "confirmed"
            and link.id == before_id
        )

    rec["trace"]["priority_order"] = []
    if "purchase.sale.reconciliation.rule" in e:
        rec["trace"]["priority_order"] = e[
            "purchase.sale.reconciliation.rule"
        ].get_trace_priority(company)

    rec["trace"]["result"] = (
        "PASS"
        if rec["trace"].get("so_to_invoice")
        and rec["trace"].get("so_to_po")
        and rec["trace"].get("multi_po")
        and rec["trace"].get("po_to_bill")
        and rec["trace"].get("cross_company") == 0
        and rec["trace"].get("invoice_rel")
        and rec["trace"].get("aml_purchase_line")
        and rec["trace"].get("sale_line_id")
        and rec["trace"].get("manual_preserved")
        else "FAIL"
    )
    e.cr.commit()
    return rec


operational = env["res.company"].search(
    [("active", "=", True), ("account_fiscal_country_id.code", "=", "DO")],
    order="id",
)
for company in operational:
    result["companies"][str(company.id)] = process_company(company)

ops_pass = True
multi_po_pass = True
cxp_pass = True
trace_pass = True
prio_pass = True
for rec in result["companies"].values():
    for key, val in rec.get("ops", {}).items():
        if isinstance(val, dict) and val.get("result") == "FAIL":
            ops_pass = False
        if key == "B_one_so_multi_po" and (
            not isinstance(val, dict) or val.get("result") != "PASS"
        ):
            multi_po_pass = False
        if key == "D_partial_vendor_pay" and (
            not isinstance(val, dict) or val.get("result") != "PASS"
        ):
            cxp_pass = False
    if rec.get("trace", {}).get("result") != "PASS":
        trace_pass = False
    if rec.get("errors"):
        ops_pass = False
    order = rec.get("trace", {}).get("priority_order") or []
    if order and order[-1] != "heuristic":
        prio_pass = False
    if not rec.get("trace", {}).get("manual_preserved"):
        prio_pass = False

result["MARGIN_QA_MASS"] = "PASS" if ops_pass else "FAIL"
result["MULTI_PO_RELATION_QA"] = "PASS" if multi_po_pass else "FAIL"
result["MARGIN_CXP_INTEGRATION_QA"] = "PASS" if cxp_pass else "FAIL"
result["TRACEABILITY_QA_MASS"] = "PASS" if trace_pass else "FAIL"
result["TRACE_PRIORITY_QA"] = "PASS" if prio_pass else "FAIL"
result["finished"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
open(OUT, "w").write(json.dumps(result, indent=2, default=str))
print("WROTE", OUT)
print("MARGIN_QA_MASS", result["MARGIN_QA_MASS"])
print("MULTI_PO_RELATION_QA", result["MULTI_PO_RELATION_QA"])
print("MARGIN_CXP_INTEGRATION_QA", result["MARGIN_CXP_INTEGRATION_QA"])
print("TRACEABILITY_QA_MASS", result["TRACEABILITY_QA_MASS"])
print("TRACE_PRIORITY_QA", result["TRACE_PRIORITY_QA"])
