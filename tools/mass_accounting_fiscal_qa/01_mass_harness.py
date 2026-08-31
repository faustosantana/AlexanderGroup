# -*- coding: utf-8 -*-
"""Mass accounting/fiscal QA on STAGING only. Prefix DXQA-MASS. No mail. No prod."""

import json
import os
import time
from collections import defaultdict

TAG = "DXQA-MASS-20260831"
INV_DATE = "2026-08-15"
PAY_DATE = "2026-08-20"
CN_DATE = "2026-08-22"
OVERDUE_DATE = "2026-06-15"
DUE_OPEN = "2026-07-01"
DUE_FUTURE = "2026-09-30"
OUT = "/tmp/mass_qa_harness.json"

ctx_mail = {
    "mail_notrack": True,
    "tracking_disable": True,
    "mail_create_nolog": True,
    "mail_create_nosubscribe": True,
}

only = os.environ.get("QA_COMPANY_IDS", "").strip()
only_ids = [int(x) for x in only.split(",") if x.strip().isdigit()] if only else []

report = {
    "tag": TAG,
    "companies": {},
    "errors": [],
    "started": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
}


def _ctx(company):
    return dict(
        env.context,
        allowed_company_ids=[company.id],
        justech_approval_skip=True,
        **ctx_mail,
    )


def _tax18(Tax, company, use):
    return Tax.search(
        [
            ("company_id", "=", company.id),
            ("type_tax_use", "=", use),
            ("amount", "=", 18),
            ("active", "=", True),
            ("name", "ilike", "ITBIS"),
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


def _tax_named(Tax, company, use, needle):
    return Tax.search(
        [
            ("company_id", "=", company.id),
            ("type_tax_use", "=", use),
            ("active", "=", True),
            ("name", "ilike", needle),
        ],
        limit=1,
    )


def ensure_partner(
    Partner, company, name, vat, supplier=False, doc=None, do_fiscal=True
):
    rec = Partner.search(
        [("name", "=", name), ("company_id", "=", company.id)], limit=1
    )
    if not rec:
        rec = Partner.search([("name", "=", name), ("vat", "=", vat)], limit=1)
    vals = {
        "name": name,
        "company_id": company.id,
        "vat": vat,
        "country_id": env.ref("base.do").id if do_fiscal else env.ref("base.us").id,
        "is_company": True,
        "customer_rank": 0 if supplier else 1,
        "supplier_rank": 1 if supplier else 0,
        "email": "dxqa.noreply@example.invalid",
    }
    if not rec:
        rec = Partner.create(vals)
    write_vals = {
        "justech_do_rnc_status": "valid" if do_fiscal else "pending",
        "justech_do_fiscal_config_state": (
            "validated_padron" if do_fiscal else "not_applicable"
        ),
        "justech_do_fiscal_config_source": "DXQA mass fiscal QA (isolated)",
        "justech_do_rnc_official_name": name,
    }
    if do_fiscal and doc:
        write_vals["justech_do_default_document_type_id"] = doc.id
    rec.write(write_vals)
    return rec


def ensure_product(Product, company, code, taxes, ptaxes):
    rec = Product.search([("default_code", "=", code)], limit=1)
    if rec:
        return rec
    return Product.create(
        {
            "name": "DXQA product %s" % code,
            "default_code": code,
            "list_price": 10000,
            "standard_price": 6000,
            "type": "consu",
            "company_id": company.id,
            "taxes_id": [(6, 0, taxes.ids)] if taxes else False,
            "supplier_taxes_id": [(6, 0, ptaxes.ids)] if ptaxes else False,
        }
    )


def create_move(
    Move,
    company,
    move_type,
    partner,
    journal,
    ref,
    price,
    product,
    taxes=None,
    invoice_date=INV_DATE,
    due=DUE_FUTURE,
    ncf=None,
    doc=None,
    extra_line=None,
    expense_type=None,
    latam_type=None,
    registration_mode=None,
    received_ncf=None,
):
    line = {
        "product_id": product.id,
        "name": ref,
        "quantity": 1,
        "price_unit": price,
    }
    if taxes:
        line["tax_ids"] = [(6, 0, taxes.ids)]
    else:
        line["tax_ids"] = [(6, 0, [])]
    vals = {
        "move_type": move_type,
        "company_id": company.id,
        "partner_id": partner.id,
        "journal_id": journal.id,
        "invoice_date": invoice_date,
        "invoice_date_due": due,
        "invoice_line_ids": [(0, 0, line)],
        "ref": ref,
    }
    if extra_line:
        vals["invoice_line_ids"].append((0, 0, extra_line))
    if doc and "justech_do_document_type_id" in Move._fields:
        vals["justech_do_document_type_id"] = doc.id
    if ncf:
        if "justech_do_ncf" in Move._fields:
            vals["justech_do_ncf"] = ncf
        if "l10n_latam_document_number" in Move._fields:
            vals["l10n_latam_document_number"] = ncf
    if received_ncf and "l10n_latam_document_number" in Move._fields:
        vals["l10n_latam_document_number"] = received_ncf
    if latam_type and "l10n_latam_document_type_id" in Move._fields:
        vals["l10n_latam_document_type_id"] = latam_type.id
    if registration_mode and "justech_do_purchase_registration_mode" in Move._fields:
        vals["justech_do_purchase_registration_mode"] = registration_mode
    if expense_type and "justech_do_expense_type_id" in Move._fields:
        vals["justech_do_expense_type_id"] = expense_type.id
    existing = Move.search(
        [("ref", "=", ref), ("company_id", "=", company.id)], limit=1
    )
    if existing:
        if existing.state == "draft":
            if expense_type and "justech_do_expense_type_id" in Move._fields:
                existing.justech_do_expense_type_id = expense_type.id
            existing.action_post()
        return existing
    move = Move.create(vals)
    move.action_post()
    return move


def pay_moves(
    company, partner, partner_type, journal, method, moves_amounts, ref, received=None
):
    Wizard = (
        env["multi.invoice.manual.payment.wizard"]
        .with_company(company)
        .with_context(force_payment_move=True)
    )
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
            "amount_received": received if received is not None else total,
            "line_ids": lines,
        }
    )
    action = wiz.action_create_payment()
    pay = env["account.payment"].browse(action.get("res_id"))
    return pay


