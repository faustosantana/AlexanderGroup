# -*- coding: utf-8 -*-
"""19.0.4.0.0 — Asistentes UX: relacionar / validar / aprobar con datos mínimos."""
from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools.float_utils import float_compare


class PurchaseSaleRelateDocumentsWizard(models.TransientModel):
    _name = "purchase.sale.relate.documents.wizard"
    _description = "Relacionar documentos de compra y venta"

    company_id = fields.Many2one(
        "res.company", string="Empresa", required=True, default=lambda self: self.env.company
    )
    transaction_id = fields.Many2one("purchase.sale.margin.transaction", string="Operación")
    vendor_bill_id = fields.Many2one(
        "account.move",
        string="Factura de proveedor",
        domain="[('company_id', '=', company_id), ('move_type', 'in', ('in_invoice', 'in_refund')), ('state', '=', 'posted')]",
    )
    customer_invoice_id = fields.Many2one(
        "account.move",
        string="Factura de cliente",
        domain="[('company_id', '=', company_id), ('move_type', 'in', ('out_invoice', 'out_refund')), ('state', '=', 'posted')]",
    )
    sale_order_id = fields.Many2one(
        "sale.order",
        string="Orden de venta",
        domain="[('company_id', '=', company_id), ('state', 'in', ('sale', 'done'))]",
    )
    amount_to_relate = fields.Monetary(string="Monto a relacionar", currency_field="currency_id")
    currency_id = fields.Many2one("res.currency", compute="_compute_currency")
    notes = fields.Char(string="Comentario (opcional)")

    customer_id = fields.Many2one("res.partner", string="Cliente", compute="_compute_autofill", readonly=True)
    supplier_id = fields.Many2one("res.partner", string="Proveedor", compute="_compute_autofill", readonly=True)
    ncf_number = fields.Char(string="NCF", compute="_compute_autofill", readonly=True)
    purchase_order_id = fields.Many2one("purchase.order", string="Orden de compra", compute="_compute_autofill", readonly=True)

    @api.depends("vendor_bill_id", "customer_invoice_id", "company_id")
    def _compute_currency(self):
        for rec in self:
            rec.currency_id = (
                rec.vendor_bill_id.currency_id
                or rec.customer_invoice_id.currency_id
                or rec.company_id.currency_id
                or self.env.company.currency_id
            )

    @api.depends("vendor_bill_id", "customer_invoice_id", "sale_order_id")
    def _compute_autofill(self):
        for rec in self:
            bill = rec.vendor_bill_id
            inv = rec.customer_invoice_id
            so = rec.sale_order_id
            rec.supplier_id = bill.partner_id if bill else False
            rec.customer_id = (inv.partner_id if inv else False) or (so.partner_id if so else False)
            rec.ncf_number = False
            if bill:
                for fname in ("l10n_do_fiscal_number", "l10n_latam_document_number"):
                    val = getattr(bill, fname, False)
                    if val:
                        rec.ncf_number = val
                        break
                if not rec.ncf_number:
                    rec.ncf_number = bill.ref or ""
            po = self.env["purchase.order"]
            if bill:
                po = bill.invoice_line_ids.mapped("purchase_line_id.order_id")[:1]
            rec.purchase_order_id = po
            # amount_to_relate is set via onchange / defaults, not here

    @api.onchange("vendor_bill_id")
    def _onchange_vendor_bill(self):
        if self.vendor_bill_id:
            self.amount_to_relate = self.vendor_bill_id.amount_untaxed
            self.company_id = self.vendor_bill_id.company_id

    def action_confirm(self):
        self.ensure_one()
        if not self.vendor_bill_id and not self.customer_invoice_id and not self.sale_order_id:
            raise UserError(_("Indique al menos una factura de proveedor y una venta o factura de cliente."))
        if self.vendor_bill_id and not (self.customer_invoice_id or self.sale_order_id or self.transaction_id):
            raise UserError(_("Seleccione la factura de cliente, la orden de venta o la operación comercial."))

        for doc in (self.vendor_bill_id, self.customer_invoice_id, self.sale_order_id):
            if doc and doc.company_id and doc.company_id != self.company_id:
                raise ValidationError(_("No se pueden relacionar documentos de empresas distintas."))

        Transaction = self.env["purchase.sale.margin.transaction"]
        tx = self.transaction_id
        if not tx:
            vals = {
                "company_id": self.company_id.id,
                "name": _("Relación manual"),
                "source": "manual",
                "state": "pending_review",
                "transaction_type": "resale",
            }
            if self.sale_order_id:
                vals.update(
                    {
                        "customer_id": self.sale_order_id.partner_id.id,
                        "sale_order_ids": [(4, self.sale_order_id.id)],
                        "name": self.sale_order_id.name,
                    }
                )
            if self.customer_invoice_id:
                vals.update(
                    {
                        "customer_id": self.customer_invoice_id.partner_id.id,
                        "customer_invoice_ids": [(4, self.customer_invoice_id.id)],
                        "name": self.customer_invoice_id.name or vals.get("name"),
                    }
                )
            if self.sale_order_id or self.customer_invoice_id:
                tx = Transaction.find_or_create_canonical_transaction(
                    sale_order=self.sale_order_id or None,
                    customer_invoice=self.customer_invoice_id or None,
                    vals=vals,
                )
            else:
                tx = Transaction.create(vals)

        writes = {}
        if self.vendor_bill_id:
            writes["vendor_bill_ids"] = [(4, self.vendor_bill_id.id)]
            if self.purchase_order_id:
                writes["purchase_order_ids"] = [(4, self.purchase_order_id.id)]
            writes.setdefault("supplier_ids", [(4, self.vendor_bill_id.partner_id.id)])
        if self.customer_invoice_id:
            writes["customer_invoice_ids"] = [(4, self.customer_invoice_id.id)]
            writes["customer_id"] = self.customer_invoice_id.partner_id.id
        if self.sale_order_id:
            writes["sale_order_ids"] = [(4, self.sale_order_id.id)]
            writes.setdefault("customer_id", self.sale_order_id.partner_id.id)
        if writes:
            tx.write(writes)

        Aux = self.env["purchase.sale.payable.auxiliary"]
        if self.vendor_bill_id:
            aux = Aux.search([("vendor_bill_id", "=", self.vendor_bill_id.id)], limit=1)
            if not aux:
                aux = Aux.create(
                    {
                        "company_id": self.company_id.id,
                        "vendor_bill_id": self.vendor_bill_id.id,
                    }
                )
            aux_vals = {"transaction_ids": [(4, tx.id)]}
            if self.sale_order_id:
                aux_vals["sale_order_ids"] = [(4, self.sale_order_id.id)]
            if self.customer_invoice_id:
                aux_vals["customer_invoice_ids"] = [(4, self.customer_invoice_id.id)]
            aux.write(aux_vals)

        note = (" " + self.notes) if self.notes else ""
        tx.message_post(
            body=_(
                "%(user)s relacionó %(bill)s con %(sale)s por %(amount)s.%(note)s"
            )
            % {
                "user": self.env.user.display_name,
                "bill": self.vendor_bill_id.display_name if self.vendor_bill_id else _("(sin factura proveedor)"),
                "sale": (
                    self.customer_invoice_id.display_name
                    if self.customer_invoice_id
                    else (self.sale_order_id.display_name if self.sale_order_id else tx.transaction_number)
                ),
                "amount": self.amount_to_relate,
                "note": note,
            }
        )
        return {
            "type": "ir.actions.act_window",
            "name": _("Control financiero de la operación"),
            "res_model": "purchase.sale.margin.transaction",
            "res_id": tx.id,
            "view_mode": "form",
        }


