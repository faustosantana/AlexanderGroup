from odoo import fields, models


class JustechAdminModuleCompany(models.Model):
    _name = "justech.admin.module.company"
    _description = "Estado funcional Justech por empresa"
    _order = "company_id, module_id"

    module_id = fields.Many2one("justech.admin.module", required=True, ondelete="cascade", index=True)
    company_id = fields.Many2one("res.company", required=True, ondelete="cascade", index=True)
    functional_state = fields.Selection(
        selection=[
            ("unconfigured", "No configurado"),
            ("inactive", "Inactivo"),
            ("active", "Activo"),
            ("blocked", "Bloqueado"),
            ("attention", "Requiere atención"),
            ("error", "Error"),
        ],
        default="unconfigured",
        required=True,
    )
    fiscal_engine = fields.Selection(
        selection=[
            ("none", "Sin motor"),
            ("traditional_ncf", "NCF tradicional"),
            ("electronic", "Facturación electrónica"),
        ],
        default="none",
        string="Motor fiscal",
    )
    last_change_at = fields.Datetime(readonly=True)
    last_change_uid = fields.Many2one("res.users", readonly=True)
    notes = fields.Text()
    product_id = fields.Many2one(related="module_id.product_id", store=True)
    is_global = fields.Boolean(related="module_id.is_global")
    activation_scope = fields.Selection(related="module_id.activation_scope")

    _sql_constraints = [
        (
            "module_company_uniq",
            "unique(module_id, company_id)",
            "Ya existe configuración de este módulo para la empresa.",
        ),
    ]

    def action_prepare_activate(self):
        self.ensure_one()
        gate = self.env["justech.admin.center.auth.service"].gate_or_wizard()
        if gate:
            return gate
        return self.env["justech.admin.company.activation.wizard"].action_open(self, "activate")

    def action_prepare_deactivate(self):
        self.ensure_one()
        gate = self.env["justech.admin.center.auth.service"].gate_or_wizard()
        if gate:
            return gate
        return self.env["justech.admin.company.activation.wizard"].action_open(self, "deactivate")

    def action_prepare_engine_change(self):
        self.ensure_one()
        gate = self.env["justech.admin.center.auth.service"].gate_or_wizard()
        if gate:
            return gate
        return self.env["justech.admin.company.activation.wizard"].action_open(self, "engine")
