# ruff: noqa
"""QA de permisos en staging (o verificación de grupos en prod).

No consume NCF: usa SAVEPOINT y rollback.
No envía email, e-CF ni DGII.
No toca facturas históricas.
"""

from __future__ import annotations

import json
import os
import sys

from odoo.exceptions import AccessError, UserError, ValidationError

sys.path.insert(0, "/tmp")
from catalog import (  # noqa: E402
    DEFAULT_COMPANY_ID,
    OPERATIONAL_COMPANY_IDS,
    PEOPLE,
)

OUT = os.environ.get("ODOO_USER_QA_OUT", "/tmp/odoo_user_qa.json")
LIVE_DOCS = os.environ.get("ODOO_QA_LIVE_DOCS") == "1"


def _user(env, login):
    return (
        env["res.users"]
        .with_context(active_test=False)
        .search([("login", "=", login)], limit=1)
    )


def _flags(user):
    return {
        "SALES": user.has_group("sales_team.group_sale_salesman"),
        "SALES_ALL": user.has_group("sales_team.group_sale_salesman_all_leads"),
        "PURCHASE": user.has_group("purchase.group_purchase_user"),
        "INVOICING": user.has_group("account.group_account_invoice"),
        "ACCOUNTING_ADMIN": user.has_group("account.group_account_manager"),
        "ODOO_ADMIN": user.has_group("base.group_system"),
        "ACCESS_RIGHTS": user.has_group("base.group_erp_manager"),
        "FISCAL_USER": user.has_group(
            "justech_l10n_do_base.group_justech_do_fiscal_user"
        ),
        "FISCAL_MANAGER": user.has_group(
            "justech_l10n_do_base.group_justech_do_fiscal_manager"
        ),
        "SELF_APPROVE": user.has_group("justech_approval_flow.group_self_approve"),
    }


def _partner(envu, company_id):
    return envu["res.partner"].create(
        {
            "name": "DX QA USER PROVISION — NO FISCAL REAL",
            "company_id": company_id,
            "email": "noreply-qa-users@invalid.local",
        }
    )


def _product(env_admin, company_id):
    Product = env_admin["product.product"].sudo()
    existing = Product.search(
        [
            ("default_code", "=", "DX-QA-USER-PROV"),
            ("company_id", "in", [False, company_id]),
        ],
        limit=1,
    )
    sale_tax = (
        env_admin["account.tax"]
        .sudo()
        .search(
            [
                ("company_id", "=", company_id),
                ("type_tax_use", "=", "sale"),
                ("amount", "=", 0),
            ],
            limit=1,
        )
    )
    if not sale_tax:
        sale_tax = (
            env_admin["account.tax"]
            .sudo()
            .search(
                [("company_id", "=", company_id), ("type_tax_use", "=", "sale")],
                limit=1,
            )
        )
    purchase_tax = (
        env_admin["account.tax"]
        .sudo()
        .search(
            [
                ("company_id", "=", company_id),
                ("type_tax_use", "=", "purchase"),
                ("amount", "=", 0),
            ],
            limit=1,
        )
    )
    if not purchase_tax:
        purchase_tax = (
            env_admin["account.tax"]
            .sudo()
            .search(
                [("company_id", "=", company_id), ("type_tax_use", "=", "purchase")],
                limit=1,
            )
        )
    vals = {
        "name": "DX QA USER PROVISION PRODUCT",
        "default_code": "DX-QA-USER-PROV",
        "type": "consu",
        "list_price": 100.0,
        "company_id": company_id,
        "invoice_policy": "order",
        "taxes_id": [(6, 0, sale_tax.ids)],
        "supplier_taxes_id": [(6, 0, purchase_tax.ids)],
    }
    if existing:
        existing.product_tmpl_id.write(
            {
                "invoice_policy": "order",
                "taxes_id": [(6, 0, sale_tax.ids)],
                "supplier_taxes_id": [(6, 0, purchase_tax.ids)],
            }
        )
        return existing
    rec = Product.create(vals)
    rec.product_tmpl_id.invoice_policy = "order"
    return rec


def _try(fn):
    try:
        fn()
        return {"ok": True, "error": None, "access_error": False}
    except AccessError as exc:
        return {
            "ok": False,
            "error": "AccessError",
            "access_error": True,
            "msg": str(exc)[:240],
        }
    except (UserError, ValidationError) as exc:
        return {
            "ok": False,
            "error": type(exc).__name__,
            "access_error": False,
            "msg": str(exc)[:240],
        }
    except Exception as exc:
        name = type(exc).__name__
        access = name in {"AccessError", "AccessDenied"}
        return {
            "ok": False,
            "error": name,
            "access_error": access,
            "msg": str(exc)[:240],
        }