def reverse_move(move, journal, reason, fraction=1.0, vendor_cn_ncf=None):
    Reversal = env["account.move.reversal"]
    vals = {
        "reason": reason,
        "date": CN_DATE,
        "journal_id": journal.id,
    }
    if "move_ids" in Reversal._fields:
        vals["move_ids"] = [(6, 0, move.ids)]
    if "company_id" in Reversal._fields:
        vals["company_id"] = move.company_id.id
    if vendor_cn_ncf and "justech_vendor_cn_ncf" in Reversal._fields:
        vals["justech_vendor_cn_ncf"] = vendor_cn_ncf
        vals["justech_vendor_cn_date"] = CN_DATE
    rev = Reversal.with_context(
        active_model="account.move",
        active_ids=move.ids,
        active_id=move.id,
        justech_approval_skip=True,
        **ctx_mail,
    ).create(vals)
    action = rev.refund_moves()
    cn = env["account.move"]
    if isinstance(action, dict) and action.get("res_id"):
        cn = env["account.move"].browse(action["res_id"])
    elif isinstance(action, dict) and action.get("domain"):
        cn = env["account.move"].search(action["domain"], limit=1)
    if not cn:
        cn = env["account.move"].search(
            [("reversed_entry_id", "=", move.id)], order="id desc", limit=1
        )
    if cn and fraction < 1.0 and cn.state == "draft":
        for line in cn.invoice_line_ids:
            line.price_unit = line.price_unit * fraction
        cn.action_post()
    elif cn and cn.state == "draft":
        cn.action_post()
    return cn


def void_ncf(move):
    Wiz = env["justech.do.ncf.void.wizard"]
    wiz = Wiz.create(
        {
            "move_id": move.id,
            "cancel_type": "04",
            "acknowledge_accounting_intact": True,
            "observation": "DXQA mass QA void — not a real NCF",
        }
    )
    wiz.action_confirm_void()
    return move


