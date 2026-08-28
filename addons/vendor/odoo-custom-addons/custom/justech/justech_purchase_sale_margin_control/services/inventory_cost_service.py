# -*- coding: utf-8 -*-
"""Costo de inventario consumido por ventas (SVL o fallback estándar/periódico).

Regla: el margen usa solo la valoración de las salidas entregadas de la venta.
La factura proveedor de la compra de stock pertenece a CxP, no se suma completa
como costo de cada venta (evita duplicar bill + valuation).
"""
from collections import defaultdict

from odoo import _, api, fields, models


COST_SOURCE = [
    ("direct_purchase", "Compra directa"),
    ("inventory", "Inventario"),
    ("manual", "Manual"),
    ("additional_cost", "Costo adicional"),
    ("service", "Servicio"),
]

INVENTORY_STATUS = [
    ("available", "Inventario disponible"),
    ("partial", "Inventario parcialmente consumido"),
    ("consumed", "Inventario consumido"),
]


class PurchaseSaleInventoryCostService(models.AbstractModel):
    _name = "purchase.sale.inventory.cost.service"
    _description = "Costo de inventario consumido (margen)"

    @api.model
    def _svl_model(self):
        if "stock.valuation.layer" in self.env:
            return self.env["stock.valuation.layer"]
        return False

    @api.model
    def _is_outgoing_move(self, move):
        dest = move.location_dest_id
        src = move.location_id
        picking = move.picking_id
        if picking and picking.picking_type_id:
            code = picking.picking_type_id.code
            if code == "outgoing":
                return True
            if code == "incoming" and src.usage == "customer":
                return False  # customer return intake
        if dest.usage == "customer":
            return True
        if src.usage == "customer" and dest.usage in ("internal", "transit"):
            return False
        return False

    @api.model
    def _is_customer_return_move(self, move):
        src = move.location_id
        picking = move.picking_id
        if src.usage == "customer":
            return True
        if picking and picking.picking_type_id and picking.picking_type_id.code == "incoming":
            if move.sale_line_id and src.usage == "customer":
                return True
        return False

    @api.model
    def _move_qty(self, move):
        qty = getattr(move, "quantity", None)
        if qty is None or qty is False:
            qty = move.product_uom_qty or 0.0
        return abs(qty or 0.0)

    @api.model
    def move_consumed_cost(self, move):
        """Costo positivo de una salida (o valor absoluto de SVL).

        Preferencia:
        1) stock.valuation.layer.value (suma; salidas suelen ser negativas → abs)
        2) stock.move.value / stock_value si existe
        3) price_unit * qty
        4) product.standard_price * qty  (típico AVCO/standard periódico sin SVL)
        """
        svl = self._svl_model()
        if svl is not False:
            if "stock_valuation_layer_ids" in move._fields:
                layers = move.stock_valuation_layer_ids
            else:
                layers = svl.search([("stock_move_id", "=", move.id)])
            if layers:
                return abs(sum(layers.mapped("value")))

        for fname in ("stock_value", "value"):
            if fname in move._fields and move[fname]:
                return abs(move[fname])

        qty = self._move_qty(move)
        if not qty:
            return 0.0
        price = 0.0
        if "price_unit" in move._fields and move.price_unit:
            price = abs(move.price_unit)
        elif move.product_id:
            price = abs(move.product_id.standard_price or 0.0)
        return price * qty

    @api.model
    def sale_delivery_moves(self, sale_orders):
        """Movimientos done vinculados a líneas de las ventas (salida y devolución)."""
        sale_orders = sale_orders.filtered(lambda s: s)
        if not sale_orders:
            return self.env["stock.move"]
        lines = sale_orders.mapped("order_line").filtered(lambda l: not l.display_type)
        if not lines:
            return self.env["stock.move"]
        Move = self.env["stock.move"]
        moves = Move.search(
            [
                ("sale_line_id", "in", lines.ids),
                ("state", "=", "done"),
                ("product_id", "!=", False),
            ]
        )
        return moves.filtered(
            lambda m: self._is_outgoing_move(m) or self._is_customer_return_move(m)
        )

    @api.model
    def inventory_cost_rows_for_sales(self, sale_orders, currency=None):
        """Filas de reporte: una por albarán de salida (agregado).

        Returns list of dicts compatible with _cost_rows.
        """
        moves = self.sale_delivery_moves(sale_orders)
        if not moves:
            return []

        company_currency = currency
        if not company_currency and sale_orders:
            company_currency = sale_orders[:1].company_id.currency_id

        by_picking = defaultdict(
            lambda: {
                "untaxed": 0.0,
                "qty": 0.0,
                "date": False,
                "name": "",
                "move_ids": [],
                "details": [],
            }
        )
        orphan_key = ("move", 0)

        for move in moves:
            amount = self.move_consumed_cost(move)
            if self._is_customer_return_move(move):
                amount = -abs(amount)
            else:
                amount = abs(amount)
            qty = self._move_qty(move)
            if self._is_customer_return_move(move):
                qty = -qty

            picking = move.picking_id
            key = ("picking", picking.id) if picking else ("move", move.id)
            bucket = by_picking[key]
            bucket["untaxed"] += amount
            bucket["qty"] += qty
            bucket["move_ids"].append(move.id)
            bucket["date"] = fields.Date.to_date(move.date) if move.date else bucket["date"]
            if picking:
                bucket["name"] = picking.name or move.reference or move.display_name or ""
            else:
                bucket["name"] = move.reference or move.display_name or _("Salida")
            unit = (abs(amount) / abs(qty)) if qty else 0.0
            bucket["details"].append(
                {
                    "product": move.product_id.display_name,
                    "product_id": move.product_id.id,
                    "qty": qty,
                    "unit_cost": unit,
                    "amount": amount,
                    "move_name": move.reference or move.display_name or str(move.id),
                    "picking": picking.name if picking else "",
                }
            )

        rows = []
        for _key, bucket in sorted(by_picking.items(), key=lambda kv: (kv[1]["date"] or fields.Date.today(), kv[1]["name"])):
            if abs(bucket["untaxed"]) < 0.0001 and not bucket["move_ids"]:
                continue
            doc = bucket["name"] or _("Salida")
            if not doc.upper().startswith("SALIDA"):
                doc_label = _("Salida %s") % doc
            else:
                doc_label = doc
            rows.append(
                {
                    "vendor": _("INVENTARIO"),
                    "partner_id": False,
                    "po": "",
                    "po_ids": (),
                    "bill": doc_label,
                    "bill_id": False,
                    "ncf": "",
                    "date": bucket["date"],
                    "untaxed": bucket["untaxed"],
                    "tax": 0.0,
                    "total": bucket["untaxed"],
                    "residual": 0.0,
                    "payment_state": _("Consumido"),
                    "raw_payment_state": "consumed",
                    "move_type": False,
                    "currency": company_currency,
                    "currency_name": company_currency.name if company_currency else "",
                    "kind": "inventory",
                    "label": doc_label,
                    "cost_source": "inventory",
                    "include_in_margin": True,
                    "include_in_cxp": False,
                    "inventory_details": bucket["details"],
                    "origin_note": _("Inventario consumido"),
                }
            )
        return rows

    @api.model
    def _is_inventory_po_line(self, pol):
        """Solo inventario explícito. Sin clasificación no se asume inventario."""
        usage = getattr(pol, "cost_usage_type", False) or ""
        return usage in ("inventory_pending", "inventory")

    @api.model
    def _sale_qty_for_cost(self, sale_line):
        """Qty a costear: entregada si >0; si no, pedida (provisional)."""
        delivered = abs(sale_line.qty_delivered or 0.0)
        if delivered > 0.0001:
            return delivered
        return abs(sale_line.product_uom_qty or 0.0)

    @api.model
    def allocate_inventory_po_cost_for_sales(
        self, purchase_orders, sale_orders, allocation_ledger=None, currency=None
    ):
        """Asigna costo de OC inventario por producto × cantidad de la venta.

        Nunca imputa el total de la OC. Respeta un ledger de qty ya asignada
        por purchase.order.line para no duplicar la misma OC en varias ventas.
        """
        if allocation_ledger is None:
            allocation_ledger = {}
        purchase_orders = purchase_orders.filtered(lambda p: p)
        sale_orders = sale_orders.filtered(lambda s: s)
        if not purchase_orders or not sale_orders:
            return [], allocation_ledger

        company_currency = currency
        if not company_currency:
            company_currency = sale_orders[:1].company_id.currency_id

        sale_lines = sale_orders.mapped("order_line").filtered(
            lambda l: not l.display_type and l.product_id
        )
        # demanda por producto
        demand = {}
        for sl in sale_lines:
            demand[sl.product_id.id] = demand.get(sl.product_id.id, 0.0) + self._sale_qty_for_cost(sl)

        details = []
        untaxed = 0.0
        po_names = []
        vendor = ""
        date = False
        for po in purchase_orders:
            inv_lines = po.order_line.filtered(
                lambda l: not l.display_type and self._is_inventory_po_line(l)
            )
            if not inv_lines:
                continue
            po_names.append(po.name)
            vendor = vendor or (po.partner_id.display_name or "")
            if po.date_order:
                date = fields.Date.to_date(po.date_order)
            for pol in inv_lines:
                pid = pol.product_id.id
                need = demand.get(pid, 0.0)
                if need <= 0.0001:
                    continue
                already = allocation_ledger.get(pol.id, 0.0)
                capacity = max((pol.product_qty or 0.0) - already, 0.0)
                if capacity <= 0.0001:
                    continue
                take = min(need, capacity)
                unit = abs(pol.price_unit or 0.0)
                amount = take * unit
                if amount <= 0.0001:
                    continue
                untaxed += amount
                allocation_ledger[pol.id] = already + take
                demand[pid] = need - take
                details.append(
                    {
                        "product": pol.product_id.display_name,
                        "product_id": pid,
                        "qty": take,
                        "unit_cost": unit,
                        "amount": amount,
                        "po": po.name,
                        "po_line_id": pol.id,
                        "move_name": po.name,
                        "picking": "",
                    }
                )

        if abs(untaxed) < 0.0001:
            return [], allocation_ledger

        label = _("Inventario consumido (asignado)")
        rows = [
            {
                "vendor": vendor or _("INVENTARIO"),
                "partner_id": False,
                "po": ", ".join(po_names),
                "po_ids": tuple(sorted(purchase_orders.ids)),
                "bill": label,
                "bill_id": False,
                "ncf": "",
                "date": date,
                "untaxed": untaxed,
                "tax": 0.0,
                "total": untaxed,
                "residual": 0.0,
                "payment_state": _("Consumido"),
                "raw_payment_state": "consumed",
                "move_type": False,
                "currency": company_currency,
                "currency_name": company_currency.name if company_currency else "",
                "kind": "inventory",
                "label": label,
                "cost_source": "inventory",
                "include_in_margin": True,
                "include_in_cxp": False,
                "inventory_details": details,
                "origin_note": _("Inventario · qty vendida × costo OC"),
            }
        ]
        return rows, allocation_ledger

    @api.model
    def purchase_inventory_status(self, purchase_order):
        """Clasifica OC de stock: disponible / parcial / consumido (aprox por qty)."""
        po = purchase_order
        if not po:
            return "available", 0.0, 0.0, 0.0
        qty_ordered = sum(po.order_line.filtered(lambda l: not l.display_type).mapped("product_qty"))
        # qty received
        qty_received = sum(po.order_line.filtered(lambda l: not l.display_type).mapped("qty_received"))
        # qty sold via linked sale lines (MTO) + heuristic: not fully tracked without lots
        linked_sale_lines = po.order_line.mapped("sale_line_id")
        qty_sold = sum(linked_sale_lines.mapped("qty_delivered")) if linked_sale_lines else 0.0
        remaining = max(qty_received - qty_sold, 0.0)
        original_cost = po.amount_untaxed or 0.0
        unit = (original_cost / qty_ordered) if qty_ordered else 0.0
        assigned = unit * qty_sold
        pending = unit * remaining
        if qty_sold <= 0.0001:
            status = "available"
        elif remaining <= 0.0001:
            status = "consumed"
        else:
            status = "partial"
        return status, original_cost, assigned, pending
