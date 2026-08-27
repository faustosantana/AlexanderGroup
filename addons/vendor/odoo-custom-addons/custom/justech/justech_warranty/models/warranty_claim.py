# -*- coding: utf-8 -*-
from odoo import _, api, fields, models


class JustechWarrantyClaim(models.Model):
    _name = "justech.warranty.claim"
    _description = "Reclamo de garantía (RMA)"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "claim_date desc, id desc"

    name = fields.Char(
        string="Referencia", required=True, copy=False, readonly=True,
        default=lambda self: _("Nuevo"),
    )
    warranty_id = fields.Many2one(
        "justech.warranty", string="Garantía", required=True,
        ondelete="cascade", index=True, tracking=True,
    )
    unit_ids = fields.Many2many(
        "justech.warranty.unit",
        "justech_warranty_claim_unit_rel",
        "claim_id",
        "unit_id",
        string="Unidades reclamadas",
        domain="[('warranty_id', '=', warranty_id)]",
        help="Unidades específicas cubiertas por este reclamo. Vacío = todo el "
        "header.",
    )
    unit_count = fields.Integer(
        string="Nº unidades", compute="_compute_unit_count",
    )
    partner_id = fields.Many2one(
        related="warranty_id.partner_id", string="Cliente", store=True, index=True,
    )
    product_id = fields.Many2one(
        related="warranty_id.product_id", string="Producto", store=True,
    )
    serial_manufacturer = fields.Char(
        string="Serial reclamado",
        compute="_compute_serial_manufacturer",
        store=False,
        help="Serial de fabricante de la primera unidad reclamada (informativo).",
    )
    company_id = fields.Many2one(
        related="warranty_id.company_id", string="Compañía", store=True, index=True,
    )
    reason_id = fields.Many2one(
        "justech.warranty.claim.reason", string="Motivo", tracking=True,
        domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]",
        ondelete="restrict",
    )
    claim_date = fields.Date(
        string="Fecha de reclamo", required=True, default=fields.Date.context_today, tracking=True,
    )
    description = fields.Text(string="Descripción del problema", required=True)
    resolution = fields.Text(string="Resolución")
    state = fields.Selection(
        [
            ("draft", "Borrador"),
            ("submitted", "Enviado"),
            ("in_progress", "En proceso"),
            ("resolved", "Resuelto"),
            ("rejected", "Rechazado"),
        ],
        string="Estado", default="draft", required=True, tracking=True, index=True,
    )

    @api.depends("unit_ids")
    def _compute_unit_count(self):
        for claim in self:
            claim.unit_count = len(claim.unit_ids)

    @api.depends("unit_ids", "unit_ids.serial_manufacturer")
    def _compute_serial_manufacturer(self):
        for claim in self:
            first = claim.unit_ids[:1]
            claim.serial_manufacturer = first.serial_manufacturer if first else False

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", _("Nuevo")) == _("Nuevo"):
                vals["name"] = self.env["ir.sequence"].next_by_code(
                    "justech.warranty.claim"
                ) or _("Nuevo")
        return super().create(vals_list)

    def action_submit(self):
        self.write({"state": "submitted"})
        return True

    def action_start(self):
        self.write({"state": "in_progress"})
        return True

    def action_resolve(self):
        self.write({"state": "resolved"})
        for claim in self:
            units = claim.unit_ids
            if units:
                # Reclamo parcial: sólo se marcan como "claimed" las unidades
                # indicadas. El header queda "claimed" únicamente si TODAS
                # sus unidades activas ya están reclamadas.
                units.filtered(lambda u: u.state in ("active", "pending_serial", "planned")).write(
                    {"state": "claimed"}
                )
                if all(
                    u.state == "claimed"
                    for u in claim.warranty_id.unit_ids
                    if u.state != "void"
                ):
                    if claim.warranty_id.state == "active":
                        claim.warranty_id.state = "claimed"
            else:
                if claim.warranty_id.state == "active":
                    claim.warranty_id.state = "claimed"
        return True

    def action_reject(self):
        self.write({"state": "rejected"})
        return True
