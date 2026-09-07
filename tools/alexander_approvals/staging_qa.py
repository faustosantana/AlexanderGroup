"""Staging approval QA. Rolls back document writes. Does not send mail or consume NCF."""

import json

OPERATIONAL = [
    "luis.aquino@inversionesdoralex.com",
    "janny.montero@inversionesdoralex.com",
    "elianny.sanchez@inversionesdoralex.com",
    "leopordo.jimenez@inversionesdoralex.com",
    "geilin.rosario@inversionesdoralex.com",
]
ALEXANDER = "alexander.pina@inversionesdoralex.com"
SELF_MAP = {
    "LUIS_SELF_APPROVAL": "luis.aquino@inversionesdoralex.com",
    "JANNY_SELF_APPROVAL": "janny.montero@inversionesdoralex.com",
    "ELIANNY_SELF_APPROVAL": "elianny.sanchez@inversionesdoralex.com",
    "LEOPORDO_SELF_APPROVAL": "leopordo.jimenez@inversionesdoralex.com",
    "GEILIN_SELF_APPROVAL": "geilin.rosario@inversionesdoralex.com",
}


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


def _company(token):
    return env["res.company"].sudo().search([("name", "ilike", token)], limit=1)


def _create_so(user_env, company, partner, product, amount=1500):
    return user_env["sale.order"].create(
        {
            "partner_id": partner.id,
            "company_id": company.id,
            "order_line": [
                (
                    0,
                    0,
                    {
                        "product_id": product.id,
                        "product_uom_qty": 1,
                        "price_unit": amount,
                    },
                )
            ],
        }
    )


def _create_po(user_env, company, partner, product, amount=2200):
    vals = {
        "partner_id": partner.id,
        "company_id": company.id,
        "order_line": [
            (
                0,
                0,
                {
                    "product_id": product.id,
                    "product_qty": 1,
                    "price_unit": amount,
                    "name": product.display_name,
                },
            )
        ],
    }
    return user_env["purchase.order"].create(vals)


def _try_confirm(record):
    try:
        result = record.with_context(justech_approval_force_wizard=True).action_confirm()
        if isinstance(result, dict):
            return "WIZARD"
        return "CONFIRMED"
    except Exception as exc:  # noqa: BLE001
        text = str(exc).lower()
        if "aprob" in text:
            return "DENIED"
        return str(exc)[:160]


def _try_approve(request, login):
    try:
        request.with_user(_user(login)).action_approve()
        return "YES"
    except Exception:  # noqa: BLE001
        return "NO"


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
    "NCF_CONSUMED": "NO",
    "EMAIL_SENT": "NO",
    "errors": [],
}

root = env.ref("justech_approval_flow.menu_justech_approval_root")
settings = env.ref("base.menu_administration")
report["APPROVAL_TOP_LEVEL_APP"] = "YES" if (not root.parent_id and root.active) else "NO"
report["APPROVAL_INSIDE_SETTINGS_OPERATIONAL_MENU"] = (
    "YES" if root.parent_id and root.parent_id.id == settings.id else "NO"
)
base_view = env.ref("base.res_config_settings_view_form")
combined = str(base_view.get_combined_arch())
settings_inbox = any(
    needle in combined
    for needle in ("action_justech_approval_pending", "Pendientes", "Histórico")
) and "justech_approval_block" in combined
report["SETTINGS_APPROVAL_CONFIG_SECTION"] = (
    "YES" if "justech_approval_block" in combined else "NO"
)
report["settings_has_operational_inbox"] = (
    "YES" if "action_justech_approval_pending" in combined else "NO"
)

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
for needle in ("Aprobaciones Justech", "Justech Approval", "justech.do", "justgroup.app"):
    if needle.lower() in combined.lower():
        justech_hits.append("settings:" + needle)
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

for key, login in SELF_MAP.items():
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

company = _company("DORALEX") or env.company
rempart = _company("REMPART")
Product = env["product.product"].sudo().search(
    [("sale_ok", "=", True), ("company_id", "in", [False, company.id])], limit=1
)
PoProduct = env["product.product"].sudo().search(
    [("purchase_ok", "=", True), ("company_id", "in", [False, company.id])], limit=1
) or Product
Partner = env["res.partner"].sudo().search([("customer_rank", ">", 0)], limit=1) or env[
    "res.partner"
].sudo().search([], limit=1)
Vendor = env["res.partner"].sudo().search([("supplier_rank", ">", 0)], limit=1) or Partner

