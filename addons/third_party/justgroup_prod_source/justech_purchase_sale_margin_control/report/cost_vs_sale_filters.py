# -*- coding: utf-8 -*-
"""19.0.8.9.0 — Filtros de pago/cobro y etiquetas gerenciales (solo presentación).

No altera fórmulas de margen; filtra operaciones y etiqueta con payment_state /
amount_residual estándar de Contabilidad.
"""
from odoo import _, api, fields, models


VENDOR_PAY_BADGE = {
    "not_paid": ("PENDIENTE", "#B91C1C"),
    "partial": ("PARCIAL", "#CA8A04"),
    "in_payment": ("EN PROCESO", "#2563EB"),
    "paid": ("PAGADA", "#15803D"),
    "reversed": ("REVERTIDA", "#64748B"),
}

CUSTOMER_PAY_BADGE = {
    "not_paid": ("Pendiente de cobro", "#B91C1C"),
    "partial": ("Cobro parcial", "#CA8A04"),
    "in_payment": ("En proceso de cobro", "#2563EB"),
    "paid": ("Cobrada", "#15803D"),
    "reversed": ("Revertida", "#64748B"),
}

MARGIN_STATE_SHORT = {
    "positive": ("SALUDABLE", "#15803D"),
    "low": ("BAJO", "#CA8A04"),
    "negative": ("NEGATIVO", "#DC2626"),
    "pending": ("PENDIENTE", "#64748B"),
}

FINANCE_VIEW_MAP = {
    "all": ("all", "all"),
    "vendor_payable": ("not_paid", "all"),
    "vendor_paid": ("paid", "all"),
    "customer_receivable": ("all", "not_paid"),
    "customer_collected": ("all", "paid"),
    "collected_vendor_pending": ("not_paid", "paid"),
    "paid_vendor_customer_pending": ("paid", "not_paid"),
    "fully_closed": ("paid", "paid"),
    "with_balance": ("all", "all"),
}