class PurchaseSaleValidateWizard(models.TransientModel):
    _name = "purchase.sale.validate.wizard"
    _description = "Validar relación (Compras)"

    transaction_id = fields.Many2one("purchase.sale.margin.transaction", required=True)
    sale_amount = fields.Monetary(related="transaction_id.display_sale_amount", readonly=True)
    cost_amount = fields.Monetary(related="transaction_id.display_cost_amount", readonly=True)
    margin_amount = fields.Monetary(related="transaction_id.estimated_margin", readonly=True)
    amount_to_pay = fields.Monetary(related="transaction_id.amount_to_pay", readonly=True)
    amount_to_collect = fields.Monetary(related="transaction_id.amount_to_collect", readonly=True)
    currency_id = fields.Many2one(related="transaction_id.company_currency_id")
    confirm_supplier = fields.Boolean(string="Proveedor correcto", default=True)
    confirm_products = fields.Boolean(string="Artículos correctos", default=True)
    confirm_cost = fields.Boolean(string="Costo correcto", default=True)
    confirm_sale = fields.Boolean(string="Venta correcta", default=True)

    def action_confirm(self):
        self.ensure_one()
        if not all(
            [self.confirm_supplier, self.confirm_products, self.confirm_cost, self.confirm_sale]
        ):
            raise UserError(_("Marque las cuatro confirmaciones antes de validar la relación."))
        if self.transaction_id.state in ("draft", "detected", "reopened"):
            self.transaction_id.action_send_review()
        self.transaction_id.action_validate_costs()
        return {"type": "ir.actions.act_window_close"}


class PurchaseSaleApproveWizard(models.TransientModel):
    _name = "purchase.sale.approve.wizard"
    _description = "Aprobar operación (Finanzas)"

    transaction_id = fields.Many2one("purchase.sale.margin.transaction", required=True)
    sale_amount = fields.Monetary(related="transaction_id.display_sale_amount", readonly=True)
    cost_amount = fields.Monetary(related="transaction_id.display_cost_amount", readonly=True)
    margin_amount = fields.Monetary(related="transaction_id.display_margin_amount", readonly=True)
    amount_to_pay = fields.Monetary(related="transaction_id.amount_to_pay", readonly=True)
    amount_to_collect = fields.Monetary(related="transaction_id.amount_to_collect", readonly=True)
    currency_id = fields.Many2one(related="transaction_id.company_currency_id")

    def action_confirm(self):
        self.ensure_one()
        tx = self.transaction_id
        if tx.state == "pending_review":
            raise UserError(_("Compras debe validar la relación antes de la aprobación de Finanzas."))
        if tx.state != "validated":
            if tx.validation_state != "validated":
                raise UserError(_("La operación debe estar validada por Compras."))
            if tx.state not in ("validated",):
                raise UserError(_("Estado inválido para aprobación."))
        if tx.approval_state != "pending":
            tx.action_send_approval()
        tx.action_approve()
        return {"type": "ir.actions.act_window_close"}
