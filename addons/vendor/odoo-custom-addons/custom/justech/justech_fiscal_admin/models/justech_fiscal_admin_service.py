# -*- coding: utf-8 -*-
"""Servicio de administración fiscal — stack, salud, integridad."""
from odoo import _, fields, models


FISCAL_MODULES = (
    "justech_l10n_do_base",
    "justech_l10n_do_ncf",
    "justech_l10n_do_reports",
    "justech_l10n_do_dashboard",
    "justech_l10n_do_payments_withholding",
    "justech_fiscal_admin",
)


class JustechFiscalAdminService(models.AbstractModel):
    _name = "justech.fiscal.admin.service"
    _description = "Justech Fiscal Administration Service"

    def stack_status(self, company=None):
        company = company or self.env.company
        Module = self.env["ir.module.module"]
        rows = []
        for name in FISCAL_MODULES:
            mod = Module.search([("name", "=", name)], limit=1)
            rows.append(
                {
                    "name": name,
                    "state": mod.state if mod else "uninstalled",
                    "version": mod.latest_version if mod else "—",
                    "installed": mod.state == "installed" if mod else False,
                }
            )
        flags = self.env["justech.fiscal.feature.flag"].sudo()
        feature_rows = []
        for flag in flags.search(
            ["|", ("company_id", "=", False), ("company_id", "=", company.id)],
            order="sequence",
        ):
            effective = flags.is_enabled(flag.code, company)
            feature_rows.append(
                {
                    "code": flag.code,
                    "name": flag.name,
                    "category": flag.category,
                    "enabled": effective,
                    "readonly": flag.readonly_flag,
                }
            )
        return {
            "company": {"id": company.id, "name": company.name},
            "modules": rows,
            "features": feature_rows,
            "fiscal_enabled": company.justech_do_fiscal_enabled,
            "motor_active": company.justech_do_fiscal_enabled
            and flags.is_enabled("ncf_motor", company),
            "provider_mode": "historical_read_only",
            "reports_active": flags.is_enabled("dgii_reports", company),
            "dashboard_active": flags.is_enabled("fiscal_dashboard", company),
        }

    def _severity_rank(self, severity):
        return {
            "critical": 10,
            "high": 20,
            "medium": 30,
            "low": 40,
            "info": 50,
        }.get(severity, 50)

    def _finding(
        self,
        code,
        name,
        severity,
        company,
        category="error",
        impact=None,
        model_name=None,
        res_model=None,
        res_id=None,
        action=None,
    ):
        return {
            "code": code,
            "name": name,
            "severity": severity,
            "severity_rank": self._severity_rank(severity),
            "category": category,
            "company_id": company.id,
            "company_name": company.display_name,
            "impact": impact or "",
            "model_name": model_name or "",
            "res_model": res_model or "",
            "res_id": res_id or 0,
            "recommended_action": action or "",
        }

    def health_check(self, company=None):
        """Salud fiscal de UNA empresa autorizada (sin contadores cruzados)."""
        company = company or self.env.company
        allowed = self.env.companies
        if company not in allowed and not self.env.su:
            # No evaluar empresas no autorizadas
            return {
                "ok": True,
                "gl_balanced": True,
                "gl_debit": 0.0,
                "gl_credit": 0.0,
                "issues": [],
                "warnings": [],
                "recommendations": [],
                "findings": [],
                "diagnostic_count": 0,
                "duplicate_groups": 0,
                "skipped_unauthorized": True,
            }

        findings = []
        issues = []
        warnings = []
        recommendations = []

        if company.country_id.code != "DO":
            f = self._finding(
                "COUNTRY_NOT_DO",
                _("Empresa sin país República Dominicana."),
                "low",
                company,
                category="warning",
                impact=_("Localización fiscal DO no aplica."),
                model_name="res.company",
                res_model="res.company",
                res_id=company.id,
                action=_("Verificar país de la empresa."),
            )
            findings.append(f)
            warnings.append(f["name"])

        if not company.justech_do_fiscal_enabled:
            f = self._finding(
                "MOTOR_OFF",
                _("Motor fiscal desactivado para esta empresa."),
                "high",
                company,
                impact=_("No se asignarán NCF Justech."),
                model_name="res.company",
                res_model="res.company",
                res_id=company.id,
                action=_("Activar motor fiscal Justech en la empresa."),
            )
            findings.append(f)
            issues.append(f["name"])

        sale_j = self.env["account.journal"].search(
            [("company_id", "=", company.id), ("type", "=", "sale")], limit=1
        )
        if sale_j:
            if sale_j.l10n_latam_use_documents:
                f = self._finding(
                    "LATAM_DOCS",
                    _("Diario de ventas con documentos LATAM activos — riesgo doble motor."),
                    "high",
                    company,
                    impact=_("Doble asignación de comprobantes."),
                    model_name="account.journal",
                    res_model="account.journal",
                    res_id=sale_j.id,
                    action=_("Desactivar 'Usar documentos' LATAM en el diario de ventas."),
                )
                findings.append(f)
                issues.append(f["name"])
            if not sale_j.justech_do_use_ncf:
                f = self._finding(
                    "NCF_JOURNAL_OFF",
                    _("Diario de ventas sin NCF Justech activo."),
                    "medium",
                    company,
                    category="warning",
                    model_name="account.journal",
                    res_model="account.journal",
                    res_id=sale_j.id,
                    action=_("Activar NCF Justech en el diario."),
                )
                findings.append(f)
                warnings.append(f["name"])

        diag = []
        if "justech.do.ncf.diagnostic.service" in self.env:
            diag = self.env["justech.do.ncf.diagnostic.service"].run_full_scan(company)
            for item in diag:
                sev_map = {"error": "high", "warning": "medium", "info": "info"}
                sev = sev_map.get(item.get("severity"), "medium")
                code = (item.get("code") or "").upper()
                title = item.get("title") or item.get("code") or "?"
                detail = item.get("detail") or ""
                if any(
                    x in (title or "").lower()
                    for x in ("adel", "histórico", "historico", "solo lectura", "read-only")
                ):
                    sev = "info"
                res_model = item.get("action_model") or ""
                res_id = 0
                domain = item.get("action_domain") or []
                if (
                    isinstance(domain, (list, tuple))
                    and len(domain) == 1
                    and isinstance(domain[0], (list, tuple))
                    and len(domain[0]) == 3
                    and domain[0][0] == "id"
                    and domain[0][1] == "="
                ):
                    try:
                        res_id = int(domain[0][2])
                    except (TypeError, ValueError):
                        res_id = 0
                impact_map = {
                    "PARTNER_INVALID_RNC": _("Factura/partner con tipo que exige RNC sin validación."),
                    "POSTED_MISSING_NCF": _("Documento publicado sin comprobante fiscal Justech."),
                }
                action_map = {
                    "PARTNER_INVALID_RNC": _(
                        "Abrir el partner, corregir RNC/cédula y revalidar contra padrón DGII."
                    ),
                    "POSTED_MISSING_NCF": _(
                        "Abrir la factura, asignar NCF Justech o anular/rehacer según política fiscal."
                    ),
                }
                f = self._finding(
                    code or "DIAG",
                    title,
                    sev,
                    company,
                    category="error" if sev in ("critical", "high") else "warning",
                    impact=impact_map.get(code) or detail or item.get("impact") or "",
                    model_name=res_model,
                    res_model=res_model,
                    res_id=res_id,
                    action=action_map.get(code)
                    or item.get("recommendation")
                    or item.get("action")
                    or "",
                )
                f["cause"] = detail or title
                findings.append(f)
                if sev in ("critical", "high"):
                    issues.append(title)
                elif sev in ("medium", "low"):
                    warnings.append(title)

        cr = self.env.cr
        cr.execute(
            """
            SELECT COALESCE(SUM(aml.debit),0), COALESCE(SUM(aml.credit),0)
            FROM account_move_line aml
            JOIN account_move am ON am.id = aml.move_id
            WHERE am.state = 'posted' AND am.company_id = %s
            """,
            (company.id,),
        )
        d, c = cr.fetchone()
        gl_ok = float(d) == float(c)
        if not gl_ok:
            f = self._finding(
                "GL_UNBALANCED",
                _("Libro mayor desbalanceado en esta empresa."),
                "critical",
                company,
                impact=_("Integridad contable comprometida."),
                model_name="account.move.line",
                action=_("Revisar asientos descuadrados de la empresa."),
            )
            f["cause"] = _("Suma de débitos distinta a suma de créditos en asientos publicados.")
            findings.append(f)
            issues.append(f["name"])

        dup_groups = []
        if "justech.do.ncf.duplicate.service" in self.env:
            dup_groups = self.env["justech.do.ncf.duplicate.service"].find_duplicate_groups_v2(
                company
            )
            if dup_groups:
                f = self._finding(
                    "NCF_DUP",
                    _("Duplicados NCF detectados: %(n)s grupos.", n=len(dup_groups)),
                    "critical",
                    company,
                    impact=_("Riesgo de rechazo DGII."),
                    model_name="justech.do.ncf.consumption",
                    action=_("Abrir diagnóstico de duplicados NCF."),
                )
                f["cause"] = _("Más de un movimiento publicado con la misma clave NCF.")
                findings.append(f)
                issues.append(f["name"])

        # Padrón: GLOBAL (no por empresa). Solo alertas reales de integridad.
        if "justech.do.rnc.padron.import.service" in self.env:
            try:
                pad = self.env["justech.do.rnc.padron.import.service"].sudo().integrity_check()
                for i in pad.get("issues", []):
                    f = self._finding(
                        "PADRON_ISSUE",
                        _("Padrón DGII: %s") % i,
                        "critical",
                        company,
                        impact=_("Validación RNC afectada (padrón global)."),
                        action=_(
                            "Reparar el padrón global una sola vez en Centro Fiscal "
                            "(no cargar padrón por empresa)."
                        ),
                    )
                    f["cause"] = i
                    findings.append(f)
                    issues.append(f["name"])
                for w in pad.get("warnings", []):
                    f = self._finding(
                        "PADRON_WARN",
                        _("Padrón DGII: %s") % w,
                        "medium",
                        company,
                        category="warning",
                        action=_("Revisar historial global de importación del padrón."),
                    )
                    f["cause"] = w
                    findings.append(f)
                    warnings.append(f["name"])
                if pad.get("never_loaded") or pad.get("count", 0) <= 0:
                    recommendations.append(
                        _(
                            "Después de restaurar una base sin padrón DGII, "
                            "utilice Importar padrón DGII (global) en el Centro Fiscal."
                        )
                    )
                elif pad.get("ok"):
                    recommendations.append(
                        _(
                            "Padrón DGII global operativo (%(n)s registros) — "
                            "compartido por todas las empresas."
                        )
                        % {"n": pad.get("count", 0)}
                    )
            except Exception:  # noqa: BLE001
                warnings.append(_("No se pudo evaluar el padrón DGII."))

        # Filtrar hallazgos: no contar info / histórico como error
        error_findings = [
            f
            for f in findings
            if f["severity"] in ("critical", "high") and f["category"] == "error"
        ]
        if not warnings and not error_findings:
            recommendations.append(_("Stack fiscal operando correctamente."))

        return {
            "ok": not error_findings,
            "gl_balanced": gl_ok,
            "gl_debit": float(d),
            "gl_credit": float(c),
            "issues": [f["name"] for f in error_findings],
            "warnings": warnings,
            "recommendations": recommendations,
            "findings": findings,
            "diagnostic_count": len(diag),
            "duplicate_groups": len(dup_groups),
        }

    def multi_company_summary(self):
        """Solo empresas autorizadas del usuario actual."""
        companies = self.env.companies
        rows = []
        for co in companies:
            hc = self.health_check(co)
            if hc.get("skipped_unauthorized"):
                continue
            rows.append(
                {
                    "id": co.id,
                    "name": co.name,
                    "fiscal_enabled": co.justech_do_fiscal_enabled,
                    "health_ok": hc["ok"],
                    "issues": len(hc.get("issues") or []),
                    "warnings": len(hc.get("warnings") or []),
                }
            )
        return rows

    def sequence_validation(self, company=None):
        company = company or self.env.company
        Range = self.env["justech.do.ncf.range"]
        rows = []
        today = fields.Date.context_today(self)
        for rng in Range.search([("company_id", "=", company.id)]):
            rows.append(
                {
                    "prefix": rng.prefix,
                    "name": rng.name,
                    "state": rng.state,
                    "next_sequence": rng.next_sequence,
                    "remaining": max(0, rng.sequence_end - rng.next_sequence + 1),
                    "expired": rng.date_to < today if rng.date_to else False,
                }
            )
        return rows

    def ncf_consumption_summary(self, company=None):
        """Consumo de rangos NCF con alertas de agotamiento."""
        company = company or self.env.company
        if "justech.do.ncf.range" not in self.env:
            return {"ranges": [], "alerts": [], "total_remaining": 0}
        Range = self.env["justech.do.ncf.range"]
        today = fields.Date.context_today(self)
        ranges = []
        alerts = []
        total_remaining = 0
        for rng in Range.search([("company_id", "=", company.id)], order="prefix"):
            capacity = max(1, rng.sequence_end - rng.sequence_start + 1)
            used = max(0, rng.next_sequence - rng.sequence_start)
            remaining = max(0, rng.sequence_end - rng.next_sequence + 1)
            used_pct = (used / capacity) * 100.0
            total_remaining += remaining
            expired = bool(rng.date_to and rng.date_to < today)
            low = remaining <= max(10, int(capacity * 0.1))
            row = {
                "prefix": rng.prefix,
                "name": rng.name,
                "state": rng.state,
                "next_sequence": rng.next_sequence,
                "remaining": remaining,
                "capacity": capacity,
                "used_pct": round(used_pct, 1),
                "expired": expired,
                "date_to": rng.date_to,
                "status": "error" if expired else ("warning" if low else "ok"),
            }
            ranges.append(row)
            if expired:
                alerts.append(_("Rango %(pfx)s vencido.", pfx=rng.prefix))
            elif low and rng.state == "active":
                alerts.append(
                    _("Rango %(pfx)s agotándose: quedan %(n)s NCF.", pfx=rng.prefix, n=remaining)
                )
        return {"ranges": ranges, "alerts": alerts, "total_remaining": total_remaining}

    def payments_withholding_status(self, company=None):
        """Estado read-only Pagos y Retenciones."""
        company = company or self.env.company
        Module = self.env["ir.module.module"]
        wh_pkg = Module.search([("name", "=", "justech_l10n_do_payments_withholding")], limit=1)
        flags = self.env["justech.fiscal.feature.flag"].sudo()

        catalog_count = catalog_active = wh_lines = wh_payments = 0
        banks = []
        inconsistencies = []
        taxes_reused = 0

        if "justech.do.withholding.catalog" in self.env:
            Catalog = self.env["justech.do.withholding.catalog"]
            catalog_count = Catalog.search_count([("company_id", "=", company.id)])
            catalog_active = Catalog.search_count(
                [("company_id", "=", company.id), ("active", "=", True)]
            )
            taxes_reused = Catalog.search_count(
                [("company_id", "=", company.id), ("tax_id", "!=", False)]
            )
        if "justech.payment.withholding.line" in self.env:
            wh_lines = self.env["justech.payment.withholding.line"].search_count(
                [("company_id", "=", company.id)]
            )
        if "justech_withholding_total" in self.env["account.payment"]._fields:
            wh_payments = self.env["account.payment"].search_count(
                [
                    ("company_id", "=", company.id),
                    ("justech_withholding_total", ">", 0),
                    ("state", "in", ("paid", "in_process", "posted")),
                ]
            )

        for j in self.env["account.journal"].search(
            [("company_id", "=", company.id), ("type", "in", ("bank", "cash"))]
        ):
            banks.append({"code": j.code, "name": j.name, "type": j.type})

        if not wh_pkg or wh_pkg.state != "installed":
            inconsistencies.append(_("Módulo justech_l10n_do_payments_withholding no instalado."))
        elif not flags.is_enabled("payments_withholding", company):
            inconsistencies.append(_("Feature flag Pagos y Retenciones desactivado."))
        if catalog_count == 0 and wh_pkg and wh_pkg.state == "installed":
            inconsistencies.append(_("Catálogo retenciones vacío — ejecute sincronización."))

        standard_status = "activo" if wh_pkg and wh_pkg.state == "installed" and not inconsistencies else "pendiente"
        wizard_installed = "justech.payment.partner.wizard" in self.env

        return {
            "modules": {
                "payments_withholding": wh_pkg.state if wh_pkg else "missing",
            },
            "feature_enabled": flags.is_enabled("payments_withholding", company),
            "wizard_unified": wizard_installed,
            "catalog_total": catalog_count,
            "catalog_active": catalog_active,
            "taxes_reused": taxes_reused,
            "withholding_lines": wh_lines,
            "payments_with_withholding": wh_payments,
            "banks": banks,
            "inconsistencies": inconsistencies,
            "standard_status": standard_status,
        }
