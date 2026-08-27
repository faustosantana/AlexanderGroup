"""Mixin compartido exportadores DGII — clasificación, validación y Excel oficial."""
from __future__ import annotations

import base64
import io
import json
import re
from collections import defaultdict
from pathlib import Path

from odoo import _, fields, models
from odoo.exceptions import UserError
from odoo.tools import float_round


class JustechDoDgiiExporterMixin(models.AbstractModel):
    _name = "justech.do.dgii.exporter.mixin"
    _description = "Mixin exportador DGII"

    # --- Hooks (subclases) ---

    def _dgii_report_code(self):
        raise NotImplementedError

    def _dgii_mapping_filename(self):
        raise NotImplementedError

    def _dgii_base_period_domain(self, company, date_from, date_to):
        raise NotImplementedError

    def _dgii_validate_single_move(self, move, date_from, date_to):
        raise NotImplementedError

    def _dgii_build_row_values(self, move, line_number, date_from, date_to):
        raise NotImplementedError

    def _dgii_withholding_affects(self, catalog):
        raise NotImplementedError

    def _classifier(self):
        return self.env["justech.do.dgii.tax.classifier"]

    def _dgii_summary_title(self):
        return _("Resumen validación %(code)s") % {"code": self._dgii_report_code()}

    def _dgii_partner_role_label(self):
        return _("Contacto")

    def _dgii_text_columns(self):
        return set()

    # --- Utilidades compartidas ---

    @classmethod
    def _mapping_path(cls, filename):
        return Path(__file__).resolve().parent.parent / "data" / filename

    def _load_mapping(self):
        filename = self._dgii_mapping_filename()
        path = self._mapping_path(filename)
        if not path.is_file():
            raise UserError(
                _("No se encontró el mapeo DGII %(code)s en %(path)s")
                % {"code": self._dgii_report_code(), "path": path}
            )
        return json.loads(path.read_text(encoding="utf-8"))

    def _format_dgii_date(self, value):
        if not value:
            return ""
        if isinstance(value, str):
            return value.replace("-", "")
        return fields.Date.to_date(value).strftime("%Y%m%d")

    def _format_amount(self, amount, digits=2):
        return float_round(abs(amount or 0.0), precision_digits=digits)

    def _is_withholding_tax_line(self, line):
        tax = line.tax_line_id
        return bool(tax and tax.amount < 0)

    def _withholding_catalog_model(self):
        if "justech.do.withholding.catalog" in self.env:
            return self.env["justech.do.withholding.catalog"]
        return self.env["account.tax"].browse()

    def _payment_withholding_lines(self, payment, move=None):
        if "justech_withholding_line_ids" in payment._fields:
            lines = payment.justech_withholding_line_ids
        else:
            return self.env["account.move"].browse()
        if move:
            return lines.filtered(lambda w: w.move_id == move)
        return lines

    def _catalog_for_tax(self, tax, company):
        if not tax:
            return self.env["account.tax"].browse()
        Catalog = self._withholding_catalog_model()
        if not Catalog:
            return self.env["account.tax"].browse()
        return Catalog.search(
            [("tax_id", "=", tax.id), ("company_id", "=", company.id)],
            limit=1,
        )

    def _withholding_breakdown(self, move):
        itbis_wh = 0.0
        isr_wh = 0.0
        isr_type = ""
        missing_codes = []
        Catalog = self._withholding_catalog_model()
        if not Catalog:
            return itbis_wh, isr_wh, isr_type, missing_codes
        for line in move.line_ids.filtered(self._is_withholding_tax_line):
            tax = line.tax_line_id
            catalog = self._catalog_for_tax(tax, move.company_id)
            amount = self._format_amount(line.balance)
            if catalog.withholding_type == "itbis":
                itbis_wh += amount
            elif catalog.withholding_type == "isr":
                isr_wh += amount
                if catalog.dgii_withholding_code:
                    isr_type = catalog.dgii_withholding_code
                elif self._dgii_withholding_affects(catalog):
                    missing_codes.append(catalog.display_name)
            elif tax and catalog:
                missing_codes.append(catalog.display_name or tax.name)
        for payment in move._get_reconciled_payments():
            for wh in self._payment_withholding_lines(payment, move):
                amount = self._format_amount(wh.amount)
                catalog = wh.catalog_id
                if not catalog:
                    continue
                if catalog.withholding_type == "itbis":
                    itbis_wh += amount
                elif catalog.withholding_type == "isr":
                    isr_wh += amount
                    if catalog.dgii_withholding_code:
                        isr_type = catalog.dgii_withholding_code
                    elif self._dgii_withholding_affects(catalog):
                        missing_codes.append(catalog.display_name)
        return itbis_wh, isr_wh, isr_type, missing_codes

    def _fdp(self):
        return self.env["justech.do.fiscal.data.provider"]

    def _is_cancelled_move(self, move):
        return self._fdp().is_voided(move)

    def _move_label(self, move):
        return move.name or move.ref or str(move.id)

    def _refresh_move_fiscal_state(self, move, date_from, date_to):
        if self._is_cancelled_move(move):
            state = "cancelled"
        elif not self._fdp().include_in_dgii(move):
            state = "excluded"
        elif self._dgii_validate_single_move(move, date_from, date_to):
            state = "incomplete"
        else:
            state = "valid"
        if move.justech_do_dgii_fiscal_state != state:
            move.justech_do_dgii_fiscal_state = state
        return state

    def classify_moves(self, company, date_from, date_to, refresh_states=True):
        all_moves = self.env["account.move"].search(
            self._dgii_base_period_domain(company, date_from, date_to),
            order="invoice_date, id",
        )
        buckets = {
            "all": all_moves,
            "cancelled": self.env["account.move"],
            "excluded": self.env["account.move"],
            "incomplete": self.env["account.move"],
            "valid": self.env["account.move"],
        }
        for move in all_moves:
            if refresh_states:
                state = self._refresh_move_fiscal_state(move, date_from, date_to)
            elif self._is_cancelled_move(move):
                state = "cancelled"
            elif not self._fdp().include_in_dgii(move):
                state = "excluded"
            elif self._dgii_validate_single_move(move, date_from, date_to):
                state = "incomplete"
            else:
                state = "valid"
            buckets[state] |= move
        return buckets

    def validate_period(self, company, date_from, date_to, refresh_states=True):
        buckets = self.classify_moves(
            company, date_from, date_to, refresh_states=refresh_states
        )
        errors_flat = []
        errors_by_partner = defaultdict(list)
        move_errors = {}
        for move in buckets["incomplete"]:
            move_errs = self._dgii_validate_single_move(move, date_from, date_to)
            move_errors[move.id] = move_errs
            partner_name = move.partner_id.display_name
            for err in move_errs:
                errors_flat.append(err)
                errors_by_partner[partner_name].append(
                    {
                        "move": self._move_label(move),
                        "move_id": move.id,
                        "error": err,
                    }
                )
        return {
            "buckets": buckets,
            "errors_flat": errors_flat,
            "errors_by_partner": dict(errors_by_partner),
            "move_errors": move_errors,
            "counts": {
                "all": len(buckets["all"]),
                "valid": len(buckets["valid"]),
                "incomplete": len(buckets["incomplete"]),
                "excluded": len(buckets["excluded"]),
                "cancelled": len(buckets["cancelled"]),
                "partners_affected": len(errors_by_partner),
                "error_lines": len(errors_flat),
            },
        }

    def format_validation_summary(self, result):
        counts = result["counts"]
        if not counts["all"]:
            return self._dgii_summary_title() + "\n" + _("No hay documentos en el período.")
        role = self._dgii_partner_role_label()
        lines = [
            self._dgii_summary_title(),
            "—" * 24,
            _("Documentos en período: %(n)s") % {"n": counts["all"]},
            _("Válidos para exportar: %(n)s") % {"n": counts["valid"]},
            _("Incompletos (con errores): %(n)s") % {"n": counts["incomplete"]},
            _("Excluidos fiscalmente: %(n)s") % {"n": counts["excluded"]},
            _("Anulados: %(n)s") % {"n": counts["cancelled"]},
            _("%(role)s con errores: %(n)s") % {"role": role, "n": counts["partners_affected"]},
            _("Total líneas de error: %(n)s") % {"n": counts["error_lines"]},
        ]
        if result["errors_by_partner"]:
            lines.append("")
            lines.append(_("Detalle por %(role)s (primeros 15):") % {"role": role.lower()})
            for partner_name in list(result["errors_by_partner"])[:15]:
                partner_errors = result["errors_by_partner"][partner_name]
                move_names = sorted({item["move"] for item in partner_errors})
                lines.append(
                    _("• %(partner)s — %(moves)s factura(s), %(errs)s error(es)")
                    % {
                        "partner": partner_name,
                        "moves": len(move_names),
                        "errs": len(partner_errors),
                    }
                )
            if len(result["errors_by_partner"]) > 15:
                lines.append(
                    _("… y %(n)s más. Descargue el detalle en Excel.")
                    % {"n": len(result["errors_by_partner"]) - 15}
                )
        elif counts["valid"]:
            lines.append("")
            lines.append(_("Sin errores en documentos incluidos. Listo para exportar."))
        return "\n".join(lines)

    def validate_moves(self, company, date_from, date_to, moves=None):
        if moves is not None:
            errors = []
            for move in moves:
                if not self._fdp().include_in_dgii(move) or self._is_cancelled_move(move):
                    continue
                errors.extend(self._dgii_validate_single_move(move, date_from, date_to))
            return errors
        result = self.validate_period(company, date_from, date_to)
        return result["errors_flat"]

    def _moves_for_period(self, company, date_from, date_to, only_valid=True):
        buckets = self.classify_moves(company, date_from, date_to)
        if only_valid:
            return buckets["valid"]
        return buckets["all"].filtered(
            lambda m: self._fdp().include_in_dgii(m) and not self._is_cancelled_move(m)
        )

    def export_errors_xlsx(self, company, date_from, date_to, result=None):
        try:
            import xlsxwriter
        except ImportError:
            raise UserError(_("Se requiere la librería xlsxwriter para exportar errores."))

        result = result or self.validate_period(company, date_from, date_to)
        buckets = result["buckets"]
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {"in_memory": True})
        bold = workbook.add_format({"bold": True})
        wrap = workbook.add_format({"text_wrap": True})
        role = self._dgii_partner_role_label()

        sheet_errors = workbook.add_worksheet("Errores"[:31])
        headers = [role, _("RNC/Cédula"), _("Factura"), _("NCF"), _("Estado fiscal"), _("Errores")]
        for col, header in enumerate(headers):
            sheet_errors.write(0, col, header, bold)
        row = 1
        state_labels = dict(
            self.env["account.move"]._fields["justech_do_dgii_fiscal_state"].selection
        )
        for move in buckets["incomplete"]:
            errs = result["move_errors"].get(move.id) or self._dgii_validate_single_move(
                move, date_from, date_to
            )
            sheet_errors.write(row, 0, move.partner_id.display_name)
            sheet_errors.write(row, 1, move.partner_id.vat or "")
            sheet_errors.write(row, 2, self._move_label(move))
            sheet_errors.write(row, 3, self._fdp().get_ncf(move))
            sheet_errors.write(row, 4, state_labels.get(move.justech_do_dgii_fiscal_state, ""))
            sheet_errors.write(row, 5, "\n".join(errs), wrap)
            row += 1

        sheet_excluded = workbook.add_worksheet("Excluidos"[:31])
        ex_headers = [role, _("Factura"), _("NCF"), _("Estado fiscal"), _("Motivo exclusión")]
        for col, header in enumerate(ex_headers):
            sheet_excluded.write(0, col, header, bold)
        for row_idx, move in enumerate(buckets["excluded"] | buckets["cancelled"], start=1):
            sheet_excluded.write(row_idx, 0, move.partner_id.display_name)
            sheet_excluded.write(row_idx, 1, self._move_label(move))
            sheet_excluded.write(row_idx, 2, self._fdp().get_ncf(move))
            sheet_excluded.write(
                row_idx, 3, state_labels.get(move.justech_do_dgii_fiscal_state, "")
            )
            sheet_excluded.write(row_idx, 4, self._fdp().get_dgii_exclusion_reason(move))

        sheet_valid = workbook.add_worksheet("Validos"[:31])
        val_headers = [role, _("Factura"), _("NCF"), _("Fecha"), _("Total")]
        for col, header in enumerate(val_headers):
            sheet_valid.write(0, col, header, bold)
        for row_idx, move in enumerate(buckets["valid"], start=1):
            sheet_valid.write(row_idx, 0, move.partner_id.display_name)
            sheet_valid.write(row_idx, 1, self._move_label(move))
            sheet_valid.write(row_idx, 2, self._fdp().get_ncf(move))
            sheet_valid.write(row_idx, 3, str(move.invoice_date or ""))
            sheet_valid.write(row_idx, 4, abs(move.amount_total_signed))

        workbook.close()
        period = date_from.strftime("%Y%m")
        code = self._dgii_report_code()
        filename = f"DGII_{code}_errores_{period}.xlsx"
        return base64.b64encode(output.getvalue()), filename

    def export_xlsx(self, company, date_from, date_to, moves=None, strict=False):
        mapping = self._load_mapping()
        code = self._dgii_report_code()
        if moves is None:
            result = self.validate_period(company, date_from, date_to)
            moves = result["buckets"]["valid"]
            if strict and result["counts"]["incomplete"]:
                raise UserError(
                    self.format_validation_summary(result)
                    + "\n\n"
                    + _("Corrija los documentos incompletos o exclúyalos fiscalmente.")
                )
        else:
            errors = self.validate_moves(company, date_from, date_to, moves=moves)
            if errors:
                raise UserError("\n".join(errors))

        if not moves:
            raise UserError(
                _("No hay documentos fiscalmente válidos para exportar en el período seleccionado.")
            )

        try:
            import xlsxwriter
        except ImportError:
            raise UserError(
                _("Se requiere la librería xlsxwriter para exportar el %(code)s.")
                % {"code": code}
            )

        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {"in_memory": True})
        sheet_name = mapping.get("hoja_principal", f"Herramienta Formato {code}")[:31]
        sheet = workbook.add_worksheet(sheet_name)
        bold = workbook.add_format({"bold": True})
        amount_fmt = workbook.add_format({"num_format": "0.00"})

        period = date_from.strftime("%Y%m")
        company_vat = re.sub(r"[\s\-]", "", company.vat or "")
        sheet.write(3, 0, "RNC o Cédula")
        sheet.write(3, 1, company_vat)
        sheet.write(4, 0, "Periodo")
        sheet.write(4, 1, period)
        sheet.write(5, 0, "Cantidad Registros")
        sheet.write(5, 2, len(moves))

        header_row = mapping.get("fila_encabezado", 11) - 1
        columns = mapping.get("columnas", [])
        col_index = {}
        text_cols = self._dgii_text_columns()
        for col_def in columns:
            letter = col_def.get("columna_excel")
            if not letter:
                continue
            idx = self._excel_col_index(letter)
            col_index[letter] = idx
            sheet.write(header_row, idx, col_def.get("nombre_dgii", ""), bold)

        data_start = mapping.get("fila_inicio_datos", 12) - 1
        for line_no, move in enumerate(moves, start=1):
            row_vals = self._dgii_build_row_values(move, line_no, date_from, date_to)
            row = data_start + line_no - 1
            for letter, value in row_vals.items():
                idx = col_index.get(letter)
                if idx is None:
                    continue
                if letter in text_cols:
                    sheet.write(row, idx, value)
                else:
                    sheet.write(row, idx, value, amount_fmt)

        workbook.close()
        filename = f"DGII_{code}_{period}.xlsx"
        return base64.b64encode(output.getvalue()), filename

    @staticmethod
    def _excel_col_index(letters):
        result = 0
        for char in letters:
            result = result * 26 + (ord(char) - 64)
        return result - 1
