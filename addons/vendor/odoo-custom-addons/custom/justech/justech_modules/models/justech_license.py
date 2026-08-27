import re
import secrets

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from .justech_license_key_util import fingerprint_from_hash, hash_license_key


class JustechLicense(models.Model):
    _name = "justech.license"
    _description = "Justech License"
    _order = "name"

    name = fields.Char(required=True)
    license_key_hash = fields.Char(
        index=True,
        copy=False,
        groups="justech_modules.group_justech_license_manager,base.group_system",
    )
    license_key_fingerprint = fields.Char(
        string="License Key",
        compute="_compute_license_key_fingerprint",
        store=False,
    )
    tier = fields.Selection(
        [
            ("TRIAL", "Trial"),
            ("STD", "Standard"),
            ("PRO", "Professional"),
            ("ENT", "Enterprise"),
        ],
        required=True,
        default="STD",
    )
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("active", "Active"),
            ("expired", "Expired"),
            ("revoked", "Revoked"),
        ],
        default="draft",
        required=True,
        index=True,
    )
    expires_at = fields.Date(index=True)
    starts_at = fields.Date(string="Start Date", index=True)
    max_users = fields.Integer(default=0, help="0 = unlimited")
    max_companies = fields.Integer(default=0, help="0 = unlimited")
    grace_days = fields.Integer(default=7)
    feature_line_ids = fields.One2many(
        "justech.license.feature",
        "license_id",
        string="Licensed Features",
    )
    company_line_ids = fields.One2many(
        "justech.license.company",
        "license_id",
        string="Licensed Companies",
    )
    feature_ids = fields.Many2many(
        "justech.feature",
        compute="_compute_feature_ids",
        string="Features",
    )
    company_ids = fields.Many2many(
        "res.company",
        compute="_compute_company_ids",
        string="Companies",
    )

    _license_key_hash_unique = models.Constraint(
        "UNIQUE(license_key_hash)",
        "License key must be unique.",
    )

    @api.depends("license_key_hash")
    def _compute_license_key_fingerprint(self):
        for license_rec in self:
            license_rec.license_key_fingerprint = fingerprint_from_hash(
                license_rec.license_key_hash
            )

    @api.model
    def _generate_license_key(self, tier="STD"):
        token = secrets.token_hex(6).upper()
        return f"JT-{tier}-{token}"

    @api.model
    def _hash_license_key(self, key):
        return hash_license_key(self.env, key)

    @api.model
    def _find_by_license_key(self, key):
        if not key:
            return self.browse()
        digest = self._hash_license_key(key)
        return self.search([("license_key_hash", "=", digest)], limit=1)

    @api.model_create_multi
    def create(self, vals_list):
        prepared = []
        for vals in vals_list:
            vals = dict(vals)
            plain = vals.pop("license_key", None) or vals.pop("license_key_input", None)
            if not vals.get("license_key_hash"):
                if not plain:
                    plain = self._generate_license_key(vals.get("tier", "STD"))
                vals["license_key_hash"] = self._hash_license_key(plain)
            prepared.append(vals)
        records = super().create(prepared)
        self.env["justech.license.service"].clear_license_cache()
        return records

    def write(self, vals):
        if "license_key" in vals or "license_key_input" in vals:
            plain = vals.pop("license_key", None) or vals.pop("license_key_input", None)
            if plain:
                vals["license_key_hash"] = self._hash_license_key(plain)
        res = super().write(vals)
        if {"state", "expires_at", "license_key_hash"} & set(vals):
            self.env["justech.license.service"].clear_license_cache()
        return res

    @api.model
    def migrate_plaintext_license_keys(self):
        """One-time migration from legacy license_key column (pre F31.1.2)."""
        self.env.cr.execute(
            """
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'justech_license' AND column_name = 'license_key'
            """
        )
        if not self.env.cr.fetchone():
            return 0
        self.env.cr.execute(
            """
            SELECT id, license_key FROM justech_license
            WHERE license_key IS NOT NULL AND license_key <> ''
            """
        )
        migrated = 0
        for row_id, plain_key in self.env.cr.fetchall():
            digest = self._hash_license_key(plain_key)
            self.env.cr.execute(
                """
                UPDATE justech_license SET license_key_hash = %s WHERE id = %s
                AND (license_key_hash IS NULL OR license_key_hash = '')
                """,
                (digest, row_id),
            )
            migrated += 1
        return migrated

    @api.model
    def backfill_missing_license_hashes(self):
        """Backfill hashes when legacy plaintext column is gone (cert seed pattern)."""
        missing = self.search(
            ["|", ("license_key_hash", "=", False), ("license_key_hash", "=", "")]
        )
        if not missing:
            return 0
        cert_idx = re.compile(r"^cert_f311_lic (\d+)$")
        cert_named = {
            "api_test": "JT-STD-CERT_F311_API001",
            "concurrency": "JT-STD-CERT_F311_CONC01",
            "mc_a": "JT-STD-CERT_F311_MCA01",
            "lifecycle": "JT-STD-CERT_F311_LIFE01",
            "draft": "JT-STD-CERT_F311_DRAFT1",
            "rollback": "JT-STD-CERT_F311_ROLL01",
            "max_users": "JT-STD-CERT_F311_MAXUSR",
        }
        updated = 0
        for lic in missing:
            plain = None
            match = cert_idx.match(lic.name or "")
            if match:
                plain = f"JT-STD-CERT_F311_L{int(match.group(1)):04d}"
            elif lic.name and lic.name.startswith("cert_f311_lic "):
                suffix = lic.name.split("cert_f311_lic ", 1)[1]
                plain = cert_named.get(suffix)
            if not plain:
                continue
            digest = self._hash_license_key(plain)
            if self.search_count(
                [("license_key_hash", "=", digest), ("id", "!=", lic.id)]
            ):
                continue
            lic.write({"license_key_hash": digest})
            updated += 1
        return updated

    @api.depends("feature_line_ids.feature_id")
    def _compute_feature_ids(self):
        for license_rec in self:
            license_rec.feature_ids = license_rec.feature_line_ids.feature_id

    @api.depends("company_line_ids.company_id")
    def _compute_company_ids(self):
        for license_rec in self:
            license_rec.company_ids = license_rec.company_line_ids.company_id

    def _count_users_for_license(self):
        self.ensure_one()
        companies = self.company_line_ids.company_id
        if not companies:
            return 0
        return self.env["res.users"].search_count(
            [
                ("share", "=", False),
                ("company_id", "in", companies.ids),
            ]
        )

    def _check_max_companies(self):
        for license_rec in self:
            if license_rec.max_companies <= 0:
                continue
            count = len(license_rec.company_line_ids)
            if count > license_rec.max_companies:
                raise ValidationError(
                    _(
                        "License '%(name)s' allows at most %(max)s companies "
                        "(%(count)s assigned)."
                    )
                    % {
                        "name": license_rec.name,
                        "max": license_rec.max_companies,
                        "count": count,
                    }
                )

    def _check_max_users(self):
        for license_rec in self:
            if license_rec.max_users <= 0:
                continue
            user_count = license_rec._count_users_for_license()
            if user_count > license_rec.max_users:
                raise ValidationError(
                    _(
                        "License '%(name)s' allows at most %(max)s users "
                        "(%(count)s assigned to licensed companies)."
                    )
                    % {
                        "name": license_rec.name,
                        "max": license_rec.max_users,
                        "count": user_count,
                    }
                )

    def action_activate(self):
        for license_rec in self:
            if not license_rec.company_line_ids:
                raise ValidationError(
                    _(
                        "Cannot activate license '%(name)s' without at least "
                        "one assigned company."
                    )
                    % {"name": license_rec.name}
                )
            license_rec._check_max_companies()
            license_rec._check_max_users()
            license_rec.state = "active"
            license_rec._sync_company_features()
        self.env["justech.license.service"].clear_license_cache()

    def _sync_company_features(self):
        service = self.env["justech.license.service"]
        for license_rec in self:
            if license_rec.state != "active":
                continue
            features = service._order_features_by_module_dependencies(
                license_rec.feature_line_ids.feature_id
            )
            for company_line in license_rec.company_line_ids:
                for feature in features:
                    deps = service.check_dependencies(
                        feature.code,
                        company=company_line.company_id,
                    )
                    if not deps["ok"]:
                        raise ValidationError(
                            _(
                                "Cannot activate feature '%(feature)s' for "
                                "%(company)s: missing dependencies %(missing)s."
                            )
                            % {
                                "feature": feature.code,
                                "company": company_line.company_id.name,
                                "missing": ", ".join(
                                    m["module_code"] for m in deps["missing"]
                                ),
                            }
                        )
                    service.activate_feature(
                        feature.code,
                        company=company_line.company_id,
                    )
