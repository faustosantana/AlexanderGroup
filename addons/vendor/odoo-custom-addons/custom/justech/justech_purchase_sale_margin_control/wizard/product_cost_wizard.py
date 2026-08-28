# -*- coding: utf-8 -*-
"""Product cost modal — one product, one of four cost sources (DEV professional UX)."""
from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError
from odoo.tools.float_utils import float_compare

from odoo.addons.justech_purchase_sale_margin_control.models.margin_acl import (
    ensure_canonical_mtx_for_authorized_docs,
    functional_access_denied,
    margin_transaction,
)
from odoo.addons.justech_purchase_sale_margin_control.services.cost_management_service import (
    CostManagementService,
)
from odoo.addons.justech_purchase_sale_margin_control.services.line_allocation_service import (
    _is_product_line,
)


class PurchaseSaleProductCostWizard(models.TransientModel):
    _name = "purchase.sale.product.cost.wizard"
    _description = "Gestionar costo de un producto"

    hub_wizard_id = fields.Many2one(
        "purchase.sale.manage.purchases.wizard", required=True, ondelete="cascade"
    )
    company_id = fields.Many2one("res.company", required=True)
    sale_line_id = fields.Many2one("sale.order.line", required=True)
    product_id = fields.Many2one("product.product", required=True)
    product_label = fields.Char(readonly=True)
    sold_qty = fields.Float(readonly=True)
    covered_qty = fields.Float(readonly=True)
    pending_qty = fields.Float(readonly=True)
    stock_qty = fields.Float(string="Existencia (ref.)", readonly=True)
    stock_reserved = fields.Float(string="Reservado (ref.)", readonly=True)
    stock_available = fields.Float(string="Disponible (ref.)", readonly=True)
    is_readonly = fields.Boolean(readonly=True)

    step = fields.Selection(
        [
            ("choose", "Elegir fuente"),
            ("relate", "Compra existente"),
            ("bill", "Factura proveedor"),
            ("create_po", "Nueva compra"),
            ("historical", "Histórico / manual"),
            ("sources", "Ver fuentes"),
        ],
        default="choose",
        required=True,
    )

    # --- Relate PO ---
    supplier_id = fields.Many2one("res.partner", string="Proveedor")
    purchase_order_id = fields.Many2one("purchase.order", string="Orden de compra")
    purchase_order_domain = fields.Char(compute="_compute_po_domain")
    eligible_po_ids = fields.Many2many(
        "purchase.order", string="OC disponibles", compute="_compute_eligible_pos"
    )
    show_exhausted = fields.Boolean(string="Mostrar sin disponible")
    pol_pick_ids = fields.One2many(
        "purchase.sale.product.cost.wizard.pol", "wizard_id", string="Líneas OC"
    )

    # --- Vendor bill ---
    bill_supplier_id = fields.Many2one("res.partner", string="Proveedor (factura)")
    bill_search = fields.Char(string="Buscar factura / NCF")
    vendor_bill_id = fields.Many2one("account.move", string="Factura proveedor")
    vendor_bill_domain = fields.Char(compute="_compute_bill_domain")
    bill_line_ids = fields.One2many(
        "purchase.sale.product.cost.wizard.bill.line", "wizard_id", string="Líneas factura"
    )

    # --- Create PO (preparation — not created until confirm) ---
    new_partner_id = fields.Many2one("res.partner", string="Proveedor")
    new_currency_id = fields.Many2one("res.currency", string="Moneda")
    new_date_order = fields.Datetime(string="Fecha", default=fields.Datetime.now)
    new_payment_term_id = fields.Many2one(
        "account.payment.term", string="Condiciones de pago"
    )
    new_partner_ref = fields.Char(string="Referencia proveedor")
    new_user_id = fields.Many2one(
        "res.users", string="Responsable compras", default=lambda self: self.env.user
    )
    new_notes = fields.Text(string="Notas")
    new_buy_qty = fields.Float(string="Cantidad a comprar")
    new_assign_qty = fields.Float(string="Cantidad atribuida a esta venta")
    new_price = fields.Float(string="Precio unitario")
    new_residual_qty = fields.Float(
        string="Residual libre (compra − atribuido)", compute="_compute_new_residual"
    )

    # --- Historical ---
    hist_qty = fields.Float(string="Cantidad")
    hist_unit_cost = fields.Float(string="Costo unitario")
    hist_note = fields.Char(string="Nota / motivo")

    # --- Applied sources (view) ---
    source_html = fields.Html(sanitize=False, readonly=True)

    @api.depends("new_buy_qty", "new_assign_qty")
    def _compute_new_residual(self):
        for rec in self:
            rec.new_residual_qty = max((rec.new_buy_qty or 0.0) - (rec.new_assign_qty or 0.0), 0.0)

    @api.depends("supplier_id", "company_id")
    def _compute_po_domain(self):
        for rec in self:
            if not rec.company_id or not rec.supplier_id:
                rec.purchase_order_domain = repr([("id", "=", False)])
            else:
                rec.purchase_order_domain = repr(
                    [
                        ("company_id", "=", rec.company_id.id),
                        (
                            "partner_id",
                            "child_of",
                            rec.supplier_id.commercial_partner_id.id,
                        ),
                        ("state", "!=", "cancel"),
                    ]
                )

    @api.depends("supplier_id", "company_id", "show_exhausted")
    def _compute_eligible_pos(self):
        svc = CostManagementService(self.env)
        for rec in self:
            if not rec.supplier_id or not rec.company_id:
                rec.eligible_po_ids = False
                continue
            rec.eligible_po_ids = svc.eligible_purchase_orders(
                rec.company_id, rec.supplier_id, show_exhausted=rec.show_exhausted
            )

    @api.depends("bill_supplier_id", "company_id", "bill_search")
    def _compute_bill_domain(self):
        for rec in self:
            if not rec.company_id or not rec.bill_supplier_id:
                rec.vendor_bill_domain = repr([("id", "=", False)])
                continue
            domain = [
                ("company_id", "=", rec.company_id.id),
                ("move_type", "in", ("in_invoice", "in_refund")),
                ("state", "=", "posted"),
                (
                    "partner_id",
                    "child_of",
                    rec.bill_supplier_id.commercial_partner_id.id,
                ),
            ]
            rec.vendor_bill_domain = repr(domain)

    def _assert_writable(self):
        self.ensure_one()
        if self.is_readonly or self.hub_wizard_id.is_readonly_mode:
            raise UserError(
                _("OPERACIÓN CANCELADA — SOLO CONSULTA. No se permiten cambios.")
            )

    def _ensure_tx(self):
        hub = self.hub_wizard_id
        return hub._ensure_transaction()

    def _return_hub(self):
        hub = self.hub_wizard_id
        hub._refresh_coverage()
        return {
            "type": "ir.actions.act_window",
            "name": _("Gestionar compras y costos"),
            "res_model": "purchase.sale.manage.purchases.wizard",
            "res_id": hub.id,
            "view_mode": "form",
            "target": "new",
        }

    def action_choose_relate(self):
        self._assert_writable()
        self.step = "relate"
        return self._reopen()

    def action_choose_bill(self):
        self._assert_writable()
        self.step = "bill"
        self.bill_supplier_id = self.supplier_id or self.bill_supplier_id
        return self._reopen()

    def action_choose_create_po(self):
        self._assert_writable()
        self.step = "create_po"
        self.new_buy_qty = self.pending_qty
        self.new_assign_qty = self.pending_qty
        if self.product_id and not self.new_price:
            self.new_price = self._suggest_price()
        if not self.new_currency_id:
            self.new_currency_id = self.company_id.currency_id
        return self._reopen()

    def action_choose_historical(self):
        self._assert_writable()
        self.step = "historical"
        self.hist_qty = self.pending_qty
        return self._reopen()

    def action_choose_sources(self):
        self.step = "sources"
        self._rebuild_sources_html()
        return self._reopen()

    def action_back_choose(self):
        self.step = "choose"
        return self._reopen()

    def _reopen(self):
        return {
            "type": "ir.actions.act_window",
            "name": _("Gestionar costo"),
            "res_model": "purchase.sale.product.cost.wizard",
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }

    def _suggest_price(self):
        product = self.product_id
        partner = self.new_partner_id
        price = product.standard_price or 0.0
        if partner and "product.supplierinfo" in self.env:
            info = self.env["product.supplierinfo"].sudo().search(
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

    @api.onchange("new_partner_id")
    def _onchange_new_partner(self):
        if self.new_partner_id and self.product_id:
            self.new_price = self._suggest_price()

    @api.onchange("supplier_id", "show_exhausted")
    def _onchange_supplier(self):
        self.purchase_order_id = False
        self.pol_pick_ids = [(5, 0, 0)]

    @api.onchange("purchase_order_id", "show_exhausted")
    def _onchange_po(self):
        self.pol_pick_ids = [(5, 0, 0)]
        if not self.purchase_order_id:
            return
        svc = CostManagementService(self.env)
        cmds = [
            (
                0,
                0,
                {
                    **row,
                    "qty_to_use": 0.0,
                },
            )
            for row in svc.pol_pick_rows(
                self.purchase_order_id,
                focus_product=self.product_id,
                show_exhausted=self.show_exhausted,
            )
        ]
        self.pol_pick_ids = cmds

    @api.onchange("vendor_bill_id")
    def _onchange_bill(self):
        self.bill_line_ids = [(5, 0, 0)]
        bill = self.vendor_bill_id
        if not bill:
            return
        cmds = []
        for aml in bill.invoice_line_ids.filtered(
            lambda l: (not l.display_type or l.display_type == "product") and l.product_id
        ):
            unit = (
                abs(aml.price_subtotal or 0.0) / aml.quantity if aml.quantity else 0.0
            )
            cmds.append(
                (
                    0,
                    0,
                    {
                        "move_line_id": aml.id,
                        "product_id": aml.product_id.id,
                        "qty_on_bill": aml.quantity or 0.0,
                        "unit_cost": unit,
                        "qty_to_use": 0.0,
                        "is_focus_product": bool(
                            self.product_id and aml.product_id == self.product_id
                        ),
                    },
                )
            )
        self.bill_line_ids = cmds

    def action_apply_relate(self):
        self.ensure_one()
        self._assert_writable()
        picks = self.pol_pick_ids.filtered(
            lambda p: float_compare(p.qty_to_use or 0.0, 0.0, precision_digits=4) > 0
        )
        if not picks:
            raise UserError(_("Indique la cantidad a usar en al menos una línea."))
        total = sum(picks.mapped("qty_to_use"))
        if float_compare(total, self.pending_qty or 0.0, precision_digits=4) > 0:
            raise UserError(
                _("No puede relacionar %(qty)s: pendiente %(pending)s.")
                % {"qty": total, "pending": self.pending_qty}
            )
        tx = self._ensure_tx()
        svc = CostManagementService(self.env)
        try:
            svc.apply_relate_po_lines(
                tx,
                self.company_id,
                self.sale_line_id,
                [
                    {
                        "purchase_line": p.purchase_line_id,
                        "quantity": p.qty_to_use,
                    }
                    for p in picks
                ],
            )
        except AccessError as err:
            raise functional_access_denied(err) from err
        return self._return_hub()

    def action_apply_bill(self):
        self.ensure_one()
        self._assert_writable()
        picks = self.bill_line_ids.filtered(
            lambda p: float_compare(p.qty_to_use or 0.0, 0.0, precision_digits=4) > 0
        )
        if not picks:
            raise UserError(_("Indique cantidad en al menos una línea de factura."))
        total = sum(picks.mapped("qty_to_use"))
        if float_compare(total, self.pending_qty or 0.0, precision_digits=4) > 0:
            raise UserError(
                _("No puede relacionar %(qty)s: pendiente %(pending)s.")
                % {"qty": total, "pending": self.pending_qty}
            )
        tx = self._ensure_tx()
        svc = CostManagementService(self.env)
        try:
            for p in picks:
                amount = (p.qty_to_use or 0.0) * (p.unit_cost or 0.0)
                svc.apply_vendor_bill_line(
                    tx,
                    self.company_id,
                    self.sale_line_id,
                    p.move_line_id,
                    p.qty_to_use,
                    amount=amount,
                )
        except AccessError as err:
            raise functional_access_denied(err) from err
        return self._return_hub()

    def action_confirm_create_po(self):
        """Create PO only after user reviews partner/price/qty/terms."""
        self.ensure_one()
        self._assert_writable()
        buy = self.new_buy_qty or 0.0
        assign = self.new_assign_qty or 0.0
        if not self.new_partner_id:
            raise UserError(_("Seleccione el proveedor."))
        if float_compare(buy, 0.0, precision_digits=4) <= 0:
            raise UserError(_("Indique la cantidad a comprar."))
        if float_compare(assign, 0.0, precision_digits=4) <= 0:
            raise UserError(_("Indique cuánto se atribuye a esta venta."))
        if float_compare(assign, buy, precision_digits=4) > 0:
            raise UserError(
                _("Lo atribuido a la venta no puede superar la cantidad comprada.")
            )
        if float_compare(assign, self.pending_qty or 0.0, precision_digits=4) > 0:
            raise UserError(
                _("Lo atribuido (%(a)s) supera el pendiente (%(p)s).")
                % {"a": assign, "p": self.pending_qty}
            )
        tx = self._ensure_tx()
        svc = CostManagementService(self.env)
        po_extra = {
            "date_order": self.new_date_order or fields.Datetime.now(),
            "partner_ref": self.new_partner_ref or False,
            "user_id": self.new_user_id.id if self.new_user_id else False,
            "notes": self.new_notes or False,
        }
        if self.new_currency_id and "currency_id" in self.env["purchase.order"]._fields:
            po_extra["currency_id"] = self.new_currency_id.id
        if self.new_payment_term_id:
            po_extra["payment_term_id"] = self.new_payment_term_id.id
        try:
            po = svc.create_purchase_order(
                self.company_id,
                self.new_partner_id,
                [
                    {
                        "product": self.product_id,
                        "qty": buy,
                        "price": self.new_price or 0.0,
                    }
                ],
                vals=po_extra,
            )
            # Leave draft for review unless confirm is desired — user asked editable before create;
            # creation happens here after review. Do NOT auto-confirm.
            pol = po.order_line.filtered(_is_product_line)[:1]
            if not pol:
                raise UserError(_("No se pudo crear la línea de compra."))
            svc.assign_po_line_to_sale(
                tx, self.company_id, self.sale_line_id, pol, assign
            )
        except AccessError as err:
            raise functional_access_denied(err) from err
        return self._return_hub()

    def action_apply_historical(self):
        self.ensure_one()
        self._assert_writable()
        if float_compare(self.hist_qty or 0.0, self.pending_qty or 0.0, precision_digits=4) > 0:
            raise UserError(
                _("No puede cubrir %(qty)s: pendiente %(pending)s.")
                % {"qty": self.hist_qty, "pending": self.pending_qty}
            )
        tx = self._ensure_tx()
        svc = CostManagementService(self.env)
        try:
            svc.apply_historical(
                tx,
                self.company_id,
                self.sale_line_id,
                self.product_id,
                self.hist_qty,
                self.hist_unit_cost,
                note=self.hist_note or "",
            )
        except AccessError as err:
            raise functional_access_denied(err) from err
        return self._return_hub()

    def _rebuild_sources_html(self):
        self.ensure_one()
        hub = self.hub_wizard_id
        line = hub.line_ids.filtered(lambda l: l.sale_line_id == self.sale_line_id)[:1]
        parts = ["<ul>"]
        if line:
            for src in line.source_ids:
                parts.append(
                    "<li>✓ %s — %s u. — %s</li>"
                    % (
                        src.label or "—",
                        src.quantity or 0.0,
                        src.amount or 0.0,
                    )
                )
        if len(parts) == 1:
            parts.append("<li>%s</li>" % _("Sin fuentes aplicadas todavía."))
        parts.append("</ul>")
        self.source_html = "".join(parts)

    def action_close(self):
        return self._return_hub()


class PurchaseSaleProductCostWizardPol(models.TransientModel):
    _name = "purchase.sale.product.cost.wizard.pol"
    _description = "POL pick (product cost modal)"

    wizard_id = fields.Many2one(
        "purchase.sale.product.cost.wizard", required=True, ondelete="cascade"
    )
    purchase_line_id = fields.Many2one("purchase.order.line", required=True)
    product_id = fields.Many2one("product.product")
    qty_purchased = fields.Float()
    qty_assigned = fields.Float(string="Ya relacionado")
    qty_available = fields.Float(string="Disponible")
    unit_cost = fields.Float()
    qty_to_use = fields.Float(string="Usar")
    is_focus_product = fields.Boolean()


class PurchaseSaleProductCostWizardBillLine(models.TransientModel):
    _name = "purchase.sale.product.cost.wizard.bill.line"
    _description = "Vendor bill line pick"

    wizard_id = fields.Many2one(
        "purchase.sale.product.cost.wizard", required=True, ondelete="cascade"
    )
    move_line_id = fields.Many2one("account.move.line", required=True)
    product_id = fields.Many2one("product.product")
    qty_on_bill = fields.Float(string="En factura")
    unit_cost = fields.Float()
    qty_to_use = fields.Float(string="Usar")
    is_focus_product = fields.Boolean()
