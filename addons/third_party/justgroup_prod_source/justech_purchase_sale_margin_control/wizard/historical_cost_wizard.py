# -*- coding: utf-8 -*-
"""Inventario histórico / costo manual — solo Costos y Márgenes (no stock/contabilidad)."""
from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools.float_utils import float_compare

from odoo.addons.justech_purchase_sale_margin_control.services.line_allocation_service import (
    LineAllocationService,
)


class PurchaseSaleHistoricalCostWizard(models.TransientModel):
    _name = "purchase.sale.historical.cost.wizard"
    _description = "Inventario histórico / costo manual"

    company_id = fields.Many2one("res.company", required=True)
    transaction_id = fields.Many2one(
        "purchase.sale.margin.transaction", string="Operación", required=True
    )
    manage_wizard_id = fields.Many2one("purchase.sale.manage.purchases.wizard")
    currency_id = fields.Many2one(
        "res.currency", related="company_id.currency_id", readonly=True
    )
    line_ids = fields.One2many(
        "purchase.sale.historical.cost.wizard.line",
        "wizard_id",
        string="Productos",
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        tx_id = res.get("transaction_id") or self.env.context.get("default_transaction_id")
        if not tx_id:
            return res
        tx = self.env["purchase.sale.margin.transaction"].browse(tx_id)
        res.setdefault("company_id", tx.company_id.id)
        res.setdefault("transaction_id", tx.id)
        return res

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._load_pending_lines()
        return records

    def _load_pending_lines(self):
        """Prefer hub pending (sale-first); fall back to service analyze."""
        svc = LineAllocationService(self.env)
        focus_sol = self.env.context.get("default_focus_sale_line_id")
        focus_product = self.env.context.get("default_focus_product_id")
        for wiz in self:
            wiz.line_ids.unlink()
            rows = []
            hub = wiz.manage_wizard_id
            if hub:
                hub._refresh_coverage()
                for hl in hub.line_ids:
                    pending = hl.pending_qty or 0.0
                    if float_compare(pending, 0.0, precision_digits=4) <= 0:
                        continue
                    rows.append(
                        {
                            "sale_line_id": hl.sale_line_id.id,
                            "product_id": hl.product_id.id,
                            "sold_qty": hl.sold_qty,
                            "purchase_qty": hl.purchase_qty,
                            "historical_qty": hl.historical_qty,
                            "pending_qty": pending,
                        }
                    )
            if not rows:
                rows = svc.analyze_transaction_sale_cost_coverage(wiz.transaction_id)
            # Prioritize focused sold line / product (do not exclusive-filter)
            if focus_sol or focus_product:
                rows = sorted(
                    rows,
                    key=lambda r: (
                        0
                        if (
                            (focus_sol and r.get("sale_line_id") == focus_sol)
                            or (focus_product and r.get("product_id") == focus_product)
                        )
                        else 1
                    ),
                )
            cmds = []
            for r in rows:
                pending = r.get("pending_qty") or 0.0
                if float_compare(pending, 0.0, precision_digits=4) <= 0:
                    continue
                cmds.append(
                    (
                        0,
                        0,
                        {
                            "sale_line_id": r["sale_line_id"],
                            "product_id": r.get("product_id"),
                            "sold_qty": r["sold_qty"],
                            "purchase_qty": r.get("purchase_qty", 0.0),
                            "historical_qty": r.get("historical_qty", 0.0),
                            "pending_qty": pending,
                            "qty_to_cover": pending,
                            "unit_cost": 0.0,
                        },
                    )
                )
            if cmds:
                wiz.write({"line_ids": cmds})

    def action_apply(self):
        self.ensure_one()
        Line = self.env["purchase.sale.margin.transaction.line"]
        applied = 0
        for line in self.line_ids:
            if float_compare(line.qty_to_cover, 0.0, precision_digits=4) <= 0:
                continue
            if float_compare(line.qty_to_cover, line.pending_qty, precision_digits=4) > 0:
                raise UserError(
                    _(
                        "No se puede cubrir %(qty)s de %(product)s: solo hay %(pending)s pendiente."
                    )
                    % {
                        "qty": line.qty_to_cover,
                        "product": line.product_id.display_name,
                        "pending": line.pending_qty,
                    }
                )
            if float_compare(line.unit_cost, 0.0, precision_digits=4) < 0:
                raise UserError(_("El costo unitario no puede ser negativo."))
            amount = line.qty_to_cover * (line.unit_cost or 0.0)
            sol = line.sale_line_id
            Line.create(
                {
                    "transaction_id": self.transaction_id.id,
                    "line_type": "cost",
                    "data_origin": "manual",
                    "cost_source": "inventory",
                    "sale_order_id": sol.order_id.id if sol else False,
                    "sale_order_line_id": sol.id if sol else False,
                    "product_id": line.product_id.id,
                    "description": _(
                        "Inventario histórico / costo manual — %s"
                    )
                    % (line.product_id.display_name or ""),
                    "currency_id": self.currency_id.id,
                    "quantity": line.qty_to_cover,
                    "amount_untaxed": amount,
                    "amount_total": amount,
                    "is_manual": True,
                    "notes": _(
                        "Solo Costos y Márgenes. Sin stock, sin asiento, sin recepción."
                    ),
                }
            )
            applied += 1
        if not applied:
            raise UserError(
                _("Indique cantidad y costo unitario en al menos una línea pendiente.")
            )
        # Recompute parent amounts
        if hasattr(self.transaction_id, "_compute_amounts"):
            self.transaction_id.invalidate_recordset()
        if self.manage_wizard_id:
            return self.manage_wizard_id.action_reopen_hub(refresh=True)
        return {
            "type": "ir.actions.act_window",
            "name": _("Gestionar compras y costos"),
            "res_model": "purchase.sale.manage.purchases.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_transaction_id": self.transaction_id.id,
                "default_sale_order_ids": [(6, 0, self.transaction_id.sale_order_ids.ids)],
                "default_customer_invoice_ids": [
                    (6, 0, self.transaction_id.customer_invoice_ids.ids)
                ],
            },
        }


class PurchaseSaleHistoricalCostWizardLine(models.TransientModel):
    _name = "purchase.sale.historical.cost.wizard.line"
    _description = "Línea inventario histórico / costo manual"

    wizard_id = fields.Many2one(
        "purchase.sale.historical.cost.wizard", required=True, ondelete="cascade"
    )
    sale_line_id = fields.Many2one("sale.order.line", string="Línea venta")
    product_id = fields.Many2one("product.product", string="Producto")
    sold_qty = fields.Float(string="Vendido", digits="Product Unit of Measure", readonly=True)
    purchase_qty = fields.Float(string="Relacionado con OC", digits="Product Unit of Measure", readonly=True)
    historical_qty = fields.Float(
        string="Inventario histórico", digits="Product Unit of Measure", readonly=True
    )
    pending_qty = fields.Float(string="Pendiente", digits="Product Unit of Measure", readonly=True)
    qty_to_cover = fields.Float(
        string="Cantidad a cubrir", digits="Product Unit of Measure"
    )
    currency_id = fields.Many2one(related="wizard_id.currency_id")
    unit_cost = fields.Monetary(string="Costo unitario", currency_field="currency_id")
    total_cost = fields.Monetary(
        string="Costo total",
        currency_field="currency_id",
        compute="_compute_total_cost",
    )

    @api.depends("qty_to_cover", "unit_cost")
    def _compute_total_cost(self):
        for line in self:
            line.total_cost = (line.qty_to_cover or 0.0) * (line.unit_cost or 0.0)