def process_company(company):
    t0 = time.time()
    rec = {
        "name": company.name,
        "currency": company.currency_id.name,
        "fiscal_country": (
            company.account_fiscal_country_id.code
            if company.account_fiscal_country_id
            else None
        ),
        "sales": [],
        "bills": [],
        "payments": [],
        "credit_notes": [],
        "voids": [],
        "errors": [],
        "flags": {},
    }
    e = env(context=_ctx(company))
    Move = e["account.move"].with_company(company)
    Tax = e["account.tax"].with_company(company)
    Partner = e["res.partner"].with_company(company)
    Product = e["product.product"].with_company(company)
    Journal = e["account.journal"].with_company(company)
    PML = e["account.payment.method.line"]

    sale_j = Journal.search(
        [("company_id", "=", company.id), ("type", "=", "sale"), ("active", "=", True)],
        limit=1,
    )
    purch_j = Journal.search(
        [
            ("company_id", "=", company.id),
            ("type", "=", "purchase"),
            ("active", "=", True),
        ],
        limit=1,
    )
    bank_j = Journal.search(
        [("company_id", "=", company.id), ("type", "=", "bank"), ("active", "=", True)],
        limit=1,
    )
    inbound = PML.search(
        [
            ("journal_id", "=", bank_j.id),
            ("payment_method_id.payment_type", "=", "inbound"),
        ],
        limit=1,
    )
    outbound = PML.search(
        [
            ("journal_id", "=", bank_j.id),
            ("payment_method_id.payment_type", "=", "outbound"),
        ],
        limit=1,
    )
    sale_tax = _tax18(Tax, company, "sale")
    purch_tax = _tax18(Tax, company, "purchase")
    purch_serv = _tax_named(Tax, company, "purchase", "ITBIS Serv") or purch_tax
    purch_good = _tax_named(Tax, company, "purchase", "Cost Good") or purch_tax
    do_fiscal = company.account_fiscal_country_id.code == "DO"
    doc_b01 = doc_b04 = False
    if do_fiscal and "justech.do.fiscal.document.type" in e:
        doc_b01 = e["justech.do.fiscal.document.type"].search(
            [("prefix", "=", "B01")], limit=1
        )
        doc_b04 = e["justech.do.fiscal.document.type"].search(
            [("prefix", "=", "B04")], limit=1
        )
    rec["flags"]["ncf_configured"] = bool(
        do_fiscal
        and e["justech.do.ncf.range"].search_count(
            [("company_id", "=", company.id), ("state", "=", "active")]
        )
    )
    rec["flags"]["withholding_configured"] = bool(
        "justech.do.withholding.company.config" in e
        and e["justech.do.withholding.company.config"].search_count(
            [("company_id", "=", company.id), ("active_config", "=", True)]
        )
    )
    rec["flags"]["b17_configured"] = bool(
        do_fiscal
        and e["justech.do.ncf.range"].search_count(
            [
                ("company_id", "=", company.id),
                ("prefix", "=", "B17"),
                ("state", "=", "active"),
            ]
        )
    )

    slug = (
        "".join(ch for ch in company.name if ch.isalnum())[:10].upper()
        or "C%s" % company.id
    )
    cust = ensure_partner(
        Partner,
        company,
        "DXQA Customer %s" % slug,
        "1019920%02d" % company.id,
        supplier=False,
        doc=doc_b01,
        do_fiscal=do_fiscal,
    )
    vend = ensure_partner(
        Partner,
        company,
        "DXQA Vendor %s" % slug,
        "2019920%02d" % company.id,
        supplier=True,
        doc=doc_b01,
        do_fiscal=do_fiscal,
    )
    prod = ensure_product(Product, company, "DXQA-%s" % company.id, sale_tax, purch_tax)
    rec["customer_id"] = cust.id
    rec["vendor_id"] = vend.id
    rec["product_id"] = prod.id
    exp_cost = exp_serv = False
    if "justech.do.dgii.expense.type" in e:
        exp_cost = e["justech.do.dgii.expense.type"].search(
            [("code", "=", "09")], limit=1
        )
        exp_serv = e["justech.do.dgii.expense.type"].search(
            [("code", "=", "02")], limit=1
        )
    latam_b01 = False
    if "l10n_latam.document.type" in e:
        latam_b01 = e["l10n_latam.document.type"].search(
            [("doc_code_prefix", "=", "B01")], limit=1
        )
    e.cr.commit()

    sales = {}

    def _sale(key, price, tax, due=DUE_FUTURE, invoice_date=INV_DATE):
        ref = "%s-C%s-S-%s" % (TAG, company.id, key)
        try:
            with e.cr.savepoint():
                inv = create_move(
                    Move,
                    company,
                    "out_invoice",
                    cust,
                    sale_j,
                    ref,
                    price,
                    prod,
                    taxes=tax,
                    invoice_date=invoice_date,
                    due=due,
                    doc=doc_b01 if rec["flags"]["ncf_configured"] else None,
                )
            sales[key] = inv
            rec["sales"].append(
                {
                    "key": key,
                    "id": inv.id,
                    "name": inv.name,
                    "total": inv.amount_total,
                    "residual": inv.amount_residual,
                    "tax": inv.amount_tax,
                    "ncf": getattr(inv, "justech_do_ncf", None),
                    "state": inv.state,
                    "payment_state": inv.payment_state,
                }
            )
            return inv
        except Exception as exc:
            rec["errors"].append("SALE %s: %s: %s" % (key, type(exc).__name__, exc))
            return None

    # 10 full → paid as multi 2+3+5
    for i in range(1, 11):
        _sale("FULL%02d" % i, 5000, sale_tax)
    # 8 partial
    for i in range(1, 9):
        _sale("PART%02d" % i, 5000, sale_tax)
    # 5 multi-partial; first is residual ladder 10000 no tax
    _sale("LADDER", 10000, None)
    for i in range(2, 6):
        _sale("MPART%02d" % i, 8000, None)
    # 5 unpaid (2 later voided)
    for i in range(1, 6):
        _sale("UNPAID%02d" % i, 4000, sale_tax, due=DUE_OPEN, invoice_date=OVERDUE_DATE)
    # 4 multi-invoice dedicated
    for i in range(1, 5):
        _sale("MULTI%02d" % i, 3000, sale_tax)
    # 3 partial CN + 2 full CN
    for i in range(1, 4):
        _sale("CNPART%02d" % i, 6000, sale_tax)
    for i in range(1, 3):
        _sale("CNFULL%02d" % i, 4500, sale_tax)
    # 2 extra full (withholding N/A)
    for i in range(1, 3):
        _sale("XFULL%02d" % i, 3500, sale_tax)
    # 1 special: higher amount
    _sale("SPECIAL", 25000, sale_tax)

    bills = {}

    def _bill(key, price, tax, ncf_seq, expense=None):
        ref = "%s-C%s-B-%s" % (TAG, company.id, key)
        received = "B01%02d%02d%04d" % (88, company.id, ncf_seq)
        try:
            with e.cr.savepoint():
                bill = create_move(
                    Move,
                    company,
                    "in_invoice",
                    vend,
                    purch_j,
                    ref,
                    price,
                    prod,
                    taxes=tax,
                    expense_type=expense or exp_cost,
                    latam_type=latam_b01,
                    registration_mode="received",
                    received_ncf=received,
                )
            bills[key] = bill
            rec["bills"].append(
                {
                    "key": key,
                    "id": bill.id,
                    "name": bill.name,
                    "total": bill.amount_total,
                    "residual": bill.amount_residual,
                    "tax": bill.amount_tax,
                    "ncf": getattr(bill, "justech_do_ncf", None),
                    "state": bill.state,
                    "payment_state": bill.payment_state,
                }
            )
            return bill
        except Exception as exc:
            rec["errors"].append("BILL %s: %s: %s" % (key, type(exc).__name__, exc))
            return None

    seq = 1
    for i in range(1, 11):
        _bill("FULL%02d" % i, 4000, purch_tax, seq)
        seq += 1
    for i in range(1, 9):
        _bill("PART%02d" % i, 4000, purch_tax, seq)
        seq += 1
    _bill("LADDER", 10000, None, seq)
    seq += 1
    for i in range(2, 6):
        _bill("MPART%02d" % i, 7000, None, seq)
        seq += 1
    for i in range(1, 6):
        _bill("UNPAID%02d" % i, 3500, purch_tax, seq)
        seq += 1
    for i in range(1, 5):
        _bill("MULTI%02d" % i, 2500, purch_tax, seq)
        seq += 1
    for i in range(1, 4):
        _bill("CNPART%02d" % i, 5000, purch_tax, seq)
        seq += 1
    for i in range(1, 3):
        _bill("CNFULL%02d" % i, 3800, purch_tax, seq)
        seq += 1
    for i in range(1, 3):
        _bill("XFULL%02d" % i, 2800, purch_tax, seq)
        seq += 1
    _bill("EXPGOOD", 2200, purch_good, seq, expense=exp_cost)
    seq += 1
    _bill("EXPSERV", 2200, purch_serv, seq, expense=exp_serv)
    seq += 1
    _bill("SPECIAL", 18000, purch_tax, seq)

    def _safe_pay(label, partner, ptype, journal, method, pairs, ref, received=None):
        pairs = [(m, a) for m, a in pairs if m]
        if not pairs:
            rec["errors"].append("PAY skip empty %s" % label)
            return None
        try:
            with e.cr.savepoint():
                pay = pay_moves(
                    company, partner, ptype, journal, method, pairs, ref, received
                )
            rec["payments"].append(
                {
                    "label": label,
                    "id": pay.id if pay else None,
                    "name": pay.name if pay else None,
                    "amount": pay.amount if pay else None,
                    "state": pay.state if pay else None,
                    "applied": len(pay.justech_applied_invoice_ids) if pay else 0,
                    "invoices": [m.id for m, _a in pairs],
                }
            )
            return pay
        except Exception as exc:
            rec["errors"].append("PAY %s: %s: %s" % (label, type(exc).__name__, exc))
            return None

    # Customer payments
    fulls = [sales.get("FULL%02d" % i) for i in range(1, 11)]
    _safe_pay(
        "cust_multi2",
        cust,
        "customer",
        bank_j,
        inbound,
        [
            (fulls[0], fulls[0].amount_residual if fulls[0] else 0),
            (fulls[1], fulls[1].amount_residual if fulls[1] else 0),
        ],
        "%s-C%s-PAY-C-M2" % (TAG, company.id),
    )
    _safe_pay(
        "cust_multi3",
        cust,
        "customer",
        bank_j,
        inbound,
        [
            (fulls[2], fulls[2].amount_residual if fulls[2] else 0),
            (fulls[3], fulls[3].amount_residual if fulls[3] else 0),
            (fulls[4], fulls[4].amount_residual if fulls[4] else 0),
        ],
        "%s-C%s-PAY-C-M3" % (TAG, company.id),
    )
    _safe_pay(
        "cust_multi5",
        cust,
        "customer",
        bank_j,
        inbound,
        [(fulls[i], fulls[i].amount_residual if fulls[i] else 0) for i in range(5, 10)],
        "%s-C%s-PAY-C-M5" % (TAG, company.id),
    )
    multis = [sales.get("MULTI%02d" % i) for i in range(1, 5)]
    _safe_pay(
        "cust_multi4",
        cust,
        "customer",
        bank_j,
        inbound,
        [(m, m.amount_residual if m else 0) for m in multis],
        "%s-C%s-PAY-C-M4" % (TAG, company.id),
    )
    for i in range(1, 9):
        inv = sales.get("PART%02d" % i)
        if inv:
            _safe_pay(
                "cust_partial_%02d" % i,
                cust,
                "customer",
                bank_j,
                inbound,
                [(inv, round(inv.amount_residual * 0.4, 2))],
                "%s-C%s-PAY-C-P%02d" % (TAG, company.id, i),
            )
    ladder = sales.get("LADDER")
    if ladder:
        _safe_pay(
            "cust_ladder1",
            cust,
            "customer",
            bank_j,
            inbound,
            [(ladder, 4000)],
            "%s-C%s-PAY-C-L1" % (TAG, company.id),
        )
        ladder.invalidate_recordset()
        rec["flags"]["residual_after_4000"] = ladder.amount_residual
        _safe_pay(
            "cust_ladder2",
            cust,
            "customer",
            bank_j,
            inbound,
            [(ladder, 2500)],
            "%s-C%s-PAY-C-L2" % (TAG, company.id),
        )
        ladder.invalidate_recordset()
        rec["flags"]["residual_after_2500"] = ladder.amount_residual
        _safe_pay(
            "cust_ladder3",
            cust,
            "customer",
            bank_j,
            inbound,
            [(ladder, 3500)],
            "%s-C%s-PAY-C-L3" % (TAG, company.id),
        )
        ladder.invalidate_recordset()
        rec["flags"]["residual_after_3500"] = ladder.amount_residual
        rec["flags"]["residual_ladder_ok"] = (
            abs((ladder.amount_residual or 0) - 0) < 0.05
        )
    for i in range(2, 6):
        inv = sales.get("MPART%02d" % i)
        if not inv:
            continue
        half = round(inv.amount_residual / 2.0, 2)
        _safe_pay(
            "cust_mpart_%02d_a" % i,
            cust,
            "customer",
            bank_j,
            inbound,
            [(inv, half)],
            "%s-C%s-PAY-C-MP%02da" % (TAG, company.id, i),
        )
        inv.invalidate_recordset()
        rest = inv.amount_residual
        _safe_pay(
            "cust_mpart_%02d_b" % i,
            cust,
            "customer",
            bank_j,
            inbound,
            [(inv, rest)],
            "%s-C%s-PAY-C-MP%02db" % (TAG, company.id, i),
        )
    for i in range(1, 3):
        inv = sales.get("XFULL%02d" % i)
        if inv:
            _safe_pay(
                "cust_xfull_%02d" % i,
                cust,
                "customer",
                bank_j,
                inbound,
                [(inv, inv.amount_residual)],
                "%s-C%s-PAY-C-X%02d" % (TAG, company.id, i),
            )
    spec = sales.get("SPECIAL")
    if spec:
        _safe_pay(
            "cust_special",
            cust,
            "customer",
            bank_j,
            inbound,
            [(spec, spec.amount_residual)],
            "%s-C%s-PAY-C-SP" % (TAG, company.id),
        )

    # Credit notes
    for i in range(1, 4):
        inv = sales.get("CNPART%02d" % i)
        if not inv:
            continue
        try:
            with e.cr.savepoint():
                cn = reverse_move(inv, sale_j, "%s partial CN" % TAG, fraction=0.3)
            rec["credit_notes"].append(
                {
                    "origin": inv.id,
                    "id": cn.id if cn else None,
                    "total": cn.amount_total if cn else None,
                    "ncf": getattr(cn, "justech_do_ncf", None) if cn else None,
                    "kind": "partial",
                }
            )
        except Exception as exc:
            rec["errors"].append("CN PART %s: %s: %s" % (i, type(exc).__name__, exc))
    for i in range(1, 3):
        inv = sales.get("CNFULL%02d" % i)
        if not inv:
            continue
        try:
            with e.cr.savepoint():
                cn = reverse_move(inv, sale_j, "%s full CN" % TAG, fraction=1.0)
            rec["credit_notes"].append(
                {
                    "origin": inv.id,
                    "id": cn.id if cn else None,
                    "total": cn.amount_total if cn else None,
                    "ncf": getattr(cn, "justech_do_ncf", None) if cn else None,
                    "kind": "full",
                }
            )
        except Exception as exc:
            rec["errors"].append("CN FULL %s: %s: %s" % (i, type(exc).__name__, exc))

    # 608 voids on 2 unpaid (NCF only)
    if rec["flags"]["ncf_configured"]:
        for i in (1, 2):
            inv = sales.get("UNPAID%02d" % i)
            if not inv or not getattr(inv, "justech_do_ncf", None):
                continue
            try:
                with e.cr.savepoint():
                    void_ncf(inv)
                inv.invalidate_recordset()
                rec["voids"].append(
                    {
                        "id": inv.id,
                        "ncf": inv.justech_do_ncf,
                        "voided": bool(getattr(inv, "justech_do_ncf_voided", False)),
                    }
                )
            except Exception as exc:
                rec["errors"].append("VOID %s: %s: %s" % (i, type(exc).__name__, exc))

    # Vendor payments (mirror)
    bfulls = [bills.get("FULL%02d" % i) for i in range(1, 11)]
    _safe_pay(
        "vend_multi2",
        vend,
        "supplier",
        bank_j,
        outbound,
        [
            (bfulls[0], bfulls[0].amount_residual if bfulls[0] else 0),
            (bfulls[1], bfulls[1].amount_residual if bfulls[1] else 0),
        ],
        "%s-C%s-PAY-V-M2" % (TAG, company.id),
    )
    _safe_pay(
        "vend_multi3",
        vend,
        "supplier",
        bank_j,
        outbound,
        [
            (bfulls[i], bfulls[i].amount_residual if bfulls[i] else 0)
            for i in range(2, 5)
        ],
        "%s-C%s-PAY-V-M3" % (TAG, company.id),
    )
    _safe_pay(
        "vend_multi5",
        vend,
        "supplier",
        bank_j,
        outbound,
        [
            (bfulls[i], bfulls[i].amount_residual if bfulls[i] else 0)
            for i in range(5, 10)
        ],
        "%s-C%s-PAY-V-M5" % (TAG, company.id),
    )
    bmultis = [bills.get("MULTI%02d" % i) for i in range(1, 5)]
    _safe_pay(
        "vend_multi4",
        vend,
        "supplier",
        bank_j,
        outbound,
        [(m, m.amount_residual if m else 0) for m in bmultis],
        "%s-C%s-PAY-V-M4" % (TAG, company.id),
    )
    for i in range(1, 9):
        bill = bills.get("PART%02d" % i)
        if bill:
            _safe_pay(
                "vend_partial_%02d" % i,
                vend,
                "supplier",
                bank_j,
                outbound,
                [(bill, round(bill.amount_residual * 0.4, 2))],
                "%s-C%s-PAY-V-P%02d" % (TAG, company.id, i),
            )
    bl = bills.get("LADDER")
    if bl:
        _safe_pay(
            "vend_ladder1",
            vend,
            "supplier",
            bank_j,
            outbound,
            [(bl, 4000)],
            "%s-C%s-PAY-V-L1" % (TAG, company.id),
        )
        bl.invalidate_recordset()
        rec["flags"]["ap_residual_after_4000"] = bl.amount_residual
        _safe_pay(
            "vend_ladder2",
            vend,
            "supplier",
            bank_j,
            outbound,
            [(bl, 2500)],
            "%s-C%s-PAY-V-L2" % (TAG, company.id),
        )
        bl.invalidate_recordset()
        rec["flags"]["ap_residual_after_2500"] = bl.amount_residual
        _safe_pay(
            "vend_ladder3",
            vend,
            "supplier",
            bank_j,
            outbound,
            [(bl, 3500)],
            "%s-C%s-PAY-V-L3" % (TAG, company.id),
        )
        bl.invalidate_recordset()
        rec["flags"]["ap_residual_after_3500"] = bl.amount_residual
    for i in range(2, 6):
        bill = bills.get("MPART%02d" % i)
        if not bill:
            continue
        half = round(bill.amount_residual / 2.0, 2)
        _safe_pay(
            "vend_mpart_%02d_a" % i,
            vend,
            "supplier",
            bank_j,
            outbound,
            [(bill, half)],
            "%s-C%s-PAY-V-MP%02da" % (TAG, company.id, i),
        )
        bill.invalidate_recordset()
        _safe_pay(
            "vend_mpart_%02d_b" % i,
            vend,
            "supplier",
            bank_j,
            outbound,
            [(bill, bill.amount_residual)],
            "%s-C%s-PAY-V-MP%02db" % (TAG, company.id, i),
        )
    for i in range(1, 3):
        bill = bills.get("XFULL%02d" % i)
        if bill:
            _safe_pay(
                "vend_xfull_%02d" % i,
                vend,
                "supplier",
                bank_j,
                outbound,
                [(bill, bill.amount_residual)],
                "%s-C%s-PAY-V-X%02d" % (TAG, company.id, i),
            )
    for key in ("EXPGOOD", "EXPSERV", "SPECIAL"):
        bill = bills.get(key)
        if bill:
            _safe_pay(
                "vend_%s" % key,
                vend,
                "supplier",
                bank_j,
                outbound,
                [(bill, bill.amount_residual)],
                "%s-C%s-PAY-V-%s" % (TAG, company.id, key),
            )

    for i in range(1, 4):
        bill = bills.get("CNPART%02d" % i)
        if not bill:
            continue
        try:
            with e.cr.savepoint():
                cn = reverse_move(
                    bill,
                    purch_j,
                    "%s vendor partial CN" % TAG,
                    fraction=0.3,
                    vendor_cn_ncf="B04%02d%02d%04d" % (88, company.id, 100 + i),
                )
            rec["credit_notes"].append(
                {
                    "origin": bill.id,
                    "id": cn.id if cn else None,
                    "total": cn.amount_total if cn else None,
                    "kind": "vendor_partial",
                    "ncf": getattr(cn, "justech_do_ncf", None) if cn else None,
                }
            )
        except Exception as exc:
            rec["errors"].append("VCN PART %s: %s: %s" % (i, type(exc).__name__, exc))
    for i in range(1, 3):
        bill = bills.get("CNFULL%02d" % i)
        if not bill:
            continue
        try:
            with e.cr.savepoint():
                cn = reverse_move(
                    bill,
                    purch_j,
                    "%s vendor full CN" % TAG,
                    fraction=1.0,
                    vendor_cn_ncf="B04%02d%02d%04d" % (88, company.id, 200 + i),
                )
            rec["credit_notes"].append(
                {
                    "origin": bill.id,
                    "id": cn.id if cn else None,
                    "total": cn.amount_total if cn else None,
                    "kind": "vendor_full",
                    "ncf": getattr(cn, "justech_do_ncf", None) if cn else None,
                }
            )
        except Exception as exc:
            rec["errors"].append("VCN FULL %s: %s: %s" % (i, type(exc).__name__, exc))

    # Trace/margin subset: 1 SO + 1 PO if models exist
    rec["flags"]["so_id"] = None
    rec["flags"]["po_id"] = None
    try:
        if "sale.order" in e:
            so = (
                e["sale.order"]
                .with_company(company)
                .create(
                    {
                        "partner_id": cust.id,
                        "company_id": company.id,
                        "client_order_ref": "%s-C%s-SO" % (TAG, company.id),
                        "order_line": [
                            (
                                0,
                                0,
                                {
                                    "product_id": prod.id,
                                    "product_uom_qty": 1,
                                    "price_unit": 9000,
                                },
                            )
                        ],
                    }
                )
            )
            so.action_confirm()
            rec["flags"]["so_id"] = so.id
            rec["flags"]["so_state"] = so.state
    except Exception as exc:
        rec["errors"].append("SO: %s: %s" % (type(exc).__name__, exc))
    try:
        if "purchase.order" in e:
            po = (
                e["purchase.order"]
                .with_company(company)
                .create(
                    {
                        "partner_id": vend.id,
                        "company_id": company.id,
                        "partner_ref": "%s-C%s-PO" % (TAG, company.id),
                        "order_line": [
                            (
                                0,
                                0,
                                {
                                    "product_id": prod.id,
                                    "name": "DXQA PO line",
                                    "product_qty": 1,
                                    "price_unit": 5400,
                                },
                            )
                        ],
                    }
                )
            )
            po.button_confirm()
            rec["flags"]["po_id"] = po.id
            rec["flags"]["po_state"] = po.state
    except Exception as exc:
        rec["errors"].append("PO: %s: %s" % (type(exc).__name__, exc))

    rec["counts"] = {
        "sales": len(rec["sales"]),
        "bills": len(rec["bills"]),
        "payments": len(rec["payments"]),
        "credit_notes": len(rec["credit_notes"]),
        "voids": len(rec["voids"]),
        "errors": len(rec["errors"]),
    }
    rec["seconds"] = round(time.time() - t0, 2)
    e.cr.commit()
    return rec


