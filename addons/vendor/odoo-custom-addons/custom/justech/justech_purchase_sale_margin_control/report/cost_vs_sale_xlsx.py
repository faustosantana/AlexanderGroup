# -*- coding: utf-8 -*-
"""19.0.8.0.0 — Detalle Costos vs Ventas: una fila por relación (factura proveedor).

Tabla continua con autofiltro, subtotal por transacción y total general.
La venta se repite visualmente por fila pero NO se suma N veces.
"""
import base64
import io

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools.misc import formatLang

try:
    from odoo.addons.justech_purchase_sale_margin_control.wizard.margin_labels import (
        label_payment_state,
    )
except ImportError:
    def label_payment_state(state):
        return state or ""


STATE_LABELS = {
    "draft": "Borrador",
    "detected": "Detectada",
    "pending_review": "Pendiente de revisión",
    "validated": "Validada",
    "approved": "Aprobada",
    "closed": "Cerrada",
    "rejected": "Rechazada",
    "reopened": "Reabierta",
}


def _move_ncf(move):
    if not move:
        return ""
    for fname in ("l10n_do_fiscal_number", "l10n_latam_document_number"):
        if fname in move._fields and move[fname]:
            return move[fname]
    return move.ref or ""


def _move_label(move):
    if not move:
        return ""
    name = (move.name or "").strip()
    if name and name != "/":
        return name
    return (move.ref or move.display_name or "").strip()


