# -*- coding: utf-8 -*-
from odoo import api, fields, models


class SaleOrderLine(models.Model):
    _inherit = ["sale.order.line", "justech.warranty.line.mixin"]
    _name = "sale.order.line"

    warranty_apply = fields.Boolean(
        string="Garantía",
        default=False,
        help="Indica si esta línea llevará garantía.",
    )
    warranty_months = fields.Integer(string="Meses de garantía", default=0)
    warranty_type_id = fields.Many2one(
        "justech.warranty.type",
        string="Tipo de garantía",
        domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]",
    )
    warranty_unit_ids = fields.One2many(
        "justech.warranty.unit",
        "sale_line_id",
        string="Unidades de garantía",
        readonly=True,
    )

    @api.model
    def _warranty_values_from_product(self, product):
        months = product._get_warranty_months()
        return {
            "warranty_apply": months > 0,
            "warranty_months": months if months > 0 else 0,
        }

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if (
                vals.get("product_id")
                and vals.get("display_type") not in ("line_section", "line_note", "line_subsection")
                and "warranty_apply" not in vals
            ):
                product = self.env["product.product"].browse(vals["product_id"])
                vals.update(self._warranty_values_from_product(product))
            if (
                vals.get("product_id")
                and vals.get("warranty_apply")
                and not vals.get("warranty_expected_units")
            ):
                qty = int(vals.get("product_uom_qty") or 1)
                vals["warranty_expected_units"] = max(qty, 1)
        lines = super().create(vals_list)
        lines.filtered(
            lambda line: line.warranty_apply
            and line.product_id
            and line.display_type not in ("line_section", "line_note", "line_subsection")
        )._apply_warranty_product_defaults()
        return lines

    @api.onchange("product_id")
    def _onchange_product_warranty_defaults(self):
        if self.display_type or not self.product_id:
            self.warranty_apply = False
            self.warranty_months = 0
            self.warranty_type_id = False
            self.warranty_expected_units = 0
            self.warranty_planned_serials = False
            return
        values = self._warranty_values_from_product(self.product_id)
        self.warranty_apply = values["warranty_apply"]
        self.warranty_months = values["warranty_months"]
        if self.warranty_apply:
            self._apply_warranty_product_defaults_onchange()

    @api.onchange("product_uom_qty")
    def _onchange_product_uom_qty_warranty(self):
        if not self.warranty_apply:
            return
        qty = int(self.product_uom_qty or 0)
        if qty > 0 and (
            not self.warranty_expected_units
            or self.warranty_expected_units < qty
        ):
            self.warranty_expected_units = qty

    def write(self, vals):
        res = super().write(vals)
        if vals.get("warranty_apply") is False:
            self._clear_warranty_details()
        elif vals.get("warranty_apply") is True:
            self.filtered("warranty_apply")._apply_warranty_product_defaults()
        return res

    def _prepare_invoice_line(self, **optional_values):
        res = super()._prepare_invoice_line(**optional_values)
        if res.get("display_type") in ("line_section", "line_note", "line_subsection"):
            return res
        res.update(
            {
                "warranty_apply": self.warranty_apply,
                "warranty_months": self.warranty_months if self.warranty_apply else 0,
                "warranty_type_id": self.warranty_type_id.id if self.warranty_type_id else False,
                "warranty_notes": self.warranty_notes if self.warranty_apply else False,
                "warranty_expected_units": (
                    self.warranty_expected_units if self.warranty_apply else 0
                ),
                "warranty_vendor_id": (
                    self.warranty_vendor_id.id if self.warranty_apply and self.warranty_vendor_id else False
                ),
                "warranty_planned_serials": (
                    self.warranty_planned_serials if self.warranty_apply else False
                ),
            }
        )
        return res
