# -*- coding: utf-8 -*-
from odoo import _, api, models
from odoo.exceptions import UserError


class JustechDoFiscalAuditActions(models.AbstractModel):
    _name = "justech.do.fiscal.audit.actions"
    _description = "Acciones de menú Auditoría Fiscal"

    @api.model
    def action_open_withholding_catalog(self):
        module = self.env["ir.module.module"].search(
            [("name", "=", "justech_l10n_do_payments_withholding"), ("state", "=", "installed")],
            limit=1,
        )
        if module:
            return self.env.ref(
                "justech_l10n_do_payments_withholding.action_justech_withholding_catalog"
            ).read()[0]
        raise UserError(
            _("Instale el módulo Justech Pagos y Retenciones para administrar retenciones.")
        )
