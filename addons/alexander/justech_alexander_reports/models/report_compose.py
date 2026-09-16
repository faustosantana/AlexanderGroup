from odoo import models
from odoo.tools.misc import format_amount, format_date

from .propet_math import propet_display_texts, propet_line_amounts
from .report_layout import count_body_lines, spacer_mm, white_png_data_uri


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
        "phone": partner.phone or getattr(partner, "mobile", None) or "",
        "email": partner.email or "",
    }


def _dx_banks(company):
    rows = []
    holder = company._dx_legal_display()
    for bank in company._dx_report_banks():
        rows.append(
            {
                "bank": bank.bank_id.name if bank.bank_id else "Banco",
                "account": bank.acc_number or "",
                # Customer-facing titular is the company, not a personal holder.
                "holder": holder,
            }
        )
    return rows


def _dx_line_taxes(line):
    if "tax_ids" in line._fields:
        return line.tax_ids
    if "taxes_id" in line._fields:
        return line.taxes_id
    return line.env["account.tax"]


def _dx_line_uom(line):
    for fname in ("product_uom_id", "product_uom"):
        if fname in line._fields and line[fname]:
            return line[fname].display_name
    return ""


def _dx_money(env, amount, currency):
    return format_amount(env, amount or 0.0, currency)


def _dx_sign_space(lines, paper="A4", extra_mm=0):
    mm = spacer_mm(count_body_lines(lines), paper, extra_mm)
    px = max(0, int(round(mm * 96.0 / 25.4)))
    chunks = []
    remain = px
    while remain > 0:
        piece = min(48, remain)
        chunks.append(
            {
                "src": white_png_data_uri(piece),
                "h": piece,
                "style": (
                    "display:block;width:8px;height:%spx;max-height:none;"
                    "border:0;background:#ffffff;" % piece
                ),
                "tick_style": (
                    "display:block;height:%spx;min-height:%spx;line-height:%spx;"
                    "font-size:16px;background:#ffffff;color:#ffffff;"
                    "padding:0;margin:0;border:0;" % (piece, piece, piece)
                ),
            }
        )
        remain -= piece
    return {
        "spacer_mm": mm,
        "spacer_px": px,
        "spacer_chunks": chunks,
    }


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


def _dx_layout(company):
    return company._dx_report_theme().get("layout") or "dor"


_DX_PICKING_BADGE = {
    "draft": "BORRADOR",
    "waiting": "ESPERANDO",
    "confirmed": "CONFIRMADO",
    "assigned": "LISTO",
    "done": "",
    "cancel": "ANULADA",
}


