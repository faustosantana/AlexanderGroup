import re

from odoo import api, models

# Paleta V4: DOR/PIN/REM/BLU de logos DEV; DOM/MAY de PNG oficiales 2026-08-29.
# No recolorear logos. DOM/MAY van sobre papel blanco (logo_on_dark False).
_DX_THEMES = {
    "DOR": {
        "code": "DOR",
        "layout": "dor",
        "primary": "#E46018",
        "secondary": "#1A1A1A",
        "accent": "#E46018",
        "neutral": "#5C5C5C",
        "logo_h": 28,
        "logo_w": 32,
        "logo_on_dark": False,
        "logo_source": "res.company.logo DOR.png",
    },
    "PIN": {
        "code": "PIN",
        "layout": "pin",
        "primary": "#30A83C",
        "secondary": "#C00000",
        "accent": "#C00000",
        "neutral": "#5C5C5C",
        "logo_h": 30,
        "logo_w": 32,
        "logo_on_dark": False,
        "logo_source": "res.company.logo PIN.png",
    },
    "DOM": {
        "code": "DOM",
        "layout": "dom",
        "primary": "#50B0B0",
        "secondary": "#F09040",
        "accent": "#F09040",
        "neutral": "#5C5C5C",
        "logo_h": 30,
        "logo_w": 32,
        "logo_on_dark": False,
        "logo_source": "user PNG Dominion Business 2026-08-29",
    },
    "MAY": {
        "code": "MAY",
        "layout": "may",
        "primary": "#1A1A1A",
        "secondary": "#54B4A8",
        "accent": "#54B4A8",
        "neutral": "#5C5C5C",
        "logo_h": 20,
        "logo_w": 56,
        "logo_on_dark": False,
        "logo_source": "user PNG El Mayuma 2026-08-29",
    },
    "REM": {
        "code": "REM",
        "layout": "rem",
        "primary": "#1A1A1A",
        "secondary": "#3048A8",
        "accent": "#3048A8",
        "neutral": "#5C5C5C",
        "logo_h": 36,
        "logo_w": 42,
        "logo_on_dark": False,
        "logo_source": "res.company.logo REM.png",
    },
    "BLU": {
        "code": "BLU",
        "layout": "blu",
        "primary": "#243C9C",
        "secondary": "#18B4F0",
        "accent": "#18B4F0",
        "neutral": "#5C5C5C",
        "logo_h": 30,
        "logo_w": 34,
        "logo_on_dark": False,
        "logo_source": "res.company.logo BLU.png",
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

    def _dx_legal_display(self):
        self.ensure_one()
        name = re.sub(r"\s+", " ", (self.name or "").strip())
        name = re.sub(r",\s*", ", ", name)
        name = re.sub(r"S\.?\s*R\.?\s*L\.?", "S.R.L.", name, flags=re.I)
        return name

    def _dx_street_display(self):
        self.ensure_one()
        street = (self.street or "").strip()
        if street and street == street.upper():
            street = street.title().replace("S.R.L.", "S.R.L.")
        return street

    def _dx_city_display(self):
        self.ensure_one()
        city = (self.city or "").strip()
        if city and city == city.upper():
            city = city.title()
        return city

    def _dx_header_identity_for(self, record):
        self.ensure_one()
        if record and hasattr(record, "_dx_doc_identity"):
            try:
                return record._dx_doc_identity()
            except Exception:
                return {}
        return {}

    def _dx_report_theme(self):
        self.ensure_one()
        code = (self.dx_short_code or "").upper()
        theme = dict(_DX_THEMES.get(code) or {"code": code or "DX", "layout": "dor"})
        theme.setdefault("primary", self.primary_color or "#1A1A1A")
        theme.setdefault("secondary", self.secondary_color or "#555555")
        theme.setdefault("logo_h", self.dx_report_logo_height or 20)
        theme.setdefault("logo_w", 48)
        theme.setdefault("logo_on_dark", False)
        theme.setdefault("layout", "dor")
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
