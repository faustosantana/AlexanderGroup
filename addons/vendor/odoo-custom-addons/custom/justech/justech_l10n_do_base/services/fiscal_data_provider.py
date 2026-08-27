"""Capa de lectura fiscal unificada — coexistencia Justech / Adel / l10n_latam / Odoo.

Solo lectura: no modifica datos ni histórico.
"""
from __future__ import annotations

import re

from odoo import models

# Classic paper NCF: 11 (B01 + 8). e-CF DGII: 13 (E31 + 10).
# Some vendor e-NCF arrive with 11 sequence digits (14 total) — must still display.
NCF_RE = re.compile(r"^[BE][0-9]{2}[0-9]{7,12}$")


class JustechDoFiscalDataProvider(models.AbstractModel):
    _name = "justech.do.fiscal.data.provider"
    _description = "Justech Fiscal Data Provider (read-only coexistence layer)"

    # ------------------------------------------------------------------ helpers

    def _has_field(self, record, name):
        return name in record._fields

    def _clean_text(self, value):
        if value is None or value is False:
            return ""
        text = str(value).strip()
        return text

    def _first_text(self, record, names):
        for name in names:
            if not self._has_field(record, name):
                continue
            text = self._clean_text(record[name])
            if text:
                return text
        return ""

    def _normalize_ncf(self, value):
        text = self._clean_text(value).upper().replace(" ", "").replace("-", "")
        if not text:
            return ""
        if NCF_RE.match(text):
            return text
        return ""

    def _ncf_from_standard_fields(self, move):
        for name in ("ref", "payment_reference", "name"):
            if not self._has_field(move, name):
                continue
            candidate = self._normalize_ncf(move[name])
            if candidate:
                return candidate
        return ""

    def _latam_doc_type_record(self, move):
        if not self._has_field(move, "l10n_latam_document_type_id"):
            return self.env["l10n_latam.document.type"].browse()
        return move.l10n_latam_document_type_id

    def _latam_doc_type_prefix(self, doc_type):
        if not doc_type:
            return ""
        for attr in ("doc_code_prefix", "code", "internal_type"):
            if hasattr(doc_type, attr):
                value = self._clean_text(getattr(doc_type, attr, ""))
                if len(value) >= 3 and value[0] in "BE" and value[:3].isalnum():
                    return value[:3].upper()
        name = self._clean_text(doc_type.display_name or doc_type.name)
        for token in name.replace("-", " ").split():
            token = token.strip().upper()
            if len(token) >= 3 and token[0] in "BE":
                return token[:3]
        return ""

    # ------------------------------------------------------------------ API pública

    def get_ncf(self, move):
        """NCF / e-CF: Justech → Adel/latam → estándar Odoo (solo formato NCF) → vacío."""
        move.ensure_one()
        for name in ("justech_do_ncf",):
            if self._has_field(move, name):
                ncf = self._normalize_ncf(move[name])
                if ncf:
                    return ncf
        for name in ("l10n_latam_document_number",):
            if self._has_field(move, name):
                ncf = self._normalize_ncf(move[name])
                if ncf:
                    return ncf
        return self._ncf_from_standard_fields(move)

    def get_document_number(self, move):
        """Número de comprobante: NCF primero; si no hay, cadena documental Odoo."""
        move.ensure_one()
        ncf = self.get_ncf(move)
        if ncf:
            return ncf
        for name in ("ref", "payment_reference", "name"):
            if self._has_field(move, name):
                text = self._clean_text(move[name])
                if text:
                    return text
        return ""

    def get_document_type_prefix(self, move):
        """Prefijo tipo comprobante (B01, E31, …)."""
        move.ensure_one()
        selected = self.get_selected_document_type_prefix(move)
        if selected:
            return selected
        ncf = self.get_ncf(move)
        return ncf[:3].upper() if len(ncf) >= 3 else ""

    def get_selected_document_type_prefix(self, move):
        """Prefijo del tipo seleccionado (Justech/LATAM), sin fallback al NCF.

        Permite detectar inconsistencias tipo ≠ prefijo del número registrado.
        """
        move.ensure_one()
        if self._has_field(move, "justech_do_document_type_id") and move.justech_do_document_type_id:
            prefix = self._clean_text(move.justech_do_document_type_id.prefix)
            if prefix:
                return prefix.upper()[:3]
        latam_doc = self._latam_doc_type_record(move)
        prefix = self._latam_doc_type_prefix(latam_doc)
        return prefix.upper()[:3] if prefix else ""

    def get_ncf_prefix(self, move):
        """Primeros 3 caracteres del NCF efectivo (normalizado, sin alterar el valor)."""
        move.ensure_one()
        ncf = self.get_ncf(move)
        if ncf and len(ncf) >= 3:
            return ncf[:3].upper()
        # Lectura cruda por si hay guiones/espacios que _normalize_ncf descartó
        for name in ("justech_do_ncf", "l10n_latam_document_number"):
            if not self._has_field(move, name):
                continue
            raw = self._clean_text(move[name]).upper().replace(" ", "").replace("-", "")
            if len(raw) >= 3 and raw[0] in "BE":
                return raw[:3]
        return ""

    def check_type_ncf_prefix_consistency(self, move):
        """Compara tipo seleccionado vs prefijo del NCF almacenado.

        Returns:
            dict with keys:
            - ok (bool): True si no hay inconsistencia verificable
            - expected (str): prefijo del tipo seleccionado
            - found (str): prefijo del NCF
            - ncf (str): NCF efectivo
        No modifica datos.
        """
        move.ensure_one()
        expected = self.get_selected_document_type_prefix(move)
        ncf = self.get_ncf(move) or ""
        found = self.get_ncf_prefix(move)
        if not expected or not found:
            return {"ok": True, "expected": expected, "found": found, "ncf": ncf}
        return {
            "ok": expected == found,
            "expected": expected,
            "found": found,
            "ncf": ncf,
        }

    def get_document_type_name(self, move):
        move.ensure_one()
        if self._has_field(move, "justech_do_document_type_id") and move.justech_do_document_type_id:
            return move.justech_do_document_type_id.display_name
        latam_doc = self._latam_doc_type_record(move)
        if latam_doc:
            return latam_doc.display_name
        prefix = self.get_document_type_prefix(move)
        if prefix:
            doc = self.env["justech.do.fiscal.document.type"].get_by_prefix(
                prefix, move.company_id
            )
            if doc:
                return doc.display_name
        return ""

    def get_ncf_modified(self, move):
        move.ensure_one()
        for name in ("justech_do_ncf_modified", "justech_do_origin_ncf", "l10n_do_origin_ncf"):
            if self._has_field(move, name):
                ncf = self._normalize_ncf(move[name])
                if ncf:
                    return ncf
        return ""

    def get_origin_ncf(self, move):
        move.ensure_one()
        for name in ("justech_do_origin_ncf", "l10n_do_origin_ncf"):
            if self._has_field(move, name):
                ncf = self._normalize_ncf(move[name])
                if ncf:
                    return ncf
        return self.get_ncf_modified(move)

    def get_income_type_607(self, move):
        move.ensure_one()
        if self._has_field(move, "justech_do_income_type_607"):
            code = self._clean_text(move.justech_do_income_type_607)
            if code:
                return code
        if self._has_field(move, "l10n_do_income_type"):
            code = self._clean_text(move.l10n_do_income_type)
            if code:
                return code
        prefix = self.get_document_type_prefix(move)
        DocType = self.env["justech.do.fiscal.document.type"]
        if prefix in ("B14", "E44"):
            return "02"
        if prefix in ("B16", "E46"):
            return "06"
        if prefix in DocType.CONSUMER_NCF_PREFIXES:
            return "01"
        return "01"

    def get_expense_type_606(self, move):
        move.ensure_one()
        if self._has_field(move, "justech_do_expense_type_606"):
            code = self._clean_text(move.justech_do_expense_type_606)
            if code:
                return code
        if self._has_field(move, "l10n_do_expense_type"):
            code = self._clean_text(move.l10n_do_expense_type)
            if code:
                return code
        prefix = self.get_document_type_prefix(move)
        if prefix == "B13":
            return "06"
        return "02"

    def get_income_expense_type_display(self, move):
        """Etiqueta UI de ingreso (607) o costo/gasto (606) — solo lectura."""
        move.ensure_one()
        move_type = move.move_type if self._has_field(move, "move_type") else ""
        if move_type in ("out_invoice", "out_refund"):
            code = self.get_income_type_607(move)
            labels = {
                "01": "01 - Ingresos por Operaciones (No Financieros)",
                "02": "02 - Ingresos Financieros",
                "03": "03 - Ingresos Extraordinarios",
                "04": "04 - Ingresos por Arrendamientos",
                "05": "05 - Ingresos por Venta de Activo Depreciable",
                "06": "06 - Otros Ingresos",
            }
            if self._has_field(move, "l10n_do_income_type"):
                try:
                    sel = dict(move._fields["l10n_do_income_type"]._description_selection(move.env))
                    labels.update(sel)
                except Exception:
                    pass
            return labels.get(code, code or "")
        if move_type in ("in_invoice", "in_refund"):
            code = self.get_expense_type_606(move)
            labels = {
                "01": "01 - Gastos de Personal",
                "02": "02 - Gastos por Trabajo, Suministros y Servicio",
                "03": "03 - Arrendamientos",
                "04": "04 - Gastos de Activos Fijos",
                "05": "05 - Gastos de Representación",
                "06": "06 - Otras Deducciones Admitidas",
                "07": "07 - Gastos Financieros",
                "08": "08 - Gastos Extraordinarios",
                "09": "09 - Compras y Gastos que forman parte del Costo de Venta",
                "10": "10 - Adquisiciones de Activos",
                "11": "11 - Gastos de Seguros",
            }
            if self._has_field(move, "l10n_do_expense_type"):
                try:
                    sel = dict(move._fields["l10n_do_expense_type"]._description_selection(move.env))
                    labels.update(sel)
                except Exception:
                    pass
            return labels.get(code, code or "")
        return ""

    def get_cancellation_type(self, move):
        move.ensure_one()
        if self._has_field(move, "justech_do_ncf_cancel_type"):
            code = self._clean_text(move.justech_do_ncf_cancel_type)
            if code:
                return code.lstrip("0") or code
        if self._has_field(move, "l10n_do_cancellation_type"):
            code = self._clean_text(move.l10n_do_cancellation_type)
            if code:
                return code.lstrip("0") or code
        return ""

    def is_ecf(self, move):
        move.ensure_one()
        ncf = self.get_ncf(move)
        return bool(ncf and ncf.startswith("E"))

    def is_voided(self, move):
        move.ensure_one()
        if self._has_field(move, "justech_do_ncf_voided") and move.justech_do_ncf_voided:
            return True
        if self._has_field(move, "justech_do_dgii_line_status") and move.justech_do_dgii_line_status == "2":
            return True
        if self._has_field(move, "l10n_do_cancellation_type") and self._clean_text(move.l10n_do_cancellation_type):
            return True
        return False

    def get_void_date(self, move):
        move.ensure_one()
        if self._has_field(move, "justech_do_ncf_void_date") and move.justech_do_ncf_void_date:
            return move.justech_do_ncf_void_date
        if self.is_voided(move):
            return move.invoice_date
        return False

    def get_void_reason(self, move):
        move.ensure_one()
        return self._first_text(move, ("justech_do_ncf_void_reason",))

    def get_void_metadata(self, move):
        move.ensure_one()
        return {
            "voided": self.is_voided(move),
            "void_date": self.get_void_date(move),
            "void_reason": self.get_void_reason(move),
            "cancel_type": self.get_cancellation_type(move),
            "ncf": self.get_ncf(move),
        }

    def get_foreign_document_ref(self, move):
        move.ensure_one()
        if self._has_field(move, "justech_do_foreign_document_ref"):
            text = self._clean_text(move.justech_do_foreign_document_ref)
            if text:
                return text
        for name in ("ref", "payment_reference", "name"):
            if self._has_field(move, name):
                text = self._clean_text(move[name])
                if text:
                    return text
        return ""

    def get_foreign_service_type(self, move):
        move.ensure_one()
        if self._has_field(move, "justech_do_foreign_service_type"):
            return self._clean_text(move.justech_do_foreign_service_type)
        return ""

    def get_foreign_payment_date(self, move):
        move.ensure_one()
        if self._has_field(move, "justech_do_foreign_payment_date") and move.justech_do_foreign_payment_date:
            return move.justech_do_foreign_payment_date
        payments = move._get_reconciled_payments()
        if payments:
            return min(payments.mapped("date"))
        return move.invoice_date

    def get_foreign_exchange_rate(self, move):
        move.ensure_one()
        if self._has_field(move, "justech_do_foreign_exchange_rate") and move.justech_do_foreign_exchange_rate:
            return move.justech_do_foreign_exchange_rate
        if move.currency_id and move.currency_id != move.company_id.currency_id:
            return move.invoice_currency_rate or 0.0
        return 1.0

    def get_foreign_isr_retained(self, move):
        move.ensure_one()
        if self._has_field(move, "justech_do_foreign_isr_retained") and move.justech_do_foreign_isr_retained:
            return move.justech_do_foreign_isr_retained
        return 0.0

    def get_foreign_presumed_income(self, move):
        move.ensure_one()
        if self._has_field(move, "justech_do_foreign_presumed_income") and move.justech_do_foreign_presumed_income:
            return move.justech_do_foreign_presumed_income
        return 0.0

    def include_in_dgii(self, move):
        move.ensure_one()
        if self._has_field(move, "justech_do_include_in_dgii"):
            return bool(move.justech_do_include_in_dgii)
        return True

    def get_dgii_line_status(self, move):
        move.ensure_one()
        if self.is_voided(move):
            return "2"
        if self._has_field(move, "justech_do_dgii_line_status"):
            return move.justech_do_dgii_line_status or "1"
        return "1"

    def get_dgii_exclusion_reason(self, move):
        move.ensure_one()
        if self._has_field(move, "justech_do_dgii_exclusion_reason"):
            return self._clean_text(move.justech_do_dgii_exclusion_reason)
        return ""

    def get_payment_reference(self, move):
        """Referencia de pago / cheque (623 y similares)."""
        move.ensure_one()
        for name in (
            "justech_do_gov_retention_ref",
            "payment_reference",
            "ref",
        ):
            if self._has_field(move, name):
                text = self._clean_text(move[name])
                if text:
                    return text
        return ""

    def get_supported_sources(self, move):
        """Diagnóstico: qué capa aportó el NCF (solo lectura)."""
        move.ensure_one()
        if self._has_field(move, "justech_do_ncf") and self._normalize_ncf(move.justech_do_ncf):
            return "justech"
        if self._has_field(move, "l10n_latam_document_number") and self._normalize_ncf(
            move.l10n_latam_document_number
        ):
            return "adel_latam"
        ncf_std = self._ncf_from_standard_fields(move)
        if ncf_std:
            return "odoo_standard"
        return "none"
