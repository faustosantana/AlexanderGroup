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

    def set_values(self):
        super().set_values()
        apply_ecf_operational_state(
            self.env, enabled=bool(self.justech_ecf_operational_enabled)
        )