def _sales_purchase_flow(env, user):
    companies = [user.company_id.id] + [
        cid for cid in user.company_ids.ids if cid != user.company_id.id
    ]
    envu = env(
        user=user.id,
        context=dict(
            env.context,
            allowed_company_ids=companies,
            tracking_disable=True,
            mail_create_nolog=True,
            mail_notrack=True,
            no_reset_password=True,
        ),
    )
    cr = env.cr
    cr.execute("SAVEPOINT qa_sp_flow_%s" % user.id)
    out = {}
    try:
        partner = _partner(envu, user.company_id.id)
        product = envu["product.product"].browse(_product(env, user.company_id.id).id)
        so = envu["sale.order"].create(
            {
                "partner_id": partner.id,
                "company_id": user.company_id.id,
                "order_line": [
                    (0, 0, {"product_id": product.id, "product_uom_qty": 1})
                ],
            }
        )
        out["quote_create"] = {"ok": True, "id": so.id, "company": so.company_id.id}
        so.write({"client_order_ref": "DX-QA-USER-PROV"})
        out["quote_write"] = {"ok": True}
        out["quote_confirm"] = _try(so.action_confirm)
        po = envu["purchase.order"].create(
            {
                "partner_id": partner.id,
                "company_id": user.company_id.id,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": product.id,
                            "name": product.display_name,
                            "product_qty": 1,
                            "price_unit": 50.0,
                            "tax_ids": [(6, 0, [])],
                        },
                    )
                ],
            }
        )
        out["po_create"] = {"ok": True, "id": po.id, "company": po.company_id.id}
        po.write({"partner_ref": "DX-QA-USER-PROV"})
        out["po_write"] = {"ok": True}
        out["po_confirm"] = _try(po.button_confirm)
    except AccessError as exc:
        out["access_error"] = True
        out["msg"] = str(exc)[:240]
    except Exception as exc:
        out["error"] = type(exc).__name__
        out["msg"] = str(exc)[:240]
        out["access_error"] = type(exc).__name__ in {"AccessError", "AccessDenied"}
    finally:
        cr.execute("ROLLBACK TO SAVEPOINT qa_sp_flow_%s" % user.id)
        env.invalidate_all()
    return out


def _invoice_flow(env, user):
    companies = [user.company_id.id] + [
        cid for cid in user.company_ids.ids if cid != user.company_id.id
    ]
    envu = env(
        user=user.id,
        context=dict(
            env.context,
            allowed_company_ids=companies,
            tracking_disable=True,
            mail_create_nolog=True,
            mail_notrack=True,
        ),
    )
    cr = env.cr
    cr.execute("SAVEPOINT qa_inv_flow_%s" % user.id)
    out = {}
    try:
        partner = _partner(envu, user.company_id.id)
        product = envu["product.product"].browse(_product(env, user.company_id.id).id)
        so = envu["sale.order"].create(
            {
                "partner_id": partner.id,
                "company_id": user.company_id.id,
                "order_line": [
                    (0, 0, {"product_id": product.id, "product_uom_qty": 1})
                ],
            }
        )
        out["quote"] = {"ok": True, "id": so.id}
        out["confirm"] = _try(so.action_confirm)
        so.invalidate_recordset()
        inv_action = None

        def _make_invoice():
            nonlocal inv_action
            inv_action = so._create_invoices()

        out["create_invoice"] = _try(_make_invoice)
        invoices = so.invoice_ids
        if not invoices:

            def _direct():
                return envu["account.move"].create(
                    {
                        "move_type": "out_invoice",
                        "partner_id": partner.id,
                        "company_id": user.company_id.id,
                        "invoice_line_ids": [
                            (
                                0,
                                0,
                                {
                                    "product_id": product.id,
                                    "quantity": 1,
                                    "price_unit": 100.0,
                                    "name": "DX QA USER PROVISION",
                                },
                            )
                        ],
                    }
                )

            created = _try(_direct)
            out["direct_invoice"] = created
            invoices = envu["account.move"].search(
                [("partner_id", "=", partner.id), ("move_type", "=", "out_invoice")],
                limit=5,
            )
        out["draft_invoices"] = invoices.ids
        if invoices:
            inv = invoices[0]
            out["draft_state"] = inv.state
            out["post"] = _try(inv.action_post)
            out["posted_state_before_rollback"] = inv.state
            out["ncf"] = getattr(inv, "justech_do_ncf", False) or False
        else:
            out["post"] = {"ok": False, "error": "NO_INVOICE", "access_error": False}
    except AccessError as exc:
        out["access_error"] = True
        out["msg"] = str(exc)[:240]
    except Exception as exc:
        out["error"] = type(exc).__name__
        out["msg"] = str(exc)[:240]
        out["access_error"] = type(exc).__name__ in {"AccessError", "AccessDenied"}
    finally:
        cr.execute("ROLLBACK TO SAVEPOINT qa_inv_flow_%s" % user.id)
        env.invalidate_all()
    return out


