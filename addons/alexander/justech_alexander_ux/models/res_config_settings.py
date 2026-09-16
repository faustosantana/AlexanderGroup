from odoo import fields, models

from ..hooks import (
    APPROVAL_PARAM,
    ECF_PARAM,
    PADRON_PARAM,
    apply_ecf_operational_state,
    apply_padron_disabled,
)


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    justech_ecf_operational_enabled = fields.Boolean(
        string="Activar facturación electrónica (e-CF)",
        config_parameter=ECF_PARAM,
        default=False,
        help=(
            "Cuando está desactivado, los menús e-CF/DGII se ocultan al usuario "
            "normal y se detienen las colas/crons. Los módulos siguen instalados."
        ),
    )
    justech_approval_flow_enabled = fields.Boolean(
        string="Flujo de aprobaciones Alexander",
        default=False,
        readonly=True,
        help="Desactivado por decisión de negocio. El módulo permanece instalado.",
    )
    justech_dgii_padron_enabled = fields.Boolean(
        string="Padrón DGII",
        default=False,
        readonly=True,
        help="Desactivado. No descarga, no importa, no sincroniza.",
    )

    def get_values(self):
        res = super().get_values()
        icp = self.env["ir.config_parameter"].sudo()
        raw = icp.get_param(ECF_PARAM, "")
        # Odoo 19 converts config_parameter booleans with bool("False") → True.
        res["justech_ecf_operational_enabled"] = raw in ("True", "true", "1")
        res["justech_approval_flow_enabled"] = icp.get_param(APPROVAL_PARAM, "") in (
            "True",
            "true",
            "1",
        )
        res["justech_dgii_padron_enabled"] = icp.get_param(PADRON_PARAM, "") in (
            "True",
            "true",
            "1",
        )
        return res

    def set_values(self):
        super().set_values()
        apply_ecf_operational_state(
            self.env, enabled=bool(self.justech_ecf_operational_enabled)
        )
        apply_padron_disabled(self.env)
