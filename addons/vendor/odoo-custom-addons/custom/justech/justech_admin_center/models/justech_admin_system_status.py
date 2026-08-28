from odoo import api, fields, models, _


class JustechAdminSystemStatus(models.TransientModel):
    _name = "justech.admin.system.status"
    _description = "Estado del sistema Justech"

    name = fields.Char(default="Estado del sistema", readonly=True)
    company_id = fields.Many2one("res.company", string="Empresa", readonly=True)
    health_score = fields.Integer(readonly=True, string="Puntuación")
    status_label = fields.Char(readonly=True, string="Estado general")
    status_visual = fields.Selection(
        selection=[
            ("green", "Correcto"),
            ("yellow", "Atención"),
            ("red", "Error"),
            ("grey", "Sin datos"),
        ],
        readonly=True,
    )
    error_count = fields.Integer(readonly=True, string="Errores")
    warning_count = fields.Integer(readonly=True, string="Advertencias")
    last_validation = fields.Datetime(readonly=True, string="Última validación")
    platform_status = fields.Char(readonly=True)
    security_status = fields.Char(readonly=True)
    fiscal_status = fields.Char(readonly=True)
    finance_status = fields.Char(readonly=True)
    warranty_status = fields.Char(readonly=True)
    integrations_status = fields.Char(readonly=True)
    automation_status = fields.Char(readonly=True)
    next_action = fields.Char(readonly=True)

    @api.model
    def action_open(self, company=None):
        gate = self.env["justech.admin.center.auth.service"].gate_or_wizard()
        if gate:
            return gate
        hub = self.create({"company_id": company.id if company else self.env.company.id})
        hub._load()
        return {
            "type": "ir.actions.act_window",
            "name": _("Estado del sistema"),
            "res_model": self._name,
            "res_id": hub.id,
            "view_mode": "form",
            "target": "current",
            "context": {"form_view_initial_mode": "readonly", "clear_breadcrumbs": True},
        }

    def _cat_status(self, domain_extra=None):
        Finding = self.env["justech.admin.health.finding"].sudo()
        domain = [
            ("state", "in", ["open", "in_progress"]),
            ("severity", "in", ["warning", "error", "critical"]),
        ]
        if self.company_id:
            domain = [
                "|",
                ("company_id", "=", False),
                ("company_id", "=", self.company_id.id),
            ] + domain
        if domain_extra:
            domain = domain + domain_extra
        findings = Finding.search(domain)
        if findings.filtered(lambda f: f.severity in ("error", "critical")):
            return _("Error")
        if findings:
            return _("Atención")
        return _("Correcto")

    def _load(self):
        self.ensure_one()
        Finding = self.env["justech.admin.health.finding"].sudo()
        domain = [
            ("state", "in", ["open", "in_progress"]),
            ("severity", "in", ["warning", "error", "critical"]),
        ]
        if self.company_id:
            domain = [
                "|",
                ("company_id", "=", False),
                ("company_id", "=", self.company_id.id),
            ] + domain
        pending = Finding.search(domain)
        self.error_count = len(pending.filtered(lambda f: f.severity in ("error", "critical")))
        self.warning_count = len(pending.filtered(lambda f: f.severity == "warning"))
        last = Finding.search([], order="detected_at desc, id desc", limit=1)
        self.last_validation = last.detected_at if last else False
        score = 100 - min(60, self.error_count * 15) - min(30, self.warning_count * 5)
        self.health_score = max(0, score)
        if self.error_count:
            self.status_visual = "red"
            self.status_label = _("Error")
            self.next_action = pending.filtered(lambda f: f.severity in ("error", "critical"))[:1].name
        elif self.warning_count:
            self.status_visual = "yellow"
            self.status_label = _("Atención")
            self.next_action = pending[:1].name
        else:
            self.status_visual = "green"
            self.status_label = _("Correcto")
            self.next_action = _("Sin acción requerida")

        Product = self.env["justech.admin.product"]
        fiscal = Product.search([("code", "=", "fiscal")], limit=1)
        finance = Product.search([("code", "=", "finance")], limit=1)
        warranty = Product.search([("code", "=", "warranty")], limit=1)
        self.platform_status = _("Correcto")
        self.security_status = self._cat_status([("code", "ilike", "JAC_%USER%")]) or _("Correcto")
        self.fiscal_status = fiscal.estado_general if fiscal else _("No aplica")
        self.finance_status = finance.estado_general if finance else _("No aplica")
        self.warranty_status = warranty.estado_general if warranty else _("No aplica")
        self.integrations_status = _("No aplica")
        self.automation_status = _("Correcto")

    def action_run_diagnostics(self):
        self.env["justech.admin.health.service"].run_global_diagnostics()
        return self.env["justech.admin.console"]._ensure_singleton().action_open_pending_center()

    def action_open_pending(self):
        return self.env["justech.admin.console"]._ensure_singleton().action_open_pending_center()

    def action_back_console(self):
        return self.env["justech.admin.console"].action_open_console()
