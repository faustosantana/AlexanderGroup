"""Exportador DGII 623 — retenciones del Estado (5% Gobierno)."""
from __future__ import annotations

from odoo import _, models

GOV_CATALOG_CODES = ("RET-GOB-5", "wh_isr_gov", "RET5%")
GOV_TAX_NAME = "-5% ISR Gov."


class JustechDoDgii623Exporter(models.AbstractModel):
    _name = "justech.do.dgii.623.exporter"
    _inherit = "justech.do.dgii.exporter.mixin"
    _description = "Exportador DGII formato 623"

    def _dgii_report_code(self):
        return "623"

    def _dgii_mapping_filename(self):
        return "dgii_623_mapping.json"

    def _dgii_summary_title(self):
        return _("Resumen validación 623")

    def _dgii_partner_role_label(self):
        return _("Entidad del Estado")

    def _dgii_text_columns(self):
        return {"B", "F", "G", "H"}

    def _dgii_withholding_affects(self, catalog):
        return getattr(catalog, "affects_623", False) or catalog.code in GOV_CATALOG_CODES

    def _withholding_catalog_model(self):
        if "justech.do.withholding.catalog" in self.env:
            return self.env["justech.do.withholding.catalog"]
        return self.env["account.move"].browse()

    def _payment_wh_model(self):
        if "justech.payment.withholding.line" in self.env:
            return self.env["justech.payment.withholding.line"]
        return self.env["account.move"].browse()

    def _gov_catalog(self, company):
        Catalog = self._withholding_catalog_model()
        if not Catalog:
            return self.env["account.move"].browse()
        # Preferir override de empresa; si no, catálogo global compartido.
        rec = Catalog.search(
            [
                ("code", "in", list(GOV_CATALOG_CODES)),
                ("company_id", "=", company.id),
                ("active", "=", True),
            ],
            limit=1,
        )
        if rec:
            return rec
        return Catalog.search(
            [
                ("code", "in", list(GOV_CATALOG_CODES)),
                ("company_id", "=", False),
                ("active", "=", True),
            ],
            limit=1,
        )

    def _gov_tax(self, company):
        return self.env["account.tax"].search(
            [
                ("name", "=", GOV_TAX_NAME),
                ("type_tax_use", "=", "sale"),
                ("company_id", "=", company.id),
            ],
            limit=1,
        )

    def _persistent_gov_lines(self, move=None, company=None, date_from=None, date_to=None):
        Wh = self._payment_wh_model()
        if Wh._name not in ("justech.payment.withholding.line"):
            return Wh.browse()
        domain = [
            ("amount", ">", 0),
            "|",
            ("affects_623", "=", True),
            ("catalog_id.code", "in", list(GOV_CATALOG_CODES)),
        ]
        if move:
            domain.append(("move_id", "=", move.id))
        if company:
            domain.append(("company_id", "=", company.id))
        if date_from:
            domain.append(("date", ">=", date_from))
        if date_to:
            domain.append(("date", "<=", date_to))
        return Wh.search(domain)

    def _payment_gov_wh_lines(self, payment, move=None):
        if "justech_withholding_line_ids" in payment._fields:
            lines = payment.justech_withholding_line_ids
        else:
            return self.env["account.move"].browse()
        lines = lines.filtered(
            lambda w: w.amount
            and (
                getattr(w, "affects_623", False)
                or (w.catalog_id and w.catalog_id.code in GOV_CATALOG_CODES)
            )
        )
        if move:
            lines = lines.filtered(lambda w: w.move_id == move)
        return lines

    def _has_gov_withholding(self, move, gov_tax):
        if move.justech_do_gov_withholding_amount:
            return True
        if self._persistent_gov_lines(move=move):
            return True
        if gov_tax and move.line_ids.filtered(lambda l: l.tax_line_id == gov_tax):
            return True
        for payment in move._get_reconciled_payments():
            if payment.justech_do_gov_withholding_amount:
                return True
            if self._payment_gov_wh_lines(payment, move):
                return True
        foreign_ret = getattr(move, "justech_ret_isr_gov", False)
        return bool(foreign_ret and self._gov_amount(move, gov_tax))

    def _gov_amount(self, move, gov_tax):
        persistent = self._persistent_gov_lines(move=move)
        if persistent:
            return self._format_amount(sum(persistent.mapped("amount")))
        if move.justech_do_gov_withholding_amount:
            return self._format_amount(move.justech_do_gov_withholding_amount)
        payments = move._get_reconciled_payments().filtered("justech_do_gov_withholding_amount")
        if payments:
            return self._format_amount(sum(payments.mapped("justech_do_gov_withholding_amount")))
        for payment in move._get_reconciled_payments():
            gov_wh = self._payment_gov_wh_lines(payment, move)
            if gov_wh:
                return self._format_amount(sum(gov_wh.mapped("amount")))
        amount = 0.0
        if gov_tax:
            amount += sum(
                abs(line.balance)
                for line in move.line_ids.filtered(lambda l: l.tax_line_id == gov_tax)
            )
        return self._format_amount(amount)

    def _payment_with_gov_data(self, move):
        payments = move._get_reconciled_payments().sorted("date", reverse=True)
        for payment in payments:
            if payment.justech_do_gov_withholding_amount:
                return payment
            if self._payment_gov_wh_lines(payment, move):
                return payment
            check_no = getattr(payment, "justech_check_number", None) or getattr(
                payment, "justech_check_number", None
            )
            if check_no:
                return payment
        return payments[:1]

    def _retention_date(self, move):
        if move.justech_do_gov_retention_date:
            return move.justech_do_gov_retention_date
        persistent = self._persistent_gov_lines(move=move)
        if persistent:
            return persistent[:1].date
        payment = self._payment_with_gov_data(move)
        if payment:
            return payment.date
        return move.invoice_date

    def _reference_data(self, move):
        payment = self._payment_with_gov_data(move)
        ref = move.justech_do_gov_retention_ref or ""
        ref_type = move.justech_do_gov_retention_ref_type or ""
        bank = move.justech_do_gov_retention_bank_id
        if payment:
            ref = (
                ref
                or getattr(payment, "justech_check_number", None)
                or getattr(payment, "justech_check_number", None)
                or getattr(payment, "justech_payment_reference", None)
                or getattr(payment, "justech_payment_reference", None)
                or payment.name
                or ""
            )
            if not ref_type:
                is_check = getattr(payment, "justech_is_check", False) or getattr(
                    payment, "justech_is_check", False
                )
                check_no = getattr(payment, "justech_check_number", None) or getattr(
                    payment, "justech_check_number", None
                )
                if is_check or check_no:
                    ref_type = "1"
                else:
                    ref_type = "2"
            if not bank:
                bank = getattr(payment, "justech_check_bank_id", None) or getattr(
                    payment, "justech_check_bank_id", None
                )
        if not ref_type:
            ref_type = "2"
        bank_name = bank.name if bank else ""
        return ref, ref_type, bank_name

    def _dgii_base_period_domain(self, company, date_from, date_to):
        gov_tax = self._gov_tax(company)
        domain = [
            ("company_id", "=", company.id),
            ("state", "=", "posted"),
            ("move_type", "in", ("out_invoice",)),
        ]
        if gov_tax:
            domain.append(("line_ids.tax_line_id", "=", gov_tax.id))
        else:
            domain.append(("justech_do_gov_withholding_amount", ">", 0))
        return domain

    def classify_moves(self, company, date_from, date_to, refresh_states=True):
        gov_tax = self._gov_tax(company)
        candidates = self.env["account.move"].search(
            self._dgii_base_period_domain(company, date_from, date_to),
            order="invoice_date, id",
        )
        if gov_tax:
            extra = self.env["account.move"].search(
                [
                    ("company_id", "=", company.id),
                    ("state", "=", "posted"),
                    ("move_type", "in", ("out_invoice",)),
                    ("justech_do_gov_withholding_amount", ">", 0),
                ]
            )
            candidates |= extra
        wh_moves = self._persistent_gov_lines(
            company=company, date_from=date_from, date_to=date_to
        )
        if wh_moves:
            candidates |= wh_moves.mapped("move_id")
        period_moves = self.env["account.move"]
        for move in candidates:
            if not self._has_gov_withholding(move, gov_tax):
                continue
            ret_date = self._retention_date(move)
            if ret_date and date_from <= ret_date <= date_to:
                period_moves |= move
        buckets = {
            "all": period_moves,
            "cancelled": self.env["account.move"],
            "excluded": self.env["account.move"],
            "incomplete": self.env["account.move"],
            "valid": self.env["account.move"],
        }
        for move in period_moves:
            if refresh_states:
                state = self._refresh_move_fiscal_state(move, date_from, date_to)
            elif not move.justech_do_include_in_dgii:
                state = "excluded"
            elif self._dgii_validate_single_move(move, date_from, date_to):
                state = "incomplete"
            else:
                state = "valid"
            buckets[state] |= move
        return buckets

    def _dgii_validate_single_move(self, move, date_from, date_to):
        errors = []
        label = self._move_label(move)
        partner = move.partner_id
        gov_tax = self._gov_tax(move.company_id)
        amount = self._gov_amount(move, gov_tax)
        if amount <= 0:
            errors.append(
                _("%(doc)s: no tiene retención 5%% Gobierno registrada.")
                % {"doc": label}
            )
        if not partner.vat:
            errors.append(
                _("%(doc)s: la entidad %(partner)s no tiene RNC.")
                % {"doc": label, "partner": partner.display_name}
            )
        ret_date = self._retention_date(move)
        if not ret_date:
            errors.append(_("%(doc)s: falta fecha de retención.") % {"doc": label})
        elif ret_date < date_from or ret_date > date_to:
            errors.append(
                _("%(doc)s: la fecha de retención %(fecha)s está fuera del período.")
                % {"doc": label, "fecha": ret_date}
            )
        ref, _ref_type, _bank = self._reference_data(move)
        if not ref:
            payment = self._payment_with_gov_data(move)
            if payment and payment.name:
                ref = payment.name
        if not ref:
            errors.append(
                _("%(doc)s: falta número de referencia del pago (cheque o transferencia).")
                % {"doc": label}
            )
        return errors

    def format_validation_summary(self, result):
        lines = super().format_validation_summary(result).split("\n")
        exportable = result["buckets"]["valid"]
        total_wh = sum(
            self._gov_amount(m, self._gov_tax(m.company_id)) for m in exportable
        )
        counts = result["counts"]
        lines.extend(
            [
                "",
                _("Resumen retenciones Estado (documentos válidos)"),
                "—" * 24,
                _("Retenciones exportables: %(n)s") % {"n": counts["valid"]},
                _("Total retenido: %(amount).2f") % {"amount": total_wh},
                _("Documentos incompletos: %(n)s") % {"n": counts["incomplete"]},
            ]
        )
        return "\n".join(lines)

    def _dgii_build_row_values(self, move, line_number, date_from, date_to):
        partner = move.partner_id
        gov_tax = self._gov_tax(move.company_id)
        ret_date = self._retention_date(move)
        ref, ref_type, bank_name = self._reference_data(move)
        vat = partner.vat or ""
        if hasattr(partner, "justech_do_clean_vat"):
            vat = partner.justech_do_clean_vat() or vat
        return {
            "A": line_number,
            "B": vat,
            "C": ret_date.strftime("%Y%m") if ret_date else "",
            "D": self._format_dgii_date(ret_date),
            "E": self._gov_amount(move, gov_tax),
            "F": ref,
            "G": ref_type,
            "H": bank_name,
        }

    def validate_period_623(self, company, date_from, date_to, refresh_states=True):
        return self.validate_period(company, date_from, date_to, refresh_states)
