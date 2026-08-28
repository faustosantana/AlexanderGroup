from odoo import api, models

# Paleta y caja de logo derivadas de los PNG reales (no de colores genéricos).
_DX_THEMES = {
    "DOR": {
        "code": "DOR",
        "primary": "#E86A12",
        "secondary": "#1A1A1A",
        "logo_h": 22,
        "logo_w": 46,
        "logo_on_dark": False,
    },
    "PIN": {
        "code": "PIN",
        "primary": "#C41E3A",
        "secondary": "#2E7D32",
        "logo_h": 26,
        "logo_w": 36,
        "logo_on_dark": False,
    },
    "DOM": {
        "code": "DOM",
        "primary": "#2AA8A4",
        "secondary": "#F08A3C",
        "logo_h": 22,
        "logo_w": 26,
        "logo_on_dark": True,
    },
    "MAY": {
        "code": "MAY",
        "primary": "#2EC4B6",
        "secondary": "#111111",
        "logo_h": 20,
        "logo_w": 62,
        "logo_on_dark": True,
    },
    "REM": {
        "code": "REM",
        "primary": "#1A1A1A",
        "secondary": "#3D7AB5",
        "logo_h": 24,
        "logo_w": 32,
        "logo_on_dark": False,
    },
    "BLU": {
        "code": "BLU",
        "primary": "#0A3D91",
        "secondary": "#00AEEF",
        "logo_h": 24,
        "logo_w": 32,
        "logo_on_dark": False,
    },
}


class ResCompany(models.Model):
    _inherit = "res.company"

    def _dx_vat_display(self):
        self.ensure_one()
        raw = (self.vat or "").replace("-", "").replace(" ", "")
        if len(raw) == 9 and raw.isdigit():
            return "%s-%s-%s-%s" % (raw[0], raw[1:3], raw[3:8], raw[8])
        return self.vat or ""

    def _dx_report_theme(self):
        self.ensure_one()
        code = (self.dx_short_code or "").upper()
        theme = dict(_DX_THEMES.get(code) or {"code": code or "DX"})
        theme.setdefault("primary", self.primary_color or "#1A1A1A")
        theme.setdefault("secondary", self.secondary_color or "#555555")
        theme.setdefault("logo_h", self.dx_report_logo_height or 20)
        theme.setdefault("logo_w", 48)
        theme.setdefault("logo_on_dark", False)
        theme["trade"] = self.dx_trade_name or self.name
        return theme

    def _dx_report_banks(self):
        self.ensure_one()
        if not self.dx_report_show_bank:
            return self.env["res.partner.bank"]
        return self.partner_id.sudo().bank_ids

    def _dx_report_logo_style(self):
        self.ensure_one()
        theme = self._dx_report_theme()
        height = theme.get("logo_h") or self.dx_report_logo_height or 20
        width = theme.get("logo_w") or 48
        return "max-height: %smm; max-width: %smm; width: auto; height: auto;" % (
            height,
            width,
        )

    def _dx_report_missing_fields(self):
        self.ensure_one()
        missing = []
        if not self.logo:
            missing.append("logo")
        if not self.vat:
            missing.append("rnc")
        if not (self.street or self.city):
            missing.append("address")
        if not self.phone:
            missing.append("phone")
        if not self.email:
            missing.append("email")
        if not self.website:
            missing.append("website")
        if not self._dx_report_banks():
            missing.append("bank")
        if not (self.dx_report_terms or self.invoice_terms):
            missing.append("terms")
        return missing

    def _dx_sync_report_brand_colors(self):
        for company in self:
            theme = _DX_THEMES.get((company.dx_short_code or "").upper())
            if not theme:
                continue
            vals = {}
            if company.primary_color != theme["primary"]:
                vals["primary_color"] = theme["primary"]
            if company.secondary_color != theme["secondary"]:
                vals["secondary_color"] = theme["secondary"]
            if vals:
                company.write(vals)
        return True

    @api.model
    def _dx_bootstrap_report_brand(self):
        companies = self.sudo().search([("dx_short_code", "!=", False)])
        companies._dx_sync_report_brand_colors()
        return True
