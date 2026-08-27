# -*- coding: utf-8 -*-
"""Gestionar compras y costos — hub sale-first INLINE (29.26).

Single operational screen. Cost sources applied via LineAllocationService /
qty.assignment / MTX historical lines. Bulk 4-step wizard stays secondary.
"""
from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools.float_utils import float_compare
from markupsafe import Markup, escape

from odoo.addons.justech_purchase_sale_margin_control.models.margin_acl import (
    assert_hub_open_authorized,
    ensure_canonical_mtx_for_authorized_docs,
    functional_access_denied,
    margin_transaction,
    user_can_read_customer_invoices,
)
from odoo.addons.justech_purchase_sale_margin_control.services.line_allocation_service import (
    LineAllocationService,
    _is_product_line,
)

COVERAGE_STATES = [
    ("complete", "COSTOS COMPLETOS"),
    ("partial", "COSTOS PARCIALES"),
    ("none", "COSTOS PENDIENTES"),
    ("n_a", "N/A"),
]

LINE_STATUS = [
    ("pending", "PENDIENTE"),
    ("partial", "PARCIAL"),
    ("complete", "COMPLETO"),
]

PANEL_MODES = [
    ("", "Ninguno"),
    ("relate", "Relacionar OC"),
    ("historical", "Inventario histórico/manual"),
    ("create_po", "Crear compra"),
]

NO_COST_MARKER = "[SIN_COSTO]"