def _negative_invoice(env, user):
    envu = env(user=user.id, su=False)
    envu = envu(
        context=dict(envu.context, allowed_company_ids=list(user.company_ids.ids))
    )
    cr = env.cr
    cr.execute("SAVEPOINT qa_neg_inv")
    try:
        partner = envu["res.partner"].search(
            [("company_id", "in", [False, user.company_id.id])], limit=1
        )
        move_holder = {}

        def _create_and_post():
            move = envu["account.move"].create(
                {
                    "move_type": "out_invoice",
                    "partner_id": partner.id,
                    "company_id": user.company_id.id,
                    "invoice_line_ids": [
                        (
                            0,
                            0,
                            {
                                "name": "DX QA SHOULD FAIL",
                                "quantity": 1,
                                "price_unit": 10,
                            },
                        )
                    ],
                }
            )
            move_holder["id"] = move.id
            move.action_post()

        result = _try(_create_and_post)
        result["created_move_id"] = move_holder.get("id")
    finally:
        cr.execute("ROLLBACK TO SAVEPOINT qa_neg_inv")
    return result


def _negative_settings(env, user):
    envu = env(user=user.id, su=False)
    cr = env.cr
    cr.execute("SAVEPOINT qa_neg_set")
    try:
        result = _try(
            lambda: envu["res.users"].create(
                {
                    "name": "DX QA SHOULD FAIL",
                    "login": "dx.qa.should.fail@invalid.local",
                }
            )
        )
    finally:
        cr.execute("ROLLBACK TO SAVEPOINT qa_neg_set")
    return result


