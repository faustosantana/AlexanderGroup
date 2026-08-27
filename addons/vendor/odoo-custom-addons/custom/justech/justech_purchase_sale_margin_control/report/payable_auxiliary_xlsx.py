# -*- coding: utf-8 -*-
"""19.0.8.29.14 — CxP operativo: Preview / PDF / Excel (open vendor bills + relations).

READ-ONLY reporting. Source of truth: open_vendor_bill_domain (account.move).
Does not modify MTX, SO/PO, bills, payments, or Trace assignments.

Relation priority:
  L1 AML.purchase_line_id → PO
  L2 POL.sale_line_id → Sale
  L3 PO.origin == SO.name (ORIGIN_EXACT)
  L4 MTX manual (vendor_bill_ids + sale_order_ids)
  L5 Trace justech.purchase.sale.qty.assignment (active, same company)
  L6 unresolved
"""
import base64
import io
import logging
from collections import defaultdict

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools.misc import formatLang, format_date

from ..models.payable_cxp_source import open_vendor_bill_domain

_logger = logging.getLogger(__name__)

PAYMENT_STATE_LABELS = {
    "not_paid": "PENDIENTE",
    "in_payment": "EN PAGO",
    "partial": "PARCIAL",
    "paid": "PAGADA",
    "reversed": "REVERTIDA",
}

CUSTOMER_STATE_LABELS = {
    "collected": "COBRADA",
    "partial": "PARCIAL",
    "pending": "PENDIENTE",
    "no_invoice": "SIN FACTURA",
    "no_sale": "SIN VENTA",
}


def _move_ncf(move):
    if not move:
        return ""
    for fname in ("l10n_do_fiscal_number", "l10n_latam_document_number"):
        if fname in move._fields and move[fname]:
            return move[fname]
    return move.ref or ""