companies = env["res.company"].search([("active", "=", True)], order="id")
if only_ids:
    companies = companies.filtered(lambda c: c.id in only_ids)

print("HARNESS_COMPANIES", [(c.id, c.name) for c in companies])
for company in companies:
    print("BEGIN_COMPANY", company.id, company.name)
    try:
        rec = process_company(company)
        report["companies"][str(company.id)] = rec
        print(
            "END_COMPANY",
            company.id,
            rec["counts"],
            "errors",
            rec["counts"]["errors"],
            "sec",
            rec["seconds"],
        )
    except Exception as exc:
        env.cr.rollback()
        report["errors"].append(
            "COMPANY %s: %s: %s" % (company.id, type(exc).__name__, exc)
        )
        print("FAIL_COMPANY", company.id, type(exc).__name__, exc)

report["finished"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
with open(OUT, "w", encoding="utf-8") as fh:
    json.dump(report, fh, indent=2, default=str)
print("HARNESS_WRITTEN", OUT)
print(
    "TOTALS",
    "sales",
    sum(c["counts"]["sales"] for c in report["companies"].values()),
    "bills",
    sum(c["counts"]["bills"] for c in report["companies"].values()),
    "pays",
    sum(c["counts"]["payments"] for c in report["companies"].values()),
    "cns",
    sum(c["counts"]["credit_notes"] for c in report["companies"].values()),
)