qa = {}
cr = env.cr
mail_before = env["mail.mail"].sudo().search_count([])
ncf_before = env["account.move"].sudo().search_count(
    [("move_type", "=", "out_invoice"), ("state", "=", "posted")]
)
cr.execute("SAVEPOINT approval_qa")
try:
    env["ir.mail_server"].sudo().search([]).write({"active": False})

    for login, label in (
        ("luis.aquino@inversionesdoralex.com", "luis"),
        ("janny.montero@inversionesdoralex.com", "janny"),
        ("elianny.sanchez@inversionesdoralex.com", "elianny"),
        ("leopordo.jimenez@inversionesdoralex.com", "leopordo"),
    ):
        user_env = _as_env(login)
        if not user_env or not Product or not Partner:
            qa[label + "_so_create"] = "SKIP"
            qa[label + "_po_create"] = "SKIP"
            continue
        so = _create_so(user_env, company, Partner, Product)
        qa[label + "_so_create"] = "PASS"
        qa[label + "_so_gate"] = _try_confirm(so)
        if hasattr(so, "action_justech_request_approval") and so.justech_approval_state != "pending":
            try:
                so.action_justech_request_approval()
            except Exception as exc:  # noqa: BLE001
                qa[label + "_so_request"] = str(exc)[:160]
        pending = Request.search(
            [("document_model", "=", "sale.order"), ("res_id", "=", so.id)], limit=1
        )
        if pending:
            qa[label + "_self_approve"] = _try_approve(pending, login)
            try:
                so.with_user(_user(login)).write({"justech_approval_state": "approved"})
                qa[label + "_direct_write"] = "YES"
            except Exception:
                qa[label + "_direct_write"] = "NO"

        if PoProduct and Vendor:
            po = _create_po(user_env, company, Vendor, PoProduct)
            qa[label + "_po_create"] = "PASS"
            qa[label + "_po_gate"] = _try_confirm(po)
            if hasattr(po, "action_justech_request_approval") and po.justech_approval_state != "pending":
                try:
                    po.action_justech_request_approval()
                except Exception as exc:  # noqa: BLE001
                    qa[label + "_po_request"] = str(exc)[:160]
            pending_po = Request.search(
                [("document_model", "=", "purchase.order"), ("res_id", "=", po.id)],
                limit=1,
            )
            if pending_po:
                qa[label + "_po_self_approve"] = _try_approve(pending_po, login)
                if label == "luis" and alex:
                    try:
                        pending_po.with_user(alex).action_reject(note="QA reject rollback")
                        qa["alexander_reject"] = (
                            "PASS" if pending_po.state == "rejected" else pending_po.state
                        )
                    except Exception as exc:  # noqa: BLE001
                        qa["alexander_reject"] = str(exc)[:160]

    manager = env.ref("justech_approval_flow.group_manager", raise_if_not_found=False)
    for login, label in (
        ("janny.montero@inversionesdoralex.com", "janny"),
        ("elianny.sanchez@inversionesdoralex.com", "elianny"),
    ):
        user = _user(login)
        qa[label + "_approval_admin"] = "YES" if _has(user, "justech_approval_flow.group_manager") else "NO"
        if manager:
            try:
                user_env = _as_env(login)
                manager.with_user(user).write({"comment": "qa-denied"})
                qa[label + "_change_rules"] = "YES"
            except Exception:
                qa[label + "_change_rules"] = "NO"
            try:
                Rule = user_env["justech.approval.user.rule"] if user_env else None
                if Rule is not None:
                    Rule.search([], limit=1).write({"approve_sale": False})
                    qa[label + "_write_rule"] = "YES"
            except Exception:
                qa[label + "_write_rule"] = "NO"

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
                first = inv.action_justech_request_approval()
                second = inv.action_justech_request_approval()
                qa["geilin_request"] = "PASS"
                qa["duplicate_create"] = (
                    0
                    if getattr(first, "id", None) == getattr(second, "id", None)
                    else 2
                )
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
            act_type = env.ref(
                "justech_approval_flow.mail_activity_approval",
                raise_if_not_found=False,
            )
            acts = env["mail.activity"].sudo().search(
                [
                    ("res_model", "=", "account.move"),
                    ("res_id", "=", inv.id),
                    ("activity_type_id", "=", act_type.id if act_type else 0),
                ]
            )
            qa["activity_for_approver"] = "YES" if acts else "NO"
            qa["geilin_self_approve"] = _try_approve(pending, "geilin.rosario@inversionesdoralex.com")
            if alex:
                try:
                    pending.with_user(alex).action_approve()
                    qa["alexander_approve"] = (
                        "PASS" if pending.state == "approved" else pending.state
                    )
                    qa["decided_by"] = pending.decided_by_id.login if pending.decided_by_id else ""
                except Exception as exc:  # noqa: BLE001
                    qa["alexander_approve"] = str(exc)[:160]
            gate_open = (
                inv.justech_approval_state == "approved"
                and not (
                    inv._justech_invoice_requires_approval()
                    and inv.justech_approval_state != "approved"
                )
            )
            qa["geilin_post_after"] = "PASS" if gate_open else "DENIED"
            qa["geilin_posted_after"] = inv.state

    if rempart and alex:
        rempart_env = env(
            user=alex.id,
            context=dict(env.context, allowed_company_ids=[rempart.id]),
        )
        product_r = env["product.product"].sudo().search(
            [("sale_ok", "=", True), ("company_id", "in", [False, rempart.id])],
            limit=1,
        ) or Product
        if product_r and Partner:
            so_r = rempart_env["sale.order"].create(
                {
                    "partner_id": Partner.id,
                    "company_id": rempart.id,
                    "order_line": [
                        (
                            0,
                            0,
                            {
                                "product_id": product_r.id,
                                "product_uom_qty": 1,
                                "price_unit": 900,
                            },
                        )
                    ],
                }
            )
            if hasattr(so_r, "action_justech_request_approval"):
                try:
                    so_r.action_justech_request_approval()
                except Exception as exc:  # noqa: BLE001
                    qa["rempart_request"] = str(exc)[:160]
            pending_r = Request.search(
                [("document_model", "=", "sale.order"), ("res_id", "=", so_r.id)],
                limit=1,
            )
            luis = _user("luis.aquino@inversionesdoralex.com")
            if pending_r and luis:
                kept = luis.company_ids.filtered(lambda c: c.id != rempart.id)
                if kept:
                    luis.write({"company_ids": [(6, 0, kept.ids)]})
                    isolated = env(
                        user=luis.id,
                        context=dict(env.context, allowed_company_ids=kept.ids),
                    )
                    seen = isolated["justech.approval.request"].search_count(
                        [("id", "=", pending_r.id)]
                    )
                    qa["rempart_visible_without_company"] = "YES" if seen else "NO"
                    report["MULTICOMPANY_APPROVAL_ISOLATION"] = (
                        "YES" if seen == 0 else "NO"
                    )

    report["GEILIN_INVOICE_APPROVAL_FLOW"] = qa
    report["document_qa"] = qa
