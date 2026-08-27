# -*- coding: utf-8 -*-
"""Centro de Administración Fiscal Justech — hub Enterprise."""
import json

from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError


def _status_icon(ok, warn=False):
    if ok:
        return "🟢"
    if warn:
        return "🟡"
    return "🔴"


def _progress_bar(used_pct):
    pct = min(100, max(0, int(used_pct or 0)))
    color = "success" if pct < 70 else ("warning" if pct < 90 else "danger")
    return (
        f'<div class="progress justech-fiscal-progress" style="height:22px">'
        f'<div class="progress-bar bg-{color}" role="progressbar" '
        f'style="width:{pct}%" aria-valuenow="{pct}" aria-valuemin="0" aria-valuemax="100">'
        f"{pct}%</div></div>"
    )


class JustechFiscalAdminCenter(models.Model):
    _name = "justech.fiscal.admin.center"
    _description = "Centro de Administración Fiscal Justech"
    _rec_name = "display_name"

    display_name = fields.Char(compute="_compute_display_name", store=True)
    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
        index=True,
        ondelete="cascade",
    )

    _sql_constraints = [
        (
            "justech_fiscal_admin_center_company_uniq",
            "unique(company_id)",
            "Solo puede existir un Centro Fiscal por empresa.",
        ),
    ]

    @api.depends("company_id")
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = _(
                "Centro Fiscal — %(company)s",
                company=rec.company_id.display_name or "",
            )
    stack_json = fields.Text(readonly=True)
    health_json = fields.Text(readonly=True)
    dashboard_html = fields.Html(compute="_compute_dashboard_html", sanitize=False)
    last_refresh = fields.Datetime(readonly=True)
    health_ok = fields.Boolean(readonly=True)
    issue_count = fields.Integer(readonly=True)
    warning_count = fields.Integer(readonly=True)
    motor_status = fields.Char(readonly=True)
    provider_status = fields.Char(readonly=True)
    reports_status = fields.Char(readonly=True)

    payments_json = fields.Text(readonly=True)
    ncf_json = fields.Text(readonly=True)
    padron_json = fields.Text(readonly=True)
    health_findings_json = fields.Text(readonly=True)
    is_system_admin = fields.Boolean(compute="_compute_fiscal_caps")
    is_fiscal_admin = fields.Boolean(compute="_compute_fiscal_caps")
    is_fiscal_officer = fields.Boolean(compute="_compute_fiscal_caps")
    is_fiscal_user_only = fields.Boolean(compute="_compute_fiscal_caps")
    can_manage_padron = fields.Boolean(compute="_compute_fiscal_caps")
    can_manage_users = fields.Boolean(compute="_compute_fiscal_caps")
    can_revalidate_health = fields.Boolean(compute="_compute_fiscal_caps")
    can_open_ncf_admin = fields.Boolean(compute="_compute_fiscal_caps")
    access_mode = fields.Selection(
        [
            ("admin", "Administrador"),
            ("officer", "Responsable"),
            ("user", "Usuario"),
        ],
        compute="_compute_fiscal_caps",
    )

    def _compute_fiscal_caps(self):
        user = self.env.user
        is_system = user.has_group("base.group_system")
        is_admin = is_system or user.has_group(
            "justech_fiscal_admin.group_justech_fiscal_admin_manager"
        )
        is_officer = is_admin or user.has_group(
            "justech_l10n_do_base.group_justech_do_fiscal_manager"
        )
        is_user = is_officer or user.has_group(
            "justech_l10n_do_base.group_justech_do_fiscal_user"
        )
        for rec in self:
            rec.is_system_admin = is_system
            rec.is_fiscal_admin = is_admin
            rec.is_fiscal_officer = is_officer and not is_admin
            rec.is_fiscal_user_only = is_user and not is_officer
            rec.can_manage_padron = is_admin
            rec.can_manage_users = is_admin
            rec.can_revalidate_health = is_officer or is_admin
            rec.can_open_ncf_admin = is_admin or is_officer
            if is_admin:
                rec.access_mode = "admin"
            elif is_officer:
                rec.access_mode = "officer"
            else:
                rec.access_mode = "user"

    @api.depends(
        "stack_json",
        "health_json",
        "payments_json",
        "ncf_json",
        "padron_json",
        "company_id",
        "is_fiscal_admin",
        "can_manage_padron",
    )
    def _compute_dashboard_html(self):
        svc = self.env["justech.fiscal.admin.service"]
        for rec in self:
            if not rec.stack_json:
                rec.dashboard_html = Markup("<p class='text-muted'>Pulse Actualizar.</p>")
                continue
            stack = json.loads(rec.stack_json)
            health = json.loads(rec.health_json) if rec.health_json else {}
            pay = json.loads(rec.payments_json) if rec.payments_json else {}
            ncf = json.loads(rec.ncf_json) if rec.ncf_json else {}
            padron = json.loads(rec.padron_json) if rec.padron_json else {}

            motor_ok = stack.get("motor_active")
            reports_ok = stack.get("reports_active")
            pay_ok = pay.get("standard_status") == "activo" and pay.get("wizard_unified")
            health_warn = not health.get("ok") and health.get("warnings")

            modules_html = "".join(
                f"<li>{_status_icon(m['state']=='installed')} <strong>{m['name']}</strong> "
                f"— {m['state']} ({m['version']})</li>"
                for m in stack.get("modules", [])
            )
            features_html = "".join(
                f"<li>{_status_icon(f['enabled'], warn=not f['enabled'] and not f.get('readonly'))} "
                f"{f['name']}: {'Activado' if f['enabled'] else 'Desactivado'}</li>"
                for f in stack.get("features", [])
            )
            issues = "".join(f"<li>{_status_icon(False)} {i}</li>" for i in health.get("issues", []))
            warns = "".join(f"<li>{_status_icon(False, warn=True)} {w}</li>" for w in health.get("warnings", []))
            recs = "".join(
                f"<li>{_status_icon(True, warn=True)} {r}</li>" for r in health.get("recommendations", [])
            )
            multi = svc.multi_company_summary()
            multi_html = "".join(
                f"<tr><td>{r['name']}</td>"
                f"<td>{_status_icon(r['fiscal_enabled'])} {'Sí' if r['fiscal_enabled'] else 'No'}</td>"
                f"<td>{_status_icon(r['health_ok'], warn=not r['health_ok'] and r['warnings']==0)}</td>"
                f"<td>{r['issues']}</td><td>{r['warnings']}</td></tr>"
                for r in multi
            )
            pay_inc = "".join(
                f"<li>{_status_icon(False, warn=True)} {i}</li>" for i in pay.get("inconsistencies", [])
            )
            ncf_rows = "".join(
                f"<tr><td>{r['prefix']}</td>"
                f"<td>{_status_icon(r['status']=='ok', warn=r['status']=='warning')} {r['state']}</td>"
                f"<td>{r['remaining']}/{r['capacity']}</td>"
                f"<td>{_progress_bar(r['used_pct'])}</td></tr>"
                for r in ncf.get("ranges", [])
            )
            ncf_alerts = "".join(
                f"<li>{_status_icon(False, warn=True)} {a}</li>" for a in ncf.get("alerts", [])
            )

            padron_html = ""
            if padron:
                visual = padron.get("status_visual") or "grey"
                color = {
                    "green": "success",
                    "yellow": "warning",
                    "red": "danger",
                    "grey": "secondary",
                }.get(visual, "secondary")
                icon = {
                    "green": "🟢",
                    "yellow": "🟡",
                    "red": "🔴",
                    "grey": "⚪",
                }.get(visual, "⚪")
                pad_issues = "".join(
                    f"<li>{_status_icon(False)} {i}</li>" for i in padron.get("issues", [])
                )
                pad_warns = "".join(
                    f"<li>{_status_icon(False, warn=True)} {w}</li>"
                    for w in padron.get("warnings", [])
                )
                padron_html = f"""
                    <div class="card p-3 mb-3 border-{color}">
                        <h4>{icon} Padrón DGII</h4>
                        <p class="mb-2"><strong>{padron.get('status_label') or '—'}</strong></p>
                        <div class="row">
                            <div class="col-md-6">
                                <ul class="mb-0">
                                    <li>Estado actual: {padron.get('status_label') or '—'}</li>
                                    <li>Última actualización: {padron.get('sync_date') or '—'}</li>
                                    <li>Cantidad de registros: {padron.get('count', 0)}</li>
                                    <li>Fuente: {padron.get('source') or '—'}</li>
                                    <li>Nombre del archivo: {padron.get('filename') or '—'}</li>
                                    <li>Tamaño: {padron.get('file_size') or 0} bytes</li>
                                </ul>
                            </div>
                            <div class="col-md-6">
                                <ul class="mb-0">
                                    <li>Hash: <code>{(padron.get('file_hash') or '—')[:16]}…</code></li>
                                    <li>Usuario última carga: {padron.get('user') or '—'}</li>
                                    <li>Fecha/hora importación: {padron.get('last_import_at') or '—'}</li>
                                    <li>Estado última importación: {padron.get('last_import_state') or '—'}</li>
                                    <li>Actualización automática: {'Sí' if padron.get('auto_update_enabled') else 'No'}</li>
                                    <li>Frecuencia: {padron.get('frequency_days') or 45} días</li>
                                    <li>Última ejecución: {padron.get('last_run_at') or '—'}</li>
                                    <li>Próxima ejecución: {padron.get('next_run_at') or '—'}</li>
                                    <li>Nuevos / actualizados / rechazados: {padron.get('count_new_last', 0)} / {padron.get('count_updated_last', 0)} / {padron.get('count_rejected_last', 0)}</li>
                                </ul>
                            </div>
                        </div>
                        <p class="text-muted mt-2 mb-1"><em>{padron.get('guide') or ''}</em></p>
                        <ul>{pad_issues}{pad_warns}</ul>
                    </div>
                """

            rec.dashboard_html = Markup(
                f"""
                <div class="justech-fiscal-admin o_justech_fiscal_compact">
                    <div class="row g-2 mb-3">
                        <div class="col-6 col-md-3"><div class="card p-2 h-100">
                            <div class="small text-muted">Motor NCF</div>
                            <div class="fw-bold">{_status_icon(motor_ok)} {rec.motor_status or '—'}</div>
                        </div></div>
                        <div class="col-6 col-md-3"><div class="card p-2 h-100">
                            <div class="small text-muted">Salud fiscal</div>
                            <div class="fw-bold">{_status_icon(health.get('ok'), warn=health_warn)}
                                {rec.issue_count} errores · {rec.warning_count} adv.</div>
                        </div></div>
                        <div class="col-6 col-md-3"><div class="card p-2 h-100">
                            <div class="small text-muted">Reportes DGII</div>
                            <div class="fw-bold">{_status_icon(reports_ok)} {rec.reports_status or '—'}</div>
                        </div></div>
                        <div class="col-6 col-md-3"><div class="card p-2 h-100">
                            <div class="small text-muted">Padrón DGII</div>
                            <div class="fw-bold">{_status_icon(padron.get('status') == 'ok', warn=padron.get('status') == 'warn')}
                                {padron.get('status_label') or '—'}</div>
                            <div class="small text-muted">{padron.get('count', 0)} registros · {padron.get('sync_date') or 'sin sync'}</div>
                        </div></div>
                    </div>
                    <div class="row g-2 mb-3">
                        <div class="col-12 col-lg-6"><div class="card p-2 h-100">
                            <div class="d-flex justify-content-between align-items-center mb-1">
                                <strong>Rangos NCF</strong>
                                <span class="badge text-bg-secondary">{ncf.get('total_remaining', 0)} disponibles</span>
                            </div>
                            <table class="table table-sm mb-0">
                                <thead><tr><th>Prefijo</th><th>Estado</th><th>Restantes</th><th>Uso</th></tr></thead>
                                <tbody>{ncf_rows or '<tr><td colspan="4" class="text-muted">Sin rangos activos</td></tr>'}</tbody>
                            </table>
                            <ul class="mb-0 small">{ncf_alerts}</ul>
                        </div></div>
                        <div class="col-12 col-lg-6"><div class="card p-2 h-100">
                            <strong>Retenciones / pagos</strong>
                            <ul class="mb-1">
                                <li>Catálogo activo: {pay.get('catalog_active', 0)} / {pay.get('catalog_total', 0)}</li>
                                <li>Pagos con retención: {pay.get('payments_with_withholding', 0)}</li>
                                <li>Líneas: {pay.get('withholding_lines', 0)}</li>
                            </ul>
                            <ul class="mb-0 small">{pay_inc}</ul>
                            <hr class="my-2"/>
                            <strong>Acción recomendada</strong>
                            <ul class="mb-0">{recs or '<li class="text-muted">Sin acciones pendientes</li>'}</ul>
                        </div></div>
                    </div>
                    <div class="card p-2 mb-2" invisible="0">
                        <strong>Alertas</strong>
                        <ul class="mb-0">{issues}{warns or '<li class="text-muted">Sin alertas</li>'}</ul>
                    </div>
                    <details class="mb-2">
                        <summary class="fw-semibold">Más — técnico</summary>
                        <div class="mt-2">
                            <div class="small text-muted mb-1">Última validación: {rec.last_refresh or '—'}</div>
                            <h6 class="mb-1">Módulos</h6><ul class="small">{modules_html}</ul>
                            <h6 class="mb-1">Feature flags</h6><ul class="small">{features_html}</ul>
                            <h6 class="mb-1">Multiempresa</h6>
                            <table class="table table-sm"><thead><tr><th>Empresa</th><th>Fiscal</th><th>Salud</th><th>Err</th><th>Adv</th></tr></thead>
                            <tbody>{multi_html}</tbody></table>
                            {padron_html}
                        </div>
                    </details>
                </div>
                """
            )

    @api.model
    def _user_can_open_center(self):
        """Quién puede abrir el Centro Fiscal (con distinta profundidad de UI)."""
        user = self.env.user
        return (
            user.has_group("base.group_system")
            or user.has_group("justech_fiscal_admin.group_justech_fiscal_admin_manager")
            or user.has_group("justech_l10n_do_base.group_justech_do_fiscal_manager")
            or user.has_group("justech_l10n_do_base.group_justech_do_fiscal_user")
        )

    @api.model
    def _user_denied_center_message(self):
        return _(
            "No tiene permiso para acceder al Centro de Administración Fiscal. "
            "Contacte a un administrador del sistema o Administrador Fiscal."
        )

    @api.model
    def _current_company(self):
        """Empresa activa de la sesión Odoo 19.

        En Odoo 19 ``env.company`` es la empresa activa del switcher
        (primer id de ``allowed_company_ids`` / ``cids`` de sesión).

        No se usa un ``company_id`` fijo en contexto.
        No se toma el primer singleton de la tabla.
        """
        company = self.env.company
        if not company:
            raise AccessError(_("No hay empresa activa en la sesión."))
        allowed = self.env.companies
        if company not in allowed:
            raise AccessError(
                _("La empresa activa %(c)s no está entre las empresas autorizadas.")
                % {"c": company.display_name}
            )
        return company

    @api.model
    def open_for_user(self):
        """Abre el Centro Fiscal de la empresa activa (env.company)."""
        if not self._user_can_open_center():
            raise AccessError(self._user_denied_center_message())
        # Alinear el entorno al switcher de la sesión (Odoo 19).
        company = self._current_company()
        self = self.with_company(company)
        allowed_ids = list(self.env.companies.ids)
        if company.id not in allowed_ids:
            raise AccessError(
                _("No está autorizado a operar en la empresa %(c)s.")
                % {"c": company.display_name}
            )
        # Singleton de la empresa activa — búsqueda explícita por company_id.
        center = self.sudo().search([("company_id", "=", company.id)], limit=1)
        if not center:
            center = self.sudo().create({"company_id": company.id})
        center = self.browse(center.id).with_company(company)
        if center.company_id.id != company.id:
            raise UserError(
                _(
                    "Inconsistencia de empresa: se esperaba %(exp)s y se obtuvo %(got)s."
                )
                % {
                    "exp": company.display_name,
                    "got": center.company_id.display_name,
                }
            )
        try:
            center.check_access("read")
            center._refresh()
        except AccessError:
            if center.company_id.id not in allowed_ids:
                raise
            center.sudo().with_company(company)._refresh()
            center = self.browse(center.id).with_company(company)
        return center.action_open()

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            company_id = vals.get("company_id") or self.env.company.id
            if company_id not in self.env.companies.ids and not self.env.su:
                raise AccessError(
                    _("No puede crear el Centro Fiscal para una empresa no autorizada.")
                )
            existing = self.sudo().search([("company_id", "=", company_id)], limit=1)
            if existing:
                raise UserError(
                    _(
                        "Ya existe un Centro Fiscal para esta empresa. "
                        "No se permiten registros duplicados."
                    )
                )
        return super().create(vals_list)

    def _refresh(self):
        """Recalcula el dashboard exclusivamente para ``self.company_id``.

        La empresa del registro debe coincidir con la activa al abrir desde el menú.
        Salud, NCF, pagos y retenciones se filtran por esa empresa.
        Multiempresa del resumen solo incluye ``env.companies`` (autorizadas).
        """
        self.ensure_one()
        company = self.company_id
        allowed_ids = list(self.env.companies.ids)
        if company.id not in allowed_ids and not self.env.su:
            raise AccessError(
                _("Empresa no autorizada para este usuario: %s") % company.display_name
            )
        # Forzar contexto de cálculo a la empresa del centro.
        # with_company puede no existir en algunos entornos; pasar company explícito.
        svc = self.env["justech.fiscal.admin.service"]
        if hasattr(svc, "with_company"):
            svc = svc.with_company(company)
        stack = svc.stack_status(company)
        health = svc.health_check(company)
        payments = svc.payments_withholding_status(company)
        ncf = svc.ncf_consumption_summary(company)
        padron = {}
        if "justech.do.rnc.padron.import.service" in self.env:
            # Estado global: visible a todos los roles con acceso al Centro.
            padron = (
                self.env["justech.do.rnc.padron.import.service"]
                .sudo()
                .status_payload()
            )
        self.sudo().write(
            {
                "stack_json": json.dumps(stack, ensure_ascii=False, default=str),
                "health_json": json.dumps(
                    {
                        "ok": health["ok"],
                        "issues": health["issues"],
                        "warnings": health["warnings"],
                        "recommendations": health["recommendations"],
                        "gl_balanced": health["gl_balanced"],
                        "findings": health.get("findings") or [],
                    },
                    ensure_ascii=False,
                    default=str,
                ),
                "health_findings_json": json.dumps(
                    health.get("findings") or [], ensure_ascii=False, default=str
                ),
                "payments_json": json.dumps(payments, ensure_ascii=False, default=str),
                "ncf_json": json.dumps(ncf, ensure_ascii=False, default=str),
                "padron_json": json.dumps(padron, ensure_ascii=False, default=str),
                "last_refresh": fields.Datetime.now(),
                "health_ok": health["ok"],
                "issue_count": len(health["issues"]),
                "warning_count": len(health["warnings"]),
                "motor_status": _("Activo") if stack.get("motor_active") else _("Inactivo"),
                "provider_status": _("Solo lectura histórica"),
                "reports_status": _("Activo") if stack.get("reports_active") else _("Inactivo"),
            }
        )

    def action_open(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _(
                "Centro Fiscal — %(company)s",
                company=self.company_id.display_name,
            ),
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "current",
            "context": {
                "create": False,
                "delete": False,
                # Conservar empresas autorizadas de la sesión; no fijar company_id.
                "allowed_company_ids": self.env.companies.ids,
            },
        }

    def action_refresh(self):
        self._refresh()
        return False

    def action_run_health_check(self):
        self._refresh()
        return self.action_open_health_detail()

    def action_open_health_detail(self):
        """Abre el detalle estructurado de Salud Fiscal."""
        self.ensure_one()
        self._refresh()
        # Filtrar hallazgos a la empresa del centro (nunca cruzar otras)
        findings = [
            f
            for f in json.loads(self.health_findings_json or "[]")
            if not f.get("company_id") or f.get("company_id") == self.company_id.id
        ]
        Issue = self.env["justech.fiscal.health.issue"].sudo()
        # limpiar líneas previas de este centro
        Issue.search([("center_id", "=", self.id)]).unlink()
        vals_list = []
        for f in findings:
            vals_list.append(
                {
                    "center_id": self.id,
                    "company_id": f.get("company_id") or self.company_id.id,
                    "code": f.get("code") or "GEN",
                    "name": f.get("name") or "",
                    "severity": f.get("severity") or "medium",
                    "severity_rank": f.get("severity_rank") or 50,
                    "impact": f.get("impact") or "",
                    "model_name": f.get("model_name") or "",
                    "res_model": f.get("res_model") or False,
                    "res_id": f.get("res_id") or 0,
                    "recommended_action": f.get("recommended_action") or "",
                    "cause": f.get("cause") or "",
                    "category": f.get("category") or "error",
                    "state": "open",
                }
            )
        if vals_list:
            Issue.create(vals_list)
        return {
            "type": "ir.actions.act_window",
            "name": _("Salud Fiscal — Detalle"),
            "res_model": "justech.fiscal.health.issue",
            "view_mode": "list,form",
            "domain": [("center_id", "=", self.id)],
            "target": "current",
            "context": {"create": False, "delete": False},
        }

    def action_open_fiscal_users(self):
        if not self.can_manage_users:
            raise AccessError(_("Solo Administradores Fiscales pueden gestionar roles."))
        return {
            "type": "ir.actions.act_window",
            "name": _("Usuarios y permisos fiscales"),
            "res_model": "res.users",
            "view_mode": "list,form",
            "domain": [
                "|",
                ("group_ids", "in", [
                    self.env.ref("justech_l10n_do_base.group_justech_do_fiscal_user").id,
                    self.env.ref("justech_l10n_do_base.group_justech_do_fiscal_manager").id,
                    self.env.ref("justech_fiscal_admin.group_justech_fiscal_admin_manager").id,
                ]),
                ("share", "=", False),
            ],
            "context": {"search_default_filter_no_share": 1},
        }

    def action_open_feature_flags(self):
        if not (
            self.env.user.has_group("base.group_system")
            or self.env.user.has_group(
                "justech_fiscal_admin.group_justech_fiscal_admin_manager"
            )
        ):
            raise AccessError(
                _("No tiene permiso para administrar Feature Flags fiscales.")
            )
        return {
            "type": "ir.actions.act_window",
            "name": _("Feature Flags Fiscales"),
            "res_model": "justech.fiscal.feature.flag",
            "view_mode": "list,form",
            "domain": [
                "|",
                ("company_id", "=", False),
                ("company_id", "=", self.company_id.id),
            ],
            "context": {
                "default_company_id": self.company_id.id,
                "create": self.env.user.has_group("base.group_system"),
            },
        }

    def action_open_ncf_ranges(self):
        return self.env["justech.do.fiscal.range.center"].action_open()

    def action_open_purchase_received_types(self):
        return self.env.ref(
            "justech_l10n_do_ncf.action_justech_do_purchase_received_types"
        ).read()[0]

    def action_open_purchase_emission_config(self):
        action = self.env.ref(
            "justech_l10n_do_ncf.action_justech_do_purchase_emission_config"
        ).read()[0]
        action["domain"] = [("company_id", "=", self.company_id.id)]
        action["context"] = {
            "default_company_id": self.company_id.id,
            "search_default_company_id": self.company_id.id,
        }
        return action

    def action_open_purchase_expense_types(self):
        return self.env.ref(
            "justech_l10n_do_base.action_justech_do_dgii_expense_type"
        ).read()[0]

    def action_open_purchase_ncf_ranges(self):
        return {
            "type": "ir.actions.act_window",
            "name": _("Rangos de Compras"),
            "res_model": "justech.do.ncf.range",
            "view_mode": "list,form",
            "domain": [
                ("company_id", "=", self.company_id.id),
                ("prefix", "in", ("B11", "B13", "B17")),
            ],
            "context": {"default_company_id": self.company_id.id},
        }

    def action_open_purchase_incidents(self):
        return self.action_open_diagnostic()

    def action_open_diagnostic(self):
        wizard = self.env["justech.do.fiscal.diagnostic.wizard"].create(
            {"company_id": self.company_id.id}
        )
        wizard.action_run_scan()
        return {
            "type": "ir.actions.act_window",
            "name": _("Diagnóstico Fiscal"),
            "res_model": "justech.do.fiscal.diagnostic.wizard",
            "res_id": wizard.id,
            "view_mode": "form",
            "target": "new",
        }

    def action_open_dgii_reports(self):
        mod = self.env["ir.module.module"].search(
            [("name", "=", "justech_l10n_do_reports"), ("state", "=", "installed")],
            limit=1,
        )
        if not mod:
            raise UserError(_("Instale el módulo Justech Reportes DGII."))
        return self.env.ref("justech_l10n_do_reports.action_justech_do_fiscal_report").read()[0]

    def action_open_ncf_admin(self):
        if not self.can_open_ncf_admin:
            raise AccessError(
                _("El Usuario Fiscal no administra el Centro NCF; use Rangos NCF.")
            )
        return self.env["justech.do.ncf.admin.center"].open_for_user(self.env)

    def action_open_withholding_catalog(self):
        mod = self.env["ir.module.module"].search(
            [("name", "=", "justech_l10n_do_payments_withholding"), ("state", "=", "installed")],
            limit=1,
        )
        if not mod:
            raise UserError(_("Instale el módulo Pagos y Retenciones Justech."))
        return self.env.ref(
            "justech_l10n_do_payments_withholding.action_justech_withholding_catalog"
        ).read()[0]

    def action_sync_withholding_catalog(self):
        if not self.is_fiscal_admin:
            raise AccessError(_("Solo Administradores Fiscales pueden sincronizar retenciones."))
        if "justech.do.withholding.catalog" not in self.env:
            raise UserError(_("Catálogo de retenciones no disponible."))
        self.env["justech.do.withholding.catalog"].sync_catalog_from_taxes(self.company_id)
        self._refresh()
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Catálogo sincronizado"),
                "message": _("Retenciones actualizadas desde impuestos l10n_do."),
                "type": "success",
            },
        }

    def _padron_require_system(self):
        if not (
            self.env.user.has_group("base.group_system")
            or self.env.user.has_group(
                "justech_fiscal_admin.group_justech_fiscal_admin_manager"
            )
        ):
            raise UserError(
                _(
                    "Solo Administradores del Sistema o Administradores Fiscales "
                    "pueden administrar el padrón DGII."
                )
            )

    def action_padron_import(self):
        self._padron_require_system()
        empty = self.env["justech.do.rnc.padron"].sudo().search_count([]) == 0
        return {
            "type": "ir.actions.act_window",
            "name": _("Importar padrón DGII") if empty else _("Actualizar padrón DGII"),
            "res_model": "justech.do.rnc.padron.import.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_mode": "import" if empty else "update"},
        }

    def action_padron_history(self):
        self._padron_require_system()
        return {
            "type": "ir.actions.act_window",
            "name": _("Historial padrón DGII"),
            "res_model": "justech.do.rnc.padron.import.log",
            "view_mode": "list,form",
            "target": "current",
        }

    def action_padron_integrity(self):
        self._padron_require_system()
        result = self.env["justech.do.rnc.padron.import.service"].integrity_check()
        self._refresh()
        body = "\n".join(result.get("issues", []) + result.get("warnings", []))
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Integridad padrón: %s") % result.get("status_visual"),
                "message": body
                or _("OK — %(n)s registros.") % {"n": result.get("count", 0)},
                "type": "success" if result.get("status_visual") == "green" else "warning",
                "sticky": result.get("status_visual") in ("red", "yellow"),
            },
        }

    def action_padron_retry_last(self):
        self._padron_require_system()
        return self.env["justech.do.rnc.padron.auto.service"].retry_last_failed()

    def action_padron_reimport_after_restore(self):
        """Tras restore de BD sin padrón: abre wizard de importación global."""
        self._padron_require_system()
        count = self.env["justech.do.rnc.padron"].sudo().search_count([])
        if count > 0:
            raise UserError(
                _(
                    "El padrón global ya tiene %(n)s registros. "
                    "Use «Actualizar ahora» o importación manual si necesita refrescar."
                )
                % {"n": count}
            )
        return {
            "type": "ir.actions.act_window",
            "name": _("Reimportar padrón DGII tras restore"),
            "res_model": "justech.do.rnc.padron.import.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_mode": "import"},
        }

    def action_padron_config(self):
        self._padron_require_system()
        config = self.env["justech.do.rnc.padron.config"].get_config()
        return {
            "type": "ir.actions.act_window",
            "name": _("Configurar actualización automática"),
            "res_model": "justech.do.rnc.padron.config",
            "res_id": config.id,
            "view_mode": "form",
            "target": "new",
        }

    def action_padron_update_now(self):
        self._padron_require_system()
        return self.env["justech.do.rnc.padron.auto.service"].run_auto_update(force=True)
