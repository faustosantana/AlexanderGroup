"""Optional mixin for future license gates (F31.1.5 — no blocking yet)."""

from odoo import models


class JustechLicenseMixin(models.AbstractModel):
    _name = "justech.license.mixin"
    _description = "Justech License Helper Mixin"

    def _justech_service(self):
        return self.env["justech.license.service"]

    def _justech_is_active(self, feature_code, company=None):
        company = company or self.env.company
        return self._justech_service().is_active(feature_code, company=company)

    def _justech_require_active(self, feature_code, company=None):
        company = company or self.env.company
        return self._justech_service().require_active(
            feature_code, company=company
        )
