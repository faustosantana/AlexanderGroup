# -*- coding: utf-8 -*-
"""19.0.8.29.15 — Canonical SOL↔POL qty allocation for Margins.

Reuses Trace ``justech.purchase.sale.qty.assignment`` when installed.
Writes proportional MTX estimated cost lines (never full-PO silently).
Does not alter accounting, SO/PO quantities, or NCF.
"""
from odoo import _
from odoo.exceptions import UserError, ValidationError
from odoo.tools.float_utils import float_compare, float_is_zero


def _is_product_line(line):
    dtype = getattr(line, "display_type", False)
    if dtype in ("line_section", "line_note", "tax", "payment_term"):
        return False
    if dtype == "product":
        return True
    return bool(getattr(line, "product_id", False))


class LineAllocationService:
    """Stateless helpers bound to an ``env``."""

    def __init__(self, env):
        self.env = env

    @staticmethod
    def commercial_id(partner):
        if not partner:
            return False
        return partner.commercial_partner_id.id or partner.id

    def assert_sale_docs_match_customer(self, company, customer, sale_orders, invoices):
        if not customer:
            return
        cid = self.commercial_id(customer)
        for so in sale_orders:
            if so.company_id != company:
                raise ValidationError(_("La orden de venta pertenece a otra empresa."))
            if self.commercial_id(so.partner_id) != cid:
                raise ValidationError(
                    _("La orden %s no pertenece al cliente seleccionado.") % so.name
                )
        for inv in invoices:
            if inv.company_id != company:
                raise ValidationError(_("La factura de cliente pertenece a otra empresa."))
            if inv.move_type not in ("out_invoice", "out_refund"):
                raise ValidationError(_("Documento de cliente no válido."))
            if self.commercial_id(inv.partner_id) != cid:
                raise ValidationError(
                    _("La factura %s no pertenece al cliente seleccionado.") % inv.name
                )

    def assert_purchase_docs_match_supplier(self, company, supplier, purchase_orders, bills):
        """Single-supplier check (compat). Prefer ``assert_purchase_docs_match_suppliers``."""
        if not supplier:
            return
        self.assert_purchase_docs_match_suppliers(
            company, supplier, purchase_orders, bills
        )

    def assert_purchase_docs_match_suppliers(self, company, suppliers, purchase_orders, bills):
        """Validate POs/bills belong to company and to one of the given suppliers."""
        suppliers = suppliers if hasattr(suppliers, "ids") else suppliers
        if not suppliers:
            return
        allowed = {self.commercial_id(s) for s in suppliers if s}
        for po in purchase_orders:
            if po.company_id != company:
                raise ValidationError(_("La orden de compra pertenece a otra empresa."))
            if self.commercial_id(po.partner_id) not in allowed:
                raise ValidationError(
                    _("La OC %s no pertenece a los proveedores seleccionados.") % po.name
                )
        for bill in bills:
            if bill.company_id != company:
                raise ValidationError(_("La factura de proveedor pertenece a otra empresa."))
            if bill.move_type not in ("in_invoice", "in_refund"):
                raise ValidationError(_("Documento de proveedor no válido."))
            if self.commercial_id(bill.partner_id) not in allowed:
                raise ValidationError(
                    _("La factura %s no pertenece a los proveedores seleccionados.")
                    % (bill.name or bill.display_name)
                )

    def pol_qty_available(self, pol, exclude_assignment_ids=None):
        """Commercial remaining qty for Margins cost relation.

        Canonical rule (margins):
            available = product_qty - active qty.assignment

        Does NOT use as primary gate: pending_purchase, qty_received,
        qty_invoiced, or stock availability. Cancelled POL/PO → 0.

        Note: Trace's ``_justech_qty_available_to_assign`` also treats a bare
        ``sale_line_id`` M2O as fully assigned; Margins intentionally counts
        only active ``justech.purchase.sale.qty.assignment`` rows.
        """
        exclude_assignment_ids = exclude_assignment_ids or []
        if not pol or pol.state == "cancel" or pol.order_id.state == "cancel":
            return 0.0
        product_qty = pol.product_qty or 0.0
        # Trace direct M2O (full commercial claim without ASG row).
        if pol.sale_line_id:
            return 0.0
        assigned = 0.0
        if "justech.purchase.sale.qty.assignment" in self.env:
            Assign = self.env["justech.purchase.sale.qty.assignment"]
            domain = [
                ("purchase_line_id", "=", pol.id),
                ("state", "=", "active"),
            ]
            if exclude_assignment_ids:
                domain.append(("id", "not in", list(exclude_assignment_ids)))
            assigned = sum(Assign.search(domain).mapped("quantity"))
        else:
            Line = self.env["purchase.sale.margin.transaction.line"]
            assigned = sum(
                Line.search(
                    [
                        ("purchase_order_line_id", "=", pol.id),
                        ("line_type", "=", "cost"),
                        ("data_origin", "=", "estimated"),
                        ("state", "!=", "excluded"),
                    ]
                ).mapped("quantity")
            )
        return max(product_qty - assigned, 0.0)

    def sol_qty_pending(self, sol):
        """Legacy Trace purchase-pending (inventory coverage). Prefer assignment APIs for margin."""
        if "justech_qty_pending_purchase" in sol._fields:
            return sol.justech_qty_pending_purchase or 0.0
        return self.sol_qty_available_for_margin(sol)

    def sol_qty_assigned_to_purchase(self, sol):
        """Active Trace commercial link qty for this SOL (ASG + direct POL M2O)."""
        assigned = 0.0
        covered_pol_ids = set()
        if "justech.purchase.sale.qty.assignment" in self.env:
            Assign = self.env["justech.purchase.sale.qty.assignment"]
            asgs = Assign.search(
                [("sale_line_id", "=", sol.id), ("state", "=", "active")]
            )
            assigned = sum(asgs.mapped("quantity"))
            covered_pol_ids = set(asgs.mapped("purchase_line_id").ids)
        # Trace full-line path may set purchase.order.line.sale_line_id without ASG.
        pols = self.env["purchase.order.line"].sudo().search(
            [
                ("sale_line_id", "=", sol.id),
                ("state", "!=", "cancel"),
                ("order_id.state", "!=", "cancel"),
            ]
        )
        for pol in pols:
            if pol.id in covered_pol_ids:
                continue
            assigned += pol.product_qty or 0.0
        return assigned

    def sol_qty_historical_manual(self, sol, transaction=None):
        """Qty covered by margin-only inventory/manual cost lines (no stock/accounting)."""
        Line = self.env["purchase.sale.margin.transaction.line"]
        domain = [
            ("line_type", "=", "cost"),
            ("state", "!=", "excluded"),
            ("cost_source", "in", ("inventory", "manual")),
            ("quantity", ">", 0),
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

    def sol_net_invoiced_qty(self, sol, invoice_moves=None):
        """Net posted customer invoice qty (invoices − refunds) for one SOL."""
        lines = sol.invoice_lines.filtered(
            lambda l: l.move_id.state == "posted"
            and l.move_id.move_type in ("out_invoice", "out_refund")
            and (not l.display_type or l.display_type == "product")
        )
        if invoice_moves is not None:
            lines = lines.filtered(lambda l: l.move_id in invoice_moves)
        qty = 0.0
        for aml in lines:
            if aml.move_id.move_type == "out_refund":
                qty -= aml.quantity or 0.0
            else:
                qty += aml.quantity or 0.0
        return max(qty, 0.0)

    def sol_final_sale_qty(self, sol, invoice_moves=None):
        """SALE ACTUAL when posted invoices exist; else SALE COMMITTED (SO qty)."""
        has_inv = bool(
            sol.invoice_lines.filtered(
                lambda l: l.move_id.state == "posted"
                and l.move_id.move_type in ("out_invoice", "out_refund")
            )
        )
        if invoice_moves:
            return self.sol_net_invoiced_qty(sol, invoice_moves)
        if has_inv:
            return self.sol_net_invoiced_qty(sol)
        return sol.product_uom_qty or 0.0

    def sol_qty_available_for_margin(self, sol, invoice_moves=None):
        final = self.sol_final_sale_qty(sol, invoice_moves=invoice_moves)
        assigned = self.sol_qty_assigned_to_purchase(sol)
        return max(final - assigned, 0.0)

    def customer_invoices_for_sale_orders(self, sale_orders, company=None):
        """Posted customer invoices linked via sale_order_line_invoice_rel / SOL.invoice_lines."""
        Move = self.env["account.move"]
        if not sale_orders:
            return Move
        company = company or sale_orders[:1].company_id
        moves = sale_orders.mapped("order_line.invoice_lines.move_id")
        moves |= sale_orders.mapped("invoice_ids")
        return moves.filtered(
            lambda m: m.company_id == company
            and m.move_type in ("out_invoice", "out_refund")
            and m.state == "posted"
        )

    def po_full_cost_sync_is_safe(self, transaction, po):
        """True when linking this PO may sync 100% of POL costs (Golden path)."""
        sos = transaction.sale_order_ids
        if not sos:
            return True
        pols = po.order_line.filtered(_is_product_line)
        if not pols:
            return False
        if "justech.purchase.sale.qty.assignment" in self.env:
            Assign = self.env["justech.purchase.sale.qty.assignment"]
            asgs = Assign.search(
                [
                    ("purchase_line_id", "in", pols.ids),
                    ("sale_order_id", "in", sos.ids),
                    ("state", "=", "active"),
                ]
            )
            if asgs:
                for pol in pols:
                    linked = sum(
                        asgs.filtered(lambda a, p=pol: a.purchase_line_id == p).mapped(
                            "quantity"
                        )
                    )
                    if float_compare(linked, pol.product_qty or 0.0, precision_digits=4) < 0:
                        return False
                return True
        for pol in pols:
            if pol.sale_line_id and pol.sale_line_id.order_id in sos:
                if (
                    float_compare(
                        pol.product_qty or 0.0,
                        pol.sale_line_id.product_uom_qty or 0.0,
                        precision_digits=4,
                    )
                    == 0
                ):
                    continue
                return False
            matches = sos.mapped("order_line").filtered(
                lambda l, p=pol: _is_product_line(l) and l.product_id == p.product_id
            )
            if (
                len(matches) == 1
                and float_compare(
                    matches.product_uom_qty or 0.0,
                    pol.product_qty or 0.0,
                    precision_digits=4,
                )
                == 0
            ):
                continue
            return False
        return True

    def cost_allocation_pending(self, transaction):
        if not transaction.sale_order_ids or not transaction.purchase_order_ids:
            return False
        if "justech.purchase.sale.qty.assignment" in self.env:
            Assign = self.env["justech.purchase.sale.qty.assignment"]
            asgs = Assign.search(
                [
                    ("sale_order_id", "in", transaction.sale_order_ids.ids),
                    ("purchase_order_id", "in", transaction.purchase_order_ids.ids),
                    ("state", "=", "active"),
                ]
            )
            if asgs:
                return False
        for po in transaction.purchase_order_ids:
            if not self.po_full_cost_sync_is_safe(transaction, po):
                return True
        return False

    def link_pol_to_sol(self, pol, sol, quantity):
        if float_compare(quantity, 0.0, precision_digits=4) <= 0:
            raise UserError(_("La cantidad a relacionar debe ser positiva."))
        if pol.company_id != sol.company_id:
            raise ValidationError(_("No se puede relacionar OC y venta de empresas distintas."))
        if (
            pol.product_id
            and sol.product_id
            and pol.product_id != sol.product_id
            and not self.env.context.get("margin_allow_cross_product_link")
        ):
            raise ValidationError(
                _("El producto de compra no coincide con el de venta (%s ≠ %s).")
                % (pol.product_id.display_name, sol.product_id.display_name)
            )
        # Idempotent full-line claim: already parked on this SOL.
        if pol.sale_line_id == sol:
            ratio = (quantity / pol.product_qty) if pol.product_qty else 0.0
            return (pol.price_subtotal * ratio) if pol.product_qty else quantity * (
                pol.price_unit or 0.0
            )
        # Server-side SOL capacity first (clear UX when both SOL/POL are short).
        avail_sol = self.sol_qty_available_for_margin(sol)
        if float_compare(quantity, avail_sol, precision_digits=4) > 0:
            raise UserError(
                _(
                    "No puede asignar %(qty)s unidades.\n"
                    "Cantidad disponible en la venta: %(avail)s."
                )
                % {
                    "qty": quantity,
                    "avail": avail_sol,
                }
            )
        avail = self.pol_qty_available(pol)
        if float_compare(quantity, avail, precision_digits=4) > 0:
            raise UserError(
                _(
                    "No se puede asignar %(qty)s: solo hay %(avail)s disponible en la línea de OC."
                )
                % {"qty": quantity, "avail": avail}
            )

        cross_product = (
            self.env.context.get("margin_allow_cross_product_link")
            and pol.product_id
            and sol.product_id
            and pol.product_id != sol.product_id
        )
        if cross_product:
            if not pol.sale_line_id:
                pol.with_context(skip_margin_live_cost_refresh=True).write(
                    {"sale_line_id": sol.id}
                )
            ratio = (quantity / pol.product_qty) if pol.product_qty else 0.0
            return (pol.price_subtotal * ratio) if pol.product_qty else quantity * (
                pol.price_unit or 0.0
            )

        # Trace helper refuses when justech_qty_pending_purchase is 0 (e.g. stock-
        # covered). Margins still needs a commercial qty.assignment for cost share.
        linked = False
        if hasattr(pol, "justech_link_to_sale_line"):
            pending = None
            if "justech_qty_pending_purchase" in sol._fields:
                sol.invalidate_recordset(["justech_qty_pending_purchase"])
                if hasattr(sol, "_compute_justech_purchase_coverage"):
                    sol._compute_justech_purchase_coverage()
                pending = sol.justech_qty_pending_purchase or 0.0
            if pending is None or float_compare(quantity, pending, precision_digits=4) <= 0:
                try:
                    pol.justech_link_to_sale_line(sol, quantity)
                    pol.invalidate_recordset()
                    # Trace may link via:
                    # 1) qty.assignment row
                    # 2) direct sale_line_id M2O (full line)
                    # 3) split POL copy with sale_line_id
                    if "justech.purchase.sale.qty.assignment" in self.env:
                        Assign = self.env["justech.purchase.sale.qty.assignment"]
                        exists = Assign.search(
                            [
                                ("purchase_line_id", "in", pol.order_id.order_line.ids),
                                ("sale_line_id", "=", sol.id),
                                ("state", "=", "active"),
                            ],
                            limit=1,
                        )
                        if exists:
                            linked = True
                    if not linked and pol.sale_line_id == sol:
                        linked = True
                    if not linked:
                        twin = self.env["purchase.order.line"].search(
                            [
                                ("order_id", "=", pol.order_id.id),
                                ("sale_line_id", "=", sol.id),
                                ("product_id", "=", sol.product_id.id),
                                ("state", "!=", "cancel"),
                            ],
                            limit=1,
                        )
                        linked = bool(twin)
                except (UserError, ValidationError):
                    linked = False

        if not linked:
            if "justech.purchase.sale.qty.assignment" not in self.env:
                raise UserError(
                    _(
                        "El módulo de trazabilidad (qty.assignment) no está instalado; "
                        "no se puede registrar la asignación por cantidad."
                    )
                )
            # If Trace already parked the full POL on this SOL via M2O, do not
            # create a duplicate ASG (Trace would reject available=0).
            if pol.sale_line_id == sol:
                pass
            else:
                ratio = (quantity / pol.product_qty) if pol.product_qty else 0.0
                amount_for_asg = (
                    (pol.price_subtotal * ratio)
                    if pol.product_qty
                    else quantity * (pol.price_unit or 0.0)
                )
                self.env["justech.purchase.sale.qty.assignment"].create(
                    {
                        "company_id": sol.company_id.id,
                        "purchase_line_id": pol.id,
                        "sale_line_id": sol.id,
                        "quantity": quantity,
                        "amount": amount_for_asg,
                        "state": "active",
                        "note": _("Asignación comercial Margins (costo por cantidad)"),
                    }
                )

        ratio = (quantity / pol.product_qty) if pol.product_qty else 0.0
        amount = (pol.price_subtotal * ratio) if pol.product_qty else quantity * (
            pol.price_unit or 0.0
        )
        return amount

    def upsert_mtx_estimated_cost_line(
        self, transaction, pol, quantity, amount_untaxed, replace=True
    ):
        from odoo.addons.justech_purchase_sale_margin_control.models.margin_acl import (
            margin_transaction_line,
        )

        Line = self.env["purchase.sale.margin.transaction.line"]
        if self.env.context.get("margin_hub_mtx_elevate"):
            # Hub already validated sale access; elevate only MTX line writes.
            Line = margin_transaction_line(self.env)
        ratio = (quantity / pol.product_qty) if pol.product_qty else 0.0
        amount_tax = (pol.price_tax or 0.0) * ratio
        amount_total = (pol.price_total or 0.0) * ratio if pol.product_qty else (
            amount_untaxed + amount_tax
        )
        existing = Line.search(
            [
                ("transaction_id", "=", transaction.id),
                ("purchase_order_line_id", "=", pol.id),
                ("line_type", "=", "cost"),
                ("data_origin", "=", "estimated"),
            ],
            limit=1,
        )
        vals = {
            "transaction_id": transaction.id,
            "line_type": "cost",
            "data_origin": "estimated",
            "purchase_order_id": pol.order_id.id,
            "purchase_order_line_id": pol.id,
            "partner_id": pol.order_id.partner_id.id,
            "product_id": pol.product_id.id,
            "description": pol.name,
            "currency_id": pol.order_id.currency_id.id,
            "cost_usage_type": getattr(pol, "cost_usage_type", False) or "resale_direct",
            "quantity": quantity,
            "amount_untaxed": amount_untaxed,
            "amount_tax": amount_tax,
            "amount_total": amount_total,
            "is_manual": False,
            "state": "confirmed",
        }
        # Explicit hub allocation: stamp sale line when Trace M2O available.
        sol = self.env.context.get("margin_hub_sale_line_id")
        if sol and "sale_order_line_id" in Line._fields:
            vals["sale_order_line_id"] = sol
        if existing:
            if replace:
                existing.with_context(skip_line_sync=True).write(vals)
            else:
                # Cap at POL qty so re-apply cannot invent coverage (3+3→6).
                # apply_allocations_to_transaction always refreshes from live after.
                cap = pol.product_qty or 0.0
                proposed = (existing.quantity or 0.0) + quantity
                new_qty = min(proposed, cap) if float_compare(cap, 0.0, precision_digits=4) > 0 else proposed
                new_amt = self._pol_proportional_untaxed(pol, new_qty)
                ratio2 = (new_qty / pol.product_qty) if pol.product_qty else 0.0
                existing.with_context(skip_line_sync=True).write(
                    {
                        "quantity": new_qty,
                        "amount_untaxed": new_amt,
                        "amount_tax": (pol.price_tax or 0.0) * ratio2,
                        "amount_total": (pol.price_total or 0.0) * ratio2,
                    }
                )
            return existing
        return Line.create(vals)

    def apply_allocations_to_transaction(self, transaction, allocation_rows, replace=True):
        created = self.env["purchase.sale.margin.transaction.line"]
        # Aggregate by POL so one MTX cost line per POL with summed qty
        by_pol = {}
        for row in allocation_rows:
            sol = row["sale_line"]
            pol = row["purchase_line"]
            qty = row["quantity"]
            amount = self.link_pol_to_sol(pol, sol, qty)
            key = pol.id
            if key not in by_pol:
                by_pol[key] = {"pol": pol, "qty": 0.0, "amount": 0.0, "sol": sol}
            by_pol[key]["qty"] += qty
            by_pol[key]["amount"] += amount
            by_pol[key]["sol"] = sol
        for data in by_pol.values():
            sol = data.get("sol")
            svc = self
            if sol:
                svc = self.__class__(
                    self.env(context=dict(self.env.context, margin_hub_sale_line_id=sol.id))
                )
            created |= svc.upsert_mtx_estimated_cost_line(
                transaction,
                data["pol"],
                data["qty"],
                data["amount"],
                replace=replace,
            )
        # Canonical rewrite from live ASG + POL.sale_line_id (idempotent).
        self.refresh_estimated_costs_from_live_assignments(transaction)
        return created

    def confirm_unequivocal_cost_relations(self, transaction):
        """Promote draft cost.link / allocation when SOL↔POL is unequivocal.

        Unequivocal = live assignment (qty.assignment or Trace pol.sale_line_id)
        on a non-cancelled PO. Does NOT confirm product-only ambiguous suggestions
        without an explicit SOL↔POL assignment. Never deletes draft rows.
        """
        tx = transaction
        if not tx:
            return
        Link = self.env["purchase.sale.cost.link"].sudo()
        Alloc = self.env["purchase.sale.cost.allocation"].sudo()
        for so in tx.sale_order_ids:
            for row in self.collect_live_assigned_cost_rows(so):
                sol = row.get("sale_line")
                pol = row.get("purchase_line")
                if not sol or not pol:
                    continue
                if pol.state == "cancel" or pol.order_id.state == "cancel":
                    continue
                links = Link.search(
                    [
                        ("sale_line_id", "=", sol.id),
                        ("purchase_line_id", "=", pol.id),
                        ("state", "in", ("draft", "suggested")),
                    ]
                )
                if links:
                    links.write(
                        {
                            "state": "confirmed",
                            "confidence": 100,
                            "is_manual": True,
                        }
                    )
                allocs = Alloc.search(
                    [
                        ("sale_order_line_id", "=", sol.id),
                        ("purchase_order_line_id", "=", pol.id),
                        ("state", "in", ("draft", "suggested")),
                    ]
                )
                if allocs:
                    allocs.write({"state": "confirmed", "confidence": 100})

    def confirm_explicit_hub_relation(self, transaction):
        """Hub-created SOL↔POL is explicit: confirm relation automatically.

        - Cost coverage complete + valid margin → MTX validated; no finance gate.
        - Negative / anomalous margin → validated for ops but finance approval pending.
        - Partial / none → leave pending (SO shows Costos pendientes).
        - Unequivocal live SOL↔POL drafts → cost.link / allocation confirmed.
        """
        from odoo import fields as odoo_fields
        from odoo.tools.float_utils import float_compare

        tx = transaction
        if not tx:
            return
        self.confirm_unequivocal_cost_relations(tx)
        tx.invalidate_recordset()
        coverage = getattr(tx, "cost_coverage_state", False)
        if coverage != "complete":
            return
        vals = {}
        if tx.state in ("draft", "detected", "pending_review", "reopened"):
            vals.update(
                {
                    "state": "validated",
                    "validation_state": "validated",
                    "validated_by_id": self.env.user.id,
                    "validated_at": odoo_fields.Datetime.now(),
                }
            )
        # Real exception only: negative display margin → finance review.
        margin = tx.display_margin_amount
        if margin is None:
            margin = (tx.display_sale_amount or 0.0) - (tx.display_cost_amount or 0.0)
        if float_compare(margin or 0.0, 0.0, precision_digits=2) < 0:
            if getattr(tx, "approval_state", None) not in ("approved", "rejected"):
                vals["approval_state"] = "pending"
        elif getattr(tx, "approval_state", None) in (False, "not_requested", None, "pending"):
            # Normal fully-covered sale: never require finance approval.
            vals["approval_state"] = "not_requested"
        if vals:
            tx.with_context(skip_line_sync=True).write(vals)

    def _pol_proportional_untaxed(self, pol, quantity):
        """Current POL untaxed share for assigned quantity (live price)."""
        if not pol or float_compare(quantity or 0.0, 0.0, precision_digits=4) <= 0:
            return 0.0
        if pol.state == "cancel" or pol.order_id.state == "cancel":
            return 0.0
        product_qty = pol.product_qty or 0.0
        if product_qty and float_compare(product_qty, 0.0, precision_digits=4) > 0:
            return (pol.price_subtotal or 0.0) * ((quantity or 0.0) / product_qty)
        return (quantity or 0.0) * (pol.price_unit or 0.0)

    def _pol_posted_bill_qty_cost(self, pol):
        """Posted vendor-bill qty/untaxed for a POL (ignores zero-qty phantom bills)."""
        if not pol:
            return 0.0, 0.0
        qty = 0.0
        untaxed = 0.0
        for aml in pol.invoice_lines:
            move = aml.move_id
            if not move or move.state != "posted":
                continue
            if move.move_type not in ("in_invoice", "in_refund"):
                continue
            if float_is_zero(aml.quantity or 0.0, precision_digits=4):
                continue
            if float_is_zero(aml.price_subtotal or 0.0, precision_digits=2):
                continue
            sign = -1.0 if move.move_type == "in_refund" else 1.0
            qty += sign * (aml.quantity or 0.0)
            untaxed += sign * abs(aml.price_subtotal or 0.0)
        return max(qty, 0.0), max(untaxed, 0.0)

    def _split_assigned_real_estimated(self, pol, assigned_qty):
        """Split assigned qty into bill(real) + PO(estimated) without double count."""
        assigned_qty = assigned_qty or 0.0
        if float_compare(assigned_qty, 0.0, precision_digits=4) <= 0:
            return 0.0, 0.0, 0.0, 0.0
        billed_qty, billed_untaxed = self._pol_posted_bill_qty_cost(pol)
        real_qty = min(assigned_qty, billed_qty)
        est_qty = assigned_qty - real_qty
        if float_compare(billed_qty, 0.0, precision_digits=4) > 0 and float_compare(
            real_qty, 0.0, precision_digits=4
        ) > 0:
            real_cost = billed_untaxed * (real_qty / billed_qty)
        else:
            real_cost = 0.0
        est_cost = self._pol_proportional_untaxed(pol, est_qty)
        return real_qty, real_cost, est_qty, est_cost

    def collect_live_assigned_cost_rows(self, sale_order):
        """Live cost rows from ASG + Trace POL.sale_line_id (real+estimated split).

        Uses CURRENT purchase.order.line prices — never frozen MTX amounts.
        Skips cancelled POs/POLs. Posted vendor bills with qty>0 replace the
        matching assigned quantity (no OC+bill double count).
        """
        rows = []
        if not sale_order:
            return rows
        covered_pol_ids = set()
        if "justech.purchase.sale.qty.assignment" in self.env:
            Assign = self.env["justech.purchase.sale.qty.assignment"].sudo()
            for asg in Assign.search(
                [
                    ("sale_line_id.order_id", "=", sale_order.id),
                    ("state", "=", "active"),
                ]
            ):
                pol = asg.purchase_line_id
                sol = asg.sale_line_id
                if not pol or not sol:
                    continue
                if pol.state == "cancel" or pol.order_id.state == "cancel":
                    continue
                qty = asg.quantity or 0.0
                if float_compare(qty, 0.0, precision_digits=4) <= 0:
                    continue
                real_qty, real_cost, est_qty, est_cost = self._split_assigned_real_estimated(
                    pol, qty
                )
                unit = (
                    (pol.price_subtotal or 0.0) / pol.product_qty
                    if pol.product_qty
                    else (pol.price_unit or 0.0)
                )
                rows.append(
                    {
                        "sale_line": sol,
                        "product": sol.product_id,
                        "sold_qty": sol.product_uom_qty or 0.0,
                        "purchase_order": pol.order_id,
                        "purchase_line": pol,
                        "po_qty": pol.product_qty or 0.0,
                        "assigned_qty": qty,
                        "real_qty": real_qty,
                        "real_cost": real_cost,
                        "estimated_qty": est_qty,
                        "estimated_cost": est_cost,
                        "unit_cost": unit,
                        "cost": real_cost + est_cost,
                        "source": "qty.assignment",
                    }
                )
                covered_pol_ids.add(pol.id)
        # Trace full-line M2O (no ASG row)
        pols = (
            self.env["purchase.order.line"]
            .sudo()
            .search(
                [
                    ("sale_line_id.order_id", "=", sale_order.id),
                    ("state", "!=", "cancel"),
                    ("order_id.state", "!=", "cancel"),
                ]
            )
        )
        for pol in pols:
            if pol.id in covered_pol_ids:
                continue
            sol = pol.sale_line_id
            qty = pol.product_qty or 0.0
            # Never cover this sale beyond what was sold on the linked SOL.
            if sol:
                sold = self.sol_final_sale_qty(sol)
                qty = min(qty, sold)
            if float_compare(qty, 0.0, precision_digits=4) <= 0:
                continue
            real_qty, real_cost, est_qty, est_cost = self._split_assigned_real_estimated(
                pol, qty
            )
            unit = (
                (pol.price_subtotal or 0.0) / pol.product_qty
                if pol.product_qty
                else (pol.price_unit or 0.0)
            )
            rows.append(
                {
                    "sale_line": sol,
                    "product": sol.product_id,
                    "sold_qty": sol.product_uom_qty or 0.0,
                    "purchase_order": pol.order_id,
                    "purchase_line": pol,
                    "po_qty": pol.product_qty or 0.0,
                    "assigned_qty": qty,
                    "real_qty": real_qty,
                    "real_cost": real_cost,
                    "estimated_qty": est_qty,
                    "estimated_cost": est_cost,
                    "unit_cost": unit,
                    "cost": real_cost + est_cost,
                    "source": "pol.sale_line_id",
                }
            )
        return rows

    def refresh_estimated_costs_from_live_assignments(self, transaction):
        """Rewrite MTX cost lines from live assignments (estimated + real split).

        For each POL assignment:
        - billed qty (posted bill with amount) → accounting line
        - remainder → estimated line from live POL price
        No OC+bill double count.
        """
        from odoo.addons.justech_purchase_sale_margin_control.models.margin_acl import (
            margin_transaction_line,
        )

        tx = transaction
        if not tx:
            return
        Line = margin_transaction_line(self.env)
        live_by_pol = {}
        for so in tx.sale_order_ids:
            for row in self.collect_live_assigned_cost_rows(so):
                pol = row["purchase_line"]
                key = pol.id
                if key not in live_by_pol:
                    live_by_pol[key] = {
                        "pol": pol,
                        "assigned_qty": 0.0,
                        "real_qty": 0.0,
                        "real_cost": 0.0,
                        "estimated_qty": 0.0,
                        "estimated_cost": 0.0,
                        "sol": row["sale_line"],
                        "_sol_ids": set(),
                    }
                sol = row["sale_line"]
                sol_id = sol.id if sol else False
                # Same SOL must not contribute twice if sale_order_ids loops oddly.
                if sol_id and sol_id in live_by_pol[key]["_sol_ids"]:
                    continue
                if sol_id:
                    live_by_pol[key]["_sol_ids"].add(sol_id)
                live_by_pol[key]["assigned_qty"] += row["assigned_qty"]
                live_by_pol[key]["real_qty"] += row.get("real_qty") or 0.0
                live_by_pol[key]["real_cost"] += row.get("real_cost") or 0.0
                live_by_pol[key]["estimated_qty"] += row.get("estimated_qty") or 0.0
                live_by_pol[key]["estimated_cost"] += row.get("estimated_cost") or 0.0
                live_by_pol[key]["sol"] = row["sale_line"]

        # Exclude stale *purchase-linked* cost lines for cancelled / removed POLs.
        # NEVER exclude inventory/manual lines: they have no POL by design and are
        # explicit cost coverage (hub "Usar inventario").
        cost_lines = Line.search(
            [
                ("transaction_id", "=", tx.id),
                ("line_type", "=", "cost"),
                ("state", "!=", "excluded"),
            ]
        )
        for el in cost_lines:
            if getattr(el, "cost_source", None) in ("inventory", "manual"):
                continue
            pol = el.purchase_order_line_id
            if (
                not pol
                or pol.state == "cancel"
                or pol.order_id.state == "cancel"
                or pol.id not in live_by_pol
            ):
                el.with_context(skip_line_sync=True).write({"state": "excluded"})

        # Reinstate inventory/manual lines wrongly excluded by older refresh logic.
        wrongly_excluded = Line.search(
            [
                ("transaction_id", "=", tx.id),
                ("line_type", "=", "cost"),
                ("state", "=", "excluded"),
                ("cost_source", "in", ("inventory", "manual")),
                ("quantity", ">", 0),
            ]
        )
        if wrongly_excluded:
            wrongly_excluded.with_context(skip_line_sync=True).write(
                {"state": "confirmed"}
            )

        for pol_id, data in live_by_pol.items():
            pol = data["pol"]
            sol = data.get("sol")
            # Cap real+estimated at POL qty (never invent coverage beyond the purchase line).
            cap = pol.product_qty or 0.0
            total_q = (data.get("real_qty") or 0.0) + (data.get("estimated_qty") or 0.0)
            if (
                float_compare(cap, 0.0, precision_digits=4) > 0
                and float_compare(total_q, cap, precision_digits=4) > 0
                and total_q
            ):
                scale = cap / total_q
                data["real_qty"] = (data.get("real_qty") or 0.0) * scale
                data["real_cost"] = (data.get("real_cost") or 0.0) * scale
                data["estimated_qty"] = (data.get("estimated_qty") or 0.0) * scale
                data["estimated_cost"] = (data.get("estimated_cost") or 0.0) * scale
                data["assigned_qty"] = data["real_qty"] + data["estimated_qty"]
            # --- estimated portion ---
            est_lines = Line.search(
                [
                    ("transaction_id", "=", tx.id),
                    ("purchase_order_line_id", "=", pol_id),
                    ("line_type", "=", "cost"),
                    ("data_origin", "=", "estimated"),
                    ("state", "!=", "excluded"),
                ]
            )
            if float_compare(data["estimated_qty"], 0.0, precision_digits=4) > 0:
                ratio = (
                    (data["estimated_qty"] / pol.product_qty) if pol.product_qty else 0.0
                )
                vals = {
                    "quantity": data["estimated_qty"],
                    "amount_untaxed": data["estimated_cost"],
                    "amount_tax": (pol.price_tax or 0.0) * ratio,
                    "amount_total": (pol.price_total or 0.0) * ratio
                    if pol.product_qty
                    else data["estimated_cost"],
                    "purchase_order_id": pol.order_id.id,
                    "product_id": pol.product_id.id,
                    "state": "confirmed",
                    "data_origin": "estimated",
                    "cost_source": "direct_purchase",
                }
                if "sale_order_line_id" in Line._fields and sol:
                    vals["sale_order_line_id"] = sol.id
                if est_lines:
                    est_lines[0].with_context(skip_line_sync=True).write(vals)
                    (est_lines - est_lines[0]).with_context(skip_line_sync=True).write(
                        {"state": "excluded"}
                    )
                else:
                    ctx = dict(self.env.context, margin_hub_mtx_elevate=True)
                    if sol:
                        ctx["margin_hub_sale_line_id"] = sol.id
                    self.__class__(self.env(context=ctx)).upsert_mtx_estimated_cost_line(
                        tx,
                        pol,
                        data["estimated_qty"],
                        data["estimated_cost"],
                        replace=True,
                    )
            else:
                if est_lines:
                    est_lines.with_context(skip_line_sync=True).write({"state": "excluded"})

            # --- real / accounting portion ---
            acc_lines = Line.search(
                [
                    ("transaction_id", "=", tx.id),
                    ("purchase_order_line_id", "=", pol_id),
                    ("line_type", "=", "cost"),
                    ("data_origin", "=", "accounting"),
                    ("state", "!=", "excluded"),
                ]
            )
            if float_compare(data["real_qty"], 0.0, precision_digits=4) > 0:
                bill = False
                for aml in pol.invoice_lines.filtered(
                    lambda l: l.move_id.state == "posted"
                    and l.move_id.move_type in ("in_invoice", "in_refund")
                    and not float_is_zero(l.quantity or 0.0, precision_digits=4)
                ):
                    bill = aml.move_id
                    break
                vals = {
                    "quantity": data["real_qty"],
                    "amount_untaxed": data["real_cost"],
                    "amount_total": data["real_cost"],
                    "amount_company_currency": data["real_cost"],
                    "purchase_order_id": pol.order_id.id,
                    "product_id": pol.product_id.id,
                    "state": "confirmed",
                    "data_origin": "accounting",
                    "account_move_id": bill.id if bill else False,
                    "description": _("%s (costo real factura)")
                    % ((bill.name or bill.display_name) if bill else _("factura")),
                }
                if "sale_order_line_id" in Line._fields and sol:
                    vals["sale_order_line_id"] = sol.id
                if acc_lines:
                    acc_lines[0].with_context(skip_line_sync=True).write(vals)
                    (acc_lines - acc_lines[0]).with_context(skip_line_sync=True).write(
                        {"state": "excluded"}
                    )
                else:
                    create_vals = {
                        "transaction_id": tx.id,
                        "line_type": "cost",
                        "purchase_order_line_id": pol.id,
                        **vals,
                    }
                    Line.with_context(skip_line_sync=True).create(create_vals)
                if bill:
                    tx.with_context(skip_line_sync=True).write(
                        {"vendor_bill_ids": [(4, bill.id)]}
                    )
            else:
                if acc_lines:
                    acc_lines.with_context(skip_line_sync=True).write({"state": "excluded"})

        tx.invalidate_recordset(
            [
                "cost_estimated_amount",
                "cost_real_amount",
                "display_cost_amount",
                "estimated_margin",
                "real_margin",
            ]
        )
        if hasattr(tx, "_compute_amounts"):
            tx._compute_amounts()

    def refresh_estimated_to_real_from_bill(self, bill):
        """After posting a vendor bill: refresh related MTX from live split.

        Zero-qty / zero-amount bills only get document link; they never wipe PO cost.
        """
        if bill.move_type not in ("in_invoice", "in_refund") or bill.state != "posted":
            return
        Line = self.env["purchase.sale.margin.transaction.line"]
        pols = bill.invoice_line_ids.mapped("purchase_line_id")
        if not pols:
            return
        txs = Line.search(
            [
                ("purchase_order_line_id", "in", pols.ids),
                ("line_type", "=", "cost"),
                ("state", "!=", "excluded"),
            ]
        ).mapped("transaction_id")
        # Also find MTX via PO M2M
        Tx = self.env["purchase.sale.margin.transaction"]
        txs |= Tx.search([("purchase_order_ids", "in", pols.mapped("order_id").ids)])
        for tx in txs:
            tx.with_context(skip_line_sync=True).write({"vendor_bill_ids": [(4, bill.id)]})
            if float_is_zero(bill.amount_untaxed or 0.0, precision_digits=2) and float_is_zero(
                bill.amount_total or 0.0, precision_digits=2
            ):
                continue
            self.refresh_estimated_costs_from_live_assignments(tx)
            self.confirm_explicit_hub_relation(tx)
            for so in tx.sale_order_ids:
                so.invalidate_recordset(
                    [
                        "real_cost_amount",
                        "estimated_cost_amount",
                        "margin_control_cost",
                        "margin_control_margin",
                        "margin_control_margin_pct",
                        "margin_control_state",
                        "margin_control_cost_origin",
                    ]
                )

    def suggest_unique_product_pairs(self, sale_orders, purchase_orders):
        pairs = []
        sols = sale_orders.mapped("order_line").filtered(_is_product_line)
        pols = purchase_orders.mapped("order_line").filtered(_is_product_line)
        for sol in sols:
            matches = pols.filtered(lambda p, s=sol: p.product_id == s.product_id)
            if len(matches) != 1:
                continue
            pol = matches[0]
            reverse = sols.filtered(lambda s, p=pol: s.product_id == p.product_id)
            if len(reverse) != 1:
                continue
            pairs.append((sol, pol))
        return pairs

    def analyze_transaction_sale_cost_coverage(self, transaction):
        """Per sold/invoiced SOL: sold, purchase ASG, historical/manual, pending."""
        rows = []
        invoices = transaction.customer_invoice_ids.filtered(
            lambda m: m.state == "posted"
            and m.move_type in ("out_invoice", "out_refund")
        )
        sols = transaction.sale_order_ids.mapped("order_line").filtered(_is_product_line)
        # Also include SOLs only reachable from invoices on the hub
        if invoices:
            sols |= invoices.mapped("invoice_line_ids.sale_line_ids").filtered(_is_product_line)
        for sol in sols:
            sold = self.sol_final_sale_qty(sol, invoice_moves=invoices or None)
            if float_compare(sold, 0.0, precision_digits=4) <= 0:
                continue
            purchase_qty = min(self.sol_qty_assigned_to_purchase(sol), sold)
            hist_qty = min(
                self.sol_qty_historical_manual(sol, transaction=transaction),
                max(sold - purchase_qty, 0.0),
            )
            # assigned_qty = purchase + historical (legacy banner / provisional checks)
            assigned_disp = min(purchase_qty + hist_qty, sold)
            pending = max(sold - assigned_disp, 0.0)
            doc = sol.order_id.name or ""
            if invoices:
                inv_names = sol.invoice_lines.filtered(
                    lambda l: l.move_id in invoices
                ).mapped("move_id.name")
                if inv_names:
                    doc = ", ".join(dict.fromkeys(inv_names))
            rows.append(
                {
                    "sale_line_id": sol.id,
                    "product_id": sol.product_id.id,
                    "product_name": sol.product_id.display_name or sol.name,
                    "sale_doc": doc,
                    "sold_qty": sold,
                    "purchase_qty": purchase_qty,
                    "historical_qty": hist_qty,
                    "assigned_qty": assigned_disp,
                    "pending_qty": pending,
                }
            )
        return rows
