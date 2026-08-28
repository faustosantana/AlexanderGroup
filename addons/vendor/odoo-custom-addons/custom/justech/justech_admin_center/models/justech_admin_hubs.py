from odoo import api, fields, models, _


class JustechAdminPadronHub(models.TransientModel):
    _name = "justech.admin.padron.hub"
    _description = "Administración Padrón DGII"

    name = fields.Char(default="Padrón DGII", readonly=True)
    record_count = fields.Integer(string="Registros cargados", readonly=True)
    last_success_at = fields.Datetime(string="Última actualización exitosa", readonly=True)
    next_run_at = fields.Datetime(string="Próxima actualización", readonly=True)
    frequency_days = fields.Integer(string="Frecuencia (días)", readonly=True)
    cron_active = fields.Boolean(string="Actualización automática activa", readonly=True)
    official_url = fields.Char(string="Fuente", readonly=True)
    last_status = fields.Char(string="Último estado", readonly=True)
    last_message = fields.Text(string="Último mensaje", readonly=True)
    scope_note = fields.Char(readonly=True, string="Alcance")
    company_count = fields.Integer(readonly=True, string="Empresas cubiertas")

    @api.model
    def action_open(self):
        gate = self.env["justech.admin.center.auth.service"].gate_or_wizard()
        if gate:
            return gate
        hub = self.create({})
        hub._load()
        return {
            "type": "ir.actions.act_window",
            "name": _("Padrón DGII"),
            "res_model": self._name,
            "res_id": hub.id,
            "view_mode": "form",
            "target": "current",
        }

    def _load(self):
        self.ensure_one()
        companies = self.env["res.company"].search_count([])
        vals = {
            "scope_note": _("Global — disponible para las %s empresas") % companies,
            "company_count": companies,
        }
        if "justech.do.rnc.padron" in self.env:
            vals["record_count"] = self.env["justech.do.rnc.padron"].sudo().search_count([])
        if "justech.do.rnc.padron.config" in self.env:
            cfg = self.env["justech.do.rnc.padron.config"].sudo().get_config()
            vals.update(
                {
                    "last_success_at": cfg.last_success_at,
                    "next_run_at": cfg.next_run_at,
                    "frequency_days": cfg.frequency_days,
                    "cron_active": cfg.cron_active,
                    "official_url": cfg.official_url,
                    "last_status": cfg.last_status,
                    "last_message": cfg.last_message,
                }
            )
        self.write(vals)

    def action_open_records(self):
        return self.env.ref("justech_l10n_do_base.action_justech_do_rnc_padron").sudo().read()[0]

    def action_open_import(self):
        return self.env.ref("justech_l10n_do_base.action_justech_do_rnc_padron_import").sudo().read()[0]

    def action_open_history(self):
        return self.env.ref(
            "justech_l10n_do_base.action_justech_do_rnc_padron_import_log"
        ).sudo().read()[0]

    def action_open_cron(self):
        return self.env.ref(
            "justech_l10n_do_base.action_justech_do_rnc_padron_config_server"
        ).sudo().run()

    def action_update_now(self):
        return self.action_open_cron()

    def action_verify(self):
        self._load()
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Integridad del padrón"),
                "message": _(
                    "%(n)s registros · próxima actualización %(next)s · frecuencia %(d)s días"
                )
                % {
                    "n": self.record_count,
                    "next": self.next_run_at or "—",
                    "d": self.frequency_days or 45,
                },
                "type": "success",
            },
        }


class JustechAdminFiscalHub(models.TransientModel):
    _name = "justech.admin.fiscal.hub"
    _description = "Centro Fiscal — resumen administrativo"

    name = fields.Char(default="Centro Fiscal", readonly=True)
    status_label = fields.Char(readonly=True, string="Estado")
    open_alert_count = fields.Integer(readonly=True, string="Acciones requeridas")
    summary_note = fields.Char(readonly=True)

    @api.model
    def action_open(self):
        gate = self.env["justech.admin.center.auth.service"].gate_or_wizard()
        if gate:
            return gate
        hub = self.create({})
        hub._load()
        return {
            "type": "ir.actions.act_window",
            "name": _("Centro Fiscal"),
            "res_model": self._name,
            "res_id": hub.id,
            "view_mode": "form",
            "target": "current",
            "context": {"clear_breadcrumbs": True},
        }

    def _load(self):
        Product = self.env["justech.admin.product"].search([("code", "=", "fiscal")], limit=1)
        Finding = self.env["justech.admin.health.finding"]
        open_n = 0
        if Product:
            open_n = Finding.search_count(
                [
                    ("module_id", "in", Product.module_ids.ids),
                    ("state", "in", ["open", "in_progress"]),
                    ("severity", "in", ["warning", "error", "critical"]),
                ]
            )
        self.write(
            {
                "open_alert_count": open_n,
                "status_label": _("Atención") if open_n else _("Correcto"),
                "summary_note": _(
                    "Salud fiscal, accesos a submódulos y estado por empresa."
                ),
            }
        )

    def action_open_padron(self):
        return self.env["justech.admin.padron.hub"].action_open()

    def action_open_ncf(self):
        mod = self.env["justech.admin.module"].search(
            [("technical_name", "=", "justech_l10n_do_ncf")], limit=1
        )
        return mod.action_open_admin() if mod else False

    def action_open_reports(self):
        mod = self.env["justech.admin.module"].search(
            [("technical_name", "=", "justech_l10n_do_reports")], limit=1
        )
        return mod.action_open_admin() if mod else False

    def action_open_ecf(self):
        if "justech.ecf.admin.hub" in self.env:
            return self.env["justech.ecf.admin.hub"].action_open()
        return False

    def action_open_companies(self):
        product = self.env["justech.admin.product"].search([("code", "=", "fiscal")], limit=1)
        return product.action_open_company_matrix() if product else False

    def action_open_health(self):
        return self.env["justech.admin.console"].action_open_health()

    def action_open_users(self):
        return self.env["justech.admin.console"].action_open_users()


class JustechAdminTreasuryHub(models.TransientModel):
    _name = "justech.admin.treasury.hub"
    _description = "Administración Tesorería Justech"

    name = fields.Char(default="Tesorería", readonly=True)
    summary_note = fields.Char(readonly=True)

    @api.model
    def action_open(self):
        gate = self.env["justech.admin.center.auth.service"].gate_or_wizard()
        if gate:
            return gate
        hub = self.create(
            {
                "summary_note": _(
                    "Cobros, pagos, pagos abiertos y conciliación bancaria por empresa."
                ),
            }
        )
        return {
            "type": "ir.actions.act_window",
            "name": _("Tesorería"),
            "res_model": self._name,
            "res_id": hub.id,
            "view_mode": "form",
            "target": "current",
            "context": {"clear_breadcrumbs": True},
        }

    def action_open_customer_payments(self):
        return self.env.ref("account.action_account_payments").sudo().read()[0]

    def action_open_vendor_payments(self):
        return self.env.ref("account.action_account_payments_payable").sudo().read()[0]

    def action_open_open_customer(self):
        return self.env.ref("justech_l10n_do_treasury.action_treasury_open_payments_customer").sudo().read()[0]

    def action_open_open_vendor(self):
        return self.env.ref("justech_l10n_do_treasury.action_treasury_open_payments_vendor").sudo().read()[0]

    def action_open_reconciliation(self):
        return self.env.ref("justech_l10n_do_treasury.action_justech_bank_reconciliation").sudo().read()[0]

    def action_open_register_customer(self):
        return self.env.ref(
            "justech_l10n_do_payments_withholding.action_justech_register_customer_payment"
        ).sudo().read()[0]
