"""Wizard de diagnóstico fiscal — detección sin modificar datos."""
import json

from odoo import _, api, fields, models


class JustechDoFiscalDiagnosticLine(models.TransientModel):
    _name = "justech.do.fiscal.diagnostic.line"
    _description = "Línea de diagnóstico fiscal"
    _order = "severity desc, id"

    wizard_id = fields.Many2one(
        "justech.do.fiscal.diagnostic.wizard", required=True, ondelete="cascade"
    )
    code = fields.Char(readonly=True)
    severity = fields.Selection(
        selection=[
            ("info", "Información"),
            ("warning", "Advertencia"),
            ("error", "Error"),
        ],
        readonly=True,
    )
    title = fields.Char(readonly=True)
    detail = fields.Text(readonly=True)
    action_model = fields.Char(readonly=True)
    action_domain = fields.Char(readonly=True)

    def action_open_records(self):
        self.ensure_one()
        if not self.action_model:
            return False
        domain = json.loads(self.action_domain or "[]")
        return {
            "type": "ir.actions.act_window",
            "name": self.title,
            "res_model": self.action_model,
            "view_mode": "list,form",
            "domain": domain,
        }


class JustechDoFiscalDiagnosticWizard(models.TransientModel):
    _name = "justech.do.fiscal.diagnostic.wizard"
    _description = "Diagnóstico Fiscal NCF"

    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
    )
    line_ids = fields.One2many("justech.do.fiscal.diagnostic.line", "wizard_id")
    error_count = fields.Integer(compute="_compute_counts")
    warning_count = fields.Integer(compute="_compute_counts")
    info_count = fields.Integer(compute="_compute_counts")
    scan_date = fields.Datetime(readonly=True)

    @api.depends("line_ids.severity")
    def _compute_counts(self):
        for wiz in self:
            wiz.error_count = len(wiz.line_ids.filtered(lambda l: l.severity == "error"))
            wiz.warning_count = len(wiz.line_ids.filtered(lambda l: l.severity == "warning"))
            wiz.info_count = len(wiz.line_ids.filtered(lambda l: l.severity == "info"))

    def action_run_scan(self):
        self.ensure_one()
        self.line_ids.unlink()
        findings = self.env["justech.do.ncf.diagnostic.service"].run_full_scan(self.company_id)
        Line = self.env["justech.do.fiscal.diagnostic.line"]
        for item in findings:
            Line.create(
                {
                    "wizard_id": self.id,
                    "code": item["code"],
                    "severity": item["severity"],
                    "title": item["title"],
                    "detail": item["detail"],
                    "action_model": item.get("action_model"),
                    "action_domain": json.dumps(item.get("action_domain") or []),
                }
            )
        self.scan_date = fields.Datetime.now()
        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }
