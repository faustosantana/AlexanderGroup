"""Diagnóstico fiscal NCF — solo lectura, sin modificar datos."""
from odoo import _, fields, models


class JustechDoNcfDiagnosticService(models.AbstractModel):
    _name = "justech.do.ncf.diagnostic.service"
    _description = "NCF Fiscal Diagnostic Service"

    SEVERITY_INFO = "info"
    SEVERITY_WARNING = "warning"
    SEVERITY_ERROR = "error"

    def run_full_scan(self, company=None):
        company = company or self.env.company
        findings = []
        findings.extend(self._check_company_config(company))
        findings.extend(self._check_journals(company))
        findings.extend(self._check_ranges(company))
        findings.extend(self._check_partners(company))
        findings.extend(self._check_posted_documents(company))
        findings.extend(self._check_duplicates_v2(company))
        return findings

    def _finding(self, code, severity, title, detail, action_model=None, action_domain=None):
        return {
            "code": code,
            "severity": severity,
            "title": title,
            "detail": detail,
            "action_model": action_model,
            "action_domain": action_domain or [],
        }

    def _check_company_config(self, company):
        findings = []
        if company.country_id.code != "DO":
            findings.append(
                self._finding(
                    "company_not_do",
                    self.SEVERITY_WARNING,
                    _("País de la empresa"),
                    _("La empresa %(name)s no tiene país República Dominicana.", name=company.name),
                )
            )
        if not company.justech_do_fiscal_enabled:
            findings.append(
                self._finding(
                    "fiscal_disabled",
                    self.SEVERITY_ERROR,
                    _("Fiscal desactivado"),
                    _("La configuración fiscal dominicana está desactivada para %(name)s.", name=company.name),
                    "res.company",
                    [("id", "=", company.id)],
                )
            )
        if not company.partner_id.vat:
            findings.append(
                self._finding(
                    "company_no_vat",
                    self.SEVERITY_WARNING,
                    _("RNC empresa"),
                    _("La empresa no tiene RNC/VAT configurado en su contacto."),
                )
            )
        return findings

    def _check_journals(self, company):
        findings = []
        journals = self.env["account.journal"].search(
            [("company_id", "=", company.id), ("justech_do_use_ncf", "=", True)]
        )
        Range = self.env["justech.do.ncf.range"]
        today = fields.Date.context_today(self)
        for journal in journals:
            doc_types = journal.justech_do_document_type_ids
            if not doc_types and journal.justech_do_default_document_type_id:
                doc_types = journal.justech_do_default_document_type_id
            for doc in doc_types:
                active = Range.search_count(
                    [
                        ("company_id", "=", company.id),
                        ("document_type_id", "=", doc.id),
                        ("state", "=", "active"),
                        ("date_to", ">=", today),
                    ]
                )
                if not active:
                    findings.append(
                        self._finding(
                            "journal_no_range",
                            self.SEVERITY_ERROR,
                            _("Diario sin rango activo"),
                            _(
                                "El diario %(journal)s requiere NCF tipo %(prefix)s pero no hay rango activo.",
                                journal=journal.display_name,
                                prefix=doc.prefix,
                            ),
                            "justech.do.ncf.range",
                            [("company_id", "=", company.id), ("document_type_id", "=", doc.id)],
                        )
                    )
        return findings

    def _check_ranges(self, company):
        findings = []
        audit = self.env["justech.do.ncf.range.audit.service"]
        for row in audit.range_health_rows(company):
            if row["health_status"] == "expired_pending":
                findings.append(
                    self._finding(
                        "range_expired_active",
                        self.SEVERITY_ERROR,
                        _("Rango vencido aún activo"),
                        _("%(name)s (%(prefix)s) venció el %(date)s.", name=row["name"], prefix=row["prefix"], date=row["date_to"]),
                        "justech.do.ncf.range",
                        [("id", "=", row["range_id"])],
                    )
                )
            elif row["health_status"] == "expiring":
                findings.append(
                    self._finding(
                        "range_expiring",
                        self.SEVERITY_WARNING,
                        _("Rango por vencer"),
                        _("%(name)s vence el %(date)s (quedan %(rem)s NCF).", name=row["name"], date=row["date_to"], rem=row["remaining_count"]),
                        "justech.do.ncf.range",
                        [("id", "=", row["range_id"])],
                    )
                )
            elif row["health_status"] == "low_stock":
                name = row.get("name") or _("Rango sin nombre")
                rem = row.get("remaining_count")
                if rem is None:
                    rem = 0
                pct = row.get("pct_used")
                try:
                    pct = float(pct) if pct is not None else 0.0
                except (TypeError, ValueError):
                    pct = 0.0
                findings.append(
                    self._finding(
                        "range_low_stock",
                        self.SEVERITY_WARNING,
                        _("Rango casi agotado"),
                        _(
                            "%(name)s tiene %(rem)s NCF restantes (%(pct).1f%% usado)."
                        )
                        % {
                            "name": name,
                            "rem": rem,
                            "pct": pct,
                        },
                        "justech.do.ncf.range",
                        [("id", "=", row["range_id"])],
                    )
                )
            elif row["state"] == "depleted":
                findings.append(
                    self._finding(
                        "range_depleted",
                        self.SEVERITY_INFO,
                        _("Rango agotado"),
                        _("%(name)s (%(prefix)s) está agotado.", name=row["name"], prefix=row["prefix"]),
                        "justech.do.ncf.range",
                        [("id", "=", row["range_id"])],
                    )
                )
        return findings

    def _check_partners(self, company):
        findings = []
        Move = self.env["account.move"]
        moves = Move.search(
            [
                ("company_id", "=", company.id),
                ("state", "=", "posted"),
                ("move_type", "in", ("out_invoice", "out_refund")),
            ],
            limit=500,
        )
        for move in moves:
            doc = move.justech_do_document_type_id
            if not doc or not doc.requires_vat:
                continue
            if move.partner_id and not move.partner_id.justech_do_has_rnc():
                findings.append(
                    self._finding(
                        "partner_invalid_rnc",
                        self.SEVERITY_ERROR,
                        _("Cliente sin RNC válido"),
                        _("%(move)s — %(partner)s requiere RNC para %(prefix)s.", move=move.name, partner=move.partner_id.display_name, prefix=move.justech_do_document_type_id.prefix),
                        "account.move",
                        [("id", "=", move.id)],
                    )
                )
        return findings[:20]

    def _check_posted_documents(self, company):
        findings = []
        Move = self.env["account.move"]
        missing = Move.search(
            [
                ("company_id", "=", company.id),
                ("state", "=", "posted"),
                ("move_type", "in", ("out_invoice", "out_refund")),
                ("journal_id.justech_do_use_ncf", "=", True),
                ("justech_do_ncf", "=", False),
                ("justech_do_ncf_voided", "=", False),
            ],
            limit=50,
        )
        for move in missing:
            if move.l10n_latam_document_number:
                findings.append(
                    self._finding(
                        "posted_historical_adel_ncf",
                        self.SEVERITY_INFO,
                        _("Histórico Adel (compat)"),
                        _(
                            "%(move)s usa NCF histórico %(ncf)s vía l10n_latam.",
                            move=move.name,
                            ncf=move.l10n_latam_document_number,
                        ),
                        "account.move",
                        [("id", "=", move.id)],
                    )
                )
                continue
            findings.append(
                self._finding(
                    "posted_missing_ncf",
                    self.SEVERITY_ERROR,
                    _("Factura sin NCF"),
                    _("%(move)s publicada sin comprobante fiscal.", move=move.name),
                    "account.move",
                    [("id", "=", move.id)],
                )
            )
        invalid = Move.search(
            [
                ("company_id", "=", company.id),
                ("state", "=", "posted"),
                ("justech_do_ncf", "!=", False),
            ],
            limit=200,
        )
        validator = self.env["justech.do.fiscal.validator.service"]
        for move in invalid:
            try:
                validator.validate_ncf_format(move.justech_do_ncf)
            except Exception:
                findings.append(
                    self._finding(
                        "invalid_ncf_format",
                        self.SEVERITY_ERROR,
                        _("Formato NCF inválido"),
                        _("%(move)s tiene NCF con formato incorrecto: %(ncf)s.", move=move.name, ncf=move.justech_do_ncf),
                        "account.move",
                        [("id", "=", move.id)],
                    )
                )
        return findings

    def _check_duplicates_v2(self, company):
        findings = []
        groups = self.env["justech.do.ncf.duplicate.service"].find_duplicate_groups_v2(company)
        for group in groups:
            names = ", ".join(m["name"] for m in group["moves"])
            findings.append(
                self._finding(
                    "duplicate_ncf_v2",
                    self.SEVERITY_ERROR,
                    _("NCF duplicado (v2.0)"),
                    _("Clave %(key)s — documentos: %(names)s.", key=group["key"], names=names),
                    "account.move",
                    [("id", "in", [m["id"] for m in group["moves"]])],
                )
            )
        return findings
