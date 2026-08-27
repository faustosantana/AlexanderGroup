# -*- coding: utf-8 -*-

from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    justech_approval_purchase_enabled = fields.Boolean(
        string="Aprobar órdenes de compra",
        default=False,
        help="Reutiliza el estado nativo 'to approve' y envía email/actividad.",
    )
    justech_approval_sale_enabled = fields.Boolean(
        string="Aprobar cotizaciones",
        default=False,
    )
    justech_approval_invoice_enabled = fields.Boolean(
        string="Aprobar facturas de cliente",
        default=False,
        help="No aplica a facturas de proveedor (Vendor Bill Control).",
    )
    justech_approval_user_ids = fields.Many2many(
        "res.users",
        "justech_approval_company_user_rel",
        "company_id",
        "user_id",
        string="Aprobadores",
        domain="[('share', '=', False)]",
        help="Si está vacío, se notifica a todos los usuarios del grupo Aprobador.",
    )
    justech_approval_token_days = fields.Integer(
        string="Validez del token (días)",
        default=14,
    )
