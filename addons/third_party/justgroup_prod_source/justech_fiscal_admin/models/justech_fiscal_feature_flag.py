# -*- coding: utf-8 -*-
"""Feature flags funcionales del stack fiscal Justech (sin instalar módulos)."""
from odoo import _, api, fields, models


class JustechFiscalFeatureFlag(models.Model):
    _name = "justech.fiscal.feature.flag"
    _description = "Justech Fiscal Feature Flag"
    _order = "sequence, code"

    name = fields.Char(required=True, translate=True)
    code = fields.Char(required=True, index=True)
    sequence = fields.Integer(default=10)
    description = fields.Text(translate=True)
    category = fields.Selection(
        [
            ("motor", "Motor NCF"),
            ("provider", "Fiscal Data Provider"),
            ("reports", "Reportes DGII"),
            ("dashboard", "Dashboard"),
            ("payments", "Pagos"),
            ("integrity", "Integridad"),
            ("general", "General"),
        ],
        default="general",
        required=True,
    )
    company_id = fields.Many2one(
        "res.company",
        string="Empresa",
        help="Vacío = valor por defecto global.",
        ondelete="cascade",
    )
    enabled = fields.Boolean(default=True)
    readonly_flag = fields.Boolean(
        string="Solo lectura",
        default=False,
        help="Flags de sistema que no pueden desactivarse desde la UI.",
    )
    active = fields.Boolean(default=True)

    _sql_constraints = [
        (
            "code_company_uniq",
            "unique(code, company_id)",
            "El código de feature flag debe ser único por empresa.",
        ),
    ]

    @api.model
    def is_enabled(self, code, company=None):
        """Lectura segura de configuración global (sudo). No crea registros."""
        company = company or self.env.company
        Flag = self.sudo()
        rec = Flag.search(
            [("code", "=", code), ("company_id", "=", company.id), ("active", "=", True)],
            limit=1,
        )
        if rec:
            return rec.enabled
        rec = Flag.search(
            [("code", "=", code), ("company_id", "=", False), ("active", "=", True)],
            limit=1,
        )
        return rec.enabled if rec else True

    def write(self, vals):
        if "enabled" in vals:
            for rec in self:
                if rec.readonly_flag and not vals["enabled"]:
                    from odoo.exceptions import UserError

                    raise UserError(
                        _("El flag %(name)s es de sistema y no puede desactivarse.", name=rec.name)
                    )
        return super().write(vals)
