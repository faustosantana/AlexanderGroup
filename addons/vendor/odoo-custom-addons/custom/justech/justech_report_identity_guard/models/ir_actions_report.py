# -*- coding: utf-8 -*-
from odoo import api, models, _
from odoo.exceptions import UserError

from ..hooks import FORBIDDEN_REPORT_PREFIXES, OFFICIAL_REPORT_BINDINGS


def _is_forbidden_template(report_name):
    if not report_name:
        return False
    name = report_name.strip()
    for prefix in FORBIDDEN_REPORT_PREFIXES:
        if name.startswith(prefix) or ("hellenia" in name.lower() and "justech_report_design" in name):
            return True
    if name.startswith("justech_report_design.") or "report_hellenia_" in name:
        return True
    return False


class IrActionsReport(models.Model):
    _inherit = "ir.actions.report"

    def _jt_guard_enabled(self):
        icp = self.env["ir.config_parameter"].sudo()
        return icp.get_param("justech_report_identity_guard.enabled", "1") == "1"

    def _jt_assert_allowed_report_name(self, report_name, context_label=""):
        if not self._jt_guard_enabled():
            return
        if _is_forbidden_template(report_name):
            raise UserError(
                _(
                    "Error de configuración de reportes: la plantilla '%(tpl)s' "
                    "pertenece a Hellenia / justech_report_design y no puede usarse "
                    "en Justgroup. Cada empresa debe usar su identidad corporativa "
                    "(Odoo estándar + Studio + logo). No hay sustitución automática "
                    "por plantillas de otra marca.%(ctx)s"
                )
                % {
                    "tpl": report_name,
                    "ctx": (" [%s]" % context_label) if context_label else "",
                }
            )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            self._jt_assert_allowed_report_name(
                vals.get("report_name") or vals.get("report_file"),
                "create",
            )
        return super().create(vals_list)

    def write(self, vals):
        if (
            self._jt_guard_enabled()
            and not self.env.context.get("jt_report_identity_restore")
            and ("report_name" in vals or "report_file" in vals)
        ):
            candidate = vals.get("report_name") or vals.get("report_file")
            self._jt_assert_allowed_report_name(candidate, "write")
            for action in self:
                xmlid = action.get_external_id().get(action.id)
                if xmlid in OFFICIAL_REPORT_BINDINGS and candidate:
                    expected = OFFICIAL_REPORT_BINDINGS[xmlid]["report_name"]
                    if candidate != expected:
                        raise UserError(
                            _(
                                "Error de configuración: la acción oficial '%(xmlid)s' "
                                "debe usar la plantilla '%(expected)s'. "
                                "Se intentó asignar '%(got)s'. "
                                "No se permite reutilizar plantillas de otra empresa/marca."
                            )
                            % {
                                "xmlid": xmlid,
                                "expected": expected,
                                "got": candidate,
                            }
                        )
        return super().write(vals)

    def _render_qweb_pdf(self, report_ref, res_ids=None, data=None):
        if self._jt_guard_enabled():
            report_name = None
            if isinstance(report_ref, str):
                report_name = report_ref
                try:
                    report = self._get_report(report_ref)
                    report_name = report.report_name or report_ref
                except Exception:
                    report_name = report_ref
            elif isinstance(report_ref, models.BaseModel):
                report_name = report_ref[:1].report_name
            self._jt_assert_allowed_report_name(report_name, "render_qweb_pdf")
            if report_name:
                View = self.env["ir.ui.view"].sudo()
                exists = bool(self.env.ref(report_name, raise_if_not_found=False)) or bool(
                    View.search_count([("key", "=", report_name), ("type", "=", "qweb")], limit=1)
                )
                if not exists:
                    raise UserError(
                        _(
                            "Error de configuración de reportes: falta la plantilla QWeb "
                            "'%(tpl)s'. No se sustituirá por una plantilla de otra empresa. "
                            "Restaure la plantilla corporativa correcta o contacte a soporte."
                        )
                        % {"tpl": report_name}
                    )
        return super()._render_qweb_pdf(report_ref, res_ids=res_ids, data=data)
