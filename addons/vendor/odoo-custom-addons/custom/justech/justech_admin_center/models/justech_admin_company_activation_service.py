from odoo import api, fields, models, _
from odoo.exceptions import UserError


STATE_LABELS = {
    "unconfigured": "No configurado",
    "inactive": "Inactivo",
    "active": "Activo",
    "blocked": "Bloqueado",
    "attention": "Requiere atención",
    "error": "Error",
    "none": "Sin motor",
    "traditional_ncf": "NCF tradicional",
    "electronic": "Facturación electrónica",
}

# Qué habilita cada familia al activar (sin mezclar NCF en Garantías, etc.)
ENABLES_BY_PRODUCT = {
    "warranty": [
        "Registro de garantías",
        "Seguimiento de garantías",
        "Consulta por cliente",
        "Roles de garantías",
        "Menús operativos de garantías",
    ],
    "fiscal": [
        "Operaciones fiscales nuevas en la empresa",
        "Emisión y control según el submódulo",
        "Menús y roles fiscales relacionados",
    ],
    "finance": [
        "Cobros, pagos o tesorería según el submódulo",
        "Menús operativos financieros",
        "Roles de finanzas relacionados",
    ],
    "core": [
        "Servicios de plataforma Justech",
        "Integración con otros productos",
    ],
    "audit": [
        "Registro de auditoría y diagnósticos",
    ],
    "integrations": [
        "Conexiones con servicios externos",
    ],
}

ENABLES_BY_TECH = {
    "justech_warranty": [
        "Registro de garantías",
        "Seguimiento de garantías",
        "Consulta por cliente",
        "Roles de garantías",
        "Menús operativos",
    ],
    "justech_l10n_do_ncf": [
        "Asignación de NCF",
        "Control de rangos y secuencias",
        "Emisión fiscal según motor de la empresa",
    ],
    "justech_l10n_do_reports": [
        "Generación de reportes 606, 607, 608, 609 y 623",
        "Validaciones e historial de declaraciones",
    ],
    "justech_l10n_do_treasury": [
        "Cobros y pagos",
        "Pagos abiertos",
        "Flujos de tesorería",
    ],
    "justech_l10n_do_payments_withholding": [
        "Retenciones en cobros y pagos",
        "Reglas operativas de retención",
    ],
    "justech_fiscal_admin": [
        "Resumen de salud fiscal",
        "Alertas y permisos fiscales por empresa",
    ],
}