class PurchaseSaleManagePurchasesWizard(models.TransientModel):
    _name = "purchase.sale.manage.purchases.wizard"
    _description = "Gestionar compras y costos"

    company_id = fields.Many2one("res.company", required=True)
    customer_id = fields.Many2one("res.partner", string="Cliente")
    # Denormalized labels — never depend on MTX or restricted fields for hub header.
    sale_label = fields.Char(string="Venta", readonly=True)
    invoice_label = fields.Char(string="Factura", readonly=True)
    customer_label = fields.Char(string="Cliente", readonly=True)
    salesperson_label = fields.Char(string="Vendedor", readonly=True)
    primary_sale_order_id = fields.Integer(readonly=True)
    is_readonly_mode = fields.Boolean(
        string="Solo consulta",
        readonly=True,
        help="SO cancelada: hub abierto en modo consulta.",
    )
    readonly_banner = fields.Char(readonly=True)
    sale_order_ids = fields.Many2many("sale.order", string="Ventas")
    customer_invoice_ids = fields.Many2many(
        "account.move", string="Facturas de cliente"
    )
    # Server-side only — never put in form view (margin_band ACL on MTX).
    transaction_id = fields.Many2one(
        "purchase.sale.margin.transaction", string="Operación"
    )
    salesperson_id = fields.Many2one("res.users", string="Vendedor comercial")
    registrar_id = fields.Many2one(
        "res.users",
        string="Usuario que registra",
        default=lambda self: self.env.user,
    )
    currency_id = fields.Many2one(
        "res.currency", related="company_id.currency_id", readonly=True
    )
    sale_untaxed = fields.Monetary(
        string="Venta sin ITBIS", currency_field="currency_id", readonly=True
    )
    coverage_pct = fields.Float(string="Cobertura de costos %", readonly=True)
    coverage_state = fields.Selection(COVERAGE_STATES, string="Estado", readonly=True)
    related_po_ids = fields.Many2many("purchase.order", string="Compras ya relacionadas")
    related_supplier_ids = fields.Many2many(
        "res.partner", string="Proveedores ya relacionados"
    )
    header_html = fields.Html(string="Encabezado", sanitize=False, readonly=True)
    coverage_summary_html = fields.Html(
        string="Resumen cobertura", sanitize=False, readonly=True
    )
    documents_html = fields.Html(
        string="Documentos detectados", sanitize=False, readonly=True
    )
    summary_html = fields.Html(string="Resumen", sanitize=False, readonly=True)
    line_ids = fields.One2many(
        "purchase.sale.manage.purchases.wizard.line",
        "wizard_id",
        string="Artículos vendidos / costos pendientes",
    )
    active_line_id = fields.Many2one(
        "purchase.sale.manage.purchases.wizard.line",
        string="Línea en gestión",
    )
    has_pending = fields.Boolean(readonly=True)
    pending_banner = fields.Char(readonly=True)
    sold_line_count = fields.Integer(readonly=True)
    complete_line_count = fields.Integer(readonly=True)
    partial_line_count = fields.Integer(readonly=True)
    pending_line_count = fields.Integer(readonly=True)
    demand_source = fields.Char(readonly=True)
    show_fully_assigned_pos = fields.Boolean(
        string="Auditoría: mostrar OC/POL sin disponible",
        default=False,
        help="Incluye órdenes con cantidad comercial ya agotada (solo referencia).",
    )
    show_more_options = fields.Boolean(
        string="Más opciones",
        default=False,
        help="Opciones masivas / legacy — no forman parte del flujo diario.",
    )
    show_operation_info = fields.Boolean(
        string="Información de la operación",
        default=False,
    )
    show_line_detail = fields.Boolean(default=False)
    detail_html = fields.Html(sanitize=False, readonly=True)
    detail_line_id = fields.Many2one(
        "purchase.sale.manage.purchases.wizard.line", string="Detalle artículo"
    )

    # Related panel fields (active line) for a stable form layout
    panel_mode = fields.Selection(
        related="active_line_id.panel_mode", readonly=False, string="Panel"
    )
    panel_product_label = fields.Char(related="active_line_id.product_name", readonly=True)
    panel_sold_qty = fields.Float(related="active_line_id.sold_qty", readonly=True)
    panel_covered_qty = fields.Float(related="active_line_id.covered_qty", readonly=True)
    panel_purchase_qty = fields.Float(related="active_line_id.purchase_qty", readonly=True)
    panel_historical_qty = fields.Float(
        related="active_line_id.historical_qty", readonly=True
    )
    panel_pending_qty = fields.Float(related="active_line_id.pending_qty", readonly=True)
    panel_stock_available = fields.Float(
        related="active_line_id.stock_available", readonly=True
    )
    panel_stock_qty = fields.Float(
        related="active_line_id.stock_qty", readonly=True
    )
    panel_stock_reserved = fields.Float(
        related="active_line_id.stock_reserved", readonly=True
    )
    panel_supplier_id = fields.Many2one(
        related="active_line_id.supplier_id", readonly=False
    )
    panel_purchase_order_id = fields.Many2one(
        related="active_line_id.purchase_order_id", readonly=False
    )
    panel_purchase_order_domain = fields.Char(
        related="active_line_id.purchase_order_domain", readonly=True
    )
    panel_pol_pick_ids = fields.One2many(
        related="active_line_id.pol_pick_ids", readonly=False
    )
    panel_source_ids = fields.One2many(
        related="active_line_id.source_ids", readonly=True
    )
    panel_hist_qty = fields.Float(related="active_line_id.hist_qty", readonly=False)
    panel_hist_unit_cost = fields.Float(
        related="active_line_id.hist_unit_cost", readonly=False
    )
    panel_hist_note = fields.Char(related="active_line_id.hist_note", readonly=False)
    panel_new_po_supplier_id = fields.Many2one(
        related="active_line_id.new_po_supplier_id", readonly=False
    )
    panel_new_po_qty = fields.Float(related="active_line_id.new_po_qty", readonly=False)
    panel_new_po_price = fields.Float(
        related="active_line_id.new_po_price", readonly=False
    )

    @api.model
    def _resolve_docs_from_context(self):
        ctx = self.env.context
        Invoice = self.env["account.move"]
        Sale = self.env["sale.order"]
        Tx = self.env["purchase.sale.margin.transaction"]

        invoice = Invoice.browse()
        sales = Sale.browse()
        tx = Tx.browse()

        active_model = ctx.get("active_model")
        active_id = ctx.get("active_id")
        if active_model == "account.move" and active_id:
            invoice = Invoice.browse(active_id)
        elif active_model == "sale.order" and active_id:
            sales = Sale.browse(active_id)
        elif active_model == "purchase.sale.margin.transaction" and active_id:
            tx = Tx.browse(active_id)

        if ctx.get("default_customer_invoice_ids"):
            inv_ids = self._m2m_ids(ctx["default_customer_invoice_ids"])
            invoice = Invoice.browse(inv_ids[:1]) if inv_ids else invoice
        if ctx.get("default_sale_order_ids"):
            so_ids = self._m2m_ids(ctx["default_sale_order_ids"])
            sales = Sale.browse(so_ids) if so_ids else sales
        if ctx.get("default_transaction_id"):
            tx = Tx.browse(ctx["default_transaction_id"])

        if invoice and invoice.move_type in ("out_invoice", "out_refund"):
            try:
                sales |= invoice.invoice_line_ids.mapped("sale_line_ids.order_id")
            except AccessError:
                pass
            if not tx:
                try:
                    tx = invoice.margin_transaction_ids[:1]
                except AccessError:
                    tx = margin_transaction(self.env).browse(
                        invoice.sudo().margin_transaction_ids[:1].id
                    ) if invoice.sudo().margin_transaction_ids else tx
        if sales and not tx:
            so = sales[:1]
            company = so.sudo().company_id
            found = margin_transaction(self.env).find_canonical_for_sale(
                so, company=company
            )
            tx = (
                self.env["purchase.sale.margin.transaction"].browse(found.id)
                if found
                else tx
            )
        if tx:
            try:
                sales |= tx.sale_order_ids
            except AccessError:
                sales |= margin_transaction(self.env).browse(tx.id).sale_order_ids
            invoice = invoice or tx.customer_invoice_ids[:1]
            if not invoice:
                invoice = margin_transaction(self.env).browse(
                    tx.id
                ).customer_invoice_ids[:1]
        return invoice, sales, tx

    @staticmethod
    def _m2m_ids(commands):
        ids = []
        if not commands:
            return ids
        for cmd in commands:
            if isinstance(cmd, (list, tuple)) and cmd:
                if cmd[0] == 6 and len(cmd) >= 3:
                    ids.extend(cmd[2] or [])
                elif cmd[0] in (4, 1) and len(cmd) >= 2:
                    ids.append(cmd[1])
        return ids

    _HUB_DOC_M2M = (
        "sale_order_ids",
        "customer_invoice_ids",
        "related_po_ids",
        "related_supplier_ids",
    )

    @api.model
    def default_get(self, fields_list):
        if self.env.context.get("margin_hub_skip_doc_defaults"):
            return super().default_get(fields_list)
        res = super().default_get(fields_list)
        invoice, sales, tx = self._resolve_docs_from_context()
        if not sales and not invoice and not tx:
            return res

        company = False
        if sales:
            company = sales[:1].sudo().company_id
        elif invoice:
            company = invoice.sudo().company_id
        elif tx:
            company = margin_transaction(self.env).browse(tx.id).company_id
        # Always gate open (even when MTX already exists).
        try:
            assert_hub_open_authorized(
                self.env,
                sale_order=sales[:1] if sales else None,
                customer_invoice=invoice if invoice else None,
                transaction=tx if tx else None,
            )
        except AccessError as err:
            raise functional_access_denied(err) from err

        if not tx and (sales or invoice):
            try:
                tx = ensure_canonical_mtx_for_authorized_docs(
                    self.env,
                    sale_order=sales[:1] if sales else None,
                    customer_invoice=invoice if invoice else None,
                    vals={
                        "company_id": company.id if company else False,
                        "customer_invoice_ids": [(4, invoice.id)] if invoice else False,
                    },
                )
            except AccessError as err:
                raise functional_access_denied(err) from err
        elif tx and invoice and invoice.id not in (
            margin_transaction(self.env).browse(tx.id).customer_invoice_ids.ids
        ):
            try:
                # Attach invoice only after SO/invoice already validated via resolve
                margin_transaction(self.env).browse(tx.id).write(
                    {"customer_invoice_ids": [(4, invoice.id)]}
                )
                tx = self.env["purchase.sale.margin.transaction"].browse(tx.id)
            except AccessError as err:
                raise functional_access_denied(err) from err

        tx_s = margin_transaction(self.env).browse(tx.id) if tx else False
        customer = (
            (invoice.sudo().partner_id if invoice else False)
            or (sales[:1].sudo().partner_id if sales else False)
            or (tx_s.customer_id if tx_s else False)
        )
        salesperson = (
            sales[:1].sudo().user_id
            if sales and sales[:1].sudo().user_id
            else (tx_s.salesperson_id if tx_s else False)
        )
        invoices = invoice
        if tx_s:
            invoices |= tx_s.customer_invoice_ids.filtered(
                lambda m: m.move_type in ("out_invoice", "out_refund")
            )
        if sales and not invoices:
            if user_can_read_customer_invoices(self.env):
                invoices = LineAllocationService(self.env).customer_invoices_for_sale_orders(
                    sales, company=company
                )

        sale_untaxed = 0.0
        if invoices:
            for inv in invoices.sudo().filtered(lambda m: m.state == "posted"):
                sale_untaxed += abs(inv.amount_untaxed_signed or inv.amount_untaxed or 0.0)
        elif sales:
            sale_untaxed = sum(sales.sudo().mapped("amount_untaxed"))

        related_po_ids = False
        related_supplier_ids = False
        if tx_s:
            active_pos = tx_s.purchase_order_ids.filtered(lambda p: p.state != "cancel")
            related_po_ids = [(6, 0, active_pos.ids)]
            related_supplier_ids = [(6, 0, tx_s.supplier_ids.ids)]

        primary = sales[:1].sudo() if sales else self.env["sale.order"]
        is_readonly = bool(primary and primary.state == "cancel")
        sale_label = ", ".join(sales.sudo().mapped("name")) if sales else ""
        if not sale_label and tx_s:
            sale_label = ", ".join(tx_s.sale_order_ids.mapped("name"))
        inv_label = ", ".join(
            invoices.sudo().mapped(lambda m: m.name or m.display_name or "")
        ) if invoices else ""

        res.update(
            {
                "company_id": company.id if company else False,
                "customer_id": customer.id if customer else False,
                "customer_label": customer.display_name if customer else "",
                "sale_label": sale_label or "",
                "invoice_label": inv_label or "",
                "salesperson_label": salesperson.display_name if salesperson else "",
                "primary_sale_order_id": primary.id if primary else 0,
                "is_readonly_mode": is_readonly,
                "readonly_banner": (
                    _("OPERACIÓN CANCELADA — SOLO CONSULTA") if is_readonly else False
                ),
                "sale_order_ids": [(6, 0, sales.ids)] if sales else False,
                "customer_invoice_ids": [(6, 0, invoices.ids)] if invoices else False,
                "transaction_id": tx.id if tx else False,
                "salesperson_id": salesperson.id if salesperson else False,
                "sale_untaxed": sale_untaxed,
                "related_po_ids": related_po_ids,
                "related_supplier_ids": related_supplier_ids,
            }
        )
        return res

    @api.model_create_multi
    def create(self, vals_list):
        # Web client sometimes calls create({}) with only action context. Resolving
        # docs via default_get FIRST (real user) is mandatory — otherwise the
        # sudo elevate below skips defaults and the ARTÍCULOS table stays empty.
        enriched = []
        skip_keys = {
            "id",
            "create_uid",
            "create_date",
            "write_uid",
            "write_date",
            "display_name",
        }
        for vals in vals_list:
            vals = dict(vals or {})
            has_docs = bool(
                vals.get("sale_order_ids")
                or vals.get("customer_invoice_ids")
                or vals.get("transaction_id")
                or vals.get("primary_sale_order_id")
            )
            if not has_docs and not self.env.context.get("margin_hub_skip_doc_defaults"):
                defaults = self.default_get(
                    [f for f in self._fields if f not in skip_keys]
                )
                defaults.update({k: v for k, v in vals.items() if k in vals})
                vals = defaults
            enriched.append(vals)
        # Document M2Ms may reference sale.order / purchase.order the hub operator
        # cannot ACL-read. default_get already ran assert_hub_open_authorized —
        # elevate ONLY the transient create write; do not wipe context defaults.
        self_su = self.sudo().with_context(margin_hub_skip_doc_defaults=True)
        records_su = super(PurchaseSaleManagePurchasesWizard, self_su).create(enriched)
        records = self.browse(records_su.ids)
        records._refresh_coverage()
        return records

    def _hub_set_doc_m2m(self, field_commands):
        """Set hub document M2Ms without comodel ACL (post assert_hub_open)."""
        self.ensure_one()
        if not field_commands:
            return True
        # Transient link write as sudo — same scope as create elevation.
        self.sudo().write(field_commands)
        return True

    def _posted_customer_invoices(self):
        self.ensure_one()
        inv = self.sudo().customer_invoice_ids
        if not inv and self.transaction_id:
            inv = margin_transaction(self.env).browse(
                self.transaction_id.id
            ).customer_invoice_ids
        return inv.filtered(
            lambda m: m.state == "posted"
            and m.move_type in ("out_invoice", "out_refund")
        )

    def _hub_historical_qty(self, sol, sold, purchase_qty, transaction):
        """Historical/manual that closes pending: amount>0 or explicit [SIN_COSTO]."""
        from odoo.addons.justech_purchase_sale_margin_control.models.margin_acl import (
            margin_transaction_line,
        )

        Line = margin_transaction_line(self.env)
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
        qty = 0.0
        for line in Line.search(domain):
            amount = line.amount_untaxed or 0.0
            notes = line.notes or ""
            if float_compare(amount, 0.0, precision_digits=4) > 0:
                qty += line.quantity or 0.0
            elif NO_COST_MARKER in notes:
                qty += line.quantity or 0.0
        return min(qty, max(sold - purchase_qty, 0.0))

    def _build_sale_demand_rows(self):
        """Coverage from CostManagementService — never reads margin_band."""
        self.ensure_one()
        from odoo.addons.justech_purchase_sale_margin_control.services.cost_management_service import (
            CostManagementService,
        )

        svc = CostManagementService(self.env)
        sales = self.sudo().sale_order_ids
        if not sales and self.primary_sale_order_id:
            sales = self.env["sale.order"].sudo().browse(self.primary_sale_order_id)
        invoices = self.sudo().customer_invoice_ids
        tx = False
        if self.transaction_id:
            tx = margin_transaction(self.env).browse(self.transaction_id.id)
        rows, source = svc.build_demand_rows(sales, invoices=invoices, transaction=tx)
        self.demand_source = source
        return rows

    def _sale_demand_sols(self):
        """Backward-compatible wrapper."""
        from odoo.addons.justech_purchase_sale_margin_control.services.cost_management_service import (
            CostManagementService,
        )

        sales = self.sudo().sale_order_ids
        if not sales and self.primary_sale_order_id:
            sales = self.env["sale.order"].sudo().browse(self.primary_sale_order_id)
        return CostManagementService(self.env).sale_demand_sols(
            sales, self.sudo().customer_invoice_ids
        )

    def _applied_source_commands(self, sol):
        """Readonly source rows: ASG purchases + historical/manual MTX lines."""
        cmds = []
        tx = self.transaction_id
        if "justech.purchase.sale.qty.assignment" in self.env:
            Assign = self.env["justech.purchase.sale.qty.assignment"].sudo()
            for a in Assign.search(
                [("sale_line_id", "=", sol.id), ("state", "=", "active")]
            ):
                pol = a.purchase_line_id
                unit = 0.0
                if pol and pol.product_qty:
                    unit = (pol.price_subtotal or 0.0) / pol.product_qty
                elif pol:
                    unit = pol.price_unit or 0.0
                cmds.append(
                    (
                        0,
                        0,
                        {
                            "source_kind": "purchase",
                            "label": _("%(partner)s / %(po)s")
                            % {
                                "partner": pol.order_id.partner_id.display_name
                                if pol
                                else "—",
                                "po": pol.order_id.name if pol else "—",
                            },
                            "quantity": a.quantity or 0.0,
                            "unit_cost": unit,
                            "amount": (a.quantity or 0.0) * unit,
                            "purchase_line_id": pol.id if pol else False,
                            "assignment_id": a.id,
                        },
                    )
                )
        # Trace direct POL.sale_line_id links (no ASG row)
        linked_pols = self.env["purchase.order.line"].sudo().search(
            [
                ("sale_line_id", "=", sol.id),
                ("state", "!=", "cancel"),
                ("order_id.state", "!=", "cancel"),
            ]
        )
        asg_pol_ids = {
            c[2].get("purchase_line_id")
            for c in cmds
            if c[2].get("purchase_line_id")
        }
        for pol in linked_pols:
            if pol.id in asg_pol_ids:
                continue
            unit = (
                (pol.price_subtotal or 0.0) / pol.product_qty
                if pol.product_qty
                else (pol.price_unit or 0.0)
            )
            cmds.append(
                (
                    0,
                    0,
                    {
                        "source_kind": "purchase",
                        "label": _("%(partner)s / %(po)s")
                        % {
                            "partner": pol.order_id.partner_id.display_name,
                            "po": pol.order_id.name,
                        },
                        "quantity": pol.product_qty or 0.0,
                        "unit_cost": unit,
                        "amount": (pol.product_qty or 0.0) * unit,
                        "purchase_line_id": pol.id,
                        "assignment_id": False,
                    },
                )
            )
        from odoo.addons.justech_purchase_sale_margin_control.models.margin_acl import (
            margin_transaction_line,
        )

        Line = margin_transaction_line(self.env)
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
        if tx:
            domain.append(("transaction_id", "=", tx.id))
        for line in Line.search(domain):
            amount = line.amount_untaxed or 0.0
            notes = line.notes or ""
            if float_compare(amount, 0.0, precision_digits=4) <= 0 and NO_COST_MARKER not in notes:
                continue
            qty = line.quantity or 0.0
            unit = (amount / qty) if qty else 0.0
            kind = "no_cost" if NO_COST_MARKER in notes else "historical"
            cmds.append(
                (
                    0,
                    0,
                    {
                        "source_kind": kind,
                        "label": line.description
                        or _("Inventario histórico / costo manual"),
                        "quantity": qty,
                        "unit_cost": unit,
                        "amount": amount,
                        "mtx_line_id": line.id,
                    },
                )
            )
        return cmds

    def _stock_info(self, product, company):
        """Odoo stock reference only — never auto-applied."""
        if not product or not company:
            return 0.0, 0.0, 0.0
        qty = reserved = available = 0.0
        try:
            if "qty_available" in product._fields:
                wh_product = product.with_company(company)
                qty = wh_product.qty_available or 0.0
                reserved = getattr(wh_product, "outgoing_qty", 0.0) or 0.0
                available = getattr(wh_product, "free_qty", None)
                if available is None:
                    available = max(qty - reserved, 0.0)
                else:
                    available = available or 0.0
        except Exception:  # noqa: BLE001
            pass
        return qty, reserved, available

    def _refresh_coverage(self, keep_active_line_sol=None, keep_panel_mode=None):
        for wiz in self:
            prev_sol = keep_active_line_sol
            if not prev_sol and wiz.active_line_id:
                prev_sol = wiz.active_line_id.sale_line_id.id
            prev_mode = keep_panel_mode
            if prev_mode is None and wiz.active_line_id:
                prev_mode = wiz.active_line_id.panel_mode or ""
            wiz.line_ids.unlink()
            wiz.active_line_id = False
            rows = wiz._build_sale_demand_rows()
            sold = sum(r["sold_qty"] for r in rows)
            covered = sum(r["purchase_qty"] + r["historical_qty"] for r in rows)
            pending = sum(r["pending_qty"] for r in rows)
            n_complete = sum(1 for r in rows if r["line_status"] == "complete")
            n_partial = sum(1 for r in rows if r["line_status"] == "partial")
            n_pending = sum(1 for r in rows if r["line_status"] == "pending")
            if not rows:
                state = "n_a"
                pct = 0.0
            elif float_compare(pending, 0.0, precision_digits=4) <= 0:
                state = "complete"
                pct = 100.0
            elif float_compare(covered, 0.0, precision_digits=4) <= 0:
                state = "none"
                pct = 0.0
            else:
                state = "partial"
                pct = (covered / sold * 100.0) if sold else 0.0
            wiz.coverage_state = state
            wiz.coverage_pct = pct
            wiz.has_pending = float_compare(pending, 0.0, precision_digits=4) > 0
            wiz.pending_banner = (
                _(
                    "COSTOS PENDIENTES — hay cantidades sin cubrir "
                    "(inventario + compra)"
                )
                if wiz.has_pending
                else False
            )
            wiz.sold_line_count = len(rows)
            wiz.complete_line_count = n_complete
            wiz.partial_line_count = n_partial
            wiz.pending_line_count = n_pending
            line_cmds = []
            for r in rows:
                sol = self.env["sale.order.line"].sudo().browse(r["sale_line_id"])
                from odoo.addons.justech_purchase_sale_margin_control.services.cost_management_service import (
                    CostManagementService,
                )

                stock_qty, stock_res, stock_av = CostManagementService(
                    wiz.env
                ).stock_info(sol.product_id, wiz.company_id)
                can_select = (
                    float_compare(r["pending_qty"], 0.0, precision_digits=4) > 0
                )
                line_cmds.append(
                    (
                        0,
                        0,
                        {
                            "sale_line_id": r["sale_line_id"],
                            "product_id": r.get("product_id"),
                            "product_name": r["product_name"],
                            "sold_qty": r["sold_qty"],
                            "purchase_qty": r["purchase_qty"],
                            "historical_qty": r["historical_qty"],
                            "pending_qty": r["pending_qty"],
                            "pending_receive_qty": r.get("pending_receive_qty") or 0.0,
                            "line_status": r["line_status"],
                            "selection_allowed": can_select,
                            "selected": False,
                            "stock_qty": stock_qty,
                            "stock_reserved": stock_res,
                            "stock_available": stock_av,
                            "source_ids": wiz._applied_source_commands(sol),
                            "hist_qty": r["pending_qty"],
                            "new_po_qty": r["pending_qty"],
                        },
                    )
                )
            if line_cmds:
                wiz.write({"line_ids": line_cmds})
            if prev_sol:
                match = wiz.line_ids.filtered(lambda l: l.sale_line_id.id == prev_sol)[:1]
                if match:
                    wiz.active_line_id = match.id
                    if prev_mode:
                        match.panel_mode = prev_mode
            if tx := wiz.transaction_id:
                tx_s = margin_transaction(wiz.env).browse(tx.id)
                wiz._hub_set_doc_m2m(
                    {
                        "related_po_ids": [(
                            6,
                            0,
                            tx_s.purchase_order_ids.filtered(lambda p: p.state != "cancel").ids,
                        )],
                        "related_supplier_ids": [(6, 0, tx_s.supplier_ids.ids)],
                    }
                )
            wiz._rebuild_html_blocks(state, pct)

    def _rebuild_html_blocks(self, state, pct):
        self.ensure_one()
        sale_names = self.sale_label or "—"
        inv_names = self.invoice_label or "—"
        state_label = dict(COVERAGE_STATES).get(state, state)
        banner = ""
        if self.is_readonly_mode:
            banner = (
                "<p class='text-warning mb-1'><strong>%s</strong></p>"
                % escape(self.readonly_banner or _("SOLO CONSULTA"))
            )
        self.header_html = Markup(
            "<div class='o_manage_purchases_header'>"
            "%s"
            "<p class='mb-1'><b>GESTIONAR COMPRAS</b></p>"
            "<p class='mb-0'><b>%s</b> · %s</p>"
            "</div>"
        ) % (
            Markup(banner),
            escape(sale_names),
            escape(self.customer_label or self.customer_id.display_name or "—"),
        )
        pending_note = (
            Markup("<p class='text-danger mb-1'><strong>%s</strong></p>")
            % escape(self.pending_banner)
            if self.has_pending
            else Markup(
                "<p class='text-success mb-1'><strong>%s</strong></p>"
                % escape(_("🟢 Todos los costos cubiertos"))
            )
        )
        self.coverage_summary_html = Markup(
            "<div class='o_manage_purchases_cov_summary'>"
            "%s"
            "<p class='mb-0 text-muted'>%s artículos · "
            "%s cubiertos · %s parciales · %s sin cubrir</p>"
            "</div>"
        ) % (
            pending_note,
            self.sold_line_count,
            self.complete_line_count,
            self.partial_line_count,
            self.pending_line_count,
        )
        self.documents_html = Markup(
            "<div class='o_manage_purchases_docs text-muted'>"
            "<p class='mb-0'><b>Venta:</b> %s · <b>Factura:</b> %s</p>"
            "<p class='mb-0'><b>Cliente:</b> %s · <b>Vendedor:</b> %s</p>"
            "<p class='mb-0'><b>Venta sin ITBIS:</b> %s</p>"
            "</div>"
        ) % (
            escape(sale_names),
            escape(inv_names),
            escape(self.customer_label or self.customer_id.display_name or "—"),
            escape(self.salesperson_label or self.salesperson_id.display_name or "—"),
            escape(str(self.sale_untaxed or 0.0)),
        )
        self.summary_html = self.header_html

    def _ensure_transaction(self):
        self.ensure_one()
        if self.transaction_id:
            # Return sudo-safe browse id as user recordset without reading restricted fields
            return self.env["purchase.sale.margin.transaction"].browse(
                self.transaction_id.id
            )
        sales = self.sudo().sale_order_ids
        if not sales and self.primary_sale_order_id:
            sales = self.env["sale.order"].sudo().browse(self.primary_sale_order_id)
        invoices = self.sudo().customer_invoice_ids
        if not sales and not invoices:
            raise UserError(_("No hay venta/factura para gestionar costos."))
        try:
            tx = ensure_canonical_mtx_for_authorized_docs(
                self.env,
                sale_order=sales[:1],
                customer_invoice=invoices[:1],
            )
        except AccessError as err:
            raise functional_access_denied(err) from err
        self.sudo().write({"transaction_id": tx.id})
        return self.env["purchase.sale.margin.transaction"].browse(tx.id)

    def _hub_mtx_write(self, vals):
        """Write MTX document links with technical elevation after hub validation."""
        self.ensure_one()
        tx = self._ensure_transaction()
        try:
            margin_transaction(self.env).browse(tx.id).write(vals)
        except AccessError as err:
            raise functional_access_denied(err) from err
        return self.env["purchase.sale.margin.transaction"].browse(tx.id)

    def action_reopen_hub(self, refresh=False, keep_sol=None, keep_panel=None):
        """Re-show hub form. Refresh coverage only after apply (not panel nav).

        Panel open/close must NOT unlink line rows (MissingError + lost POL picks).
        """
        self.ensure_one()
        if refresh:
            active_sol = keep_sol
            if not active_sol and self.active_line_id:
                active_sol = self.active_line_id.sale_line_id.id
            panel = keep_panel
            if panel is None and self.active_line_id:
                panel = self.active_line_id.panel_mode or ""
            self._refresh_coverage(
                keep_active_line_sol=active_sol, keep_panel_mode=panel or ""
            )
        return {
            "type": "ir.actions.act_window",
            "name": _("Gestionar compras"),
            "res_model": "purchase.sale.manage.purchases.wizard",
            "view_mode": "form",
            "views": [(False, "form")],
            "res_id": self.id,
            "target": "new",
        }

    def action_close_panel(self):
        self.ensure_one()
        if self.active_line_id:
            self.active_line_id.write(
                {
                    "panel_mode": "",
                    "supplier_id": False,
                    "purchase_order_id": False,
                    "pol_pick_ids": [(5, 0, 0)],
                }
            )
        self.active_line_id = False
        return self.action_reopen_hub(refresh=False)

    def action_relate_existing_purchases(self):
        """Bulk secondary: canonical 4-step wizard (not the daily path)."""
        self.ensure_one()
        tx = self._ensure_transaction()
        act = tx.action_relate_purchases()
        ctx = dict(act.get("context") or {})
        ctx["manage_purchases_wizard_id"] = self.id
        act["context"] = ctx
        return act

    def action_create_purchase_order(self):
        """Bulk secondary: Trace buy-pending / create PO."""
        self.ensure_one()
        so = self.sale_order_ids[:1]
        if not so:
            raise UserError(_("No hay orden de venta vinculada para crear una OC."))
        if hasattr(so, "action_justech_buy_pending"):
            action = so.action_justech_buy_pending()
            ctx = dict(action.get("context") or {})
            ctx.update(
                {
                    "manage_purchases_wizard_id": self.id,
                    "default_sale_order_id": so.id,
                }
            )
            action["context"] = ctx
            return action
        raise UserError(
            _(
                "El módulo de trazabilidad de compras no está disponible. "
                "Use «Crear compra» en la línea del producto."
            )
        )

    def action_open_historical_cost(self):
        """Bulk secondary: historical wizard for all pending lines."""
        self.ensure_one()
        tx = self._ensure_transaction()
        return {
            "type": "ir.actions.act_window",
            "name": _("Inventario histórico / costo manual"),
            "res_model": "purchase.sale.historical.cost.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_manage_wizard_id": self.id,
                "default_transaction_id": tx.id,
                "default_company_id": self.company_id.id,
            },
        }

    @api.onchange("panel_purchase_order_id", "show_fully_assigned_pos")
    def _onchange_panel_purchase_order(self):
        """Autoload POL when OC changes in the inline panel."""
        line = self.active_line_id
        if line:
            line.purchase_order_id = self.panel_purchase_order_id
            line._onchange_purchase_order_id()

    @api.onchange("panel_supplier_id")
    def _onchange_panel_supplier(self):
        line = self.active_line_id
        if line:
            line.supplier_id = self.panel_supplier_id
            line._onchange_supplier_id()

    def action_apply_relate_panel(self):
        self.ensure_one()
        line = self.active_line_id
        if not line:
            raise UserError(_("Seleccione un producto con [Gestionar costo]."))
        # Ensure POL candidates loaded even if onchange did not fire
        if line.purchase_order_id and not line.pol_pick_ids:
            line.action_reload_pol_picks()
        return line.action_apply_relate()

    def action_apply_historical_panel(self):
        self.ensure_one()
        line = self.active_line_id
        if not line:
            raise UserError(_("Seleccione un producto con [Gestionar costo]."))
        return line.action_apply_historical()

    def action_apply_create_po_panel(self):
        self.ensure_one()
        line = self.active_line_id
        if not line:
            raise UserError(_("Seleccione un producto con [Gestionar costo]."))
        return line.action_apply_create_po()

    def action_panel_relate(self):
        self.ensure_one()
        if not self.active_line_id:
            raise UserError(_("Seleccione un producto con [Gestionar costo]."))
        return self.active_line_id.action_set_panel_relate()

    def action_panel_another_po(self):
        """Same as relate: add another purchase/supplier source for this line."""
        return self.action_panel_relate()

    def action_panel_historical(self):
        self.ensure_one()
        if not self.active_line_id:
            raise UserError(_("Seleccione un producto con [Gestionar costo]."))
        return self.active_line_id.action_set_panel_historical()

    def action_panel_create_po(self):
        self.ensure_one()
        if not self.active_line_id:
            raise UserError(_("Seleccione un producto con [Gestionar costo]."))
        return self.active_line_id.action_set_panel_create_po()

    def action_toggle_more_options(self):
        self.ensure_one()
        self.show_more_options = not self.show_more_options
        return self.action_reopen_hub(refresh=False)

    def action_toggle_operation_info(self):
        self.ensure_one()
        self.show_operation_info = not self.show_operation_info
        return self.action_reopen_hub(refresh=False)

    def _pending_hub_lines(self):
        """Lines with remaining qty to cover."""
        self.ensure_one()
        return self.line_ids.filtered(
            lambda l: float_compare(l.pending_qty or 0.0, 0.0, precision_digits=4) > 0
        )

    def _clear_complete_selection(self):
        """Complete lines stay visible but never stay selected for new actions."""
        self.ensure_one()
        complete = self.line_ids.filtered(
            lambda l: float_compare(l.pending_qty or 0.0, 0.0, precision_digits=4) <= 0
        )
        if complete:
            complete.write({"selected": False})

    def action_select_all_lines(self):
        """Seleccionar todas = solo artículos con cantidad pendiente."""
        self.ensure_one()
        if self.is_readonly_mode:
            raise UserError(_("OPERACIÓN CANCELADA — SOLO CONSULTA"))
        self.line_ids.write({"selected": False})
        pending = self._pending_hub_lines()
        if pending:
            pending.write({"selected": True})
        return self.action_reopen_hub(refresh=False)

    def action_clear_selection(self):
        self.ensure_one()
        self.line_ids.write({"selected": False})
        return self.action_reopen_hub(refresh=False)

    def _selected_hub_lines(self):
        """Selected lines that still have pending qty (suggest only remaining)."""
        self.ensure_one()
        selected = self.line_ids.filtered(
            lambda l: l.selected
            and float_compare(l.pending_qty or 0.0, 0.0, precision_digits=4) > 0
        )
        if not selected:
            raise UserError(
                _("Seleccione al menos un artículo con cantidad pendiente.")
            )
        return selected

    def action_open_create_purchase(self):
        self.ensure_one()
        if self.is_readonly_mode:
            raise UserError(_("OPERACIÓN CANCELADA — SOLO CONSULTA"))
        lines = self._selected_hub_lines()
        cmds = []
        for line in lines:
            price = line.product_id.standard_price if line.product_id else 0.0
            pending = line.pending_qty or 0.0
            cmds.append(
                (
                    0,
                    0,
                    {
                        "sale_line_id": line.sale_line_id.id,
                        "product_id": line.product_id.id,
                        "product_name": line.product_name,
                        "pending_qty": pending,
                        "buy_qty": pending,
                        "sale_cover_qty": pending,
                        "assign_qty": pending,
                        "price_unit": price or 0.0,
                        "currency_id": self.company_id.currency_id.id,
                    },
                )
            )
        if not cmds:
            raise UserError(
                _("Los artículos seleccionados ya están cubiertos. Elija líneas pendientes.")
            )
        wiz = self.env["purchase.sale.cost.create.purchase.wizard"].create(
            {
                "hub_wizard_id": self.id,
                "company_id": self.company_id.id,
                "step": "prepare",
                "line_ids": cmds,
            }
        )
        return {
            "type": "ir.actions.act_window",
            "name": _("Crear nueva compra"),
            "res_model": "purchase.sale.cost.create.purchase.wizard",
            "res_id": wiz.id,
            "view_mode": "form",
            "views": [(False, "form")],
            "target": "new",
        }

    def action_open_link_purchase(self):
        self.ensure_one()
        if self.is_readonly_mode:
            raise UserError(_("OPERACIÓN CANCELADA — SOLO CONSULTA"))
        lines = self._selected_hub_lines()
        wiz = self.env["purchase.sale.cost.link.wizard"].create(
            {
                "hub_wizard_id": self.id,
                "company_id": self.company_id.id,
                "mode": "po",
                "sale_line_ids": [(6, 0, lines.mapped("sale_line_id").ids)],
            }
        )
        return {
            "type": "ir.actions.act_window",
            "name": _("Vincular compra existente"),
            "res_model": "purchase.sale.cost.link.wizard",
            "res_id": wiz.id,
            "view_mode": "form",
            "views": [(False, "form")],
            "target": "new",
        }

    def action_open_inventory(self):
        self.ensure_one()
        if self.is_readonly_mode:
            raise UserError(_("OPERACIÓN CANCELADA — SOLO CONSULTA"))
        lines = self._selected_hub_lines()
        from odoo.addons.justech_purchase_sale_margin_control.services.cost_management_service import (
            CostManagementService,
        )

        svc = CostManagementService(self.env)
        cmds = []
        for line in lines:
            sq, sr, sa = svc.stock_info(line.product_id, self.company_id)
            pending = line.pending_qty or 0.0
            cmds.append(
                (
                    0,
                    0,
                    {
                        "sale_line_id": line.sale_line_id.id,
                        "product_id": line.product_id.id,
                        "product_name": line.product_name,
                        "pending_qty": pending,
                        "stock_qty": sq,
                        "stock_reserved": sr,
                        "stock_available": sa,
                        "use_qty": pending,
                        "unit_cost": (line.product_id.standard_price or 0.0)
                        if line.product_id
                        else 0.0,
                    },
                )
            )
        wiz = self.env["purchase.sale.cost.inventory.wizard"].create(
            {
                "hub_wizard_id": self.id,
                "company_id": self.company_id.id,
                "mode": "historical",
                "line_ids": cmds,
            }
        )
        return {
            "type": "ir.actions.act_window",
            "name": _("Usar inventario"),
            "res_model": "purchase.sale.cost.inventory.wizard",
            "res_id": wiz.id,
            "view_mode": "form",
            "views": [(False, "form")],
            "target": "new",
        }

    def action_close_line_detail(self):
        self.ensure_one()
        self.write(
            {"show_line_detail": False, "detail_html": False, "detail_line_id": False}
        )
        return self.action_reopen_hub(refresh=False)

    def action_detail_add_source(self):
        """From detail: select this line only and stay on hub for the 3 actions."""
        self.ensure_one()
        line = self.detail_line_id
        if not line:
            raise UserError(_("No hay artículo en detalle."))
        self.line_ids.write({"selected": False})
        line.selected = True
        self.show_line_detail = False
        return self.action_reopen_hub(refresh=False)

    def _rebuild_line_detail_html(self, line):
        """Human article card — no technical fields / IDs / domains."""
        self.ensure_one()
        currency = self.company_id.currency_id

        def _fmt_money(amount):
            try:
                return currency.format(amount or 0.0)
            except Exception:  # noqa: BLE001
                return "%.2f" % (amount or 0.0)

        status = line.line_status or ""
        if status == "complete":
            status_txt = "🟢 Costo cubierto"
        elif status == "partial":
            status_txt = "🟡 Parcial"
        else:
            status_txt = "🔴 Sin cubrir"

        purchase_bits = []
        inventory_bits = []
        for src in line.source_ids:
            kind = src.source_kind or ""
            label = src.label or "—"
            unit = src.unit_cost or 0.0
            row = (
                "<li><b>%s</b><br/>%s unidades × %s<br/>Costo estimado %s</li>"
                % (
                    escape(label),
                    src.quantity or 0.0,
                    escape(_fmt_money(unit)),
                    escape(_fmt_money(src.amount or 0.0)),
                )
            )
            if kind in ("historical", "no_cost"):
                inventory_bits.append(row)
            else:
                purchase_bits.append(row)
        if not purchase_bits and not inventory_bits:
            purchase_bits = [
                "<li class='text-muted'>%s</li>"
                % escape(_("Todavía no hay fuente de costo."))
            ]

        receive_row = ""
        if float_compare(line.pending_receive_qty or 0.0, 0.0, precision_digits=4) > 0:
            receive_row = (
                "<tr><td>Pendiente de recibir</td>"
                "<td class='text-end'><b>%s</b></td></tr>"
                % (line.pending_receive_qty or 0.0)
            )

        html = Markup(
            "<div class='o_cost_line_detail'>"
            "<h4 class='mb-2'>%s</h4>"
            "<p class='text-muted mb-2'>%s</p>"
            "<table class='table table-sm mb-2' style='width:auto'>"
            "<tr><td>Vendido</td><td class='text-end'><b>%s</b></td></tr>"
            "<tr><td>Desde inventario</td><td class='text-end'><b>%s</b></td></tr>"
            "<tr><td>Ordenado a proveedor</td><td class='text-end'><b>%s</b></td></tr>"
            "<tr><td>Sin cubrir</td><td class='text-end'><b>%s</b></td></tr>"
            "%s"
            "<tr><td>Estado</td><td class='text-end'><b>%s</b></td></tr>"
            "</table>"
            "<p class='mb-1'><b>%s</b></p>"
            "<ul class='mb-2'>%s</ul>"
            "<p class='mb-1'><b>%s</b></p>"
            "<ul class='mb-0'>%s</ul>"
            "</div>"
        ) % (
            escape(_("DETALLE DE COSTO")),
            escape(line.product_name or ""),
            line.sold_qty or 0.0,
            line.historical_qty or 0.0,
            line.purchase_qty or 0.0,
            line.pending_qty or 0.0,
            Markup(receive_row),
            escape(status_txt),
            escape(_("Fuente de compra")),
            Markup("".join(purchase_bits)),
            escape(_("Inventario / manual")),
            Markup(
                "".join(inventory_bits)
                or (
                    "<li class='text-muted'>%s</li>"
                    % escape(_("Sin inventario asignado"))
                )
            ),
        )
        return html

    def action_detail_open_purchase(self):
        """Open first related PO from detail sources."""
        self.ensure_one()
        line = self.detail_line_id
        if not line:
            raise UserError(_("No hay artículo en detalle."))
        pol = line.source_ids.mapped("purchase_line_id")[:1]
        if not pol:
            raise UserError(_("No hay orden de compra vinculada a este artículo."))
        return {
            "type": "ir.actions.act_window",
            "name": _("Orden de compra"),
            "res_model": "purchase.order",
            "res_id": pol.order_id.id,
            "view_mode": "form",
            "views": [(False, "form")],
            "target": "current",
        }

    def action_add_another_source(self):
        """Keep product selected; clear source panel so user picks again."""
        self.ensure_one()
        line = self.active_line_id
        if not line:
            raise UserError(_("Seleccione un producto con [Gestionar costo]."))
        line.write(
            {
                "panel_mode": "",
                "supplier_id": False,
                "purchase_order_id": False,
                "pol_pick_ids": [(5, 0, 0)],
                "hist_qty": line.pending_qty,
                "new_po_qty": line.pending_qty,
            }
        )
        return self.action_reopen_hub(refresh=False)

    def action_load_po_lines(self):
        """Explicit reload when OC selected (onchange may not persist in dialog)."""
        self.ensure_one()
        line = self.active_line_id
        if not line:
            raise UserError(_("Seleccione un producto con [Gestionar costo]."))
        if not line.purchase_order_id and self.panel_purchase_order_id:
            line.purchase_order_id = self.panel_purchase_order_id
        return line.action_reload_pol_picks()


