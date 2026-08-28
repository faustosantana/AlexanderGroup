# -*- coding: utf-8 -*-
from odoo import fields, models


class JustechWarrantyClaimReason(models.Model):
    _name = "justech.warranty.claim.reason"
    _description = "Motivo de reclamo (RMA)"
    _order = "sequence, name"

    name = fields.Char(string="Motivo", required=True, translate=True)
    active = fields.Boolean(string="Activo", default=True)
    sequence = fields.Integer(string="Secuencia", default=10)
    note = fields.Text(string="Descripción")
    company_id = fields.Many2one(
        "res.company",
        string="Compañía",
        default=lambda self: self.env.company,
        help="Déjelo vacío para que el motivo esté disponible en todas las compañías.",
    )
