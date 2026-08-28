from odoo import models


class ResCompany(models.Model):
    _inherit = "res.company"

    def _dx_vat_display(self):
        self.ensure_one()
        raw = (self.vat or "").replace("-", "").replace(" ", "")
        if len(raw) == 9 and raw.isdigit():
            return "%s-%s-%s-%s" % (raw[0], raw[1:3], raw[3:8], raw[8])
        return self.vat or ""

    def _dx_report_banks(self):
        self.ensure_one()
        if not self.dx_report_show_bank:
            return self.env["res.partner.bank"]
        return self.partner_id.sudo().bank_ids

    def _dx_report_logo_style(self):
        self.ensure_one()
        height = self.dx_report_logo_height or 18
        return "max-height: %smm; max-width: 55mm;" % height
