from odoo import api, fields, models, _


class JustechAdminHealthService(models.AbstractModel):
    _name = "justech.admin.health.service"
    _description = "Diagnóstico y health checks Justech Admin"

    @api.model
    def run_global_diagnostics(self):
        Finding = self.env["justech.admin.health.finding"].sudo()
        Finding.search([("state", "=", "open"), ("code", "like", "JAC_%")]).write({"state": "resolved"})
        # Close informational noise from prior runs
        Finding.search([("severity", "=", "info"), ("state", "in", ["open", "in_progress"])]).write(
            {"state": "resolved"}
        )
        findings = []

        sys_group = self.env.ref("base.group_system")
        admins = self.env["res.users"].sudo().search([("group_ids", "in", sys_group.id)])
        if not admins:
            findings.append(
                self._f(
                    "JAC_NO_SYSTEM_ADMIN",
                    "critical",
                    _("Sin Administrador del Sistema"),
                    _("Debe existir al menos un administrador del sistema."),
                )
            )

        jac_group = self.env.ref("justech_admin_center.group_justech_admin_center_manager")
        jac_managers = self.env["res.users"].sudo().search([("group_ids", "in", jac_group.id)])
        if not jac_managers and not admins:
            findings.append(
                self._f(
                    "JAC_NO_JAC_ADMIN",
                    "critical",
                    _("Sin Administrador Justech"),
                    _("Asigne el rol Administrador Justech a un usuario."),
                )
            )

        lonely = self.env["res.users"].sudo().search([("share", "=", False), ("company_ids", "=", False)])
        for u in lonely[:10]:
            findings.append(
                self._f(
                    "JAC_USER_NO_COMPANY",
                    "error",
                    _("Usuario sin empresa: %s") % u.login,
                    _("Asigne al menos una empresa."),
                    res_model="res.users",
                    res_id=u.id,
                )
            )

        IrModule = self.env["ir.module.module"].sudo()
        registered_names = set(
            self.env["justech.admin.module"].sudo().search([]).mapped("technical_name")
        )
        for irm in IrModule.search([("name", "=like", "justech_%"), ("state", "=", "installed")]):
            if irm.name not in registered_names:
                findings.append(
                    self._f(
                        "JAC_UNREGISTERED",
                        "warning",
                        _("Módulo instalado sin registro: %s") % irm.name,
                        _("Ejecute sincronización del catálogo."),
                    )
                )

        fiscal_enabled_anywhere = False
        if "justech_do_fiscal_enabled" in self.env["res.company"]._fields:
            fiscal_enabled_anywhere = any(
                self.env["res.company"].sudo().search([]).mapped("justech_do_fiscal_enabled")
            )
        for mod in self.env["justech.admin.module"].sudo().search(
            [("functional_state", "=", "active"), ("technical_state", "=", "installed")]
        ):
            if mod.category == "fiscal" and "justech_do_fiscal_enabled" in self.env["res.company"]._fields:
                if not fiscal_enabled_anywhere:
                    findings.append(
                        self._f(
                            "JAC_FISCAL_ACTIVE_NO_CO",
                            "warning",
                            _("Fiscal activo sin empresa fiscal"),
                            _("Active fiscal por empresa o desactive el módulo."),
                            module=mod,
                        )
                    )

        for vals in findings:
            Finding.create(vals)

        for mod in self.env["justech.admin.module"].search([("technical_state", "=", "installed")]):
            self.run_module_health(mod, create_findings=True, open_findings=False)

        return self.env["justech.admin.console"]._ensure_singleton().action_open_pending_center()

    @api.model
    def run_module_health(self, module, create_findings=True, open_findings=False):
        module.ensure_one()
        Finding = self.env["justech.admin.health.finding"].sudo()
        checks = list(self._product_checks(module))

        if module.health_method:
            try:
                custom = self._invoke_health_method(module.health_method, module)
                checks.append(("health_method", "info", _("Método propio"), str(custom)[:300], _("Revisar detalle")))
            except Exception as exc:
                checks.append(("health_method", "error", _("Health falló"), str(exc)[:300], _("Corregir método")))

        if create_findings:
            Finding.search(
                [
                    ("module_id", "=", module.id),
                    ("state", "in", ["open", "in_progress"]),
                    ("code", "like", "JAC_M_%"),
                ]
            ).write({"state": "resolved"})
            for check in checks:
                code, severity, name, detail, reco = check[:5]
                if severity == "info":
                    continue
                extra = check[5] if len(check) > 5 and isinstance(check[5], dict) else {}
                Finding.create(
                    self._f(
                        "JAC_M_%s_%s" % (module.technical_name, code),
                        severity,
                        name,
                        detail,
                        module=module,
                        recommendation=reco,
                        **extra,
                    )
                )

        worst = "info"
        for check in checks:
            sev = check[1]
            if sev == "critical":
                worst = "critical"
            elif sev == "error" and worst not in ("critical",):
                worst = "error"
            elif sev == "warning" and worst in ("info",):
                worst = "warning"
        summary = _("; ").join("%s:%s" % (c[0], c[1]) for c in checks[:8]) or _("OK")
        module.write({"last_health_at": fields.Datetime.now(), "last_health_summary": summary[:500]})
        if worst in ("error", "critical"):
            module.functional_state = "error"

        if open_findings:
            return {
                "type": "ir.actions.act_window",
                "name": _("Pendientes — %s") % module.functional_name,
                "res_model": "justech.admin.health.finding",
                "view_mode": "kanban,list,form",
                "domain": [
                    ("module_id", "=", module.id),
                    ("state", "in", ["open", "in_progress"]),
                ],
                "target": "current",
            }
        return True

    @api.model
    def _product_checks(self, module):
        """Controles reales mínimos por submódulo."""
        tech = module.technical_name
        IrModule = self.env["ir.module.module"].sudo()
        irm = IrModule.search([("name", "=", tech)], limit=1)
        if not irm or irm.state != "installed":
            yield ("installed", "error", _("Módulo instalado"), _("No instalado"), _("Instalar módulo"))
            return
        yield ("installed", "info", _("Módulo instalado"), _("Estado: %s") % irm.state, _("OK"))
        yield ("registry", "info", _("Registry Odoo"), _("Cargado en registry"), _("OK"))

        # Dependencias declaradas
        missing = []
        for dep in irm.dependencies_id.filtered(lambda d: d.depend_id.state != "installed"):
            missing.append(dep.depend_id.name)
        if missing:
            yield (
                "deps",
                "error",
                _("Dependencias"),
                _("Faltan: %s") % ", ".join(missing[:10]),
                _("Instalar dependencias"),
            )
        else:
            yield ("deps", "info", _("Dependencias"), _("Satisfactorias"), _("OK"))

        companies = self.env["res.company"].sudo().search_count([])
        yield (
            "companies",
            "info",
            _("Empresas"),
            _("%s empresas en la base") % companies,
            _("OK"),
        )

        if tech == "justech_l10n_do_base" and "justech.do.rnc.padron" in self.env:
            n = self.env["justech.do.rnc.padron"].sudo().search_count([])
            sev = "info" if n else "warning"
            yield (
                "padron_data",
                sev,
                _("Datos del padrón"),
                _("%s registros") % n,
                _("Importar padrón") if not n else _("OK"),
            )
            if "justech.do.rnc.padron.config" in self.env:
                cfg = self.env["justech.do.rnc.padron.config"].sudo().get_config()
                yield (
                    "padron_cron",
                    "info" if cfg.cron_active else "warning",
                    _("Cron padrón"),
                    _("Activo=%s · próxima=%s") % (cfg.cron_active, cfg.next_run_at),
                    _("Activar cron 45 días") if not cfg.cron_active else _("OK"),
                )

        if tech == "justech_l10n_do_ncf" and "justech.do.ncf.range" in self.env:
            ranges = self.env["justech.do.ncf.range"].sudo().search_count([])
            yield (
                "ncf_ranges",
                "info" if ranges else "warning",
                _("Rangos NCF"),
                _("%s rangos") % ranges,
                _("Configurar rangos") if not ranges else _("OK"),
            )

        if tech.startswith("justech_ecf") and "justech.ecf.company.config" in self.env:
            Config = self.env["justech.ecf.company.config"].sudo()
            companies = self.env["res.company"].sudo().search([])
            cfg_by_company = {
                cfg.company_id.id: cfg
                for cfg in Config.search([("company_id", "in", companies.ids)])
            }
            for company in companies:
                cfg = cfg_by_company.get(company.id)
                if not cfg:
                    yield (
                        "ecf_cfg_%s" % company.id,
                        "warning",
                        _("e-CF sin configurar — %s") % company.name,
                        _("La empresa no tiene configuración e-CF."),
                        _("Configurar e-CF"),
                        {
                            "company_id": company.id,
                            "impact": _("No se pueden emitir comprobantes electrónicos."),
                            "action_label": _("Configurar e-CF"),
                            "responsible_hint": _("Administrador fiscal"),
                            "resolve_xmlid": "justech_ecf_admin.action_justech_ecf_admin_hub",
                        },
                    )
                    continue
                if not cfg.certificate_id:
                    yield (
                        "ecf_cert_%s" % company.id,
                        "warning",
                        _("Certificado e-CF pendiente — %s") % company.name,
                        _("Falta cargar y validar el certificado digital."),
                        _("Cargar certificado"),
                        {
                            "company_id": company.id,
                            "impact": _("No se pueden firmar comprobantes electrónicos."),
                            "action_label": _("Configurar certificado"),
                            "responsible_hint": _("Administrador fiscal"),
                            "resolve_xmlid": "justech_ecf_core.action_justech_ecf_certificate",
                        },
                    )
                else:
                    yield (
                        "ecf_cfg_%s" % company.id,
                        "info",
                        _("e-CF configurado — %s") % company.name,
                        _("Certificado asignado."),
                        _("OK"),
                        {"company_id": company.id},
                    )

        if tech == "justech_warranty" and "justech.warranty" in self.env:
            # model name may vary — soft check
            yield ("warranty", "info", _("Garantías"), _("Módulo instalado"), _("OK"))

        if tech == "justech_global_audit_log" and "justech.audit.log" in self.env:
            n = self.env["justech.audit.log"].sudo().search_count([])
            yield ("audit_logs", "info", _("Logs de auditoría"), _("%s eventos") % n, _("OK"))

    @api.model
    def _invoke_health_method(self, dotted, module):
        parts = dotted.rsplit(".", 1)
        if len(parts) != 2:
            return None
        model_name, method = parts
        if model_name not in self.env:
            return _("Método no disponible (%s)") % model_name
        obj = self.env[model_name].sudo()
        meth = getattr(obj, method, None)
        if not callable(meth):
            return _("Método inexistente")
        try:
            result = meth(self.env.company)
        except TypeError:
            result = meth()
        if isinstance(result, list):
            errors = [
                f
                for f in result
                if isinstance(f, dict) and str(f.get("severity", "")).lower() in ("error", "critical")
            ]
            return _("%s hallazgos (%s errores)") % (len(result), len(errors))
        return str(result)[:200]

    @api.model
    def _f(
        self,
        code,
        severity,
        name,
        detail,
        module=None,
        res_model=None,
        res_id=None,
        recommendation=None,
        company_id=None,
        impact=None,
        action_label=None,
        responsible_hint=None,
        resolve_xmlid=None,
        **kwargs,
    ):
        vals = {
            "code": code,
            "severity": severity,
            "name": name,
            "detail": detail,
            "recommendation": recommendation or detail,
            "impact": impact or detail,
            "action_label": action_label or _("Resolver"),
            "responsible_hint": responsible_hint or _("Administrador Justech"),
            "module_id": module.id if module else False,
            "res_model": res_model,
            "res_id": res_id or 0,
            "company_id": company_id or False,
            "resolve_xmlid": resolve_xmlid or False,
            "state": "open",
            "detected_at": fields.Datetime.now(),
        }
        vals.update({k: v for k, v in kwargs.items() if k in vals or True})
        # Keep only known fields
        return {
            k: v
            for k, v in vals.items()
            if k
            in {
                "code",
                "severity",
                "name",
                "detail",
                "recommendation",
                "impact",
                "action_label",
                "responsible_hint",
                "module_id",
                "res_model",
                "res_id",
                "company_id",
                "resolve_xmlid",
                "state",
                "detected_at",
            }
        }
