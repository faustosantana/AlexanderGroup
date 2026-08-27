# -*- coding: utf-8 -*-
"""Servicio central de clasificación fiscal DGII — sin lógica por nombre."""
from __future__ import annotations

from collections import defaultdict

from odoo import models
from odoo.tools import float_round


class JustechDoDgiiTaxClassifier(models.AbstractModel):
    _name = "justech.do.dgii.tax.classifier"
    _description = "Clasificador fiscal DGII"

    REPORT_TAX_USE = {
        "606": "purchase",
        "607": "sale",
    }
    REPORT_TAX_COLUMNS = {
        "606": frozenset({"N", "W", "X", "Y"}),
        "607": frozenset({"J", "O", "P", "Q"}),
    }

    def _format_amount(self, amount, digits=2):
        return float_round(abs(amount or 0.0), precision_digits=digits)

    def get_classification(self, tax, company=None):
        if not tax:
            return self.env["justech.do.dgii.tax.classification"].browse()
        Classification = self.env["justech.do.dgii.tax.classification"]
        return Classification.search([("tax_id", "=", tax.id), ("active", "=", True)], limit=1)

    def get_column(self, tax, report_code, company=None):
        classification = self.get_classification(tax, company)
        if not classification:
            return False
        return classification.get_column_for_report(report_code)

    def is_itbis(self, tax, report_code=None, company=None):
        classification = self.get_classification(tax, company)
        return bool(classification and classification.classification_role == "itbis")

    def is_classified(self, tax, report_code, company=None):
        classification = self.get_classification(tax, company)
        if not classification:
            return False
        if classification.classification_role in ("exempt", "ignore"):
            return True
        return bool(classification.get_column_for_report(report_code))

    def _positive_tax_lines(self, move):
        return move.line_ids.filtered(lambda line: line.tax_line_id and line.tax_line_id.amount > 0)

    def unknown_taxes(self, move, report_code):
        """Impuestos positivos del movimiento sin clasificación válida para el reporte."""
        expected_use = self.REPORT_TAX_USE.get(report_code)
        unknown = self.env["account.tax"]
        for line in self._positive_tax_lines(move):
            tax = line.tax_line_id
            if expected_use and tax.type_tax_use != expected_use:
                continue
            if not self.is_classified(tax, report_code, move.company_id):
                unknown |= tax
        return unknown

    def move_column_amounts(self, move, report_code):
        """Montos por columna DGII para impuestos positivos del movimiento."""
        amounts = defaultdict(float)
        for line in self._positive_tax_lines(move):
            tax = line.tax_line_id
            column = self.get_column(tax, report_code, move.company_id)
            if column:
                amounts[column] += self._format_amount(line.balance)
        return dict(amounts)

    def move_itbis_amount(self, move, report_code):
        total = 0.0
        for line in self._positive_tax_lines(move):
            if self.is_itbis(line.tax_line_id, report_code, move.company_id):
                total += self._format_amount(line.balance)
        return total

    def apply_tax_columns(self, row_values, move, report_code, sign=1):
        """Fusiona montos clasificados en columnas fiscales sin tocar otras columnas."""
        allowed = self.REPORT_TAX_COLUMNS.get(report_code, frozenset())
        amounts = self.move_column_amounts(move, report_code)
        for column, amount in amounts.items():
            if column in allowed and column in row_values:
                row_values[column] = amount * sign
        return row_values
