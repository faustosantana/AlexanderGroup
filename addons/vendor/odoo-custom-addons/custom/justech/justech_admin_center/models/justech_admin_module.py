from odoo import api, fields, models, _
from odoo.exceptions import UserError


# Acciones administrativas dedicadas por submódulo (nunca abrir pantallas ajenas)
ADMIN_ACTIONS = {
    "justech_l10n_do_base": {
        "admin": "justech_admin_center.action_justech_admin_padron_hub",
        "configure": "justech_l10n_do_base.action_justech_do_rnc_padron_config_server",
        "operation": "justech_l10n_do_base.action_justech_do_rnc_padron_import",
        "status": "justech_l10n_do_base.action_justech_do_rnc_padron",
    },
    "justech_l10n_do_ncf": {
        "admin": "justech_l10n_do_ncf.action_justech_do_ncf_range",
        "configure": "justech_l10n_do_ncf.action_justech_do_ncf_range",
        "operation": "justech_l10n_do_ncf.action_justech_do_ncf_consumption",
        "status": "justech_l10n_do_ncf.action_justech_do_fiscal_diagnostic",
    },
    "justech_l10n_do_reports": {
        "admin": "justech_l10n_do_reports.action_justech_do_fiscal_report",
        "configure": "justech_l10n_do_reports.action_justech_do_fiscal_report_wizard",
        "operation": "justech_l10n_do_reports.action_justech_do_report_606",
        "status": "justech_l10n_do_reports.action_justech_do_fiscal_review_pending",
    },
    "justech_l10n_do_adel_freeze": {
        "admin": "justech_fiscal_admin.action_justech_fiscal_admin_center_server",
        "configure": "justech_fiscal_admin.action_justech_fiscal_feature_flags",
        "operation": "justech_fiscal_admin.action_justech_fiscal_admin_center_server",
        "status": "justech_admin_center.action_justech_admin_health",
    },
    "justech_fiscal_admin": {
        # Hub propio de la consola — no la pantalla antigua mezclada
        "admin": "justech_admin_center.action_justech_admin_fiscal_hub",
        "configure": "justech_fiscal_admin.action_justech_fiscal_feature_flags",
        "operation": "justech_fiscal_admin.action_justech_fiscal_admin_center_server",
        "status": "justech_admin_center.action_justech_admin_fiscal_hub",
    },
    "justech_l10n_do_payments_withholding": {
        "admin": "justech_l10n_do_reports.action_justech_do_withholding_catalog",
        "configure": "justech_l10n_do_reports.action_justech_do_withholding_catalog",
        "operation": "justech_l10n_do_payments_withholding.action_justech_register_customer_payment",
        "status": "justech_l10n_do_reports.action_justech_do_report_623",
    },
    "justech_l10n_do_treasury": {
        "admin": "justech_admin_center.action_justech_admin_treasury_hub",
        "configure": "justech_l10n_do_treasury.action_justech_bank_reconciliation",
        "operation": "justech_l10n_do_treasury.action_treasury_open_payments_customer",
        "status": "justech_l10n_do_treasury.action_treasury_open_payments_vendor",
    },
    "justech_warranty": {
        "admin": "justech_warranty.action_justech_warranty_dashboard",
        "configure": "justech_warranty.action_justech_warranty_config_settings",
        "operation": "justech_warranty.action_justech_warranty",
        "status": "justech_warranty.action_justech_warranty_claim",
    },
    "justech_admin_center": {
        "admin": "justech_admin_center.action_justech_admin_console",
        "configure": "justech_admin_center.action_justech_admin_console",
        "operation": "justech_admin_center.action_justech_admin_health",
        "status": "justech_admin_center.action_justech_admin_health",
    },
    "justech_global_audit_log": {
        "admin": "justech_global_audit_log.action_justech_audit_dashboard",
        "configure": "justech_global_audit_log.action_justech_audit_rule",
        "operation": "justech_global_audit_log.action_justech_audit_log",
        "status": "justech_global_audit_log.action_justech_audit_dashboard",
    },
    "justech_ecf_admin": {
        "admin": "justech_ecf_admin.action_justech_ecf_admin_hub",
        "configure": "justech_ecf_core.action_justech_ecf_company_config",
        "operation": "justech_ecf_admin.action_justech_ecf_dashboard",
        "status": "justech_ecf_admin.action_justech_ecf_dashboard",
    },
    "justech_ecf_core": {
        "admin": "justech_ecf_admin.action_justech_ecf_admin_hub",
        "configure": "justech_ecf_core.action_justech_ecf_company_config",
        "operation": "justech_ecf_core.action_justech_ecf_document",
        "status": "justech_ecf_admin.action_justech_ecf_dashboard",
    },
}