class PurchaseSaleManagePurchasesWizardLine(models.TransientModel):
    _name = "purchase.sale.manage.purchases.wizard.line"
    _description = "Línea de cobertura Gestionar compras"

    wizard_id = fields.Many2one(
        "purchase.sale.manage.purchases.wizard", required=True, ondelete="cascade"
    )
    sale_line_id = fields.Many2one("sale.order.line", string="Línea venta")
    product_id = fields.Many2one("product.product", string="Producto")
    product_name = fields.Char(string="Producto")
    selected = fields.Boolean(string=" ", default=False)
    sold_qty = fields.Float(string="Vendido", digits="Product Unit of Measure")
    purchase_qty = fields.Float(
        string="En compra", digits="Product Unit of Measure"
    )
    historical_qty = fields.Float(
        string="Inventario", digits="Product Unit of Measure"
    )
    covered_qty = fields.Float(
        string="Cubierto",
        digits="Product Unit of Measure",
        compute="_compute_covered_qty",
        store=True,
    )
    pending_qty = fields.Float(
        string="Sin cubrir", digits="Product Unit of Measure"
    )
    pending_receive_qty = fields.Float(
        string="Pendiente de recibir", digits="Product Unit of Measure"
    )
    selection_allowed = fields.Boolean(default=True)
    line_status = fields.Selection(LINE_STATUS, string="Estado", default="pending")
    status_label = fields.Char(compute="_compute_status_label", string="Estado")
    stock_qty = fields.Float(string="Existencia Odoo", digits="Product Unit of Measure")
    stock_reserved = fields.Float(string="Reservado", digits="Product Unit of Measure")
    stock_available = fields.Float(
        string="Disponible Odoo", digits="Product Unit of Measure"
    )
    panel_mode = fields.Selection(PANEL_MODES, default="", string="Panel activo")
    source_ids = fields.One2many(
        "purchase.sale.manage.purchases.wizard.source",
        "line_id",
        string="Fuentes ya aplicadas",
    )
    # Relate OC panel
    supplier_id = fields.Many2one(
        "res.partner",
        string="Proveedor",
        domain="[('supplier_rank', '>', 0)]",
    )
    purchase_order_id = fields.Many2one("purchase.order", string="Orden de compra")
    purchase_order_domain = fields.Char(compute="_compute_purchase_order_domain")
    pol_pick_ids = fields.One2many(
        "purchase.sale.manage.purchases.wizard.pol",
        "line_id",
        string="Artículos de la OC",
    )
    # Historical panel
    hist_qty = fields.Float(string="Cantidad histórica", digits="Product Unit of Measure")
    hist_unit_cost = fields.Float(string="Costo unitario")
    hist_note = fields.Char(string="Motivo / justificación")
    # Create PO panel
    new_po_supplier_id = fields.Many2one(
        "res.partner",
        string="Proveedor nueva OC",
        domain="[('supplier_rank', '>', 0)]",
    )
    new_po_qty = fields.Float(
        string="Cantidad a comprar", digits="Product Unit of Measure"
    )
    new_po_price = fields.Float(string="Precio unitario OC")

    @api.depends("purchase_qty", "historical_qty")
    def _compute_covered_qty(self):
        for rec in self:
            rec.covered_qty = (rec.purchase_qty or 0.0) + (rec.historical_qty or 0.0)

    @api.depends("line_status")
    def _compute_status_label(self):
        icons = {"pending": "🔴", "partial": "🟡", "complete": "🟢"}
        labels = {
            "pending": "Sin cubrir",
            "partial": "Parcial",
            "complete": "Cubierto",
        }
        for rec in self:
            st = rec.line_status or "pending"
            rec.status_label = "%s %s" % (icons.get(st, ""), labels.get(st, st))

    @api.depends("supplier_id", "wizard_id.company_id", "wizard_id.show_fully_assigned_pos")
    def _compute_purchase_order_domain(self):
        for rec in self:
            company = rec.wizard_id.company_id
            supplier = rec.supplier_id
            if not company or not supplier:
                rec.purchase_order_domain = repr([("id", "=", False)])
                continue
            domain = [
                ("company_id", "=", company.id),
                ("partner_id", "child_of", supplier.commercial_partner_id.id),
                ("state", "!=", "cancel"),
            ]
            rec.purchase_order_domain = repr(domain)

    def action_manage_line(self):
        """Read-only detail for pending/partial lines; no action when fully covered."""
        self.ensure_one()
        if self.line_status == "complete":
            return True
        wiz = self.wizard_id
        wiz.detail_line_id = self.id
        wiz.detail_html = wiz._rebuild_line_detail_html(self)
        wiz.show_line_detail = True
        return wiz.action_reopen_hub(refresh=False)

    def action_set_panel_relate(self):
        self.ensure_one()
        self.wizard_id.active_line_id = self.id
        self.panel_mode = "relate"
        return self.wizard_id.action_reopen_hub(refresh=False)

    def action_set_panel_historical(self):
        self.ensure_one()
        self.wizard_id.active_line_id = self.id
        self.panel_mode = "historical"
        self.hist_qty = self.pending_qty
        return self.wizard_id.action_reopen_hub(refresh=False)

    def action_set_panel_create_po(self):
        self.ensure_one()
        self.wizard_id.active_line_id = self.id
        self.panel_mode = "create_po"
        self.new_po_qty = self.pending_qty
        if self.product_id:
            self.new_po_price = self.product_id.standard_price or 0.0
        return self.wizard_id.action_reopen_hub(refresh=False)

    @api.onchange("supplier_id")
    def _onchange_supplier_id(self):
        self.purchase_order_id = False
        self.pol_pick_ids = [(5, 0, 0)]

    @api.onchange("purchase_order_id")
    def _onchange_purchase_order_id(self):
        """Autoload POL candidates — no extra button."""
        self.pol_pick_ids = [(5, 0, 0)]
        po = self.purchase_order_id
        if not po:
            return
        svc = LineAllocationService(self.env)
        cmds = []
        focus_product = self.product_id
        pols = po.order_line.filtered(_is_product_line)
        # Prefer matching product first
        ordered = pols.sorted(
            key=lambda p: 0 if focus_product and p.product_id == focus_product else 1
        )
        show_zero = self.wizard_id.show_fully_assigned_pos
        for pol in ordered:
            if pol.order_id.state == "cancel" or pol.state == "cancel":
                continue
            avail = svc.pol_qty_available(pol)
            # Hide exhausted lines unless auditoría (show_fully_assigned_pos)
            if (
                not show_zero
                and float_compare(avail, 0.0, precision_digits=4) <= 0
            ):
                continue
            unit = (
                (pol.price_subtotal or 0.0) / pol.product_qty
                if pol.product_qty
                else (pol.price_unit or 0.0)
            )
            # Never auto-fill Usar — user must type the quantity.
            cmds.append(
                (
                    0,
                    0,
                    {
                        "purchase_line_id": pol.id,
                        "product_id": pol.product_id.id,
                        "qty_purchased": pol.product_qty or 0.0,
                        "qty_assigned": max((pol.product_qty or 0.0) - avail, 0.0),
                        "qty_available": avail,
                        "unit_cost": unit,
                        "qty_to_use": 0.0,
                        "is_focus_product": bool(
                            focus_product and pol.product_id == focus_product
                        ),
                    },
                )
            )
        self.pol_pick_ids = cmds

    def action_reload_pol_picks(self):
        self.ensure_one()
        self._onchange_purchase_order_id()
        return self.wizard_id.action_reopen_hub(refresh=False)

    def action_apply_relate(self):
        self.ensure_one()
        wiz = self.wizard_id
        sol_id = self.sale_line_id.id
        tx = wiz._ensure_transaction()
        svc = LineAllocationService(
            self.env(context=dict(self.env.context, margin_hub_mtx_elevate=True))
        )
        picks = self.pol_pick_ids.filtered(
            lambda p: float_compare(p.qty_to_use or 0.0, 0.0, precision_digits=4) > 0
        )
        if not picks:
            raise UserError(
                _("Indique al menos una cantidad «Usar ahora» en los artículos de la OC.")
            )
        total = sum(picks.mapped("qty_to_use"))
        if float_compare(total, self.pending_qty or 0.0, precision_digits=4) > 0:
            raise UserError(
                _(
                    "No puede relacionar %(qty)s: solo hay %(pending)s pendiente de costo."
                )
                % {"qty": total, "pending": self.pending_qty}
            )
        sol = self.sale_line_id
        if sol.company_id != wiz.company_id:
            raise ValidationError(_("La línea de venta pertenece a otra compañía."))
        rows = []
        for pick in picks:
            pol = pick.purchase_line_id
            if pol.company_id != wiz.company_id:
                raise ValidationError(
                    _("La OC %s pertenece a otra compañía.") % (pol.order_id.name,)
                )
            rows.append(
                {
                    "sale_line": sol,
                    "purchase_line": pol,
                    "quantity": pick.qty_to_use,
                }
            )
        try:
            svc.apply_allocations_to_transaction(tx, rows, replace=False)
            wiz._hub_mtx_write(
                {
                    "purchase_order_ids": [
                        (4, p.purchase_line_id.order_id.id) for p in picks
                    ],
                    "supplier_ids": [
                        (
                            4,
                            p.purchase_line_id.order_id.partner_id.commercial_partner_id.id,
                        )
                        for p in picks
                    ],
                }
            )
            tx = wiz.transaction_id
            if hasattr(tx, "_sync_lines_from_documents"):
                margin_transaction(self.env).browse(tx.id).with_context(
                    skip_line_sync=False, margin_skip_unsafe_po_cost=True
                )._sync_lines_from_documents()
        except AccessError as err:
            raise functional_access_denied(err) from err
        return wiz.action_reopen_hub(refresh=True, keep_sol=sol_id, keep_panel="")

    def action_apply_historical(self):
        self.ensure_one()
        wiz = self.wizard_id
        sol_id = self.sale_line_id.id
        tx = wiz._ensure_transaction()
        qty = self.hist_qty or 0.0
        if float_compare(qty, 0.0, precision_digits=4) <= 0:
            raise UserError(_("Indique la cantidad a cubrir con inventario/histórico."))
        if float_compare(qty, self.pending_qty or 0.0, precision_digits=4) > 0:
            raise UserError(
                _("No puede cubrir %(qty)s: pendiente %(pending)s.")
                % {"qty": qty, "pending": self.pending_qty}
            )
        if float_compare(self.hist_unit_cost or 0.0, 0.0, precision_digits=4) < 0:
            raise UserError(_("El costo unitario no puede ser negativo."))
        amount = qty * (self.hist_unit_cost or 0.0)
        note = (self.hist_note or "").strip()
        sol = self.sale_line_id
        from odoo.addons.justech_purchase_sale_margin_control.models.margin_acl import (
            margin_transaction_line,
        )

        try:
            margin_transaction_line(self.env).create(
                {
                    "transaction_id": tx.id,
                    "line_type": "cost",
                    "data_origin": "manual",
                    "cost_source": "inventory",
                    "sale_order_id": sol.order_id.id,
                    "sale_order_line_id": sol.id,
                    "product_id": self.product_id.id,
                    "description": _("Inventario histórico / costo manual — %s")
                    % (self.product_id.display_name or ""),
                    "currency_id": wiz.currency_id.id,
                    "quantity": qty,
                    "amount_untaxed": amount,
                    "amount_total": amount,
                    "is_manual": True,
                    "notes": note
                    or _(
                        "Solo Costos y Márgenes. Sin stock, sin asiento, sin recepción."
                    ),
                }
            )
        except AccessError as err:
            raise functional_access_denied(err) from err
        return wiz.action_reopen_hub(refresh=True, keep_sol=sol_id, keep_panel="")

    def action_apply_create_po(self):
        """Create PO for requested qty; ASG only min(pending, purchased) to this sale."""
        self.ensure_one()
        wiz = self.wizard_id
        sol_id = self.sale_line_id.id
        tx = wiz._ensure_transaction()
        supplier = self.new_po_supplier_id
        buy_qty = self.new_po_qty or 0.0
        if not supplier:
            raise UserError(_("Seleccione el proveedor de la nueva compra."))
        if float_compare(buy_qty, 0.0, precision_digits=4) <= 0:
            raise UserError(_("Indique la cantidad a comprar."))
        if self.product_id.company_id and self.product_id.company_id != wiz.company_id:
            # product may be shared; only enforce SO company
            pass
        sol = self.sale_line_id
        if sol.company_id != wiz.company_id:
            raise ValidationError(_("La venta pertenece a otra compañía."))
        assign_qty = min(buy_qty, self.pending_qty or 0.0)
        if float_compare(assign_qty, 0.0, precision_digits=4) <= 0:
            raise UserError(
                _("No hay pendiente de costo para vincular. Ajuste la cantidad.")
            )
        po_line_vals = {
            "product_id": self.product_id.id,
            "name": self.product_id.display_name,
            "product_qty": buy_qty,
            "price_unit": self.new_po_price or 0.0,
            "date_planned": fields.Datetime.now(),
        }
        if "product_uom_id" in self.env["purchase.order.line"]._fields:
            po_line_vals["product_uom_id"] = self.product_id.uom_id.id
        elif "product_uom" in self.env["purchase.order.line"]._fields:
            po_line_vals["product_uom"] = self.product_id.uom_id.id
        po = self.env["purchase.order"].create(
            {
                "partner_id": supplier.id,
                "company_id": wiz.company_id.id,
                "order_line": [(0, 0, po_line_vals)],
            }
        )
        if hasattr(po, "button_confirm"):
            try:
                po.button_confirm()
            except Exception:  # noqa: BLE001 — draft PO still usable for ASG
                pass
        pol = po.order_line.filtered(_is_product_line)[:1]
        if not pol:
            raise UserError(_("No se pudo crear la línea de compra."))
        svc = LineAllocationService(
            self.env(context=dict(self.env.context, margin_hub_mtx_elevate=True))
        )
        try:
            svc.apply_allocations_to_transaction(
                tx,
                [{"sale_line": sol, "purchase_line": pol, "quantity": assign_qty}],
                replace=False,
            )
            wiz._hub_mtx_write(
                {
                    "purchase_order_ids": [(4, po.id)],
                    "supplier_ids": [(4, supplier.commercial_partner_id.id)],
                }
            )
            tx = wiz.transaction_id
            if hasattr(tx, "_sync_lines_from_documents"):
                margin_transaction(self.env).browse(tx.id).with_context(
                    skip_line_sync=False, margin_skip_unsafe_po_cost=True
                )._sync_lines_from_documents()
        except AccessError as err:
            raise functional_access_denied(err) from err
        return wiz.action_reopen_hub(refresh=True, keep_sol=sol_id, keep_panel="")


