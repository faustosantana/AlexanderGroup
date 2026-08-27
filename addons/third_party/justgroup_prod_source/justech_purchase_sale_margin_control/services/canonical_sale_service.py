# -*- coding: utf-8 -*-
"""Venta comercial canónica: factura posted prevalece; costo atribuible por SO.

No escribe históricos. Solo resuelve el read-model del reporte de márgenes.
"""
from odoo import api, models


class PurchaseSaleCanonicalSaleService(models.AbstractModel):
    _name = "purchase.sale.canonical.sale.service"
    _description = "Resolver de venta canónica (factura posted vs estimada)"

    _CUSTOMER_MOVE_TYPES = ("out_invoice", "out_refund")

    @api.model
    def _valid_customer_moves(self, moves):
        return moves.filtered(
            lambda m: m.move_type in self._CUSTOMER_MOVE_TYPES and m.state != "cancel"
        )

    @api.model
    def _posted_customer_moves(self, moves):
        return self._valid_customer_moves(moves).filtered(lambda m: m.state == "posted")

    @api.model
    def invoiced_moves_for_orders(self, sale_orders):
        """Facturas/NC cliente ligadas a las SO (posted si existen; si no, no canceladas)."""
        sale_orders = sale_orders.filtered(lambda s: s)
        if not sale_orders:
            return self.env["account.move"]
        moves = sale_orders.mapped("invoice_ids")
        posted = self._posted_customer_moves(moves)
        if posted:
            return posted
        return self._valid_customer_moves(moves)

    @api.model
    def tx_own_invoices(self, tx):
        return self._valid_customer_moves(tx.customer_invoice_ids)

    @api.model
    def tx_has_invoice_sale(self, tx):
        return bool(self.tx_own_invoices(tx))

    @api.model
    def is_superseded_estimated(self, tx):
        """MTX estimada/hub cuyo negocio ya está facturado en otra MTX.

        No oculta la MTX que sí carga las facturas. No borra históricos.
        """
        if self.tx_own_invoices(tx):
            return False
        sos = tx.sale_order_ids
        if not sos:
            return False
        invoiced = self.invoiced_moves_for_orders(sos)
        if not invoiced:
            return False
        others = self.env["purchase.sale.margin.transaction"].search(
            [
                ("id", "!=", tx.id),
                ("customer_invoice_ids", "in", invoiced.ids),
            ],
            limit=1,
        )
        return bool(others)

    @api.model
    def resolve_canonical_sale(self, tx):
        """Fuente única de venta comercial para una MTX.

        1) Facturas posted (o válidas) de las SO + las de la MTX, sin canceladas.
        2) Si no hay factura: SO estimada.
        3) Si esta MTX es hub estimado y otra MTX ya tiene las facturas: superseded.
        4) NC (out_refund) se incluyen para neteo en el caller.
        """
        sos = tx.sale_order_ids
        own = self.tx_own_invoices(tx)
        so_invoiced = self.invoiced_moves_for_orders(sos)
        superseded = self.is_superseded_estimated(tx)
        moves = so_invoiced | own
        if superseded:
            return {
                "sale_orders": sos,
                "moves": so_invoiced,
                "is_estimated": False,
                "is_superseded": True,
            }
        if moves:
            return {
                "sale_orders": sos,
                "moves": moves,
                "is_estimated": False,
                "is_superseded": False,
            }
        return {
            "sale_orders": sos,
            "moves": self.env["account.move"],
            "is_estimated": bool(sos),
            "is_superseded": False,
        }

    @api.model
    def attributable_purchase_orders(self, tx):
        """OC del negocio: MTX actual, hermanas por SO, merged, cost.link, sale_line."""
        pos = tx.purchase_order_ids
        sos = tx.sale_order_ids
        if not sos:
            return pos
        Tx = self.env["purchase.sale.margin.transaction"]
        siblings = Tx.search([("sale_order_ids", "in", sos.ids)])
        pos |= siblings.mapped("purchase_order_ids")
        merged = Tx.search([("merged_into_id", "in", (siblings | tx).ids)])
        pos |= merged.mapped("purchase_order_ids")
        if "purchase.sale.cost.link" in self.env:
            links = self.env["purchase.sale.cost.link"].search(
                [
                    ("sale_id", "in", sos.ids),
                    ("state", "!=", "cancelled"),
                    ("purchase_id", "!=", False),
                ]
            )
            pos |= links.mapped("purchase_id")
        Purchase = self.env["purchase.order"]
        pos |= Purchase.search(
            [
                ("company_id", "=", tx.company_id.id),
                ("order_line.sale_line_id.order_id", "in", sos.ids),
            ]
        )
        return pos

    @api.model
    def attributable_vendor_bills(self, tx):
        bills = self.env["account.move"]
        own = tx.vendor_bill_ids.filtered(
            lambda m: m.move_type in ("in_invoice", "in_refund") and m.state != "cancel"
        )
        bills |= own
        sos = tx.sale_order_ids
        if not sos:
            return bills
        Tx = self.env["purchase.sale.margin.transaction"]
        siblings = Tx.search([("sale_order_ids", "in", sos.ids)])
        bills |= siblings.mapped("vendor_bill_ids").filtered(
            lambda m: m.move_type in ("in_invoice", "in_refund") and m.state != "cancel"
        )
        merged = Tx.search([("merged_into_id", "in", (siblings | tx).ids)])
        bills |= merged.mapped("vendor_bill_ids").filtered(
            lambda m: m.move_type in ("in_invoice", "in_refund") and m.state != "cancel"
        )
        return bills
