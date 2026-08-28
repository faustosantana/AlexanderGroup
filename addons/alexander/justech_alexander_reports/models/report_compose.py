from odoo import models
from odoo.tools.misc import format_amount, format_date


def _dx_qty(qty):
    try:
        value = float(qty or 0.0)
    except (TypeError, ValueError):
        return "—"
    if abs(value - int(value)) < 0.00001:
        return str(int(value))
    return ("%.2f" % value).rstrip("0").rstrip(".")


def _dx_tax_label(taxes):
    if not taxes:
        return "—"
    parts = []
    for tax in taxes:
        amount = tax.amount or 0.0
        if abs(amount) < 0.00001:
            parts.append("Exento")
        else:
            parts.append("%g%%" % amount)
    return " + ".join(parts)


def _dx_partner_lines(partner):
    partner = partner.commercial_partner_id or partner
    street = ", ".join(p for p in [partner.street, partner.street2] if p)
    city = ", ".join(
        p
        for p in [
            partner.city,
            partner.state_id.name if partner.state_id else False,
        ]
        if p
    )
    return {
        "name": partner.name or "",
        "vat": partner.vat or "",
        "street": street,
        "city": city,
        "phone": partner.phone or partner.mobile or "",
        "email": partner.email or "",
    }


def _dx_banks(company):
    rows = []
    for bank in company._dx_report_banks():
        rows.append(
            {
                "bank": bank.bank_id.name if bank.bank_id else "Banco",
                "account": bank.acc_number or "",
                "holder": bank.acc_holder_name or company.name,
            }
        )
    return rows


def _dx_money(env, amount, currency):
    return format_amount(env, amount or 0.0, currency)


def _dx_date(env, value):
    if not value:
        return "—"
    if hasattr(value, "date"):
        value = value.date()
    return format_date(env, value)


def _dx_salesperson(user, company):
    if not company.dx_report_show_salesperson or not user:
        return ""
    name = (user.name or "").strip()
    if name in ("OdooBot", "Administrator", "Public user", "Public User"):
        return "Equipo comercial"
    return name


def _dx_method_label(name):
    mapping = {
        "Manual Payment": "Pago manual",
        "Manual": "Pago manual",
        "Electronic": "Transferencia",
        "Check": "Cheque",
        "Batch Payment": "Pago en lote",
    }
    return mapping.get(name or "", name or "—")


def _dx_terms(company, fallback):
    return (company.dx_report_terms or company.invoice_terms or fallback or "").strip()


class SaleOrderCompose(models.Model):
    _inherit = "sale.order"

    def _dx_doc_identity(self):
        self.ensure_one()
        quote = self.state in ("draft", "sent")
        return {
            "title": "COTIZACIÓN" if quote else "PEDIDO DE VENTA",
            "number": self.name or "—",
            "badge": "BORRADOR" if self.state == "draft" else "",
            "kicker": self.company_id.dx_trade_name or self.company_id.name,
        }

    def _dx_sale_compose(self):
        self.ensure_one()
        company = self.company_id
        currency = self.currency_id
        ident = self._dx_doc_identity()
        lines = []
        for line in self.order_line:
            if line.display_type == "line_section":
                lines.append({"kind": "section", "name": line.name or ""})
                continue
            if line.display_type == "line_note":
                lines.append({"kind": "note", "name": line.name or ""})
                continue
            if line.display_type:
                continue
            name = line.name or (
                line.product_id.display_name if line.product_id else ""
            )
            if line.discount:
                name = "%s (desc. %g%%)" % (name, line.discount)
            lines.append(
                {
                    "kind": "line",
                    "name": name,
                    "qty": _dx_qty(line.product_uom_qty),
                    "uom": (
                        line.product_uom_id.display_name if line.product_uom_id else ""
                    ),
                    "price": _dx_money(self.env, line.price_unit, currency),
                    "tax": _dx_tax_label(line.tax_ids),
                    "amount": _dx_money(self.env, line.price_subtotal, currency),
                }
            )
        quote = self.state in ("draft", "sent")
        fallback = (
            "Validez según la fecha indicada. Los precios no incluyen ITBIS salvo "
            "que la columna de impuestos lo indique. Esta cotización no constituye "
            "un comprobante fiscal; la factura se emite al aceptar."
            if quote
            else ""
        )
        totals = [
            {
                "label": "Subtotal",
                "value": _dx_money(self.env, self.amount_untaxed, currency),
                "grand": False,
            },
        ]
        if self.amount_tax:
            totals.append(
                {
                    "label": "ITBIS",
                    "value": _dx_money(self.env, self.amount_tax, currency),
                    "grand": False,
                }
            )
        totals.append(
            {
                "label": "Total",
                "value": _dx_money(self.env, self.amount_total, currency),
                "grand": True,
            }
        )
        return {
            "ident": ident,
            "partner": _dx_partner_lines(self.partner_id),
            "date": _dx_date(self.env, self.date_order),
            "validity": _dx_date(self.env, self.validity_date),
            "salesperson": _dx_salesperson(self.user_id, company),
            "payment_term": self.payment_term_id.name if self.payment_term_id else "—",
            "currency": currency.name if currency else "",
            "client_ref": self.client_order_ref or "",
            "lines": lines,
            "totals": totals,
            "note": self.note or "",
            "terms": _dx_terms(company, fallback),
            "banks": _dx_banks(company) if company.dx_report_show_bank else [],
            "show_signature": bool(company.dx_report_show_signature),
            "sign_left": "Elaborado por",
            "sign_right": "Aceptado por el cliente",
        }


