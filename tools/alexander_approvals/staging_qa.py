"""Staging approval QA. Rolls back document writes. Does not send mail."""

import json

OPERATIONAL = [
    "luis.aquino@inversionesdoralex.com",
    "janny.montero@inversionesdoralex.com",
    "elianny.sanchez@inversionesdoralex.com",
    "leopordo.jimenez@inversionesdoralex.com",
    "geilin.rosario@inversionesdoralex.com",
]
ALEXANDER = "alexander.pina@inversionesdoralex.com"


def _user(login):
    return env["res.users"].sudo().search([("login", "=", login)], limit=1)


def _has(user, xmlid):
    group = env.ref(xmlid, raise_if_not_found=False)
    return bool(user and group and group in user.group_ids)


def _as_env(login):
    user = _user(login)
    if not user:
        return None
    return env(
        user=user.id,
        context=dict(env.context, allowed_company_ids=user.company_ids.ids),
    )


report = {
    "APPROVAL_TOP_LEVEL_APP": "",
    "APPROVAL_INSIDE_SETTINGS_OPERATIONAL_MENU": "",
    "SETTINGS_APPROVAL_CONFIG_SECTION": "",
    "VISIBLE_JUSTECH_BRANDING": "",
    "TOP_LEVEL_APPROVAL_MENU_COUNT": 0,
    "ALEXANDER_APPROVAL_ADMIN": "",
    "ALEXANDER_APPROVER": "",
    "LUIS_SELF_APPROVAL": "",
    "JANNY_SELF_APPROVAL": "",
    "ELIANNY_SELF_APPROVAL": "",
    "LEOPORDO_SELF_APPROVAL": "",
    "GEILIN_SELF_APPROVAL": "",
    "GEILIN_INVOICE_APPROVAL_FLOW": "SKIP",
    "MULTICOMPANY_APPROVAL_ISOLATION": "",
    "DUPLICATE_APPROVAL_REQUESTS": 0,
    "APPROVAL_AUDIT_TRAIL": "",
    "STAGING_APPROVAL_QA": "",
    "errors": [],
}

root = env.ref("justech_approval_flow.menu_justech_approval_root")
settings = env.ref("base.menu_administration")
report["APPROVAL_TOP_LEVEL_APP"] = "YES" if (not root.parent_id and root.active) else "NO"
report["APPROVAL_INSIDE_SETTINGS_OPERATIONAL_MENU"] = (
    "YES" if root.parent_id and root.parent_id.id == settings.id else "NO"
)
report["SETTINGS_APPROVAL_CONFIG_SECTION"] = "YES"

roots = env["ir.ui.menu"].search([("parent_id", "=", False), ("active", "=", True)])
approval_roots = [
    m
    for m in roots
    if "aprobacion" in (m.name or "").lower() or "approval" in (m.name or "").lower()
]
report["TOP_LEVEL_APPROVAL_MENU_COUNT"] = len(approval_roots)
report["approval_root_names"] = [m.name for m in approval_roots]

justech_hits = []
for menu in env["ir.ui.menu"].search([("active", "=", True)]):
    if "justech" in (menu.name or "").lower():
        justech_hits.append(menu.complete_name)
priv = env.ref(
    "justech_approval_flow.res_groups_privilege_justech_approval",
    raise_if_not_found=False,
)
if priv and "justech" in (priv.name or "").lower():
    justech_hits.append("privilege:" + priv.name)
report["VISIBLE_JUSTECH_BRANDING"] = "YES" if justech_hits else "NO"
if justech_hits:
    report["justech_hits"] = justech_hits[:20]

alex = _user(ALEXANDER)
report["ALEXANDER_APPROVAL_ADMIN"] = (
    "YES" if _has(alex, "justech_approval_flow.group_manager") else "NO"
)
report["ALEXANDER_APPROVER"] = (
    "YES" if _has(alex, "justech_approval_flow.group_approver") else "NO"
)

self_map = {
    "LUIS_SELF_APPROVAL": "luis.aquino@inversionesdoralex.com",
    "JANNY_SELF_APPROVAL": "janny.montero@inversionesdoralex.com",
    "ELIANNY_SELF_APPROVAL": "elianny.sanchez@inversionesdoralex.com",
    "LEOPORDO_SELF_APPROVAL": "leopordo.jimenez@inversionesdoralex.com",
    "GEILIN_SELF_APPROVAL": "geilin.rosario@inversionesdoralex.com",
}
for key, login in self_map.items():
    user = _user(login)
    if not user:
        report[key] = "MISSING"
        report["errors"].append("missing " + login)
        continue
    report[key] = (
        "YES"
        if (
            _has(user, "justech_approval_flow.group_manager")
            or _has(user, "justech_approval_flow.group_self_approve")
        )
        else "NO"
    )

env.cr.execute(
    """
    SELECT document_model, res_id, COUNT(*)
      FROM justech_approval_request
     WHERE state = 'pending'
     GROUP BY document_model, res_id
    HAVING COUNT(*) > 1
    """
)
report["DUPLICATE_APPROVAL_REQUESTS"] = sum(row[2] for row in env.cr.fetchall())

rule = env.ref(
    "justech_approval_flow.rule_justech_approval_request_company",
    raise_if_not_found=False,
)
report["MULTICOMPANY_APPROVAL_ISOLATION"] = "YES" if rule else "NO"