def main():
    env.cr.execute(
        "SELECT count(*) FROM account_move WHERE ref ILIKE %s AND state = 'posted'",
        ("%ALEXANDER_OPENING%",),
    )
    opening_before = env.cr.fetchone()[0]
    rows = {}
    acl_errors = 0
    rpc_errors = 0
    non_invoicing_can_invoice = 0
    non_admin_settings = 0
    for person in PEOPLE:
        user = _user(env, person["upn"])
        if not user:
            rows[person["key"]] = {"LOGIN_QA": "MISSING", "login": person["upn"]}
            acl_errors += 1
            continue
        flags = _flags(user)
        row = {
            "PERSON": person["display_name"],
            "ODOO_USER_ID": user.id,
            "PARTNER_ID": user.partner_id.id,
            "ACTIVE": user.active,
            "DEFAULT_COMPANY": user.company_id.id,
            "ALLOWED_COMPANIES": user.company_ids.ids,
            "ROLE": person["role"],
            **flags,
        }
        if set(user.company_ids.ids) != set(OPERATIONAL_COMPANY_IDS):
            row["COMPANY_MISMATCH"] = True
            acl_errors += 1
        if user.company_id.id != DEFAULT_COMPANY_ID:
            row["DEFAULT_MISMATCH"] = True
        if LIVE_DOCS:
            if person["role"] in {"SALES_PURCHASE", "INVOICING", "ODOO_ADMIN"}:
                row["sales_purchase_qa"] = _sales_purchase_flow(env, user)
                sp = row["sales_purchase_qa"]
                for key in (
                    "quote_create",
                    "quote_write",
                    "quote_confirm",
                    "po_create",
                    "po_write",
                    "po_confirm",
                ):
                    step = sp.get(key) or {}
                    if step.get("access_error"):
                        acl_errors += 1
                    elif (
                        key.endswith("confirm")
                        and not step.get("ok")
                        and step.get("error")
                        not in {
                            "UserError",
                            "ValidationError",
                        }
                    ):
                        # confirm puede fallar por stock/aprobación; no es AccessError
                        if step.get("error") not in {
                            None,
                            "UserError",
                            "ValidationError",
                        }:
                            rpc_errors += 1
            if person["role"] == "INVOICING":
                row["invoice_qa"] = _invoice_flow(env, user)
                post = (row["invoice_qa"] or {}).get("post") or {}
                create_inv = (row["invoice_qa"] or {}).get("create_invoice") or {}
                direct = (row["invoice_qa"] or {}).get("direct_invoice") or {}
                if (
                    post.get("access_error")
                    or create_inv.get("access_error")
                    or direct.get("access_error")
                ):
                    acl_errors += 1
                    row["GEILIN_INVOICE_QA"] = "FAIL_ACCESS"
                elif (
                    create_inv.get("ok")
                    or direct.get("ok")
                    or (row["invoice_qa"] or {}).get("draft_invoices")
                ):
                    row["GEILIN_INVOICE_QA"] = (
                        "PASS" if not post.get("access_error") else "FAIL_ACCESS"
                    )
                    if post.get("ok"):
                        row["GEILIN_INVOICE_QA"] = "PASS_POSTED_ROLLED_BACK"
                    elif post.get("error") in {"UserError", "ValidationError"}:
                        row["GEILIN_INVOICE_QA"] = "PASS_DRAFT_POST_BLOCKED_BUSINESS"
                else:
                    row["GEILIN_INVOICE_QA"] = "FAIL_%s" % (
                        create_inv.get("error") or "UNKNOWN"
                    )
            if person["role"] == "SALES_PURCHASE":
                neg_i = _negative_invoice(env, user)
                neg_s = _negative_settings(env, user)
                row["negative_invoice"] = neg_i
                row["negative_settings"] = neg_s
                if neg_i.get("ok"):
                    non_invoicing_can_invoice += 1
                if flags["ODOO_ADMIN"] or flags["ACCESS_RIGHTS"] or neg_s.get("ok"):
                    non_admin_settings += 1
            if person["role"] == "ODOO_ADMIN":
                row["ALEXANDER_ADMIN_QA"] = (
                    "PASS"
                    if flags["ODOO_ADMIN"]
                    and flags["ACCOUNTING_ADMIN"]
                    and len(user.company_ids) == 6
                    else "FAIL"
                )
        else:
            if person["role"] == "SALES_PURCHASE":
                if (
                    flags["INVOICING"]
                    or flags["ODOO_ADMIN"]
                    or flags["ACCOUNTING_ADMIN"]
                ):
                    non_invoicing_can_invoice += int(bool(flags["INVOICING"]))
                    non_admin_settings += int(
                        bool(flags["ODOO_ADMIN"] or flags["ACCESS_RIGHTS"])
                    )
            if person["role"] == "ODOO_ADMIN":
                row["ALEXANDER_ADMIN_QA"] = "PASS" if flags["ODOO_ADMIN"] else "FAIL"
        # Cross-company: no company 1
        if 1 in user.company_ids.ids:
            row["HAS_TECHNICAL_COMPANY_1"] = True
            acl_errors += 1
        envu = env(user=user.id)
        envu = envu(
            context=dict(envu.context, allowed_company_ids=list(user.company_ids.ids))
        )
        try:
            foreign = envu["account.move"].search_count(
                [("company_id", "not in", list(OPERATIONAL_COMPANY_IDS))]
            )
        except Exception as exc:
            foreign = "ERROR:%s" % type(exc).__name__
        row["FOREIGN_MOVES_VISIBLE"] = foreign
        rows[person["key"]] = row

    env.cr.execute(
        "SELECT count(*) FROM account_move WHERE ref ILIKE %s AND state = 'posted'",
        ("%ALEXANDER_OPENING%",),
    )
    opening_after = env.cr.fetchone()[0]
    report = {
        "users": rows,
        "ACL_ERRORS": acl_errors,
        "RPC_ERRORS": rpc_errors,
        "NON_INVOICING_USERS_CAN_INVOICE": non_invoicing_can_invoice,
        "NON_ADMIN_USERS_CAN_ACCESS_SETTINGS": non_admin_settings,
        "OPENING_POSTED_BEFORE": opening_before,
        "OPENING_POSTED_AFTER": opening_after,
        "OPENING_INTACT": opening_before == opening_after,
        "LIVE_DOCS": LIVE_DOCS,
    }
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, ensure_ascii=False, default=str)
    print(json.dumps(report, indent=2, ensure_ascii=False, default=str))


main()
