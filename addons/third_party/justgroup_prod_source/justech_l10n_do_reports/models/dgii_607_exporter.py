"""Exportador piloto DGII 607 — layout oficial según dgii_607_mapping.json."""
from __future__ import annotations

from odoo import _, models


class JustechDoDgii607Exporter(models.AbstractModel):
    _name = "justech.do.dgii.607.exporter"
    _inherit = "justech.do.dgii.exporter.mixin"
    _description = "Exportador DGII formato 607"

    CONSUMER_NCF_PREFIXES = ("B02", "B12", "E32", "E33")

    def _dgii_report_code(self):
        return "607"

    def _dgii_mapping_filename(self):
        return "dgii_607_mapping.json"

    def _dgii_summary_title(self):
        return _("Resumen validación 607")

    def _dgii_partner_role_label(self):
        return _("Cliente")

    def _dgii_text_columns(self):
        return {"A", "B", "C", "D", "E", "F", "G", "H"}

    def _dgii_withholding_affects(self, catalog):
        return catalog.affects_607

    def _dgii_base_period_domain(self, company, date_from, date_to):
        return [
            ("company_id", "=", company.id),
            ("state", "=", "posted"),
            ("move_type", "in", ("out_invoice", "out_refund")),
            ("invoice_date", ">=", date_from),
            ("invoice_date", "<=", date_to),
        ]

    def _ncf_prefix(self, move):
        return self._fdp().get_document_type_prefix(move)

    def _is_consumer_invoice(self, move):
        return self._ncf_prefix(move) in self.CONSUMER_NCF_PREFIXES

    def _retention_date(self, move, date_from, date_to):
        for line in move.line_ids.filtered(self._is_withholding_tax_line):
            line_date = line.date
            if line_date and date_from <= line_date <= date_to:
                return line_date
        return False

    def _payment_method_code(self, move):
        if move.move_type == "out_refund":
            return "06"
        if move.payment_state in ("paid", "in_payment"):
            payments = move._get_reconciled_payments()
            if payments:
                name = (payments[0].payment_method_line_id.name or "").lower()
                if "efectivo" in name or "cash" in name:
                    return "01"
                if "tarjeta" in name or "card" in name:
                    return "03"
                if "cheque" in name:
                    return "02"
                return "02"
            return "02"
        if move.payment_state == "not_paid":
            return "04"
        return "07"

    def _income_type_code(self, move):
        return self._fdp().get_income_type_607(move)

    def _payment_amount_columns(self, move, total_with_tax, sign):
        """Asigna el total con ITBIS a la columna de medio de pago inferida."""
        cols = {letter: 0.0 for letter in ("R", "S", "T", "U", "V", "W")}
        code = self._payment_method_code(move)
        mapping = {
            "01": "R",
            "02": "S",
            "03": "T",
            "04": "U",
            "06": "U",
            "07": "R",
        }
        letter = mapping.get(code, "R")
        cols[letter] = total_with_tax * sign
        return cols

    def _dgii_validate_single_move(self, move, date_from, date_to):
        errors = []
        label = self._move_label(move)
        partner = move.partner_id
        consumer = self._is_consumer_invoice(move)
        if not self._fdp().get_ncf(move):
            errors.append(_("%(doc)s: la factura no tiene NCF.") % {"doc": label})
        if not consumer and not partner.vat:
            errors.append(
                _("%(doc)s: el cliente %(partner)s no tiene RNC/Cédula.")
                % {"doc": label, "partner": partner.display_name}
            )
        if partner.vat and not partner.justech_do_partner_id_type:
            errors.append(
                _("%(doc)s: el cliente %(partner)s no tiene tipo de identificación DGII.")
                % {"doc": label, "partner": partner.display_name}
            )
        if move.invoice_date and (move.invoice_date < date_from or move.invoice_date > date_to):
            errors.append(
                _("%(doc)s: la fecha %(fecha)s está fuera del período.")
                % {"doc": label, "fecha": move.invoice_date}
            )
        unknown = self._classifier().unknown_taxes(move, self._dgii_report_code())
        if unknown:
            errors.append(
                _("%(doc)s: impuesto no clasificado para DGII: %(taxes)s")
                % {
                    "doc": label,
                    "taxes": ", ".join(unknown.mapped("name")),
                }
            )
        _itbis_wh, _isr_wh, _isr_type, missing_codes = self._withholding_breakdown(move)
        for wh_name in missing_codes:
            errors.append(
                _("%(doc)s: retención «%(wh)s» sin código DGII configurado.")
                % {"doc": label, "wh": wh_name}
            )
        return errors

    def _dgii_build_row_values(self, move, line_number, date_from, date_to):
        partner = move.partner_id
        classifier = self._classifier()
        report_code = self._dgii_report_code()
        itbis = self._format_amount(classifier.move_itbis_amount(move, report_code))
        itbis_wh, isr_wh, _isr_type, _missing = self._withholding_breakdown(move)
        total_untaxed = self._format_amount(move.amount_untaxed_signed)
        total_with_tax = self._format_amount(move.amount_total_signed)
        retention_date = self._retention_date(move, date_from, date_to)
        fdp = self._fdp()
        ncf_modified = fdp.get_ncf_modified(move)
        sign = -1 if move.move_type == "out_refund" else 1
        payment_cols = self._payment_amount_columns(move, total_with_tax, sign)
        vat = ""
        if partner.vat:
            vat = (
                partner.justech_do_clean_vat()
                if hasattr(partner, "justech_do_clean_vat")
                else partner.vat
            )
        row = {
            "A": line_number,
            "B": vat,
            "C": partner.justech_do_partner_id_type or "",
            "D": fdp.get_ncf(move),
            "E": ncf_modified,
            "F": self._income_type_code(move),
            "G": self._format_dgii_date(move.invoice_date),
            "H": self._format_dgii_date(retention_date) if retention_date else "",
            "I": total_untaxed * sign,
            "J": itbis * sign,
            "K": self._format_amount(itbis_wh) * sign,
            "L": 0.0,
            "M": self._format_amount(isr_wh) * sign,
            "N": 0.0,
            "O": 0.0,
            "P": 0.0,
            "Q": 0.0,
        }
        row.update(payment_cols)
        return classifier.apply_tax_columns(row, move, report_code, sign=sign)

    def validate_period_607(self, company, date_from, date_to, refresh_states=True):
        return self.validate_period(company, date_from, date_to, refresh_states)

    def validate_moves_607(self, company, date_from, date_to, moves=None):
        return self.validate_moves(company, date_from, date_to, moves=moves)

    def _validate_single_move(self, move, date_from, date_to):
        return self._dgii_validate_single_move(move, date_from, date_to)

    def build_row_values(self, move, line_number, date_from, date_to):
        return self._dgii_build_row_values(move, line_number, date_from, date_to)