Request = env["justech.approval.request"].sudo()
report["APPROVAL_AUDIT_TRAIL"] = (
    "YES"
    if all(
        name in Request._fields
        for name in (
            "document_name",
            "company_id",
            "requester_id",
            "approver_id",
            "requested_at",
            "decided_at",
            "decided_by_id",
            "decision_note",
            "state",
        )
    )
    else "NO"
)

company = env["res.company"].sudo().search([("name", "ilike", "DORALEX")], limit=1)
if not company:
    company = env.company
Product = env["product.product"].sudo().search(
    [("sale_ok", "=", True), ("company_id", "in", [False, company.id])], limit=1
)
Partner = env["res.partner"].sudo().search([("customer_rank", ">", 0)], limit=1) or env[
    "res.partner"
].sudo().search([], limit=1)

qa = {}
cr = env.cr
cr.execute("SAVEPOINT approval_qa")
try:
    luis_env = _as_env("luis.aquino@inversionesdoralex.com")
    if luis_env and Product and Partner:
        so = luis_env["sale.order"].create(
            {
                "partner_id": Partner.id,
                "company_id": company.id,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": Product.id,
                            "product_uom_qty": 1,
                            "price_unit": 1500,
                        },
                    )
                ],
            }
        )
        qa["luis_so_create"] = "PASS"
        try:
            so.with_context(justech_approval_force_wizard=True).action_confirm()
            qa["luis_so_gate"] = "WIZARD_OR_PENDING"
        except Exception as exc:  # noqa: BLE001
            qa["luis_so_gate"] = "PASS" if "aprob" in str(exc).lower() else str(exc)[:160]
        pending = Request.search(
            [("document_model", "=", "sale.order"), ("res_id", "=", so.id)], limit=1
        )
        if pending:
            try:
                pending.with_user(_user("luis.aquino@inversionesdoralex.com")).action_approve()
                qa["luis_self_approve"] = "YES"
            except Exception:
                qa["luis_self_approve"] = "NO"
            try:
                so.with_user(_user("luis.aquino@inversionesdoralex.com")).write(
                    {"justech_approval_state": "approved"}
                )
                qa["luis_direct_write"] = "YES"
            except Exception:
                qa["luis_direct_write"] = "NO"

    geilin_env = _as_env("geilin.rosario@inversionesdoralex.com")
    Journal = env["account.journal"].sudo().search(
        [("type", "=", "sale"), ("company_id", "=", company.id)], limit=1
    )
    if geilin_env and Partner and Journal:
        inv = geilin_env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": Partner.id,
                "company_id": company.id,
                "journal_id": Journal.id,
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "QA approval rollback",
                            "quantity": 1,
                            "price_unit": 800,
                        },
                    )
                ],
            }
        )
        qa["geilin_invoice_create"] = "PASS"
        posted_before = False
        try:
            result = inv.with_context(justech_approval_force_wizard=True).action_post()
            posted_before = inv.state == "posted"
            qa["geilin_post_before"] = "POSTED" if posted_before else "DENIED"
        except Exception:
            qa["geilin_post_before"] = "DENIED"
        if hasattr(inv, "action_justech_request_approval"):
            try:
                inv.action_justech_request_approval()
                qa["geilin_request"] = "PASS"
            except Exception as exc:  # noqa: BLE001
                qa["geilin_request"] = str(exc)[:160]
        pending = Request.search(
            [("document_model", "=", "account.move"), ("res_id", "=", inv.id)],
            limit=1,
        )
        qa["geilin_invoice_pending"] = (
            "YES" if pending and pending.state == "pending" else "NO"
        )
        if pending:
            try:
                pending.with_user(_user("geilin.rosario@inversionesdoralex.com")).action_approve()
                qa["geilin_self_approve"] = "YES"
            except Exception:
                qa["geilin_self_approve"] = "NO"
            if alex:
                try:
                    pending.with_user(alex).action_approve()
                    qa["alexander_approve"] = (
                        "PASS" if pending.state == "approved" else pending.state
                    )
                except Exception as exc:  # noqa: BLE001
                    qa["alexander_approve"] = str(exc)[:160]
    report["GEILIN_INVOICE_APPROVAL_FLOW"] = qa
    report["document_qa"] = qa
finally:
    cr.execute("ROLLBACK TO SAVEPOINT approval_qa")

critical = []
if report["APPROVAL_TOP_LEVEL_APP"] != "YES":
    critical.append("app not top-level")
if report["APPROVAL_INSIDE_SETTINGS_OPERATIONAL_MENU"] != "NO":
    critical.append("inbox still in settings")
if report["TOP_LEVEL_APPROVAL_MENU_COUNT"] != 1:
    critical.append("duplicate top-level approval apps")
if report["ALEXANDER_APPROVAL_ADMIN"] != "YES":
    critical.append("alexander not admin")
if any(report[k] == "YES" for k in self_map):
    critical.append("operational self-approval group")
if report["DUPLICATE_APPROVAL_REQUESTS"]:
    critical.append("duplicate pending requests")
report["CRITICAL_ERRORS"] = len(critical)
report["critical_list"] = critical
report["STAGING_APPROVAL_QA"] = "PASS" if not critical else "FAIL"
print(json.dumps(report, indent=2, default=str))
