# -*- coding: utf-8 -*-
from odoo import fields, models


class JustechDoNcfMigrationLog(models.Model):
    _name = "justech.do.ncf.migration.log"
    _description = "NCF Migration / Reconcile Audit Log"
    _order = "create_date desc, id desc"

    company_id = fields.Many2one("res.company", required=True, index=True)
    prefix = fields.Char(required=True, index=True)
    legacy_sequence_id = fields.Many2one("account.fiscal.sequence", ondelete="set null")
    range_id = fields.Many2one("justech.do.ncf.range", ondelete="set null")
    last_published_ncf = fields.Char()
    safe_next = fields.Integer()
    source = fields.Selection(
        selection=[
            ("legacy_migration", "Migración legacy → Justech"),
            ("post_sync_reconcile", "Reconciliación post-sync"),
        ],
        required=True,
        index=True,
    )
    evidence_hash = fields.Char(index=True)
    payload_json = fields.Text()
    user_id = fields.Many2one("res.users", required=True, default=lambda self: self.env.user)
