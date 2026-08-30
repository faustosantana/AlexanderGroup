from odoo import api, models

# CRM core menus ship es_DO="Leads". Do not edit core; overlay language only.
CRM_LEAD_MENU_XMLIDS = (
    "crm.crm_menu_leads",
    "crm.crm_opportunity_report_menu_lead",
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
