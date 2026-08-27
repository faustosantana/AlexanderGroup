# -*- coding: utf-8 -*-

from .models.url_utils import align_public_url_with_web_base

WATERMARK_XMLIDS = (
    "justech_approval_flow.report_purchaseorder_document_justech_banner",
    "justech_approval_flow.report_purchasequotation_document_justech_banner",
    "justech_approval_flow.report_saleorder_document_justech_banner",
)


def _migrate_approver_rules(env):
    Rule = env["justech.approval.user.rule"].sudo()
    for company in env["res.company"].search([]):
        for user in company.justech_approval_user_ids:
            if Rule.search([("user_id", "=", user.id)], limit=1):
                continue
            Rule.create(
                {
                    "user_id": user.id,
                    "active": True,
                    "approve_sale": True,
                    "approve_purchase": True,
                    "approve_invoice": True,
                    "allow_self_approval": user.has_group(
                        "justech_approval_flow.group_self_approve"
                    ),
                }
            )


def _ensure_public_url(env):
    """Default public URL to this database's web.base.url. Never hardcode PROD host."""
    icp = env["ir.config_parameter"].sudo()
    web = (icp.get_param("web.base.url") or "").strip()
    public = (icp.get_param("justech.approval.public.base.url") or "").strip()
    aligned = align_public_url_with_web_base(public, web)
    if aligned and aligned.rstrip("/") != public.rstrip("/"):
        icp.set_param("justech.approval.public.base.url", aligned.rstrip("/"))
    elif not public and web:
        icp.set_param("justech.approval.public.base.url", web.rstrip("/"))


def post_init_hook(env):
    """Remove QWeb watermarks added in 19.0.1.0.0 and ensure PO ACL compat."""
    for xid in WATERMARK_XMLIDS:
        view = env.ref(xid, raise_if_not_found=False)
        if view:
            view.unlink()
    env["justech.approval.request"]._ensure_cost_link_purchase_read()
    _enable_flags_all_companies(env)
    _migrate_approver_rules(env)
    _ensure_public_url(env)


def _enable_flags_all_companies(env):
    """If approval is on in any company, enable it in all (no per-company exception)."""
    companies = env["res.company"].sudo().search([])
    if not companies:
        return
    if not any(
        c.justech_approval_sale_enabled
        or c.justech_approval_purchase_enabled
        or c.justech_approval_invoice_enabled
        for c in companies
    ):
        return
    companies.write(
        {
            "justech_approval_purchase_enabled": True,
            "justech_approval_sale_enabled": True,
            "justech_approval_invoice_enabled": True,
        }
    )