class JustechAdminCompanyActivationService(models.AbstractModel):
    _name = "justech.admin.company.activation.service"
    _description = "Activación funcional Justech por empresa"

    @api.model
    def _label(self, value):
        return STATE_LABELS.get(value, value or "—")

    @api.model
    def _enables_for(self, module):
        if module.technical_name in ENABLES_BY_TECH:
            return ENABLES_BY_TECH[module.technical_name]
        code = module.product_id.code if module.product_id else "core"
        return ENABLES_BY_PRODUCT.get(code, ["Funciones operativas del submódulo en la empresa"])

    @api.model
    def _no_impact_for(self, module):
        code = module.product_id.code if module.product_id else ""
        if code == "warranty":
            return _(
                "No se modificará: ventas históricas, facturas, contabilidad ni garantías ya registradas."
            )
        if code == "finance":
            return _(
                "No se modificará: pagos históricos, asientos publicados ni conciliación cerrada."
            )
        if code == "fiscal":
            return _(
                "No se modificará: NCF ya emitidos, facturas históricas, reportes generados ni contabilidad publicada."
            )
        return _(
            "No se modificará el histórico operativo ni la contabilidad publicada."
        )

    @api.model
    def build_preview(self, line, operation, new_engine=None):
        line.ensure_one()
        module = line.module_id
        company = line.company_id
        if module.activation_scope == "global":
            raise UserError(
                _(
                    "%s es un componente global de la base. "
                    "No se activa ni desactiva por empresa."
                )
                % module.functional_name
            )

        before_state = self._label(line.functional_state)
        before_engine = self._label(line.fiscal_engine) if module.fiscal_engine_capable else False
        after_state = before_state
        after_engine = before_engine
        risks = []
        title = _("Activar producto")
        enables = self._enables_for(module)

        if operation == "activate":
            title = _("Activar — %s") % module.functional_name
            after_state = self._label("active")
            if module.fiscal_engine_capable:
                eng = new_engine or (
                    line.fiscal_engine if line.fiscal_engine != "none" else "traditional_ncf"
                )
                after_engine = self._label(eng)
            risks.append(_("Se habilitarán operaciones nuevas de este submódulo en la empresa."))
        elif operation == "deactivate":
            title = _("Desactivar — %s") % module.functional_name
            after_state = self._label("inactive")
            risks.append(_("Se bloquearán nuevas operaciones; el histórico se conserva."))
            if module.is_critical:
                others = self.env["justech.admin.module.company"].search(
                    [
                        ("module_id", "=", module.id),
                        ("id", "!=", line.id),
                        ("functional_state", "=", "active"),
                    ]
                )
                if not others:
                    risks.append(
                        _("Advertencia: ninguna otra empresa tendrá este submódulo crítico activo.")
                    )
        elif operation == "engine":
            title = _("Cambiar motor fiscal — %s") % company.name
            if not module.fiscal_engine_capable:
                raise UserError(_("Este submódulo no admite selección de motor fiscal."))
            if not new_engine:
                raise UserError(_("Seleccione el motor fiscal destino."))
            after_engine = self._label(new_engine)
            after_state = self._label("active")
            risks.append(
                _("No se permite emitir con dos motores incompatibles en la misma empresa.")
            )
            enables = [
                _("Motor fiscal unificado en la empresa: %s") % after_engine,
            ]

        setup_needed = [
            _("Revisar responsables y permisos de la empresa"),
            _("Completar parámetros requeridos del submódulo antes de operar"),
        ]
        if module.fiscal_engine_capable and operation in ("activate", "engine"):
            setup_needed.append(_("Confirmar el motor fiscal (NCF tradicional o electrónico)"))

        return {
            "title": title,
            "product_name": module.product_id.name if module.product_id else module.functional_name,
            "module_name": module.functional_name,
            "company_name": company.name,
            "before_state": before_state,
            "after_state": after_state,
            "before_engine": before_engine or "",
            "after_engine": after_engine or "",
            "enables_text": "\n".join("• %s" % e for e in enables),
            "setup_text": "\n".join("• %s" % s for s in setup_needed),
            "risks": "\n".join(risks),
            "no_impact": self._no_impact_for(module),
            "rollback": _("Puede revertir el estado funcional desde la misma consola."),
            # compat keys for audit log (human readable)
            "before": {
                "empresa": company.name,
                "submodulo": module.functional_name,
                "estado": before_state,
                "motor": before_engine or "—",
            },
            "after": {
                "empresa": company.name,
                "submodulo": module.functional_name,
                "estado": after_state,
                "motor": after_engine or "—",
            },
        }

    @api.model
    def apply(self, line, operation, new_engine=None):
        self.env["justech.admin.center.auth.service"].require_session()
        preview = self.build_preview(line, operation, new_engine=new_engine)
        module = line.module_id
        company = line.company_id
        vals = {
            "last_change_at": fields.Datetime.now(),
            "last_change_uid": self.env.uid,
        }
        if operation == "activate":
            vals["functional_state"] = "active"
            engine = new_engine or (
                line.fiscal_engine if line.fiscal_engine != "none" else "traditional_ncf"
            )
            if module.fiscal_engine_capable:
                vals["fiscal_engine"] = engine
                self._unify_company_engine(company, engine, prefer_line=line)
            self._sync_company_flags(module, company, enabled=True)
            self._sync_fiscal_enabled(company, enabled=True)
        elif operation == "deactivate":
            vals["functional_state"] = "inactive"
            self._sync_company_flags(module, company, enabled=False)
        elif operation == "engine":
            vals["fiscal_engine"] = new_engine
            vals["functional_state"] = "active"
            self._unify_company_engine(company, new_engine, prefer_line=line)
            self._sync_company_flags(module, company, enabled=True)
            self._sync_fiscal_enabled(company, enabled=True)
        line.write(vals)
        active_any = self.env["justech.admin.module.company"].search_count(
            [("module_id", "=", module.id), ("functional_state", "=", "active")]
        )
        module.write({"functional_state": "active" if active_any else "inactive"})
        self.env["justech.admin.audit.log"].sudo().log_simple(
            summary=_("%s / %s → %s") % (module.functional_name, company.name, operation),
            operation=operation,
            module_id=module.id,
            state_before="%s → %s" % (preview["before_state"], preview.get("before_engine") or "—"),
            state_after="%s → %s" % (preview["after_state"], preview.get("after_engine") or "—"),
            reason=preview["risks"],
        )
        return preview

    @api.model
    def _unify_company_engine(self, company, engine, prefer_line=None):
        Line = self.env["justech.admin.module.company"]
        domain = [
            ("company_id", "=", company.id),
            ("module_id.fiscal_engine_capable", "=", True),
        ]
        lines = Line.search(domain)
        for other in lines:
            if prefer_line and other.id == prefer_line.id:
                continue
            other.write({"fiscal_engine": engine, "functional_state": "active"})

    @api.model
    def _sync_company_flags(self, module, company, enabled):
        codes = [c.strip() for c in (module.feature_flag_codes or "").split(",") if c.strip()]
        if not codes or "justech.fiscal.feature.flag" not in self.env:
            return
        Flag = self.env["justech.fiscal.feature.flag"].sudo()
        for code in codes:
            flag = Flag.search([("code", "=", code), ("company_id", "=", company.id)], limit=1)
            if not flag:
                flag = Flag.search([("code", "=", code), ("company_id", "=", False)], limit=1)
            if not flag:
                continue
            if "is_enabled" in Flag._fields:
                if flag.company_id:
                    flag.write({"is_enabled": enabled})
                else:
                    existing = Flag.search([("code", "=", code), ("company_id", "=", company.id)], limit=1)
                    if existing:
                        existing.write({"is_enabled": enabled})
                    else:
                        try:
                            Flag.create(
                                {
                                    "code": code,
                                    "company_id": company.id,
                                    "is_enabled": enabled,
                                    "name": code,
                                }
                            )
                        except Exception:
                            flag.write({"is_enabled": enabled})
            elif "enabled" in Flag._fields:
                flag.write({"enabled": enabled})

    @api.model
    def _sync_fiscal_enabled(self, company, enabled):
        if "justech_do_fiscal_enabled" in company._fields:
            company.sudo().write({"justech_do_fiscal_enabled": enabled})

    @api.model
    def ensure_lines_for_module(self, module):
        if module.technical_state != "installed":
            return
        # Global modules: optional informational lines, all marked active (shared)
        Company = self.env["res.company"].sudo()
        Line = self.env["justech.admin.module.company"].sudo()
        for company in Company.search([]):
            existing = Line.search(
                [("module_id", "=", module.id), ("company_id", "=", company.id)], limit=1
            )
            if existing:
                if module.activation_scope == "global" and existing.functional_state == "unconfigured":
                    existing.write({"functional_state": "active"})
                continue
            state = "active" if module.activation_scope == "global" else "unconfigured"
            engine = "none"
            if module.fiscal_engine_capable and getattr(company, "justech_do_fiscal_enabled", False):
                state = "active"
                engine = "traditional_ncf"
            Line.create(
                {
                    "module_id": module.id,
                    "company_id": company.id,
                    "functional_state": state,
                    "fiscal_engine": engine if module.fiscal_engine_capable else "none",
                }
            )