finally:
    cr.execute("ROLLBACK TO SAVEPOINT approval_qa")

ncf_after = env["account.move"].sudo().search_count(
    [("move_type", "=", "out_invoice"), ("state", "=", "posted")]
)
mail_after = env["mail.mail"].sudo().search_count([])
report["NCF_CONSUMED"] = "YES" if ncf_after > ncf_before else "NO"
report["EMAIL_SENT"] = "YES" if mail_after > mail_before else "NO"
report["posted_invoices"] = ncf_after

if qa.get("duplicate_create"):
    report["DUPLICATE_APPROVAL_REQUESTS"] = max(
        report["DUPLICATE_APPROVAL_REQUESTS"], qa["duplicate_create"]
    )

critical = []
if report["APPROVAL_TOP_LEVEL_APP"] != "YES":
    critical.append("app not top-level")
if report["APPROVAL_INSIDE_SETTINGS_OPERATIONAL_MENU"] != "NO":
    critical.append("inbox still in settings")
if report["TOP_LEVEL_APPROVAL_MENU_COUNT"] != 1:
    critical.append("duplicate top-level approval apps")
if report["ALEXANDER_APPROVAL_ADMIN"] != "YES":
    critical.append("alexander not admin")
if any(report[k] == "YES" for k in SELF_MAP):
    critical.append("operational self-approval group")
if report["DUPLICATE_APPROVAL_REQUESTS"]:
    critical.append("duplicate pending requests")
if report["NCF_CONSUMED"] == "YES":
    critical.append("ncf consumed")
if qa.get("geilin_post_before") == "POSTED":
    critical.append("geilin posted before approval")
if qa.get("geilin_self_approve") == "YES":
    critical.append("geilin self-approved")
if qa.get("luis_self_approve") == "YES" or qa.get("luis_po_self_approve") == "YES":
    critical.append("luis self-approved")
if qa.get("rempart_visible_without_company") == "YES":
    critical.append("rempart leaked")
if report["VISIBLE_JUSTECH_BRANDING"] == "YES":
    critical.append("visible justech branding")
report["CRITICAL_ERRORS"] = len(critical)
report["critical_list"] = critical
report["STAGING_APPROVAL_QA"] = "PASS" if not critical else "FAIL"
print(json.dumps(report, indent=2, default=str))