class PurchaseSaleCostVsSaleReport(models.TransientModel):
    _name = "purchase.sale.cost.vs.sale.report"
    _description = "Detalle Costos vs Ventas por transacción (XLSX/PDF)"

    company_id = fields.Many2one(
        "res.company", default=lambda self: self.env.company, required=True
    )
    company_ids = fields.Many2many(
        "res.company",
        string="Compañías",
        default=lambda self: self.env.companies,
    )
    date_from = fields.Date(
        required=True, default=lambda self: fields.Date.context_today(self).replace(month=1, day=1)
    )
    date_to = fields.Date(required=True, default=fields.Date.context_today)
    export_file = fields.Binary(string="Archivo", readonly=True)
    export_filename = fields.Char(string="Nombre de archivo", readonly=True)
    only_uat = fields.Boolean(string="Solo fixtures UAT")
    # Fuente de verdad única: tipos de operación a mostrar (multi-select)
    show_complete = fields.Boolean(
        string="Operaciones completas",
        default=True,
        help="Ventas con costo relacionado (completas o parciales con costo).",
    )
    show_sales_without_cost = fields.Boolean(
        string="Ventas sin costos",
        default=False,
        help="Solo operaciones de venta sin costo válido relacionado.",
    )
    show_costs_without_sale = fields.Boolean(
        string="Costos sin venta",
        default=False,
        help="Solo compras/costos sin venta relacionada.",
    )
    show_incomplete = fields.Boolean(
        string="Operaciones incompletas",
        default=False,
        help="Todo lo no-completo: parciales, ventas sin costo, costos sin venta.",
    )
    show_all_operations = fields.Boolean(
        string="Todas",
        default=False,
        help="UNION de completas + costos sin venta + ventas sin costo + incompletas.",
    )
    relation_filter = fields.Selection(
        [
            ("all", "Todas"),
            ("confirmed", "Confirmadas / relacionadas"),
            ("unconfirmed", "Sin confirmar"),
            ("unrelated", "Sin relacionar"),
        ],
        string="Estado de relación",
        default="all",
        required=True,
        help="Independiente de la clase de operación. Completas no requiere confirmación.",
    )
    # Compat legada (tests/API): se mapean a show_* en create/write
    include_sales_without_cost = fields.Boolean(
        string="Incluir ventas sin costos (compat)",
        default=False,
        help="Compatibilidad: preferir Operaciones a mostrar.",
    )
    include_costs_without_sale = fields.Boolean(
        string="Incluir costos sin venta (compat)",
        default=False,
    )
    include_incomplete = fields.Boolean(
        string="Incluir incompletas (compat)",
        default=False,
    )
    report_scope = fields.Selection(
        [
            ("all", "Todas las operaciones"),
            ("complete_only", "Solo operaciones completas"),
            ("sales_wo_cost", "Solo ventas sin costos"),
            ("costs_wo_sale", "Solo costos sin venta"),
            ("incomplete_only", "Solo operaciones incompletas"),
        ],
        string="Alcance (compat)",
        default="all",
        help="Compat 8.18: se traduce a Operaciones a mostrar.",
    )
    report_layout = fields.Selection(
        [
            ("compact", "Compacto gerencial"),
            ("detailed", "Detallado por operación"),
            ("summary", "Solo resumen"),
        ],
        string="Tipo de reporte",
        default="compact",
        required=True,
    )
    show_fiscal_detail = fields.Boolean(
        string="Mostrar detalle fiscal",
        default=False,
        help="NCF, ITBIS por costo, totales y saldos. Desactivado en el compacto gerencial.",
    )
    sort_by = fields.Selection(
        [
            ("date", "Fecha"),
            ("customer", "Cliente"),
            ("sale_amount", "Monto de venta"),
            ("margin", "Margen"),
        ],
        string="Ordenar por",
        default="date",
        required=True,
    )

    def _compute_legacy_include_flags(self):
        # reserved no-op (campos legados son editables; se sincronizan en create/write)
        return

    @api.model
    def _vals_apply_operation_types(self, vals):
        """Traduce report_scope / include_* → show_* (una sola fuente de verdad)."""
        vals = dict(vals)
        scope_explicit = "report_scope" in vals
        show_explicit = any(
            k in vals
            for k in (
                "show_complete",
                "show_sales_without_cost",
                "show_costs_without_sale",
                "show_incomplete",
            )
        )
        if scope_explicit and (not show_explicit or vals.get("report_scope") not in (False, None, "all")):
            scope = vals.get("report_scope") or "all"
            if scope == "complete_only":
                vals.update(
                    {
                        "show_complete": True,
                        "show_sales_without_cost": False,
                        "show_costs_without_sale": False,
                        "show_incomplete": False,
                    }
                )
            elif scope == "sales_wo_cost":
                vals.update(
                    {
                        "show_complete": False,
                        "show_sales_without_cost": True,
                        "show_costs_without_sale": False,
                        "show_incomplete": False,
                    }
                )
            elif scope == "costs_wo_sale":
                vals.update(
                    {
                        "show_complete": False,
                        "show_sales_without_cost": False,
                        "show_costs_without_sale": True,
                        "show_incomplete": False,
                    }
                )
            elif scope == "incomplete_only":
                vals.update(
                    {
                        "show_complete": False,
                        "show_sales_without_cost": False,
                        "show_costs_without_sale": False,
                        "show_incomplete": True,
                    }
                )
            elif scope == "all":
                vals.setdefault("show_complete", True)
                if "include_sales_without_cost" in vals:
                    vals["show_sales_without_cost"] = bool(vals["include_sales_without_cost"])
                if "include_costs_without_sale" in vals:
                    vals["show_costs_without_sale"] = bool(vals["include_costs_without_sale"])
                if "include_incomplete" in vals:
                    vals["show_incomplete"] = bool(vals["include_incomplete"])
        else:
            if "include_sales_without_cost" in vals and "show_sales_without_cost" not in vals:
                vals["show_sales_without_cost"] = bool(vals["include_sales_without_cost"])
            if "include_costs_without_sale" in vals and "show_costs_without_sale" not in vals:
                vals["show_costs_without_sale"] = bool(vals["include_costs_without_sale"])
            if "include_incomplete" in vals and "show_incomplete" not in vals:
                vals["show_incomplete"] = bool(vals["include_incomplete"])
        # espejo reverse para campos compat
        if "show_sales_without_cost" in vals:
            vals["include_sales_without_cost"] = bool(vals["show_sales_without_cost"])
        if "show_costs_without_sale" in vals:
            vals["include_costs_without_sale"] = bool(vals["show_costs_without_sale"])
        if "show_incomplete" in vals:
            vals["include_incomplete"] = bool(vals["show_incomplete"])
        return vals

    @api.model_create_multi
    def create(self, vals_list):
        vals_list = [self._vals_apply_operation_types(v) for v in vals_list]
        return super().create(vals_list)

    def write(self, vals):
        vals = self._vals_apply_operation_types(vals)
        return super().write(vals)

    @api.onchange("show_all_operations")
    def _onchange_show_all_operations(self):
        if self.show_all_operations:
            self.show_complete = True
            self.show_sales_without_cost = True
            self.show_costs_without_sale = True
            self.show_incomplete = True

    def _operation_type_flags(self):
        """Effective class checkboxes (TODAS expands to full UNION)."""
        self.ensure_one()
        if getattr(self, "show_all_operations", False):
            return True, True, True, True
        return (
            bool(self.show_complete),
            bool(self.show_sales_without_cost),
            bool(self.show_costs_without_sale),
            bool(self.show_incomplete),
        )

    def _report_scope_label(self):
        self.ensure_one()
        if getattr(self, "show_all_operations", False):
            return _("Todas las operaciones")
        parts = []
        if self.show_complete:
            parts.append(_("Completas"))
        if self.show_sales_without_cost:
            parts.append(_("Ventas sin costos"))
        if self.show_costs_without_sale:
            parts.append(_("Costos sin venta"))
        if self.show_incomplete:
            parts.append(_("Incompletas"))
        if not parts:
            return _("(sin selección)")
        if (
            self.show_complete
            and self.show_sales_without_cost
            and self.show_costs_without_sale
            and self.show_incomplete
        ):
            return _("Todas las operaciones")
        return " · ".join(parts)

    def _ensure_operation_types_selected(self):
        self.ensure_one()
        show_c, show_s, show_k, show_i = self._operation_type_flags()
        if not any([show_c, show_s, show_k, show_i]):
            raise UserError(
                _(
                    "Debe seleccionar al menos un tipo de operación a mostrar "
                    "(completas, ventas sin costos, costos sin venta, incompletas o Todas)."
                )
            )

    def action_select_all_operation_types(self):
        self.ensure_one()
        self.write(
            {
                "show_all_operations": True,
                "show_complete": True,
                "show_sales_without_cost": True,
                "show_costs_without_sale": True,
                "show_incomplete": True,
            }
        )
        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }

    def action_clear_operation_types(self):
        self.ensure_one()
        self.write(
            {
                "show_all_operations": False,
                "show_complete": False,
                "show_sales_without_cost": False,
                "show_costs_without_sale": False,
                "show_incomplete": False,
            }
        )
        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }

    def _effective_include_flags(self):
        """Compat: deriva flags desde la selección múltiple."""
        self.ensure_one()
        return {
            "sales_wo_cost": bool(self.show_sales_without_cost or self.show_incomplete),
            "costs_wo_sale": bool(self.show_costs_without_sale or self.show_incomplete),
            "incomplete": bool(self.show_incomplete),
        }

    def _allowed_relation_classes(self):
        """Strict class UNION from operation-type checkboxes only.

        Payment / document / partner / relation filters must never add classes.
        Checkboxes combine with OR (union), never AND.
        """
        self.ensure_one()
        show_c, show_s, show_k, show_i = self._operation_type_flags()
        allowed = []
        if show_c:
            # Completa estructural (venta+costo), incl. sin confirmar.
            # Domain amplio: _op_included exige both sides.
            allowed.extend(
                [
                    "complete",
                    "partial_with_cost",
                    "pending_relation",
                ]
            )
        if show_s:
            allowed.extend(["sale_without_cost", "pending_relation"])
        if show_k:
            allowed.append("incomplete_historical")
        if show_i:
            # Residual + umbrella cuando solo incompletas
            allowed.extend(
                [
                    "pending_relation",
                    "probable_duplicate",
                ]
            )
            if not (show_c or show_s or show_k):
                allowed.extend(
                    [
                        "sale_without_cost",
                        "incomplete_historical",
                        "partial_with_cost",
                    ]
                )
        return list(dict.fromkeys(allowed))

    def _transaction_domain(self):
        self.ensure_one()
        self._ensure_operation_types_selected()
        companies = self.company_ids or self.company_id
        domain = [
            ("company_id", "in", companies.ids),
            ("transaction_date", ">=", self.date_from),
            ("transaction_date", "<=", self.date_to),
        ]
        if self.only_uat:
            domain.append(("is_uat_fixture", "=", True))
        allowed = self._allowed_relation_classes()
        show_c, show_s, show_k, show_i = self._operation_type_flags()
        if not allowed:
            domain.append(("id", "=", 0))
        else:
            domain.append(("report_relation_class", "in", allowed))
            if show_i and not show_c:
                domain.append(("report_relation_class", "!=", "complete"))
        if not show_i and not show_s and not show_k:
            domain.append(("state", "not in", ("draft", "rejected")))
        return domain

    def _iter_transactions(self):
        return self.env["purchase.sale.margin.transaction"].search(
            self._transaction_domain(), order="transaction_date, id"
        )

    @api.model
    def _relation_rows(self, tx):
        """One row dict per vendor bill (or committed PO without bill)."""
        invoices = tx.customer_invoice_ids.sorted(
            lambda m: (m.invoice_date or fields.Date.today(), m.id)
        )
        inv = invoices[:1]
        sale_untaxed = inv.amount_untaxed if inv else (tx.sale_real_amount or tx.sale_estimated_amount or 0.0)
        sale_tax = inv.amount_tax if inv else 0.0
        sale_total = inv.amount_total if inv else sale_untaxed
        sale_curr = inv.currency_id if inv else tx.currency_id
        sale_date = inv.invoice_date if inv else tx.transaction_date
        sale_name = _move_label(inv) if inv else ", ".join(tx.sale_order_ids.mapped("name"))
        sale_ncf = _move_ncf(inv) if inv else ""
        customer = (
            (inv.partner_id.display_name if inv else False)
            or (tx.customer_id.display_name if tx.customer_id else "")
        )

        rows = []
        bills = tx.vendor_bill_ids.sorted(lambda m: (m.invoice_date or fields.Date.today(), m.id))
        for bill in bills:
            pos = bill.invoice_line_ids.mapped("purchase_line_id.order_id")
            cost = abs(bill.amount_untaxed)
            margin = sale_untaxed - cost  # per-row informational; subtotal uses unique sale
            rows.append(
                {
                    "company": tx.company_id.name,
                    "tx": tx.transaction_number or tx.name,
                    "state": STATE_LABELS.get(tx.state, tx.state),
                    "customer": customer,
                    "sale_inv": sale_name,
                    "sale_ncf": sale_ncf,
                    "sale_date": sale_date,
                    "sale_untaxed": sale_untaxed,
                    "sale_tax": sale_tax,
                    "sale_total": sale_total,
                    "sale_currency": sale_curr.name if sale_curr else "",
                    "vendor": bill.partner_id.display_name or "",
                    "po": ", ".join(pos.mapped("name")),
                    "bill": _move_label(bill),
                    "bill_ncf": _move_ncf(bill),
                    "bill_date": bill.invoice_date,
                    "bill_untaxed": bill.amount_untaxed,
                    "bill_tax": bill.amount_tax,
                    "bill_total": bill.amount_total,
                    "bill_currency": bill.currency_id.name if bill.currency_id else "",
                    "bill_residual": bill.amount_residual,
                    "payment_state": label_payment_state(bill.payment_state),
                    "allocated_cost": cost,
                    "margin_row": margin,
                    "margin_pct_row": (margin / sale_untaxed * 100.0) if sale_untaxed else 0.0,
                    "relation_state": STATE_LABELS.get(tx.state, tx.state),
                    "validated_by": tx.validated_by_id.name if "validated_by_id" in tx._fields and tx.validated_by_id else "",
                    "approved_by": tx.approved_by_id.name if "approved_by_id" in tx._fields and tx.approved_by_id else "",
                    "kind": "bill",
                }
            )
        if not bills and tx.purchase_order_ids:
            for po in tx.purchase_order_ids:
                cost = po.amount_untaxed
                margin = sale_untaxed - cost
                rows.append(
                    {
                        "company": tx.company_id.name,
                        "tx": tx.transaction_number or tx.name,
                        "state": STATE_LABELS.get(tx.state, tx.state),
                        "customer": customer,
                        "sale_inv": sale_name,
                        "sale_ncf": sale_ncf,
                        "sale_date": sale_date,
                        "sale_untaxed": sale_untaxed,
                        "sale_tax": sale_tax,
                        "sale_total": sale_total,
                        "sale_currency": sale_curr.name if sale_curr else "",
                        "vendor": po.partner_id.display_name or "",
                        "po": po.name,
                        "bill": "",
                        "bill_ncf": "",
                        "bill_date": False,
                        "bill_untaxed": po.amount_untaxed,
                        "bill_tax": po.amount_tax,
                        "bill_total": po.amount_total,
                        "bill_currency": po.currency_id.name if po.currency_id else "",
                        "bill_residual": 0.0,
                        "payment_state": _("Comprometido"),
                        "allocated_cost": cost,
                        "margin_row": margin,
                        "margin_pct_row": (margin / sale_untaxed * 100.0) if sale_untaxed else 0.0,
                        "relation_state": STATE_LABELS.get(tx.state, tx.state),
                        "validated_by": "",
                        "approved_by": "",
                        "kind": "po",
                    }
                )
        if not rows and self.env.context.get("include_empty_sale"):
            rows.append(
                {
                    "company": tx.company_id.name,
                    "tx": tx.transaction_number or tx.name,
                    "state": STATE_LABELS.get(tx.state, tx.state),
                    "customer": customer,
                    "sale_inv": sale_name,
                    "sale_ncf": sale_ncf,
                    "sale_date": sale_date,
                    "sale_untaxed": sale_untaxed,
                    "sale_tax": sale_tax,
                    "sale_total": sale_total,
                    "sale_currency": sale_curr.name if sale_curr else "",
                    "vendor": "",
                    "po": "",
                    "bill": "",
                    "bill_ncf": "",
                    "bill_date": False,
                    "bill_untaxed": 0.0,
                    "bill_tax": 0.0,
                    "bill_total": 0.0,
                    "bill_currency": "",
                    "bill_residual": 0.0,
                    "payment_state": "",
                    "allocated_cost": 0.0,
                    "margin_row": sale_untaxed,
                    "margin_pct_row": 100.0 if sale_untaxed else 0.0,
                    "relation_state": _("Venta sin costos"),
                    "validated_by": "",
                    "approved_by": "",
                    "kind": "sale_only",
                }
            )
        return rows, sale_untaxed, sale_tax, sale_total

    # Keep Sprint 6 PDF helper API
    @api.model
    def _paired_rows(self, tx):
        rows, sale_untaxed, sale_tax, sale_total = self._relation_rows(tx)
        left = []
        for r in rows:
            left.append(
                {
                    "partner": r["vendor"],
                    "name": r["bill"] or r["po"],
                    "ncf": r["bill_ncf"],
                    "untaxed": r["bill_untaxed"],
                    "tax": r["bill_tax"],
                    "total": r["bill_total"],
                    "po": r["po"],
                    "payment_state": r["payment_state"],
                }
            )
        inv = tx.customer_invoice_ids[:1]
        right = []
        if inv or tx.sale_order_ids:
            right.append(
                {
                    "partner": rows[0]["customer"] if rows else (tx.customer_id.display_name or ""),
                    "name": rows[0]["sale_inv"] if rows else "",
                    "ncf": rows[0]["sale_ncf"] if rows else "",
                    "untaxed": sale_untaxed,
                    "tax": sale_tax,
                    "total": sale_total,
                    "payment_state": "",
                    "move": inv,
                }
            )
        n = max(len(left), len(right), 1)
        pairs = []
        for i in range(n):
            l = left[i] if i < len(left) else False
            if right:
                r = right[0]
                visual = i > 0
            else:
                r = False
                visual = False
            pairs.append((l, r, visual))
        return pairs, left, right

    def _format_amount(self, amount, currency=None):
        currency = currency or self.company_id.currency_id
        return formatLang(self.env, amount or 0.0, currency_obj=currency)

    def _general_summary(self, transactions):
        """Totales por moneda (no mezcla USD+DOP)."""
        by_cur = {}
        pending_po = 0
        sales_wo_cost = 0
        pending_review = 0
        for tx in transactions:
            rows, sale_u, sale_t, sale_tot = self.with_context(
                include_empty_sale=self._effective_include_flags()["sales_wo_cost"]
            )._relation_rows(tx)
            if not rows and not self._effective_include_flags()["sales_wo_cost"]:
                continue
            inv = tx.customer_invoice_ids[:1]
            cur = (inv.currency_id or tx.currency_id or tx.company_id.currency_id).name
            bucket = by_cur.setdefault(
                cur,
                {
                    "tx_count": 0,
                    "sale_untaxed": 0.0,
                    "sale_tax": 0.0,
                    "sale_total": 0.0,
                    "cost_untaxed": 0.0,
                    "cost_tax": 0.0,
                    "cost_total": 0.0,
                    "margin": 0.0,
                },
            )
            cost_u = sum(r["bill_untaxed"] for r in rows)
            cost_t = sum(r["bill_tax"] for r in rows)
            cost_tot = sum(r["bill_total"] for r in rows)
            bucket["tx_count"] += 1
            bucket["sale_untaxed"] += sale_u
            bucket["sale_tax"] += sale_t
            bucket["sale_total"] += sale_tot
            bucket["cost_untaxed"] += cost_u
            bucket["cost_tax"] += cost_t
            bucket["cost_total"] += cost_tot
            bucket["margin"] += sale_u - cost_u
            if tx.purchase_order_ids and not tx.vendor_bill_ids:
                pending_po += 1
            if not tx.purchase_order_ids and not tx.vendor_bill_ids and tx.customer_invoice_ids:
                sales_wo_cost += 1
            if tx.state in ("pending_review", "detected", "draft"):
                pending_review += 1
        return {
            "by_currency": by_cur,
            "pending_po": pending_po,
            "sales_wo_cost": sales_wo_cost,
            "pending_review": pending_review,
            "tx_count": sum(b["tx_count"] for b in by_cur.values()),
        }

    def action_generate_xlsx(self):
        self.ensure_one()
        try:
            import xlsxwriter
        except ImportError as exc:
            raise UserError(_("La librería xlsxwriter no está disponible en el servidor.")) from exc

        transactions = self._iter_transactions()

        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {"in_memory": True})
        sheet = workbook.add_worksheet("Detalle")

        fmt_title = workbook.add_format({"bold": True, "font_size": 14})
        fmt_meta = workbook.add_format({"italic": True, "font_color": "#333333"})
        fmt_head = workbook.add_format(
            {"bold": True, "bg_color": "#1F4E79", "font_color": "white", "border": 1}
        )
        fmt_money = workbook.add_format({"num_format": "#,##0.00", "border": 1})
        fmt_text = workbook.add_format({"border": 1})
        fmt_date = workbook.add_format({"num_format": "yyyy-mm-dd", "border": 1})
        fmt_sub = workbook.add_format(
            {"bold": True, "bg_color": "#FFF2CC", "num_format": "#,##0.00", "border": 1}
        )
        fmt_sub_t = workbook.add_format({"bold": True, "bg_color": "#FFF2CC", "border": 1})
        fmt_tot = workbook.add_format(
            {"bold": True, "bg_color": "#DDEBF7", "num_format": "#,##0.00", "border": 1}
        )
        fmt_tot_t = workbook.add_format({"bold": True, "bg_color": "#DDEBF7", "border": 1})

        company = self.company_id or self.env.company
        sheet.write(0, 0, company.name or "Justech", fmt_title)
        sheet.write(1, 0, _("Detalle Costos vs Ventas — una fila por relación"), fmt_meta)
        sheet.write(
            2,
            0,
            _("Período: %s → %s | Operaciones: %s | Generado: %s | Usuario: %s")
            % (
                self.date_from,
                self.date_to,
                self._report_scope_label(),
                fields.Datetime.now(),
                self.env.user.name,
            ),
            fmt_meta,
        )
        sheet.write(
            3,
            0,
            _(
                "Leyenda: la factura de venta se repite por fila para filtros; "
                "en subtotales/total la venta se cuenta una sola vez por transacción."
            ),
            fmt_meta,
        )

        headers = [
            "Empresa",
            "Transacción",
            "Estado",
            "Cliente",
            "Factura cliente",
            "NCF cliente",
            "Fecha venta",
            "Subtotal venta",
            "ITBIS venta",
            "Total venta",
            "Moneda venta",
            "Proveedor",
            "OC",
            "Factura proveedor",
            "NCF proveedor",
            "Fecha compra",
            "Subtotal compra",
            "ITBIS compra",
            "Total compra",
            "Moneda compra",
            "Saldo proveedor",
            "Estado de pago",
            "Costo asignado",
            "Margen (fila)",
            "Margen % (fila)",
            "Estado de relación",
            "Validado por",
            "Aprobado por",
        ]
        header_row = 5
        for col, h in enumerate(headers):
            sheet.write(header_row, col, h, fmt_head)
        sheet.freeze_panes(header_row + 1, 0)
        sheet.autofilter(header_row, 0, header_row, len(headers) - 1)

        row = header_row + 1
        grand_sale = 0.0
        grand_cost = 0.0
        data_rows = 0
        ctx = self.with_context(
            include_empty_sale=self._effective_include_flags()["sales_wo_cost"]
        )

        for tx in transactions:
            rel_rows, sale_u, sale_t, sale_tot = ctx._relation_rows(tx)
            if not rel_rows:
                continue
            cost_sum = sum(r["allocated_cost"] for r in rel_rows)
            for r in rel_rows:
                sheet.write(row, 0, r["company"], fmt_text)
                sheet.write(row, 1, r["tx"], fmt_text)
                sheet.write(row, 2, r["state"], fmt_text)
                sheet.write(row, 3, r["customer"], fmt_text)
                sheet.write(row, 4, r["sale_inv"], fmt_text)
                sheet.write(row, 5, r["sale_ncf"], fmt_text)
                if r["sale_date"]:
                    sheet.write(row, 6, str(r["sale_date"]), fmt_text)
                else:
                    sheet.write(row, 6, "", fmt_text)
                sheet.write(row, 7, r["sale_untaxed"], fmt_money)
                sheet.write(row, 8, r["sale_tax"], fmt_money)
                sheet.write(row, 9, r["sale_total"], fmt_money)
                sheet.write(row, 10, r["sale_currency"], fmt_text)
                sheet.write(row, 11, r["vendor"], fmt_text)
                sheet.write(row, 12, r["po"], fmt_text)
                sheet.write(row, 13, r["bill"], fmt_text)
                sheet.write(row, 14, r["bill_ncf"], fmt_text)
                if r["bill_date"]:
                    sheet.write(row, 15, str(r["bill_date"]), fmt_text)
                else:
                    sheet.write(row, 15, "", fmt_text)
                sheet.write(row, 16, r["bill_untaxed"], fmt_money)
                sheet.write(row, 17, r["bill_tax"], fmt_money)
                sheet.write(row, 18, r["bill_total"], fmt_money)
                sheet.write(row, 19, r["bill_currency"], fmt_text)
                sheet.write(row, 20, r["bill_residual"], fmt_money)
                sheet.write(row, 21, r["payment_state"], fmt_text)
                sheet.write(row, 22, r["allocated_cost"], fmt_money)
                sheet.write(row, 23, r["margin_row"], fmt_money)
                sheet.write(row, 24, r["margin_pct_row"], fmt_money)
                sheet.write(row, 25, r["relation_state"], fmt_text)
                sheet.write(row, 26, r["validated_by"], fmt_text)
                sheet.write(row, 27, r["approved_by"], fmt_text)
                row += 1
                data_rows += 1

            # Subtotal: sale once, cost sum, consolidated margin
            margin_tx = sale_u - cost_sum
            sheet.write(row, 0, "", fmt_sub_t)
            sheet.write(row, 1, _("SUBTOTAL %s") % (tx.transaction_number or tx.name), fmt_sub_t)
            for c in range(2, 7):
                sheet.write(row, c, "", fmt_sub_t)
            sheet.write(row, 7, sale_u, fmt_sub)
            sheet.write(row, 8, sale_t, fmt_sub)
            sheet.write(row, 9, sale_tot, fmt_sub)
            for c in range(10, 22):
                sheet.write(row, c, "", fmt_sub_t)
            sheet.write(row, 22, cost_sum, fmt_sub)
            sheet.write(row, 23, margin_tx, fmt_sub)
            sheet.write(
                row,
                24,
                (margin_tx / sale_u * 100.0) if sale_u else 0.0,
                fmt_sub,
            )
            sheet.write(row, 25, STATE_LABELS.get(tx.state, tx.state), fmt_sub_t)
            sheet.write(row, 26, "", fmt_sub_t)
            sheet.write(row, 27, "", fmt_sub_t)
            row += 1
            grand_sale += sale_u
            grand_cost += cost_sum

        # Grand total
        grand_margin = grand_sale - grand_cost
        sheet.write(row, 1, _("TOTAL GENERAL"), fmt_tot_t)
        sheet.write(row, 7, grand_sale, fmt_tot)
        sheet.write(row, 22, grand_cost, fmt_tot)
        sheet.write(row, 23, grand_margin, fmt_tot)
        sheet.write(
            row,
            24,
            (grand_margin / grand_sale * 100.0) if grand_sale else 0.0,
            fmt_tot,
        )
        row += 1

        for col, width in enumerate(
            [18, 16, 14, 22, 18, 14, 12, 12, 10, 12, 10, 22, 12, 18, 14, 12, 12, 10, 12, 10, 12, 12, 12, 12, 10, 14, 12, 12]
        ):
            sheet.set_column(col, col, width)


        # Hoja Resumen
        summary = self._general_summary(transactions)
        sheet2 = workbook.add_worksheet("Resumen")
        sheet2.write(0, 0, _("RESUMEN GENERAL"), fmt_title)
        sheet2.write(1, 0, _("Período: %s → %s") % (self.date_from, self.date_to), fmt_meta)
        companies = self.company_ids or self.company_id
        sheet2.write(2, 0, _("Compañías incluidas: %s") % ", ".join(companies.mapped("name")), fmt_meta)
        sheet2.write(4, 0, _("Indicador"), fmt_head)
        sheet2.write(4, 1, _("Moneda"), fmt_head)
        sheet2.write(4, 2, _("Importe"), fmt_head)
        r2 = 5
        sheet2.write(r2, 0, _("Cantidad de transacciones"), fmt_text)
        sheet2.write(r2, 2, summary["tx_count"], fmt_text)
        r2 += 1
        for cur, bucket in summary["by_currency"].items():
            for label, key in [
                (_("Total de ventas sin ITBIS"), "sale_untaxed"),
                (_("ITBIS total de ventas"), "sale_tax"),
                (_("Total facturado a clientes"), "sale_total"),
                (_("Total de costos sin ITBIS"), "cost_untaxed"),
                (_("ITBIS total de costos"), "cost_tax"),
                (_("Total facturado por proveedores"), "cost_total"),
                (_("Margen estimado / confirmado"), "margin"),
            ]:
                sheet2.write(r2, 0, label, fmt_text)
                sheet2.write(r2, 1, cur, fmt_text)
                sheet2.write(r2, 2, bucket[key], fmt_money)
                r2 += 1
            pct = (bucket["margin"] / bucket["sale_untaxed"] * 100.0) if bucket["sale_untaxed"] else 0.0
            sheet2.write(r2, 0, _("Margen total %%"), fmt_text)
            sheet2.write(r2, 1, cur, fmt_text)
            sheet2.write(r2, 2, pct, fmt_money)
            r2 += 2
        sheet2.write(r2, 0, _("Compras pendientes de factura"), fmt_text)
        sheet2.write(r2, 2, summary["pending_po"], fmt_text)
        r2 += 1
        sheet2.write(r2, 0, _("Ventas sin costo"), fmt_text)
        sheet2.write(r2, 2, summary["sales_wo_cost"], fmt_text)
        r2 += 1
        sheet2.write(r2, 0, _("Operaciones pendientes de revisión"), fmt_text)
        sheet2.write(r2, 2, summary["pending_review"], fmt_text)
        sheet2.set_column(0, 0, 42)
        sheet2.set_column(1, 1, 12)
        sheet2.set_column(2, 2, 16)

        # Hoja Pendientes (opcional)
        sheet3 = workbook.add_worksheet("Pendientes")
        sheet3.write(0, 0, _("Pendientes"), fmt_title)
        sheet3.write(2, 0, _("Tipo"), fmt_head)
        sheet3.write(2, 1, _("Transacción"), fmt_head)
        sheet3.write(2, 2, _("Detalle"), fmt_head)
        r3 = 3
        for tx in transactions:
            if not tx.purchase_order_ids and not tx.vendor_bill_ids:
                sheet3.write(r3, 0, _("Venta sin costos"), fmt_text)
                sheet3.write(r3, 1, tx.transaction_number or tx.name or "", fmt_text)
                sheet3.write(r3, 2, tx.customer_id.display_name or "", fmt_text)
                r3 += 1
            elif tx.purchase_order_ids and not tx.customer_invoice_ids and not tx.sale_order_ids:
                sheet3.write(r3, 0, _("Compra sin venta"), fmt_text)
                sheet3.write(r3, 1, tx.transaction_number or tx.name or "", fmt_text)
                sheet3.write(r3, 2, ", ".join(tx.purchase_order_ids.mapped("name")), fmt_text)
                r3 += 1
            elif tx.state in ("pending_review", "detected"):
                sheet3.write(r3, 0, _("Pendiente de revisión"), fmt_text)
                sheet3.write(r3, 1, tx.transaction_number or tx.name or "", fmt_text)
                sheet3.write(r3, 2, STATE_LABELS.get(tx.state, tx.state), fmt_text)
                r3 += 1
        sheet3.set_column(0, 0, 24)
        sheet3.set_column(1, 1, 18)
        sheet3.set_column(2, 2, 40)


        workbook.close()
        content = output.getvalue()
        filename = "detalle_costos_vs_ventas_%s_%s.xlsx" % (self.date_from, self.date_to)
        self.write(
            {
                "export_file": base64.b64encode(content),
                "export_filename": filename,
            }
        )
        return {
            "type": "ir.actions.act_url",
            "url": (
                "/web/content/?model=purchase.sale.cost.vs.sale.report&id=%s"
                "&field=export_file&filename_field=export_filename&download=true"
                % self.id
            ),
            "target": "self",
        }

    def action_print_pdf(self):
        self.ensure_one()
        return self.env.ref(
            "justech_purchase_sale_margin_control.action_report_cost_vs_sale_pdf"
        ).report_action(self)

    def action_generate_pdf(self):
        return self.action_print_pdf()
