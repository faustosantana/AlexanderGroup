# -*- coding: utf-8 -*-
"""Operational cost UX — clean transients over CostManagementService.

Hub → one action window → hub.
One selection + create/link = ONE supplier / ONE PO or bill.
"""
from __future__ import annotations

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools.float_utils import float_compare
from markupsafe import Markup, escape

from odoo.addons.justech_purchase_sale_margin_control.services.cost_management_service import (
    CostManagementService,
)


def _suggest_price(env, product, partner=None):
    price = product.standard_price or 0.0
    if partner and "product.supplierinfo" in env:
        info = env["product.supplierinfo"].sudo().search(
            [
                ("product_tmpl_id", "=", product.product_tmpl_id.id),
                ("partner_id", "child_of", partner.commercial_partner_id.id),
            ],
            order="sequence, id",
            limit=1,
        )
        if info and info.price:
            price = info.price
    return price


def _product_label(product):
    if not product:
        return ""
    return product.display_name or product.name or ""


class PurchaseSaleCostCreatePurchaseWizard(models.TransientModel):
    _name = "purchase.sale.cost.create.purchase.wizard"
    _description = "Crear nueva compra (operativo)"

    hub_wizard_id = fields.Many2one(
        "purchase.sale.manage.purchases.wizard", required=True, ondelete="cascade"
    )
    company_id = fields.Many2one("res.company", required=True)
    currency_id = fields.Many2one(
        "res.currency", related="company_id.currency_id", readonly=True
    )
    step = fields.Selection(
        [("prepare", "Preparar"), ("review", "Revisar")],
        default="prepare",
        required=True,
    )
    show_more_details = fields.Boolean(string="Más detalles", default=False)
    supplier_id = fields.Many2one(
        "res.partner",
        string="Proveedor",
        domain="[('supplier_rank', '>', 0)]",
        required=False,
    )
    payment_term_id = fields.Many2one("account.payment.term", string="Términos de pago")
    partner_ref = fields.Char(string="Referencia")
    notes = fields.Char(string="Notas")
    excess_html = fields.Html(sanitize=False, readonly=True, compute="_compute_excess_html")
    line_ids = fields.One2many(
        "purchase.sale.cost.create.purchase.wizard.line",
        "wizard_id",
        string="Artículos",
    )
    review_ids = fields.One2many(
        "purchase.sale.cost.create.purchase.wizard.review",
        "wizard_id",
        string="Revisión",
    )
    review_html = fields.Html(sanitize=False, readonly=True)

    @api.depends("line_ids.buy_qty", "line_ids.pending_qty", "line_ids.sale_cover_qty")
    def _compute_excess_html(self):
        for rec in self:
            parts = []
            for line in rec.line_ids:
                buy = line.buy_qty or 0.0
                pending = line.pending_qty or 0.0
                cover = min(pending, buy) if buy > 0 else 0.0
                residual = max(buy - cover, 0.0)
                if float_compare(residual, 0.0, precision_digits=4) > 0:
                    parts.append(
                        "<li><b>%s</b>: PARA ESTA VENTA: %s · QUEDAN DISPONIBLES: %s</li>"
                        % (
                            escape(line.product_name or ""),
                            cover,
                            residual,
                        )
                    )
            if parts:
                rec.excess_html = Markup(
                    "<div class='text-muted'><p class='mb-1'>%s</p><ul>%s</ul></div>"
                    % (
                        escape(
                            _(
                                "Comprará más de lo pendiente en esta venta:"
                            )
                        ),
                        "".join(parts),
                    )
                )
            else:
                rec.excess_html = False

    def _return_hub(self):
        hub = self.hub_wizard_id
        hub._refresh_coverage()
        hub._clear_complete_selection()
        return hub.action_reopen_hub(refresh=False)

    def _reopen(self):
        return {
            "type": "ir.actions.act_window",
            "name": _("Crear nueva compra"),
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "views": [(False, "form")],
            "target": "new",
        }

    def action_toggle_more_details(self):
        self.ensure_one()
        self.show_more_details = not self.show_more_details
        return self._reopen()

    def action_back_prepare(self):
        self.ensure_one()
        self.step = "prepare"
        return self._reopen()

    @api.onchange("supplier_id")
    def _onchange_supplier_header(self):
        partner = self.supplier_id
        if partner:
            if "property_supplier_payment_term_id" in partner._fields:
                self.payment_term_id = partner.property_supplier_payment_term_id
            for line in self.line_ids:
                if line.product_id:
                    line.price_unit = _suggest_price(self.env, line.product_id, partner)

    def _sync_line_cover_qty(self):
        """Auto: for this sale = min(pending, buy)."""
        for line in self.line_ids:
            buy = line.buy_qty or 0.0
            pending = line.pending_qty or 0.0
            cover = min(pending, buy) if float_compare(buy, 0.0, precision_digits=4) > 0 else 0.0
            line.sale_cover_qty = cover
            line.assign_qty = cover  # backend still uses assign_qty

    def action_goto_review(self):
        self.ensure_one()
        if self.hub_wizard_id.is_readonly_mode:
            raise UserError(_("OPERACIÓN CANCELADA — SOLO CONSULTA"))
        if not self.supplier_id:
            raise UserError(_("Indique el proveedor."))
        lines = self.line_ids
        if not lines:
            raise UserError(_("No hay artículos para comprar."))
        self._sync_line_cover_qty()
        missing_price = []
        for line in lines:
            if float_compare(line.buy_qty or 0.0, 0.0, precision_digits=4) <= 0:
                raise UserError(
                    _("Indique cantidad a comprar para %s.") % (line.product_name,)
                )
            if float_compare(line.price_unit or 0.0, 0.0, precision_digits=4) <= 0:
                missing_price.append(line.product_name or "—")
            if float_compare(
                line.sale_cover_qty or 0.0, line.buy_qty, precision_digits=4
            ) > 0:
                raise UserError(
                    _(
                        "En %s la cantidad para esta venta no puede superar lo comprado."
                    )
                    % (line.product_name,)
                )
            if float_compare(
                line.sale_cover_qty or 0.0, line.pending_qty or 0.0, precision_digits=4
            ) > 0:
                raise UserError(
                    _(
                        "En %s no puede cubrir más que el pendiente de la venta."
                    )
                    % (line.product_name,)
                )
        if missing_price:
            raise UserError(
                _(
                    "No puede crear la orden de compra.\n\n"
                    "Indique el precio unitario de compra para todos los artículos.\n\n"
                    "Falta precio en:\n- %s"
                )
                % ("\n- ".join(missing_price))
            )
        self.review_ids.unlink()
        cmds = []
        total = 0.0
        for line in lines:
            cmds.append(
                (
                    0,
                    0,
                    {
                        "supplier_id": self.supplier_id.id,
                        "product_id": line.product_id.id,
                        "product_name": line.product_name,
                        "sale_line_id": line.sale_line_id.id,
                        "buy_qty": line.buy_qty,
                        "assign_qty": line.sale_cover_qty,
                        "price_unit": line.price_unit,
                        "currency_id": (line.currency_id or self.company_id.currency_id).id,
                        "payment_term_id": self.payment_term_id.id,
                        "partner_ref": self.partner_ref,
                        "notes": self.notes,
                    },
                )
            )
            total += (line.buy_qty or 0.0) * (line.price_unit or 0.0)
        self.write({"review_ids": cmds, "step": "review"})
        cur = self.company_id.currency_id
        rows = []
        for line in lines:
            rows.append(
                "<li>%s<br/><span class='text-muted'>%s × %s %s</span>"
                "<br/><span class='text-muted'>PARA ESTA VENTA: %s%s</span></li>"
                % (
                    escape(line.product_name or ""),
                    line.buy_qty,
                    "%.2f" % (line.price_unit or 0.0),
                    escape(cur.name or ""),
                    line.sale_cover_qty,
                    (
                        " · QUEDAN DISPONIBLES: %s"
                        % max((line.buy_qty or 0.0) - (line.sale_cover_qty or 0.0), 0.0)
                        if float_compare(
                            (line.buy_qty or 0.0) - (line.sale_cover_qty or 0.0),
                            0.0,
                            precision_digits=4,
                        )
                        > 0
                        else ""
                    ),
                )
            )
        self.review_html = Markup(
            "<div>"
            "<p class='mb-1'><b>%s</b></p>"
            "<p class='mb-2'><b>%s</b></p>"
            "<ul>%s</ul>"
            "<p class='mt-2'><b>%s</b> %s %s</p>"
            "</div>"
        ) % (
            escape(_("REVISAR ORDEN DE COMPRA")),
            escape(self.supplier_id.display_name),
            Markup("".join(rows)),
            escape(_("Total estimado:")),
            "%.2f" % total,
            escape(cur.name or ""),
        )
        return self._reopen()

    def action_create_draft_orders(self):
        self.ensure_one()
        if self.hub_wizard_id.is_readonly_mode:
            raise UserError(_("OPERACIÓN CANCELADA — SOLO CONSULTA"))
        if not self.supplier_id:
            raise UserError(_("Indique el proveedor."))
        if not self.review_ids:
            raise UserError(_("Revise la orden antes de crear."))
        hub = self.hub_wizard_id
        tx = hub._ensure_transaction()
        svc = CostManagementService(self.env)
        po_vals = {}
        if self.currency_id:
            po_vals["currency_id"] = self.currency_id.id
        if self.payment_term_id:
            po_vals["payment_term_id"] = self.payment_term_id.id
        if self.partner_ref:
            po_vals["partner_ref"] = self.partner_ref
        if self.notes:
            po_vals["notes"] = self.notes
        groups = [
            {
                "partner": self.supplier_id,
                "po_vals": po_vals,
                "lines": [
                    {
                        "product": ln.product_id,
                        "buy_qty": ln.buy_qty,
                        "assign_qty": ln.assign_qty,
                        "price": ln.price_unit,
                        "sale_line": ln.sale_line_id,
                        "name": ln.product_name,
                    }
                    for ln in self.review_ids
                ],
            }
        ]
        pos = svc.create_draft_pos_and_assign(tx, self.company_id, groups)
        if not pos:
            raise UserError(_("No se creó la orden de compra."))
        return self._return_hub()


