from odoo import fields, models

from ..hooks import ECF_PARAM, apply_ecf_operational_state


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

    def get_values(self):
        res = super().get_values()
        raw = self.env["ir.config_parameter"].sudo().get_param(ECF_PARAM, "")
        # Odoo 19 converts config_parameter booleans with bool("False") → True.
        res["justech_ecf_operational_enabled"] = raw in ("True", "true", "1")
        return res

    def set_values(self):
        super().set_values()
        apply_ecf_operational_state(
            self.env, enabled=bool(self.justech_ecf_operational_enabled)
        )