class SaleOrderCompose(models.Model):
    _inherit = "sale.order"

    def _dx_is_proforma(self):
        ctx = self.env.context
        return bool(
            ctx.get("proforma") or ctx.get("proforma_invoice") or ctx.get("dx_proforma")
        )

    def _dx_doc_identity(self):
        self.ensure_one()
        if self.env.context.get("dx_propet"):
            return {
                "title": "FORMATO PROPET",
                "number": self.name or "—",
                "badge": "",
                "kicker": self.company_id.dx_trade_name or self.company_id.name,
            }
        if self._dx_is_proforma():
            return {
                "title": "FACTURA PROFORMA",
                "number": self.name or "—",
                "badge": "PROFORMA",
                "kicker": self.company_id.dx_trade_name or self.company_id.name,
            }
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
            "layout": _dx_layout(company),
            "partner": _dx_partner_lines(self.partner_id),
            "date": _dx_date(self.env, self.date_order),
            "validity": _dx_date(self.env, self.validity_date),
            "salesperson": _dx_salesperson(self.user_id, company),
            "payment_term": self.payment_term_id.name if self.payment_term_id else "—",
            "currency": currency.name if currency else "",
            "client_ref": self.client_order_ref or "",
            "client_ref_label": "Número de Orden de Compra del Cliente",
            "lines": lines,
            "totals": totals,
            "note": self.note or "",
            "terms": _dx_terms(company, fallback),
            "banks": _dx_banks(company) if company.dx_report_show_bank else [],
            "party_title": "Cliente",
            "show_signature": bool(company.dx_report_show_signature),
            "sign_left": "Elaborado por",
            "sign_right": ("Aceptado por el cliente" if quote else "Aprobado por"),
            **_dx_sign_space(lines),
        }

    def _dx_sale_propet_compose(self):
        """Formato Propet: columnas fiscales con importes nativos de Odoo."""
        payload = self._dx_sale_compose()
        payload["ident"] = dict(payload["ident"])
        if not self._dx_is_proforma():
            payload["ident"]["title"] = "FORMATO PROPET"
        currency = self.currency_id
        propet_lines = []
        for line in self.order_line:
            if line.display_type == "line_section":
                propet_lines.append({"kind": "section", "name": line.name or ""})
                continue
            if line.display_type == "line_note":
                propet_lines.append({"kind": "note", "name": line.name or ""})
                continue
            if line.display_type:
                continue
            amounts = propet_line_amounts(line)
            product = line.product_id
            product_label, description = propet_display_texts(
                product.name if product else "",
                product.display_name if product else "",
                line.name or "",
            )
            propet_lines.append(
                {
                    "kind": "line",
                    "product": product_label,
                    "name": description,
                    "qty": _dx_qty(amounts["qty"]),
                    "discount": (
                        ("%g%%" % amounts["discount"])
                        if amounts.get("discount")
                        else "—"
                    ),
                    "unit_excl": _dx_money(self.env, amounts["unit_excl"], currency),
                    "tax": _dx_money(self.env, amounts["tax"], currency),
                    "unit_incl": _dx_money(self.env, amounts["unit_incl"], currency),
                    "subtotal": _dx_money(self.env, amounts["subtotal"], currency),
                    "total": _dx_money(self.env, amounts["total"], currency),
                    "raw": amounts,
                }
            )
        payload["propet_lines"] = propet_lines
        payload["lines"] = propet_lines
        payload["totals"] = [
            {
                "label": "Subtotal sin impuesto",
                "value": _dx_money(self.env, self.amount_untaxed, currency),
                "grand": False,
            },
            {
                "label": "ITBIS",
                "value": _dx_money(self.env, self.amount_tax, currency),
                "grand": False,
            },
            {
                "label": "Total general",
                "value": _dx_money(self.env, self.amount_total, currency),
                "grand": True,
            },
        ]
        return payload

    def _dx_outgoing_pickings(self):
        self.ensure_one()
        pickings = self.picking_ids
        return pickings.filtered(lambda p: p.picking_type_code == "outgoing")


class AccountMoveCompose(models.Model):
    _inherit = "account.move"

    def _dx_doc_identity(self):
        self.ensure_one()
        if self.env.context.get("dx_propet"):
            return {
                "title": "FORMATO PROPET",
                "number": (
                    self.name
                    if self.state == "posted" and self.name and self.name != "/"
                    else (self.name or "Pendiente")
                ),
                "badge": "BORRADOR" if self.state == "draft" else "",
                "kicker": self.company_id.dx_trade_name or self.company_id.name,
            }
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
        if self.state == "posted" and self.name and self.name != "/":
            number = self.name
        else:
            number = "Pendiente"
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
        if "justech_do_ncf" in self._fields:
            ncf = self.justech_do_ncf or ""
        if not ncf and "l10n_latam_document_number" in self._fields:
            ncf = self.l10n_latam_document_number or ""
        origin_ncf = ""
        if "justech_do_origin_ncf" in self._fields:
            origin_ncf = self.justech_do_origin_ncf or ""
        if not origin_ncf and "l10n_do_origin_ncf" in self._fields:
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
        if refund:
            sign_left, sign_right = "Preparado por", "Aprobado por"
        else:
            sign_left, sign_right = "Elaborado por", "Recibido conforme"
        return {
            "ident": ident,
            "partner": _dx_partner_lines(self.partner_id),
            "date": _dx_date(self.env, self.invoice_date or self.date),
            "due": _dx_date(self.env, self.invoice_date_due),
            "layout": _dx_layout(company),
            "salesperson": _dx_salesperson(
                self.invoice_user_id if "invoice_user_id" in self._fields else False,
                company,
            ),
            "ncf": ncf,
            "ncf_missing": not bool(ncf),
            "ncf_pending": not bool(ncf),
            "origin_ncf": origin_ncf,
            "origin_move": origin_move,
            "origin": self.invoice_origin or "",
            "client_ref": self.ref or "",
            "client_ref_label": "Número de Orden de Compra del Cliente",
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
            "party_title": "Cliente",
            "credited": (
                _dx_money(self.env, self.amount_total, currency) if refund else ""
            ),
            "show_signature": False,
            "sign_left": sign_left,
            "sign_right": sign_right,
            "is_refund": refund,
            **_dx_sign_space(lines, extra_mm=18 if refund else 0),
        }

    def _dx_invoice_propet_compose(self):
        payload = self._dx_invoice_compose()
        payload["ident"] = dict(payload["ident"])
        payload["ident"]["title"] = "FORMATO PROPET"
        currency = self.currency_id
        propet_lines = []
        invoice_lines = self.invoice_line_ids.filtered(
            lambda l: l.display_type in (False, "product")
        )
        for line in invoice_lines:
            amounts = propet_line_amounts(line)
            product = line.product_id
            product_label, description = propet_display_texts(
                product.name if product else "",
                product.display_name if product else "",
                line.name or "",
            )
            propet_lines.append(
                {
                    "kind": "line",
                    "product": product_label,
                    "name": description,
                    "qty": _dx_qty(amounts["qty"]),
                    "discount": (
                        ("%g%%" % amounts["discount"])
                        if amounts.get("discount")
                        else "—"
                    ),
                    "unit_excl": _dx_money(self.env, amounts["unit_excl"], currency),
                    "tax": _dx_money(self.env, amounts["tax"], currency),
                    "unit_incl": _dx_money(self.env, amounts["unit_incl"], currency),
                    "subtotal": _dx_money(self.env, amounts["subtotal"], currency),
                    "total": _dx_money(self.env, amounts["total"], currency),
                    "raw": amounts,
                }
            )
        for line in self.invoice_line_ids.filtered(
            lambda l: l.display_type == "line_section"
        ):
            propet_lines.insert(0, {"kind": "section", "name": line.name or ""})
        payload["propet_lines"] = propet_lines
        payload["lines"] = propet_lines
        payload["totals"] = [
            {
                "label": "Subtotal sin impuesto",
                "value": _dx_money(self.env, self.amount_untaxed, currency),
                "grand": False,
            },
            {
                "label": "ITBIS",
                "value": _dx_money(self.env, self.amount_tax, currency),
                "grand": False,
            },
            {
                "label": "Total general",
                "value": _dx_money(self.env, self.amount_total, currency),
                "grand": True,
            },
        ]
        return payload