class PurchaseSaleCostCreatePurchaseWizardLine(models.TransientModel):
    _name = "purchase.sale.cost.create.purchase.wizard.line"
    _description = "Línea preparar compra"

    wizard_id = fields.Many2one(
        "purchase.sale.cost.create.purchase.wizard", required=True, ondelete="cascade"
    )
    sale_line_id = fields.Many2one("sale.order.line", required=True)
    product_id = fields.Many2one("product.product", required=True)
    product_name = fields.Char(string="Artículo")
    pending_qty = fields.Float(
        string="Pendiente venta", digits="Product Unit of Measure"
    )
    buy_qty = fields.Float(string="Comprar", digits="Product Unit of Measure")
    sale_cover_qty = fields.Float(
        string="Para esta venta",
        digits="Product Unit of Measure",
        help="Por defecto: mínimo entre pendiente y comprar.",
    )
    # Kept for backend create_draft_pos_and_assign compatibility (not shown in UX).
    assign_qty = fields.Float(digits="Product Unit of Measure")
    supplier_id = fields.Many2one("res.partner")  # unused in UX; header owns supplier
    price_unit = fields.Float(string="Precio unitario")
    currency_id = fields.Many2one("res.currency", string="Moneda")
    payment_term_id = fields.Many2one("account.payment.term")
    partner_ref = fields.Char()
    notes = fields.Char()

    @api.onchange("buy_qty", "pending_qty")
    def _onchange_buy_qty(self):
        buy = self.buy_qty or 0.0
        pending = self.pending_qty or 0.0
        self.sale_cover_qty = min(pending, buy) if buy > 0 else 0.0
        self.assign_qty = self.sale_cover_qty


