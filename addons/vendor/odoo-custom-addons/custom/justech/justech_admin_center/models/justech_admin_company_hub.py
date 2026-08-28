from odoo import api, fields, models, _


class JustechAdminCompanyHub(models.TransientModel):
    _name = "justech.admin.company.hub"
    _description = "Administración por empresa Justech"

    name = fields.Char(readonly=True)
    company_id = fields.Many2one("res.company", required=True, readonly=True)
    status_label = fields.Char(readonly=True)
    status_visual = fields.Selection(
        selection=[
            ("green", "Correcto"),
            ("yellow", "Atención"),
            ("red", "Error"),
            ("grey", "Sin datos"),
        ],
        readonly=True,
    )
    status_reason = fields.Char(readonly=True)
    pending_count = fields.Integer(readonly=True)
    user_count = fields.Integer(readonly=True)
    active_product_count = fields.Integer(readonly=True)
    pending_ids = fields.Many2many("justech.admin.health.finding", readonly=True)
    product_ids = fields.Many2many("justech.admin.product", readonly=True)
    activity_ids = fields.Many2many("justech.admin.audit.log", readonly=True)

    @api.model
    def action_open(self, company):
        gate = self.env["justech.admin.center.auth.service"].gate_or_wizard()
        if gate:
            return gate
        if not company:
            company = self.env.company
        hub = self.create({"company_id": company.id, "name": company.name})
        hub._load()
        return {
            "type": "ir.actions.act_window",
            "name": company.name,
            "res_model": self._name,
            "res_id": hub.id,
            "view_mode": "form",
            "target": "current",
            "context": {
                "form_view_initial_mode": "readonly",
                "clear_breadcrumbs": True,
                "justech_admin_company_id": company.id,
            },
        }

    def _load(self):
        self.ensure_one()
        company = self.company_id
        Finding = self.env["justech.admin.health.finding"].sudo()
        Line = self.env["justech.admin.module.company"].sudo()
        Product = self.env["justech.admin.product"].sudo()
        Audit = self.env["justech.admin.audit.log"].sudo()
        pending = Finding.search(
            [
                ("state", "in", ["open", "in_progress"]),
                ("severity", "in", ["warning", "error", "critical"]),
                "|",
                ("company_id", "=", company.id),
                ("company_id", "=", False),
            ],
            order="severity_rank desc",
            limit=20,
        )
        self.pending_ids = pending
        self.pending_count = len(pending)
        if pending.filtered(lambda f: f.severity in ("error", "critical")):
            self.status_visual = "red"
            self.status_label = _("Error")
            self.status_reason = pending[0].name
        elif pending:
            self.status_visual = "yellow"
            self.status_label = _("Atención")
            self.status_reason = pending[0].name
        else:
            self.status_visual = "green"
            self.status_label = _("Correcto")
            self.status_reason = _("Sin acciones requeridas")
        active_lines = Line.search(
            [
                ("company_id", "=", company.id),
                ("functional_state", "=", "active"),
                ("module_id.activation_scope", "=", "company"),
            ]
        )
        self.product_ids = Product.search([("active", "=", True)], order="sequence")
        self.active_product_count = len(active_lines.mapped("product_id"))
        self.user_count = self.env["res.users"].sudo().search_count(
            [
                ("share", "=", False),
                ("active", "=", True),
                ("company_ids", "in", company.id),
                ("justech_is_test_user", "=", False),
            ]
        )
        self.activity_ids = Audit.search(
            [("company_ids", "in", company.id)], order="id desc", limit=5
        )

    def action_open_pending(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Pendientes — %s") % self.company_id.name,
            "res_model": "justech.admin.health.finding",
            "view_mode": "kanban,list,form",
            "domain": [
                ("state", "in", ["open", "in_progress"]),
                ("severity", "in", ["warning", "error", "critical"]),
                "|",
                ("company_id", "=", self.company_id.id),
                ("company_id", "=", False),
            ],
            "target": "current",
            "context": {
                "clear_breadcrumbs": True,
                "justech_admin_company_id": self.company_id.id,
            },
        }

    def action_run_diagnostics(self):
        self.env["justech.admin.health.service"].run_global_diagnostics()
        return self.action_open_pending()

    def action_open_users(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Usuarios — %s") % self.company_id.name,
            "res_model": "res.users",
            "view_mode": "list,form",
            "domain": [
                ("share", "=", False),
                ("company_ids", "in", self.company_id.id),
                ("justech_is_test_user", "=", False),
            ],
            "target": "current",
            "context": {"clear_breadcrumbs": True},
        }

    def action_back_console(self):
        return self.env["justech.admin.console"].action_open_console()
