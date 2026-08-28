# -*- coding: utf-8 -*-
"""Cost management orchestration for Gestionar compras (hub + product modal).

Reuses LineAllocationService / qty.assignment / MTX — no new ledger.
Never reads margin_band (groups-restricted); coverage is operational qty only.
"""
from __future__ import annotations

from odoo import fields
from odoo.exceptions import UserError, ValidationError
from odoo.tools.float_utils import float_compare
from odoo.tools.translate import _

from odoo.addons.justech_purchase_sale_margin_control.models.margin_acl import (
    margin_transaction,
    margin_transaction_line,
)
from odoo.addons.justech_purchase_sale_margin_control.services.line_allocation_service import (
    LineAllocationService,
    _is_product_line,
)


class CostManagementService:
    """A–E orchestration: demand, coverage, allocation, eligible docs."""

    def __init__(self, env):
        self.env = env
        self.alloc = LineAllocationService(env)

    def mtx(self, transaction):
        """Always elevate MTX reads — avoids margin_band field ACL."""
        if not transaction:
            return self.env["purchase.sale.margin.transaction"]
        return margin_transaction(self.env).browse(transaction.id)

    def sale_demand_sols(self, sale_orders, invoices=None):
        """Invoice posted first; else sale.order.line. Never 'transaction' alone."""
        invoices = invoices or self.env["account.move"]
        sols = self.env["sale.order.line"]
        source = "none"
        posted = invoices.filtered(
            lambda m: m.state == "posted"
            and m.move_type in ("out_invoice", "out_refund")
        )
        if posted:
            sols = (
                posted.mapped("invoice_line_ids")
                .filtered(
                    lambda l: (not l.display_type or l.display_type == "product")
                    and l.product_id
                )
                .mapped("sale_line_ids")
                .filtered(_is_product_line)
            )
            source = "invoice"
        if not sols and sale_orders:
            sols = sale_orders.sudo().mapped("order_line").filtered(_is_product_line)
            source = "sale_order" if sols else "none"
        return sols, source, posted

    def build_demand_rows(self, sale_orders, invoices=None, transaction=None):
        """Operational coverage rows — no margin_band."""
        sols, source, posted = self.sale_demand_sols(sale_orders, invoices)
        tx_s = self.mtx(transaction) if transaction else False
        rows = []
        for sol in sols:
            sold = self.alloc.sol_final_sale_qty(sol, invoice_moves=posted or None)
            if float_compare(sold, 0.0, precision_digits=4) <= 0:
                continue
            purchase_qty = min(self.alloc.sol_qty_assigned_to_purchase(sol), sold)
            hist_qty = min(
                self.alloc.sol_qty_historical_manual(
                    sol, transaction=tx_s if tx_s else None
                ),
                max(sold - purchase_qty, 0.0),
            )
            # Vendor-bill cost lines linked to SOL (qty coverage without ASG)
            bill_qty = self._sol_qty_vendor_bill(sol, tx_s)
            hist_qty = min(hist_qty + bill_qty, max(sold - purchase_qty, 0.0))
            covered = min(purchase_qty + hist_qty, sold)
            pending = max(sold - covered, 0.0)
            pending_receive = self._sol_qty_pending_receive(sol)
            if float_compare(pending, 0.0, precision_digits=4) <= 0:
                status = "complete"
            elif float_compare(covered, 0.0, precision_digits=4) <= 0:
                status = "pending"
            else:
                status = "partial"
            rows.append(
                {
                    "sale_line_id": sol.id,
                    "product_id": sol.product_id.id,
                    "product_name": sol.product_id.display_name or sol.name,
                    "sold_qty": sold,
                    "purchase_qty": purchase_qty,
                    "historical_qty": hist_qty,
                    "inventory_qty": hist_qty,
                    "covered_qty": covered,
                    "pending_qty": pending,
                    "pending_receive_qty": pending_receive,
                    "line_status": status,
                }
            )
        return rows, source

    def _sol_qty_pending_receive(self, sol):
        """Physical receive gap on related active POLs (not cost pending)."""
        if not sol:
            return 0.0
        if "justech_qty_pending_receive" in sol._fields:
            return max(sol.justech_qty_pending_receive or 0.0, 0.0)
        pending = 0.0
        pols = self.env["purchase.order.line"].sudo().search(
            [
                ("sale_line_id", "=", sol.id),
                ("state", "!=", "cancel"),
                ("order_id.state", "!=", "cancel"),
            ]
        )
        covered_pol_ids = set(pols.ids)
        if "justech.purchase.sale.qty.assignment" in self.env:
            Assign = self.env["justech.purchase.sale.qty.assignment"].sudo()
            for asg in Assign.search(
                [("sale_line_id", "=", sol.id), ("state", "=", "active")]
            ):
                pol = asg.purchase_line_id
                if not pol or pol.id in covered_pol_ids:
                    continue
                if pol.state == "cancel" or pol.order_id.state == "cancel":
                    continue
                pols |= pol
        for pol in pols:
            ordered = pol.product_qty or 0.0
            received = pol.qty_received or 0.0
            pending += max(ordered - received, 0.0)
        return pending

    def _sol_qty_vendor_bill(self, sol, transaction):
        Line = margin_transaction_line(self.env)
        domain = [
            ("line_type", "=", "cost"),
            ("state", "!=", "excluded"),
            ("account_move_id", "!=", False),
            ("account_move_id.move_type", "in", ("in_invoice", "in_refund")),
            ("quantity", ">", 0),
            ("cost_source", "=", "direct_purchase"),
        ]
        if "sale_order_line_id" in Line._fields:
            domain.append(("sale_order_line_id", "=", sol.id))
        else:
            domain += [
                ("sale_order_id", "=", sol.order_id.id),
                ("product_id", "=", sol.product_id.id),
            ]
        if transaction:
            domain.append(("transaction_id", "=", transaction.id))
        return sum(Line.search(domain).mapped("quantity") or [0.0])

    def stock_info(self, product, company):
        qty = reserved = available = 0.0
        if not product or not company:
            return qty, reserved, available
        try:
            wh = self.env["stock.warehouse"].sudo().search(
                [("company_id", "=", company.id)], limit=1
            )
            if wh and hasattr(product, "with_context"):
                p = product.sudo().with_context(
                    warehouse_id=wh.id, allowed_company_ids=[company.id]
                )
                qty = p.qty_available or 0.0
                reserved = getattr(p, "outgoing_qty", 0.0) or 0.0
                available = getattr(p, "free_qty", None)
                if available is None:
                    available = qty - reserved
                available = available or 0.0
        except Exception:  # noqa: BLE001
            pass
        return qty, reserved, available

    def eligible_purchase_orders(self, company, supplier, show_exhausted=False):
        """POs for supplier with commercially available POL qty (not cancelled)."""
        if not company or not supplier:
            return self.env["purchase.order"]
        domain = [
            ("company_id", "=", company.id),
            ("partner_id", "child_of", supplier.commercial_partner_id.id),
            ("state", "!=", "cancel"),
        ]
        pos = self.env["purchase.order"].sudo().search(domain, order="date_order desc, id desc")
        if show_exhausted:
            return pos
        keep = self.env["purchase.order"]
        for po in pos:
            for pol in po.order_line.filtered(_is_product_line):
                if float_compare(self.alloc.pol_qty_available(pol), 0.0, precision_digits=4) > 0:
                    keep |= po
                    break
        return keep

    def pol_pick_rows(self, purchase_order, focus_product=None, show_exhausted=False):
        rows = []
        if not purchase_order:
            return rows
        pols = purchase_order.sudo().order_line.filtered(_is_product_line)
        ordered = pols.sorted(
            key=lambda p: 0 if focus_product and p.product_id == focus_product else 1
        )
        for pol in ordered:
            if pol.order_id.state == "cancel" or pol.state == "cancel":
                continue
            avail = self.alloc.pol_qty_available(pol)
            if (
                not show_exhausted
                and float_compare(avail, 0.0, precision_digits=4) <= 0
            ):
                continue
            unit = (
                (pol.price_subtotal or 0.0) / pol.product_qty
                if pol.product_qty
                else (pol.price_unit or 0.0)
            )
            rows.append(
                {
                    "purchase_line_id": pol.id,
                    "product_id": pol.product_id.id,
                    "qty_purchased": pol.product_qty or 0.0,
                    "qty_assigned": max((pol.product_qty or 0.0) - avail, 0.0),
                    "qty_available": avail,
                    "unit_cost": unit,
                    "is_focus_product": bool(
                        focus_product and pol.product_id == focus_product
                    ),
                }
            )
        return rows

    def eligible_vendor_bills(self, company, supplier, name_search=None):
        domain = [
            ("company_id", "=", company.id),
            ("move_type", "in", ("in_invoice", "in_refund")),
            ("state", "=", "posted"),
            ("partner_id", "child_of", supplier.commercial_partner_id.id),
        ]
        if name_search:
            domain = [
                "&",
                *domain,
                "|",
                "|",
                ("name", "ilike", name_search),
                ("ref", "ilike", name_search),
                ("l10n_latam_document_number", "ilike", name_search),
            ] if "l10n_latam_document_number" in self.env["account.move"]._fields else [
                "&",
                *domain,
                "|",
                ("name", "ilike", name_search),
                ("ref", "ilike", name_search),
            ]
        return self.env["account.move"].sudo().search(domain, order="invoice_date desc, id desc", limit=80)

    def apply_relate_po_lines(self, transaction, company, sol, pick_rows):
        """pick_rows: list of {purchase_line, quantity}."""
        tx_s = self.mtx(transaction)
        if sol.company_id != company:
            raise ValidationError(_("La línea de venta pertenece a otra compañía."))
        rows = []
        for pick in pick_rows:
            pol = pick["purchase_line"]
            qty = pick["quantity"]
            if float_compare(qty, 0.0, precision_digits=4) <= 0:
                continue
            if pol.company_id != company:
                raise ValidationError(
                    _("La OC %s pertenece a otra compañía.") % (pol.order_id.name,)
                )
            rows.append({"sale_line": sol, "purchase_line": pol, "quantity": qty})
        if not rows:
            raise UserError(
                _("Indique al menos una cantidad «Usar» en los artículos de la OC.")
            )
        elev = LineAllocationService(
            self.env(context=dict(self.env.context, margin_hub_mtx_elevate=True))
        )
        elev.apply_allocations_to_transaction(tx_s, rows, replace=False)
        po_ids = list({r["purchase_line"].order_id.id for r in rows})
        partner_ids = list(
            {
                r["purchase_line"].order_id.partner_id.commercial_partner_id.id
                for r in rows
            }
        )
        tx_s.write(
            {
                "purchase_order_ids": [(4, i) for i in po_ids],
                "supplier_ids": [(4, i) for i in partner_ids],
            }
        )
        if hasattr(tx_s, "_sync_lines_from_documents"):
            tx_s.with_context(
                skip_line_sync=False, margin_skip_unsafe_po_cost=True
            )._sync_lines_from_documents()
        LineAllocationService(self.env).confirm_explicit_hub_relation(tx_s)
        return tx_s

    def apply_historical(self, transaction, company, sol, product, qty, unit_cost, note=""):
        tx_s = self.mtx(transaction)
        if float_compare(qty, 0.0, precision_digits=4) <= 0:
            raise UserError(_("Indique la cantidad a cubrir con inventario/histórico."))
        if float_compare(unit_cost or 0.0, 0.0, precision_digits=4) < 0:
            raise UserError(_("El costo unitario no puede ser negativo."))
        amount = qty * (unit_cost or 0.0)
        margin_transaction_line(self.env).create(
            {
                "transaction_id": tx_s.id,
                "line_type": "cost",
                "data_origin": "manual",
                "cost_source": "inventory",
                "sale_order_id": sol.order_id.id,
                "sale_order_line_id": sol.id,
                "product_id": product.id,
                "description": _("Inventario histórico / costo manual — %s")
                % (product.display_name or ""),
                "currency_id": company.currency_id.id,
                "quantity": qty,
                "amount_untaxed": amount,
                "amount_total": amount,
                "is_manual": True,
                "notes": (note or "").strip()
                or _(
                    "Solo Costos y Márgenes. Sin stock, sin asiento, sin recepción."
                ),
            }
        )
        LineAllocationService(self.env).confirm_explicit_hub_relation(tx_s)
        return tx_s

    def apply_vendor_bill_line(self, transaction, company, sol, aml, qty, amount=None):
        """Relate vendor bill line to sale line via MTX (+ ASG if POL exists)."""
        tx_s = self.mtx(transaction)
        bill = aml.move_id
        if bill.move_type not in ("in_invoice", "in_refund") or bill.state != "posted":
            raise UserError(_("Solo facturas de proveedor publicadas."))
        if bill.company_id != company:
            raise ValidationError(_("La factura pertenece a otra compañía."))
        if float_compare(qty, 0.0, precision_digits=4) <= 0:
            raise UserError(_("Indique la cantidad a relacionar."))
        unit = 0.0
        if aml.quantity:
            unit = abs(aml.price_subtotal or 0.0) / aml.quantity
        amount = amount if amount is not None else qty * unit
        pol = aml.purchase_line_id
        if pol:
            elev = LineAllocationService(
                self.env(context=dict(self.env.context, margin_hub_mtx_elevate=True))
            )
            elev.apply_allocations_to_transaction(
                tx_s,
                [{"sale_line": sol, "purchase_line": pol, "quantity": qty}],
                replace=False,
            )
            tx_s.write(
                {
                    "purchase_order_ids": [(4, pol.order_id.id)],
                    "vendor_bill_ids": [(4, bill.id)],
                    "supplier_ids": [(4, bill.partner_id.commercial_partner_id.id)],
                }
            )
            elev.refresh_estimated_to_real_from_bill(bill)
        else:
            # Explicit Bill → Sale (no invented PO)
            margin_transaction_line(self.env).create(
                {
                    "transaction_id": tx_s.id,
                    "line_type": "cost",
                    "data_origin": "accounting",
                    "cost_source": "direct_purchase",
                    "sale_order_id": sol.order_id.id,
                    "sale_order_line_id": sol.id,
                    "product_id": (aml.product_id or sol.product_id).id,
                    "account_move_id": bill.id,
                    "account_move_line_id": aml.id,
                    "description": _("Factura proveedor %s")
                    % (bill.name or bill.display_name),
                    "currency_id": bill.currency_id.id or company.currency_id.id,
                    "quantity": qty,
                    "amount_untaxed": amount,
                    "amount_total": amount,
                    "notes": _("Relación Bill→Sale sin OC (CxP visible)."),
                }
            )
            tx_s.write(
                {
                    "vendor_bill_ids": [(4, bill.id)],
                    "supplier_ids": [(4, bill.partner_id.commercial_partner_id.id)],
                }
            )
        if hasattr(tx_s, "_sync_lines_from_documents"):
            tx_s.with_context(
                skip_line_sync=False, margin_skip_unsafe_po_cost=True
            )._sync_lines_from_documents()
        # Refresh real cost from bill when possible.
        elev = LineAllocationService(
            self.env(context=dict(self.env.context, margin_hub_mtx_elevate=True))
        )
        if hasattr(elev, "refresh_estimated_to_real_from_bill"):
            elev.refresh_estimated_to_real_from_bill(bill)
        LineAllocationService(self.env).confirm_explicit_hub_relation(tx_s)
        return tx_s

    def create_purchase_order(self, company, partner, lines, vals=None):
        """Create normal purchase.order from prepared lines.

        lines: [{product, qty, price, name?}]
        Does NOT auto-assign to sale — caller assigns.
        """
        if not partner:
            raise UserError(_("Seleccione el proveedor."))
        if not lines:
            raise UserError(_("Agregue al menos un artículo a la compra."))
        order_lines = []
        POL = self.env["purchase.order.line"]
        for row in lines:
            product = row["product"]
            qty = row["qty"]
            if float_compare(qty, 0.0, precision_digits=4) <= 0:
                continue
            po_line_vals = {
                "product_id": product.id,
                "name": row.get("name") or product.display_name,
                "product_qty": qty,
                "price_unit": row.get("price") or 0.0,
                "date_planned": row.get("date_planned") or fields.Datetime.now(),
            }
            if "product_uom_id" in POL._fields:
                po_line_vals["product_uom_id"] = product.uom_id.id
            elif "product_uom" in POL._fields:
                po_line_vals["product_uom"] = product.uom_id.id
            order_lines.append((0, 0, po_line_vals))
        if not order_lines:
            raise UserError(_("Indique cantidades válidas."))
        po_vals = {
            "partner_id": partner.id,
            "company_id": company.id,
            "order_line": order_lines,
        }
        if vals:
            PO = self.env["purchase.order"]
            po_vals.update(
                {
                    k: v
                    for k, v in vals.items()
                    if k in PO._fields and v not in (None, False, "")
                }
            )
        return self.env["purchase.order"].create(po_vals)

    def assign_po_line_to_sale(self, transaction, company, sol, pol, assign_qty):
        if float_compare(assign_qty, 0.0, precision_digits=4) <= 0:
            raise UserError(_("No hay cantidad a atribuir a la venta."))
        elev = LineAllocationService(
            self.env(context=dict(self.env.context, margin_hub_mtx_elevate=True))
        )
        tx_s = self.mtx(transaction)
        elev.apply_allocations_to_transaction(
            tx_s,
            [{"sale_line": sol, "purchase_line": pol, "quantity": assign_qty}],
            replace=False,
        )
        tx_s.write(
            {
                "purchase_order_ids": [(4, pol.order_id.id)],
                "supplier_ids": [
                    (4, pol.order_id.partner_id.commercial_partner_id.id)
                ],
            }
        )
        if hasattr(tx_s, "_sync_lines_from_documents"):
            tx_s.with_context(
                skip_line_sync=False, margin_skip_unsafe_po_cost=True
            )._sync_lines_from_documents()
        return tx_s

    def create_draft_pos_and_assign(self, transaction, company, groups):
        """Create one draft PO per supplier group and assign only sale qty.

        groups: [
            {
                "partner": res.partner,
                "po_vals": optional dict (currency, payment_term, notes, ...),
                "lines": [
                    {
                        "product": product.product,
                        "buy_qty": float,
                        "assign_qty": float,  # may be < buy_qty
                        "price": float,
                        "sale_line": sale.order.line,
                        "name": optional str,
                    },
                    ...
                ],
            },
            ...
        ]
        Residual (buy - assign) stays free on the PO commercially.

        Assignments are applied in one batch after all POs exist so an
        intermediate MTX sync cannot drop partial qty.assignment rows.
        """
        tx_s = self.mtx(transaction)
        created = self.env["purchase.order"]
        alloc_rows = []
        po_ids = []
        partner_ids = []
        for group in groups:
            partner = group.get("partner")
            rows = group.get("lines") or []
            if not partner or not rows:
                continue
            po_lines = []
            pending_assigns = []
            for row in rows:
                buy = row.get("buy_qty") or 0.0
                assign = row.get("assign_qty") or 0.0
                product = row["product"]
                sol = row["sale_line"]
                if float_compare(buy, 0.0, precision_digits=4) <= 0:
                    continue
                if float_compare(assign, buy, precision_digits=4) > 0:
                    raise UserError(
                        _(
                            "La cantidad atribuida a la venta no puede superar "
                            "la cantidad a comprar (%s)."
                        )
                        % (product.display_name,)
                    )
                if float_compare(assign, 0.0, precision_digits=4) < 0:
                    raise UserError(_("La cantidad atribuida no puede ser negativa."))
                po_lines.append(
                    {
                        "product": product,
                        "qty": buy,
                        "price": row.get("price") or 0.0,
                        "name": row.get("name") or product.display_name,
                    }
                )
                if float_compare(assign, 0.0, precision_digits=4) > 0:
                    pending_assigns.append((sol, product, assign))
            if not po_lines:
                continue
            po = self.create_purchase_order(
                company, partner, po_lines, vals=group.get("po_vals") or {}
            )
            created |= po
            po_ids.append(po.id)
            partner_ids.append(partner.commercial_partner_id.id)
            pols = po.order_line.filtered(_is_product_line)
            for sol, product, assign_qty in pending_assigns:
                pol = pols.filtered(lambda p, prod=product: p.product_id == prod)[:1]
                if not pol:
                    raise UserError(
                        _(
                            "No se encontró la línea de OC para %s tras crear la compra."
                        )
                        % (product.display_name,)
                    )
                alloc_rows.append(
                    {
                        "sale_line": sol,
                        "purchase_line": pol,
                        "quantity": assign_qty,
                    }
                )
        if not created:
            return created
        if alloc_rows:
            elev = LineAllocationService(
                self.env(context=dict(self.env.context, margin_hub_mtx_elevate=True))
            )
            elev.apply_allocations_to_transaction(tx_s, alloc_rows, replace=False)
        tx_s.write(
            {
                "purchase_order_ids": [(4, i) for i in po_ids],
                "supplier_ids": [(4, i) for i in partner_ids],
            }
        )
        if hasattr(tx_s, "_sync_lines_from_documents"):
            tx_s.with_context(
                skip_line_sync=False, margin_skip_unsafe_po_cost=True
            )._sync_lines_from_documents()
        # Explicit hub create → confirm relation (not finance approval).
        LineAllocationService(self.env).confirm_explicit_hub_relation(tx_s)
        return created
