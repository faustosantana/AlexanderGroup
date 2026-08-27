# -*- coding: utf-8 -*-
from odoo import api, SUPERUSER_ID

# Official print actions → historical Justgroup templates (Odoo standard + Studio).
# Identity per company = res.company logo + external_report_layout (bubble).
OFFICIAL_REPORT_BINDINGS = {
    "sale.action_report_saleorder": {
        "report_name": "sale.report_saleorder",
        "report_file": "sale.report_saleorder",
        "paperformat_id": False,
    },
    "account.account_invoices": {
        "report_name": "account.report_invoice_with_payments",
        "report_file": "account.report_invoice_with_payments",
        "paperformat_id": False,
    },
    "account.account_invoices_without_payment": {
        "report_name": "account.report_invoice",
        "report_file": "account.report_invoice",
        "paperformat_id": False,
    },
    "stock.action_report_delivery": {
        "report_name": "stock.report_deliveryslip",
        "report_file": "stock.report_deliveryslip",
        "paperformat_id": False,
        "domain": False,
    },
    "purchase.action_report_purchase_order": {
        "report_name": "purchase.report_purchaseorder",
        "report_file": "purchase.report_purchaseorder",
        "paperformat_id": False,
    },
    "purchase.report_purchase_quotation": {
        "report_name": "purchase.report_purchasequotation",
        "report_file": "purchase.report_purchasequotation",
        "paperformat_id": False,
    },
}

FORBIDDEN_REPORT_PREFIXES = (
    "justech_report_design.",
    "hellenia_reports.",
    "hellenia_",
)


def restore_official_report_bindings(env):
    """Force official actions back to standard Odoo QWeb (fail-closed restore)."""
    # Bypass guard write checks during controlled restore (hook / shell).
    reports = env["ir.actions.report"].sudo().with_context(jt_report_identity_restore=True)
    for xmlid, values in OFFICIAL_REPORT_BINDINGS.items():
        action = env.ref(xmlid, raise_if_not_found=False)
        if not action:
            continue
        action.with_context(jt_report_identity_restore=True).write(dict(values))


def post_init_hook(env):
    restore_official_report_bindings(env)
