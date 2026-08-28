# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools.float_utils import float_compare


class JustechLinkExistingPoWizard(models.TransientModel):
    _name = "justech.link.existing.po.wizard"
    _description = "Relacionar compra existente a venta"

    sale_order_id = fields.Many2one(
        "sale.order",
        string="Orden de venta",
        required=True,
        readonly=True,
    )
    company_id = fields.Many2one(related="sale_order_id.company_id", readonly=True)
    document_type = fields.Selection(
        [
            ("purchase_order", "Orden de compra"),
            ("vendor_bill", "Factura de proveedor"),
        ],
        string="Tipo de documento",
        required=True,
        default="purchase_order",
    )
    partner_id = fields.Many2one(
        "res.partner",
        string="Proveedor (opcional)",
        domain="[('supplier_rank', '>', 0)]",
        check_company=True,
    )
    info_html = fields.Html(string="Información", sanitize=True)
    line_ids = fields.One2many(
        "justech.link.existing.po.wizard.line",
        "wizard_id",
        string="Líneas OC",
    )
    bill_line_ids = fields.One2many(
        "justech.link.existing.bill.wizard.line",
        "wizard_id",
        string="Líneas factura",
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        so = self.env["sale.order"].browse(
            self.env.context.get("default_sale_order_id")
            or self.env.context.get("active_id")
        )
        if so.exists() and so._name == "sale.order":
            res["sale_order_id"] = so.id
            doc_type = res.get("document_type") or "purchase_order"
            partner = self.env["res.partner"].browse(res.get("partner_id") or False)
            if doc_type == "vendor_bill":
                res["bill_line_ids"] = [
                    (0, 0, vals)
                    for vals in self._prepare_candidate_bill_lines_for(so, partner)
                ]
                res["line_ids"] = []
            else:
                res["line_ids"] = [
                    (0, 0, vals)
                    for vals in self._prepare_candidate_lines_for(so, partner)
                ]
                res["bill_line_ids"] = []
        return res

    @api.onchange("document_type", "partner_id", "sale_order_id")
    def _onchange_reload_candidates(self):
        self.line_ids = [(5, 0, 0)]
        self.bill_line_ids = [(5, 0, 0)]
        self.info_html = False
        if not self.sale_order_id:
            return
        if self.document_type == "vendor_bill":
            vals_list = self._prepare_candidate_bill_lines()
            self.bill_line_ids = [(0, 0, vals) for vals in vals_list]
            po_names = sorted(
                {
                    bl.source_po_name
                    for bl in self.bill_line_ids
                    if bl.source_po_name
                }
            )
            if po_names:
                self.info_html = (
                    "<div class='alert alert-info mb-0'>%s</div>"
                    % _(
                        "Algunas líneas provienen de OC existentes: %s. "
                        "Se reutilizará esa trazabilidad."
                    )
                    % ", ".join(po_names)
                )
        else:
            self.line_ids = [
                (0, 0, vals) for vals in self._prepare_candidate_lines()
            ]

    def action_load_candidates(self):
        self.ensure_one()
        self._onchange_reload_candidates()
        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }

    def _justech_po_state_label(self, state):
        labels = {
            "draft": _("Borrador"),
            "sent": _("Enviada"),
            "to approve": _("Por aprobar"),
            "purchase": _("Orden confirmada"),
            "done": _("Recibida / Completada"),
            "cancel": _("Cancelada"),
        }
        return labels.get(state, state or "")

    @api.model
    def _justech_bill_ncf_display(self, move):
        """Presentación NCF/e-CF sin dependencia dura de módulos fiscales."""
        for fname in (
            "fiscal_ncf_display",
            "justech_do_ncf",
            "l10n_latam_document_number",
            "l10n_do_origin_ncf",
        ):
            if fname in move._fields:
                val = move[fname]
                if val:
                    return val
        return move.ref or False

    def _justech_bill_state_label(self, move):
        if move.move_type == "in_refund":
            return _("Nota de crédito de proveedor")
        labels = {
            "draft": _("Borrador"),
            "posted": _("Publicada"),
            "cancel": _("Cancelada"),
        }
        return labels.get(move.state, move.state or "")

    def _score_candidate(self, pol, so, sol, avail, partner=None):
        reasons = [_("mismo producto"), _("misma compañía")]
        score = 20
        if so.name and (
            pol.order_id.origin == so.name or pol.order_id.partner_ref == so.name
        ):
            score += 30
            reasons.append(_("referencia / origin de la venta"))
        so_vendors = so.order_line.mapped("purchase_line_ids.order_id.partner_id")
        if pol.order_id.partner_id in so_vendors:
            score += 15
            reasons.append(_("proveedor ya usado en esta venta"))
        po_date = pol.order_id.date_order
        so_date = so.date_order
        if po_date and so_date:
            delta = abs((po_date - so_date).days)
            if delta <= 30:
                score += 10
                reasons.append(_("fecha cercana"))
        if pol.order_id.state in ("purchase", "done"):
            score += 5
            reasons.append(_("OC confirmada"))
        pending = sol.justech_qty_pending_purchase or 0.0
        if pending and float_compare(avail, pending, precision_digits=4) >= 0:
            score += 10
            reasons.append(_("cantidad disponible suficiente"))
        if partner and pol.order_id.partner_id == partner:
            score += 10
            reasons.append(_("proveedor filtrado"))
        if score >= 40:
            level = "alta"
        elif score >= 25:
            level = "media"
        else:
            level = "baja"
        return score, level, ", ".join(reasons)

    def _prepare_candidate_lines(self):
        self.ensure_one()
        return self._prepare_candidate_lines_for(self.sale_order_id, self.partner_id)

    @api.model
    def _prepare_candidate_lines_for(self, so, partner=None):
        if not so:
            return []
        products = so.order_line.filtered(lambda l: not l.display_type).mapped(
            "product_id"
        )
        if not products:
            return []
        domain = [
            ("company_id", "=", so.company_id.id),
            ("order_id.state", "!=", "cancel"),
            ("state", "!=", "cancel"),
            ("product_id", "in", products.ids),
            ("display_type", "=", False),
        ]
        if partner:
            domain.append(("order_id.partner_id", "=", partner.id))
        pols = self.env["purchase.order.line"].search(domain, limit=200)
        result = []
        for pol in pols:
            avail = pol._justech_qty_available_to_assign()
            if float_compare(avail, 0.0, precision_digits=4) <= 0:
                continue
            sol_candidates = so.order_line.filtered(
                lambda l: not l.display_type and l.product_id == pol.product_id
            )
            if not sol_candidates:
                continue
            sol = sol_candidates.sorted(
                key=lambda l: l.justech_qty_pending_purchase, reverse=True
            )[:1]
            pending = max(sol.justech_qty_pending_purchase or 0.0, 0.0)
            if float_compare(pending, 0.0, precision_digits=4) <= 0:
                continue
            score, level, reasons = self._score_candidate(
                pol, so, sol, avail, partner=partner
            )
            result.append(
                {
                    "purchase_line_id": pol.id,
                    "purchase_order_id": pol.order_id.id,
                    "partner_id": pol.order_id.partner_id.id,
                    "product_id": pol.product_id.id,
                    "qty_po": pol.product_qty,
                    "qty_assigned": pol.justech_qty_assigned_to_sales,
                    "qty_available": avail,
                    "qty_to_assign": min(avail, pending),
                    "sale_line_id": sol.id,
                    "selected": False,
                    "date_order": pol.order_id.date_order,
                    "po_state_label": self._justech_po_state_label(pol.order_id.state),
                    "match_score": score,
                    "match_level": level,
                    "match_reason": reasons,
                    "snapshot_pending": pending,
                    "snapshot_available": avail,
                }
            )
        result.sort(key=lambda r: r.get("match_score", 0), reverse=True)
        return result

    def _prepare_candidate_bill_lines(self):
        self.ensure_one()
        return self._prepare_candidate_bill_lines_for(
            self.sale_order_id, self.partner_id
        )

    @api.model
    def _prepare_candidate_bill_lines_for(self, so, partner=None):
        if not so:
            return []
        products = so.order_line.filtered(lambda l: not l.display_type).mapped(
            "product_id"
        )
        if not products:
            return []
        domain = self.env["account.move.line"]._justech_vendor_bill_line_domain(
            so.company_id, products, partner=partner
        )
        amls = self.env["account.move.line"].search(domain, limit=200)
        result = []
        for aml in amls:
            move = aml.move_id
            if move.move_type not in ("in_invoice", "in_refund"):
                continue
            sol_candidates = so.order_line.filtered(
                lambda l: not l.display_type and l.product_id == aml.product_id
            )
            if not sol_candidates:
                continue
            sol = sol_candidates.sorted(
                key=lambda l: l.justech_qty_pending_purchase, reverse=True
            )[:1]
            pending = max(sol.justech_qty_pending_purchase or 0.0, 0.0)
            # NC no requiere pendiente positivo de compra; reduce costo.
            if move.move_type == "in_invoice" and float_compare(
                pending, 0.0, precision_digits=4
            ) <= 0:
                continue
            avail_qty = aml._justech_bill_qty_available()
            if float_compare(avail_qty, 0.0, precision_digits=4) <= 0:
                continue
            avail_amt = aml._justech_bill_amount_available()
            qty_suggest = (
                min(avail_qty, pending)
                if move.move_type == "in_invoice"
                else min(avail_qty, sol.justech_qty_purchased or avail_qty)
            )
            bill_qty = aml._justech_bill_qty_signed()
            unit_amt = (
                (aml._justech_bill_amount_signed() / bill_qty) if bill_qty else 0.0
            )
            source_po = aml.purchase_line_id.order_id if aml.purchase_line_id else False
            note = False
            if source_po:
                note = _("Esta factura proviene de la OC %s.") % source_po.name
            result.append(
                {
                    "vendor_bill_line_id": aml.id,
                    "vendor_bill_id": move.id,
                    "purchase_line_id": aml.purchase_line_id.id,
                    "purchase_order_id": source_po.id if source_po else False,
                    "partner_id": move.partner_id.id,
                    "product_id": aml.product_id.id,
                    "description": aml.name or aml.product_id.display_name,
                    "sale_line_id": sol.id,
                    "qty_bill": bill_qty,
                    "qty_assigned": aml._justech_bill_qty_assigned(),
                    "qty_available": avail_qty,
                    "qty_to_assign": qty_suggest,
                    "amount_bill": aml._justech_bill_amount_signed(),
                    "amount_assigned": aml._justech_bill_amount_assigned(),
                    "amount_available": avail_amt,
                    "amount_to_assign": min(avail_amt, unit_amt * qty_suggest)
                    if qty_suggest
                    else 0.0,
                    "currency_id": move.currency_id.id,
                    "selected": False,
                    "bill_state_label": self._justech_bill_state_label(move),
                    "source_po_name": source_po.name if source_po else False,
                    "ncf_display": self._justech_bill_ncf_display(move),
                    "info_note": note,
                    "snapshot_pending": pending,
                    "snapshot_available": avail_qty,
                    "snapshot_amount_available": avail_amt,
                }
            )
        return result

    def action_confirm_link(self):
        self.ensure_one()
        if self.document_type == "vendor_bill":
            return self._action_confirm_bill_link()
        return self._action_confirm_po_link()

    def _action_confirm_po_link(self):
        selected = self.line_ids.filtered(
            lambda l: l.selected
            and l.sale_line_id
            and l.purchase_line_id
            and float_compare(l.qty_to_assign, 0.0, precision_digits=4) > 0
        )
        if not selected:
            raise UserError(_("Seleccione líneas y cantidades a asignar."))

        sale_lines = selected.mapped("sale_line_id")
        sale_lines._justech_lock_for_purchase()
        fresh = sale_lines.justech_get_pending_snapshot()
        used = {}

        for wline in selected:
            pol = wline.purchase_line_id
            sol = wline.sale_line_id
            if pol.company_id != sol.company_id:
                raise UserError(_("No se permite relacionar OC de otra compañía."))
            if pol.order_id.state == "cancel":
                raise UserError(_("No se puede relacionar una OC cancelada."))
            current_pending = fresh.get(sol.id, 0.0) - used.get(sol.id, 0.0)
            current_avail = pol._justech_qty_available_to_assign()
            if float_compare(
                wline.snapshot_available or 0.0, current_avail, precision_digits=4
            ) != 0 or float_compare(
                wline.snapshot_pending or 0.0, fresh.get(sol.id, 0.0), precision_digits=4
            ) != 0:
                raise UserError(
                    _(
                        "Las cantidades disponibles cambiaron. "
                        "Actualice y revise nuevamente."
                    )
                )
            if float_compare(wline.qty_to_assign, current_pending, precision_digits=4) > 0:
                raise UserError(
                    _(
                        "No puede relacionar %(qty)s unidades de %(product)s. "
                        "Solo quedan %(pending)s unidades pendientes de cubrir "
                        "para esta venta."
                    )
                    % {
                        "qty": wline.qty_to_assign,
                        "product": sol.product_id.display_name,
                        "pending": max(current_pending, 0.0),
                    }
                )
            if float_compare(wline.qty_to_assign, current_avail, precision_digits=4) > 0:
                raise UserError(
                    _(
                        "No puede relacionar %(qty)s unidades de %(product)s. "
                        "Solo quedan %(pending)s unidades disponibles en la OC."
                    )
                    % {
                        "qty": wline.qty_to_assign,
                        "product": sol.product_id.display_name,
                        "pending": current_avail,
                    }
                )
            used[sol.id] = used.get(sol.id, 0.0) + wline.qty_to_assign
            pol.justech_link_to_sale_line(sol, wline.qty_to_assign)

        self.sale_order_id.message_post(
            body=_("OC relacionadas a la venta: %s")
            % ", ".join(selected.mapped("purchase_order_id.name"))
        )
        return {"type": "ir.actions.act_window_close"}

    def _action_confirm_bill_link(self):
        selected = self.bill_line_ids.filtered(
            lambda l: l.selected
            and l.sale_line_id
            and l.vendor_bill_line_id
            and float_compare(l.qty_to_assign, 0.0, precision_digits=4) > 0
        )
        if not selected:
            raise UserError(_("Seleccione líneas y cantidades a asignar."))

        sale_lines = selected.mapped("sale_line_id")
        sale_lines._justech_lock_for_purchase()
        fresh = sale_lines.justech_get_pending_snapshot()
        used_qty = {}
        used_amt = {}
        linked_docs = set()

        for wline in selected:
            aml = wline.vendor_bill_line_id
            sol = wline.sale_line_id
            move = aml.move_id
            if move.company_id != sol.company_id:
                raise UserError(
                    _("No se permite relacionar una factura proveedor de otra compañía.")
                )
            if move.state == "cancel":
                raise UserError(
                    _("No se puede relacionar una factura proveedor cancelada.")
                )
            if move.move_type not in ("in_invoice", "in_refund"):
                raise UserError(_("Documento de proveedor no válido."))

            current_avail = aml._justech_bill_qty_available()
            current_amt = aml._justech_bill_amount_available()
            if float_compare(
                wline.snapshot_available or 0.0, current_avail, precision_digits=4
            ) != 0 or float_compare(
                wline.snapshot_amount_available or 0.0,
                current_amt,
                precision_digits=4,
            ) != 0:
                raise UserError(
                    _(
                        "Las cantidades disponibles cambiaron. "
                        "Actualice y revise nuevamente."
                    )
                )

            # Factura con OC: reutilizar trazabilidad POL, sin relación paralela.
            if aml.purchase_line_id:
                pol = aml.purchase_line_id
                current_pending = fresh.get(sol.id, 0.0) - used_qty.get(sol.id, 0.0)
                if move.move_type == "in_invoice" and float_compare(
                    wline.qty_to_assign, current_pending, precision_digits=4
                ) > 0:
                    raise UserError(
                        _(
                            "Solo quedan %(pending)s unidades pendientes de cubrir "
                            "para esta venta."
                        )
                        % {"pending": max(current_pending, 0.0)}
                    )
                pol.justech_link_to_sale_line(sol, wline.qty_to_assign)
                used_qty[sol.id] = used_qty.get(sol.id, 0.0) + wline.qty_to_assign
                linked_docs.add(
                    move.name
                    or move.display_name
                    or (_("Factura borrador #%s") % move.id)
                )
                continue

            # Factura directa sin OC.
            current_pending = fresh.get(sol.id, 0.0) - used_qty.get(sol.id, 0.0)
            if move.move_type == "in_invoice":
                if float_compare(
                    wline.qty_to_assign, current_pending, precision_digits=4
                ) > 0:
                    raise UserError(
                        _(
                            "Solo quedan %(pending)s unidades pendientes de cubrir "
                            "para esta venta."
                        )
                        % {"pending": max(current_pending, 0.0)}
                    )
            if float_compare(wline.qty_to_assign, current_avail, precision_digits=4) > 0:
                raise UserError(
                    _(
                        "No puede relacionar %(qty)s unidades de %(product)s. "
                        "Solo quedan %(pending)s unidades disponibles en la factura."
                    )
                    % {
                        "qty": wline.qty_to_assign,
                        "product": sol.product_id.display_name,
                        "pending": current_avail,
                    }
                )
            amount = wline.amount_to_assign or 0.0
            if float_compare(amount, 0.0, precision_digits=4) <= 0:
                bill_qty = aml._justech_bill_qty_signed()
                amount = (
                    aml._justech_bill_amount_signed() * (wline.qty_to_assign / bill_qty)
                    if bill_qty
                    else 0.0
                )
            amt_left = current_amt - used_amt.get(aml.id, 0.0)
            if float_compare(amount, amt_left, precision_digits=4) > 0:
                raise UserError(
                    _(
                        "No puede asignar el monto %(amt)s de %(product)s. "
                        "Solo queda %(avail)s disponible en la factura."
                    )
                    % {
                        "amt": amount,
                        "product": sol.product_id.display_name,
                        "avail": amt_left,
                    }
                )
            self.env["justech.purchase.sale.qty.assignment"].create(
                {
                    "company_id": sol.company_id.id,
                    "vendor_bill_line_id": aml.id,
                    "sale_line_id": sol.id,
                    "quantity": wline.qty_to_assign,
                    "amount": amount,
                    "state": "active",
                    "note": _(
                        "Relación comercial factura proveedor sin alterar contabilidad"
                    ),
                }
            )
            used_qty[sol.id] = used_qty.get(sol.id, 0.0) + wline.qty_to_assign
            used_amt[aml.id] = used_amt.get(aml.id, 0.0) + amount
            # Draft moves often have name=False until posted (Odoo 19).
            linked_docs.add(
                move.name
                or move.display_name
                or (_("Factura borrador #%s") % move.id)
            )

        self.sale_order_id.message_post(
            body=_("Facturas proveedor relacionadas a la venta: %s")
            % ", ".join(sorted(linked_docs))
        )
        return {"type": "ir.actions.act_window_close"}


