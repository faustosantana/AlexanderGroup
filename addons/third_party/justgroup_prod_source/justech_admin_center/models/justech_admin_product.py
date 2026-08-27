from odoo import api, fields, models, _


PRODUCT_BLURBS = {
    "core": {
        "name": "Justech Core",
        "short": (
            "Núcleo común de la plataforma Justech. Administra la integración entre productos, "
            "permisos, empresas, auditoría, diagnósticos y servicios compartidos. "
            "Este producto es requerido por otros productos Justech y normalmente debe permanecer activo."
        ),
        "capabilities": (
            "Administración Justech; Seguridad y roles; Configuración multiempresa; "
            "Auditoría global; Estado del sistema; Diagnóstico"
        ),
    },
    "fiscal": {
        "name": "Justech Fiscal",
        "short": (
            "Centraliza la gestión fiscal dominicana: comprobantes, NCF, padrón DGII, "
            "reportes, retenciones, auditoría y salud fiscal."
        ),
        "capabilities": (
            "Motor Fiscal NCF; Tipos de comprobante; Rangos y secuencias NCF; Padrón DGII; "
            "Centro Fiscal; Reportes 606/607/608/609/623; Retenciones fiscales (capacidad compartida); "
            "Auditoría Fiscal; Salud Fiscal"
        ),
    },
    "finance": {
        "name": "Justech Finanzas",
        "short": (
            "Centraliza cobros, pagos, pagos abiertos, tesorería, bancos, conciliación "
            "y control financiero."
        ),
        "capabilities": (
            "Cobros de clientes; Pagos a proveedores; Pagos abiertos; Tesorería; Bancos; "
            "Conciliación; Retenciones operativas (capacidad compartida); Auditoría financiera"
        ),
    },
    "warranty": {
        "name": "Justech Garantías",
        "short": (
            "Administre garantías de productos vendidos: configuración, registro, "
            "reclamaciones, aprobaciones, cierre y reportes."
        ),
        "capabilities": (
            "3.1 Configuración; 3.2 Registro y seguimiento; 3.3 Reclamaciones; "
            "3.4 Aprobaciones; 3.5 Cierre; 3.6 Reportes"
        ),
    },
    "integrations": {
        "name": "Integraciones",
        "short": (
            "Administra conexiones con DGII, bancos, proveedores, APIs y servicios externos."
        ),
        "capabilities": "DGII; Bancos; Microsoft; APIs; Proveedores; Servicios externos",
    },
    "audit": {
        "name": "Auditoría y cumplimiento",
        "short": (
            "Centraliza trazabilidad, diagnósticos, alertas, controles y registros de cambios "
            "de la plataforma Justech."
        ),
        "capabilities": (
            "Auditoría global; Logs funcionales; Diagnóstico; Estado del sistema; "
            "Historial de cambios; Alertas"
        ),
    },
}


WARRANTY_CAPABILITY_CARDS = [
    ("3.1", _("Configuración"), _("Parámetros, tipos y reglas de garantía.")),
    ("3.2", _("Registro y seguimiento"), _("Altas, vigencia y estado de garantías.")),
    ("3.3", _("Reclamaciones"), _("Solicitudes y motivos de reclamo.")),
    ("3.4", _("Aprobaciones"), _("Flujo de aprobación de reclamos.")),
    ("3.5", _("Cierre"), _("Cierre y resolución de casos.")),
    ("3.6", _("Reportes"), _("Indicadores y listados operativos.")),
]

FISCAL_SUBMODULE_LABELS = {
    "justech_fiscal_admin": "1.1 Centro Fiscal",
    "justech_l10n_do_ncf": "1.2 Motor Fiscal NCF",
    "justech_ecf_admin": "1.3 Facturación electrónica e-CF",
    "justech_l10n_do_base": "1.4 Padrón DGII",
    "justech_l10n_do_reports": "1.5 Reportes DGII",
    "justech_l10n_do_payments_withholding": "1.6 Retenciones",
    "justech_l10n_do_adel_freeze": "1.7 Auditoría y Salud Fiscal",
}


