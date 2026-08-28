# -*- coding: utf-8 -*-
from odoo import api, models, _
from odoo.exceptions import UserError

from .sale_order import _contains_hellenia_terms


class SaleOrderTemplate(models.Model):
    _inherit = "sale.order.template"

    def _jt_terms_guard_enabled(self):
        return (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("justech_sale_terms_guard.enabled", "1")
            == "1"
        )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if self._jt_terms_guard_enabled() and _contains_hellenia_terms(vals.get("note")):
                raise UserError(
                    _(
                        "No se puede guardar una plantilla de cotización con "
                        "términos Hellenia. Use contenido propio de la empresa."
                    )
                )
            # Corporate note content requires company_id (no global brand text)
            if (
                self._jt_terms_guard_enabled()
                and vals.get("note")
                and str(vals.get("note")).strip()
                and not vals.get("company_id")
            ):
                # allow empty; if note set without company → block
                from odoo.tools import is_html_empty

                if not is_html_empty(vals.get("note")):
                    raise UserError(
                        _(
                            "Plantilla con términos debe tener compañía (company_id). "
                            "No se permiten términos globales corporativos."
                        )
                    )
        return super().create(vals_list)

    def write(self, vals):
        if self._jt_terms_guard_enabled():
            if "note" in vals and _contains_hellenia_terms(vals.get("note")):
                raise UserError(
                    _(
                        "No se puede guardar una plantilla de cotización con "
                        "términos Hellenia."
                    )
                )
            for tmpl in self:
                note = vals["note"] if "note" in vals else tmpl.note
                company = (
                    vals["company_id"]
                    if "company_id" in vals
                    else tmpl.company_id.id
                )
                from odoo.tools import is_html_empty

                if note and not is_html_empty(note) and not company:
                    raise UserError(
                        _(
                            "Plantilla con términos debe tener compañía (company_id)."
                        )
                    )
        return super().write(vals)