class AccountMoveCompose(models.Model):
    _inherit = "account.move"

    def _dx_doc_identity(self):
        self.ensure_one()
        refund = self.move_type in ("out_refund", "in_refund")
        dtype = ""
        if (
            "l10n_latam_document_type_id" in self._fields
            and self.l10n_latam_document_type_id
        ):
            dtype = (
                self.l10n_latam_document_type_id.report_name
                or self.l10n_latam_document_type_id.name
                or ""
            ).lower()
        if refund:
            title = "NOTA DE CRÉDITO"
        elif "crédito fiscal" in dtype or "credito fiscal" in dtype:
            title = "FACTURA DE CRÉDITO"
        else:
            title = "FACTURA"
        number = self.name if self.name and self.name != "/" else "Sin numerar"
        badge = ""
        if self.state == "draft":
            badge = "BORRADOR"
        elif self.state == "cancel":
            badge = "ANULADA"
        return {
            "title": title,
            "number": number,
            "badge": badge,
            "kicker": self.company_id.dx_trade_name or self.company_id.name,
        }

    def _dx_invoice_compose(self):
        self.ensure_one()
        company = self.company_id
        currency = self.currency_id
        ident = self._dx_doc_identity()
        ncf = ""
        if "l10n_latam_document_number" in self._fields:
            ncf = self.l10n_latam_document_number or ""
        origin_ncf = ""
        if "l10n_do_origin_ncf" in self._fields:
            origin_ncf = self.l10n_do_origin_ncf or ""
        origin_move = ""
        if self.reversed_entry_id:
            origin_move = self.reversed_entry_id.name or ""
        lines = []
        invoice_lines = self.invoice_line_ids.filtered(
            lambda l: l.display_type in (False, "product")
        )
        for line in invoice_lines:
            name = line.name or (
                line.product_id.display_name if line.product_id else ""
            )
            if line.discount:
                name = "%s (desc. %g%%)" % (name, line.discount)
            lines.append(
                {
                    "kind": "line",
                    "name": name,
                    "qty": _dx_qty(line.quantity),
                    "uom": (
                        line.product_uom_id.display_name if line.product_uom_id else ""
                    ),
                    "price": _dx_money(self.env, line.price_unit, currency),
                    "tax": _dx_tax_label(line.tax_ids),
                    "amount": _dx_money(self.env, line.price_subtotal, currency),
                }
            )
        for line in self.invoice_line_ids.filtered(
            lambda l: l.display_type == "line_section"
        ):
            lines.insert(0, {"kind": "section", "name": line.name or ""})
        totals = [
            {
                "label": "Subtotal",
                "value": _dx_money(self.env, self.amount_untaxed, currency),
                "grand": False,
            },
        ]
        if self.amount_tax:
            totals.append(
                {
                    "label": "ITBIS",
                    "value": _dx_money(self.env, self.amount_tax, currency),
                    "grand": False,
                }
            )
        totals.append(
            {
                "label": "Total",
                "value": _dx_money(self.env, self.amount_total, currency),
                "grand": True,
            }
        )
        refund = self.move_type in ("out_refund", "in_refund")
        fallback = (
            "Documento fiscal. Conserve este comprobante. ITBIS de acuerdo a la "
            "legislación dominicana vigente."
        )
        reason = ""
        if refund:
            reason = self.ref or self.narration or ""
        return {
            "ident": ident,
            "partner": _dx_partner_lines(self.partner_id),
            "date": _dx_date(self.env, self.invoice_date or self.date),
            "due": _dx_date(self.env, self.invoice_date_due),
            "ncf": ncf or "Pendiente de NCF",
            "ncf_missing": not bool(ncf),
            "origin_ncf": origin_ncf,
            "origin_move": origin_move,
            "origin": self.invoice_origin or "",
            "reason": reason,
            "payment_term": (
                self.invoice_payment_term_id.name
                if self.invoice_payment_term_id
                else "—"
            ),
            "currency": currency.name if currency else "",
            "lines": lines,
            "totals": totals,
            "note": self.narration or "",
            "terms": _dx_terms(company, fallback),
            "banks": (
                _dx_banks(company) if company.dx_report_show_bank and not refund else []
            ),
            "show_signature": bool(company.dx_report_show_signature),
            "sign_left": "Elaborado por",
            "sign_right": "Recibido conforme",
            "is_refund": refund,
        }


