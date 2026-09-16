from odoo import api, models

# CRM core menus ship es_DO="Leads". Do not edit core; overlay language only.
CRM_LEAD_MENU_XMLIDS = (
    "crm.crm_menu_leads",
    "crm.crm_opportunity_report_menu_lead",
)

# Default demo/core labels only. Never rename custom stages or partner names.
CRM_STAGE_RENAMES = {
    "New": "Nuevo",
    "Qualified": "Calificado",
    "Proposition": "Propuesta",
    "Won": "Ganado",
    "Lost": "Perdido",
}
CRM_TEAM_RENAMES = {
    "Sales": "Ventas",
    "Point of Sale": "Punto de venta",
    "Website": "Sitio web",
}

APPROVAL_STATE_MODELS = (
    "sale.order",
    "purchase.order",
    "account.move",
    "account.bank.statement.line",
)


class IrUiMenu(models.Model):
    _inherit = "ir.ui.menu"

    def init(self):
        super().init()
        self._dx_apply_spanish_menu_overrides()

    @api.model
    def _dx_apply_spanish_menu_overrides(self):
        for xmlid in CRM_LEAD_MENU_XMLIDS:
            menu = self.env.ref(xmlid, raise_if_not_found=False)
            if menu:
                menu.with_context(lang="es_DO").name = "Iniciativas"
        fields = (
            self.env["ir.model.fields"]
            .sudo()
            .search(
                [
                    ("name", "=", "justech_approval_state"),
                    ("model", "in", list(APPROVAL_STATE_MODELS)),
                ]
            )
        )
        for field in fields:
            field.with_context(lang="es_DO").field_description = "Estado de aprobación"
            field.with_context(lang="en_US").field_description = "Estado de aprobación"
        self._dx_apply_spanish_crm_records()

    @api.model
    def _dx_apply_spanish_crm_records(self):
        if "crm.stage" in self.env:
            for stage in self.env["crm.stage"].sudo().search([]):
                spanish = CRM_STAGE_RENAMES.get(stage.name)
                if spanish:
                    stage.with_context(lang="es_DO").name = spanish
                    stage.with_context(lang="en_US").name = spanish
        if "crm.team" in self.env:
            for team in self.env["crm.team"].sudo().search([]):
                spanish = CRM_TEAM_RENAMES.get(team.name)
                if spanish:
                    team.with_context(lang="es_DO").name = spanish
                    team.with_context(lang="en_US").name = spanish
