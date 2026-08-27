"""Exportador DGII 609 — pagos por servicios al exterior."""
from __future__ import annotations

from odoo import _, models


class JustechDoDgii609Exporter(models.AbstractModel):
    _name = "justech.do.dgii.609.exporter"
    _inherit = "justech.do.dgii.exporter.mixin"
    _description = "Exportador DGII formato 609"

    def _dgii_report_code(self):
        return "609"

    def _dgii_mapping_filename(self):
        return "dgii_609_mapping.json"

    def _dgii_summary_title(self):
        return _("Resumen validación 609")

    def _dgii_partner_role_label(self):
        return _("Proveedor extranjero")

    def _dgii_text_columns(self):
        return {"B", "D", "E", "H"}

    def _dgii_withholding_affects(self, catalog):
        return catalog.withholding_type == "isr"

    def _is_foreign_partner(self, partner):
        country = partner.country_id
        if not country or not country.code:
            return False
        return country.code.upper() != "DO"

    def _dgii_base_period_domain(self, company, date_from, date_to):
        return [
            ("company_id", "=", company.id),
            ("state", "=", "posted"),
            ("move_type", "in", ("in_invoice",)),
            ("invoice_date", ">=", date_from),
            ("invoice_date", "<=", date_to),
            "|",
            ("justech_do_foreign_609", "=", True),
            "&",
            ("partner_id.country_id.code", "!=", "DO"),
            ("partner_id.country_id", "!=", False),
        ]

    def _document_ref(self, move):
        return self._fdp().get_foreign_document_ref(move)

    def _payment_date(self, move):
        return self._fdp().get_foreign_payment_date(move)

    def _isr_retained(self, move):
        explicit = self._fdp().get_foreign_isr_retained(move)
        if explicit:
            return self._format_amount(explicit)
        _itbis, isr_wh, _isr_type, _missing = self._withholding_breakdown(move)
        return isr_wh

    def _presumed_income(self, move):
        explicit = self._fdp().get_foreign_presumed_income(move)
        if explicit:
            return self._format_amount(explicit)
        isr = self._isr_retained(move)
        if isr:
            return self._format_amount(abs(move.amount_untaxed_signed))
        return 0.0

    def _exchange_rate(self, move):
        return self._fdp().get_foreign_exchange_rate(move)

    def _dgii_validate_single_move(self, move, date_from, date_to):
        errors = []
        label = self._move_label(move)
        partner = move.partner_id
        if not self._is_foreign_partner(partner) and not move.justech_do_foreign_609:
            errors.append(
                _("%(doc)s: el proveedor no es del exterior.")
                % {"doc": label}
            )
        if not partner.name:
            errors.append(_("%(doc)s: falta razón social del proveedor.") % {"doc": label})
        if not partner.country_id or not partner.country_id.code:
            errors.append(
                _("%(doc)s: el proveedor %(partner)s no tiene país configurado.")
                % {"doc": label, "partner": partner.display_name}
            )
        if not self._fdp().get_foreign_service_type(move):
            errors.append(_("%(doc)s: falta tipo de servicio DGII (609).") % {"doc": label})
        doc_ref = self._document_ref(move)
        if not doc_ref:
            errors.append(_("%(doc)s: falta número de documento de soporte.") % {"doc": label})
        if not move.invoice_date:
            errors.append(_("%(doc)s: falta fecha del documento.") % {"doc": label})
        elif move.invoice_date < date_from or move.invoice_date > date_to:
            errors.append(
                _("%(doc)s: la fecha %(fecha)s está fuera del período.")
                % {"doc": label, "fecha": move.invoice_date}
            )
        amount = abs(move.amount_total_signed)
        if amount <= 0:
            errors.append(_("%(doc)s: el monto facturado debe ser mayor que cero.") % {"doc": label})
        if move.currency_id and not move.currency_id.name:
            errors.append(_("%(doc)s: falta moneda del documento.") % {"doc": label})
        rate = self._exchange_rate(move)
        if move.currency_id != move.company_id.currency_id and not rate:
            errors.append(_("%(doc)s: falta tasa de cambio para moneda extranjera.") % {"doc": label})
        isr = self._isr_retained(move)
        if isr and not self._payment_date(move):
            errors.append(
                _("%(doc)s: falta fecha de retención ISR para el pago al exterior.")
                % {"doc": label}
            )
        return errors

    def format_validation_summary(self, result):
        lines = super().format_validation_summary(result).split("\n")
        exportable = result["buckets"]["valid"]
        total_amount = sum(abs(m.amount_total_signed) for m in exportable)
        total_isr = sum(self._isr_retained(m) for m in exportable)
        counts = result["counts"]
        lines.extend(
            [
                "",
                _("Resumen pagos exterior (documentos válidos)"),
                "—" * 24,
                _("Pagos exportables: %(n)s") % {"n": counts["valid"]},
                _("Monto facturado: %(amount).2f") % {"amount": total_amount},
                _("ISR retenido: %(amount).2f") % {"amount": total_isr},
                _("Documentos incompletos: %(n)s") % {"n": counts["incomplete"]},
            ]
        )
        return "\n".join(lines)

    def _dgii_build_row_values(self, move, line_number, date_from, date_to):
        partner = move.partner_id
        retention_date = self._payment_date(move)
        isr = self._isr_retained(move)
        fdp = self._fdp()
        return {
            "A": line_number,
            "B": (partner.name or "")[:30],
            "C": fdp.get_foreign_service_type(move),
            "D": (partner.country_id.code or "").upper(),
            "E": self._document_ref(move),
            "F": self._format_dgii_date(move.invoice_date),
            "G": self._format_amount(abs(move.amount_total_signed)),
            "H": move.currency_id.name or move.company_id.currency_id.name or "",
            "I": self._exchange_rate(move),
            "J": self._format_dgii_date(retention_date) if isr else "",
            "K": self._presumed_income(move),
            "L": isr,
        }

    def validate_period_609(self, company, date_from, date_to, refresh_states=True):
        return self.validate_period(company, date_from, date_to, refresh_states)
