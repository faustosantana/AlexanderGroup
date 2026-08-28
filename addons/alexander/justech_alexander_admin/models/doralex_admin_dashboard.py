from odoo import api, fields, models
from odoo.release import version_info

ENTERPRISE_REQUIRED = (
    "justech_l10n_do_hr_payroll",
    "justech_l10n_do_hr_payroll_account",
    "justech_l10n_do_hr_payroll_attendance",
    "justech_l10n_do_hr_payroll_bank",
    "justech_l10n_do_hr_payroll_holidays",
    "justech_l10n_do_hr_payroll_reports",
    "justech_l10n_do_hr_payroll_subsidies",
    "justech_l10n_do_payments_withholding",
    "justech_l10n_do_reports",
    "justech_l10n_do_treasury",
    "studio_hotfix",
    "web_studio",
)

NOT_APPLICABLE = ("justech_admin_center",)

CONFIG_HINTS = {
    "justech_l10n_do_ncf": "Rangos NCF DGII pendientes",
    "justech_modules": "Clave administrativa",
    "justech_alexander_website": "Website institucional",
    "justech_alexander_reports": "Layout de documentos",
}


class DoralexModuleStatus(models.TransientModel):
    _name = "doralex.module.status"
    _description = "Estado de módulo Doralex"
    _order = "visual_state, technical_name"

    dashboard_id = fields.Many2one("doralex.admin.dashboard", ondelete="cascade")
    technical_name = fields.Char(required=True)
    display_name_mod = fields.Char(string="Módulo")
    version = fields.Char()
    dependencies = fields.Char()
    visual_state = fields.Selection(
        [
            ("INSTALADO", "INSTALADO"),
            ("REQUIERE_CONFIGURACION", "REQUIERE_CONFIGURACION"),
            ("ENTERPRISE_REQUIRED", "ENTERPRISE_REQUIRED"),
            ("UPDATE_AVAILABLE", "UPDATE_AVAILABLE"),
            ("ERROR", "ERROR"),
            ("DISPONIBLE", "Disponible"),
        ],
        required=True,
    )
    config_note = fields.Char(string="Configuración")
    update_info = fields.Char(string="Actualizaciones")
    origin = fields.Selection(
        [
            ("justech", "Justech"),
            ("doralex", "Doralex"),
            ("third_party", "Terceros"),
        ],
        default="justech",
    )


class DoralexAdminDashboard(models.TransientModel):
    _name = "doralex.admin.dashboard"
    _description = "Administración Doralex"

    active_company_id = fields.Many2one(
        "res.company",
        string="Empresa activa",
        default=lambda self: self.env.company,
        readonly=True,
    )
    odoo_version = fields.Char(readonly=True)
    system_state = fields.Char(readonly=True)
    diagnosis = fields.Text(readonly=True)
    module_count_installed = fields.Integer(readonly=True)
    key_configured = fields.Boolean(readonly=True)
    line_ids = fields.One2many(
        "doralex.module.status",
        "dashboard_id",
        string="Módulos",
    )

    @api.model
    def _module_visual(self, module, technical_name):
        if technical_name in ENTERPRISE_REQUIRED:
            if not module or module.state != "installed":
                return "ENTERPRISE_REQUIRED", "Requiere fuente Enterprise"
        if technical_name in NOT_APPLICABLE:
            return "DISPONIBLE", "Marcado NOT_APPLICABLE — no se instala"
        if not module:
            return "ERROR", "No está en addons_path"
        if module.state == "installed":
            note = ""
            if technical_name == "justech_l10n_do_ncf":
                if (
                    self.env["ir.config_parameter"]
                    .sudo()
                    .get_param("doralex.ncf_ranges_ready")
                    != "1"
                ):
                    note = "Rangos NCF DGII pendientes"
            if technical_name == "justech_modules":
                if not self.env["doralex.admin.auth.service"].key_is_configured():
                    note = "Clave administrativa pendiente"
            if note:
                return "REQUIERE_CONFIGURACION", note
            latest = module.latest_version or ""
            installed = module.installed_version or ""
            if latest and installed and latest != installed:
                return "UPDATE_AVAILABLE", "Instalada %s · catálogo %s" % (
                    installed,
                    latest,
                )
            return "INSTALADO", "Configuración base presente"
        if module.state in ("to install", "to upgrade", "to remove"):
            return "ERROR", "Estado transitorio: %s" % module.state
        return "DISPONIBLE", "No instalado"

    @api.model
    def _collect_module_names(self):
        Module = self.env["ir.module.module"].sudo()
        names = set(
            Module.search(
                [
                    "|",
                    "|",
                    ("name", "like", "justech_%"),
                    ("name", "like", "justech_alexander_%"),
                    (
                        "name",
                        "in",
                        list(ENTERPRISE_REQUIRED)
                        + [
                            "l10n_do_accounting",
                            "bi_convert_purchase_from_sales",
                            "multi_invoice_manual_payment_prod",
                        ],
                    ),
                ]
            ).mapped("name")
        )
        names.update(ENTERPRISE_REQUIRED)
        names.update(
            [
                "justech_alexander_base",
                "justech_alexander_website",
                "justech_alexander_admin",
                "justech_alexander_reports",
            ]
        )
        return sorted(names)

    def _fill(self):
        Module = self.env["ir.module.module"].sudo()
        lines = []
        installed = 0
        for name in self._collect_module_names():
            module = Module.search([("name", "=", name)], limit=1)
            visual, note = self._module_visual(module, name)
            if visual == "INSTALADO":
                installed += 1
            origin = "doralex" if name.startswith("justech_alexander_") else "justech"
            if name in (
                "l10n_do_accounting",
                "bi_convert_purchase_from_sales",
                "multi_invoice_manual_payment_prod",
            ):
                origin = "third_party"
            depends = ""
            display = name
            version = ""
            if module:
                display = module.shortdesc or module.display_name or name
                version = module.installed_version or module.latest_version or ""
                depends = ", ".join(module.dependencies_id.mapped("name")[:8])
            lines.append(
                (
                    0,
                    0,
                    {
                        "technical_name": name,
                        "display_name_mod": display,
                        "version": version,
                        "dependencies": depends,
                        "visual_state": visual,
                        "config_note": note,
                        "update_info": version,
                        "origin": origin,
                    },
                )
            )
        diagnosis = [
            "Empresa activa: %s" % (self.env.company.display_name,),
            "Clave administrativa configurada: %s"
            % (
                "sí"
                if self.env["doralex.admin.auth.service"].key_is_configured()
                else "no"
            ),
            "Website: %s"
            % (
                "instalado"
                if Module.search(
                    [("name", "=", "website"), ("state", "=", "installed")], limit=1
                )
                else "no instalado"
            ),
        ]
        self.write(
            {
                "odoo_version": ".".join(str(v) for v in version_info[:3]),
                "system_state": "OK" if installed else "REQUIERE_CONFIGURACION",
                "diagnosis": "\n".join(diagnosis),
                "module_count_installed": installed,
                "key_configured": self.env[
                    "doralex.admin.auth.service"
                ].key_is_configured(),
                "line_ids": [(5, 0, 0)] + lines,
            }
        )

    @api.model
    def action_open(self):
        rec = self.create({})
        rec._fill()
        return {
            "type": "ir.actions.act_window",
            "name": "Estado del sistema",
            "res_model": "doralex.admin.dashboard",
            "res_id": rec.id,
            "view_mode": "form",
            "target": "current",
        }
