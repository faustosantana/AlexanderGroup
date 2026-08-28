from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    justech_do_fiscal_enabled = fields.Boolean(
        string="Fiscal dominicano activo",
        default=True,
    )
    justech_do_ncf_alert_days = fields.Integer(
        string="Días de alerta rangos NCF (legado)",
        default=30,
        help="Compatibilidad. Preferir «Días alerta vencimiento».",
    )
    justech_do_ncf_alert_threshold_preventive = fields.Integer(
        string="Umbral preventivo NCF (disponibles)",
        default=20,
    )
    justech_do_ncf_alert_threshold_critical = fields.Integer(
        string="Umbral crítico NCF (disponibles)",
        default=5,
    )
    justech_do_ncf_alert_expiry_days = fields.Integer(
        string="Días alerta vencimiento NCF",
        default=15,
    )
