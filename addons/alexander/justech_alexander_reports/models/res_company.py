import base64
import logging
import re
from io import BytesIO

from odoo import api, models
from odoo.tools.image import image_data_uri
from odoo.tools.misc import format_date

_logger = logging.getLogger(__name__)

# V5.1: mismos hex. Logos +15–35% vs V5, por proporción (no un tamaño fijo).
# No recolorear. DOM/MAY sobre papel blanco (logo_on_dark False).
_DX_THEMES = {
    "DOR": {
        "code": "DOR",
        "layout": "dor",
        "primary": "#E46018",
        "secondary": "#1A1A1A",
        "accent": "#E46018",
        "neutral": "#5C5C5C",
        "logo_h": 38,
        "logo_w": 44,
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
        "logo_h": 34,
        "logo_w": 36,
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
        "logo_h": 34,
        "logo_w": 40,
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
        "logo_h": 26,
        "logo_w": 68,
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
        "logo_h": 44,
        "logo_w": 54,
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
        "logo_h": 38,
        "logo_w": 44,
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

    def _dx_header_meta_for(self, record):
        self.ensure_one()
        meta = {
            "date": "—",
            "validity": "—",
            "due": "—",
            "date2_label": "Validez",
            "salesperson": "—",
            "currency": "",
            "ncf": "",
        }
        if not record:
            return meta

        def _fmt(value):
            if not value:
                return "—"
            if hasattr(value, "date"):
                value = value.date()
            return format_date(self.env, value)

        user = False
        if record._name == "account.move" and "invoice_user_id" in record._fields:
            user = record.invoice_user_id
        elif "user_id" in record._fields:
            user = record.user_id
        name = (user.name or "").strip() if user else ""
        if name in ("OdooBot", "Administrator", "Public user", "Public User", ""):
            name = "Equipo comercial" if name else "—"
        meta["salesperson"] = name
        if "currency_id" in record._fields and record.currency_id:
            meta["currency"] = record.currency_id.name or ""
        if record._name == "sale.order":
            meta["date"] = _fmt(record.date_order)
            meta["validity"] = _fmt(record.validity_date)
            meta["date2_label"] = "Validez"
        elif record._name == "account.move":
            meta["date"] = _fmt(record.invoice_date or record.date)
            meta["due"] = _fmt(record.invoice_date_due)
            meta["validity"] = meta["due"]
            meta["date2_label"] = "Vencimiento"
            if "justech_do_ncf" in record._fields:
                meta["ncf"] = record.justech_do_ncf or ""
        elif record._name == "purchase.order":
            meta["date"] = _fmt(record.date_order)
            planned = record.date_planned if "date_planned" in record._fields else False
            meta["validity"] = _fmt(planned) if planned else "—"
            meta["date2_label"] = "Entrega"
        elif record._name == "stock.picking":
            meta["date"] = _fmt(record.scheduled_date or record.date_done)
            meta["date2_label"] = "Origen"
            meta["validity"] = record.origin or "—"
        elif record._name == "account.payment":
            meta["date"] = _fmt(record.date)
            meta["validity"] = ""
            meta["salesperson"] = ""
            meta["date2_label"] = ""
        elif record._name == "res.partner":
            meta["date"] = ""
            meta["validity"] = ""
            meta["salesperson"] = ""
            meta["date2_label"] = ""
        return meta

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

    def _dx_logo_content_bbox(self, image, pad_ratio=0.02):
        """Bounding box del contenido real (alpha + no-blanco), sin deformar."""
        image = image.convert("RGBA")
        width, height = image.size
        red, green, blue, alpha = image.split()
        gray = image.convert("L")
        dark = gray.point(lambda pixel: 255 if pixel < 245 else 0)
        opaque = alpha.point(lambda pixel: 255 if pixel > 10 else 0)
        try:
            from PIL import ImageChops

            mask = ImageChops.multiply(dark, opaque)
            box = mask.getbbox()
        except Exception:
            box = opaque.getbbox()
        if not box:
            box = opaque.getbbox() or (0, 0, width, height)
        pad = max(2, int(min(width, height) * pad_ratio))
        left, top, right, bottom = box
        return (
            max(0, left - pad),
            max(0, top - pad),
            min(width, right + pad),
            min(height, bottom + pad),
        )

    def _dx_crop_logo_payload(self, raw):
        """Recorta whitespace interno del PNG. No recolorea. Si falla, original."""
        if not raw:
            return raw
        try:
            from PIL import Image
        except ImportError:
            return raw
        try:
            blob = base64.b64decode(raw)
            if b"<svg" in blob[:500].lower():
                return raw
            image = Image.open(BytesIO(blob))
        except Exception:
            return raw
        try:
            box = self._dx_logo_content_bbox(image)
            cropped = image.convert("RGBA").crop(box)
            if cropped.size[0] < 8 or cropped.size[1] < 8:
                return raw
            out = BytesIO()
            cropped.save(out, format="PNG")
            return base64.b64encode(out.getvalue())
        except Exception:
            _logger.debug("dx logo crop skipped for company %s", self.id, exc_info=True)
            return raw

    def _dx_report_logo_src(self):
        self.ensure_one()
        if not self.logo:
            return ""
        payload = self._dx_crop_logo_payload(self.logo)
        try:
            return image_data_uri(payload)
        except Exception:
            return image_data_uri(self.logo)

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
