# -*- coding: utf-8 -*-
from odoo import _, api, fields, models


class PurchaseSaleMarginBoard(models.TransientModel):
    """Resumen Financiero: full-page KPI board (NOT a target=new modal).

    company_id is intentionally optional: when left empty the board
    consolidates every company in self.env.companies (the user's currently
    allowed/active companies), never companies outside that set. Setting
    company_id narrows the KPIs to that single company, but only if it is
    part of the allowed companies.
    """

    _name = "purchase.sale.margin.board"
    _description = "Resumen financiero de margen compra-venta"

    company_id = fields.Many2one(
        "res.company", string="Compañía", required=False,
        help="Vacío = todas las compañías permitidas para el usuario actual.",
    )
    company_ids = fields.Many2many(
        "res.company", string="Compañías consolidadas", compute="_compute_company_ids",
    )
    context_label = fields.Char(string="Alcance", compute="_compute_context_label")
    date_from = fields.Date(default=lambda self: fields.Date.context_today(self).replace(month=1, day=1))
    date_to = fields.Date(default=fields.Date.context_today)
    currency_id = fields.Many2one("res.currency", compute="_compute_currency_id")

    # KPIs ------------------------------------------------------------
    # total_sales_amount = VENTAS REALES contables (account.move posted), NOT MTX sum.
    total_sales_amount = fields.Monetary(
        currency_field="currency_id", readonly=True, string="Ventas reales",
        help="Suma contable neta: out_invoice − out_refund posted (amount_untaxed_signed). "
             "No depende de MTX.",
    )
    total_sales_count = fields.Integer(
        readonly=True, string="Facturas",
        help="Cantidad de facturas cliente posted (out_invoice) en el período.",
    )
    posted_credit_note_count = fields.Integer(
        readonly=True, string="Notas de crédito",
        help="Cantidad de notas de crédito cliente posted (out_refund) en el período.",
    )
    gross_sales_amount = fields.Monetary(
        currency_field="currency_id", readonly=True, string="Facturación bruta",
        help="Suma amount_untaxed_signed de out_invoice posted (sin restar NC).",
    )
    credit_note_amount = fields.Monetary(
        currency_field="currency_id", readonly=True, string="Notas de crédito (importe)",
        help="Importe absoluto de NC posted (out_refund) en moneda compañía.",
    )
    estimated_sales_amount = fields.Monetary(
        currency_field="currency_id", readonly=True, string="Ventas estimadas",
        help="SO confirmadas aún no facturadas. Separadas de ventas reales; no se suman al KPI Ventas.",
    )
    margin_ops_count = fields.Integer(
        readonly=True, string="Operaciones con margen",
        help="Operaciones canónicas con venta + costo (margen calculable).",
    )
    conciliated_sales_amount = fields.Monetary(
        currency_field="currency_id", readonly=True, string="Ventas conciliadas",
    )
    conciliated_sales_count = fields.Integer(readonly=True, string="Ventas conciliadas (cant.)")
    sales_without_cost_amount = fields.Monetary(
        currency_field="currency_id", readonly=True, string="Ventas sin costo",
    )
    sales_without_cost_count = fields.Integer(readonly=True, string="Ventas sin costo (cant.)")
    purchases_without_sale_amount = fields.Monetary(
        currency_field="currency_id", readonly=True, string="Compras sin venta",
    )
    purchases_without_sale_count = fields.Integer(readonly=True, string="Compras sin venta (cant.)")

    estimated_margin_total = fields.Monetary(
        currency_field="currency_id", readonly=True, string="Margen estimado",
    )
    confirmed_real_margin = fields.Monetary(
        currency_field="currency_id", readonly=True, string="Margen real confirmado",
        help="Relaciones Venta↔Costo confirmadas (validated/approved/closed). "
             "Costo: Vendor Bill real si existe; si no, costo comprometido de PO. "
             "No suma PO+Bill.",
    )
    confirmed_real_margin_pct = fields.Float(readonly=True, string="Margen real confirmado %")

    admin_expense_amount = fields.Monetary(
        currency_field="currency_id", readonly=True, string="Gastos administrativos",
    )
    admin_expense_count = fields.Integer(readonly=True, string="Gastos administrativos (cant.)")
    inventory_pending_amount = fields.Monetary(
        currency_field="currency_id", readonly=True, string="Inventario pendiente",
    )
    inventory_pending_count = fields.Integer(readonly=True, string="Inventario pendiente (cant.)")
    negative_margin_count = fields.Integer(readonly=True, string="Márgenes negativos")

    pending_relation_count = fields.Integer(readonly=True, string="Pendientes de relación")
    pending_review_count = fields.Integer(readonly=True, string="Pendientes de revisión")
    pending_validation_count = fields.Integer(readonly=True, string="Pendientes de validación")
    pending_approval_count = fields.Integer(readonly=True, string="Pendientes de aprobación")

    # 19.0.3.0.0: KPIs del Auxiliar de Cuentas por Pagar
    purchases_recovered_amount = fields.Monetary(
        currency_field="currency_id", readonly=True, string="Compras con costo recuperado",
    )
    purchases_recovered_count = fields.Integer(readonly=True, string="Compras con costo recuperado (cant.)")
    purchases_pending_recovery = fields.Monetary(
        currency_field="currency_id", readonly=True, string="Compras pendientes de recuperar",
    )
    purchases_pending_recovery_count = fields.Integer(readonly=True, string="Compras pendientes de recuperar (cant.)")
    purchases_pending_payment_count = fields.Integer(readonly=True, string="Compras pendientes de pago")
    purchases_without_sale_aux_count = fields.Integer(readonly=True, string="Compras sin venta (CxP)")
    cost_recovery_percent = fields.Float(readonly=True, string="% de recuperación de costo")
    committed_vendor_flow = fields.Monetary(
        currency_field="currency_id",
        readonly=True,
        string="Facturas proveedor abiertas",
        help="Residual signed de facturas/NC proveedor posted al corte. "
             "No incluye asientos CXP Accionistas ni pagos sin conciliar.",
    )

    # ------------------------------------------------------------------
    # Company scoping
    # ------------------------------------------------------------------
    def _get_scope_companies(self):
        self.ensure_one()
        allowed = self.env.companies
        if self.company_id:
            return self.company_id if self.company_id in allowed else allowed
        return allowed

    @api.depends("company_id")
    def _compute_company_ids(self):
        for rec in self:
            rec.company_ids = rec._get_scope_companies()

    @api.depends("company_id")
    def _compute_context_label(self):
        for rec in self:
            companies = rec._get_scope_companies()
            if rec.company_id and rec.company_id in self.env.companies:
                rec.context_label = _("Compañía: %s") % rec.company_id.name
            else:
                rec.context_label = _("Consolidado multiempresa (%s)") % len(companies)

    included_companies_label = fields.Char(
        string="Compañías incluidas",
        compute="_compute_included_companies_label",
    )

    @api.depends("company_id", "company_ids")
    def _compute_included_companies_label(self):
        for rec in self:
            companies = rec._get_scope_companies()
            rec.included_companies_label = ", ".join(companies.mapped("name")) or _("Ninguna")

    @api.depends("company_id")
    def _compute_currency_id(self):
        for rec in self:
            rec.currency_id = (rec.company_id or self.env.company).currency_id

    # ------------------------------------------------------------------
    # KPI computation
    # ------------------------------------------------------------------
    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        # Optional company: empty = consolidate all currently allowed companies.
        # Never recurse through self.new() / related field defaults.
        company_id = res.get("company_id") or False
        allowed = self.env.companies
        if company_id:
            company = self.env["res.company"].browse(company_id)
            companies = company if company in allowed else allowed
            if company not in allowed:
                company_id = False
        else:
            companies = allowed
        res["company_id"] = company_id or False
        date_from = res.get("date_from")
        date_to = res.get("date_to")
        if not date_from:
            date_from = fields.Date.context_today(self).replace(month=1, day=1)
            res["date_from"] = date_from
        if not date_to:
            date_to = fields.Date.context_today(self)
            res["date_to"] = date_to
        res.update(self._compute_kpis(companies, date_from, date_to))
        return res

    def _domain_base(self, companies):
        domain = [("company_id", "in", companies.ids)]
        if self.date_from:
            domain.append(("transaction_date", ">=", self.date_from))
        if self.date_to:
            domain.append(("transaction_date", "<=", self.date_to))
        return domain

    def _domain_base_aux(self, companies):
        domain = [("company_id", "in", companies.ids)]
        if self.date_from:
            domain.append(("invoice_date", ">=", self.date_from))
        if self.date_to:
            domain.append(("invoice_date", "<=", self.date_to))
        return domain

    def _posted_customer_move_domain(self, companies, date_from=None, date_to=None):
        """Accounting SoT for real sales: posted customer invoices/refunds by invoice_date."""
        domain = [
            ("company_id", "in", companies.ids),
            ("state", "=", "posted"),
            ("move_type", "in", ("out_invoice", "out_refund")),
        ]
        if date_from:
            domain.append(("invoice_date", ">=", date_from))
        if date_to:
            domain.append(("invoice_date", "<=", date_to))
        return domain

    def _accounting_sales_moves(self, companies, date_from=None, date_to=None):
        """Return posted customer moves strictly scoped to ``companies`` (cross-company = 0)."""
        Move = self.env["account.move"]
        moves = Move.search(self._posted_customer_move_domain(companies, date_from, date_to))
        # Hard guard: never leak another company's documents into the KPI.
        return moves.filtered(lambda m: m.company_id in companies)

    def _estimated_unbilled_sales_amount(self, companies, date_from=None, date_to=None):
        """Confirmed SO not fully invoiced — never mixed into accounting Ventas reales."""
        SaleOrder = self.env["sale.order"]
        domain = [
            ("company_id", "in", companies.ids),
            ("state", "in", ("sale", "done")),
            ("invoice_status", "in", ("to invoice", "no")),
        ]
        if date_from:
            domain.append(("date_order", ">=", fields.Datetime.to_datetime(date_from)))
        if date_to:
            domain.append(("date_order", "<=", "%s 23:59:59" % date_to))
        orders = SaleOrder.search(domain)
        total = 0.0
        for order in orders:
            amount = order.amount_untaxed or 0.0
            company_currency = order.company_id.currency_id
            if order.currency_id and company_currency and order.currency_id != company_currency:
                amount = order.currency_id._convert(
                    amount,
                    company_currency,
                    order.company_id,
                    (order.date_order.date() if order.date_order else fields.Date.context_today(self)),
                )
            total += amount
        return total

    def _mtx_linked_customer_invoice_ids(self, companies):
        Transaction = self.env["purchase.sale.margin.transaction"]
        txs = Transaction.search([("company_id", "in", companies.ids)])
        linked = txs.mapped("customer_invoice_ids")
        if "primary_customer_invoice_id" in Transaction._fields:
            linked |= txs.mapped("primary_customer_invoice_id")
        return set(linked.ids)

    @api.model
    def _tx_best_available_sale(self, tx):
        """Prefer posted/real sale; fall back to SO/estimated."""
        return tx.sale_real_amount or tx.sale_estimated_amount or 0.0

    @api.model
    def _tx_best_available_cost(self, tx):
        """Bill/manual real cost replaces PO committed — never PO+Bill."""
        if tx.margin_is_calculable and (tx.cost_real_amount or 0.0):
            return tx.cost_real_amount or 0.0
        return tx.cost_estimated_amount or 0.0

    @api.model
    def _tx_confirmed_relation_margin(self, tx):
        """Margin for a confirmed Sale↔Cost relation using best available amounts."""
        sale = self._tx_best_available_sale(tx)
        cost = self._tx_best_available_cost(tx)
        if not sale or not cost:
            return 0.0
        return sale - cost

    def _compute_kpis(self, companies, date_from=None, date_to=None):
        Transaction = self.env["purchase.sale.margin.transaction"]
        Link = self.env["purchase.sale.cost.link"]
        Auxiliary = self.env["purchase.sale.payable.auxiliary"]

        domain = [("company_id", "in", companies.ids)]
        if date_from:
            domain.append(("transaction_date", ">=", date_from))
        if date_to:
            domain.append(("transaction_date", "<=", date_to))

        aux_domain = [("company_id", "in", companies.ids)]
        if date_from:
            aux_domain.append(("invoice_date", ">=", date_from))
        if date_to:
            aux_domain.append(("invoice_date", "<=", date_to))
        all_aux = Auxiliary.search(aux_domain)
        recovered_aux = all_aux.filtered(
            lambda a: a.recovery_percent and a.recovery_percent >= 99.99
        )
        pending_recovery_aux = all_aux.filtered(
            lambda a: (a.recovery_percent or 0.0) < 99.99
        )
        pending_payment_aux = all_aux.filtered(
            lambda a: a.payment_state != "paid" and not a.manually_closed
        )
        without_sale_aux = all_aux.filtered(
            lambda a: not (a.transaction_ids or a.sale_order_ids or a.customer_invoice_ids)
        )
        total_aux_base = sum(all_aux.mapped("amount_untaxed"))
        total_aux_recovered = sum(all_aux.mapped("recovered_cost_amount"))

        all_tx = Transaction.search(domain)
        # Confirmed relation (post-29.9 auto-confirm → validated) — not only Finanzas approved.
        confirmed_tx = all_tx.filtered(
            lambda t: t.state in ("validated", "approved", "closed")
            and t.transaction_type != "administrative"
            and not t.sale_without_cost
            and t.has_related_sale
            and t.has_related_cost
        )
        conciliated_tx = all_tx.filtered(lambda t: t.has_related_cost and t.margin_is_calculable)
        without_cost_tx = all_tx.filtered(lambda t: t.sale_without_cost)
        without_sale_tx = all_tx.filtered(lambda t: t.has_related_cost and not t.has_related_sale)
        admin_tx = all_tx.filtered(lambda t: t.transaction_type == "administrative")
        inventory_tx = all_tx.filtered(lambda t: t.transaction_type == "inventory" and not t.has_related_sale)
        negative_tx = confirmed_tx.filtered(lambda t: self._tx_confirmed_relation_margin(t) < 0)

        confirmed_real_margin = sum(self._tx_confirmed_relation_margin(t) for t in confirmed_tx)
        # Margen % solo sobre ventas de operaciones con relación confirmada.
        confirmed_sale_base = sum(
            self._tx_best_available_sale(t)
            for t in confirmed_tx
            if self._tx_best_available_cost(t)
        )

        # ---- Accounting source of truth for VENTAS REALES ----
        acc_moves = self._accounting_sales_moves(companies, date_from, date_to)
        invoices = acc_moves.filtered(lambda m: m.move_type == "out_invoice")
        refunds = acc_moves.filtered(lambda m: m.move_type == "out_refund")
        accounting_net = sum(acc_moves.mapped("amount_untaxed_signed"))
        accounting_gross = sum(invoices.mapped("amount_untaxed_signed"))
        credit_note_abs = abs(sum(refunds.mapped("amount_untaxed_signed")))

        # Posted invoices without MTX (still real sales; classify as sin costo operativo).
        linked_invoice_ids = self._mtx_linked_customer_invoice_ids(companies)
        unlinked_invoices = invoices.filtered(lambda m: m.id not in linked_invoice_ids)
        swc_amount = sum(without_cost_tx.mapped("sale_real_amount")) + sum(
            unlinked_invoices.mapped("amount_untaxed_signed")
        )
        swc_count = len(without_cost_tx) + len(unlinked_invoices)

        # Admin costs are intentionally excluded from cost_real_amount (commercial
        # margin). Aggregate them from transaction lines for the dedicated KPI.
        admin_expense_amount = 0.0
        for tx in admin_tx:
            classified = tx.line_ids.filtered(
                lambda l: l.line_type == "cost"
                and l.cost_usage_type == "administrative_expense"
                and l.state != "excluded"
                and not l.exclude_from_margin
            )
            if classified:
                admin_expense_amount += sum(classified.mapped("amount_company_currency"))
            else:
                admin_expense_amount += sum(
                    tx.line_ids.filtered(
                        lambda l: l.line_type == "cost"
                        and l.state != "excluded"
                        and not l.exclude_from_margin
                    ).mapped("amount_company_currency")
                )

        return {
            "total_sales_amount": accounting_net,
            "total_sales_count": len(invoices),
            "posted_credit_note_count": len(refunds),
            "gross_sales_amount": accounting_gross,
            "credit_note_amount": credit_note_abs,
            "estimated_sales_amount": self._estimated_unbilled_sales_amount(companies, date_from, date_to),
            "margin_ops_count": len(conciliated_tx),
            "conciliated_sales_amount": sum(conciliated_tx.mapped("sale_real_amount")),
            "conciliated_sales_count": len(conciliated_tx),
            "sales_without_cost_amount": swc_amount,
            "sales_without_cost_count": swc_count,
            "purchases_without_sale_amount": sum(without_sale_tx.mapped("cost_real_amount")),
            "purchases_without_sale_count": len(without_sale_tx),
            "estimated_margin_total": sum(all_tx.mapped("estimated_margin")),
            "confirmed_real_margin": confirmed_real_margin,
            "confirmed_real_margin_pct": (confirmed_real_margin / confirmed_sale_base * 100.0) if confirmed_sale_base else 0.0,
            "admin_expense_amount": admin_expense_amount,
            "admin_expense_count": len(admin_tx),
            "inventory_pending_amount": sum(inventory_tx.mapped("cost_estimated_amount")),
            "inventory_pending_count": len(inventory_tx),
            "negative_margin_count": len(negative_tx),
            "pending_relation_count": Link.search_count(
                [("company_id", "in", companies.ids), ("state", "in", ("draft", "suggested"))]
            ),
            "pending_review_count": Transaction.search_count(
                domain + [("state", "in", ("draft", "detected", "pending_review"))]
            ),
            "pending_validation_count": Transaction.search_count(domain + [("state", "=", "pending_review")]),
            "pending_approval_count": Transaction.search_count(domain + [("state", "=", "validated")]),
            "purchases_recovered_amount": sum(recovered_aux.mapped("recovered_cost_amount")),
            "purchases_recovered_count": len(recovered_aux),
            "purchases_pending_recovery": sum(pending_recovery_aux.mapped("pending_recovery_amount")),
            "purchases_pending_recovery_count": len(pending_recovery_aux),
            "purchases_pending_payment_count": len(pending_payment_aux),
            "purchases_without_sale_aux_count": len(without_sale_aux),
            "cost_recovery_percent": (total_aux_recovered / total_aux_base * 100.0) if total_aux_base else 0.0,
            # Placeholder: 8.26 overwrites with accounting vendor-bill residual.
            "committed_vendor_flow": sum(pending_payment_aux.mapped("amount_residual")),
        }

    def action_refresh(self):
        self.ensure_one()
        vals = self._compute_kpis(self._get_scope_companies(), self.date_from, self.date_to)
        self.write(vals)
        return self.get_board_action(res_id=self.id)

    @api.model
    def get_board_action(self, res_id=False):
        if not res_id:
            board = self.create({})
            res_id = board.id
        return {
            "type": "ir.actions.act_window",
            "name": _("Resumen Financiero"),
            "res_model": "purchase.sale.margin.board",
            "res_id": res_id,
            "view_mode": "form",
            "view_id": self.env.ref(
                "justech_purchase_sale_margin_control.view_purchase_sale_margin_board_form"
            ).id,
            "target": "current",
        }

    # ------------------------------------------------------------------
    # KPI drill-down buttons -> filtered transaction/allocation lists
    # ------------------------------------------------------------------
    def _open_transactions(self, name, domain):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": name,
            "res_model": "purchase.sale.margin.transaction",
            "view_mode": "list,form",
            "domain": domain,
        }

    def action_open_all_sales(self):
        """Drill-down to posted customer invoices/refunds (accounting SoT), not MTX."""
        companies = self._get_scope_companies()
        domain = self._posted_customer_move_domain(companies, self.date_from, self.date_to)
        return {
            "type": "ir.actions.act_window",
            "name": _("Ventas reales (contabilidad)"),
            "res_model": "account.move",
            "view_mode": "list,form",
            "domain": domain,
            "context": {
                "default_move_type": "out_invoice",
                "create": False,
            },
        }

    def action_open_conciliated_sales(self):
        companies = self._get_scope_companies()
        return self._open_transactions(
            _("Ventas conciliadas"),
            self._domain_base(companies) + [("has_related_cost", "=", True), ("margin_is_calculable", "=", True)],
        )

    def action_open_sales_without_cost(self):
        companies = self._get_scope_companies()
        return self._open_transactions(
            _("Ventas sin costos"), self._domain_base(companies) + [("sale_without_cost", "=", True)]
        )

    def action_open_purchases_without_sale(self):
        companies = self._get_scope_companies()
        return self._open_transactions(
            _("Compras sin venta"),
            self._domain_base(companies) + [("has_related_cost", "=", True), ("has_related_sale", "=", False)],
        )

    def action_open_confirmed_margin(self):
        companies = self._get_scope_companies()
        return self._open_transactions(
            _("Margen confirmado"),
            self._domain_base(companies)
            + [
                ("state", "in", ("validated", "approved", "closed")),
                ("sale_without_cost", "=", False),
                ("has_related_sale", "=", True),
                ("has_related_cost", "=", True),
                ("transaction_type", "!=", "administrative"),
            ],
        )

    def action_open_admin_expenses(self):
        companies = self._get_scope_companies()
        return self._open_transactions(
            _("Gastos administrativos"), self._domain_base(companies) + [("transaction_type", "=", "administrative")]
        )

    def action_open_inventory_pending(self):
        companies = self._get_scope_companies()
        return self._open_transactions(
            _("Inventario pendiente"),
            self._domain_base(companies) + [("transaction_type", "=", "inventory"), ("has_related_sale", "=", False)],
        )

    def action_open_negative_margins(self):
        companies = self._get_scope_companies()
        return self._open_transactions(
            _("Márgenes negativos"),
            self._domain_base(companies) + [("real_margin", "<", 0), ("margin_is_calculable", "=", True)],
        )

    def action_open_pending_review(self):
        companies = self._get_scope_companies()
        return self._open_transactions(
            _("Pendientes de revisión"),
            self._domain_base(companies) + [("state", "in", ("draft", "detected", "pending_review"))],
        )

    def action_open_pending_validation(self):
        companies = self._get_scope_companies()
        return self._open_transactions(
            _("Pendientes de validación"), self._domain_base(companies) + [("state", "=", "pending_review")]
        )

    def action_open_pending_approval(self):
        companies = self._get_scope_companies()
        return self._open_transactions(
            _("Pendientes de aprobación"), self._domain_base(companies) + [("state", "=", "validated")]
        )

    def action_open_pending_relation(self):
        self.ensure_one()
        companies = self._get_scope_companies()
        return {
            "type": "ir.actions.act_window",
            "name": _("Pendientes de relación"),
            "res_model": "purchase.sale.cost.link",
            "view_mode": "list,form",
            "domain": [("company_id", "in", companies.ids), ("state", "in", ("draft", "suggested"))],
        }

    # ------------------------------------------------------------------
    # 19.0.3.0.0 — drill-down a purchase.sale.payable.auxiliary
    # ------------------------------------------------------------------
    def _open_auxiliary(self, name, domain):
        return {
            "type": "ir.actions.act_window",
            "name": name,
            "res_model": "purchase.sale.payable.auxiliary",
            "view_mode": "list,form",
            "domain": domain,
        }

    def action_open_purchases_recovered(self):
        companies = self._get_scope_companies()
        return self._open_auxiliary(
            _("Compras con costo recuperado"),
            self._domain_base_aux(companies) + [("recovery_percent", ">=", 99.99)],
        )

    def action_open_purchases_pending_recovery(self):
        companies = self._get_scope_companies()
        return self._open_auxiliary(
            _("Compras pendientes de recuperar"),
            self._domain_base_aux(companies) + [("recovery_percent", "<", 99.99)],
        )

    def action_open_purchases_pending_payment(self):
        companies = self._get_scope_companies()
        return self._open_auxiliary(
            _("Compras pendientes de pago"),
            self._domain_base_aux(companies) + [("payment_state", "!=", "paid"), ("manually_closed", "=", False)],
        )

    def action_open_purchases_without_sale_aux(self):
        companies = self._get_scope_companies()
        return self._open_auxiliary(
            _("Compras sin venta relacionada"),
            self._domain_base_aux(companies)
            + [("transaction_ids", "=", False), ("sale_order_ids", "=", False), ("customer_invoice_ids", "=", False)],
        )
