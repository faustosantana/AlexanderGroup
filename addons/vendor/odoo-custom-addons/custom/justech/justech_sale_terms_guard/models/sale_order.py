# -*- coding: utf-8 -*-
import re

from odoo import api, models, _
from odoo.exceptions import UserError
from odoo.tools import html2plaintext

# Fingerprints of Hellenia / justech_report_design default quotation terms.
# Not Justgroup corporate terms — used only to block known contamination.
HELLENIA_TERM_FINGERPRINTS = (
    "piezas ofrecidas son únicas",
    "pago del 100% para reservar",
    "asesoría de colocación",
    "marcas propias del tiempo",
    "styling disponible bajo cotización",
    "styling disponible bajo cotizacion",
)


def _plain(text):
    if not text:
        return ""
    if isinstance(text, str) and "<" in text:
        try:
            return html2plaintext(text) or ""
        except Exception:
            return re.sub(r"<[^>]+>", " ", text)
    return str(text)


def _contains_hellenia_terms(text):
    plain = _plain(text).lower()
    if not plain.strip():
        return False
    return any(fp in plain for fp in HELLENIA_TERM_FINGERPRINTS)


class SaleOrder(models.Model):
    _inherit = "sale.order"

    def _jt_terms_guard_enabled(self):
        return (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("justech_sale_terms_guard.enabled", "1")
            == "1"
        )

    def _jt_assert_note_not_hellenia(self, note, context_label=""):
        if not self._jt_terms_guard_enabled():
            return
        if _contains_hellenia_terms(note):
            raise UserError(
                _(
                    "Error de configuración: los términos contienen texto Hellenia "
                    "('piezas únicas' / 'styling' / '100%% para reservar'). "
                    "Justgroup no usa ese contenido corporativo. "
                    "Use términos de la empresa activa o déjelos vacíos.%(ctx)s"
                )
                % {"ctx": (" [%s]" % context_label) if context_label else ""}
            )

    def _jt_assert_template_company(self, template, company):
        if not self._jt_terms_guard_enabled() or not template:
            return
        tmpl = template
        if not isinstance(template, models.BaseModel):
            tmpl = self.env["sale.order.template"].browse(template)
        if not tmpl.exists():
            return
        if tmpl.company_id and company and tmpl.company_id != company:
            raise UserError(
                _(
                    "Error de configuración: la plantilla '%(tmpl)s' pertenece a "
                    "%(tmpl_co)s y no puede usarse en cotizaciones de %(co)s. "
                    "No hay herencia cruzada de términos entre empresas."
                )
                % {
                    "tmpl": tmpl.display_name,
                    "tmpl_co": tmpl.company_id.display_name,
                    "co": company.display_name,
                }
            )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            self._jt_assert_note_not_hellenia(vals.get("note"), "create")
            if vals.get("sale_order_template_id"):
                company = self.env["res.company"].browse(
                    vals.get("company_id") or self.env.company.id
                )
                self._jt_assert_template_company(
                    vals["sale_order_template_id"], company
                )
        return super().create(vals_list)

    def write(self, vals):
        if "note" in vals:
            self._jt_assert_note_not_hellenia(vals.get("note"), "write")
        if "sale_order_template_id" in vals and vals.get("sale_order_template_id"):
            for order in self:
                company = order.company_id
                if vals.get("company_id"):
                    company = self.env["res.company"].browse(vals["company_id"])
                self._jt_assert_template_company(
                    vals["sale_order_template_id"], company
                )
        if "company_id" in vals and vals.get("company_id"):
            company = self.env["res.company"].browse(vals["company_id"])
            for order in self:
                tmpl_id = vals.get("sale_order_template_id", order.sale_order_template_id.id)
                if tmpl_id:
                    self._jt_assert_template_company(tmpl_id, company)
            if "note" not in vals:
                # Changing company must not silently keep another brand's note if Hellenia
                for order in self:
                    if _contains_hellenia_terms(order.note):
                        raise UserError(
                            _(
                                "La cotización %(name)s tiene términos Hellenia. "
                                "Límpielos antes de cambiar de empresa."
                            )
                            % {"name": order.name}
                        )
        return super().write(vals)

    @api.onchange("sale_order_template_id")
    def _onchange_sale_order_template_id_jt_terms_guard(self):
        if self.sale_order_template_id and self.company_id:
            try:
                self._jt_assert_template_company(
                    self.sale_order_template_id, self.company_id
                )
            except UserError as err:
                self.sale_order_template_id = False
                return {"warning": {"title": _("Plantilla bloqueada"), "message": str(err)}}
