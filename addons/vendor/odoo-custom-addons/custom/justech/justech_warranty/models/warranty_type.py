# -*- coding: utf-8 -*-
from odoo import fields, models


class JustechWarrantyType(models.Model):
    _name = "justech.warranty.type"
    _description = "Tipo de garantía"
    _order = "sequence, name"

    name = fields.Char(string="Nombre", required=True, translate=True)
    code = fields.Char(string="Código")
    kind = fields.Selection(
        [
            ("store", "Tienda"),
            ("manufacturer", "Fabricante"),
            ("extended", "Extendida"),
        ],
        string="Clase",
        default="store",
        required=True,
        help="Clase base de la garantía, usada por la lógica del módulo.",
    )
    default_months = fields.Integer(
        string="Meses por defecto",
        default=0,
        help="Si es mayor que 0, se propone como duración al elegir este tipo.",
    )
    active = fields.Boolean(string="Activo", default=True)
    sequence = fields.Integer(string="Secuencia", default=10)
    note = fields.Text(string="Descripción")
    company_id = fields.Many2one(
        "res.company",
        string="Compañía",
        default=lambda self: self.env.company,
        help="Déjelo vacío para que el tipo esté disponible en todas las compañías.",
    )

    _sql_constraints = [
        ("code_uniq", "unique(code, company_id)", "El código del tipo debe ser único por compañía."),
    ]