class PurchaseSaleCostCreatePurchaseWizardReview(models.TransientModel):
    _name = "purchase.sale.cost.create.purchase.wizard.review"
    _description = "Revisión OC"

    wizard_id = fields.Many2one(
        "purchase.sale.cost.create.purchase.wizard", required=True, ondelete="cascade"
    )
    supplier_id = fields.Many2one("res.partner", string="Proveedor", required=True)
    product_id = fields.Many2one("product.product", required=True)
    product_name = fields.Char(string="Artículo")
    sale_line_id = fields.Many2one("sale.order.line", required=True)
    buy_qty = fields.Float(string="Comprar", digits="Product Unit of Measure")
    assign_qty = fields.Float(string="Para esta venta", digits="Product Unit of Measure")
    price_unit = fields.Float(string="Precio")
    currency_id = fields.Many2one("res.currency", string="Moneda")
    payment_term_id = fields.Many2one("account.payment.term")
    partner_ref = fields.Char()
    notes = fields.Char()


class PurchaseSaleCostLinkWizard(models.TransientModel):
    _name = "purchase.sale.cost.link.wizard"
    _description = "Vincular compra existente (operativo)"

    hub_wizard_id = fields.Many2one(
        "purchase.sale.manage.purchases.wizard", required=True, ondelete="cascade"
    )
    company_id = fields.Many2one("res.company", required=True)
    mode = fields.Selection(
        [("po", "Orden de compra"), ("bill", "Factura de proveedor")],
        default="po",
        required=True,
        string="Fuente",
    )
    supplier_id = fields.Many2one(
        "res.partner",
        string="Proveedor",
        domain="[('supplier_rank', '>', 0)]",
    )
    purchase_order_id = fields.Many2one("purchase.order", string="Orden de compra")
    eligible_po_ids = fields.Many2many(
        "purchase.order", string="OC elegibles", compute="_compute_eligible_pos"
    )
    show_all_po_lines = fields.Boolean(
        string="Mostrar todos los artículos de esta OC", default=False
    )
    pol_line_ids = fields.One2many(
        "purchase.sale.cost.link.wizard.pol", "wizard_id", string="Artículos de la OC"
    )
    bill_search = fields.Char(string="Buscar factura / NCF")
    vendor_bill_id = fields.Many2one("account.move", string="Factura proveedor")
    eligible_bill_ids = fields.Many2many(
        "account.move", string="Facturas", compute="_compute_eligible_bills"
    )
    show_all_bill_lines = fields.Boolean(
        string="Mostrar todas las líneas de la factura", default=False
    )
    bill_line_ids = fields.One2many(
        "purchase.sale.cost.link.wizard.bill", "wizard_id", string="Líneas factura"
    )
    sale_line_ids = fields.Many2many("sale.order.line", string="Líneas venta")

    def _selected_products(self):
        return self.sale_line_ids.mapped("product_id")

    @api.depends("supplier_id", "company_id", "sale_line_ids")
    def _compute_eligible_pos(self):
        svc = CostManagementService(self.env)
        for rec in self:
            if not rec.supplier_id or not rec.company_id:
                rec.eligible_po_ids = False
                continue
            pos = svc.eligible_purchase_orders(
                rec.company_id, rec.supplier_id, show_exhausted=False
            )
            products = rec._selected_products()
            if products:
                matching = self.env["purchase.order"]
                others = self.env["purchase.order"]
                for po in pos:
                    pols = po.order_line.filtered(
                        lambda l: l.product_id in products
                        and float_compare(
                            svc.alloc.pol_qty_available(l), 0.0, precision_digits=4
                        )
                        > 0
                    )
                    if pols:
                        matching |= po
                    else:
                        others |= po
                rec.eligible_po_ids = matching or others
            else:
                rec.eligible_po_ids = pos

    @api.depends("supplier_id", "company_id", "bill_search")
    def _compute_eligible_bills(self):
        svc = CostManagementService(self.env)
        for rec in self:
            if not rec.supplier_id or not rec.company_id:
                rec.eligible_bill_ids = False
                continue
            rec.eligible_bill_ids = svc.eligible_vendor_bills(
                rec.company_id, rec.supplier_id, name_search=rec.bill_search
            )

    def _return_hub(self):
        hub = self.hub_wizard_id
        hub._refresh_coverage()
        hub._clear_complete_selection()
        return hub.action_reopen_hub(refresh=False)

    def _reopen(self):
        return {
            "type": "ir.actions.act_window",
            "name": _("Vincular compra existente"),
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "views": [(False, "form")],
            "target": "new",
        }

    def action_set_mode_po(self):
        self.mode = "po"
        return self._reopen()

    def action_set_mode_bill(self):
        self.mode = "bill"
        return self._reopen()

    def action_toggle_show_all_po_lines(self):
        self.ensure_one()
        self.show_all_po_lines = not self.show_all_po_lines
        self.write({"pol_line_ids": [(5, 0, 0)] + self._pol_line_cmds()})
        return self._reopen()

    def action_toggle_show_all_bill_lines(self):
        self.ensure_one()
        self.show_all_bill_lines = not self.show_all_bill_lines
        self.write({"bill_line_ids": [(5, 0, 0)] + self._bill_line_cmds()})
        return self._reopen()

    @api.onchange("supplier_id")
    def _onchange_supplier(self):
        self.purchase_order_id = False
        self.vendor_bill_id = False
        self.pol_line_ids = [(5, 0, 0)]
        self.bill_line_ids = [(5, 0, 0)]

    def _hub_pending_for_product(self, product):
        hub = self.hub_wizard_id
        pending = 0.0
        for hl in hub.line_ids.filtered(
            lambda l: l.product_id == product
            and l.sale_line_id in self.sale_line_ids
            and float_compare(l.pending_qty or 0.0, 0.0, precision_digits=4) > 0
        ):
            pending += hl.pending_qty or 0.0
        return pending

    def _pol_line_cmds(self):
        self.ensure_one()
        if not self.purchase_order_id:
            return []
        svc = CostManagementService(self.env)
        products = self._selected_products()
        focus = products[:1]
        cmds = []
        for row in svc.pol_pick_rows(
            self.purchase_order_id,
            focus_product=focus,
            show_exhausted=False,
        ):
            product = self.env["product.product"].browse(row["product_id"])
            if not product:
                continue
            is_match = product in products if products else True
            if not self.show_all_po_lines and products and not is_match:
                continue
            need = self._hub_pending_for_product(product) if is_match else 0.0
            suggest = min(need, row["qty_available"] or 0.0) if is_match else 0.0
            cmds.append(
                (
                    0,
                    0,
                    {
                        **row,
                        "qty_needed": need,
                        "qty_to_use": suggest,
                        "is_focus_product": is_match,
                    },
                )
            )
        return cmds

    def _bill_line_cmds(self):
        self.ensure_one()
        bill = self.vendor_bill_id
        if not bill:
            return []
        products = self._selected_products()
        cmds = []
        for aml in bill.invoice_line_ids.filtered(
            lambda l: (not l.display_type or l.display_type == "product") and l.product_id
        ):
            product = aml.product_id
            is_match = product in products if products else True
            if not self.show_all_bill_lines and products and not is_match:
                continue
            unit = (
                abs(aml.price_subtotal or 0.0) / aml.quantity if aml.quantity else 0.0
            )
            need = self._hub_pending_for_product(product) if is_match else 0.0
            suggest = min(need, aml.quantity or 0.0) if is_match else 0.0
            cmds.append(
                (
                    0,
                    0,
                    {
                        "move_line_id": aml.id,
                        "product_id": product.id,
                        "qty_on_bill": aml.quantity or 0.0,
                        "qty_needed": need,
                        "unit_cost": unit,
                        "qty_to_use": suggest,
                    },
                )
            )
        return cmds

    @api.onchange("purchase_order_id")
    def _onchange_po(self):
        self.pol_line_ids = [(5, 0, 0)] + self._pol_line_cmds()

    @api.onchange("vendor_bill_id")
    def _onchange_bill(self):
        self.bill_line_ids = [(5, 0, 0)] + self._bill_line_cmds()

    def action_load_po_lines(self):
        self.ensure_one()
        self.write({"pol_line_ids": [(5, 0, 0)] + self._pol_line_cmds()})
        return self._reopen()

    def action_load_bill_lines(self):
        self.ensure_one()
        self.write({"bill_line_ids": [(5, 0, 0)] + self._bill_line_cmds()})
        return self._reopen()

    def _resolve_sale_lines_for_product(self, product):
        """Resolve SOL from selected hub lines. Never raise with 'False'."""
        if not product:
            return self.env["sale.order.line"]
        hub = self.hub_wizard_id
        sols = self.sale_line_ids.filtered(lambda s: s.product_id == product)
        if not sols:
            sols = hub.line_ids.filtered(
                lambda l: l.product_id == product
                and float_compare(l.pending_qty or 0.0, 0.0, precision_digits=4) > 0
            ).mapped("sale_line_id")
        if not sols:
            sols = hub.line_ids.filtered(
                lambda l: l.product_id == product
            ).mapped("sale_line_id")
        return sols

    def action_apply(self):
        self.ensure_one()
        if self.hub_wizard_id.is_readonly_mode:
            raise UserError(_("OPERACIÓN CANCELADA — SOLO CONSULTA"))
        hub = self.hub_wizard_id
        tx = hub._ensure_transaction()
        svc = CostManagementService(self.env)
        if self.mode == "po":
            picks = self.pol_line_ids.filtered(
                lambda p: float_compare(p.qty_to_use or 0.0, 0.0, precision_digits=4) > 0
            )
            if not picks:
                raise UserError(_("Indique al menos una cantidad en «Usar»."))
            for pick in picks:
                product = pick.product_id
                if not product:
                    raise UserError(
                        _(
                            "No pudimos determinar a qué artículo de la venta "
                            "corresponde esta línea."
                        )
                    )
                sols = self._resolve_sale_lines_for_product(product)
                if not sols:
                    raise UserError(
                        _(
                            "No pudimos determinar a qué artículo de la venta "
                            "corresponde «%s»."
                        )
                        % (_product_label(product),)
                    )
                remaining = pick.qty_to_use
                for sol in sols:
                    if float_compare(remaining, 0.0, precision_digits=4) <= 0:
                        break
                    hub_line = hub.line_ids.filtered(
                        lambda l, s=sol: l.sale_line_id == s
                    )[:1]
                    pending = hub_line.pending_qty if hub_line else remaining
                    use = min(remaining, pending or remaining)
                    if float_compare(use, 0.0, precision_digits=4) <= 0:
                        continue
                    svc.apply_relate_po_lines(
                        tx,
                        self.company_id,
                        sol,
                        [{"purchase_line": pick.purchase_line_id, "quantity": use}],
                    )
                    remaining -= use
        else:
            picks = self.bill_line_ids.filtered(
                lambda p: float_compare(p.qty_to_use or 0.0, 0.0, precision_digits=4) > 0
            )
            if not picks:
                raise UserError(_("Indique cantidad a usar en la factura."))
            for pick in picks:
                product = pick.product_id
                # ROOT CAUSE of "False": empty product_id → display_name formats as False
                if not product or not pick.move_line_id:
                    raise UserError(
                        _(
                            "No pudimos determinar a qué artículo de la venta "
                            "corresponde esta línea."
                        )
                    )
                sols = self._resolve_sale_lines_for_product(product)
                if not sols:
                    raise UserError(
                        _(
                            "No pudimos determinar a qué artículo de la venta "
                            "corresponde «%s»."
                        )
                        % (_product_label(product),)
                    )
                remaining = pick.qty_to_use
                for sol in sols:
                    if float_compare(remaining, 0.0, precision_digits=4) <= 0:
                        break
                    hub_line = hub.line_ids.filtered(
                        lambda l, s=sol: l.sale_line_id == s
                    )[:1]
                    pending = hub_line.pending_qty if hub_line else remaining
                    use = min(remaining, pending or remaining)
                    if float_compare(use, 0.0, precision_digits=4) <= 0:
                        continue
                    svc.apply_vendor_bill_line(
                        tx, self.company_id, sol, pick.move_line_id, use
                    )
                    remaining -= use
        return self._return_hub()


