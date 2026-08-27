from odoo import api, fields, models, _
from odoo.exceptions import UserError


class JustechAdminConsole(models.Model):
    _name = "justech.admin.console"
    _description = "Consola Administración Justech"

    name = fields.Char(default="Administración Justech", required=True)
    filter_company_id = fields.Many2one(
        "res.company",
        string="Empresa administrada",
        default=lambda self: self.env.company,
        required=True,
    )
    session_ok = fields.Boolean(compute="_compute_session_ok")
    status_visual = fields.Selection(
        selection=[
            ("green", "Correcto"),
            ("yellow", "Atención"),
            ("red", "Error"),
            ("grey", "No configurado"),
        ],
        compute="_compute_dashboard",
        string="Estado",
    )
    status_label = fields.Char(compute="_compute_dashboard", string="Estado general")
    status_reason = fields.Char(compute="_compute_dashboard", string="Motivo")
    pending_count = fields.Integer(compute="_compute_dashboard", string="Acciones requeridas")
    product_count = fields.Integer(compute="_compute_dashboard")
    active_product_count = fields.Integer(compute="_compute_dashboard")
    last_sync_at = fields.Datetime(readonly=True, string="Última sincronización")
    product_ids = fields.Many2many("justech.admin.product", compute="_compute_dashboard")
    pending_ids = fields.Many2many(
        "justech.admin.health.finding",
        compute="_compute_dashboard",
        string="Acciones requeridas",
    )
    activity_ids = fields.Many2many(
        "justech.admin.audit.log",
        compute="_compute_dashboard",
        string="Actividad reciente",
    )
    search_text = fields.Char(string="Buscar producto")

    def _compute_session_ok(self):
        Auth = self.env["justech.admin.center.auth.service"]
        for rec in self:
            try:
                rec.session_ok = Auth.is_session_valid()
            except Exception:
                rec.session_ok = False

    def _pending_domain(self, company):
        domain = [
            ("state", "in", ["open", "in_progress"]),
            ("severity", "in", ["warning", "error", "critical"]),
        ]
        if company:
            domain = [
                "|",
                ("company_id", "=", False),
                ("company_id", "=", company.id),
            ] + domain
        return domain

    def _compute_dashboard(self):
        Product = self.env["justech.admin.product"]
        Finding = self.env["justech.admin.health.finding"]
        Audit = self.env["justech.admin.audit.log"]
        Line = self.env["justech.admin.module.company"]
        for rec in self:
            company = rec.filter_company_id or self.env.company
            products = Product.search([("active", "=", True)], order="sequence, id")
            if rec.search_text:
                text = rec.search_text.strip().lower()
                products = products.filtered(
                    lambda p: text in (p.name or "").lower()
                    or text in (p.short_description or "").lower()
                )
            rec.product_ids = products
            rec.product_count = len(products)

            active_lines = Line.search(
                [
                    ("company_id", "=", company.id),
                    ("functional_state", "=", "active"),
                    ("module_id.activation_scope", "=", "company"),
                ]
            )
            rec.active_product_count = len(active_lines.mapped("product_id"))

            pending = Finding.search(
                rec._pending_domain(company),
                order="severity_rank desc, id desc",
                limit=20,
            )
            rec.pending_ids = pending
            rec.pending_count = Finding.search_count(rec._pending_domain(company))

            errors = pending.filtered(lambda f: f.severity in ("error", "critical"))
            warnings = pending.filtered(lambda f: f.severity == "warning")
            if errors:
                rec.status_visual = "red"
                rec.status_label = _("Error")
                rec.status_reason = errors[0].name
            elif warnings:
                rec.status_visual = "yellow"
                rec.status_label = _("Atención")
                rec.status_reason = warnings[0].name
            else:
                rec.status_visual = "green"
                rec.status_label = _("Correcto")
                rec.status_reason = _("Sin acciones requeridas para esta empresa")

            audits = Audit.search(
                [("company_ids", "in", company.id)],
                order="id desc",
                limit=5,
            )
            if not audits:
                audits = Audit.search([], order="id desc", limit=5)
            rec.activity_ids = audits

    @api.model
    def _ensure_singleton(self):
        console = self.search([], limit=1)
        if not console:
            console = self.create({"name": "Administración Justech"})
        return console

    def _align_odoo_company(self, company):
        """Una sola fuente de contexto: la empresa administrada = sesión Odoo."""
        self.ensure_one()
        company = company or self.env.company
        user = self.env.user
        if company not in user.company_ids:
            raise UserError(
                _("No tiene acceso a la empresa %(company)s.")
                % {"company": company.display_name}
            )
        if user.company_id != company:
            user.with_context(allowed_company_ids=user.company_ids.ids).sudo().write(
                {"company_id": company.id}
            )
        return company

    def _console_action(self, company):
        self.ensure_one()
        company = self._align_odoo_company(company)
        self.write({"filter_company_id": company.id})
        # Odoo 19 usa cookie `cids` para la cabecera; ?cids= en URL no basta.
        return {
            "type": "ir.actions.act_url",
            "url": "/justech/admin/console/company/%s?console_id=%s"
            % (company.id, self.id),
            "target": "self",
        }

    @api.model
    def action_open_console(self):
        Auth = self.env["justech.admin.center.auth.service"]
        Auth.require_authorized_user()
        wizard = Auth.gate_or_wizard()
        if wizard:
            return wizard
        console = self._ensure_singleton()
        self.env["justech.admin.product"].dedupe_by_code()
        self.env["justech.admin.registry.service"].discover_and_sync()
        self.env["justech.admin.product"].refresh_blurbs()
        # Entrada: alinear filtro con la empresa de sesión (una sola fuente)
        console.filter_company_id = self.env.company.id
        console.write({"last_sync_at": fields.Datetime.now()})
        return console._console_action(console.filter_company_id)

    def action_apply_company(self):
        self.ensure_one()
        gate = self.env["justech.admin.center.auth.service"].gate_or_wizard()
        if gate:
            return gate
        if not self.filter_company_id:
            raise UserError(_("Seleccione la empresa a administrar."))
        self.write({"last_sync_at": fields.Datetime.now()})
        return self._console_action(self.filter_company_id)

    def action_open_pending_center(self):
        self.ensure_one()
        gate = self.env["justech.admin.center.auth.service"].gate_or_wizard()
        if gate:
            return gate
        company = self.filter_company_id
        return {
            "type": "ir.actions.act_window",
            "name": _("Centro de pendientes"),
            "res_model": "justech.admin.health.finding",
            "view_mode": "kanban,list,form",
            "domain": self._pending_domain(company),
            "context": {
                "search_default_open": 1,
                "default_company_id": company.id,
                "justech_admin_company_id": company.id,
                "clear_breadcrumbs": True,
            },
            "target": "current",
        }

    def action_open_system_status(self):
        self.ensure_one()
        return self.env["justech.admin.system.status"].action_open(
            company=self.filter_company_id or self.env.company
        )

    def action_open_company_hub(self):
        self.ensure_one()
        return self.env["justech.admin.company.hub"].action_open(
            self.filter_company_id or self.env.company
        )

    def action_run_diagnostics(self):
        gate = self.env["justech.admin.center.auth.service"].gate_or_wizard()
        if gate:
            return gate
        self.env["justech.admin.health.service"].run_global_diagnostics()
        return self.action_open_pending_center()

    def action_sync_catalog(self):
        gate = self.env["justech.admin.center.auth.service"].gate_or_wizard()
        if gate:
            return gate
        self.env["justech.admin.registry.service"].discover_and_sync()
        self.env["justech.admin.product"].refresh_blurbs()
        self.write({"last_sync_at": fields.Datetime.now()})
        return self.action_apply_company()

    def action_open_users(self):
        gate = self.env["justech.admin.center.auth.service"].gate_or_wizard()
        if gate:
            return gate
        company = self.filter_company_id
        domain = [("share", "=", False), ("justech_is_test_user", "=", False)]
        if company:
            domain.append(("company_ids", "in", company.id))
        return {
            "type": "ir.actions.act_window",
            "name": _("Usuarios y roles"),
            "res_model": "res.users",
            "view_mode": "list,form",
            "domain": domain,
            "target": "current",
            "context": {"clear_breadcrumbs": True},
        }

    def action_open_audit(self):
        gate = self.env["justech.admin.center.auth.service"].gate_or_wizard()
        if gate:
            return gate
        company = self.filter_company_id
        domain = [("company_ids", "in", company.id)] if company else []
        return {
            "type": "ir.actions.act_window",
            "name": _("Auditoría"),
            "res_model": "justech.admin.audit.log",
            "view_mode": "list,form",
            "domain": domain,
            "target": "current",
            "context": {"clear_breadcrumbs": True},
        }

    def action_open_uat_technical(self):
        """Solo Administrador del Sistema — no es experiencia de producto."""
        gate = self.env["justech.admin.center.auth.service"].gate_or_wizard()
        if gate:
            return gate
        return {
            "type": "ir.actions.act_window",
            "name": _("Revisar cuentas de prueba"),
            "res_model": "res.users",
            "view_mode": "list,form",
            "domain": [("share", "=", False), ("justech_is_test_user", "=", True)],
            "target": "current",
            "context": {"clear_breadcrumbs": True},
        }

    def action_open_products(self):
        return self.action_apply_company()

    def action_open_modules(self):
        gate = self.env["justech.admin.center.auth.service"].gate_or_wizard()
        if gate:
            return gate
        return {
            "type": "ir.actions.act_window",
            "name": _("Capacidades"),
            "res_model": "justech.admin.module",
            "view_mode": "kanban,list,form",
            "domain": [("show_in_product_nav", "=", True)],
            "target": "current",
            "context": {
                "clear_breadcrumbs": True,
                "justech_admin_company_id": self.filter_company_id.id,
            },
        }

    def action_open_company_matrix(self):
        gate = self.env["justech.admin.center.auth.service"].gate_or_wizard()
        if gate:
            return gate
        company = self.filter_company_id
        return {
            "type": "ir.actions.act_window",
            "name": _("Estados por empresa"),
            "res_model": "justech.admin.module.company",
            "view_mode": "list,form",
            "domain": [("company_id", "=", company.id)] if company else [],
            "target": "current",
            "context": {"clear_breadcrumbs": True},
        }

    def action_open_permission_matrix(self):
        gate = self.env["justech.admin.center.auth.service"].gate_or_wizard()
        if gate:
            return gate
        html = self.env["justech.admin.permission.matrix.service"].render_html()
        wizard = self.env["justech.admin.role.assign.wizard"].create(
            {"mode": "matrix", "preview_html": html}
        )
        return {
            "type": "ir.actions.act_window",
            "name": _("Matriz de permisos"),
            "res_model": "justech.admin.role.assign.wizard",
            "res_id": wizard.id,
            "view_mode": "form",
            "target": "new",
        }

    def action_reauth(self):
        return self.env["justech.admin.auth.wizard"].action_open()

    # Compat aliases used by older views/actions
    def action_open_warnings(self):
        return self.action_open_pending_center()

    def action_open_errors(self):
        return self.action_open_pending_center()

    def action_open_health(self):
        return self.action_open_system_status()

    def action_open_companies(self):
        gate = self.env["justech.admin.center.auth.service"].gate_or_wizard()
        if gate:
            return gate
        return {
            "type": "ir.actions.act_window",
            "name": _("Empresas"),
            "res_model": "res.company",
            "view_mode": "list,form",
            "target": "current",
            "context": {"clear_breadcrumbs": True},
        }