class PurchaseSaleCostVsSaleReport(models.TransientModel):
    _inherit = "purchase.sale.cost.vs.sale.report"

    vendor_id = fields.Many2one(
        "res.partner",
        string="Proveedor",
        domain="[('supplier_rank', '>', 0)]",
    )
    customer_id = fields.Many2one(
        "res.partner",
        string="Cliente",
        domain="[('customer_rank', '>', 0)]",
    )
    vendor_payment_state = fields.Selection(
        [
            ("all", "Todas"),
            ("not_paid", "Pendientes de pago"),
            ("paid", "Pagadas"),
            ("partial", "Pago parcial"),
            ("in_payment", "En proceso de pago"),
        ],
        string="Estado de pago proveedor",
        default="all",
        required=True,
    )
    customer_payment_state = fields.Selection(
        [
            ("all", "Todas"),
            ("not_paid", "Pendientes de cobro"),
            ("paid", "Cobradas"),
            ("partial", "Cobro parcial"),
            ("in_payment", "En proceso de cobro"),
        ],
        string="Estado de cobro cliente",
        default="all",
        required=True,
    )
    finance_view = fields.Selection(
        [
            ("all", "Todas las operaciones"),
            ("vendor_payable", "Proveedores por pagar"),
            ("vendor_paid", "Proveedores pagados"),
            ("customer_receivable", "Clientes por cobrar"),
            ("customer_collected", "Clientes cobrados"),
            ("collected_vendor_pending", "Cobrado cliente / proveedor pendiente"),
            ("paid_vendor_customer_pending", "Proveedor pagado / cliente pendiente"),
            ("fully_closed", "Operaciones totalmente cerradas"),
            ("with_balance", "Solo operaciones con saldo"),
        ],
        string="Vista financiera",
        default="all",
        required=True,
    )
    vendor_doc_type = fields.Selection(
        [
            ("all", "Todos"),
            ("bills_only", "Solo facturas"),
            ("po_only", "Solo OC sin factura"),
            ("bills_and_po", "Facturas + OC pendientes"),
        ],
        string="Documentos proveedor",
        default="all",
        required=True,
    )
    date_basis = fields.Selection(
        [
            ("operation", "Fecha de operación"),
            ("customer_invoice", "Fecha factura cliente"),
            ("vendor_bill", "Fecha factura proveedor"),
        ],
        string="Fecha basada en",
        default="operation",
        required=True,
    )
    export_format = fields.Selection(
        [("pdf", "PDF"), ("xlsx", "XLSX")],
        string="Formato",
        default="pdf",
        required=True,
    )

    @api.onchange("finance_view")
    def _onchange_finance_view(self):
        v, c = FINANCE_VIEW_MAP.get(self.finance_view or "all", ("all", "all"))
        self.vendor_payment_state = v
        self.customer_payment_state = c

    def action_generate(self):
        """Compat: genera según formato. Preferir Previsualizar / Descargar."""
        self.ensure_one()
        self._ensure_operation_types_selected()
        if self.export_format == "xlsx":
            return self.action_generate_xlsx()
        return self.action_print_pdf()

    def action_preview(self):
        """Visor HTML nativo Odoo 19 (iframe). No dispara downloadReport.

        Misma ir.actions.report / QWeb / wizard que el PDF; solo cambia
        report_type a qweb-html. El ActionService abre ReportAction en
        pantalla en lugar de POST /report/download.
        """
        self.ensure_one()
        self._ensure_operation_types_selected()
        action = self.env.ref(
            "justech_purchase_sale_margin_control.action_report_cost_vs_sale_pdf"
        ).report_action(self)
        if action.get("type") == "ir.actions.report":
            action = dict(action)
            action["report_type"] = "qweb-html"
            action["close_on_report_download"] = False
        return action

    def action_download_pdf(self):
        self.ensure_one()
        self._ensure_operation_types_selected()
        return self.action_print_pdf()

    def action_download_xlsx(self):
        self.ensure_one()
        self._ensure_operation_types_selected()
        return self.action_generate_xlsx()

    def _transaction_domain(self):
        self.ensure_one()
        self._ensure_operation_types_selected()
        companies = self.company_ids or self.company_id
        domain = [("company_id", "in", companies.ids)]
        basis = self.date_basis or "operation"
        if basis == "customer_invoice":
            domain += [
                "|",
                "&",
                ("customer_invoice_ids.invoice_date", ">=", self.date_from),
                ("customer_invoice_ids.invoice_date", "<=", self.date_to),
                "&",
                ("customer_invoice_ids", "=", False),
                "&",
                ("transaction_date", ">=", self.date_from),
                ("transaction_date", "<=", self.date_to),
            ]
        elif basis == "vendor_bill":
            domain += [
                "|",
                "&",
                ("vendor_bill_ids.invoice_date", ">=", self.date_from),
                ("vendor_bill_ids.invoice_date", "<=", self.date_to),
                "&",
                ("vendor_bill_ids", "=", False),
                "&",
                ("transaction_date", ">=", self.date_from),
                ("transaction_date", "<=", self.date_to),
            ]
        else:
            domain += [
                ("transaction_date", ">=", self.date_from),
                ("transaction_date", "<=", self.date_to),
            ]
        if self.only_uat:
            domain.append(("is_uat_fixture", "=", True))
        allowed = self._allowed_relation_classes()
        if not allowed:
            domain.append(("id", "=", 0))
        else:
            domain.append(("report_relation_class", "in", allowed))
            show_c, show_s, show_k, show_i = self._operation_type_flags()
            if show_i and not show_c:
                domain.append(("report_relation_class", "!=", "complete"))
        show_c, show_s, show_k, show_i = self._operation_type_flags()
        if not (show_i or show_s or show_k):
            domain.append(("state", "not in", ("draft", "rejected")))
        if self.customer_id:
            domain.append(
                "|",
                ("customer_id", "=", self.customer_id.id),
                ("customer_invoice_ids.partner_id", "=", self.customer_id.id),
            )
        if self.vendor_id:
            domain.append(
                "|",
                ("vendor_bill_ids.partner_id", "=", self.vendor_id.id),
                ("purchase_order_ids.partner_id", "=", self.vendor_id.id),
            )
        return domain

    @api.model
    def _decorate_cost_payment(self, crow):
        """Etiquetas Pago/Saldo/Abono. No modifica montos base ni payment_state Odoo.

        Regla de presentación (Fase 8):
        Si amount_residual == 0 → mostrar PAGADA aunque payment_state sea
        temporalmente `in_payment` (factura contablemente cubierta).
        """
        kind = crow.get("kind")
        if kind == "inventory":
            crow["payment_code"] = "consumed"
            crow["payment_badge"] = _("CONSUMIDO")
            crow["payment_color"] = "#0B5A5E"
            crow["residual_display"] = False
            crow["doc_status"] = _("Inventario")
            crow["is_credit_note"] = False
            if not crow.get("abono"):
                crow["abono"] = False
                crow["abono_note"] = ""
            return crow
        if kind == "inventory_purchase":
            crow["payment_code"] = False
            crow["payment_badge"] = crow.get("label") or _("INVENTARIO DISPONIBLE")
            crow["payment_color"] = "#2563EB"
            crow["residual_display"] = False
            crow["doc_status"] = _("Inventario")
            crow["is_credit_note"] = False
            return crow
        if kind in ("po", "manual") or (not crow.get("bill") and kind != "bill"):
            crow["payment_code"] = False
            crow["payment_badge"] = _("SIN FACTURA") if kind == "po" else (crow.get("label") or "—")
            crow["payment_color"] = "#4A5568"
            crow["residual_display"] = False
            crow["doc_status"] = _("Sin factura")
            crow["is_credit_note"] = False
            if not crow.get("abono"):
                crow["abono"] = False
                crow["abono_note"] = ""
            return crow

        residual = abs(crow.get("residual") or 0.0)
        # Presentación: residual 0 → siempre PAGADA (no alterar payment_state técnico)
        code = crow.get("raw_payment_state") or crow.get("payment_code") or ""
        if residual <= 0.005:
            code = "paid"
        elif not code:
            total = abs(
                crow.get("cxp_total")
                if crow.get("cxp_total") is not None
                else (crow.get("total") or 0.0)
            )
            if residual + 0.005 < total:
                code = "partial"
            else:
                code = "not_paid"

        move_type = crow.get("move_type") or ""
        is_refund = (crow.get("total") or 0.0) < -0.005 or move_type == "in_refund"
        crow["is_credit_note"] = bool(is_refund)
        if is_refund:
            crow["doc_status"] = _("Nota de crédito")
            crow["payment_badge"] = _("NC")
            crow["payment_color"] = "#7C3AED"
            crow["payment_code"] = code or "reversed"
            crow["residual_display"] = residual
            if not crow.get("abono"):
                crow["abono"] = abs(crow.get("cxp_total") or crow.get("total") or 0.0)
                crow["abono_note"] = _("Nota de crédito")
            return crow

        badge, color = VENDOR_PAY_BADGE.get(code, ("—", "#4A5568"))
        crow["payment_code"] = code
        crow["payment_badge"] = badge
        crow["payment_color"] = color
        crow["doc_status"] = _("Facturado")
        crow["residual_display"] = residual
        return crow

    @api.model
    def _decorate_sale_collection(self, sale):
        moves = sale.get("moves")
        if not moves:
            sale["collection_badge"] = _("Sin factura")
            sale["collection_color"] = "#4A5568"
            sale["collection_code"] = False
            sale["residual_display"] = False
            return sale
        residual = sum(abs(m.amount_residual) for m in moves)
        codes = [m.payment_state for m in moves if m.payment_state]
        priority = ["not_paid", "partial", "in_payment", "reversed", "paid"]
        code = "paid"
        for p in priority:
            if p in codes:
                code = p
                break
        # Presentación: residual 0 → Cobrada
        if residual <= 0.005:
            code = "paid"
        badge, color = CUSTOMER_PAY_BADGE.get(
            code, (_("Pendiente de cobro"), "#B91C1C")
        )
        sale["collection_code"] = code
        sale["collection_badge"] = badge
        sale["collection_color"] = color
        sale["residual_display"] = residual
        sale["raw_payment_state"] = code
        return sale

    @api.model
    def _bill_residual_amount(self, crow):
        """Outstanding residual from decorated cost row (account.move amount_residual)."""
        if crow.get("residual_display") is not False and crow.get("residual_display") is not None:
            return abs(crow.get("residual_display") or 0.0)
        return abs(crow.get("residual") or 0.0)

    def _cost_matches_vendor_payment(self, crow, vstate):
        """Match bill rows to wizard vendor payment filter.

        Pendientes de pago / Pagadas use real residual (same idea as
        open_vendor_bill_domain), not exact payment_state equality.
        partial / in_payment keep exact code match.
        """
        if vstate == "all":
            return True
        if crow.get("kind") in ("po", "inventory", "inventory_purchase", "manual") or not crow.get(
            "bill_id"
        ):
            return False
        residual = self._bill_residual_amount(crow)
        if vstate == "not_paid":
            # Any posted-related bill with outstanding residual
            return residual > 0.005
        if vstate == "paid":
            return residual <= 0.005
        code = crow.get("payment_code") or crow.get("raw_payment_state") or ""
        return code == vstate

    def _block_matches_vendor_payment(self, costs_all, vstate):
        """Operation-level vendor payment: pending if ANY open bill; paid if ALL paid."""
        if vstate == "all":
            return True, costs_all
        bill_costs = [
            c
            for c in costs_all
            if c.get("kind") == "bill" and c.get("bill_id")
        ]
        if not bill_costs:
            return False, []
        if vstate == "not_paid":
            matching = [c for c in bill_costs if self._cost_matches_vendor_payment(c, "not_paid")]
            return bool(matching), matching
        if vstate == "paid":
            if all(self._cost_matches_vendor_payment(c, "paid") for c in bill_costs):
                return True, bill_costs
            return False, []
        matching = [c for c in bill_costs if self._cost_matches_vendor_payment(c, vstate)]
        return bool(matching), matching

    def _sale_matches_customer_payment(self, sale):
        cstate = self.customer_payment_state or "all"
        if cstate == "all":
            return True
        if sale.get("is_estimated") or not sale.get("moves"):
            return False
        return (sale.get("collection_code") or sale.get("raw_payment_state")) == cstate

    def _block_has_open_balance(self, block):
        sale = block.get("sale") or {}
        if (sale.get("residual_display") or 0.0) > 0.005:
            return True
        for c in block.get("costs") or []:
            if c.get("kind") == "bill" and (c.get("residual_display") or 0.0) > 0.005:
                return True
        return False

    def _block_matches_doc_type(self, costs):
        doc = self.vendor_doc_type or "all"
        if doc in ("all", "bills_and_po"):
            return True
        has_bill = any(c.get("kind") == "bill" for c in costs)
        has_po = any(c.get("kind") == "po" for c in costs)
        if doc == "bills_only":
            return has_bill
        if doc == "po_only":
            return has_po and not has_bill
        return True

    def _block_matches_relation(self, block, costs_all=None, sale=None):
        """Relation-status filter — never changes operation class."""
        filt = getattr(self, "relation_filter", "all") or "all"
        if filt == "all":
            return True
        status = block.get("relation_status")
        if not status:
            if block.get("incomplete_cost_only"):
                has_sale, has_cost = False, True
            elif block.get("incomplete_sale_only"):
                has_sale, has_cost = True, False
            else:
                has_sale, has_cost = True, True
            txs = block.get("txs") or block.get("tx")
            if txs is None:
                txs = self.env["purchase.sale.margin.transaction"]
            status, badge = self._block_relation_status(txs, has_sale, has_cost)
            block["relation_status"] = status
            block["relation_badge"] = badge
        return status == filt

    def _apply_report_filters(self, blocks):
        """Incluye/excluye operaciones. Conserva márgenes originales del bloque."""
        self.ensure_one()
        out = []
        vstate = self.vendor_payment_state or "all"
        for block in blocks:
            sale = self._decorate_sale_collection(dict(block["sale"]))
            costs_all = [
                self._decorate_cost_payment(dict(c)) for c in (block.get("costs") or [])
            ]

            if not self._block_matches_doc_type(costs_all):
                continue
            if not self._sale_matches_customer_payment(sale):
                continue
            if not self._block_matches_relation(block, costs_all, sale):
                continue

            if vstate != "all":
                ok, matching = self._block_matches_vendor_payment(costs_all, vstate)
                if not ok:
                    continue
                # Show payment-matching bills (keep CxP-only rows when filter active)
                costs_display = matching
            else:
                costs_display = costs_all
                if (self.vendor_doc_type or "all") == "bills_only":
                    costs_display = [c for c in costs_all if c.get("kind") == "bill"]
                elif (self.vendor_doc_type or "all") == "po_only":
                    costs_display = [c for c in costs_all if c.get("kind") == "po"]

            # Tabla de operación: solo costos de margen (inventario / compra directa / etc.)
            # Facturas CxP-only (stock facturado pero costo vía SVL) no se listan aquí.
            cxp_costs = [
                c
                for c in costs_all
                if c.get("kind") == "bill" and c.get("include_in_cxp", True)
            ]
            if vstate == "all":
                costs_display = [
                    c for c in costs_display if c.get("include_in_margin", True)
                ]
            else:
                # Payment filter: keep matched bills even if include_in_margin=False
                costs_display = [
                    c
                    for c in costs_display
                    if c.get("include_in_margin", True)
                    or (c.get("kind") == "bill" and c.get("bill_id"))
                ]

            if self.vendor_id:
                vid = self.vendor_id.id
                costs_display = [
                    c for c in costs_display if c.get("partner_id") == vid
                ]
                if not costs_display and not any(
                    c.get("partner_id") == vid for c in cxp_costs
                ):
                    continue

            block = dict(block)
            block["sale"] = sale
            block["costs"] = costs_display
            block["cxp_costs"] = cxp_costs
            # Ensure relation badge always present for QWeb
            if not block.get("relation_status"):
                has_sale = not block.get("incomplete_cost_only")
                has_cost = not block.get("incomplete_sale_only")
                txs = block.get("txs") or block.get("tx")
                st, badge = self._block_relation_status(
                    txs if txs is not None else self.env["purchase.sale.margin.transaction"],
                    bool(has_sale and not block.get("incomplete_cost_only")),
                    bool(has_cost and not block.get("incomplete_sale_only")),
                )
                block["relation_status"] = st
                block["relation_badge"] = badge
            if block.get("incomplete_sale_only"):
                short, scolor = _("COSTO PENDIENTE"), "#CA8A04"
            elif block.get("incomplete_cost_only"):
                short, scolor = _("MARGEN PENDIENTE"), "#64748B"
            else:
                short, scolor = MARGIN_STATE_SHORT.get(
                    block.get("margin_band"), ("", "#4A5568")
                )
            block["margin_state_short"] = short
            block["margin_state_color"] = scolor
            block["payment_state"] = (
                sale.get("collection_badge") or sale.get("payment_state") or ""
            )

            if (self.finance_view or "all") == "with_balance":
                if not self._block_has_open_balance(
                    {"sale": sale, "costs": costs_all}
                ):
                    continue
            out.append(block)

        for i, b in enumerate(out, start=1):
            b["sale_number"] = i
        return out

    def _iter_sale_blocks(self):
        blocks = super()._iter_sale_blocks()
        return self._apply_report_filters(blocks)

    def _get_filtered_report_blocks(self):
        """Single filtered recordset for Preview / PDF / Excel."""
        return self._iter_sale_blocks()

    def _classification_counts(self, blocks=None):
        """Counts by functional class for assertions / diagnostics."""
        self.ensure_one()
        if blocks is None:
            blocks = self._get_filtered_report_blocks()
        counts = {
            "complete": 0,
            "cost_without_sale": 0,
            "sale_without_cost": 0,
            "incomplete_other": 0,
        }
        for b in blocks:
            if b.get("incomplete_cost_only"):
                counts["cost_without_sale"] += 1
            elif b.get("incomplete_sale_only"):
                counts["sale_without_cost"] += 1
            elif b.get("margin_pending_rate") and not b.get("incomplete_cost_only"):
                counts["incomplete_other"] += 1
            else:
                counts["complete"] += 1
        return counts

    @api.model
    def _format_report_date(self, value):
        """Fecha compacta DD/MM/YYYY para PDF (orden interno no cambia)."""
        if not value:
            return ""
        if isinstance(value, str):
            try:
                value = fields.Date.to_date(value)
            except (ValueError, TypeError):
                return value
        try:
            return value.strftime("%d/%m/%Y")
        except (AttributeError, ValueError, TypeError):
            return str(value)

    def _filter_header_lines(self):
        self.ensure_one()
        vendor_lbl = dict(self._fields["vendor_payment_state"].selection).get(
            self.vendor_payment_state, self.vendor_payment_state
        )
        cust_lbl = dict(self._fields["customer_payment_state"].selection).get(
            self.customer_payment_state, self.customer_payment_state
        )
        rel_lbl = ""
        if "relation_filter" in self._fields:
            rel_lbl = dict(self._fields["relation_filter"].selection).get(
                self.relation_filter, self.relation_filter
            )
        line1 = _("Período: %s – %s") % (
            self._format_report_date(self.date_from),
            self._format_report_date(self.date_to),
        )
        line2 = _(
            "Proveedor: %s · Estado proveedor: %s · Cliente: %s · Estado cliente: %s"
        ) % (
            self.vendor_id.display_name if self.vendor_id else _("Todos"),
            vendor_lbl,
            self.customer_id.display_name if self.customer_id else _("Todos"),
            cust_lbl,
        )
        if rel_lbl:
            line2 = _("%s · Relación: %s") % (line2, rel_lbl)
        line3 = _("Operaciones: %s") % self._report_scope_label()
        return line1, line2, line3

    def _cxp_summary_rows(self, blocks=None):
        self.ensure_one()
        if blocks is None:
            blocks = self._iter_sale_blocks()
        by_vendor = {}
        for b in blocks:
            cost_pool = b.get("cxp_costs") or b.get("costs") or []
            for c in cost_pool:
                if c.get("kind") != "bill" or not c.get("include_in_cxp", True):
                    continue
                if not c.get("bill_id") and not c.get("bill"):
                    continue
                name = c.get("vendor") or _("—")
                cur = (
                    c.get("display_currency")
                    or c.get("currency")
                    or b.get("currency")
                )
                cur_key = cur.name if hasattr(cur, "name") else (cur or "")
                bucket_key = (name, cur_key)
                bucket = by_vendor.setdefault(
                    bucket_key,
                    {
                        "vendor": name,
                        "count": 0,
                        "total": 0.0,
                        "paid": 0.0,
                        "residual": 0.0,
                        "currency": cur,
                        "currency_name": cur_key,
                    },
                )
                total = abs(
                    c.get("cxp_total")
                    if c.get("cxp_total") is not None
                    else (c.get("total") or 0.0)
                )
                residual = abs(
                    c.get("residual_display")
                    if c.get("residual_display") is not False
                    else (c.get("residual") or 0.0)
                )
                paid = max(total - residual, 0.0)
                bucket["count"] += 1
                bucket["total"] += total
                bucket["paid"] += paid
                bucket["residual"] += residual
        return sorted(by_vendor.values(), key=lambda r: (r.get("currency_name") or "", -r["residual"]))

    def _cxp_totals_by_currency(self, cxp_rows=None, blocks=None):
        """Totales CxP separados por moneda — nunca mezcla DOP+USD."""
        self.ensure_one()
        if cxp_rows is None:
            cxp_rows = self._cxp_summary_rows(blocks)
        by_cur = {}
        for row in cxp_rows:
            cur = row.get("currency")
            key = cur.name if hasattr(cur, "name") else (row.get("currency_name") or "")
            bucket = by_cur.setdefault(
                key,
                {
                    "currency": cur,
                    "currency_name": key,
                    "label": _("TOTAL CxP %s") % (key or "—"),
                    "count": 0,
                    "total": 0.0,
                    "paid": 0.0,
                    "residual": 0.0,
                },
            )
            bucket["count"] += row.get("count") or 0
            bucket["total"] += row.get("total") or 0.0
            bucket["paid"] += row.get("paid") or 0.0
            bucket["residual"] += row.get("residual") or 0.0
        # Prefer DOP then USD then alpha
        order = {"DOP": 0, "USD": 1}
        return sorted(
            by_cur.values(),
            key=lambda r: (order.get(r.get("currency_name") or "", 99), r.get("currency_name") or ""),
        )

    def _payment_stats(self, blocks=None):
        self.ensure_one()
        if blocks is None:
            blocks = self._iter_sale_blocks()
        stats = {
            "bill_count": 0,
            "bill_pending": 0,
            "bill_paid": 0,
            "bill_partial": 0,
            "bill_in_payment": 0,
            "vendor_residual": 0.0,
            "customer_residual": 0.0,
            "vendor_residual_by_currency": [],
        }
        residual_by_cur = {}
        for b in blocks:
            sale = b.get("sale") or {}
            if sale.get("residual_display"):
                stats["customer_residual"] += sale["residual_display"]
            cost_pool = b.get("cxp_costs") or b.get("costs") or []
            for c in cost_pool:
                if c.get("kind") != "bill" or not c.get("include_in_cxp", True):
                    continue
                stats["bill_count"] += 1
                code = c.get("payment_code")
                if code == "paid":
                    stats["bill_paid"] += 1
                elif code == "partial":
                    stats["bill_partial"] += 1
                elif code == "in_payment":
                    stats["bill_in_payment"] += 1
                else:
                    stats["bill_pending"] += 1
                if c.get("residual_display") is not False:
                    residual = abs(c.get("residual_display") or 0.0)
                    stats["vendor_residual"] += residual
                    cur = (
                        c.get("display_currency")
                        or c.get("currency")
                        or b.get("currency")
                    )
                    key = cur.name if hasattr(cur, "name") else (cur or "")
                    bucket = residual_by_cur.setdefault(
                        key,
                        {"currency": cur, "currency_name": key, "residual": 0.0},
                    )
                    bucket["residual"] += residual
        order = {"DOP": 0, "USD": 1}
        stats["vendor_residual_by_currency"] = sorted(
            residual_by_cur.values(),
            key=lambda r: (order.get(r.get("currency_name") or "", 99), r.get("currency_name") or ""),
        )
        return stats

    def _general_summary(self, transactions=None):
        summary = super()._general_summary(transactions=transactions)
        blocks = summary.get("sales") or summary.get("operations") or []
        stats = self._payment_stats(blocks)
        summary.update(stats)
        summary["cxp_rows"] = self._cxp_summary_rows(blocks)
        summary["cxp_totals"] = self._cxp_totals_by_currency(summary["cxp_rows"], blocks)
        flines = self._filter_header_lines()
        summary["filter_line1"] = flines[0]
        summary["filter_line2"] = flines[1]
        summary["filter_line3"] = flines[2] if len(flines) > 2 else ""
        summary["report_scope"] = self.report_scope or "all"
        summary["report_scope_label"] = self._report_scope_label()
        return summary

    def _prepare_qweb_grand(self):
        """Freeze report context for QWeb (read-only; no lazy key insertion).

        Always materializes ``sales`` / ``operations`` and foreach list keys as
        plain lists on a fresh ``dict`` so template evaluation cannot mutate
        structures mid-render (RuntimeError: dictionary changed size...).
        """
        self.ensure_one()
        raw = self._general_summary()
        grand = dict(raw)
        blocks = list(grand.get("sales") or grand.get("operations") or [])
        grand["sales"] = blocks
        grand["operations"] = blocks
        for key in (
            "by_currency_rows",
            "vendor_residual_by_currency",
            "cxp_rows",
            "cxp_totals",
            "top_clients",
            "top_ops",
            "neg_ops",
            "top_vendors",
        ):
            val = grand.get(key)
            grand[key] = list(val) if val else []
        cats = grand.get("category_totals")
        grand["category_totals"] = dict(cats) if isinstance(cats, dict) else {}
        for key, default in (
            ("positive", 0),
            ("low", 0),
            ("negative", 0),
            ("bill_pending", 0),
            ("bill_paid", 0),
            ("bill_partial", 0),
            ("bill_in_payment", 0),
            ("bill_count", 0),
            ("complete_ops", 0),
            ("sales_wo_cost", 0),
            ("costs_wo_sale", 0),
            ("vendor_residual", 0.0),
            ("customer_residual", 0.0),
            ("tx_count", 0),
            ("sale_count", 0),
        ):
            grand.setdefault(key, default)
        return grand