class PurchaseSaleCostLinkWizardPol(models.TransientModel):
    _name = "purchase.sale.cost.link.wizard.pol"
    _description = "Línea OC vincular"

    wizard_id = fields.Many2one(
        "purchase.sale.cost.link.wizard", required=True, ondelete="cascade"
    )
    purchase_line_id = fields.Many2one("purchase.order.line", required=True)
    product_id = fields.Many2one("product.product", string="Artículo")
    qty_purchased = fields.Float(string="Comprado")
    qty_assigned = fields.Float(string="Ya relacionado")
    qty_available = fields.Float(string="Disponible OC")
    qty_needed = fields.Float(string="Necesito")
    unit_cost = fields.Float(string="Costo unitario")
    qty_to_use = fields.Float(string="Usar")
    is_focus_product = fields.Boolean()


class PurchaseSaleCostLinkWizardBill(models.TransientModel):
    _name = "purchase.sale.cost.link.wizard.bill"
    _description = "Línea factura vincular"

    wizard_id = fields.Many2one(
        "purchase.sale.cost.link.wizard", required=True, ondelete="cascade"
    )
    move_line_id = fields.Many2one("account.move.line", required=True)
    product_id = fields.Many2one("product.product", string="Artículo")
    qty_on_bill = fields.Float(string="En factura")
    qty_needed = fields.Float(string="Necesito")
    unit_cost = fields.Float(string="Costo unitario")
    qty_to_use = fields.Float(string="Usar")