class JustechAdminProduct(models.Model):
    _name = "justech.admin.product"
    _description = "Producto funcional Justech"
    _order = "sequence, id"

    code = fields.Char(required=True, index=True)
    name = fields.Char(required=True, translate=True)
    short_description = fields.Text(required=True, translate=True)
    long_description = fields.Html(translate=True)
    capabilities_text = fields.Text(
        string="Capacidades incluidas",
        help="Lista funcional de capacidades (no nombres técnicos).",
    )
    icon = fields.Char(default="fa-cube")
    sequence = fields.Integer(default=100)
    active = fields.Boolean(default=True)
    hierarchy_code = fields.Char(
        string="Nº",
        compute="_compute_hierarchy_code",
        help="Numeración de navegación (1, 2, 3…). No es un código técnico interno.",
    )
    display_name_nav = fields.Char(compute="_compute_hierarchy_code", string="Nombre navegación")
    module_ids = fields.One2many("justech.admin.module", "product_id", string="Submódulos")
    company_line_ids = fields.One2many(
        "justech.admin.module.company",
        "product_id",
        string="Estados por empresa",
    )
    module_count = fields.Integer(compute="_compute_counts", string="Submódulos")
    installed_count = fields.Integer(compute="_compute_counts", string="Instalados")
    active_company_count = fields.Integer(compute="_compute_counts", string="Activaciones")
    meta_label = fields.Char(compute="_compute_counts", string="Resumen")
    empty_modules_html = fields.Html(compute="_compute_counts", sanitize=False)
    status_visual = fields.Selection(
        selection=[
            ("green", "Correcto"),
            ("yellow", "Atención"),
            ("red", "Error"),
            ("blue", "Informativo"),
            ("grey", "No configurado"),
        ],
        compute="_compute_counts",
    )
    estado_general = fields.Char(compute="_compute_counts", string="Estado general")
    nav_module_ids = fields.Many2many(
        "justech.admin.module",
        compute="_compute_shell_display",
        string="Módulos visibles",
    )
    header_html = fields.Html(compute="_compute_shell_display", sanitize=False)
    dashboard_html = fields.Html(compute="_compute_shell_display", sanitize=False)
    activity_html = fields.Html(compute="_compute_shell_display", sanitize=False)
    breadcrumb_html = fields.Html(compute="_compute_shell_display", sanitize=False)
    recommended_action_label = fields.Char(compute="_compute_shell_display")
    recommended_action_help = fields.Char(compute="_compute_shell_display")
    warning_count = fields.Integer(compute="_compute_shell_display")
    error_count = fields.Integer(compute="_compute_shell_display")
    company_count = fields.Integer(compute="_compute_shell_display")
    last_validation_label = fields.Char(compute="_compute_shell_display", string="Última validación")
    warranty_open_count = fields.Integer(compute="_compute_shell_display", string="Garantías abiertas")
    warranty_claim_count = fields.Integer(compute="_compute_shell_display", string="Reclamaciones")
    warranty_expired_count = fields.Integer(compute="_compute_shell_display", string="Vencidas")
    warranty_pending_approval_count = fields.Integer(
        compute="_compute_shell_display", string="Pendientes de aprobación"
    )

    _sql_constraints = [
        ("code_uniq", "unique(code)", "El código de producto debe ser único."),
    ]

    def init(self):
        """Garantiza UNIQUE(code) aunque instalaciones antiguas no crearan el constraint."""
        self.env.cr.execute(
            """
            DO $$ BEGIN
                ALTER TABLE justech_admin_product
                    ADD CONSTRAINT justech_admin_product_code_uniq UNIQUE (code);
            EXCEPTION
                WHEN duplicate_table THEN NULL;
                WHEN duplicate_object THEN NULL;
            END $$;
            """
        )

    @api.depends("sequence", "name", "code")
    def _compute_hierarchy_code(self):
        """Numeración visual estable por producto funcional (no XMLID)."""
        order_map = {
            "fiscal": "1",
            "finance": "2",
            "warranty": "3",
            "core": "4",
            "audit": "5",
            "integrations": "6",
        }
        for rec in self:
            code = order_map.get(rec.code) or str(max(rec.sequence or 99, 1))
            rec.hierarchy_code = code
            rec.display_name_nav = "%s. %s" % (code, rec.name or "")

    def _sync_sequence_from_hierarchy(self):
        order_map = {
            "fiscal": 10,
            "finance": 20,
            "warranty": 30,
            "core": 40,
            "audit": 50,
            "integrations": 60,
        }
        for rec in self:
            desired = order_map.get(rec.code)
            if desired and rec.sequence != desired:
                rec.sequence = desired

    @api.model_create_multi
    def create(self, vals_list):
        """Evita duplicados por code (p. ej. XMLID renombrado en data/*.xml)."""
        result = self.browse()
        pending = []
        for vals in vals_list:
            code = vals.get("code")
            if code:
                existing = self.sudo().with_context(active_test=False).search(
                    [("code", "=", code)], limit=1
                )
                if existing:
                    existing.write({k: v for k, v in vals.items() if k != "code"})
                    result |= existing
                    continue
            pending.append(vals)
        if pending:
            result |= super().create(pending)
        result._sync_sequence_from_hierarchy()
        return result

    def write(self, vals):
        res = super().write(vals)
        if "code" in vals or "sequence" not in vals:
            self._sync_sequence_from_hierarchy()
        return res

    @api.model
    def dedupe_by_code(self):
        Data = self.env["ir.model.data"].sudo()
        Module = self.env["justech.admin.module"].sudo()
        for code in ["core", "fiscal", "finance", "warranty", "integrations", "audit"]:
            products = self.sudo().search([("code", "=", code)], order="id")
            if len(products) <= 1:
                continue
            keeper = self.env["justech.admin.product"]
            for p in products:
                if Data.search(
                    [
                        ("model", "=", "justech.admin.product"),
                        ("res_id", "=", p.id),
                        ("module", "=", "justech_admin_center"),
                    ],
                    limit=1,
                ):
                    keeper = p
                    break
            if not keeper:
                keeper = products.filtered(lambda p: p.module_ids)[:1] or products[:1]
            for p in products - keeper:
                Module.search([("product_id", "=", p.id)]).write({"product_id": keeper.id})
                p.unlink()
        return True

    def _context_company(self):
        cid = self.env.context.get("justech_admin_company_id")
        if cid:
            return self.env["res.company"].browse(cid)
        return self.env.company

    def _compute_counts(self):
        CompanyLine = self.env["justech.admin.module.company"]
        Finding = self.env["justech.admin.health.finding"]
        for rec in self:
            company = rec._context_company()
            mods = rec.module_ids.filtered("show_in_product_nav")
            rec.module_count = len(mods)
            rec.installed_count = len(mods.filtered(lambda m: m.technical_state == "installed"))
            company_lines = CompanyLine.search(
                [
                    ("module_id", "in", mods.ids),
                    ("company_id", "=", company.id),
                    ("functional_state", "=", "active"),
                ]
            )
            rec.active_company_count = len(company_lines)
            companies_active = len(
                set(
                    CompanyLine.search(
                        [("module_id", "in", mods.ids), ("functional_state", "=", "active")]
                    ).mapped("company_id").ids
                )
            )
            has_global = any(
                m.activation_scope == "global" and m.technical_state == "installed" for m in mods
            )
            has_company_active = bool(company_lines) or has_global
            if company_lines:
                rec.meta_label = _("Activo en esta empresa · %s empresas en total") % max(
                    companies_active, 1
                )
            elif has_global:
                rec.meta_label = _("Disponible globalmente")
            elif rec.installed_count:
                rec.meta_label = _("Disponible · no configurado aquí")
            else:
                rec.meta_label = _("%s capacidades") % rec.module_count

            pending = Finding.search_count(
                [
                    ("state", "in", ["open", "in_progress"]),
                    ("severity", "in", ["warning", "error", "critical"]),
                    "|",
                    ("product_id", "=", rec.id),
                    ("module_id", "in", mods.ids),
                    "|",
                    ("company_id", "=", False),
                    ("company_id", "=", company.id),
                ]
            )
            err = Finding.search_count(
                [
                    ("state", "in", ["open", "in_progress"]),
                    ("severity", "in", ["error", "critical"]),
                    "|",
                    ("product_id", "=", rec.id),
                    ("module_id", "in", mods.ids),
                    "|",
                    ("company_id", "=", False),
                    ("company_id", "=", company.id),
                ]
            )
            if err:
                rec.status_visual = "red"
                rec.estado_general = _("Error")
            elif pending:
                rec.status_visual = "yellow"
                rec.estado_general = _("Atención")
            elif has_company_active or (rec.code == "core" and rec.installed_count):
                rec.status_visual = "green"
                rec.estado_general = _("Correcto")
            elif rec.installed_count:
                rec.status_visual = "grey"
                rec.estado_general = _("No configurado")
            else:
                rec.status_visual = "grey"
                rec.estado_general = _("Inactivo")
            rec.empty_modules_html = False

    def _warranty_stats(self):
        stats = {"open": 0, "expired": 0, "claims": 0, "pending_approval": 0}
        if "justech.warranty" not in self.env:
            return stats
        Warranty = self.env["justech.warranty"].sudo()
        company = self._context_company()
        domain = []
        if "company_id" in Warranty._fields:
            domain = [("company_id", "=", company.id)]
        # Prefer real open states when available
        if "state" in Warranty._fields:
            stats["open"] = Warranty.search_count(domain + [("state", "in", ["active", "open", "running"])])
            stats["expired"] = Warranty.search_count(domain + [("state", "=", "expired")])
            if not stats["open"]:
                stats["open"] = Warranty.search_count(domain)
        else:
            stats["open"] = Warranty.search_count(domain)
        if "justech.warranty.claim" in self.env:
            Claim = self.env["justech.warranty.claim"].sudo()
            cdomain = []
            if "company_id" in Claim._fields:
                cdomain = [("company_id", "=", company.id)]
            stats["claims"] = Claim.search_count(cdomain + [("state", "not in", ["done", "cancel", "closed"])])
            stats["pending_approval"] = Claim.search_count(
                cdomain + [("state", "in", ["submitted", "to_approve", "pending"])]
            )
        return stats

    def _format_activity(self, audits):
        if not audits:
            return False
        return False  # activity rendered via native O2M, not HTML

    @api.depends(
        "module_ids",
        "module_ids.show_in_product_nav",
        "module_ids.status_visual",
        "module_ids.functional_state",
        "module_ids.hierarchy_code",
        "estado_general",
        "meta_label",
        "name",
        "short_description",
        "hierarchy_code",
        "icon",
        "code",
    )
    def _compute_shell_display(self):
        Audit = self.env["justech.admin.audit.log"]
        Finding = self.env["justech.admin.health.finding"]
        for rec in self:
            company = rec._context_company()
            nav_mods = rec.module_ids.filtered("show_in_product_nav").sorted(
                key=lambda m: m.hierarchy_sort
            )
            rec.nav_module_ids = nav_mods
            pending_domain = [
                ("state", "in", ["open", "in_progress"]),
                ("severity", "in", ["warning", "error", "critical"]),
                "|",
                ("product_id", "=", rec.id),
                ("module_id", "in", nav_mods.ids),
                "|",
                ("company_id", "=", False),
                ("company_id", "=", company.id),
            ]
            pending = Finding.search(pending_domain, order="severity_rank desc", limit=1)
            rec.warning_count = Finding.search_count(
                pending_domain + [("severity", "=", "warning")]
            )
            rec.error_count = Finding.search_count(
                pending_domain + [("severity", "in", ["error", "critical"])]
            )
            rec.company_count = 1
            last_audit = Audit.search(
                [("module_id", "in", rec.module_ids.ids)],
                order="id desc",
                limit=1,
            )
            rec.last_validation_label = (
                last_audit.create_date.strftime("%Y-%m-%d %H:%M")
                if last_audit and last_audit.create_date
                else _("Sin validación")
            )
            if pending:
                rec.recommended_action_label = _("Resolver")
                rec.recommended_action_help = pending.name
            elif rec.estado_general == _("No configurado"):
                rec.recommended_action_label = _("Configurar")
                rec.recommended_action_help = _("Configure este producto para %s") % company.name
            else:
                rec.recommended_action_label = _("Administrar")
                rec.recommended_action_help = _("Abrir capacidades del producto")

            # Native-only shells: keep HTML empty so views never show markup as text
            rec.breadcrumb_html = False
            rec.header_html = False
            rec.dashboard_html = False
            rec.activity_html = False
            stats = rec._warranty_stats() if rec.code == "warranty" else {}
            rec.warranty_open_count = stats.get("open", 0)
            rec.warranty_claim_count = stats.get("claims", 0)
            rec.warranty_expired_count = stats.get("expired", 0)
            rec.warranty_pending_approval_count = stats.get("pending_approval", 0)


    def action_revisar_pendientes(self):
        self.ensure_one()
        gate = self.env["justech.admin.center.auth.service"].gate_or_wizard()
        if gate:
            return gate
        return {
            "type": "ir.actions.act_window",
            "name": _("Pendientes — %s") % self.name,
            "res_model": "justech.admin.health.finding",
            "view_mode": "kanban,list,form",
            "domain": [
                ("state", "in", ["open", "in_progress"]),
                ("severity", "in", ["warning", "error", "critical"]),
                "|",
                ("product_id", "=", self.id),
                ("module_id", "in", self.module_ids.ids),
            ],
            "context": {
                "search_default_open": 1,
                "clear_breadcrumbs": True,
                "justech_admin_company_id": self.env.context.get(
                    "justech_admin_company_id", self.env.company.id
                ),
            },
            "target": "current",
        }

    def action_back_console(self):
        return self.env["justech.admin.console"].action_open_console()

    def action_open_system_status(self):
        self.ensure_one()
        return self.env["justech.admin.system.status"].action_open(company=self.env.company)

    def action_open_warranty_ops(self):
        self.ensure_one()
        gate = self.env["justech.admin.center.auth.service"].gate_or_wizard()
        if gate:
            return gate
        mod = self.module_ids.filtered(lambda m: m.technical_name == "justech_warranty")[:1]
        return mod.action_open_admin() if mod else self.action_open_detail()

    def action_open_warranty_claims(self):
        self.ensure_one()
        gate = self.env["justech.admin.center.auth.service"].gate_or_wizard()
        if gate:
            return gate
        mod = self.module_ids.filtered(lambda m: m.technical_name == "justech_warranty")[:1]
        if mod:
            return mod.action_view_status()
        return self.action_open_detail()

    @api.model
    def refresh_blurbs(self):
        """Update functional copy from catalog without touching auth."""
        for code, blurb in PRODUCT_BLURBS.items():
            product = self.search([("code", "=", code)], limit=1)
            if not product:
                continue
            product.write(
                {
                    "name": blurb["name"],
                    "short_description": blurb["short"],
                    "capabilities_text": blurb["capabilities"],
                    "long_description": (
                        "<p>%s</p><p><strong>%s</strong> %s</p>"
                        % (
                            blurb["short"],
                            _("Capacidades:"),
                            blurb["capabilities"],
                        )
                    ),
                }
            )
        return True

    def action_open_detail(self):
        self.ensure_one()
        gate = self.env["justech.admin.center.auth.service"].gate_or_wizard()
        if gate:
            return gate
        return {
            "type": "ir.actions.act_window",
            "name": self.name,
            "res_model": "justech.admin.product",
            "res_id": self.id,
            "view_mode": "form",
            "views": [(False, "form")],
            "target": "main",
            "context": {
                "form_view_initial_mode": "readonly",
                "clear_breadcrumbs": True,
                "justech_admin_company_id": self.env.context.get(
                    "justech_admin_company_id", self.env.company.id
                ),
            },
        }

    def action_run_diagnostics(self):
        self.ensure_one()
        gate = self.env["justech.admin.center.auth.service"].gate_or_wizard()
        if gate:
            return gate
        for mod in self.module_ids.filtered(lambda m: m.technical_state == "installed"):
            self.env["justech.admin.health.service"].run_module_health(mod)
        return self.env["justech.admin.console"].action_open_health()

    def action_open_users(self):
        gate = self.env["justech.admin.center.auth.service"].gate_or_wizard()
        if gate:
            return gate
        return {
            "type": "ir.actions.act_window",
            "name": _("Usuarios y roles"),
            "res_model": "res.users",
            "view_mode": "list,form",
            "domain": [("share", "=", False)],
            "target": "current",
        }

    def action_open_audit(self):
        self.ensure_one()
        gate = self.env["justech.admin.center.auth.service"].gate_or_wizard()
        if gate:
            return gate
        return {
            "type": "ir.actions.act_window",
            "name": _("Auditoría — %s") % self.name,
            "res_model": "justech.admin.audit.log",
            "view_mode": "list,form",
            "domain": [("module_id", "in", self.module_ids.ids)],
            "target": "current",
        }

    def action_open_company_matrix(self):
        self.ensure_one()
        gate = self.env["justech.admin.center.auth.service"].gate_or_wizard()
        if gate:
            return gate
        return {
            "type": "ir.actions.act_window",
            "name": _("Empresas — %s") % self.name,
            "res_model": "justech.admin.module.company",
            "view_mode": "list,form",
            "domain": [("product_id", "=", self.id)],
            "context": {"search_default_group_company": 1},
            "target": "current",
        }
