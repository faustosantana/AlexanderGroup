# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    vendor_bill_po_policy = fields.Selection(
        related="company_id.vendor_bill_po_policy",
        readonly=False,
        string="Exigir Orden de Compra en facturas de proveedor",
    )
    vendor_bill_strict_approval = fields.Boolean(
        related="company_id.vendor_bill_strict_approval",
        readonly=False,
        string="Control estricto de aprobación",
    )
    vendor_bill_require_classification = fields.Boolean(
        related="company_id.vendor_bill_require_classification",
        readonly=False,
    )
    vendor_bill_block_payment = fields.Boolean(
        related="company_id.vendor_bill_block_payment",
        readonly=False,
    )
    vendor_bill_block_treasury = fields.Boolean(
        related="company_id.vendor_bill_block_treasury",
        readonly=False,
    )
    vendor_bill_block_withholding = fields.Boolean(
        related="company_id.vendor_bill_block_withholding",
        readonly=False,
    )
    vendor_bill_amount_finance_limit = fields.Monetary(
        related="company_id.vendor_bill_amount_finance_limit",
        readonly=False,
        currency_field="company_currency_id",
    )
    vendor_bill_amount_management_limit = fields.Monetary(
        related="company_id.vendor_bill_amount_management_limit",
        readonly=False,
        currency_field="company_currency_id",
    )
    vendor_bill_default_finance_approver_id = fields.Many2one(
        related="company_id.vendor_bill_default_finance_approver_id",
        readonly=False,
    )
    vendor_bill_default_mgmt_approver_id = fields.Many2one(
        related="company_id.vendor_bill_default_mgmt_approver_id",
        readonly=False,
    )
    vendor_bill_default_substitute_id = fields.Many2one(
        related="company_id.vendor_bill_default_substitute_id",
        readonly=False,
    )
    vendor_bill_approval_deadline_hours = fields.Integer(
        related="company_id.vendor_bill_approval_deadline_hours",
        readonly=False,
    )
    vendor_bill_notify_internal = fields.Boolean(
        related="company_id.vendor_bill_notify_internal",
        readonly=False,
    )
    vendor_bill_notify_email = fields.Boolean(
        related="company_id.vendor_bill_notify_email",
        readonly=False,
    )
    vendor_bill_allow_reassign = fields.Boolean(
        related="company_id.vendor_bill_allow_reassign",
        readonly=False,
    )
    vendor_bill_allow_admin_override = fields.Boolean(
        related="company_id.vendor_bill_allow_admin_override",
        readonly=False,
    )
    vendor_bill_require_sod = fields.Boolean(
        related="company_id.vendor_bill_require_sod",
        readonly=False,
    )
    vendor_bill_no_po_auto_classification = fields.Selection(
        related="company_id.vendor_bill_no_po_auto_classification",
        readonly=False,
    )
    vendor_bill_approval_effective_from = fields.Datetime(
        related="company_id.vendor_bill_approval_effective_from",
        readonly=False,
    )
    vendor_bill_allow_self_approval = fields.Boolean(
        related="company_id.vendor_bill_allow_self_approval",
        readonly=False,
    )
