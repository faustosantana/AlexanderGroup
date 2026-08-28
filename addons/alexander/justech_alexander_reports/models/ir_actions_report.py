from odoo import models


class IrActionsReport(models.Model):
    _inherit = "ir.actions.report"

    def _dx_company_from_records(self, report_ref, res_ids):
        if not res_ids:
            return self.env["res.company"]
        report = self
        if not isinstance(report_ref, models.BaseModel):
            try:
                report = self._get_report(report_ref)
            except Exception:
                return self.env["res.company"]
        elif report_ref:
            report = report_ref[:1]
        model = report.model
        if not model or model not in self.env:
            return self.env["res.company"]
        if "company_id" not in self.env[model]._fields:
            return self.env["res.company"]
        records = self.env[model].sudo().browse(res_ids).exists()
        return records.mapped("company_id")[:1]

    def _render_qweb_pdf(self, report_ref, res_ids=None, data=None):
        company = self._dx_company_from_records(report_ref, res_ids)
        renderer = self
        if company:
            renderer = self.with_company(company).with_context(
                allowed_company_ids=company.ids,
                company_id=company.id,
            )
        return super(IrActionsReport, renderer)._render_qweb_pdf(
            report_ref, res_ids=res_ids, data=data
        )
