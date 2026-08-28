"""Centro de Administración Fiscal NCF — hub operativo para contadores."""
from odoo import _, fields, models


class JustechDoNcfAdminCenter(models.TransientModel):
    _name = "justech.do.ncf.admin.center"
    _description = "Centro de Administración Fiscal NCF"

    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
    )
    summary_json = fields.Text(readonly=True)
    active_range_count = fields.Integer(readonly=True)
    expiring_range_count = fields.Integer(readonly=True)
    depleted_range_count = fields.Integer(readonly=True)
    voided_consumption_count = fields.Integer(readonly=True)
    diagnostic_error_count = fields.Integer(readonly=True)
    diagnostic_warning_count = fields.Integer(readonly=True)
    last_scan = fields.Datetime(readonly=True)

    def action_open(self):
        self.ensure_one()
        self._refresh_stats()
        return {
            "type": "ir.actions.act_window",
            "name": _("Centro de Administración Fiscal"),
            "res_model": "justech.do.ncf.admin.center",
            "res_id": self.id,
            "view_mode": "form",
            "target": "current",
        }

    @classmethod
    def open_for_user(cls, env):
        center = env["justech.do.ncf.admin.center"].create({"company_id": env.company.id})
        center._refresh_stats()
        return center.action_open()

    def _refresh_stats(self):
        self.ensure_one()
        audit = self.env["justech.do.ncf.range.audit.service"]
        summary = audit.summary_for_company(self.company_id)
        self.write(
            {
                "active_range_count": summary["active_ranges"],
                "expiring_range_count": summary["expiring_ranges"],
                "depleted_range_count": summary["depleted_ranges"],
                "voided_consumption_count": summary["consumption_voided"],
            }
        )

    def action_refresh(self):
        self._refresh_stats()
        return self.action_open()

    def action_open_ranges(self):
        return self._action_list("justech.do.ncf.range", _("Rangos NCF"))

    def action_open_active_ranges(self):
        return self._action_list(
            "justech.do.ncf.range",
            _("Rangos activos"),
            [("company_id", "=", self.company_id.id), ("state", "=", "active")],
        )

    def action_open_consumption(self):
        return self._action_list(
            "justech.do.ncf.consumption",
            _("Consumo NCF"),
            [("company_id", "=", self.company_id.id)],
        )

    def action_open_voided_consumption(self):
        return self._action_list(
            "justech.do.ncf.consumption",
            _("NCF anulados"),
            [("company_id", "=", self.company_id.id), ("state", "=", "voided")],
        )

    def action_open_document_types(self):
        return self._action_list(
            "justech.do.fiscal.document.type",
            _("Tipos de comprobante"),
            [("company_id", "in", (False, self.company_id.id))],
        )

    def action_run_diagnostic(self):
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

    def action_open_ncf_migration(self):
        return self.env["justech.do.ncf.migration.wizard"].action_open_wizard()

    def action_open_ncf_reconcile(self):
        return self.env["justech.do.ncf.reconcile.wizard"].action_open_wizard()

    def _action_list(self, model, title, domain=None):
        return {
            "type": "ir.actions.act_window",
            "name": title,
            "res_model": model,
            "view_mode": "list,form",
            "domain": domain or [("company_id", "=", self.company_id.id)],
            "context": {"default_company_id": self.company_id.id},
        }
