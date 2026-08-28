from odoo import api, fields, models

from .catalog import ROLE_LABEL, ROLE_LOCAL


class DxMsFunctionalInbox(models.Model):
    _name = "dx.ms.functional.inbox"
    _description = "Buzón funcional Doralex"
    _inherit = ["mail.thread"]
    _order = "company_id, role"

    name = fields.Char(required=True, tracking=True)
    company_id = fields.Many2one(
        "res.company",
        required=True,
        index=True,
        default=lambda self: self.env.company,
    )
    role = fields.Selection(
        [
            ("admin", "Administración"),
            ("purchase", "Compras"),
            ("invoice", "Facturación"),
            ("accounting", "Contabilidad"),
            ("info", "Contacto"),
        ],
        required=True,
        index=True,
    )
    alias_id = fields.Many2one("mail.alias", string="Alias Odoo", ondelete="restrict")
    alias_name = fields.Char()

    _sql_constraints = [
        (
            "company_role_unique",
            "unique(company_id, role)",
            "Ya existe un buzón funcional con ese rol para la empresa.",
        )
    ]

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._dx_sync_alias()
        return records

    def write(self, vals):
        res = super().write(vals)
        if {"alias_name", "company_id", "role"} & set(vals):
            self._dx_sync_alias()
        return res

    def _dx_sync_alias(self):
        Alias = self.env["mail.alias"].sudo()
        model = self.env["ir.model"]._get("dx.ms.functional.inbox")
        for inbox in self:
            local = inbox.alias_name or ROLE_LOCAL.get(inbox.role)
            domain = inbox.company_id.alias_domain_id
            if not local or not domain or not model:
                continue
            existing = Alias.search(
                [
                    ("alias_name", "=", local),
                    ("alias_domain_id", "=", domain.id),
                ],
                limit=1,
            )
            values = {
                "alias_name": local,
                "alias_domain_id": domain.id,
                "alias_model_id": model.id,
                "alias_force_thread_id": inbox.id,
                "alias_defaults": "{}",
                "alias_contact": "everyone",
            }
            if existing:
                existing.write(values)
                alias = existing
            else:
                alias = Alias.create(values)
            updates = {}
            if inbox.alias_id != alias:
                updates["alias_id"] = alias.id
            if inbox.alias_name != local:
                updates["alias_name"] = local
            if not inbox.name:
                updates["name"] = "%s · %s" % (
                    ROLE_LABEL.get(inbox.role, inbox.role),
                    inbox.company_id.dx_trade_name or inbox.company_id.name,
                )
            if updates:
                super(DxMsFunctionalInbox, inbox).write(updates)
