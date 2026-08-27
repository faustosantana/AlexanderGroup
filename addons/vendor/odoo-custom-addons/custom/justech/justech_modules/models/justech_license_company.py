from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class JustechLicenseCompany(models.Model):
    _name = "justech.license.company"
    _description = "Company covered by a License"
    _order = "license_id, company_id"

    license_id = fields.Many2one(
        "justech.license",
        required=True,
        ondelete="cascade",
        index=True,
    )
    company_id = fields.Many2one(
        "res.company",
        required=True,
        ondelete="cascade",
        index=True,
    )

    _license_company_unique = models.Constraint(
        "UNIQUE(license_id, company_id)",
        "Company already assigned to this license.",
    )

    _company_license_idx = models.Index("(company_id, license_id)")

    def init(self):
        """Remove legacy duplicates before UNIQUE constraint (F31.1.2 CONC-01)."""
        self.env.cr.execute(
            """
            DELETE FROM justech_license_company a
            USING justech_license_company b
            WHERE a.id > b.id
              AND a.license_id = b.license_id
              AND a.company_id = b.company_id
            """
        )
        super().init()

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if self.search_count(
                [
                    ("license_id", "=", vals.get("license_id")),
                    ("company_id", "=", vals.get("company_id")),
                ]
            ):
                raise ValidationError(
                    _("Company already assigned to this license.")
                )
        records = super().create(vals_list)
        records.mapped("license_id")._check_max_companies()
        self.env["justech.license.service"].clear_license_cache()
        return records

    def write(self, vals):
        res = super().write(vals)
        self.mapped("license_id")._check_max_companies()
        if {"license_id", "company_id"} & set(vals):
            self.env["justech.license.service"].clear_license_cache()
        return res

    def unlink(self):
        licenses = self.mapped("license_id")
        res = super().unlink()
        licenses._check_max_companies()
        self.env["justech.license.service"].clear_license_cache()
        return res
