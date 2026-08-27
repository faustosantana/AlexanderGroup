# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools.float_utils import float_compare, float_round


COVERAGE_STATES = [
    ("pending_purchase", "Pendiente de comprar"),
    ("covered_stock", "Cubierta por inventario"),
    ("partial_purchase", "Compra parcial"),
    ("full_purchase", "Compra completa — pendiente de recepción"),
    ("po_cancelled", "OC cancelada"),
    ("pending_receipt", "Recepción parcial"),
    ("received", "Recibida"),
    ("vendor_invoiced", "Facturada proveedor"),
    ("vendor_partial", "Parcialmente facturada"),
]

SUPPLY_STATES = [
    ("unsupplied", "Sin abastecer"),
    ("covered_stock", "Cubierta por inventario"),
    ("pending_purchase", "Compra pendiente"),
    ("partial_purchase", "Compra parcial"),
    ("purchased", "Compra completa — pendiente de recepción"),
    ("partial_receipt", "Recepción parcial"),
    ("received", "Recibida"),
    ("ready_to_deliver", "Disponible para entregar"),
    ("partial_delivery", "Entrega parcial"),
    ("delivered", "Entregada"),
    ("incident", "Incidencia"),
]


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    justech_qty_sold = fields.Float(
        string="Vendido",
        compute="_compute_justech_purchase_coverage",
        digits="Product Unit of Measure",
    )
    justech_qty_stock_covered = fields.Float(
        string="Cubierto inventario",
        compute="_compute_justech_purchase_coverage",
        digits="Product Unit of Measure",
    )
    justech_qty_purchased = fields.Float(
        string="Ya comprado",
        compute="_compute_justech_purchase_coverage",
        digits="Product Unit of Measure",
    )
    justech_qty_pending_purchase = fields.Float(
        string="Pendiente comprar",
        compute="_compute_justech_purchase_coverage",
        digits="Product Unit of Measure",
    )
    justech_coverage_state = fields.Selection(
        COVERAGE_STATES,
        string="Estado cobertura",
        compute="_compute_justech_purchase_coverage",
    )
    justech_qty_assignment_ids = fields.One2many(
        "justech.purchase.sale.qty.assignment",
        "sale_line_id",
        string="Asignaciones OC",
    )
    justech_qty_received = fields.Float(
        string="Recibida de proveedores",
        compute="_compute_justech_purchase_coverage",
        digits="Product Unit of Measure",
    )
    justech_qty_pending_receive = fields.Float(
        string="Pendiente de recibir",
        compute="_compute_justech_purchase_coverage",
        digits="Product Unit of Measure",
    )
    justech_qty_delivered_cust = fields.Float(
        string="Entregada al cliente",
        compute="_compute_justech_purchase_coverage",
        digits="Product Unit of Measure",
    )
    justech_qty_pending_deliver = fields.Float(
        string="Pendiente de entregar",
        compute="_compute_justech_purchase_coverage",
        digits="Product Unit of Measure",
    )
    justech_qty_physical = fields.Float(
        string="Disponible físicamente",
        compute="_compute_justech_purchase_coverage",
        digits="Product Unit of Measure",
    )
    justech_qty_commercial = fields.Float(
        string="Cobertura comercial",
        compute="_compute_justech_purchase_coverage",
        digits="Product Unit of Measure",
    )
    justech_supply_state = fields.Selection(
        SUPPLY_STATES,
        string="Estado abastecimiento",
        compute="_compute_justech_purchase_coverage",
    )
    justech_vendor_supply_html = fields.Html(
        string="Detalle por proveedor",
        compute="_compute_justech_purchase_coverage",
        sanitize=False,
    )
    justech_purchase_ref = fields.Char(
        string="OC / Proveedor",
        compute="_compute_justech_purchase_coverage",
    )
    justech_vendor_bill_ref = fields.Char(
        string="Factura proveedor",
        compute="_compute_justech_purchase_coverage",
    )
    justech_trace_cost = fields.Monetary(
        string="Costo comercial",
        compute="_compute_justech_purchase_coverage",
        currency_field="currency_id",
    )
    justech_cost_origin = fields.Char(
        string="Origen costo",
        compute="_compute_justech_purchase_coverage",
    )

    def _justech_is_purchase_relevant(self):
        self.ensure_one()
        if self.display_type:
            return False
        product = self.product_id
        if not product:
            return False
        # Odoo 19: storable via is_storable; also allow purchaseable services
        if getattr(product, "is_storable", False):
            return True
        if product.type == "consu":
            return True
        if product.type == "service" and getattr(product, "service_to_purchase", False):
            return True
        # Non-storable goods that are purchased for the sale
        if product.purchase_ok:
            return True
        return False

    def _justech_active_purchase_lines(self):
        """POL linked by sale_line_id, excluding cancelled."""
        self.ensure_one()
        return self.purchase_line_ids.filtered(
            lambda l: l.state != "cancel" and l.order_id.state != "cancel"
        )

    def _justech_assignment_qty(self):
        self.ensure_one()
        assigns = self.justech_qty_assignment_ids.filtered(lambda a: a.state == "active")
        # Avoid double-count when same POL also has sale_line_id = this SOL
        total = 0.0
        for a in assigns:
            if a.purchase_line_id:
                if (
                    a.purchase_line_id.state == "cancel"
                    or a.purchase_order_id.state == "cancel"
                ):
                    continue
                if a.purchase_line_id.sale_line_id == self:
                    continue
                total += a.quantity
                continue
            # Factura proveedor directa (sin OC): solo facturas (no NC) cubren qty.
            bill = a.vendor_bill_id
            if not bill or bill.state == "cancel":
                continue
            if bill.move_type == "in_invoice":
                total += a.quantity
        return total

    def _justech_bill_only_cost(self):
        """Costo comercial de assignments de factura sin POL (NC reduce)."""
        self.ensure_one()
        cost = 0.0
        company = self.company_id
        for a in self.justech_qty_assignment_ids.filtered(
            lambda x: x.state == "active" and x.vendor_bill_line_id and not x.purchase_line_id
        ):
            bill = a.vendor_bill_id
            if not bill or bill.state == "cancel":
                continue
            amount = a.amount or 0.0
            if not amount and a.quantity and a.vendor_bill_line_id:
                bill_qty = a.vendor_bill_line_id._justech_bill_qty_signed()
                if bill_qty:
                    amount = (
                        a.vendor_bill_line_id._justech_bill_amount_signed()
                        * (a.quantity / bill_qty)
                    )
            cur = a.currency_id or bill.currency_id
            if cur and self.currency_id and cur != self.currency_id:
                amount = cur._convert(
                    amount,
                    self.currency_id,
                    company,
                    bill.invoice_date or fields.Date.context_today(self),
                )
            if bill.move_type == "in_refund":
                cost -= amount
            else:
                cost += amount
        return cost

    def _justech_compute_purchased_qty(self):
        self.ensure_one()
        pols = self._justech_active_purchase_lines()
        qty = sum(pols.mapped("product_qty"))
        qty += self._justech_assignment_qty()
        return float_round(qty, precision_digits=4)

    def _justech_linked_pols_including_cancelled(self):
        self.ensure_one()
        pols = self.purchase_line_ids
        assigns = self.justech_qty_assignment_ids
        return pols | assigns.mapped("purchase_line_id")

    def _justech_received_qty(self, active_only=False):
        """Received from linked POLs (active, and cancelled with real receipts)."""
        self.ensure_one()
        total = 0.0
        seen = set()
        for pol in self._justech_linked_pols_including_cancelled():
            if pol.id in seen:
                continue
            seen.add(pol.id)
            cancelled = pol.state == "cancel" or pol.order_id.state == "cancel"
            if active_only and cancelled:
                continue
            recv = pol.qty_received or 0.0
            if pol.sale_line_id == self:
                total += recv
                continue
            assigns = pol.justech_qty_assignment_ids.filtered(
                lambda a: a.sale_line_id == self and a.state == "active"
            )
            if assigns and pol.product_qty:
                share = sum(assigns.mapped("quantity")) / pol.product_qty
                total += recv * share
            elif cancelled and recv and not active_only:
                total += recv
        return float_round(total, precision_digits=4)

    def _justech_reserved_stock_qty(self):
        """Qty actually reserved or delivered from stock for this SOL.

        Odoo 19 stock.move:
        - product_uom_qty = planned outgoing demand (never coverage)
        - quantity = reserved (assigned / partially_available) or done
        - move_line_ids.quantity = reservation on quants (empty if unassigned)

        Do not treat demand as inventory coverage.
        """
        self.ensure_one()
        reserved = 0.0
        linked_po_moves = self._justech_active_purchase_lines().mapped("move_ids")
        for move in self.move_ids.filtered(lambda m: m.state not in ("cancel",)):
            # Skip inbound purchase moves linked to assigned POL
            if move in linked_po_moves:
                continue
            dest = move.location_dest_id
            src = move.location_id
            actual = move.quantity or 0.0
            if dest.usage == "customer" or (
                move.picking_id
                and move.picking_id.picking_type_id.code == "outgoing"
            ):
                uom_qty = move.product_uom._compute_quantity(
                    actual,
                    self.product_uom_id,
                )
                reserved += abs(uom_qty or 0.0)
            elif src.usage == "customer":
                uom_qty = move.product_uom._compute_quantity(
                    actual,
                    self.product_uom_id,
                )
                reserved -= abs(uom_qty or 0.0)
        return max(reserved, 0.0)

    def _justech_free_stock_usable(self):
        """Usable free stock today — never raw qty_available alone."""
        self.ensure_one()
        product = self.product_id
        if not product or not getattr(product, "is_storable", False):
            if product and product.type != "consu":
                return 0.0
        free = getattr(self, "free_qty_today", None)
        if free is None:
            # Fallback: product free_qty in warehouse context
            wh = self.order_id.warehouse_id
            product = product.with_context(
                warehouse_id=wh.id if wh else False,
                location=wh.lot_stock_id.id if wh and wh.lot_stock_id else False,
            )
            free = getattr(product, "free_qty", 0.0) or 0.0
        return max(free or 0.0, 0.0)

    def _justech_compute_stock_covered(self, sold, purchased):
        self.ensure_one()
        remaining = max(sold - purchased, 0.0)
        if remaining <= 0:
            return 0.0
        if not self._justech_is_purchase_relevant():
            return 0.0
        product = self.product_id
        if product.type == "service":
            return 0.0
        free = self._justech_free_stock_usable()
        reserved = self._justech_reserved_stock_qty()
        # Prefer free_qty_today; reserved for this line may already be reflected —
        # take the max signal without double-adding free+reserved when free already
        # excludes others' reservations.
        candidate = max(free, reserved) if reserved else free
        if reserved and free:
            # If free is global free and reserved is ours, sum carefully:
            # reserved units are already committed to us; free can cover more.
            candidate = reserved + free
        return min(remaining, max(candidate, 0.0))

    def _justech_coverage_state_value(self, sold, stock, purchased, pending, received=0.0):
        self.ensure_one()
        pols = self._justech_active_purchase_lines()
        cancelled_pols = self.purchase_line_ids.filtered(
            lambda l: l.state == "cancel" or l.order_id.state == "cancel"
        )
        if float_compare(pending, 0.0, precision_digits=4) > 0:
            if float_compare(purchased, 0.0, precision_digits=4) > 0:
                return "partial_purchase"
            if float_compare(stock, 0.0, precision_digits=4) > 0 and float_compare(
                stock, sold, precision_digits=4
            ) >= 0:
                return "covered_stock"
            if float_compare(stock, 0.0, precision_digits=4) > 0:
                return "partial_purchase"
            return "pending_purchase"
        if float_compare(purchased, 0.0, precision_digits=4) <= 0:
            if float_compare(stock, 0.0, precision_digits=4) > 0:
                return "covered_stock"
            if cancelled_pols and not pols:
                return "po_cancelled"
            return "pending_purchase"
        if pols:
            recv = received or sum(pols.mapped("qty_received"))
            inv = sum(pols.mapped("qty_invoiced"))
            ordered = sum(pols.mapped("product_qty")) or purchased
            if float_compare(inv, ordered, precision_digits=4) >= 0 and inv > 0:
                return "vendor_invoiced"
            if float_compare(inv, 0.0, precision_digits=4) > 0:
                return "vendor_partial"
            if float_compare(recv, ordered, precision_digits=4) >= 0 and recv > 0:
                return "received"
            if float_compare(recv, 0.0, precision_digits=4) > 0:
                return "pending_receipt"
            return "full_purchase"
        return "covered_stock"

    def _justech_supply_state_value(
        self, sold, stock, purchased, pending, received, pending_recv, delivered, pending_del, physical
    ):
        self.ensure_one()
        if float_compare(sold, 0.0, precision_digits=4) <= 0:
            return False
        if float_compare(delivered, sold, precision_digits=4) >= 0 and delivered > 0:
            return "delivered"
        if float_compare(delivered, 0.0, precision_digits=4) > 0:
            return "partial_delivery"
        if float_compare(pending, 0.0, precision_digits=4) > 0:
            if float_compare(purchased, 0.0, precision_digits=4) > 0:
                return "partial_purchase"
            if float_compare(stock, sold, precision_digits=4) >= 0:
                return "covered_stock"
            if float_compare(stock, 0.0, precision_digits=4) > 0:
                return "partial_purchase"
            return "pending_purchase" if purchased or stock else "unsupplied"
        # commercially covered
        if float_compare(purchased, 0.0, precision_digits=4) <= 0:
            if float_compare(physical, sold, precision_digits=4) >= 0:
                return "ready_to_deliver"
            return "covered_stock"
        if float_compare(pending_recv, 0.0, precision_digits=4) > 0:
            if float_compare(received, 0.0, precision_digits=4) > 0:
                return "partial_receipt"
            return "purchased"
        if float_compare(physical, sold, precision_digits=4) >= 0:
            return "ready_to_deliver"
        return "received"

    def _justech_vendor_supply_html(self, stock):
        self.ensure_one()
        rows = []
        seen = set()
        for pol in self._justech_linked_pols_including_cancelled():
            if pol.id in seen:
                continue
            seen.add(pol.id)
            qty = pol.product_qty or 0.0
            recv = pol.qty_received or 0.0
            if pol.sale_line_id != self:
                assigns = pol.justech_qty_assignment_ids.filtered(
                    lambda a: a.sale_line_id == self and a.state == "active"
                )
                if not assigns and pol.state == "cancel":
                    qty = recv
                elif assigns:
                    qty = sum(assigns.mapped("quantity"))
                    if pol.product_qty:
                        recv = recv * (qty / pol.product_qty)
            state_po = pol.order_id.state
            if state_po == "cancel":
                estado = "Cancelada"
            elif state_po == "draft":
                estado = "Borrador"
            elif state_po in ("purchase", "done"):
                estado = "Confirmada"
            else:
                estado = "En proceso"
            bills = pol.invoice_lines.mapped("move_id").filtered(
                lambda m: m.move_type == "in_invoice" and m.state != "cancel"
            )
            bill_names = [
                n for n in bills.mapped("name") if n
            ] or bills.mapped("display_name")
            bill_txt = ", ".join(bill_names) if bill_names else "—"
            pending_r = max(qty - recv, 0.0) if estado != "Cancelada" else 0.0
            rows.append(
                "<tr><td>%s</td><td>%s</td><td>%.2f</td><td>%.2f</td><td>%.2f</td><td>%s</td><td>%s</td></tr>"
                % (
                    pol.order_id.partner_id.display_name or "",
                    pol.order_id.name or "",
                    qty,
                    recv,
                    pending_r,
                    estado,
                    bill_txt,
                )
            )
        body = (
            "<table class='table table-sm'><thead><tr>"
            "<th>Proveedor</th><th>OC</th><th>Cantidad</th><th>Recibida</th>"
            "<th>Pendiente</th><th>Estado</th><th>Factura proveedor</th>"
            "</tr></thead><tbody>%s</tbody></table>" % ("".join(rows) if rows else "")
        )
        if not rows:
            body = "<p>Sin órdenes de compra vinculadas. Inventario: %.2f</p>" % (stock or 0.0)
        return body

    @api.depends(
        "product_uom_qty",
        "product_id",
        "purchase_line_ids",
        "purchase_line_ids.product_qty",
        "purchase_line_ids.state",
        "purchase_line_ids.order_id.state",
        "purchase_line_ids.qty_received",
        "purchase_line_ids.qty_invoiced",
        "purchase_line_ids.price_unit",
        "purchase_line_ids.invoice_lines",
        "purchase_line_ids.invoice_lines.move_id.state",
        "purchase_line_ids.invoice_lines.move_id.name",
        "justech_qty_assignment_ids",
        "justech_qty_assignment_ids.quantity",
        "justech_qty_assignment_ids.amount",
        "justech_qty_assignment_ids.state",
        "justech_qty_assignment_ids.vendor_bill_line_id",
        "justech_qty_assignment_ids.vendor_bill_id",
        "justech_qty_assignment_ids.purchase_line_id",
        "move_ids",
        "move_ids.state",
        "move_ids.quantity",
        "qty_delivered",
        "free_qty_today",
        "display_type",
    )
    def _compute_justech_purchase_coverage(self):
        for line in self:
            if line.display_type or not line.product_id:
                line.justech_qty_sold = 0.0
                line.justech_qty_stock_covered = 0.0
                line.justech_qty_purchased = 0.0
                line.justech_qty_pending_purchase = 0.0
                line.justech_coverage_state = False
                line.justech_qty_received = 0.0
                line.justech_qty_pending_receive = 0.0
                line.justech_qty_delivered_cust = 0.0
                line.justech_qty_pending_deliver = 0.0
                line.justech_qty_physical = 0.0
                line.justech_qty_commercial = 0.0
                line.justech_supply_state = False
                line.justech_vendor_supply_html = False
                line.justech_purchase_ref = False
                line.justech_vendor_bill_ref = False
                line.justech_trace_cost = 0.0
                line.justech_cost_origin = False
                continue
            sold = line.product_uom_qty or 0.0
            purchased = line._justech_compute_purchased_qty()
            stock = line._justech_compute_stock_covered(sold, purchased)
            pending = max(sold - stock - purchased, 0.0)
            received_active = line._justech_received_qty(active_only=True)
            received = line._justech_received_qty(active_only=False)
            pending_recv = max(purchased - received_active, 0.0)
            delivered = line.qty_delivered or 0.0
            pending_del = max(sold - delivered, 0.0)
            commercial = min(sold, stock + purchased)
            # Active receipts are extra to stock_covered (capped by remaining after purchase).
            # After cancel, received goods sit in warehouse and are already in stock_covered.
            physical = min(sold, stock + received_active)
            line.justech_qty_sold = sold
            line.justech_qty_stock_covered = stock
            line.justech_qty_purchased = purchased
            line.justech_qty_pending_purchase = pending
            line.justech_qty_received = received
            line.justech_qty_pending_receive = pending_recv
            line.justech_qty_delivered_cust = delivered
            line.justech_qty_pending_deliver = pending_del
            line.justech_qty_commercial = commercial
            line.justech_qty_physical = physical
            line.justech_coverage_state = line._justech_coverage_state_value(
                sold, stock, purchased, pending, received
            )
            line.justech_supply_state = line._justech_supply_state_value(
                sold,
                stock,
                purchased,
                pending,
                received,
                pending_recv,
                delivered,
                pending_del,
                physical,
            )
            line.justech_vendor_supply_html = line._justech_vendor_supply_html(stock)
            refs = []
            bills = []
            purchase_cost = 0.0
            origins = []
            company = line.company_id
            for pol in line._justech_active_purchase_lines():
                refs.append(
                    "%s (%s)"
                    % (pol.order_id.name, pol.order_id.partner_id.display_name)
                )
                pol_bills = pol.invoice_lines.mapped("move_id").filtered(
                    lambda m: m.move_type == "in_invoice" and m.state != "cancel"
                )
                bills.extend(
                    n
                    for n in (
                        pol_bills.mapped("name") or pol_bills.mapped("display_name")
                    )
                    if n
                )
                qty = pol.product_qty or 0.0
                if qty:
                    share = qty
                    if pol.sale_line_id != line:
                        assigns = pol.justech_qty_assignment_ids.filtered(
                            lambda a: a.sale_line_id == line and a.state == "active"
                        )
                        share = sum(assigns.mapped("quantity")) if assigns else 0.0
                    unit = pol.price_unit or 0.0
                    amount = unit * share
                    po_cur = pol.order_id.currency_id
                    if po_cur and line.currency_id and po_cur != line.currency_id:
                        amount = po_cur._convert(
                            amount,
                            line.currency_id,
                            company,
                            pol.order_id.date_order or fields.Date.context_today(line),
                        )
                    purchase_cost += amount
            if stock:
                origins.append("Inventario")
                purchase_cost += (line.product_id.standard_price or 0.0) * stock
            if refs:
                origins.append("Compra")
            bill_only_cost = line._justech_bill_only_cost()
            if bill_only_cost:
                purchase_cost += bill_only_cost
                origins.append("Factura proveedor")
            # Referencias de factura desde assignments directos
            for a in line.justech_qty_assignment_ids.filtered(
                lambda x: x.state == "active" and x.vendor_bill_id and not x.purchase_line_id
            ):
                if a.vendor_bill_id.state != "cancel":
                    bill_name = (
                        a.vendor_bill_id.name
                        or a.vendor_bill_id.display_name
                        or False
                    )
                    if bill_name:
                        bills.append(bill_name)
            line.justech_purchase_ref = ", ".join(refs) if refs else False
            line.justech_vendor_bill_ref = ", ".join(dict.fromkeys(bills)) if bills else False
            line.justech_trace_cost = purchase_cost
            line.justech_cost_origin = " + ".join(dict.fromkeys(origins)) if origins else False

    @api.constrains("product_uom_qty")
    def _justech_check_qty_not_below_purchased(self):
        """Block reducing sold qty below committed purchase / assignment qty."""
        for line in self:
            if line.display_type or not line.product_id:
                continue
            purchased = line._justech_compute_purchased_qty()
            sold = line.product_uom_qty or 0.0
            if float_compare(sold, purchased, precision_digits=4) < 0:
                raise UserError(
                    _(
                        "No puede reducir la cantidad vendida a %(sold)s porque ya "
                        "existen %(purchased)s unidades compradas o relacionadas "
                        "con esta línea. Ajuste primero las órdenes de compra o "
                        "sus relaciones."
                    )
                    % {
                        "sold": float_round(sold, precision_digits=4),
                        "purchased": float_round(purchased, precision_digits=4),
                    }
                )

    def _justech_lock_for_purchase(self):
        """Row-lock SOL for concurrency before confirming buy/link."""
        if not self.ids:
            return
        self.env.cr.execute(
            "SELECT id FROM sale_order_line WHERE id IN %s FOR UPDATE",
            (tuple(self.ids),),
        )

    def justech_get_pending_snapshot(self):
        """Fresh pending qty from DB (invalidate cache first)."""
        self.invalidate_recordset(
            [
                "justech_qty_pending_purchase",
                "justech_qty_purchased",
                "justech_qty_stock_covered",
            ]
        )
        self._compute_justech_purchase_coverage()
        return {line.id: line.justech_qty_pending_purchase for line in self}
