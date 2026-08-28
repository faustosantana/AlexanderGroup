# -*- coding: utf-8 -*-
"""19.0.3.0.0 — Requerimiento 2: Auxiliar de Cuentas por Pagar por operación.

Un registro de control OPERACIONAL (nunca contable) por cada factura de
proveedor (in_invoice/in_refund), que permite dar seguimiento a si el costo
de esa factura ya fue relacionado con ventas, cuánto de ese costo ha sido
recuperado vía margen, y el estado de cobro/pago involucrado. Nunca escribe
ni modifica montos contables de la factura ni sus asientos.
"""
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools.float_utils import float_compare, float_is_zero

OPERATIONAL_STATES = [
    ("pending_relation", "Pendiente de relación"),
    ("partial_relation", "Relación parcial"),
    ("full_relation", "Relación completa"),
    ("invoiced_to_customer", "Facturado a cliente"),
    ("pending_customer_collection", "Pendiente de cobro a cliente"),
    ("pending_vendor_payment", "Pendiente de pago a proveedor"),
    ("partial_paid", "Pagada parcialmente"),
    ("paid", "Pagada"),
    ("closed", "Cerrada"),
]


class PurchaseSalePayableAuxiliary(models.Model):
    """One record per vendor bill, used purely for operational
    purchase↔sale cost-recovery control. Never replaces or overrides
    ``account.move`` accounting state (payment_state, amount_residual,
    etc.), which is always read from the source bill via related fields."""

    _name = "purchase.sale.payable.auxiliary"
    _description = "Auxiliar de cuentas por pagar por operación"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "invoice_date desc, id desc"
    _check_company_auto = True

    name = fields.Char(string="Referencia", required=True, copy=False, default=lambda self: _("Nuevo"))
    company_id = fields.Many2one(
        "res.company", string="Compañía", required=True, default=lambda self: self.env.company, index=True,
    )
    vendor_bill_id = fields.Many2one(
        "account.move", string="Factura de proveedor", required=True, index=True,
        check_company=True, ondelete="cascade",
    )
    partner_id = fields.Many2one(related="vendor_bill_id.partner_id", store=True, string="Proveedor")

    ncf_number = fields.Char(string="NCF", readonly=True, copy=False)

    invoice_date = fields.Date(related="vendor_bill_id.invoice_date", store=True, string="Fecha de factura")
    invoice_date_due = fields.Date(related="vendor_bill_id.invoice_date_due", store=True, string="Fecha de vencimiento")
    currency_id = fields.Many2one(related="vendor_bill_id.currency_id", store=True, string="Moneda")
    amount_total = fields.Monetary(related="vendor_bill_id.amount_total", store=True, string="Monto total", currency_field="currency_id")
    amount_untaxed = fields.Monetary(related="vendor_bill_id.amount_untaxed", store=True, string="Base imponible", currency_field="currency_id")
    amount_residual = fields.Monetary(related="vendor_bill_id.amount_residual", store=True, string="Saldo pendiente", currency_field="currency_id")
    payment_state = fields.Selection(related="vendor_bill_id.payment_state", store=True, string="Estado de pago")

    operational_state = fields.Selection(
        OPERATIONAL_STATES, string="Estado operativo", compute="_compute_operational_state",
        store=True, index=True, tracking=True,
    )
    manually_closed = fields.Boolean(string="Cerrada manualmente", default=False, copy=False)

    transaction_ids = fields.Many2many(
        "purchase.sale.margin.transaction",
        "psm_pay_aux_tx_rel",
        "auxiliary_id", "transaction_id", string="Operaciones de margen",
    )
    customer_invoice_ids = fields.Many2many(
        "account.move",
        "psm_pay_aux_inv_rel",
        "auxiliary_id", "move_id", string="Facturas de cliente",
        domain=[("move_type", "in", ("out_invoice", "out_refund"))],
    )
    sale_order_ids = fields.Many2many(
        "sale.order",
        "psm_pay_aux_so_rel",
        "auxiliary_id", "sale_order_id", string="Órdenes de venta",
    )
    transaction_count = fields.Integer(compute="_compute_relation_counts")

    @api.depends("transaction_ids")
    def _compute_relation_counts(self):
        for rec in self:
            rec.transaction_count = len(rec.transaction_ids)

    recovered_cost_amount = fields.Monetary(
        string="Costo recuperado", compute="_compute_recovery_amounts", store=True, currency_field="company_currency_id",
    )
    pending_recovery_amount = fields.Monetary(
        string="Costo pendiente de recuperar", compute="_compute_recovery_amounts", store=True, currency_field="company_currency_id",
    )
    recovery_percent = fields.Float(
        string="% recuperado", compute="_compute_recovery_amounts", store=True,
    )
    margin_generated = fields.Monetary(
        string="Margen generado", compute="_compute_recovery_amounts", store=True, currency_field="company_currency_id",
        help="Suma informativa del margen real de las operaciones relacionadas; puede "
        "sobreestimarse si una operación tiene múltiples facturas de proveedor.",
    )
    coverage_percent = fields.Float(
        string="% de cobertura (operación)", compute="_compute_recovery_amounts", store=True,
        help="Promedio del % de cobertura de costo de las operaciones de margen relacionadas.",
    )
    company_currency_id = fields.Many2one(
        related="company_id.currency_id", store=True, string="Moneda compañía",
    )

    purchase_responsible_id = fields.Many2one("res.users", string="Responsable de compras")
    finance_responsible_id = fields.Many2one("res.users", string="Responsable de finanzas")
    notes = fields.Text(string="Notas")
    active = fields.Boolean(default=True)

    _vendor_bill_uniq = models.Constraint(
        "UNIQUE(vendor_bill_id)",
        "Ya existe un auxiliar de cuentas por pagar para esta factura de proveedor.",
    )

    # ------------------------------------------------------------------
    # Create / basic helpers
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", _("Nuevo")) in (False, _("Nuevo"), "Nuevo"):
                vals["name"] = self.env["ir.sequence"].next_by_code(
                    "purchase.sale.payable.auxiliary"
                ) or _("AUX")
        records = super().create(vals_list)
        records._refresh_ncf_number()
        return records

    def _refresh_ncf_number(self):
        for rec in self:
            bill = rec.vendor_bill_id
            value = False
            if bill:
                for fname in ("l10n_do_fiscal_number", "l10n_latam_document_number"):
                    value = getattr(bill, fname, False)
                    if value:
                        break
                if not value:
                    value = bill.ref or False
            rec.ncf_number = value or ""

    @api.constrains("company_id", "vendor_bill_id", "transaction_ids", "sale_order_ids", "customer_invoice_ids")
    def _check_same_company(self):
        for rec in self:
            if not rec.company_id:
                continue
            if rec.vendor_bill_id.company_id and rec.vendor_bill_id.company_id != rec.company_id:
                raise ValidationError(_("La factura de proveedor pertenece a otra compañía."))
            for docs in (rec.transaction_ids, rec.sale_order_ids, rec.customer_invoice_ids):
                mismatched = docs.filtered(lambda d: d.company_id and d.company_id != rec.company_id)
                if mismatched:
                    raise ValidationError(
                        _("No se permiten documentos de otra compañía en el auxiliar %s.") % rec.name
                    )

    # ------------------------------------------------------------------
    # Computes
    # ------------------------------------------------------------------
    @api.depends(
        "vendor_bill_id.amount_untaxed", "transaction_ids.cost_real_amount", "transaction_ids.margin_is_calculable",
        "transaction_ids.real_margin", "transaction_ids.coverage_percent",
    )
    def _compute_recovery_amounts(self):
        Line = self.env["purchase.sale.margin.transaction.line"]
        for rec in self:
            bill = rec.vendor_bill_id
            base = abs(bill.amount_untaxed) if bill else 0.0
            recovered = 0.0
            if bill:
                lines = Line.search(
                    [
                        ("account_move_id", "=", bill.id),
                        ("line_type", "=", "cost"),
                        ("state", "!=", "excluded"),
                        ("exclude_from_margin", "=", False),
                    ]
                )
                recovered_lines = lines.filtered(lambda l: l.transaction_id.has_related_sale)
                recovered = sum(recovered_lines.mapped("amount_company_currency"))
            rec.recovered_cost_amount = recovered
            rec.pending_recovery_amount = max(base - recovered, 0.0)
            rec.recovery_percent = (recovered / base * 100.0) if base else (100.0 if recovered else 0.0)

            margin_txs = rec.transaction_ids.filtered("margin_is_calculable")
            rec.margin_generated = sum(margin_txs.mapped("real_margin"))
            rec.coverage_percent = (
                sum(rec.transaction_ids.mapped("coverage_percent")) / len(rec.transaction_ids)
                if rec.transaction_ids
                else 0.0
            )

    @api.depends(
        "manually_closed", "transaction_ids", "sale_order_ids", "customer_invoice_ids",
        "recovery_percent", "customer_invoice_ids.state", "customer_invoice_ids.amount_residual",
        "vendor_bill_id.payment_state",
    )
    def _compute_operational_state(self):
        for rec in self:
            if rec.manually_closed:
                rec.operational_state = "closed"
                continue
            has_relation = bool(rec.transaction_ids or rec.sale_order_ids or rec.customer_invoice_ids)
            if not has_relation:
                rec.operational_state = "pending_relation"
                continue
            if float_compare(rec.recovery_percent, 100.0, precision_digits=2) < 0:
                rec.operational_state = "partial_relation"
                continue

            posted_customer_invoices = rec.customer_invoice_ids.filtered(lambda m: m.state == "posted")
            if not posted_customer_invoices:
                rec.operational_state = "invoiced_to_customer" if rec.customer_invoice_ids else "full_relation"
                continue

            pending_collection = posted_customer_invoices.filtered(
                lambda m: not float_is_zero(m.amount_residual, precision_digits=2)
            )
            if pending_collection:
                rec.operational_state = "pending_customer_collection"
                continue

            bill_payment_state = rec.vendor_bill_id.payment_state
            if bill_payment_state == "paid":
                rec.operational_state = "paid"
            elif bill_payment_state == "partial":
                rec.operational_state = "partial_paid"
            else:
                rec.operational_state = "pending_vendor_payment"

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def action_relate_sales(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Relacionar ventas"),
            "res_model": "purchase.sale.relate.sale.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_payable_auxiliary_id": self.id,
                "default_vendor_bill_id": self.vendor_bill_id.id,
                "default_company_id": self.company_id.id,
            },
        }

    def action_recompute_state(self):
        """Manual/cron refresh: pulls fresh accounting facts from the bill
        (payment_state/amount_residual arrive via related+store already) and
        forces recomputation of the operational classification and recovery
        percentages, plus the NCF fallback lookup."""
        for rec in self:
            rec._refresh_ncf_number()
        self._compute_recovery_amounts()
        self._compute_operational_state()
        return True

    def action_close(self):
        self.write({"manually_closed": True})
        return True

    def action_reopen(self):
        self.write({"manually_closed": False})
        return True

    def action_view_vendor_bill(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Factura de proveedor"),
            "res_model": "account.move",
            "view_mode": "form",
            "res_id": self.vendor_bill_id.id,
        }

    def action_view_transactions(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Operaciones de margen"),
            "res_model": "purchase.sale.margin.transaction",
            "view_mode": "list,form",
            "domain": [("id", "in", self.transaction_ids.ids)],
        }

    @api.model
    def cron_refresh_all(self):
        """Scheduled refresh of operational state / recovery KPIs for all
        auxiliaries that are not manually closed."""
        records = self.search([("manually_closed", "=", False)])
        records.action_recompute_state()
        return True
