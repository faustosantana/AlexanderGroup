from odoo import api, fields, models


class JustechLicenseFeature(models.Model):
    _name = "justech.license.feature"
    _description = "Feature included in a License"
    _order = "license_id, feature_id"

    license_id = fields.Many2one(
        "justech.license",
        required=True,
        ondelete="cascade",
        index=True,
    )
    feature_id = fields.Many2one(
        "justech.feature",
        required=True,
        ondelete="restrict",
        index=True,
    )

    _license_feature_unique = models.Constraint(
        "UNIQUE(license_id, feature_id)",
        "Feature already included in this license.",
    )

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        self.env["justech.license.service"].clear_license_cache()
        return records

    def unlink(self):
        res = super().unlink()
        self.env["justech.license.service"].clear_license_cache()
        return res
