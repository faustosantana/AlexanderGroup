# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools.float_utils import float_compare, float_is_zero

TRANSACTION_TYPES = [
    ("resale", "Reventa"),
    ("service", "Servicio"),
    ("project", "Proyecto"),
    ("inventory", "Inventario"),
    ("administrative", "Administrativo"),
    ("asset", "Activo"),
    ("mixed", "Mixta"),
    ("manual", "Manual"),
]

TRANSACTION_STATES = [
    ("draft", "Borrador"),
    ("detected", "Detectada"),
    ("pending_review", "Pendiente de revisión"),
    ("validated", "Validada"),
    ("approved", "Aprobada"),
    ("closed", "Cerrada"),
    ("rejected", "Rechazada"),
    ("reopened", "Reabierta"),
]

VALIDATION_STATES = [
    ("pending", "Pendiente"),
    ("validated", "Validada"),
    ("rejected", "Rechazada"),
]

APPROVAL_STATES = [
    ("not_requested", "No solicitada"),
    ("pending", "Pendiente"),
    ("approved", "Aprobada"),
    ("rejected", "Rechazada"),
]

TRANSACTION_SOURCES = [
    ("manual", "Manual"),
    ("backfill", "Backfill"),
    ("auto_detected", "Detección automática"),
    ("cost_link", "Enlace de costo"),
    ("invoice", "Factura"),
]