class PurchaseSaleManagePurchasesWizardSource(models.TransientModel):
    _name = "purchase.sale.manage.purchases.wizard.source"
    _description = "Fuente de costo aplicada (hub)"

    line_id = fields.Many2one(
        "purchase.sale.manage.purchases.wizard.line", required=True, ondelete="cascade"
    )
    source_kind = fields.Selection(
        [
            ("purchase", "Compra"),
            ("historical", "Inventario/manual"),
            ("no_cost", "Sin costo"),
        ],
        required=True,
    )
    label = fields.Char(string="Fuente")
    quantity = fields.Float(string="Cantidad", digits="Product Unit of Measure")
    unit_cost = fields.Float(string="Costo unitario")
    amount = fields.Float(string="Costo")
    purchase_line_id = fields.Many2one("purchase.order.line")
    assignment_id = fields.Integer()
    mtx_line_id = fields.Many2one("purchase.sale.margin.transaction.line")

    def action_remove_source(self):
        """Cancel ASG or unlink historical MTX line; refresh hub coverage."""
        self.ensure_one()
        hub = self.line_id.wizard_id
        sol = self.line_id.sale_line_id
        if self.source_kind == "purchase" and self.assignment_id:
            Assign = self.env["justech.purchase.sale.qty.assignment"]
            asg = Assign.browse(self.assignment_id)
            if asg.exists() and asg.state == "active":
                if hasattr(asg, "action_cancel"):
                    asg.action_cancel()
                else:
                    asg.write({"state": "cancelled"})
            # Soft-remove matching estimated MTX cost for this POL if present
            tx = hub.transaction_id
            pol = self.purchase_line_id
            if tx and pol:
                est = self.env["purchase.sale.margin.transaction.line"].search(
                    [
                        ("transaction_id", "=", tx.id),
                        ("purchase_order_line_id", "=", pol.id),
                        ("line_type", "=", "cost"),
                        ("data_origin", "=", "estimated"),
                    ]
                )
                if est:
                    est.with_context(skip_line_sync=True).unlink()
        elif self.source_kind in ("historical", "no_cost") and self.mtx_line_id:
            self.mtx_line_id.with_context(skip_line_sync=True).unlink()
        else:
            raise UserError(_("No se puede eliminar esta fuente."))
        tx = hub.transaction_id
        if tx and hasattr(tx, "_sync_lines_from_documents"):
            tx.with_context(
                skip_line_sync=False, margin_skip_unsafe_po_cost=True
            )._sync_lines_from_documents()
        return hub.action_reopen_hub(
            refresh=True, keep_sol=sol.id if sol else None, keep_panel=""
        )