GLOBAL_TECH = {
    "justech_admin_center",
    "justech_modules",
    "justech_core",
    "justech_l10n_do_base",
    "justech_global_audit_log",
}


NAV_HIDDEN_TECH = {
    "justech_ecf_core",
    "justech_modules",
    "justech_core",
}

FUNCTIONAL_DEPS = {
    "justech_ecf_admin": [
        ("justech_l10n_do_ncf", "1.2 Motor Fiscal NCF"),
        ("justech_l10n_do_base", "1.4 Padrón DGII"),
    ],
    "justech_l10n_do_reports": [
        ("justech_l10n_do_base", "1.4 Padrón DGII"),
    ],
}


class JustechAdminModule(models.Model):
    _name = "justech.admin.module"
    _description = "Catálogo de módulo Justech"
    _order = "hierarchy_sort, id"

    name = fields.Char(related="functional_name", store=True)
    technical_name = fields.Char(required=True, index=True)
    functional_name = fields.Char(required=True)
    short_description = fields.Text(required=False)
    long_description = fields.Html(
        string="Descripción funcional",
        help="Qué es, para qué sirve, procesos, criticidad, activar/desactivar.",
    )
    what_it_does = fields.Text(string="Para qué se utiliza")
    processes_affected = fields.Text(string="Procesos que afecta")
    users_who_use_it = fields.Text(string="Usuarios típicos")
    risk_activate = fields.Text(string="Riesgo al activar")
    risk_deactivate = fields.Text(string="Riesgo al desactivar")
    product_id = fields.Many2one("justech.admin.product", string="Producto", ondelete="set null", index=True)
    hierarchy_code = fields.Char(
        string="Nº",
        compute="_compute_hierarchy_code",
        help="Numeración Producto.Módulo (ej. 1.3). Guía de navegación, no código técnico.",
    )
    display_name_nav = fields.Char(compute="_compute_hierarchy_code", string="Nombre navegación")
    recommended_action_label = fields.Char(
        compute="_compute_action_labels",
        string="Acción recomendada",
    )
    recommended_action_help = fields.Char(compute="_compute_action_labels")
    activation_scope = fields.Selection(
        selection=[("global", "Global"), ("company", "Por empresa")],
        default="company",
        required=True,
        string="Alcance",
    )
    fiscal_engine_capable = fields.Boolean(default=False)
    company_line_ids = fields.One2many("justech.admin.module.company", "module_id", string="Empresas")
    category = fields.Selection(
        selection=[
            ("platform", "Plataforma"),
            ("fiscal", "Fiscal"),
            ("payments", "Pagos"),
            ("treasury", "Tesorería"),
            ("audit", "Auditoría"),
            ("reports", "Reportes"),
            ("ux", "Experiencia"),
            ("integrations", "Integraciones"),
            ("other", "Otros"),
        ],
        default="other",
        required=True,
        string="Categoría",
    )
    icon = fields.Char(default="fa-cube")
    sequence = fields.Integer(default=100)
    version = fields.Char()
    technical_state = fields.Selection(
        selection=[
            ("not_installed", "No instalado"),
            ("installed", "Instalado"),
            ("to_upgrade", "Por actualizar"),
            ("unavailable", "No disponible"),
        ],
        default="not_installed",
        required=True,
        string="Estado técnico",
    )
    functional_state = fields.Selection(
        selection=[
            ("inactive", "Inactivo"),
            ("active", "Activo"),
            ("attention", "Requiere atención"),
            ("error", "Error"),
            ("unconfigured", "No configurado"),
        ],
        default="inactive",
        required=True,
        string="Estado funcional",
    )
    status_visual = fields.Selection(
        selection=[
            ("green", "Correcto"),
            ("yellow", "Atención"),
            ("red", "Error"),
            ("blue", "Informativo"),
            ("grey", "No configurado"),
        ],
        compute="_compute_status_visual",
        store=True,
    )
    dependency_names = fields.Char(string="Dependencias")
    optional_dependency_names = fields.Char()
    open_action_xmlid = fields.Char()
    health_method = fields.Char()
    feature_flag_codes = fields.Char(help="Códigos separados por coma")
    supports_activate = fields.Boolean(default=True)
    supports_deactivate = fields.Boolean(default=True)
    is_critical = fields.Boolean(default=False)
    is_installable = fields.Boolean(default=True)
    last_sync_at = fields.Datetime()
    last_health_at = fields.Datetime()
    last_health_summary = fields.Char()
    has_operation_action = fields.Boolean(
        string="Tiene operación",
        compute="_compute_has_operation_action",
    )
    company_active_count = fields.Integer(compute="_compute_company_stats")
    company_ids_display = fields.Char(compute="_compute_company_stats")
    coverage_label = fields.Char(compute="_compute_company_stats", string="Cobertura")
    ir_module_id = fields.Many2one("ir.module.module", string="Módulo Odoo", ondelete="set null")
    operation_ids = fields.One2many("justech.admin.operation", "module_id")
    audit_ids = fields.One2many("justech.admin.audit.log", "module_id")
    finding_ids = fields.One2many("justech.admin.health.finding", "module_id")
    active_finding_count = fields.Integer(compute="_compute_finding_count")
    overview_html = fields.Html(compute="_compute_overview_html", sanitize=False)
    estado_general = fields.Char(compute="_compute_overview_html", string="Estado general")
    dependency_help = fields.Text(compute="_compute_overview_html", string="Dependencias")
    functions_help = fields.Html(compute="_compute_overview_html", sanitize=False, string="Funciones incluidas")
    is_global = fields.Boolean(compute="_compute_is_global")
    show_in_product_nav = fields.Boolean(
        compute="_compute_nav_flags",
        store=True,
        string="Visible en navegación",
    )
    hierarchy_sort = fields.Integer(compute="_compute_nav_flags", store=True)
    dependency_html = fields.Html(compute="_compute_dependency_html", sanitize=False)
    breadcrumb_label = fields.Char(compute="_compute_breadcrumb_label")

    _sql_constraints = [
        ("technical_name_uniq", "unique(technical_name)", "El módulo técnico ya está registrado."),
    ]

    @api.depends("activation_scope")
    def _compute_is_global(self):
        for rec in self:
            rec.is_global = rec.activation_scope == "global"

    @api.depends("technical_name", "hierarchy_code", "product_id")
    def _compute_nav_flags(self):
        for rec in self:
            rec.show_in_product_nav = (
                rec.technical_name not in NAV_HIDDEN_TECH and bool(rec.hierarchy_code)
            )
            try:
                parts = (rec.hierarchy_code or "99.99").split(".")
                major = int(parts[0]) if parts and parts[0] else 99
                minor = int(parts[1]) if len(parts) > 1 else 99
                rec.hierarchy_sort = major * 100 + minor
            except (ValueError, TypeError):
                rec.hierarchy_sort = 9999

    @api.depends("product_id.display_name_nav", "hierarchy_code", "functional_name")
    def _compute_breadcrumb_label(self):
        for rec in self:
            if rec.product_id and rec.hierarchy_code:
                rec.breadcrumb_label = "%s → %s %s" % (
                    rec.product_id.display_name_nav,
                    rec.hierarchy_code,
                    rec.functional_name or "",
                )
            else:
                rec.breadcrumb_label = rec.functional_name or ""

    def _dependency_status_label(self, dep_mod):
        if not dep_mod:
            return _("Bloqueado"), "blocked"
        if dep_mod.technical_state == "not_installed":
            return _("Pendiente"), "pending"
        if dep_mod.functional_state in ("error",):
            return _("Bloqueado"), "blocked"
        if dep_mod.functional_state in ("attention", "unconfigured"):
            return _("Pendiente"), "pending"
        if dep_mod.functional_state == "active" or dep_mod.technical_state == "installed":
            return _("Configurado"), "configured"
        return _("Disponible"), "available"

    @api.depends(
        "technical_name",
        "functional_state",
        "technical_state",
        "product_id",
        "hierarchy_code",
    )
    def _compute_dependency_html(self):
        # Dependencias se resuelven en action_resolve_requirements; no HTML en UI.
        for rec in self:
            rec.dependency_html = False

    def action_resolve_requirements(self):
        self.ensure_one()
        gate = self.env["justech.admin.center.auth.service"].gate_or_wizard()
        if gate:
            return gate
        Module = self.env["justech.admin.module"]
        for tech, _label in FUNCTIONAL_DEPS.get(self.technical_name, []):
            dep = Module.search([("technical_name", "=", tech)], limit=1)
            if not dep:
                continue
            _status, cls = self._dependency_status_label(dep)
            if cls in ("pending", "blocked"):
                return dep.action_configure()
        return self.action_open_admin()

    @api.depends("product_id.hierarchy_code", "product_id.code", "sequence", "functional_name", "technical_name")
    def _compute_hierarchy_code(self):
        """1.1 Centro Fiscal, 1.3 e-CF, etc. — orden funcional fijo por producto."""
        module_order = {
            "fiscal": [
                "justech_fiscal_admin",
                "justech_l10n_do_ncf",
                "justech_ecf_admin",
                "justech_l10n_do_base",
                "justech_l10n_do_reports",
                "justech_l10n_do_payments_withholding",
                "justech_l10n_do_adel_freeze",
            ],
            "finance": [
                "justech_l10n_do_treasury",
                "justech_l10n_do_payments_withholding",
            ],
            "warranty": ["justech_warranty"],
            "core": [
                "justech_admin_center",
            ],
            "audit": ["justech_global_audit_log"],
        }
        hierarchy_minor = {
            "finance": {
                "justech_l10n_do_treasury": 4,
                "justech_l10n_do_payments_withholding": 6,
            },
            "core": {
                "justech_admin_center": 1,
            },
        }
        for rec in self:
            pcode = rec.product_id.hierarchy_code if rec.product_id else "?"
            order = module_order.get(rec.product_id.code if rec.product_id else "", [])
            # Núcleo e-CF: componente técnico, no entrada de navegación funcional.
            if rec.technical_name == "justech_ecf_core":
                rec.hierarchy_code = False
                rec.display_name_nav = False
                continue
            if rec.technical_name in order:
                idx = hierarchy_minor.get(rec.product_id.code, {}).get(
                    rec.technical_name,
                    order.index(rec.technical_name) + 1,
                )
            else:
                idx = max(int(rec.sequence or 99) % 50, 1)
            rec.hierarchy_code = "%s.%s" % (pcode, idx)
            rec.display_name_nav = "%s %s" % (rec.hierarchy_code, rec.functional_name or "")

    @api.depends("technical_name", "functional_name", "functional_state")
    def _compute_action_labels(self):
        labels = {
            "justech_ecf_admin": (
                "Configurar facturación electrónica",
                "Abre el hub e-CF: empresas, certificados, colas y diagnóstico.",
            ),
            "justech_ecf_core": (
                "Abrir documentos e-CF",
                "Lista documentos electrónicos de la empresa activa.",
            ),
            "justech_l10n_do_base": (
                "Actualizar padrón DGII",
                "Abre el hub del padrón compartido (global).",
            ),
            "justech_l10n_do_ncf": (
                "Administrar rangos NCF",
                "Rangos, secuencias y consumo de NCF tradicional.",
            ),
            "justech_fiscal_admin": (
                "Abrir Centro Fiscal",
                "Resumen fiscal, alertas y accesos por empresa.",
            ),
            "justech_l10n_do_reports": (
                "Abrir reportes DGII",
                "606/607/608/609/623 e historial.",
            ),
            "justech_l10n_do_treasury": (
                "Abrir Tesorería",
                "Pagos abiertos, cobros y conciliación.",
            ),
            "justech_warranty": (
                "Administrar garantías",
                "Registro, reclamos y configuración.",
            ),
            "justech_l10n_do_adel_freeze": (
                "Revisar salud fiscal",
                "Controles de integridad y congelamiento preventivo.",
            ),
        }
        # Override display name for 1.7
        for rec in self:
            if rec.technical_name == "justech_l10n_do_adel_freeze" and rec.functional_name != "Auditoría y Salud Fiscal":
                # functional_name comes from registry; labels below still apply
                pass
            label, help_txt = labels.get(
                rec.technical_name,
                (
                    "Abrir %s" % (rec.functional_name or _("módulo")),
                    _("Abre la pantalla administrativa de este módulo."),
                ),
            )
            rec.recommended_action_label = label
            rec.recommended_action_help = help_txt

    @api.depends("technical_state", "functional_state", "active_finding_count")
    def _compute_status_visual(self):
        for rec in self:
            if rec.technical_state == "unavailable":
                rec.status_visual = "grey"
            elif rec.functional_state == "error" or rec.active_finding_count:
                rec.status_visual = "red" if rec.functional_state == "error" else "yellow"
            elif rec.technical_state == "not_installed":
                rec.status_visual = "grey"
            elif rec.functional_state == "attention":
                rec.status_visual = "yellow"
            elif rec.functional_state == "unconfigured":
                rec.status_visual = "blue"
            elif rec.functional_state == "active" and rec.technical_state == "installed":
                rec.status_visual = "green"
            else:
                rec.status_visual = "blue"

    def _compute_company_stats(self):
        Line = self.env["justech.admin.module.company"]
        company_total = self.env["res.company"].search_count([])
        for rec in self:
            if rec.activation_scope == "global":
                rec.company_active_count = company_total
                rec.company_ids_display = _("Todas")
                rec.coverage_label = _("Global — disponible para las %s empresas") % company_total
                continue
            lines = Line.search([("module_id", "=", rec.id), ("functional_state", "=", "active")])
            rec.company_active_count = len(lines)
            rec.company_ids_display = ", ".join(lines.mapped("company_id.name")[:6])
            rec.coverage_label = _("Activo en %s empresas") % len(lines)

    def _compute_finding_count(self):
        Finding = self.env["justech.admin.health.finding"]
        for rec in self:
            rec.active_finding_count = Finding.search_count(
                [
                    ("module_id", "=", rec.id),
                    ("state", "in", ["open", "in_progress"]),
                    ("severity", "in", ["warning", "error", "critical"]),
                ]
            )

    def _compute_overview_html(self):
        """Estado funcional + ayudas; sin HTML en UI (vistas nativas)."""
        for rec in self:
            if rec.technical_state == "not_installed":
                estado = _("Inactivo")
            elif rec.functional_state == "error":
                estado = _("Error")
            elif rec.active_finding_count:
                estado = _("Atención")
            elif rec.activation_scope == "global" and rec.technical_state == "installed":
                estado = _("Correcto")
            elif rec.functional_state == "active":
                estado = _("Correcto")
            elif rec.functional_state == "unconfigured":
                estado = _("No configurado")
            elif rec.technical_state == "installed":
                estado = _("Inactivo")
            else:
                estado = _("No configurado")
            rec.estado_general = estado

            deps = [d.strip() for d in (rec.dependency_names or "").split(",") if d.strip()]
            Module = self.env["justech.admin.module"]
            labels = []
            for d in deps:
                other = Module.search([("technical_name", "=", d)], limit=1)
                labels.append(
                    other.functional_name
                    if other
                    else d.replace("justech_", "").replace("_", " ").title()
                )
            if labels:
                rec.dependency_help = _(
                    "Este producto necesita: %s. Si falta alguna dependencia, "
                    "no podrá activarse de forma segura hasta instalarla."
                ) % (", ".join(labels))
            else:
                rec.dependency_help = _("No declara dependencias Justech adicionales.")

            # Compatibilidad de campos Html: vacíos para no filtrar markup como texto.
            rec.functions_help = False
            rec.overview_html = False

    def _resolve_action(self, key):
        self.ensure_one()
        cfg = ADMIN_ACTIONS.get(self.technical_name) or {}
        xmlid = cfg.get(key) or (self.open_action_xmlid if key == "admin" else False)
        if not xmlid:
            return False
        try:
            return self.env.ref(xmlid).sudo()
        except ValueError:
            return False

    def _run_action(self, key):
        act = self._resolve_action(key)
        if not act:
            return False
        if act._name == "ir.actions.server":
            return act.run()
        data = act.read()[0]
        data.pop("id", None)
        return data

    # La reautenticación se exige solo en acciones (gate_or_wizard), nunca en check_access/read.
    # Un AccessError aquí expulsaba la sesión Odoo / rompía RPC al navegar.

    @api.depends("technical_name", "open_action_xmlid")
    def _compute_has_operation_action(self):
        for rec in self:
            cfg = ADMIN_ACTIONS.get(rec.technical_name) or {}
            rec.has_operation_action = bool(cfg.get("operation") or False)

    def action_back_product(self):
        self.ensure_one()
        if self.product_id:
            return self.product_id.action_open_detail()
        return self.env["justech.admin.console"].action_open_console()

    def action_open_detail(self):
        self.ensure_one()
        gate = self.env["justech.admin.center.auth.service"].gate_or_wizard()
        if gate:
            return gate
        return {
            "type": "ir.actions.act_window",
            "name": self.functional_name,
            "res_model": "justech.admin.module",
            "res_id": self.id,
            "view_mode": "form",
            "target": "current",
        }

    def action_open_admin(self):
        """Administrar: pantalla dedicada del submódulo."""
        self.ensure_one()
        gate = self.env["justech.admin.center.auth.service"].gate_or_wizard()
        if gate:
            return gate
        action = self._run_action("admin")
        if action:
            return action
        return self.action_open_detail()

    def action_configure(self):
        self.ensure_one()
        gate = self.env["justech.admin.center.auth.service"].gate_or_wizard()
        if gate:
            return gate
        action = self._run_action("configure")
        if action:
            return action
        return self.action_open_detail()

    def action_open_operation(self):
        self.ensure_one()
        gate = self.env["justech.admin.center.auth.service"].gate_or_wizard()
        if gate:
            return gate
        action = self._run_action("operation")
        if action:
            return action
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Sin operación directa"),
                "message": _("Use Administrar o Configurar para este submódulo."),
                "type": "info",
            },
        }

    def action_view_status(self):
        self.ensure_one()
        gate = self.env["justech.admin.center.auth.service"].gate_or_wizard()
        if gate:
            return gate
        action = self._run_action("status")
        if action:
            return action
        return self.action_run_health()

    # Compatibilidad: no abrir pantallas genéricas mezcladas
    def action_open_module(self):
        return self.action_open_admin()

    def action_prepare_install(self):
        self.ensure_one()
        gate = self.env["justech.admin.center.auth.service"].gate_or_wizard()
        if gate:
            return gate
        return self.env["justech.admin.module.operation.wizard"].action_open_for_module(
            self, "install"
        )

    def action_prepare_activate(self):
        self.ensure_one()
        gate = self.env["justech.admin.center.auth.service"].gate_or_wizard()
        if gate:
            return gate
        if self.activation_scope == "global":
            raise UserError(
                _("%s es global. No se activa por empresa desde este asistente.")
                % self.functional_name
            )
        return self.env["justech.admin.module.operation.wizard"].action_open_for_module(
            self, "activate"
        )

    def action_prepare_deactivate(self):
        self.ensure_one()
        gate = self.env["justech.admin.center.auth.service"].gate_or_wizard()
        if gate:
            return gate
        return self.env["justech.admin.module.operation.wizard"].action_open_for_module(
            self, "deactivate"
        )

    def action_run_health(self):
        self.ensure_one()
        gate = self.env["justech.admin.center.auth.service"].gate_or_wizard()
        if gate:
            return gate
        return self.env["justech.admin.health.service"].run_module_health(self, open_findings=True)

    def action_diagnose(self):
        """Alias explícito: Diagnosticar siempre ejecuta controles reales."""
        return self.action_run_health()

    def action_open_users(self):
        gate = self.env["justech.admin.center.auth.service"].gate_or_wizard()
        if gate:
            return gate
        return {
            "type": "ir.actions.act_window",
            "name": _("Usuarios y roles"),
            "res_model": "res.users",
            "view_mode": "list,form",
            "domain": [("share", "=", False), ("justech_is_test_user", "=", False)],
            "target": "current",
        }

    def action_open_audit(self):
        self.ensure_one()
        gate = self.env["justech.admin.center.auth.service"].gate_or_wizard()
        if gate:
            return gate
        return {
            "type": "ir.actions.act_window",
            "name": _("Auditoría"),
            "res_model": "justech.admin.audit.log",
            "view_mode": "list,form",
            "domain": [("module_id", "=", self.id)],
            "target": "current",
        }

    def action_show_dependencies(self):
        self.ensure_one()
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Dependencias"),
                "message": self.dependency_help or _("Sin dependencias declaradas."),
                "type": "info",
                "sticky": False,
            },
        }
