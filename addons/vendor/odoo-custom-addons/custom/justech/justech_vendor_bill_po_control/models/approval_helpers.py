# -*- coding: utf-8 -*-
"""Helpers for authorized vendor-bill approvers (shared by move + wizards)."""
from odoo import fields, _


XMLID_APPROVER = "justech_vendor_bill_po_control.group_vendor_bill_approver"
XMLID_FINANCE = "justech_vendor_bill_po_control.group_vendor_bill_approver_finance"
XMLID_MGMT = "justech_vendor_bill_po_control.group_vendor_bill_approver_management"
XMLID_ACTIVITY = "justech_vendor_bill_po_control.mail_activity_vendor_bill_approval"
XMLID_MAIL = "justech_vendor_bill_po_control.mail_template_vendor_bill_approval_request"


def user_is_internal_active(user):
    return bool(
        user
        and user.active
        and not user.share
        and user.has_group("base.group_user")
    )


def user_has_company_access(user, company):
    if not user or not company:
        return False
    if user.has_group("base.group_system"):
        return True
    return company in user.company_ids


def user_is_authorized_approver(user):
    if not user_is_internal_active(user):
        return False
    return (
        user.has_group(XMLID_APPROVER)
        or user.has_group(XMLID_FINANCE)
        or user.has_group(XMLID_MGMT)
        or user.has_group("account.group_account_manager")
        or user.has_group("base.group_system")
    )


def user_meets_approval_level(user, level):
    """Return True if user may act at the required approval level."""
    if not user or not user.exists():
        return False
    # Superuser / Settings always allowed for DEV/admin override paths.
    if user.has_group("base.group_system"):
        return True
    if not user_is_authorized_approver(user):
        return False
    level = level or "finance"
    if level in ("none", "finance"):
        return (
            user.has_group(XMLID_FINANCE)
            or user.has_group(XMLID_MGMT)
            or user.has_group(XMLID_APPROVER)
            or user.has_group("account.group_account_manager")
        )
    if level == "management":
        return user.has_group(XMLID_MGMT)
    if level == "dual":
        return (
            user.has_group(XMLID_FINANCE)
            or user.has_group(XMLID_MGMT)
            or user.has_group(XMLID_APPROVER)
            or user.has_group("account.group_account_manager")
        )
    return False


def authorized_approver_domain(env, company, level="finance"):
    """Domain for Many2one approver selectors."""
    group_xmlids = [XMLID_APPROVER, XMLID_FINANCE, XMLID_MGMT]
    if level == "management":
        group_xmlids = [XMLID_MGMT]
    group_ids = []
    for xmlid in group_xmlids:
        group = env.ref(xmlid, raise_if_not_found=False)
        if group:
            group_ids.append(group.id)
    mgr = env.ref("account.group_account_manager", raise_if_not_found=False)
    if mgr and level != "management":
        group_ids.append(mgr.id)
    domain = [
        ("active", "=", True),
        ("share", "=", False),
        ("all_group_ids", "in", list(set(group_ids)) or [0]),
    ]
    if company:
        domain.append("|")
        domain.append(("company_ids", "in", [company.id]))
        domain.append(("all_group_ids", "in", [env.ref("base.group_system").id]))
    return domain


def default_approver_for_level(company, level):
    level = level or "finance"
    if level == "management":
        return company.vendor_bill_default_mgmt_approver_id
    return company.vendor_bill_default_finance_approver_id or company.vendor_bill_default_mgmt_approver_id


def approval_deadline(company):
    hours = company.vendor_bill_approval_deadline_hours or 24
    return fields.Datetime.add(fields.Datetime.now(), hours=int(hours))
