# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools.float_utils import float_compare


class JustechBuyPendingWizard(models.TransientModel):
    _name = "justech.buy.pending.wizard"
    _description = "Generar orden de compra desde venta"

    sale_order_id = fields.Many2one(
        "sale.order",
        string="Orden de venta",
        required=True,
        readonly=True,
    )
    company_id = fields.Many2one(
        related="sale_order_id.company_id",
        store=True,
        readonly=True,
    )
    partner_id = fields.Many2one(
        "res.partner",
        string="Proveedor",
        required=True,
        domain="[('supplier_rank', '>', 0)]",
        check_company=True,
    )
    date_order = fields.Datetime(
        string="Fecha de OC",
        required=True,
        default=fields.Datetime.now,
    )
    line_ids = fields.One2many(
        "justech.buy.pending.wizard.line",
        "wizard_id",
        string="Líneas",
    )
    warning_html = fields.Html(
        string="Avisos",
        compute="_compute_warning_html",
        sanitize=True,
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        so = self.env["sale.order"].browse(
            self.env.context.get("default_sale_order_id")
            or self.env.context.get("active_id")
        )
        if not so:
            return res
        res["sale_order_id"] = so.id
        lines = []
        for sol in so.order_line.filtered(lambda l: not l.display_type and l.product_id):
            sol._compute_justech_purchase_coverage()
            pending = sol.justech_qty_pending_purchase
            if float_compare(pending, 0.0, precision_digits=4) <= 0:
                continue
            lines.append(
                (
                    0,
                    0,
                    {
                        "sale_line_id": sol.id,
                        "product_id": sol.product_id.id,
                        "description": sol.name,
                        "qty_sold": sol.justech_qty_sold,
                        "qty_stock_covered": sol.justech_qty_stock_covered,
                        "qty_purchased": sol.justech_qty_purchased,
                        "qty_pending": pending,
                        "qty_to_buy": 0.0,
                        "selected": False,
                        "snapshot_pending": pending,
                    },
                )
            )
        res["line_ids"] = lines
        return res

    @api.depends(
        "line_ids.qty_stock_covered",
        "line_ids.qty_sold",
        "line_ids.selected",
        "sale_order_id",
    )
    def _compute_warning_html(self):
        for wiz in self:
            notes = []
            if wiz.sale_order_id and not wiz.line_ids:
                notes.append(
                    _(
                        "No existen cantidades pendientes de compra. "
                        "Esta venta ya está completamente cubierta por inventario "
                        "y/o compras relacionadas."
                    )
                )
            for line in wiz.line_ids:
                if float_compare(line.qty_sold, 0.0, precision_digits=4) <= 0:
                    continue
                if float_compare(
                    line.qty_stock_covered, line.qty_sold, precision_digits=4
                ) >= 0:
                    notes.append(
                        _(
                            "Esta venta puede cubrirse completamente con inventario "
                            "disponible. No es necesario generar una compra."
                        )
                    )
                    break
            wiz.warning_html = (
                "<div class='alert alert-warning mb-0'>%s</div>" % "<br/>".join(notes)
                if notes
                else False
            )

    def _justech_rebind_omitted_sale_lines(self):
        """OWL omits readonly x2m fields on save; restore identity by line order.

        Production CJO-0000694: selected=True and qty_to_buy=2 were stored, but
        sale_line_id/product_id were NULL, so generate filtered nothing.
        """
        for wiz in self:
            so = wiz.sale_order_id
            if not so:
                continue
            pending_sols = []
            for sol in so.order_line.filtered(
                lambda l: not l.display_type and l.product_id
            ):
                sol._compute_justech_purchase_coverage()
                if float_compare(sol.justech_qty_pending_purchase, 0.0, precision_digits=4) > 0:
                    pending_sols.append(sol)
            lines = wiz.line_ids.sorted("id")
            if not lines or all(line.sale_line_id for line in lines):
                continue
            # OWL keeps every displayed row (including unselected). Zip by that
            # order only when counts match — never guess a subset of rows.
            if len(lines) != len(pending_sols):
                continue
            for line, sol in zip(lines, pending_sols):
                vals = {}
                if not line.sale_line_id:
                    vals["sale_line_id"] = sol.id
                if not line.product_id:
                    vals["product_id"] = sol.product_id.id
                if not line.description:
                    vals["description"] = sol.name
                if float_compare(line.qty_sold or 0.0, 0.0, precision_digits=4) <= 0:
                    vals["qty_sold"] = sol.justech_qty_sold
                if float_compare(line.qty_stock_covered or 0.0, 0.0, precision_digits=4) <= 0:
                    vals["qty_stock_covered"] = sol.justech_qty_stock_covered
                if float_compare(line.qty_purchased or 0.0, 0.0, precision_digits=4) <= 0:
                    vals["qty_purchased"] = sol.justech_qty_purchased
                if float_compare(line.qty_pending or 0.0, 0.0, precision_digits=4) <= 0:
                    vals["qty_pending"] = sol.justech_qty_pending_purchase
                if float_compare(line.snapshot_pending or 0.0, 0.0, precision_digits=4) <= 0:
                    vals["snapshot_pending"] = sol.justech_qty_pending_purchase
                if vals:
                    line.write(vals)

    def action_create_purchase_order(self):
        self.ensure_one()
        if not self.partner_id:
            raise UserError(_("Seleccione un proveedor."))
        if self.partner_id.company_id and self.partner_id.company_id != self.company_id:
            raise UserError(_("El proveedor no pertenece a la misma compañía."))

        self._justech_rebind_omitted_sale_lines()
        selected = self.line_ids.filtered(lambda l: l.selected and l.sale_line_id)
        if not selected:
            so_lines = self.sale_order_id.order_line.filtered(
                lambda l: not l.display_type and l.product_id
            )
            so_lines._compute_justech_purchase_coverage()
            if so_lines and all(
                float_compare(l.justech_qty_pending_purchase, 0.0, precision_digits=4) <= 0
                for l in so_lines
            ):
                raise UserError(
                    _(
                        "Esta línea ya está completamente cubierta por inventario "
                        "y/o compras relacionadas."
                    )
                )
            raise UserError(_("Seleccione al menos una línea con cantidad a comprar."))

        sale_lines = selected.mapped("sale_line_id")
        sale_lines._justech_lock_for_purchase()
        fresh = sale_lines.justech_get_pending_snapshot()

        for wline in selected:
            sol = wline.sale_line_id
            current_pending = fresh.get(sol.id, 0.0)
            if float_compare(
                wline.snapshot_pending, current_pending, precision_digits=4
            ) != 0:
                raise UserError(
                    _(
                        "Las cantidades pendientes cambiaron desde que abrió esta ventana. "
                        "Actualice y revise nuevamente."
                    )
                )
            if float_compare(wline.qty_to_buy, 0.0, precision_digits=4) <= 0:
                raise UserError(_("La cantidad a comprar debe ser positiva."))
            if float_compare(current_pending, 0.0, precision_digits=4) <= 0:
                raise UserError(
                    _(
                        "Esta línea ya está completamente cubierta por inventario "
                        "y/o compras relacionadas."
                    )
                )
            if float_compare(wline.qty_to_buy, current_pending, precision_digits=4) > 0:
                raise UserError(
                    _(
                        "No puede comprar %(qty)s unidades de %(product)s. "
                        "Solo quedan %(pending)s unidades pendientes de compra."
                    )
                    % {
                        "qty": wline.qty_to_buy,
                        "product": wline.product_id.display_name,
                        "pending": current_pending,
                    }
                )

        po = self._create_purchase_order(selected)
        self.sale_order_id.message_post(
            body=_("Orden de Compra creada %(po)s (trazabilidad por línea).")
            % {"po": po.name}
        )
        # Margin auto-link if available (never swallow unexpected errors silently)
        if hasattr(po, "_justech_auto_link_margin_from_sale"):
            po._justech_auto_link_margin_from_sale()
        return {
            "name": _("Orden de Compra"),
            "type": "ir.actions.act_window",
            "res_model": "purchase.order",
            "res_id": po.id,
            "view_mode": "form",
            "target": "current",
        }

    def _create_purchase_order(self, selected_lines):
        self.ensure_one()
        so = self.sale_order_id
        company = so.company_id
        if self.partner_id.property_purchase_currency_id:
            currency = self.partner_id.property_purchase_currency_id
        else:
            currency = company.currency_id
        po = self.env["purchase.order"].create(
            {
                "partner_id": self.partner_id.id,
                "date_order": self.date_order,
                "origin": so.name,
                "partner_ref": so.name,
                "currency_id": currency.id,
                "company_id": company.id,
            }
        )
        for wline in selected_lines:
            sol = wline.sale_line_id
            product = sol.product_id
            qty = wline.qty_to_buy
            uom = sol.product_uom_id or product.uom_id
            purchase_qty_uom = uom._compute_quantity(qty, product.uom_id)
            supplierinfo = product._select_seller(
                partner_id=po.partner_id,
                quantity=purchase_qty_uom,
                date=po.date_order and po.date_order.date(),
                uom_id=product.uom_id,
            )
            fpos = po.fiscal_position_id
            taxes = fpos.map_tax(product.supplier_taxes_id) if fpos else product.supplier_taxes_id
            taxes = taxes.filtered(lambda t: t.company_id.id == company.id)
            if supplierinfo:
                price_unit = self.env["account.tax"]._fix_tax_included_price_company(
                    supplierinfo.price,
                    product.supplier_taxes_id,
                    taxes,
                    company,
                )
                if po.currency_id and supplierinfo.currency_id != po.currency_id:
                    price_unit = supplierinfo.currency_id._convert(
                        price_unit,
                        po.currency_id,
                        company,
                        fields.Date.context_today(self),
                    )
            else:
                price_unit = self.env["account.tax"]._fix_tax_included_price_company(
                    product.uom_id._compute_price(product.standard_price, uom),
                    product.supplier_taxes_id,
                    taxes,
                    company,
                )
            self.env["purchase.order.line"].create(
                {
                    "order_id": po.id,
                    "product_id": product.id,
                    "name": sol.name or product.display_name,
                    "product_qty": qty,
                    "product_uom_id": uom.id,
                    "price_unit": price_unit,
                    "date_planned": self.date_order,
                    "tax_ids": [(6, 0, taxes.ids)],
                    "sale_line_id": sol.id,
                    "company_id": company.id,
                }
            )
        return po


class JustechBuyPendingWizardLine(models.TransientModel):
    _name = "justech.buy.pending.wizard.line"
    _description = "Línea generar orden de compra"

    wizard_id = fields.Many2one(
        "justech.buy.pending.wizard",
        required=True,
        ondelete="cascade",
    )
    selected = fields.Boolean(string="Seleccionar", default=False)
    sale_line_id = fields.Many2one(
        "sale.order.line",
        string="Línea de venta",
        readonly=True,
    )
    product_id = fields.Many2one("product.product", string="Producto", readonly=True)
    description = fields.Char(string="Descripción", readonly=True)
    qty_sold = fields.Float(string="Vendido", readonly=True)
    qty_stock_covered = fields.Float(string="Cubierto por inventario", readonly=True)
    qty_purchased = fields.Float(string="Ya comprado", readonly=True)
    qty_pending = fields.Float(string="Pendiente de comprar", readonly=True)
    qty_to_buy = fields.Float(string="Cantidad a comprar")
    snapshot_pending = fields.Float(string="Snapshot pendiente", readonly=True)

    @api.constrains("qty_to_buy", "qty_pending", "selected")
    def _check_qty_to_buy(self):
        for line in self:
            if not line.selected or not line.sale_line_id:
                continue
            if float_compare(line.qty_to_buy, 0.0, precision_digits=4) < 0:
                raise ValidationError(_("No se permiten cantidades negativas."))
            if float_compare(line.qty_to_buy, line.qty_pending, precision_digits=4) > 0:
                raise ValidationError(
                    _(
                        "No puede comprar %(qty)s unidades de %(product)s. "
                        "Solo quedan %(pending)s unidades pendientes de compra."
                    )
                    % {
                        "qty": line.qty_to_buy,
                        "product": line.product_id.display_name,
                        "pending": line.qty_pending,
                    }
                )
            if float_compare(line.qty_pending, 0.0, precision_digits=4) <= 0:
                raise ValidationError(
                    _(
                        "Esta línea ya está completamente cubierta por inventario "
                        "y/o compras relacionadas."
                    )
                )

    @api.onchange("selected")
    def _onchange_selected(self):
        for line in self:
            if line.selected and float_compare(line.qty_pending, 0.0, precision_digits=4) <= 0:
                line.selected = False
            if not line.selected:
                line.qty_to_buy = 0.0
            elif float_compare(line.qty_to_buy, 0.0, precision_digits=4) <= 0:
                line.qty_to_buy = line.qty_pending