class PurchaseSaleCostInventoryWizard(models.TransientModel):
    _name = "purchase.sale.cost.inventory.wizard"
    _description = "Usar inventario / histórico (operativo)"

    hub_wizard_id = fields.Many2one(
        "purchase.sale.manage.purchases.wizard", required=True, ondelete="cascade"
    )
    company_id = fields.Many2one("res.company", required=True)
    mode = fields.Selection(
        [
            ("reference", "Inventario (referencia)"),
            ("historical", "Existencia histórica"),
        ],
        default="historical",
        required=True,
    )
    line_ids = fields.One2many(
        "purchase.sale.cost.inventory.wizard.line", "wizard_id", string="Artículos"
    )
    info_html = fields.Html(sanitize=False, readonly=True)

    def _return_hub(self):
        hub = self.hub_wizard_id
        hub._refresh_coverage()
        hub._clear_complete_selection()
        return hub.action_reopen_hub(refresh=False)

    def _reopen(self):
        return {
            "type": "ir.actions.act_window",
            "name": _("Usar inventario"),
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "views": [(False, "form")],
            "target": "new",
        }

    def action_set_historical(self):
        self.mode = "historical"
        self.info_html = False
        return self._reopen()

    def action_set_reference(self):
        self.mode = "reference"
        self.info_html = Markup(
            "<p class='text-muted'>%s</p>"
            % escape(
                _(
                    "El inventario Odoo se muestra solo como referencia. "
                    "Todavía no se consume automáticamente. "
                    "Use «Existencia histórica» para registrar cobertura."
                )
            )
        )
        return self._reopen()

    def action_apply(self):
        self.ensure_one()
        if self.hub_wizard_id.is_readonly_mode:
            raise UserError(_("OPERACIÓN CANCELADA — SOLO CONSULTA"))
        if self.mode != "historical":
            raise UserError(
                _(
                    "El inventario formal aún no se consume automáticamente. "
                    "Use existencia histórica."
                )
            )
        hub = self.hub_wizard_id
        tx = hub._ensure_transaction()
        svc = CostManagementService(self.env)
        applied = False
        for line in self.line_ids:
            qty = line.use_qty or 0.0
            if float_compare(qty, 0.0, precision_digits=4) <= 0:
                continue
            if float_compare(qty, line.pending_qty or 0.0, precision_digits=4) > 0:
                raise UserError(
                    _("No puede cubrir más que el pendiente (%s).")
                    % (line.product_name,)
                )
            svc.apply_historical(
                tx,
                self.company_id,
                line.sale_line_id,
                line.product_id,
                qty,
                line.unit_cost or 0.0,
                note=line.note or "",
            )
            applied = True
        if not applied:
            raise UserError(_("Indique cantidad y costo en al menos un artículo."))
        return self._return_hub()


class PurchaseSaleCostInventoryWizardLine(models.TransientModel):
    _name = "purchase.sale.cost.inventory.wizard.line"
    _description = "Línea inventario operativo"

    wizard_id = fields.Many2one(
        "purchase.sale.cost.inventory.wizard", required=True, ondelete="cascade"
    )
    sale_line_id = fields.Many2one("sale.order.line", required=True)
    product_id = fields.Many2one("product.product", required=True)
    product_name = fields.Char(string="Artículo")
    pending_qty = fields.Float(string="Pendiente")
    stock_qty = fields.Float(string="Existencia", readonly=True)
    stock_reserved = fields.Float(string="Reservado", readonly=True)
    stock_available = fields.Float(string="Disponible Odoo", readonly=True)
    use_qty = fields.Float(string="Usar")
    unit_cost = fields.Float(string="Costo unitario")
    note = fields.Char(string="Nota")
