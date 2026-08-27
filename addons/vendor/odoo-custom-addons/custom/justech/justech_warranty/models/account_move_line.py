# -*- coding: utf-8 -*-
from odoo import api, fields, models


class AccountMoveLine(models.Model):
    _inherit = ["account.move.line", "justech.warranty.line.mixin"]
    _name = "account.move.line"

    warranty_apply = fields.Boolean(string="Garantía", default=False)
    warranty_months = fields.Integer(string="Meses de garantía", default=0)
    warranty_type_id = fields.Many2one(
        "justech.warranty.type",
        string="Tipo de garantía",
        domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]",
    )
    warranty_unit_ids = fields.One2many(
        "justech.warranty.unit",
        "invoice_line_id",
        string="Unidades de garantía",
        readonly=True,
    )

    def _is_product_line(self):
        self.ensure_one()
        return bool(
            self.product_id
            and self.display_type not in ("line_section", "line_note", "line_subsection")
        )

    def _sync_warranty_from_source(self):
        for line in self:
            if not line._is_product_line():
                line.warranty_apply = False
                line.warranty_months = 0
                line.warranty_type_id = False
                line.warranty_notes = False
                line.warranty_expected_units = 0
                line.warranty_vendor_id = False
                line.warranty_planned_serials = False
                continue
            sale_line = line.sale_line_ids[:1]
            if sale_line:
                line.warranty_apply = sale_line.warranty_apply
                if sale_line.warranty_apply:
                    line.warranty_months = sale_line.warranty_months
                    line.warranty_type_id = sale_line.warranty_type_id
                    line.warranty_notes = sale_line.warranty_notes
                    line.warranty_expected_units = (
                        sale_line.warranty_expected_units
                        or int(line.quantity or 1)
                    )
                    line.warranty_vendor_id = sale_line.warranty_vendor_id
                    line.warranty_planned_serials = sale_line.warranty_planned_serials
                else:
                    line.warranty_months = 0
                    line.warranty_type_id = False
                    line.warranty_notes = False
                    line.warranty_expected_units = 0
                    line.warranty_vendor_id = False
                    line.warranty_planned_serials = False
                continue
            months = line.product_id._get_warranty_months()
            line.warranty_apply = months > 0
            line.warranty_months = months if months > 0 else 0
            if line.warranty_apply and not line.warranty_expected_units:
                line.warranty_expected_units = max(int(line.quantity or 1), 1)

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        lines._sync_warranty_from_source()
        lines.filtered(
            lambda line: line.warranty_apply
            and line._is_product_line()
        )._apply_warranty_product_defaults()
        return lines

    def write(self, vals):
        res = super().write(vals)
        if vals.keys() & {"product_id", "sale_line_ids", "display_type"}:
            self._sync_warranty_from_source()
        if vals.get("warranty_apply") is False:
            self._clear_warranty_details()
        elif vals.get("warranty_apply") is True:
            self.filtered("warranty_apply")._apply_warranty_product_defaults()
        return res
