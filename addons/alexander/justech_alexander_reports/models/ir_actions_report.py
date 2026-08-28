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
        if model == "res.partner":
            return self.env["res.company"]
        if "company_id" not in self.env[model]._fields:
            return self.env["res.company"]
        records = self.env[model].sudo().browse(res_ids).exists()
        return records.mapped("company_id")[:1]

    def _dx_lang_from_records(self, report_ref, res_ids, company):
        lang_code = False
        if res_ids:
            report = self
            if not isinstance(report_ref, models.BaseModel):
                try:
                    report = self._get_report(report_ref)
                except Exception:
                    report = self
            elif report_ref:
                report = report_ref[:1]
            model = report.model
            if model and model in self.env:
                records = self.env[model].sudo().browse(res_ids).exists()
                if "partner_id" in records._fields and records[:1].partner_id:
                    lang_code = records[:1].partner_id.lang
                elif "company_id" in records._fields and records[:1].company_id:
                    lang_code = records[:1].company_id.partner_id.lang
        if not lang_code and company:
            lang_code = company.partner_id.lang
        if lang_code:
            active = (
                self.env["res.lang"]
                .sudo()
                .search([("code", "=", lang_code), ("active", "=", True)], limit=1)
            )
            if active:
                return lang_code
        es = (
            self.env["res.lang"]
            .sudo()
            .search([("code", "=", "es_DO"), ("active", "=", True)], limit=1)
        )
        return es.code if es else False

    def _render_qweb_pdf(self, report_ref, res_ids=None, data=None):
        company = self._dx_company_from_records(report_ref, res_ids)
        renderer = self
        ctx = {}
        if company:
            ctx.update(
                {
                    "allowed_company_ids": company.ids,
                    "company_id": company.id,
                }
            )
            renderer = self.with_company(company)
        lang = self._dx_lang_from_records(report_ref, res_ids, company)
        if lang:
            ctx["lang"] = lang
        if ctx:
            renderer = renderer.with_context(**ctx)
        return super(IrActionsReport, renderer)._render_qweb_pdf(
            report_ref, res_ids=res_ids, data=data
        )