class AccountPaymentCompose(models.Model):
    _inherit = "account.payment"

    def _dx_payment_applications(self):
        self.ensure_one()
        rows = []
        move = self.move_id
        if not move:
            return rows
        pay_lines = move.line_ids.filtered(
            lambda l: l.account_id.account_type
            in ("asset_receivable", "liability_payable")
        )
        seen = set()
        for line in pay_lines:
            partials = line.matched_debit_ids | line.matched_credit_ids
            for partial in partials:
                inv_line = (
                    partial.debit_move_id
                    if partial.debit_move_id.move_id != move
                    else partial.credit_move_id
                )
                inv = inv_line.move_id
                if not inv or inv.id in seen or inv == move:
                    continue
                seen.add(inv.id)
                applied_amt = abs(partial.amount or 0.0)
                if line.currency_id:
                    if (
                        partial.credit_move_id == line
                        and "debit_amount_currency" in partial._fields
                        and partial.debit_amount_currency
                    ):
                        applied_amt = abs(partial.debit_amount_currency)
                    elif (
                        "credit_amount_currency" in partial._fields
                        and partial.credit_amount_currency
                    ):
                        applied_amt = abs(partial.credit_amount_currency)
                ncf = ""
                if "justech_do_ncf" in inv._fields:
                    ncf = inv.justech_do_ncf or ""
                if not ncf and "l10n_latam_document_number" in inv._fields:
                    ncf = inv.l10n_latam_document_number or ""
                label = (
                    inv.name if inv.name and inv.name != "/" else (inv.ref or "Factura")
                )
                rows.append(
                    {
                        "document": label,
                        "ncf": ncf or "—",
                        "date": _dx_date(self.env, inv.invoice_date or inv.date),
                        "invoice_amount": _dx_money(
                            self.env, inv.amount_total, inv.currency_id
                        ),
                        "applied": _dx_money(self.env, applied_amt, self.currency_id),
                        "residual": _dx_money(
                            self.env, abs(inv.amount_residual or 0.0), inv.currency_id
                        ),
                    }
                )
        return rows

    def _dx_payment_withholding_breakdown(self):
        """ISR / ITBIS / otras desde líneas reales del pago. No recalcula."""
        self.ensure_one()
        currency = self.currency_id
        rows = []
        isr = itbis = other = 0.0
        if "justech_withholding_line_ids" not in self._fields:
            return rows, isr, itbis, other
        for wh in self.justech_withholding_line_ids:
            amount = float(wh.amount or 0.0)
            wtype = (wh.withholding_type or "").lower()
            if wtype == "isr":
                isr += amount
                kind = "ISR retenido"
            elif wtype == "itbis":
                itbis += amount
                kind = "ITBIS retenido"
            else:
                other += amount
                kind = "Otras retenciones"
            rows.append(
                {
                    "kind": kind,
                    "label": wh.label or wh.withholding_code or kind,
                    "code": wh.withholding_code or "",
                    "base_label": wh.base_label or "",
                    "base": _dx_money(self.env, wh.base_amount, currency),
                    "rate": wh.rate,
                    "amount": _dx_money(self.env, amount, currency),
                    "amount_num": amount,
                }
            )
        return rows, isr, itbis, other

    def _dx_doc_identity(self):
        self.ensure_one()
        if self.state != "draft" and self.name and self.name != "/":
            number = self.name
        else:
            number = "Pendiente"
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
        applied = self._dx_payment_applications()
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
        vendor = self.partner_type == "supplier"
        wh_rows, isr_amt, itbis_amt, other_amt = (
            self._dx_payment_withholding_breakdown()
        )
        wh_total = float(
            self.justech_withholding_total
            if "justech_withholding_total" in self._fields
            and self.justech_withholding_total
            else (isr_amt + itbis_amt + other_amt)
        )
        net_num = float(
            self.justech_net_transfer
            if "justech_net_transfer" in self._fields and self.justech_net_transfer
            else (float(self.amount or 0.0) - wh_total)
        )
        gross_num = float(self.amount or 0.0)
        if vendor and wh_total and abs(gross_num - net_num) < 0.01:
            gross_num = net_num + wh_total
        amount_words = ""
        try:
            spoken = net_num if vendor else float(self.amount or 0.0)
            amount_words = currency.with_context(lang="es_DO").amount_to_text(spoken)
        except Exception:
            amount_words = ""
        return {
            "ident": self._dx_doc_identity(),
            "layout": _dx_layout(company),
            "partner": _dx_partner_lines(self.partner_id),
            "date": _dx_date(self.env, self.date),
            "amount": _dx_money(self.env, net_num if vendor else self.amount, currency),
            "amount_words": amount_words,
            "currency": currency.name if currency else "",
            "method": method or "—",
            "bank": bank or "—",
            "reference": self.memo or "",
            "applied": applied,
            "unapplied": not bool(applied),
            "withholding": _dx_money(self.env, wh_total, currency) if wh_total else "",
            "withholding_rows": wh_rows,
            "isr_withheld": _dx_money(self.env, isr_amt, currency) if isr_amt else "",
            "itbis_withheld": (
                _dx_money(self.env, itbis_amt, currency) if itbis_amt else ""
            ),
            "other_withheld": (
                _dx_money(self.env, other_amt, currency) if other_amt else ""
            ),
            "gross_amount": _dx_money(self.env, gross_num, currency),
            "net_paid": _dx_money(self.env, net_num, currency),
            "total_applied": _dx_money(self.env, gross_num, currency),
            "net_received": _dx_money(self.env, net_num, currency) if net_num else "",
            "is_vendor": vendor,
            "amount_label": "Neto pagado" if vendor else "Monto recibido",
            "banks": _dx_banks(company) if company.dx_report_show_bank else [],
            "terms": (
                "Este documento es un comprobante de pago. "
                "No sustituye factura con NCF."
                if vendor
                else "Este documento es un comprobante de ingreso. "
                "No sustituye factura con NCF."
            ),
            "party_title": "Pagado a" if vendor else "Recibido de",
            "show_signature": bool(company.dx_report_show_signature),
            "sign_left": "Recibido por",
            "sign_right": "Entregado por",
            **_dx_sign_space(applied, paper="A5", extra_mm=10),
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

    def _dx_purchase_compose(self):
        self.ensure_one()
        company = self.company_id
        currency = self.currency_id
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
            qty = line.product_qty if "product_qty" in line._fields else 0.0
            name = line.name or (
                line.product_id.display_name if line.product_id else ""
            )
            lines.append(
                {
                    "kind": "line",
                    "name": name,
                    "qty": _dx_qty(qty),
                    "uom": _dx_line_uom(line),
                    "price": _dx_money(self.env, line.price_unit, currency),
                    "tax": _dx_tax_label(_dx_line_taxes(line)),
                    "amount": _dx_money(self.env, line.price_subtotal, currency),
                }
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
        dest = ""
        if self.dest_address_id:
            dest = self.dest_address_id.display_name or ""
        return {
            "ident": self._dx_doc_identity(),
            "layout": _dx_layout(company),
            "partner": _dx_partner_lines(self.partner_id),
            "party_title": "Proveedor",
            "date": _dx_date(self.env, self.date_order),
            "validity": "",
            "due": _dx_date(self.env, self.date_planned) if self.date_planned else "",
            "salesperson": _dx_salesperson(self.user_id, company),
            "payment_term": (
                self.payment_term_id.name if self.payment_term_id else "—"
            ),
            "currency": currency.name if currency else "",
            "client_ref": self.partner_ref or "",
            "origin": dest,
            "lines": lines,
            "totals": totals,
            "note": getattr(self, "notes", None) or getattr(self, "note", None) or "",
            "terms": (
                "Documento de compra. No es una factura. "
                "Confirmar cantidades y condiciones al recibir."
            ),
            "banks": [],
            "show_signature": bool(company.dx_report_show_signature),
            "sign_left": "Solicitado por",
            "sign_right": "Aprobado por",
            **_dx_sign_space(lines),
        }


class StockPickingCompose(models.Model):
    _inherit = "stock.picking"

    def _dx_doc_identity(self):
        self.ensure_one()
        incoming = self.picking_type_code == "incoming"
        return {
            "title": "RECEPCIÓN" if incoming else "CONDUCE",
            "number": self.name or "—",
            "badge": _DX_PICKING_BADGE.get(self.state or "", ""),
            "kicker": self.company_id.dx_trade_name or self.company_id.name,
        }

    def _dx_move_done_qty(self, move):
        if "quantity" in move._fields:
            return move.quantity
        if "quantity_done" in move._fields:
            return move.quantity_done
        return 0.0

    def _dx_picking_compose(self):
        self.ensure_one()
        company = self.company_id
        incoming = self.picking_type_code == "incoming"
        partner = self.partner_id
        lines = []
        moves = self.move_ids if "move_ids" in self._fields else self.move_lines
        for move in moves:
            product = move.product_id
            product_label, description = propet_display_texts(
                product.name if product else "",
                product.display_name if product else "",
                move.name or "",
            )
            uom = ""
            if "product_uom" in move._fields and move.product_uom:
                uom = move.product_uom.display_name
            elif "product_uom_id" in move._fields and move.product_uom_id:
                uom = move.product_uom_id.display_name
            lines.append(
                {
                    "kind": "line",
                    "product": product_label,
                    "name": description or product_label,
                    "qty": _dx_qty(move.product_uom_qty),
                    "done": _dx_qty(self._dx_move_done_qty(move)),
                    "uom": uom,
                }
            )
        if incoming:
            sign_left, sign_right = "Entregado por proveedor", "Recibido por"
            party_title = "Proveedor"
        else:
            sign_left, sign_right = "Entregado por", "Recibido por"
            party_title = "Cliente"
        return {
            "ident": self._dx_doc_identity(),
            "layout": _dx_layout(company),
            "embed_masthead": incoming,
            "company_name": company._dx_legal_display(),
            "company_vat": company.vat or "",
            "company_mail": company.email or "",
            "company_phone": company.phone or "",
            "partner": _dx_partner_lines(partner) if partner else {"name": "—"},
            "party_title": party_title,
            "date": _dx_date(self.env, self.date_done or self.scheduled_date),
            "origin": self.origin or "",
            "sale_order": (
                self.sale_id.name
                if "sale_id" in self._fields and self.sale_id
                else (self.origin or "")
            ),
            "delivery_street": (
                ", ".join(
                    p
                    for p in [
                        partner.street,
                        partner.street2,
                        partner.city,
                    ]
                    if partner and p
                )
                if partner
                else ""
            ),
            "carrier": (
                self.carrier_id.display_name
                if "carrier_id" in self._fields and self.carrier_id
                else ""
            ),
            "lines": lines,
            "note": self.note or "",
            "terms": "",
            "banks": [],
            "show_signature": bool(company.dx_report_show_signature),
            "sign_left": sign_left,
            "sign_right": sign_right,
            "incoming": incoming,
            **_dx_sign_space(lines),
        }
