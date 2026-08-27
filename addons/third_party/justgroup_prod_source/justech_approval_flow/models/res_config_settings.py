# -*- coding: utf-8 -*-

from odoo import api, fields, models

from .url_utils import normalize_public_base_url


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    justech_approval_purchase_enabled = fields.Boolean(
        related="company_id.justech_approval_purchase_enabled",
        readonly=False,
    )
    justech_approval_sale_enabled = fields.Boolean(
        related="company_id.justech_approval_sale_enabled",
        readonly=False,
    )
    justech_approval_invoice_enabled = fields.Boolean(
        related="company_id.justech_approval_invoice_enabled",
        readonly=False,
    )
    justech_approval_token_days = fields.Integer(
        related="company_id.justech_approval_token_days",
        readonly=False,
    )
    justech_approval_public_base_url = fields.Char(
        string="Approval Public Base URL",
        config_parameter="justech.approval.public.base.url",
        help="URL del entorno que aloja el token. DEV: https://erp.justech.do — PROD: https://justgroup.app",
    )

    @api.constrains("justech_approval_public_base_url")
    def _check_public_base_url(self):
        for rec in self:
            if rec.justech_approval_public_base_url:
                normalize_public_base_url(rec.justech_approval_public_base_url)

    def set_values(self):
        res = super().set_values()
        companies = self.env["res.company"].sudo().search([])
        companies.write(
            {
                "justech_approval_purchase_enabled": self.justech_approval_purchase_enabled,
                "justech_approval_sale_enabled": self.justech_approval_sale_enabled,
                "justech_approval_invoice_enabled": self.justech_approval_invoice_enabled,
                "justech_approval_token_days": self.justech_approval_token_days or 14,
            }
        )
        return res
