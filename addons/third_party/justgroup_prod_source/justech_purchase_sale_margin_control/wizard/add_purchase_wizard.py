# -*- coding: utf-8 -*-
"""19.0.3.0.0 — Requerimiento 1: agregar múltiples órdenes de compra a una
sola operación de margen (purchase.sale.margin.transaction), ya sea desde la
propia operación, desde una orden de venta o desde una factura de cliente.

Nunca escribe asientos contables; solo crea/actualiza líneas de operación
(``purchase.sale.margin.transaction.line``, data_origin='estimated') y, si
existe un lado de venta identificable, una asignación de costo sugerida
(``purchase.sale.cost.allocation``).
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools.float_utils import float_compare, float_is_zero

from ..models.cost_link import COST_USAGE


class PurchaseSaleAddPurchaseWizard(models.TransientModel):
    _name = "purchase.sale.add.purchase.wizard"
    _description = "Agregar órdenes de compra a una operación de margen"

    company_id = fields.Many2one(
        "res.company", string="Compañía", default=lambda self: self.env.company, required=True
    )
    transaction_id = fields.Many2one(
        "purchase.sale.margin.transaction", string="Operación de margen",
        domain="[('company_id', '=', company_id)]",
    )
    sale_order_id = fields.Many2one(
        "sale.order", string="Orden de venta", domain="[('company_id', '=', company_id)]",
    )
    customer_invoice_id = fields.Many2one(
        "account.move", string="Factura de cliente",
        domain="[('company_id', '=', company_id), ('move_type', 'in', ('out_invoice', 'out_refund'))]",
    )
    purchase_order_ids = fields.Many2many(
        "purchase.order",
        "psm_add_po_wiz_po_rel", "wizard_id", "purchase_order_id",
        string="Órdenes de compra a agregar",
        # Confirmed/received/billed may still have commercial qty available via ASG.
        domain="[('company_id', '=', company_id), ('state', '!=', 'cancel')]",
    )
    line_ids = fields.One2many(
        "purchase.sale.add.purchase.wizard.line", "wizard_id", string="Líneas de OC",
    )
    notes = fields.Char(string="Notas")

    # ------------------------------------------------------------------
    # Onchange: rebuild wizard lines from selected POs (no manual typing)
    # ------------------------------------------------------------------
    @api.onchange("purchase_order_ids", "company_id")
    def _onchange_purchase_order_ids(self):
        self.line_ids = [(5, 0, 0)]
        if not self.purchase_order_ids:
            return
        Line = self.env["purchase.sale.add.purchase.wizard.line"]
        new_lines = []
        for po in self.purchase_order_ids:
            for po_line in po.order_line.filtered(lambda l: not l.display_type):
                qty_elsewhere = Line._qty_assigned_elsewhere(
                    po_line, exclude_transaction=self.transaction_id
                )
                qty_available = max(po_line.product_qty - qty_elsewhere, 0.0)
                # Never pre-assign the full residual: user must choose qty explicitly.
                new_lines.append(
                    (0, 0, {
                        "purchase_order_id": po.id,
                        "purchase_line_id": po_line.id,
                        "product_id": po_line.product_id.id,
                        "description": po_line.name,
                        "product_qty": po_line.product_qty,
                        "qty_received": po_line.qty_received,
                        "qty_invoiced": po_line.qty_invoiced,
                        "qty_available": qty_available,
                        "qty_to_assign": 0.0,
                        "price_unit": po_line.price_unit,
                        "price_subtotal": po_line.price_subtotal,
                        "price_tax": po_line.price_tax,
                        "price_total": po_line.price_total,
                        "currency_id": po.currency_id.id,
                        "cost_usage_type": getattr(po_line, "cost_usage_type", False),
                        "selected": False,
                        "assigned_amount_elsewhere": qty_elsewhere * po_line.price_unit,
                        "available_amount": qty_available * po_line.price_unit,
                    })
                )
        self.line_ids = new_lines

    def action_refresh_lines(self):
        """Button fallback for clients where the onchange did not trigger
        (e.g. XML-RPC / tests using write() instead of onchange)."""
        self.ensure_one()
        self._onchange_purchase_order_ids()
        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }

    # ------------------------------------------------------------------
    # Transaction resolution
    # ------------------------------------------------------------------
    def _get_or_create_transaction(self):
        self.ensure_one()
        Transaction = self.env["purchase.sale.margin.transaction"]
        if self.transaction_id:
            return self.transaction_id

        if self.sale_order_id:
            if self.sale_order_id.company_id and self.sale_order_id.company_id != self.company_id:
                raise ValidationError(_("La orden de venta pertenece a otra compañía."))
            return Transaction.find_or_create_canonical_transaction(
                sale_order=self.sale_order_id,
                vals={
                    "company_id": self.company_id.id,
                    "name": self.sale_order_id.name,
                    "source": "manual",
                    "state": "draft",
                },
            )

        if self.customer_invoice_id:
            if self.customer_invoice_id.company_id and self.customer_invoice_id.company_id != self.company_id:
                raise ValidationError(_("La factura de cliente pertenece a otra compañía."))
            return Transaction.find_or_create_canonical_transaction(
                customer_invoice=self.customer_invoice_id,
                vals={
                    "company_id": self.company_id.id,
                    "source": "manual",
                    "state": "draft",
                },
            )

        raise UserError(
            _("Seleccione una operación de margen, una orden de venta o una factura de "
              "cliente como contexto para agregar órdenes de compra.")
        )

    def _resolve_single_sale_order(self, transaction):
        """Best-effort single sale.order to suggest a cost allocation against.
        Returns an empty recordset when ambiguous (more than one candidate)."""
        if self.sale_order_id:
            return self.sale_order_id
        if self.customer_invoice_id:
            related_so = self.customer_invoice_id.invoice_line_ids.mapped("sale_line_ids.order_id")
            if len(related_so) == 1:
                return related_so
        if len(transaction.sale_order_ids) == 1:
            return transaction.sale_order_ids
        return self.env["sale.order"]

    # ------------------------------------------------------------------
    # Confirm
    # ------------------------------------------------------------------
    def action_confirm(self):
        self.ensure_one()
        if not self.purchase_order_ids:
            raise UserError(
                _(
                    "No se seleccionó ninguna Orden de Compra. "
                    "Seleccione una OC o una factura de proveedor para continuar."
                )
            )

        selected_lines = self.line_ids.filtered(lambda l: l.selected and not float_is_zero(l.qty_to_assign, precision_digits=4))
        if not selected_lines:
            raise UserError(_("No hay líneas seleccionadas con cantidad a asignar mayor que cero."))

        for po in self.purchase_order_ids:
            if po.state == "cancel":
                raise UserError(_("La orden de compra %s está cancelada.") % po.name)
            if po.company_id and po.company_id != self.company_id:
                raise UserError(
                    _("La orden de compra %s pertenece a otra compañía.") % po.name
                )

        transaction = self._get_or_create_transaction()
        if transaction.company_id != self.company_id:
            raise ValidationError(
                _("La operación %s pertenece a otra compañía.") % transaction.transaction_number
            )

        # skip_line_sync: avoid the generic whole-PO estimated line the base
        # write() would auto-create (models/margin_transaction.py); this
        # wizard creates precise per-PO-line estimated cost lines below and
        # triggers a single explicit _sync_lines_from_documents() at the end.
        transaction.with_context(skip_line_sync=True).write(
            {"purchase_order_ids": [(4, po.id) for po in self.purchase_order_ids]}
        )

        sale_target = self._resolve_single_sale_order(transaction)
        Line = self.env["purchase.sale.margin.transaction.line"]
        Allocation = self.env["purchase.sale.cost.allocation"]
        created_lines = Line
        created_allocations = Allocation

        for wline in selected_lines:
            po_line = wline.purchase_line_id
            po = wline.purchase_order_id
            if po.state == "cancel":
                raise UserError(_("La línea de %s referencia una orden cancelada.") % po.name)
            if po.company_id != self.company_id:
                raise UserError(_("No se permiten líneas de otra compañía."))

            qty_elsewhere = self.env["purchase.sale.add.purchase.wizard.line"]._qty_assigned_elsewhere(
                po_line, exclude_transaction=transaction
            )
            available = max(po_line.product_qty - qty_elsewhere, 0.0)
            if float_compare(wline.qty_to_assign, available, precision_digits=4) > 0:
                raise UserError(
                    _(
                        "No se puede asignar %(qty)s de %(product)s: solo hay %(avail)s "
                        "disponible sin asignar en otras operaciones."
                    )
                    % {
                        "qty": wline.qty_to_assign,
                        "product": po_line.product_id.display_name or po_line.name,
                        "avail": available,
                    }
                )

            ratio = (wline.qty_to_assign / po_line.product_qty) if po_line.product_qty else 0.0
            # Prefer price_subtotal (post-discount untaxed) so costs never stay at 0
            # when the OC line has a real price but price_unit edge-cases mislead.
            amount_untaxed = (po_line.price_subtotal * ratio) if po_line.product_qty else 0.0
            if float_is_zero(amount_untaxed, precision_digits=2) and not float_is_zero(
                po_line.price_unit, precision_digits=4
            ):
                amount_untaxed = wline.qty_to_assign * po_line.price_unit
            amount_tax = po_line.price_tax * ratio
            amount_total = po_line.price_total * ratio if po_line.product_qty else (amount_untaxed + amount_tax)
            if float_is_zero(amount_untaxed, precision_digits=2) and float_compare(
                po_line.price_subtotal, 0.0, precision_digits=2
            ) > 0:
                raise UserError(
                    _("La línea de compra no tiene costo válido: %s")
                    % (po_line.product_id.display_name or po_line.name)
                )

            existing_line = Line.search(
                [
                    ("transaction_id", "=", transaction.id),
                    ("purchase_order_line_id", "=", po_line.id),
                    ("line_type", "=", "cost"),
                    ("data_origin", "=", "estimated"),
                ],
                limit=1,
            )
            vals = {
                "transaction_id": transaction.id,
                "line_type": "cost",
                "data_origin": "estimated",
                "purchase_order_id": po.id,
                "purchase_order_line_id": po_line.id,
                "partner_id": po.partner_id.id,
                "product_id": po_line.product_id.id,
                "description": wline.description or po_line.name,
                "currency_id": po.currency_id.id,
                "cost_usage_type": wline.cost_usage_type or getattr(po_line, "cost_usage_type", False),
                "quantity": wline.qty_to_assign,
                "amount_untaxed": amount_untaxed,
                "amount_tax": amount_tax,
                "amount_total": amount_total,
                "is_manual": False,
            }
            if existing_line:
                existing_line.with_context(skip_line_sync=True).write(vals)
                created_lines |= existing_line
            else:
                created_lines |= Line.create(vals)

            if sale_target:
                remaining_bill_alloc = amount_untaxed - sum(
                    Allocation.search(
                        [
                            ("purchase_order_line_id", "=", po_line.id),
                            ("sale_order_id", "=", sale_target.id),
                            ("state", "not in", ("cancelled", "excluded")),
                        ]
                    ).mapped("allocated_amount")
                )
                if float_compare(remaining_bill_alloc, 0.0, precision_digits=2) > 0:
                    created_allocations |= Allocation.create(
                        {
                            "company_id": self.company_id.id,
                            "transaction_id": transaction.id,
                            "purchase_order_id": po.id,
                            "purchase_order_line_id": po_line.id,
                            "sale_order_id": sale_target.id,
                            "partner_id": sale_target.partner_id.id,
                            "supplier_id": po.partner_id.id,
                            "product_id": po_line.product_id.id,
                            "currency_id": po.currency_id.id,
                            "source_amount": po_line.price_subtotal,
                            "allocated_amount": remaining_bill_alloc,
                            "allocation_method": "qty",
                            "cost_usage_type": wline.cost_usage_type or getattr(po_line, "cost_usage_type", False),
                            "source": "rule",
                            "confidence": 80,
                            "is_manual": False,
                            "state": "suggested",
                        }
                    )

        # Attach related vendor bills already generated from the added POs.
        bills = self.env["account.move"]
        for po in self.purchase_order_ids:
            po_bills = getattr(po, "invoice_ids", self.env["account.move"])
            bills |= po_bills.filtered(lambda m: m.move_type in ("in_invoice", "in_refund") and m.state != "cancel")
        if bills:
            transaction.with_context(skip_line_sync=True).write(
                {"vendor_bill_ids": [(4, b.id) for b in bills]}
            )

        transaction._sync_lines_from_documents()

        # Explicit "Agregar / relacionar compra" OR origin-exact / sale_line_id → confirm
        if transaction._has_confirmed_sale_po_relation():
            transaction.sudo().action_auto_confirm_strong_trace()

        po_names = ", ".join(self.purchase_order_ids.mapped("name"))
        sale_label = (
            sale_target.name
            if sale_target
            else (transaction.primary_sale_order_id.name if transaction.primary_sale_order_id else transaction.transaction_number)
        )
        cost_sum = sum(created_lines.mapped("amount_untaxed"))
        transaction.message_post(
            body=_(
                "El sistema cargó las órdenes de compra %(pos)s como costo de %(sale)s "
                "por %(amount)s (%(user)s).%(notes)s"
            )
            % {
                "user": self.env.user.display_name,
                "pos": po_names,
                "sale": sale_label,
                "amount": cost_sum,
                "notes": (" " + _("Observaciones: %s") % self.notes) if self.notes else "",
            }
        )
        transaction._repair_zero_cost_lines()

        return {
            "type": "ir.actions.act_window",
            "name": _("Operación de margen"),
            "res_model": "purchase.sale.margin.transaction",
            "view_mode": "form",
            "res_id": transaction.id,
        }


class PurchaseSaleAddPurchaseWizardLine(models.TransientModel):
    _name = "purchase.sale.add.purchase.wizard.line"
    _description = "Línea del asistente de múltiples órdenes de compra"
    _order = "purchase_order_id, id"

    wizard_id = fields.Many2one(
        "purchase.sale.add.purchase.wizard", required=True, ondelete="cascade"
    )
    purchase_order_id = fields.Many2one("purchase.order", string="Orden de compra")
    purchase_line_id = fields.Many2one("purchase.order.line", string="Línea de OC")
    product_id = fields.Many2one("product.product", string="Producto")
    description = fields.Char(string="Descripción")

    product_qty = fields.Float(string="Cantidad OC")
    qty_received = fields.Float(string="Cantidad recibida")
    qty_invoiced = fields.Float(string="Cantidad facturada")
    qty_available = fields.Float(
        string="Cantidad disponible",
        help="Cantidad de la línea de OC aún no asignada a ninguna operación de margen.",
    )
    qty_to_assign = fields.Float(string="Cantidad a asignar")

    price_unit = fields.Float(string="Precio unitario")
    price_subtotal = fields.Monetary(string="Subtotal OC", currency_field="currency_id")
    price_tax = fields.Monetary(string="Impuesto OC", currency_field="currency_id")
    price_total = fields.Monetary(string="Total OC", currency_field="currency_id")
    currency_id = fields.Many2one("res.currency", string="Moneda")

    cost_usage_type = fields.Selection(COST_USAGE, string="Clasificación de costo")
    selected = fields.Boolean(string="Seleccionada", default=False)

    available_amount = fields.Monetary(string="Monto disponible", currency_field="currency_id")
    assigned_amount_elsewhere = fields.Monetary(
        string="Monto ya asignado (otras operaciones)", currency_field="currency_id"
    )

    @api.onchange("qty_to_assign")
    def _onchange_qty_to_assign(self):
        for rec in self:
            if float_compare(rec.qty_to_assign, rec.qty_available, precision_digits=4) > 0:
                rec.qty_to_assign = rec.qty_available

    @staticmethod
    def _qty_assigned_elsewhere(purchase_line, exclude_transaction=False):
        """Commercial qty already assigned: prefer Trace qty.assignment ledger."""
        env = purchase_line.env
        if "justech.purchase.sale.qty.assignment" in env:
            Assign = env["justech.purchase.sale.qty.assignment"]
            domain = [
                ("purchase_line_id", "=", purchase_line.id),
                ("state", "=", "active"),
            ]
            return sum(Assign.search(domain).mapped("quantity"))
        # Fallback: estimated MTX cost lines (legacy when Trace is absent)
        Line = env["purchase.sale.margin.transaction.line"]
        domain = [
            ("purchase_order_line_id", "=", purchase_line.id),
            ("line_type", "=", "cost"),
            ("data_origin", "=", "estimated"),
            ("state", "!=", "excluded"),
        ]
        if exclude_transaction:
            domain.append(("transaction_id", "!=", exclude_transaction.id))
        lines = Line.search(domain)
        return sum(lines.mapped("quantity"))