class JustechLinkExistingPoWizardLine(models.TransientModel):
    _name = "justech.link.existing.po.wizard.line"
    _description = "Línea relacionar OC"

    wizard_id = fields.Many2one(
        "justech.link.existing.po.wizard", required=True, ondelete="cascade"
    )
    selected = fields.Boolean(string="Seleccionar", default=False)
    purchase_line_id = fields.Many2one("purchase.order.line", readonly=True)
    purchase_order_id = fields.Many2one("purchase.order", string="OC", readonly=True)
    partner_id = fields.Many2one("res.partner", string="Proveedor", readonly=True)
    product_id = fields.Many2one("product.product", string="Producto", readonly=True)
    sale_line_id = fields.Many2one(
        "sale.order.line",
        string="Línea venta",
        readonly=True,
    )
    qty_po = fields.Float(string="Cant OC", readonly=True)
    qty_assigned = fields.Float(string="Ya relacionada", readonly=True)
    qty_available = fields.Float(string="Disponible para relacionar", readonly=True)
    qty_to_assign = fields.Float(string="Cantidad a relacionar")
    date_order = fields.Datetime(string="Fecha", readonly=True)
    po_state_label = fields.Char(string="Estado", readonly=True)
    match_score = fields.Integer(string="Puntaje", readonly=True)
    match_level = fields.Selection(
        [("alta", "Alta"), ("media", "Media"), ("baja", "Baja")],
        string="Coincidencia",
        readonly=True,
    )
    match_reason = fields.Char(string="Razón", readonly=True)
    snapshot_pending = fields.Float(readonly=True)
    snapshot_available = fields.Float(readonly=True)