class PurchaseSaleMarginTransaction(models.Model):
    """Primary financial control record: one operation groups the sale side
    (SO / customer invoices) and the cost side (PO / vendor bills) of a
    business transaction so estimated vs real margin can be tracked,
    validated (Compras) and approved (Finanzas) with full traceability.
    """

    _name = "purchase.sale.margin.transaction"
    _description = "Operación de margen compra-venta"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "transaction_date desc, id desc"
    _check_company_auto = True

    # ------------------------------------------------------------------
    # Identification
    # ------------------------------------------------------------------
    transaction_number = fields.Char(
        string="Número de operación", required=True, copy=False, readonly=True,
        default=lambda self: _("Nuevo"), tracking=True,
    )
    name = fields.Char(string="Descripción", tracking=True)
    display_name = fields.Char(compute="_compute_display_name", store=False)
    company_id = fields.Many2one(
        "res.company", string="Compañía", required=True,
        default=lambda self: self.env.company, index=True, tracking=True,
    )

    customer_id = fields.Many2one(
        "res.partner", string="Cliente", tracking=True, index=True,
    )
    supplier_ids = fields.Many2many(
        "res.partner", "purchase_sale_margin_transaction_supplier_rel",
        "transaction_id", "partner_id", string="Proveedores",
    )
    sale_order_ids = fields.Many2many(
        "sale.order", "purchase_sale_margin_transaction_sale_order_rel",
        "transaction_id", "sale_order_id", string="Órdenes de venta",
    )
    purchase_order_ids = fields.Many2many(
        "purchase.order", "purchase_sale_margin_transaction_purchase_order_rel",
        "transaction_id", "purchase_order_id", string="Órdenes de compra",
    )
    customer_invoice_ids = fields.Many2many(
        "account.move", "purchase_sale_margin_transaction_customer_invoice_rel",
        "transaction_id", "move_id", string="Facturas de cliente",
        domain=[("move_type", "in", ("out_invoice", "out_refund"))],
    )
    vendor_bill_ids = fields.Many2many(
        "account.move", "purchase_sale_margin_transaction_vendor_bill_rel",
        "transaction_id", "move_id", string="Facturas de proveedor",
        domain=[("move_type", "in", ("in_invoice", "in_refund"))],
    )
    # UX-only: cancelled docs stay on M2M for audit but are hidden from operators.
    active_purchase_order_ids = fields.Many2many(
        "purchase.order",
        compute="_compute_active_related_docs",
        string="OC activas",
    )
    active_vendor_bill_ids = fields.Many2many(
        "account.move",
        compute="_compute_active_related_docs",
        string="Facturas proveedor activas",
    )

    transaction_date = fields.Date(
        string="Fecha de operación", default=fields.Date.context_today, tracking=True,
    )
    salesperson_id = fields.Many2one("res.users", string="Vendedor", tracking=True)
    purchase_responsible_id = fields.Many2one("res.users", string="Responsable de compras", tracking=True)
    finance_responsible_id = fields.Many2one("res.users", string="Responsable de finanzas", tracking=True)
    cost_allocation_pending = fields.Boolean(
        string="Asignación de costo pendiente",
        compute="_compute_cost_allocation_pending",
        store=True,
        help="Hay venta y compra vinculadas pero el costo no está atribuido por cantidad de forma inequívoca.",
    )

    currency_id = fields.Many2one(
        "res.currency", string="Moneda", default=lambda self: self.env.company.currency_id,
    )
    company_currency_id = fields.Many2one(
        related="company_id.currency_id", store=True, string="Moneda compañía",
    )

    # ------------------------------------------------------------------
    # Lines (single source of truth for computed amounts)
    # ------------------------------------------------------------------
    line_ids = fields.One2many(
        "purchase.sale.margin.transaction.line", "transaction_id", string="Líneas",
    )
    sale_line_ids = fields.One2many(
        "purchase.sale.margin.transaction.line", "transaction_id", string="Líneas de venta",
        domain=[("line_type", "=", "sale")],
    )
    cost_line_ids = fields.One2many(
        "purchase.sale.margin.transaction.line", "transaction_id", string="Líneas de costo",
        domain=[("line_type", "=", "cost")],
        groups="justech_purchase_sale_margin_control.group_margin_sec_margins_view",
    )
    allocation_ids = fields.One2many(
        "purchase.sale.cost.allocation", "transaction_id", string="Asignaciones de costo",
        groups="justech_purchase_sale_margin_control.group_margin_sec_margins_view",
    )
    sale_order_count = fields.Integer(compute="_compute_document_counts")
    purchase_order_count = fields.Integer(compute="_compute_document_counts")
    customer_invoice_count = fields.Integer(compute="_compute_document_counts")
    vendor_bill_count = fields.Integer(compute="_compute_document_counts")
    allocation_count = fields.Integer(compute="_compute_document_counts")

    @api.depends(
        "sale_order_ids",
        "purchase_order_ids",
        "customer_invoice_ids",
        "vendor_bill_ids",
        # Do not depend on allocation_ids: groups-restricted (Márgenes ver).
    )
    def _compute_document_counts(self):
        for rec in self:
            rec.sale_order_count = len(rec.sale_order_ids.filtered(lambda s: s.state != "cancel"))
            rec.purchase_order_count = len(
                rec.purchase_order_ids.filtered(lambda p: p.state != "cancel")
            )
            rec.customer_invoice_count = len(
                rec.customer_invoice_ids.filtered(lambda m: m.state != "cancel")
            )
            rec.vendor_bill_count = len(
                rec.vendor_bill_ids.filtered(lambda m: m.state != "cancel")
            )
            # Count via sudo — field itself remains margins_view-only in forms.
            rec.allocation_count = len(rec.sudo().allocation_ids)

    @api.depends(
        "purchase_order_ids",
        "purchase_order_ids.state",
        "vendor_bill_ids",
        "vendor_bill_ids.state",
    )
    def _compute_active_related_docs(self):
        for rec in self:
            rec.active_purchase_order_ids = rec.purchase_order_ids.filtered(
                lambda p: p.state != "cancel"
            )
            rec.active_vendor_bill_ids = rec.vendor_bill_ids.filtered(
                lambda m: m.state != "cancel"
            )

    # ------------------------------------------------------------------
    # Monetary amounts (base is always sin ITBIS / untaxed, audit rule)
    # ------------------------------------------------------------------
    _MARGIN_SEC = "justech_purchase_sale_margin_control.group_margin_sec_margins_view"

    sale_estimated_amount = fields.Monetary(
        string="Venta estimada", compute="_compute_amounts", store=True, currency_field="company_currency_id",
        groups=_MARGIN_SEC,
    )
    sale_real_amount = fields.Monetary(
        string="Venta real", compute="_compute_amounts", store=True, currency_field="company_currency_id",
        groups=_MARGIN_SEC,
    )
    cost_estimated_amount = fields.Monetary(
        string="Costo estimado", compute="_compute_amounts", store=True, currency_field="company_currency_id",
        groups=_MARGIN_SEC,
    )
    cost_real_amount = fields.Monetary(
        string="Costo real", compute="_compute_amounts", store=True, currency_field="company_currency_id",
        groups=_MARGIN_SEC,
    )
    additional_cost_amount = fields.Monetary(
        string="Costo adicional", compute="_compute_amounts", store=True, currency_field="company_currency_id",
        groups=_MARGIN_SEC,
    )
    pending_cost_amount = fields.Monetary(
        string="Costo pendiente", compute="_compute_amounts", store=True, currency_field="company_currency_id",
        groups=_MARGIN_SEC,
    )
    pending_sale_amount = fields.Monetary(
        string="Venta pendiente", compute="_compute_amounts", store=True, currency_field="company_currency_id",
        groups=_MARGIN_SEC,
    )
    estimated_margin = fields.Monetary(
        string="Margen estimado", compute="_compute_amounts", store=True, currency_field="company_currency_id",
        groups=_MARGIN_SEC,
    )
    estimated_margin_pct = fields.Float(
        string="Margen estimado %", compute="_compute_amounts", store=True, groups=_MARGIN_SEC,
    )
    real_margin = fields.Monetary(
        string="Margen real", compute="_compute_amounts", store=True, currency_field="company_currency_id",
        groups=_MARGIN_SEC,
    )
    real_margin_pct = fields.Float(
        string="Margen real %", compute="_compute_amounts", store=True, groups=_MARGIN_SEC,
    )
    coverage_percent = fields.Float(
        string="% de cobertura de costo", compute="_compute_amounts", store=True,
        help="Porcentaje del costo estimado ya respaldado por costo real registrado.",
        groups=_MARGIN_SEC,
    )

    # ------------------------------------------------------------------
    # Classification / workflow
    # ------------------------------------------------------------------
    transaction_type = fields.Selection(
        TRANSACTION_TYPES, string="Tipo de operación", default="manual", tracking=True, index=True,
    )
    state = fields.Selection(
        TRANSACTION_STATES, string="Estado", default="draft", tracking=True, index=True, copy=False,
    )
    validation_state = fields.Selection(
        VALIDATION_STATES, string="Estado de validación", default="pending", tracking=True, copy=False,
    )
    approval_state = fields.Selection(
        APPROVAL_STATES, string="Estado de aprobación", default="not_requested", tracking=True, copy=False,
    )
    source = fields.Selection(TRANSACTION_SOURCES, string="Origen", default="manual")
    confidence = fields.Integer(string="Confianza %", default=0)
    notes = fields.Text(string="Notas")

    validated_by_id = fields.Many2one("res.users", string="Validado por", readonly=True, copy=False)
    validated_at = fields.Datetime(string="Validado el", readonly=True, copy=False)
    approved_by_id = fields.Many2one("res.users", string="Aprobado por", readonly=True, copy=False)
    approved_at = fields.Datetime(string="Aprobado el", readonly=True, copy=False)

    # ------------------------------------------------------------------
    # Coverage / alert flags
    # ------------------------------------------------------------------
    has_related_cost = fields.Boolean(string="Tiene costo relacionado", compute="_compute_coverage_flags", store=True)
    has_related_sale = fields.Boolean(string="Tiene venta relacionada", compute="_compute_coverage_flags", store=True)
    sale_without_cost = fields.Boolean(
        string="Venta sin costo", compute="_compute_coverage_flags", store=True, index=True,
    )
    margin_is_calculable = fields.Boolean(
        string="Margen calculable", compute="_compute_coverage_flags", store=True, index=True,
        help="Falso cuando la operación no tiene costo real registrado: el margen real "
        "no se calcula y no debe sumarse al margen real confirmado.",
        groups="justech_purchase_sale_margin_control.group_margin_sec_margins_view",
    )
    cost_fully_covered = fields.Boolean(
        string="Costo totalmente cubierto",
        compute="_compute_coverage_flags",
        store=True,
        groups="justech_purchase_sale_margin_control.group_margin_sec_margins_view",
    )
    sale_fully_invoiced = fields.Boolean(string="Venta totalmente facturada", compute="_compute_coverage_flags", store=True)
    alert_message = fields.Text(string="Alerta", compute="_compute_alert_message")

    active = fields.Boolean(default=True)

    _transaction_number_uniq = models.Constraint(
        "UNIQUE(transaction_number, company_id)",
        "El número de operación ya existe para esta compañía.",
    )

    # ------------------------------------------------------------------
    # Display / sequence
    # ------------------------------------------------------------------
    @api.depends("transaction_number", "name")
    def _compute_display_name(self):
        for rec in self:
            if rec.name:
                rec.display_name = "%s - %s" % (rec.transaction_number, rec.name)
            else:
                rec.display_name = rec.transaction_number

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("transaction_number", _("Nuevo")) in (False, _("Nuevo"), "Nuevo"):
                vals["transaction_number"] = (
                    self.env["ir.sequence"].next_by_code("purchase.sale.margin.transaction") or _("MTX")
                )
        records = super().create(vals_list)
        records._sync_lines_from_documents()
        records._invalidate_linked_document_trace()
        return records

    def write(self, vals):
        res = super().write(vals)
        doc_fields = {
            "sale_order_ids", "purchase_order_ids", "customer_invoice_ids", "vendor_bill_ids",
        }
        if doc_fields.intersection(vals) and not self.env.context.get("skip_line_sync"):
            self._sync_lines_from_documents()
        if doc_fields.intersection(vals):
            self._invalidate_linked_document_trace()
        return res

    def _invalidate_linked_document_trace(self):
        """Refresh SO/PO/AM cross-trace fields after hub M2M changes."""
        sos = self.mapped("sale_order_ids")
        pos = self.mapped("purchase_order_ids")
        moves = self.mapped("customer_invoice_ids") | self.mapped("vendor_bill_ids")
        so_fields = [
            "margin_transaction_ids",
            "margin_transaction_count",
            "jm_related_purchase_order_ids",
            "jm_related_purchase_order_count",
            "jm_related_vendor_bill_ids",
            "jm_related_vendor_bill_count",
            "jm_related_customer_invoice_ids",
            "jm_related_customer_invoice_count",
            "margin_control_sale_untaxed",
            "margin_control_cost",
            "margin_control_margin",
            "margin_control_margin_pct",
            "margin_control_state",
            "margin_control_po_names",
            "margin_control_bill_names",
            "margin_control_cost_origin",
        ]
        po_fields = [
            "margin_transaction_ids",
            "margin_transaction_count",
            "jm_related_sale_order_ids",
            "jm_related_sale_order_count",
            "jm_related_customer_invoice_ids",
            "jm_related_customer_invoice_count",
            "margin_assigned_cost",
            "margin_usage_labels",
        ]
        move_fields = [
            "margin_transaction_ids",
            "margin_transaction_count",
            "jm_related_sale_order_ids",
            "jm_related_purchase_order_ids",
            "jm_related_purchase_order_count",
            "jm_related_vendor_bill_ids",
            "jm_related_vendor_bill_count",
            "jm_related_customer_invoice_ids",
            "related_sale_count",
            "margin_control_cost",
            "margin_control_margin",
            "margin_control_margin_pct",
            "margin_control_state",
        ]
        if sos:
            sos.invalidate_recordset([f for f in so_fields if f in sos._fields])
        if pos:
            pos.invalidate_recordset([f for f in po_fields if f in pos._fields])
        if moves:
            moves.invalidate_recordset([f for f in move_fields if f in moves._fields])

    # ------------------------------------------------------------------
    # Computes
    # ------------------------------------------------------------------
    @api.depends(
        "line_ids.line_type", "line_ids.data_origin", "line_ids.amount_company_currency",
        "line_ids.exclude_from_margin", "line_ids.cost_usage_type", "line_ids.state",
    )
    def _compute_amounts(self):
        for rec in self:
            active_lines = rec.line_ids.filtered(lambda l: l.state != "excluded" and not l.exclude_from_margin)
            sale_lines = active_lines.filtered(lambda l: l.line_type == "sale")
            cost_lines = active_lines.filtered(lambda l: l.line_type == "cost")

            # Accounting bills = real. Inventory/manual hub costs are commercial
            # estimated coverage (not vendor-bill real) — never replace PO estimated.
            real_cost_lines = cost_lines.filtered(lambda l: l.data_origin == "accounting")
            inv_est_lines = cost_lines.filtered(
                lambda l: l.cost_source in ("inventory", "manual")
                and l.data_origin != "accounting"
            )
            margin_cost_lines = real_cost_lines.filtered(lambda l: l.cost_usage_type != "administrative_expense")
            admin_cost_lines = real_cost_lines.filtered(lambda l: l.cost_usage_type == "administrative_expense")
            additional_cost_lines = real_cost_lines.filtered(
                lambda l: l.cost_usage_type in ("logistic", "financial", "other")
            )

            sale_estimated = sum(sale_lines.filtered(lambda l: l.data_origin == "estimated").mapped("amount_company_currency"))
            sale_real = sum(sale_lines.filtered(lambda l: l.data_origin in ("accounting", "manual")).mapped("amount_company_currency"))
            cost_estimated = sum(
                cost_lines.filtered(lambda l: l.data_origin == "estimated").mapped(
                    "amount_company_currency"
                )
            ) + sum(inv_est_lines.mapped("amount_company_currency"))
            cost_real = sum(margin_cost_lines.mapped("amount_company_currency"))
            additional_cost = sum(additional_cost_lines.mapped("amount_company_currency"))

            # Fallback: if no estimated line was ever synced, the best known
            # estimate is the real figure already registered.
            if not sale_estimated:
                sale_estimated = sale_real
            if not cost_estimated:
                cost_estimated = cost_real

            rec.sale_estimated_amount = sale_estimated
            rec.sale_real_amount = sale_real
            rec.cost_estimated_amount = cost_estimated
            rec.cost_real_amount = cost_real
            rec.additional_cost_amount = additional_cost
            rec.pending_cost_amount = max(cost_estimated - cost_real, 0.0)
            rec.pending_sale_amount = max(sale_estimated - sale_real, 0.0)

            rec.estimated_margin = sale_estimated - cost_estimated
            rec.estimated_margin_pct = (rec.estimated_margin / sale_estimated * 100.0) if sale_estimated else 0.0

            margin_is_calculable = bool(margin_cost_lines) or bool(admin_cost_lines)
            if margin_is_calculable:
                rec.real_margin = sale_real - cost_real
                rec.real_margin_pct = (rec.real_margin / sale_real * 100.0) if sale_real else 0.0
            else:
                rec.real_margin = 0.0
                rec.real_margin_pct = 0.0

            rec.coverage_percent = (cost_real / cost_estimated * 100.0) if cost_estimated else (
                100.0 if margin_is_calculable else 0.0
            )

    @api.depends(
        "line_ids.line_type", "line_ids.data_origin", "line_ids.exclude_from_margin", "line_ids.state",
        "purchase_order_ids", "vendor_bill_ids", "sale_order_ids", "customer_invoice_ids",
        "cost_real_amount", "cost_estimated_amount", "sale_real_amount", "sale_estimated_amount",
    )
    def _compute_coverage_flags(self):
        for rec in self:
            active_lines = rec.line_ids.filtered(lambda l: l.state != "excluded" and not l.exclude_from_margin)
            cost_lines = active_lines.filtered(lambda l: l.line_type == "cost")
            sale_lines = active_lines.filtered(lambda l: l.line_type == "sale")
            real_cost_lines = cost_lines.filtered(lambda l: l.data_origin in ("accounting", "manual"))

            has_related_cost = bool(cost_lines) or bool(rec.purchase_order_ids) or bool(rec.vendor_bill_ids)
            has_related_sale = bool(sale_lines) or bool(rec.sale_order_ids) or bool(rec.customer_invoice_ids)

            rec.has_related_cost = has_related_cost
            rec.has_related_sale = has_related_sale
            rec.sale_without_cost = has_related_sale and not has_related_cost
            rec.margin_is_calculable = bool(real_cost_lines)
            rec.cost_fully_covered = (
                float_compare(rec.coverage_percent, 99.99, precision_digits=2) >= 0 if rec.cost_estimated_amount else False
            )
            rec.sale_fully_invoiced = (
                float_is_zero(rec.pending_sale_amount, precision_digits=2) and rec.sale_estimated_amount > 0
            )

    @api.depends(
        "sale_without_cost", "transaction_type", "state", "real_margin", "margin_is_calculable",
    )
    def _compute_alert_message(self):
        for rec in self:
            messages = []
            if rec.sale_without_cost:
                messages.append(_("Venta sin costo relacionado: no cuenta como margen real confirmado."))
            if rec.transaction_type == "administrative":
                messages.append(_("Gasto administrativo: excluido del margen de ventas."))
            if not rec.margin_is_calculable and not rec.sale_without_cost and rec.has_related_cost:
                messages.append(_("Costo estimado pendiente de registrar como costo real."))
            if rec.margin_is_calculable and rec.real_margin < 0:
                messages.append(_("Margen real negativo: requiere revisión."))
            if rec.state in ("draft", "detected"):
                messages.append(_("Operación pendiente de revisión."))
            rec.alert_message = "\n".join(messages) if messages else False

    @api.depends(
        "sale_order_ids",
        "purchase_order_ids",
        "line_ids.purchase_order_line_id",
        "line_ids.quantity",
        "line_ids.line_type",
        "line_ids.data_origin",
    )
    def _compute_cost_allocation_pending(self):
        from odoo.addons.justech_purchase_sale_margin_control.services.line_allocation_service import (
            LineAllocationService,
        )

        svc = LineAllocationService(self.env)
        for rec in self:
            rec.cost_allocation_pending = svc.cost_allocation_pending(rec)

    # ------------------------------------------------------------------
    # Line sync helpers ("Compute amounts from linked allocations + manual lines")
    # ------------------------------------------------------------------
    def _sync_lines_from_documents(self):
        from odoo.addons.justech_purchase_sale_margin_control.services.line_allocation_service import (
            LineAllocationService,
            _is_product_line,
        )

        Line = self.env["purchase.sale.margin.transaction.line"]
        svc = LineAllocationService(self.env)
        skip_unsafe_po = self.env.context.get("margin_skip_unsafe_po_cost")
        for rec in self:
            existing_sale_orders = rec.line_ids.filtered(lambda l: l.sale_order_id).mapped("sale_order_id")
            for so in rec.sale_order_ids - existing_sale_orders:
                Line.create(
                    {
                        "transaction_id": rec.id,
                        "line_type": "sale",
                        "data_origin": "estimated",
                        "sale_order_id": so.id,
                        "partner_id": so.partner_id.id,
                        "currency_id": so.currency_id.id,
                        "description": so.name,
                        "amount_untaxed": so.amount_untaxed,
                        "amount_tax": so.amount_tax,
                        "amount_total": so.amount_total,
                    }
                )

            existing_invoices = rec.line_ids.filtered(lambda l: l.account_move_id).mapped("account_move_id")
            for inv in rec.customer_invoice_ids - existing_invoices:
                if inv.state != "posted":
                    continue
                Line.create(
                    {
                        "transaction_id": rec.id,
                        "line_type": "sale",
                        "data_origin": "accounting",
                        "account_move_id": inv.id,
                        "sale_order_id": (inv.invoice_line_ids.mapped("sale_line_ids.order_id")[:1] or rec.sale_order_ids[:1]).id
                        if (inv.invoice_line_ids.mapped("sale_line_ids.order_id") or rec.sale_order_ids)
                        else False,
                        "partner_id": inv.partner_id.id,
                        "currency_id": inv.currency_id.id,
                        "description": inv.name or inv.ref,
                        "amount_untaxed": inv.amount_untaxed_signed if inv.move_type == "out_refund" else inv.amount_untaxed,
                        "amount_tax": inv.amount_tax,
                        "amount_total": inv.amount_total,
                        "is_manual": False,
                    }
                )

            existing_purchase_orders = rec.line_ids.filtered(lambda l: l.purchase_order_id).mapped("purchase_order_id")
            for po in rec.purchase_order_ids - existing_purchase_orders:
                # Level B/C: do not silently attribute 100% of a multi-sale PO
                if skip_unsafe_po and not svc.po_full_cost_sync_is_safe(rec, po):
                    continue
                if not skip_unsafe_po and rec.sale_order_ids and not svc.po_full_cost_sync_is_safe(rec, po):
                    # Default path for new links: also protect against false full cost
                    continue
                polines = po.order_line.filtered(_is_product_line)
                if polines:
                    for pol in polines:
                        Line.create(
                            {
                                "transaction_id": rec.id,
                                "line_type": "cost",
                                "data_origin": "estimated",
                                "purchase_order_id": po.id,
                                "purchase_order_line_id": pol.id,
                                "partner_id": po.partner_id.id,
                                "product_id": pol.product_id.id,
                                "currency_id": po.currency_id.id,
                                "description": pol.name or po.name,
                                "cost_usage_type": getattr(pol, "cost_usage_type", False) or "resale_direct",
                                "quantity": pol.product_qty,
                                "amount_untaxed": pol.price_subtotal,
                                "amount_tax": pol.price_tax,
                                "amount_total": pol.price_total,
                                "is_manual": False,
                            }
                        )
                else:
                    Line.create(
                        {
                            "transaction_id": rec.id,
                            "line_type": "cost",
                            "data_origin": "estimated",
                            "purchase_order_id": po.id,
                            "partner_id": po.partner_id.id,
                            "currency_id": po.currency_id.id,
                            "description": po.name,
                            "cost_usage_type": "resale_direct",
                            "amount_untaxed": po.amount_untaxed,
                            "amount_tax": po.amount_tax,
                            "amount_total": po.amount_total,
                        }
                    )

            existing_bills = rec.line_ids.filtered(lambda l: l.account_move_id and l.line_type == "cost").mapped(
                "account_move_id"
            )
            for bill in rec.vendor_bill_ids - existing_bills:
                if bill.state != "posted":
                    continue
                # Prefer line-level real cost via assignment refresh; skip whole-bill
                # dump when sale+PO hub already has estimated POL lines.
                if rec.sale_order_ids and rec.line_ids.filtered(
                    lambda l: l.line_type == "cost" and l.purchase_order_line_id
                ):
                    continue
                usage_type = "resale_direct"
                po_line = bill.invoice_line_ids.mapped("purchase_line_id")[:1]
                if po_line and po_line.cost_usage_type:
                    usage_type = po_line.cost_usage_type
                Line.create(
                    {
                        "transaction_id": rec.id,
                        "line_type": "cost",
                        "data_origin": "accounting",
                        "account_move_id": bill.id,
                        "purchase_order_id": po_line.order_id.id if po_line else (rec.purchase_order_ids[:1].id if rec.purchase_order_ids else False),
                        "partner_id": bill.partner_id.id,
                        "currency_id": bill.currency_id.id,
                        "description": bill.name or bill.ref,
                        "cost_usage_type": usage_type,
                        "amount_untaxed": bill.amount_untaxed,
                        "amount_tax": bill.amount_tax,
                        "amount_total": bill.amount_total,
                        "is_manual": False,
                    }
                )
        return True

    def action_recompute_lines(self):
        self._sync_lines_from_documents()
        return True

    # ------------------------------------------------------------------
    # 19.0.3.0.0 — Requerimiento 1: múltiples órdenes de compra
    # ------------------------------------------------------------------
    def action_add_purchase_orders(self):
        """Open the multi-purchase-order wizard pre-loaded with this
        operation, so several POs can be added/allocated in one step."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Agregar órdenes de compra"),
            "res_model": "purchase.sale.add.purchase.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_transaction_id": self.id,
                "default_company_id": self.company_id.id,
            },
        }

    def action_recompute_costs(self):
        """Force a recompute of the transaction's cost/sale lines and
        invalidate the aggregated monetary computes so the summary reflects
        any change made directly on linked POs/bills/allocations."""
        self._sync_lines_from_documents()
        self.invalidate_recordset()
        return True

    # ------------------------------------------------------------------
    # Constraints
    # ------------------------------------------------------------------
    @api.constrains(
        "company_id", "sale_order_ids", "purchase_order_ids", "customer_invoice_ids", "vendor_bill_ids",
    )
    def _check_same_company(self):
        for rec in self:
            if not rec.company_id:
                continue
            for docs in (
                rec.sale_order_ids,
                rec.purchase_order_ids,
                rec.customer_invoice_ids,
                rec.vendor_bill_ids,
            ):
                mismatched = docs.filtered(lambda d: d.company_id and d.company_id != rec.company_id)
                if mismatched:
                    raise ValidationError(
                        _("No se permiten documentos de otra compañía en la operación %s.")
                        % rec.transaction_number
                    )

    def _check_no_cancelled_documents(self):
        """Block finance approval only when cancelled docs still contribute actively.

        Historical cancelled POs/SOs/invoices on the M2M are allowed once their
        cost/sale lines are excluded / coverage released.
        """
        for rec in self:
            blockers = []
            for so in rec.sale_order_ids.filtered(lambda s: s.state == "cancel"):
                active = rec.line_ids.filtered(
                    lambda l, s=so: l.sale_order_id == s
                    and l.state != "excluded"
                    and not l.exclude_from_margin
                )
                if active:
                    blockers.append(so.display_name)
            for po in rec.purchase_order_ids.filtered(lambda p: p.state == "cancel"):
                active = rec.line_ids.filtered(
                    lambda l, p=po: l.purchase_order_id == p
                    and l.line_type == "cost"
                    and l.state != "excluded"
                    and not l.exclude_from_margin
                )
                if active:
                    blockers.append(po.display_name)
            for move in (rec.customer_invoice_ids | rec.vendor_bill_ids).filtered(
                lambda m: m.state == "cancel"
            ):
                active = rec.line_ids.filtered(
                    lambda l, m=move: l.account_move_id == move
                    and l.state != "excluded"
                    and not l.exclude_from_margin
                )
                if active:
                    blockers.append(move.display_name)
            if blockers:
                raise UserError(
                    _(
                        "La operación %s tiene documentos cancelados con cobertura "
                        "activa; no puede aprobarse: %s"
                    )
                    % (rec.transaction_number, ", ".join(blockers))
                )

    # ------------------------------------------------------------------
    # Workflow
    # ------------------------------------------------------------------
    def action_send_review(self):
        for rec in self:
            if rec.state not in ("draft", "detected", "reopened"):
                raise UserError(_("Solo operaciones en borrador o detectadas pueden enviarse a revisión."))
            rec.write({"state": "pending_review", "validation_state": "pending"})
        return True

    def action_validate_costs(self):
        """Purchase (Compras) validates that the cost side is correct."""
        if not self.env.user.has_group("justech_purchase_sale_margin_control.group_margin_purchase"):
            raise UserError(_("Solo el equipo de Compras puede validar los costos."))
        for rec in self:
            if rec.state not in ("pending_review", "reopened"):
                raise UserError(_("Solo operaciones pendientes de revisión pueden validarse."))
            rec.write(
                {
                    "state": "validated",
                    "validation_state": "validated",
                    "validated_by_id": self.env.user.id,
                    "validated_at": fields.Datetime.now(),
                }
            )
        return True

    def action_reject(self):
        for rec in self:
            if rec.state in ("closed",):
                raise UserError(_("No se puede rechazar una operación cerrada."))
            rec.write({"state": "rejected", "validation_state": "rejected", "approval_state": "rejected"})
        return True

    def action_send_approval(self):
        for rec in self:
            if rec.state != "validated":
                raise UserError(_("La operación debe estar validada antes de solicitar aprobación."))
            rec.write({"approval_state": "pending"})
        return True

    def action_approve(self):
        """Finance (Finanzas) approves the operation. Requires prior
        validation and no cancelled linked documents (audit rules)."""
        if not self.env.user.has_group("justech_purchase_sale_margin_control.group_margin_finance"):
            raise UserError(_("Solo el equipo de Finanzas puede aprobar operaciones."))
        for rec in self:
            if rec.state != "validated":
                raise UserError(_("No se puede aprobar una operación que no ha sido validada."))
            rec._check_no_cancelled_documents()
            rec.write(
                {
                    "state": "approved",
                    "approval_state": "approved",
                    "approved_by_id": self.env.user.id,
                    "approved_at": fields.Datetime.now(),
                }
            )
        return True

    def action_close(self):
        for rec in self:
            if rec.state != "approved":
                raise UserError(_("Solo operaciones aprobadas pueden cerrarse."))
            rec.write({"state": "closed"})
        return True

    def action_reopen(self):
        for rec in self:
            if rec.state not in ("closed", "rejected"):
                raise UserError(_("Solo operaciones cerradas o rechazadas pueden reabrirse."))
            rec.write(
                {
                    "state": "reopened",
                    "validation_state": "pending",
                    "approval_state": "not_requested",
                }
            )
        return True

    # ------------------------------------------------------------------
    # Smart button navigation
    # ------------------------------------------------------------------
    def action_view_sale_orders(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Órdenes de venta"),
            "res_model": "sale.order",
            "view_mode": "list,form",
            "domain": [("id", "in", self.sale_order_ids.ids)],
        }

    def action_view_purchase_orders(self):
        self.ensure_one()
        from .margin_cross_trace import active_purchase_orders

        pos = active_purchase_orders(self.purchase_order_ids)
        return {
            "type": "ir.actions.act_window",
            "name": _("Órdenes de compra"),
            "res_model": "purchase.order",
            "view_mode": "list,form",
            "domain": [("id", "in", pos.ids)],
        }

    def action_view_customer_invoices(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Facturas de cliente"),
            "res_model": "account.move",
            "view_mode": "list,form",
            "domain": [("id", "in", self.customer_invoice_ids.ids)],
        }

    def action_view_vendor_bills(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Facturas de proveedor"),
            "res_model": "account.move",
            "view_mode": "list,form",
            "domain": [("id", "in", self.vendor_bill_ids.ids)],
        }

    def action_view_allocations(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Asignaciones de costo"),
            "res_model": "purchase.sale.cost.allocation",
            "view_mode": "list,form",
            "domain": [("transaction_id", "=", self.id)],
            "context": {"default_transaction_id": self.id, "default_company_id": self.company_id.id},
        }
