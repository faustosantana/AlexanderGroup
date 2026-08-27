"""Catálogo DGII de tipos de costos y gastos (formato 606, columna D).

El valor operativo vive en la factura de proveedor, no en el contacto.
Este catálogo solo administra códigos, nombres y activación.
"""
from odoo import api, fields, models


class JustechDoDgiiExpenseType(models.Model):
    _name = "justech.do.dgii.expense.type"
    _description = "Tipo de costos y gastos DGII (606)"
    _order = "code"
    _rec_name = "display_name"

    code = fields.Char(
        string="Código",
        required=True,
        size=2,
        index=True,
        help="Código DGII de dos dígitos (01–11).",
    )
    name = fields.Char(string="Nombre", required=True, translate=True)
    display_name = fields.Char(
        string="Nombre completo",
        compute="_compute_display_name",
        store=True,
    )
    active = fields.Boolean(default=True)
    help_text = fields.Text(
        string="Ayuda funcional",
        help="Explicación operativa para el usuario de Compras / CxP.",
    )
    applies_to_606 = fields.Boolean(
        string="Participa en 606",
        default=True,
        help="Si está activo, el código es válido para el formato 606.",
    )

    _sql_constraints = [
        (
            "justech_do_dgii_expense_type_code_uniq",
            "unique(code)",
            "Ya existe un tipo de costos y gastos con este código DGII.",
        ),
    ]

    @api.depends("code", "name")
    def _compute_display_name(self):
        for rec in self:
            code = (rec.code or "").strip()
            name = (rec.name or "").strip()
            rec.display_name = f"{code} — {name}" if code and name else (name or code or "")