class AccountPaymentCompose(models.Model):
    _inherit = "account.payment"

    def _dx_doc_identity(self):
        self.ensure_one()
        number = self.name if self.name and self.name != "/" else "Sin numerar"
        badge = "BORRADOR" if self.state == "draft" else ""
        return {
            "title": "RECIBO DE PAGO",
            "number": number,
            "badge": badge,
            "kicker": self.company_id.dx_trade_name or self.company_id.name,
        }

    def _dx_payment_compose(self):
        self.ensure_one()
        company = self.company_id
        currency = self.currency_id
        invoices = self.env["account.move"]
        if (
            "justech_applied_invoice_ids" in self._fields
            and self.justech_applied_invoice_ids
        ):
            invoices = self.justech_applied_invoice_ids
        elif self.reconciled_invoice_ids:
            invoices = self.reconciled_invoice_ids
        applied = []
        for inv in invoices:
            ncf = ""
            if "l10n_latam_document_number" in inv._fields:
                ncf = inv.l10n_latam_document_number or ""
            label = inv.name if inv.name and inv.name != "/" else (inv.ref or "Factura")
            residual = abs(inv.amount_residual or 0.0)
            applied.append(
                {
                    "document": label,
                    "ncf": ncf or "—",
                    "date": _dx_date(self.env, inv.invoice_date or inv.date),
                    "invoice_amount": _dx_money(
                        self.env, inv.amount_total, inv.currency_id
                    ),
                    "applied": _dx_money(
                        self.env, min(self.amount, inv.amount_total), currency
                    ),
                    "residual": _dx_money(self.env, residual, inv.currency_id),
                }
            )
        method = ""
        if self.payment_method_line_id:
            method = _dx_method_label(self.payment_method_line_id.name)
        bank = ""
        if self.journal_id:
            bank = self.journal_id.name
        if self.partner_bank_id:
            bank = "%s · %s" % (
                self.partner_bank_id.bank_id.name or bank,
                self.partner_bank_id.acc_number or "",
            )
        amount_words = ""
        try:
            amount_words = currency.with_context(lang="es_DO").amount_to_text(
                self.amount
            )
        except Exception:
            amount_words = ""
        return {
            "ident": self._dx_doc_identity(),
            "partner": _dx_partner_lines(self.partner_id),
            "date": _dx_date(self.env, self.date),
            "amount": _dx_money(self.env, self.amount, currency),
            "amount_words": amount_words,
            "currency": currency.name if currency else "",
            "method": method or "—",
            "bank": bank or "—",
            "reference": self.memo or "",
            "applied": applied,
            "unapplied": not bool(applied),
            "banks": _dx_banks(company) if company.dx_report_show_bank else [],
            "terms": (
                "Este documento es un comprobante de ingreso. "
                "No sustituye factura con NCF."
            ),
            "show_signature": bool(company.dx_report_show_signature),
            "sign_left": "Recibido por",
            "sign_right": "Entregado por",
        }


class PurchaseOrderCompose(models.Model):
    _inherit = "purchase.order"

    def _dx_doc_identity(self):
        self.ensure_one()
        confirmed = self.state in ("purchase", "done")
        return {
            "title": "ORDEN DE COMPRA" if confirmed else "SOLICITUD DE COTIZACIÓN",
            "number": self.name or "—",
            "badge": "",
            "kicker": self.company_id.dx_trade_name or self.company_id.name,
        }


class StockPickingCompose(models.Model):
    _inherit = "stock.picking"

    def _dx_doc_identity(self):
        self.ensure_one()
        incoming = self.picking_type_code == "incoming"
        return {
            "title": "RECEPCIÓN" if incoming else "ENTREGA",
            "number": self.name or "—",
            "badge": (self.state or "").upper(),
            "kicker": self.company_id.dx_trade_name or self.company_id.name,
        }
