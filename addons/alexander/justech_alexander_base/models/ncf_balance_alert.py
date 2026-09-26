"""Read-only NCF balance diagnostic. Does not consume or auto-renew ranges."""

from datetime import timedelta

from odoo import api, fields, models

WARNING_REMAINING = 10
CRITICAL_REMAINING = 3
EXPIRY_ALERT_DAYS = 30


def classify_ncf_balance(remaining_count, date_to, today):
    if date_to and today > date_to:
        return "EXPIRED"
    left = int(remaining_count or 0)
    if left <= 0:
        return "EXHAUSTED"
    if left <= CRITICAL_REMAINING:
        return "CRITICAL"
    if left <= WARNING_REMAINING:
        return "WARNING"
    if date_to and today <= date_to <= today + timedelta(days=EXPIRY_ALERT_DAYS):
        return "WARNING"
    return "NORMAL"


class JustechDoNcfRange(models.Model):
    _inherit = "justech.do.ncf.range"

    dx_ncf_last_used_display = fields.Char(
        string="Último NCF",
        compute="_compute_dx_ncf_balance",
    )
    dx_ncf_balance_level = fields.Selection(
        selection=[
            ("NORMAL", "Normal"),
            ("WARNING", "Advertencia"),
            ("CRITICAL", "Crítico"),
            ("EXHAUSTED", "Agotado"),
            ("EXPIRED", "Vencido"),
        ],
        string="Alerta saldo",
        compute="_compute_dx_ncf_balance",
    )

    @api.depends("prefix", "next_sequence", "remaining_count", "date_to", "state")
    def _compute_dx_ncf_balance(self):
        today = fields.Date.context_today(self)
        for rec in self:
            last = int(rec.next_sequence or 1) - 1
            if rec.prefix and last > 0:
                rec.dx_ncf_last_used_display = f"{rec.prefix}{last:08d}"
            else:
                rec.dx_ncf_last_used_display = False
            if rec.state == "expired" or (rec.date_to and today > rec.date_to):
                rec.dx_ncf_balance_level = "EXPIRED"
            elif rec.state == "depleted" or rec.remaining_count <= 0:
                rec.dx_ncf_balance_level = "EXHAUSTED"
            else:
                rec.dx_ncf_balance_level = classify_ncf_balance(
                    rec.remaining_count, rec.date_to, today
                )

    @api.model
    def dx_classify_ncf_balance(self, remaining_count, date_to, today=None):
        today = today or fields.Date.context_today(self)
        return classify_ncf_balance(remaining_count, date_to, today)

    def dx_preview_next_ncf(self):
        """Display the next NCF without consuming it."""
        self.ensure_one()
        return self.next_ncf_display
