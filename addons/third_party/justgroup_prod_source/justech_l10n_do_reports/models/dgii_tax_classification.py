# -*- coding: utf-8 -*-
"""Catálogo parametrizable de clasificación fiscal DGII por impuesto."""
from __future__ import annotations

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

ROLE_COLUMN_DEFAULTS = {
    "itbis": {"606": "N", "607": "J"},
    "isc": {"606": "W", "607": "O"},
    "other_tax": {"606": "X", "607": "P"},
    "legal_tip": {"606": "Y", "607": "Q"},
    "exempt": {},
    "ignore": {},
}


class JustechDoDgiiTaxClassification(models.Model):
    _name = "justech.do.dgii.tax.classification"
    _description = "Clasificación fiscal DGII por impuesto"
    _order = "tax_id, id"

    name = fields.Char(compute="_compute_name", store=True)
    active = fields.Boolean(default=True)
    tax_id = fields.Many2one(
        "account.tax",
        string="Impuesto",
        required=True,
        ondelete="cascade",
        index=True,
    )
    company_id = fields.Many2one(
        "res.company",
        string="Compañía",
        related="tax_id.company_id",
        store=True,
        readonly=True,
    )
    classification_role = fields.Selection(
        selection=[
            ("itbis", "ITBIS"),
            ("isc", "ISC"),
            ("other_tax", "Otros impuestos/tasas"),
            ("legal_tip", "Propina legal"),
            ("exempt", "Exento / sin columna"),
            ("ignore", "Ignorar en validación"),
        ],
        string="Rol fiscal",
        required=True,
        default="other_tax",
    )
    column_606 = fields.Char(string="Columna 606", size=3)
    column_607 = fields.Char(string="Columna 607", size=3)
    column_609 = fields.Char(string="Columna 609", size=3)
    notes = fields.Text(string="Notas")

    _sql_constraints = [
        (
            "tax_unique",
            "unique(tax_id)",
            "Ya existe una clasificación DGII para este impuesto.",
        ),
    ]

    @api.depends("tax_id", "classification_role")
    def _compute_name(self):
        for rec in self:
            tax_name = rec.tax_id.display_name if rec.tax_id else ""
            role = dict(rec._fields["classification_role"].selection).get(
                rec.classification_role, ""
            )
            rec.name = f"{tax_name} → {role}" if tax_name else role

    @api.onchange("classification_role")
    def _onchange_classification_role(self):
        defaults = ROLE_COLUMN_DEFAULTS.get(self.classification_role, {})
        if defaults.get("606"):
            self.column_606 = defaults["606"]
        if defaults.get("607"):
            self.column_607 = defaults["607"]

    @api.constrains("column_606", "column_607", "classification_role")
    def _check_columns(self):
        for rec in self:
            if rec.classification_role in ("exempt", "ignore"):
                continue
            if rec.tax_id.type_tax_use in ("purchase", "none") and not rec.column_606:
                if rec.tax_id.type_tax_use == "purchase":
                    raise ValidationError(
                        _("El impuesto %(tax)s requiere columna 606.")
                        % {"tax": rec.tax_id.display_name}
                    )
            if rec.tax_id.type_tax_use in ("sale", "none") and not rec.column_607:
                if rec.tax_id.type_tax_use == "sale":
                    raise ValidationError(
                        _("El impuesto %(tax)s requiere columna 607.")
                        % {"tax": rec.tax_id.display_name}
                    )

    def get_column_for_report(self, report_code):
        self.ensure_one()
        field_name = f"column_{report_code}"
        if report_code not in ("606", "607", "609"):
            return False
        if hasattr(self, field_name):
            return getattr(self, field_name) or False
        return ROLE_COLUMN_DEFAULTS.get(self.classification_role, {}).get(report_code)

    @api.model
    def _tax_display_name(self, tax):
        name = tax.name
        if isinstance(name, dict):
            return name.get("en_US") or next(iter(name.values()), "")
        return name or ""

    @api.model
    def _infer_role_from_tax(self, tax):
        """Inferencia inicial al sincronizar — no se usa en exportación."""
        name = self._tax_display_name(tax).upper()
        group = ""
        if tax.tax_group_id:
            group = tax.tax_group_id.name
            if isinstance(group, dict):
                group = group.get("en_US") or ""
        group_u = (group or "").upper()

        if tax.amount < 0:
            return "ignore"
        if "ITBIS" in group_u or "ITBIS" in name:
            return "itbis"
        if "ISC" in group_u or "ISC" in name:
            return "isc"
        if "PROPINA" in name or "TIP" in name:
            return "legal_tip"
        if tax.amount == 0:
            return "exempt"
        if "CDT" in name or "TELCO" in name or "OTHER TAX" in group_u:
            return "other_tax"
        if tax.amount in (18.0, 16.0, 9.0, 8.0) and tax.type_tax_use in (
            "purchase",
            "sale",
        ):
            return "itbis"
        return "other_tax"

    @api.model
    def sync_from_taxes(self, company=None):
        """Crea clasificaciones faltantes sin modificar las existentes."""
        Tax = self.env["account.tax"].with_context(active_test=False)
        domain = []
        if company:
            domain.append(("company_id", "=", company.id))
        taxes = Tax.search(domain)
        created = self.browse()
        for tax in taxes:
            if self.search([("tax_id", "=", tax.id)], limit=1):
                continue
            role = self._infer_role_from_tax(tax)
            defaults = ROLE_COLUMN_DEFAULTS.get(role, {})
            created |= self.create(
                {
                    "tax_id": tax.id,
                    "classification_role": role,
                    "column_606": defaults.get("606"),
                    "column_607": defaults.get("607"),
                }
            )
        if created:
            self.env.flush_all()
        return created