class PurchaseSalePayableAuxiliaryReport(models.TransientModel):
    """Operational CxP report: one row per open posted vendor bill."""

    _name = "purchase.sale.payable.auxiliary.report"
    _description = "Cuentas por Pagar — reporte operativo"

    company_id = fields.Many2one(
        "res.company",
        string="Compañía principal",
        default=lambda self: self.env.company,
    )
    company_ids = fields.Many2many(
        "res.company",
        string="Compañías",
        default=lambda self: self.env.companies,
    )
    date_from = fields.Date(
        required=True,
        string="Desde",
        default=lambda self: fields.Date.context_today(self).replace(month=1, day=1),
    )
    date_to = fields.Date(
        required=True,
        string="Hasta",
        default=fields.Date.context_today,
    )
    vendor_id = fields.Many2one("res.partner", string="Proveedor")
    situation_filter = fields.Selection(
        [
            ("all", "Todas"),
            ("customer_collected", "Cliente cobrado"),
            ("customer_pending", "Cliente pendiente"),
            ("no_sale", "Sin venta relacionada"),
        ],
        string="Situación",
        default="all",
        required=True,
    )
    export_file = fields.Binary(string="Archivo", readonly=True)
    export_filename = fields.Char(string="Nombre de archivo", readonly=True)

    def _scope_company_ids(self):
        self.ensure_one()
        allowed = self.env.companies
        selected = self.company_ids or self.company_id or allowed
        return (selected & allowed).ids

    def _cxp_bills(self):
        self.ensure_one()
        company_ids = self._scope_company_ids()
        if not company_ids:
            return self.env["account.move"]
        domain = open_vendor_bill_domain(company_ids=company_ids)
        domain += [
            ("invoice_date", ">=", self.date_from),
            ("invoice_date", "<=", self.date_to),
        ]
        if self.vendor_id:
            domain.append(("partner_id", "child_of", self.vendor_id.commercial_partner_id.id))
        return self.env["account.move"].search(domain, order="invoice_date desc, id desc")

    def _batch_relations(self, bills):
        """Prefetch Bill→PO→SO→Customer invoice without per-bill searches."""
        Move = self.env["account.move"]
        POL = self.env["purchase.order.line"]
        PO = self.env["purchase.order"]
        SO = self.env["sale.order"]
        MTX = self.env["purchase.sale.margin.transaction"]

        bills = bills.with_prefetch()
        # LEVEL 1: AML → purchase_line_id
        pols = POL.browse()
        for bill in bills:
            for line in bill.invoice_line_ids:
                if line.purchase_line_id:
                    pols |= line.purchase_line_id
        pos = pols.mapped("order_id")

        # Strong SO via sale_line_id
        strong_sol = pols.filtered("sale_line_id").mapped("sale_line_id")
        sos = strong_sol.mapped("order_id")

        # ORIGIN_EXACT batch (same company, exact name)
        origin_names = {
            (po.company_id.id, (po.origin or "").strip())
            for po in pos
            if (po.origin or "").strip()
        }
        origin_sos = SO.browse()
        if origin_names:
            # one search per company for names
            by_co = defaultdict(set)
            for co_id, name in origin_names:
                if name and "http://" not in name and "https://" not in name:
                    by_co[co_id].add(name)
            for co_id, names in by_co.items():
                found = SO.search(
                    [("company_id", "=", co_id), ("name", "in", list(names))]
                )
                # keep only exact unique matches (ambiguity → skip)
                by_name = defaultdict(list)
                for so in found:
                    by_name[so.name].append(so)
                for name, group in by_name.items():
                    if len(group) == 1:
                        origin_sos |= group[0]

        sos |= origin_sos

        # MTX enrichment (optional, read-only) — LEVEL 4
        mtx_by_bill = {}
        if bills and "vendor_bill_ids" in MTX._fields:
            mtxes = MTX.search([("vendor_bill_ids", "in", bills.ids)])
            for mtx in mtxes:
                for bill in mtx.vendor_bill_ids:
                    if bill in bills:
                        mtx_by_bill.setdefault(bill.id, self.env["purchase.sale.margin.transaction"])
                        mtx_by_bill[bill.id] |= mtx
                        sos |= mtx.sale_order_ids
                        pos |= mtx.purchase_order_ids

        # LEVEL 5 — Trace qty.assignment (Bill line → Sale line), read-only
        bill_trace_sos = defaultdict(lambda: SO.browse())
        if (
            bills
            and "justech.purchase.sale.qty.assignment" in self.env
        ):
            Assign = self.env["justech.purchase.sale.qty.assignment"]
            if "vendor_bill_id" in Assign._fields:
                assigns = Assign.search(
                    [
                        ("vendor_bill_id", "in", bills.ids),
                        ("state", "=", "active"),
                    ]
                )
                for asg in assigns:
                    bill = asg.vendor_bill_id
                    so = asg.sale_order_id
                    if not bill or not so or bill not in bills:
                        continue
                    # same company: bill == sale == assignment
                    if (
                        asg.company_id != bill.company_id
                        or so.company_id != bill.company_id
                    ):
                        continue
                    bill_trace_sos[bill.id] |= so
                    sos |= so

        # Customer invoices from SO
        cust_invs = Move.browse()
        for so in sos:
            cust_invs |= so.invoice_ids.filtered(
                lambda m: m.move_type in ("out_invoice", "out_refund") and m.state == "posted"
            )

        # Map bill → POs
        bill_pos = defaultdict(lambda: PO.browse())
        for bill in bills:
            for line in bill.invoice_line_ids:
                if line.purchase_line_id:
                    bill_pos[bill.id] |= line.purchase_line_id.order_id
            for mtx in mtx_by_bill.get(bill.id, MTX.browse()):
                bill_pos[bill.id] |= mtx.purchase_order_ids

        # Map PO → SOs (strong + origin)
        po_sos = defaultdict(lambda: SO.browse())
        for pol in pols:
            if pol.sale_line_id:
                po_sos[pol.order_id.id] |= pol.sale_line_id.order_id
        origin_so_by_key = {(so.company_id.id, so.name): so for so in origin_sos}
        for po in pos:
            origin = (po.origin or "").strip()
            key = (po.company_id.id, origin)
            if key in origin_so_by_key:
                # only if not ORIGIN_MULTIPLE contamination
                if "http://" not in origin and "https://" not in origin and ";" not in origin and "," not in origin:
                    po_sos[po.id] |= origin_so_by_key[key]
        for bill_id, mtxes in mtx_by_bill.items():
            for mtx in mtxes:
                for po in mtx.purchase_order_ids:
                    po_sos[po.id] |= mtx.sale_order_ids

        so_cust = defaultdict(lambda: Move.browse())
        for inv in cust_invs:
            for so in inv.line_ids.mapped("sale_line_ids.order_id") if "sale_line_ids" in inv.line_ids._fields else SO.browse():
                so_cust[so.id] |= inv
        # fallback via invoice_origin / invoice_ids
        for so in sos:
            so_cust[so.id] |= so.invoice_ids.filtered(
                lambda m: m.move_type in ("out_invoice", "out_refund") and m.state == "posted"
            )

        return bill_pos, po_sos, so_cust, mtx_by_bill, bill_trace_sos

    def _customer_collection(self, invoices):
        if not invoices:
            return {
                "state": "no_invoice",
                "label": CUSTOMER_STATE_LABELS["no_invoice"],
                "total": 0.0,
                "paid": 0.0,
                "residual": 0.0,
                "names": "",
            }
        total = sum(abs(i.amount_total_signed) for i in invoices)
        residual = sum(abs(i.amount_residual_signed) for i in invoices)
        paid = max(total - residual, 0.0)
        if residual <= 0.005:
            state = "collected"
        elif paid > 0.005:
            state = "partial"
        else:
            state = "pending"
        return {
            "state": state,
            "label": CUSTOMER_STATE_LABELS[state],
            "total": total,
            "paid": paid,
            "residual": residual,
            "names": ", ".join(invoices.mapped("name")),
        }

    def _situation(self, has_po, has_so, cust_state):
        if not has_so and not has_po:
            return "SIN OC RELACIONADA"
        if not has_so:
            return "SIN VENTA RELACIONADA"
        # Sale related (PO optional — e.g. Trace assignment / MTX)
        if cust_state == "no_invoice":
            return "VENTA RELACIONADA · SIN FACTURA CLIENTE"
        if cust_state == "collected":
            return "LISTO PARA REVISIÓN DE PAGO"
        if cust_state == "partial":
            return "CLIENTE PARCIALMENTE COBRADO"
        return "CLIENTE PENDIENTE DE COBRO"

    def _relation_state(self, has_po, has_so, strong_or_origin, trace_confirmed=False):
        if not has_so:
            return "SIN RELACIONAR"
        # Explicit Trace Bill→Sale (no PO required)
        if trace_confirmed and not has_po:
            return "CONFIRMADA"
        if not has_po:
            return "SIN RELACIONAR"
        if strong_or_origin or trace_confirmed:
            return "CONFIRMADA"
        return "SIN CONFIRMAR"

    def _relation_source(self, has_aml_po, has_origin, has_mtx_sale, has_trace, has_so):
        if not has_so:
            return "SIN_RELACION"
        if has_aml_po:
            return "PO"
        if has_origin:
            return "ORIGIN"
        if has_mtx_sale:
            return "MTX"
        if has_trace:
            return "TRACE"
        return "SIN_RELACION"

    def _build_rows(self):
        self.ensure_one()
        bills = self._cxp_bills()
        bill_pos, po_sos, so_cust, mtx_by_bill, bill_trace_sos = self._batch_relations(bills)
        rows = []
        for bill in bills:
            pos = bill_pos.get(bill.id, self.env["purchase.order"])
            has_aml_po = any(l.purchase_line_id for l in bill.invoice_line_ids)
            primary_sos = self.env["sale.order"]
            strong = False
            has_origin = False
            for po in pos:
                primary_sos |= po_sos.get(po.id, self.env["sale.order"])
                # strong if any POL has sale_line_id
                if any(l.sale_line_id for l in po.order_line):
                    strong = True
                origin = (po.origin or "").strip()
                if origin and any(
                    so.name == origin and so.company_id == po.company_id for so in primary_sos
                ):
                    strong = True
                    has_origin = True
            has_mtx_sale = False
            for mtx in mtx_by_bill.get(bill.id, self.env["purchase.sale.margin.transaction"]):
                if mtx.sale_order_ids:
                    has_mtx_sale = True
                primary_sos |= mtx.sale_order_ids
                if mtx.state in ("validated", "approved", "closed"):
                    strong = True

            # LEVEL 5 — Trace: only if L1–4 did not already resolve a Sale,
            # or Trace sales are a subset of primary (no conflict). Else keep primary.
            trace_sos = bill_trace_sos.get(bill.id, self.env["sale.order"])
            # company safety already applied in batch; re-check
            trace_sos = trace_sos.filtered(lambda s: s.company_id == bill.company_id)
            trace_confirmed = False
            sos = primary_sos
            if trace_sos:
                if not primary_sos:
                    sos = trace_sos
                    trace_confirmed = True
                else:
                    extra = trace_sos - primary_sos
                    if extra:
                        _logger.warning(
                            "TRACE_CONFLICT bill=%s company=%s primary_sos=%s trace_extra=%s — keeping L1-4",
                            bill.name or bill.id,
                            bill.company_id.display_name,
                            primary_sos.mapped("name"),
                            extra.mapped("name"),
                        )
                        # keep primary; do not merge conflicting Trace sales
                    else:
                        # Trace agrees with stronger path — note Trace as supporting
                        trace_confirmed = False

            cust_invs = self.env["account.move"]
            for so in sos:
                cust_invs |= so_cust.get(so.id, self.env["account.move"])
            cust = self._customer_collection(cust_invs)
            if not sos:
                cust = {
                    "state": "no_sale",
                    "label": CUSTOMER_STATE_LABELS["no_sale"],
                    "total": 0.0,
                    "paid": 0.0,
                    "residual": 0.0,
                    "names": "",
                }

            situation = self._situation(bool(pos), bool(sos), cust["state"])
            # situation filter
            sf = self.situation_filter
            if sf == "customer_collected" and cust["state"] != "collected":
                continue
            if sf == "customer_pending" and cust["state"] not in ("pending", "partial", "no_invoice"):
                continue
            if sf == "no_sale" and sos:
                continue

            paid = abs(bill.amount_total) - abs(bill.amount_residual)
            if paid < 0:
                paid = 0.0
            pay_label = PAYMENT_STATE_LABELS.get(
                bill.payment_state,
                "PARCIAL" if bill.payment_state == "partial" else "PENDIENTE",
            )
            if bill.payment_state == "not_paid":
                pay_label = "PENDIENTE"
            elif bill.payment_state == "partial":
                pay_label = "PARCIAL"

            sale_amt = sum(sos.mapped("amount_untaxed")) if sos else None
            cost_amt = abs(bill.amount_untaxed) if bill.amount_untaxed else abs(bill.amount_total)
            margin = None
            margin_pct = None
            if sale_amt is not None and sale_amt > 0:
                margin = sale_amt - cost_amt
                margin_pct = (margin / sale_amt * 100.0) if sale_amt else None

            if not sos:
                relation_source = "SIN_RELACION"
            elif trace_confirmed:
                relation_source = "TRACE"
            else:
                relation_source = self._relation_source(
                    has_aml_po=has_aml_po,
                    has_origin=has_origin,
                    has_mtx_sale=has_mtx_sale,
                    has_trace=False,
                    has_so=True,
                )

            rows.append(
                {
                    "bill_id": bill.id,
                    "vendor": bill.partner_id.display_name or "",
                    "bill_name": bill.name or "",
                    "ncf": _move_ncf(bill),
                    "invoice_date": bill.invoice_date,
                    "invoice_date_due": bill.invoice_date_due,
                    "currency": bill.currency_id.name or "",
                    "currency_id": bill.currency_id.id,
                    "amount_total": abs(bill.amount_total),
                    "amount_paid": paid,
                    "amount_residual": abs(bill.amount_residual),
                    "payment_state": pay_label,
                    "po_names": ", ".join(pos.mapped("name")) or "—",
                    "so_names": ", ".join(sos.mapped("name")) or "—",
                    "customer": ", ".join(sos.mapped("partner_id.display_name")) or "—",
                    "customer_invoice": cust["names"] or "—",
                    "customer_collection": cust["label"],
                    "customer_total": cust["total"],
                    "customer_paid": cust["paid"],
                    "customer_residual": cust["residual"],
                    "sale_amount": sale_amt,
                    "cost_amount": cost_amt,
                    "margin": margin,
                    "margin_pct": margin_pct,
                    "relation_state": self._relation_state(
                        bool(pos), bool(sos), strong, trace_confirmed=trace_confirmed
                    ),
                    "relation_source": relation_source,
                    "situation": situation,
                    "company": bill.company_id.display_name or "",
                    "has_sale": bool(sos),
                    "cust_state": cust["state"],
                }
            )
        return rows

    def _build_summary(self, rows):
        by_currency = defaultdict(lambda: {"residual": 0.0, "count": 0})
        related = 0
        no_sale = 0
        collected = 0
        pending_cust = 0
        for r in rows:
            by_currency[r["currency"]]["residual"] += r["amount_residual"]
            by_currency[r["currency"]]["count"] += 1
            if r["has_sale"]:
                related += 1
            else:
                no_sale += 1
            if r["cust_state"] == "collected":
                collected += 1
            elif r["cust_state"] in ("pending", "partial", "no_invoice"):
                pending_cust += 1
        return {
            "bill_count": len(rows),
            "related": related,
            "no_sale": no_sale,
            "collected": collected,
            "pending_cust": pending_cust,
            "by_currency": [
                {"currency": cur, "residual": vals["residual"], "count": vals["count"]}
                for cur, vals in sorted(by_currency.items())
            ],
        }

    def _report_context(self):
        self.ensure_one()
        rows = self._build_rows()
        summary = self._build_summary(rows)
        return {
            "wizard": self,
            "rows": rows,
            "summary": summary,
            "company_names": ", ".join(
                self.env["res.company"].browse(self._scope_company_ids()).mapped("name")
            ),
            "generated_at": fields.Datetime.context_timestamp(
                self, fields.Datetime.now()
            ).strftime("%Y-%m-%d %H:%M"),
            "user_name": self.env.user.display_name,
            "date_from": self.date_from,
            "date_to": self.date_to,
            "formatLang": formatLang,
            "format_date": format_date,
            "env": self.env,
        }

    def action_preview(self):
        self.ensure_one()
        action = self.env.ref(
            "justech_purchase_sale_margin_control.action_report_payable_operational_pdf"
        ).report_action(self)
        if isinstance(action, dict):
            action = dict(action)
            action["report_type"] = "qweb-html"
            action["close_on_report_download"] = False
        return action

    def action_download_pdf(self):
        self.ensure_one()
        return self.env.ref(
            "justech_purchase_sale_margin_control.action_report_payable_operational_pdf"
        ).report_action(self)

    def action_download_xlsx(self):
        return self.action_generate_xlsx()

    def action_generate_xlsx(self):
        self.ensure_one()
        try:
            import xlsxwriter
        except ImportError as exc:
            raise UserError(
                _("La librería xlsxwriter no está disponible en el servidor.")
            ) from exc

        rows = self._build_rows()
        summary = self._build_summary(rows)

        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {"in_memory": True})
        sheet = workbook.add_worksheet("Cuentas por Pagar")
        bold = workbook.add_format({"bold": True, "bg_color": "#F3F4F6"})
        money = workbook.add_format({"num_format": "#,##0.00"})
        pct = workbook.add_format({"num_format": "0.00%"})

        headers = [
            "Proveedor",
            "Factura proveedor",
            "NCF / e-CF",
            "Fecha factura",
            "Vencimiento",
            "Moneda",
            "Total factura",
            "Pagado",
            "Saldo pendiente",
            "Estado",
            "OC",
            "Venta / Cotización",
            "Cliente",
            "Factura cliente",
            "Estado cobro cliente",
            "Total venta",
            "Costo relacionado",
            "Margen",
            "Margen %",
            "Estado relación",
            "Situación",
            "Empresa",
        ]
        for col, header in enumerate(headers):
            sheet.write(0, col, header, bold)
        sheet.freeze_panes(1, 0)
        sheet.autofilter(0, 0, max(len(rows), 1), len(headers) - 1)

        for row_idx, r in enumerate(rows, start=1):
            sheet.write(row_idx, 0, r["vendor"])
            sheet.write(row_idx, 1, r["bill_name"])
            sheet.write(row_idx, 2, r["ncf"])
            if r["invoice_date"]:
                sheet.write(row_idx, 3, str(r["invoice_date"]))
            else:
                sheet.write(row_idx, 3, "")
            if r["invoice_date_due"]:
                sheet.write(row_idx, 4, str(r["invoice_date_due"]))
            else:
                sheet.write(row_idx, 4, "")
            sheet.write(row_idx, 5, r["currency"])
            sheet.write_number(row_idx, 6, r["amount_total"], money)
            sheet.write_number(row_idx, 7, r["amount_paid"], money)
            sheet.write_number(row_idx, 8, r["amount_residual"], money)
            sheet.write(row_idx, 9, r["payment_state"])
            sheet.write(row_idx, 10, r["po_names"])
            sheet.write(row_idx, 11, r["so_names"])
            sheet.write(row_idx, 12, r["customer"])
            sheet.write(row_idx, 13, r["customer_invoice"])
            sheet.write(row_idx, 14, r["customer_collection"])
            if r["sale_amount"] is None:
                sheet.write(row_idx, 15, "—")
                sheet.write(row_idx, 16, "—")
                sheet.write(row_idx, 17, "—")
                sheet.write(row_idx, 18, "—")
            else:
                sheet.write_number(row_idx, 15, r["sale_amount"], money)
                sheet.write_number(row_idx, 16, r["cost_amount"], money)
                sheet.write_number(row_idx, 17, r["margin"] or 0.0, money)
                sheet.write_number(row_idx, 18, (r["margin_pct"] or 0.0) / 100.0, pct)
            sheet.write(row_idx, 19, r["relation_state"])
            sheet.write(row_idx, 20, r["situation"])
            sheet.write(row_idx, 21, r["company"])

        for col, width in enumerate(
            (22, 18, 16, 12, 12, 8, 12, 12, 14, 10, 14, 16, 22, 16, 14, 12, 12, 12, 10, 14, 28, 18)
        ):
            sheet.set_column(col, col, width)

        resum = workbook.add_worksheet("Resumen")
        resum.write(0, 0, "Métrica", bold)
        resum.write(0, 1, "Valor", bold)
        resum.write(1, 0, "Facturas pendientes")
        resum.write(1, 1, summary["bill_count"])
        resum.write(2, 0, "Relacionadas con ventas")
        resum.write(2, 1, summary["related"])
        resum.write(3, 0, "Sin venta relacionada")
        resum.write(3, 1, summary["no_sale"])
        resum.write(4, 0, "Clientes ya cobrados")
        resum.write(4, 1, summary["collected"])
        resum.write(5, 0, "Clientes pendientes de cobro")
        resum.write(5, 1, summary["pending_cust"])
        resum.write(7, 0, "Moneda", bold)
        resum.write(7, 1, "Total pendiente", bold)
        resum.write(7, 2, "Facturas", bold)
        for i, cur in enumerate(summary["by_currency"], start=8):
            resum.write(i, 0, cur["currency"])
            resum.write_number(i, 1, cur["residual"], money)
            resum.write(i, 2, cur["count"])
        resum.set_column(0, 0, 32)
        resum.set_column(1, 2, 16)

        workbook.close()
        output.seek(0)
        self.write(
            {
                "export_file": base64.b64encode(output.read()),
                "export_filename": "cxp_operativo_%s_%s.xlsx" % (self.date_from, self.date_to),
            }
        )
        return {
            "type": "ir.actions.act_url",
            "url": (
                "/web/content/?model=purchase.sale.payable.auxiliary.report&id=%s"
                "&field=export_file&filename_field=export_filename&download=true" % self.id
            ),
            "target": "self",
        }

    def _get_report_base_filename(self):
        self.ensure_one()
        return "Cuentas_por_Pagar_%s_%s" % (self.date_from, self.date_to)