class PurchaseSaleManagePurchasesWizardPol(models.TransientModel):
    _name = "purchase.sale.manage.purchases.wizard.pol"
    _description = "POL candidata inline (hub)"

    line_id = fields.Many2one(
        "purchase.sale.manage.purchases.wizard.line", required=True, ondelete="cascade"
    )
    purchase_line_id = fields.Many2one("purchase.order.line", required=True)
    product_id = fields.Many2one("product.product", string="Producto")
    qty_purchased = fields.Float(string="Comprado")
    qty_assigned = fields.Float(string="Ya usado")
    qty_available = fields.Float(string="Disponible")
    unit_cost = fields.Float(string="Costo unitario")
    qty_to_use = fields.Float(string="Usar ahora")
    is_focus_product = fields.Boolean(string="Producto de la venta")


# Keep model for ACL compatibility; primary UX no longer opens it.
class PurchaseSaleManageLineSourceWizard(models.TransientModel):
    _name = "purchase.sale.manage.line.source.wizard"
    _description = "Fuente de costo (legacy modal — no primary UX)"

    company_id = fields.Many2one("res.company", required=True)
    manage_wizard_id = fields.Many2one("purchase.sale.manage.purchases.wizard")
    hub_line_id = fields.Many2one("purchase.sale.manage.purchases.wizard.line")
    sale_line_id = fields.Many2one("sale.order.line", required=True)
    product_id = fields.Many2one("product.product", required=True)
    pending_qty = fields.Float(readonly=True)
    product_label = fields.Char(compute="_compute_product_label")
    no_cost_reason = fields.Text(string="Motivo (marcar sin costo)")

    @api.depends("product_id", "pending_qty")
    def _compute_product_label(self):
        for wiz in self:
            wiz.product_label = _("%(prod)s — pendiente: %(qty).2f") % {
                "prod": wiz.product_id.display_name or "",
                "qty": wiz.pending_qty or 0.0,
            }

    def action_relate_existing(self):
        self.ensure_one()
        hub = self.manage_wizard_id
        line = self.hub_line_id or hub.line_ids.filtered(
            lambda l: l.sale_line_id == self.sale_line_id
        )[:1]
        if line:
            return line.action_set_panel_relate()
        return hub.action_relate_existing_purchases()

    def action_create_po(self):
        self.ensure_one()
        hub = self.manage_wizard_id
        line = self.hub_line_id or hub.line_ids.filtered(
            lambda l: l.sale_line_id == self.sale_line_id
        )[:1]
        if line:
            return line.action_set_panel_create_po()
        return hub.action_create_purchase_order()

    def action_historical(self):
        self.ensure_one()
        hub = self.manage_wizard_id
        line = self.hub_line_id or hub.line_ids.filtered(
            lambda l: l.sale_line_id == self.sale_line_id
        )[:1]
        if line:
            return line.action_set_panel_historical()
        return hub.action_open_historical_cost()

    def action_mark_no_cost(self):
        self.ensure_one()
        reason = (self.no_cost_reason or "").strip()
        if not reason:
            raise UserError(_("Indique el motivo para marcar sin costo."))
        hub = self.manage_wizard_id
        tx = hub._ensure_transaction()
        sol = self.sale_line_id
        note = _("%(marker)s Motivo: %(reason)s | Usuario: %(user)s | Fecha: %(date)s") % {
            "marker": NO_COST_MARKER,
            "reason": reason,
            "user": self.env.user.display_name,
            "date": fields.Datetime.now(),
        }
        self.env["purchase.sale.margin.transaction.line"].create(
            {
                "transaction_id": tx.id,
                "line_type": "cost",
                "data_origin": "manual",
                "cost_source": "manual",
                "sale_order_id": sol.order_id.id,
                "sale_order_line_id": sol.id,
                "product_id": self.product_id.id,
                "description": _("Sin costo — %s") % (self.product_id.display_name or ""),
                "currency_id": hub.currency_id.id,
                "quantity": self.pending_qty,
                "amount_untaxed": 0.0,
                "amount_total": 0.0,
                "is_manual": True,
                "notes": note,
            }
        )
        return hub.action_reopen_hub(
            refresh=True, keep_sol=sol.id, keep_panel=""
        )
