from odoo import fields, models


class JustechAdminAccessAudit(models.Model):
    _name = "justech.admin.access.audit"
    _description = "Justech Admin Key Audit"
    _order = "create_date desc"

    user_id = fields.Many2one("res.users", required=True, ondelete="restrict")
    company_id = fields.Many2one("res.company", ondelete="set null")
    action = fields.Char(required=True)
    scope = fields.Char()
    success = fields.Boolean(default=False)
    ip_address = fields.Char()
    details = fields.Json(default=dict)
