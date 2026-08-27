# -*- coding: utf-8 -*-
"""19.0.3.0.0 — Requerimiento 2: relacionar una factura de proveedor (y su
auxiliar de CxP) con una o varias ventas (operaciones / órdenes de venta /
facturas de cliente), en ambos sentidos N:N. Nunca escribe asientos
contables; solo actualiza relaciones de control y crea asignaciones de
costo sugeridas."""
from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools.float_utils import float_compare


class PurchaseSaleRelateSaleWizard(models.TransientModel):
    _name = "purchase.sale.relate.sale.wizard"
    _description = "Relacionar factura de proveedor con ventas"

    company_id = fields.Many2one(
        "res.company", string="Compañía", default=lambda self: self.env.company, required=True
    )
    payable_auxiliary_id = fields.Many2one(
        "purchase.sale.payable.auxiliary", string="Auxiliar CxP",
        domain="[('company_id', '=', company_id)]",
    )
    vendor_bill_id = fields.Many2one(
        "account.move", string="Factura de proveedor",
        domain="[('company_id', '=', company_id), ('move_type', 'in', ('in_invoice', 'in_refund'))]",
    )
    transaction_ids = fields.Many2many(
        "purchase.sale.margin.transaction",
        "psm_relate_wiz_tx_rel", "wizard_id", "transaction_id",
        string="Operaciones de margen",
        domain="[('company_id', '=', company_id)]",
    )
    sale_order_ids = fields.Many2many(
        "sale.order",
        "psm_relate_wiz_so_rel", "wizard_id", "sale_order_id",
        string="Órdenes de venta", domain="[('company_id', '=', company_id)]",
    )
    customer_invoice_ids = fields.Many2many(
        "account.move", "psm_relate_wiz_inv_rel", "wizard_id", "move_id",
        string="Facturas de cliente",
        domain="[('company_id', '=', company_id), ('move_type', 'in', ('out_invoice', 'out_refund'))]",
    )
    notes = fields.Char(string="Notas")

    @api.onchange("payable_auxiliary_id")
    def _onchange_payable_auxiliary_id(self):
        if self.payable_auxiliary_id:
            self.vendor_bill_id = self.payable_auxiliary_id.vendor_bill_id
            self.transaction_ids = self.payable_auxiliary_id.transaction_ids
            self.sale_order_ids = self.payable_auxiliary_id.sale_order_ids
            self.customer_invoice_ids = self.payable_auxiliary_id.customer_invoice_ids

    def _get_or_create_auxiliary(self):
        self.ensure_one()
        if self.payable_auxiliary_id:
            return self.payable_auxiliary_id
        if not self.vendor_bill_id:
            raise UserError(_("Seleccione una factura de proveedor o un auxiliar existente."))
        Auxiliary = self.env["purchase.sale.payable.auxiliary"]
        existing = Auxiliary.search([("vendor_bill_id", "=", self.vendor_bill_id.id)], limit=1)
        if existing:
            return existing
        return Auxiliary.create(
            {
                "company_id": self.company_id.id,
                "vendor_bill_id": self.vendor_bill_id.id,
            }
        )

    def _get_or_create_transaction_for_sale(self, sale_order=None, customer_invoice=None):
        Transaction = self.env["purchase.sale.margin.transaction"]
        if sale_order:
            return Transaction.find_or_create_canonical_transaction(
                sale_order=sale_order,
                vals={"company_id": self.company_id.id, "source": "manual", "state": "draft"},
            )
        if customer_invoice:
            return Transaction.find_or_create_canonical_transaction(
                customer_invoice=customer_invoice,
                vals={"company_id": self.company_id.id, "source": "manual", "state": "draft"},
            )
        return Transaction

    def action_confirm(self):
        self.ensure_one()
        if not (self.transaction_ids or self.sale_order_ids or self.customer_invoice_ids):
            raise UserError(_("Seleccione al menos una operación, orden de venta o factura de cliente."))

        for docs in (self.transaction_ids, self.sale_order_ids, self.customer_invoice_ids):
            mismatched = docs.filtered(lambda d: d.company_id and d.company_id != self.company_id)
            if mismatched:
                raise ValidationError(_("No se permiten relaciones entre compañías distintas."))

        auxiliary = self._get_or_create_auxiliary()
        bill = auxiliary.vendor_bill_id
        if bill.state == "cancel":
            raise UserError(_("No se puede relacionar una factura de proveedor cancelada."))

        transactions = self.env["purchase.sale.margin.transaction"] | self.transaction_ids
        for so in self.sale_order_ids:
            transactions |= self._get_or_create_transaction_for_sale(sale_order=so)
        for inv in self.customer_invoice_ids:
            transactions |= self._get_or_create_transaction_for_sale(customer_invoice=inv)

        auxiliary.write(
            {
                "transaction_ids": [(4, tx.id) for tx in transactions],
                "sale_order_ids": [(4, so.id) for so in self.sale_order_ids],
                "customer_invoice_ids": [(4, inv.id) for inv in self.customer_invoice_ids],
            }
        )

        # Sprint 6: vendor bill belongs to exactly one transaction.
        # Prefer an existing tx that already holds the bill; else merge sales into one preferred tx.
        preferred = transactions.filtered(lambda t: bill in t.vendor_bill_ids)[:1]
        if not preferred:
            preferred = transactions[:1]
        if preferred and len(transactions) > 1:
            other_sos = transactions.mapped("sale_order_ids")
            other_invs = transactions.mapped("customer_invoice_ids")
            preferred.with_context(skip_line_sync=True).write(
                {
                    "sale_order_ids": [(4, so.id) for so in other_sos],
                    "customer_invoice_ids": [(4, inv.id) for inv in other_invs],
                    "vendor_bill_ids": [(4, bill.id)],
                }
            )
            transactions = preferred
        elif preferred:
            preferred.with_context(skip_line_sync=True).write({"vendor_bill_ids": [(4, bill.id)]})
            transactions = preferred

        Allocation = self.env["purchase.sale.cost.allocation"]
        already_allocated = sum(
            Allocation.search(
                [("vendor_bill_id", "=", bill.id), ("state", "not in", ("cancelled", "excluded"))]
            ).mapped("allocated_amount")
        )
        remaining = abs(bill.amount_untaxed) - already_allocated

        for tx in transactions:
            sale_target = tx.sale_order_ids[:1]
            if remaining > 0 and float_compare(remaining, 0.0, precision_digits=2) > 0:
                share = remaining / max(len(transactions), 1)
                Allocation.create(
                    {
                        "company_id": self.company_id.id,
                        "transaction_id": tx.id,
                        "vendor_bill_id": bill.id,
                        "sale_order_id": sale_target.id if sale_target else False,
                        "partner_id": sale_target.partner_id.id if sale_target else False,
                        "supplier_id": bill.partner_id.id,
                        "currency_id": bill.currency_id.id,
                        "source_amount": abs(bill.amount_untaxed),
                        "allocated_amount": share,
                        "allocation_method": "amount",
                        "source": "manual",
                        "confidence": 70,
                        "is_manual": False,
                        "state": "suggested",
                    }
                )
            tx._sync_lines_from_documents()

        auxiliary.action_recompute_state()

        auxiliary.message_post(
            body=_(
                "%(user)s relacionó esta factura de proveedor con %(count)s operación(es) de venta."
                "%(notes)s"
            )
            % {
                "user": self.env.user.display_name,
                "count": len(transactions),
                "notes": (" " + _("Notas: %s") % self.notes) if self.notes else "",
            }
        )

        return {
            "type": "ir.actions.act_window",
            "name": _("Auxiliar de cuentas por pagar"),
            "res_model": "purchase.sale.payable.auxiliary",
            "view_mode": "form",
            "res_id": auxiliary.id,
        }