class JustechLinkExistingBillWizardLine(models.TransientModel):
    _name = "justech.link.existing.bill.wizard.line"
    _description = "Línea relacionar factura proveedor"

    wizard_id = fields.Many2one(
        "justech.link.existing.po.wizard", required=True, ondelete="cascade"
    )
    selected = fields.Boolean(string="Seleccionar", default=False)
    vendor_bill_line_id = fields.Many2one("account.move.line", readonly=True)
    vendor_bill_id = fields.Many2one("account.move", string="Factura", readonly=True)
    purchase_line_id = fields.Many2one("purchase.order.line", readonly=True)
    purchase_order_id = fields.Many2one("purchase.order", string="OC origen", readonly=True)
    partner_id = fields.Many2one("res.partner", string="Proveedor", readonly=True)
    product_id = fields.Many2one("product.product", string="Producto", readonly=True)
    description = fields.Char(string="Descripción", readonly=True)
    sale_line_id = fields.Many2one("sale.order.line", string="Línea de venta")
    qty_bill = fields.Float(string="Cantidad factura", readonly=True)
    qty_assigned = fields.Float(string="Cantidad ya relacionada", readonly=True)
    qty_available = fields.Float(string="Cantidad disponible", readonly=True)
    qty_to_assign = fields.Float(string="Cantidad a relacionar")
    amount_bill = fields.Monetary(string="Subtotal", currency_field="currency_id", readonly=True)
    amount_assigned = fields.Monetary(
        string="Monto ya asignado", currency_field="currency_id", readonly=True
    )
    amount_available = fields.Monetary(
        string="Monto disponible", currency_field="currency_id", readonly=True
    )
    amount_to_assign = fields.Monetary(
        string="Monto a relacionar", currency_field="currency_id"
    )
    currency_id = fields.Many2one("res.currency", readonly=True)
    bill_state_label = fields.Char(string="Tipo / Estado", readonly=True)
    source_po_name = fields.Char(string="OC origen", readonly=True)
    ncf_display = fields.Char(string="NCF/e-CF", readonly=True)
    info_note = fields.Char(string="Nota", readonly=True)
    snapshot_pending = fields.Float(readonly=True)
    snapshot_available = fields.Float(readonly=True)
    snapshot_amount_available = fields.Float(readonly=True)

    @api.onchange("qty_to_assign", "vendor_bill_line_id")
    def _onchange_qty_to_assign_amount(self):
        for line in self:
            if not line.vendor_bill_line_id or not line.qty_to_assign:
                continue
            bill_qty = line.vendor_bill_line_id._justech_bill_qty_signed()
            if bill_qty:
                unit = line.vendor_bill_line_id._justech_bill_amount_signed() / bill_qty
                line.amount_to_assign = unit * line.qty_to_assign
