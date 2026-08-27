from odoo import _, api, fields, models
from odoo.exceptions import UserError


class JustechDoFiscalReportWizard(models.TransientModel):
    _name = "justech.do.fiscal.report.wizard"
    _inherit = ["justech.do.dgii.period.selector.mixin"]
    _description = "Asistente para generar reporte fiscal DGII"

    DGII_EXPORT_TYPES = ("606", "607")
    DGII_EXPORTER_MODELS = {
        "606": "justech.do.dgii.606.exporter",
        "607": "justech.do.dgii.607.exporter",
    }

    report_type = fields.Selection(
        selection=[
            ("606", "606 — Compras"),
            ("607", "607 — Ventas"),
            ("608", "608 — NCF anulados"),
            ("609", "609 — Pagos exterior"),
            ("623", "623 — Retenciones Estado"),
        ],
        string="Tipo de reporte",
        required=True,
        default="606",
    )
    period_code = fields.Char(
        string="Período (YYYYMM)",
        required=True,
        default=lambda self: self.env["justech.do.dgii.period"].default_period_code(),
    )
    date_from = fields.Date(string="Desde", required=True)
    date_to = fields.Date(string="Hasta", required=True)
    company_id = fields.Many2one(
        "res.company",
        string="Compañía",
        required=True,
        default=lambda self: self.env.company,
    )
    validation_log = fields.Text(string="Resultado de validación", readonly=True)
    validation_state = fields.Selection(
        selection=[
            ("pending", "Sin validar"),
            ("ok", "Válido"),
            ("warning", "Con advertencias"),
            ("error", "Sin documentos válidos"),
        ],
        string="Estado de validación",
        default="pending",
        readonly=True,
    )
    count_all = fields.Integer(string="Documentos en período", readonly=True)
    count_valid = fields.Integer(string="Válidos para exportar", readonly=True)
    count_incomplete = fields.Integer(string="Incompletos", readonly=True)
    count_excluded = fields.Integer(string="Excluidos", readonly=True)
    count_cancelled = fields.Integer(string="Anulados", readonly=True)
    count_partners_errors = fields.Integer(string="Proveedores con errores", readonly=True)
    error_report_file = fields.Binary(string="Reporte de errores", readonly=True)
    error_report_filename = fields.Char(string="Nombre reporte errores", readonly=True)
    saved_report_id = fields.Many2one(
        "justech.do.fiscal.report",
        string="Revisión guardada",
        readonly=True,
    )
    date_from_display = fields.Char(
        string="Desde (período)",
        compute="_compute_period_display",
    )
    date_to_display = fields.Char(
        string="Hasta (período)",
        compute="_compute_period_display",
    )

    @api.depends("date_from", "date_to")
    def _compute_period_display(self):
        for wiz in self:
            wiz.date_from_display = (
                wiz.date_from.strftime("%d/%m/%Y") if wiz.date_from else ""
            )
            wiz.date_to_display = (
                wiz.date_to.strftime("%d/%m/%Y") if wiz.date_to else ""
            )

    @api.model_create_multi
    def create(self, vals_list):
        normalized = []
        for vals in vals_list:
            normalized.append(self._justech_normalize_period_vals(vals))
        return super().create(normalized)

    def write(self, vals):
        if any(
            k in vals
            for k in (
                "period_mode",
                "period_year",
                "period_month",
                "period_code",
                "date_from",
                "date_to",
            )
        ):
            for wiz in self:
                nvals = self._justech_normalize_period_vals(vals, record=wiz)
                super(JustechDoFiscalReportWizard, wiz).write(nvals)
            return True
        return super().write(vals)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        period_util = self.env["justech.do.dgii.period"]
        period_code = res.get("period_code") or period_util.default_period_code()
        date_from, date_to = period_util.period_bounds_from_code(period_code)
        res.update(
            {
                "period_mode": res.get("period_mode") or "month",
                "period_code": period_code,
                "period_year": int(period_code[:4]),
                "period_month": str(int(period_code[4:6])),
                "date_from": date_from,
                "date_to": date_to,
            }
        )
        return res

    def _check_period(self):
        self.ensure_one()
        period_util = self.env["justech.do.dgii.period"]
        if self.period_mode == "custom":
            period_util.validate_custom_range(self.date_from, self.date_to)
        else:
            period_util.period_bounds_from_code(self.period_code)
            period_util.validate_period_dates(
                self.date_from, self.date_to, self.period_code
            )

    def _get_dgii_exporter(self):
        self.ensure_one()
        model = self.DGII_EXPORTER_MODELS.get(self.report_type)
        return self.env[model] if model else False

    def _apply_validation_result(self, result):
        self.ensure_one()
        exporter = self._get_dgii_exporter()
        counts = result["counts"]
        self.count_all = counts["all"]
        self.count_valid = counts["valid"]
        self.count_incomplete = counts["incomplete"]
        self.count_excluded = counts["excluded"]
        self.count_cancelled = counts["cancelled"]
        self.count_partners_errors = counts["partners_affected"]
        self.validation_log = exporter.format_validation_summary(result)
        error_content, error_filename = exporter.export_errors_xlsx(
            self.company_id, self.date_from, self.date_to, result=result
        )
        self.error_report_file = error_content
        self.error_report_filename = error_filename
        if counts["valid"] and counts["incomplete"]:
            self.validation_state = "warning"
        elif counts["valid"]:
            self.validation_state = "ok"
        else:
            self.validation_state = "error"

    def _create_report(self):
        self.ensure_one()
        self._check_period()
        labels = dict(self._fields["report_type"].selection)
        label = labels.get(self.report_type, self.report_type)
        return self.env["justech.do.fiscal.report"].create(
            {
                "name": f"{label} {self.period_code} — revisión fiscal",
                "report_type": self.report_type,
                "period_code": self.period_code,
                "date_from": self.date_from,
                "date_to": self.date_to,
                "company_id": self.company_id.id,
                "validation_log": self.validation_log,
                "validation_state": self.validation_state,
                "count_all": self.count_all,
                "count_valid": self.count_valid,
                "count_incomplete": self.count_incomplete,
                "count_excluded": self.count_excluded,
                "count_cancelled": self.count_cancelled,
                "count_partners_errors": self.count_partners_errors,
                "error_report_file": self.error_report_file,
                "error_report_filename": self.error_report_filename,
                "state": "draft",
            }
        )

    def _open_review_form(self, report):
        review_form = self.env.ref(
            "justech_l10n_do_reports.view_justech_do_fiscal_report_review_form",
            raise_if_not_found=False,
        )
        views = [(review_form.id, "form")] if review_form else []
        return {
            "type": "ir.actions.act_window",
            "name": _("Revisión fiscal DGII"),
            "res_model": "justech.do.fiscal.report",
            "res_id": report.id,
            "view_mode": "form",
            "views": views or False,
            "target": "current",
        }

    def action_validate(self):
        self.ensure_one()
        self._check_period()
        if self.report_type not in self.DGII_EXPORT_TYPES:
            self.validation_log = _(
                "Validación detallada no disponible para formato %(type)s."
            ) % {"type": self.report_type}
            self.validation_state = "ok"
        else:
            exporter = self._get_dgii_exporter()
            result = exporter.validate_period(
                self.company_id, self.date_from, self.date_to
            )
            self._apply_validation_result(result)
        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }

    def action_save_review(self):
        """Crea un registro persistente de revisión fiscal con todas las líneas."""
        self.ensure_one()
        self._check_period()
        if self.report_type in self.DGII_EXPORT_TYPES and self.validation_state == "pending":
            self.action_validate()
        report = self._create_report()
        report.action_load_review_lines()
        if self.report_type in self.DGII_EXPORT_TYPES:
            report.action_validate_period()
        else:
            report._transition_state("validated", _("Revisión guardada."))
        self.saved_report_id = report.id
        return self._open_review_form(report)

    def action_view_documents(self):
        """Abre la revisión guardada o la crea si aún no existe."""
        self.ensure_one()
        if self.saved_report_id:
            return self._open_review_form(self.saved_report_id)
        return self.action_save_review()

    def action_download_errors(self):
        self.ensure_one()
        if not self.error_report_file:
            if self.report_type in self.DGII_EXPORT_TYPES:
                self.action_validate()
            if not self.error_report_file:
                raise UserError(_("No hay reporte de errores para descargar."))
        return {
            "type": "ir.actions.act_url",
            "url": (
                f"/web/content/?model={self._name}&id={self.id}"
                f"&field=error_report_file&filename_field=error_report_filename&download=true"
            ),
            "target": "self",
        }

    def action_generate(self):
        self.ensure_one()
        if self.report_type in self.DGII_EXPORT_TYPES:
            if self.validation_state == "pending":
                self.action_validate()
            report = self._create_report()
            report.action_load_review_lines()
            report.action_validate_period()
            if report.manual_exclusion_count and report.state != "approved":
                return report.action_open_export_blocker_wizard()
            result = report.action_generate_dgii_export()
            if isinstance(result, dict):
                return result
            return result
        report = self._create_report()
        report.action_generate()
        return self._open_review_form(report)

    def action_generate_history(self):
        """Alias retrocompatible — guarda revisión fiscal persistente."""
        return self.action_save_review()
