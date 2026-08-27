from datetime import date

from odoo import _, api, fields, models
from odoo.tools import ormcache

from ..exceptions import JustechLicenseError


class JustechLicenseService(models.AbstractModel):
    _name = "justech.license.service"
    _description = "Justech License Public API"

    API_VERSION = 1

    # ------------------------------------------------------------------ API
    @api.model
    def get_api_version(self):
        """Return stable public API semver major version."""
        return self.API_VERSION

    @api.model
    def clear_license_cache(self):
        """Invalidate cached license lookups (call after license/feature changes)."""
        self.env.registry.clear_cache()

    @api.model
    def is_active(self, feature_code, company=None):
        company = company or self.env.company
        return self._is_active_cached(feature_code, company.id)

    @api.model
    @ormcache("feature_code", "company_id")
    def _is_active_cached(self, feature_code, company_id):
        return self._compute_is_active(feature_code, company_id)

    @api.model
    def _compute_is_active(self, feature_code, company_id):
        company = self.env["res.company"].browse(company_id)
        feature = self._get_feature_record(feature_code)
        if not feature:
            return False
        if feature.always_on:
            return True
        if feature.license_required and not self._feature_granted_to_company(
            feature, company
        ):
            return False
        if not self._feature_is_active_for_company(feature.id, company_id):
            return False
        # LIFE-01: revalidate grant after operational activation flag
        if feature.license_required and not self._feature_granted_to_company(
            feature, company
        ):
            return False
        return True

    @api.model
    def require_active(self, feature_code, company=None):
        if not self.is_active(feature_code, company=company):
            raise JustechLicenseError(
                _("Feature '%(code)s' is not licensed or active for this company.")
                % {"code": feature_code}
            )

    @api.model
    def _sudo_internal(self):
        """Gatekeeper access to internal licensing models (never use from UI)."""
        from odoo import SUPERUSER_ID

        return self.env(user=SUPERUSER_ID)

    @api.model
    def _require_activation_admin(self):
        """UI/admin mutations require step-up verification (even with session)."""
        if self.env.su or self.env.context.get("justech_skip_critical_step_up"):
            return
        self.env["justech.admin.access.service"].require_critical_step_up(
            self.env["justech.admin.access.service"].CRITICAL_PLATFORM_MUTATION
        )

    @api.model
    def _require_license_admin(self):
        """License administration mutations require license step-up grant."""
        if self.env.su or self.env.context.get("justech_skip_critical_step_up"):
            return
        svc = self.env["justech.admin.access.service"]
        token = self.env.context.get("justech_critical_token")
        if token and svc.consume_critical_grant(svc.CRITICAL_LICENSE_CHANGE, token):
            return
        svc.require_critical_step_up(svc.CRITICAL_LICENSE_CHANGE)

    @api.model
    def get_feature(self, feature_code):
        feature_id = self._get_feature_id_cached(feature_code)
        return (
            self._sudo_internal()["justech.feature"].browse(feature_id)
            if feature_id
            else self._sudo_internal()["justech.feature"]
        )

    @api.model
    @ormcache("feature_code")
    def _get_feature_id_cached(self, feature_code):
        feature = self._sudo_internal()["justech.feature"].search(
            [("code", "=", feature_code)], limit=1
        )
        return feature.id or 0

    @api.model
    def validate_license(self, key=None, feature_code=None, company=None):
        company = company or self.env.company
        result = {
            "valid": False,
            "reason": "invalid_key",
            "expires": False,
            "tier": False,
        }
        License = self.env["justech.license"]
        if not key:
            license_rec = self._get_active_license_for_company(company)
            if not license_rec:
                result["reason"] = "no_license"
                return result
        else:
            license_rec = License._find_by_license_key(key)
            if not license_rec:
                return result

        if license_rec.state == "revoked":
            result["reason"] = "revoked"
            return result
        if license_rec.state != "active":
            result["reason"] = "not_active"
            return result
        if license_rec.expires_at and license_rec.expires_at < date.today():
            result["reason"] = "expired"
            result["expires"] = license_rec.expires_at
            return result

        if feature_code:
            feature = self._get_feature_record(feature_code)
            if not feature:
                result["reason"] = "unknown_feature"
                return result
            if feature.license_required:
                granted = license_rec.feature_line_ids.filtered(
                    lambda line: line.feature_id.code == feature_code
                )
                if not granted:
                    result["reason"] = "feature_not_included"
                    result["tier"] = license_rec.tier
                    result["expires"] = license_rec.expires_at or False
                    return result

        result.update(
            {
                "valid": True,
                "reason": "ok",
                "expires": license_rec.expires_at or False,
                "tier": license_rec.tier,
            }
        )
        self._audit(
            "validate",
            license_id=license_rec.id,
            company_id=company.id,
            details={"key": bool(key), "feature_code": feature_code, "result": result},
        )
        return result

    @api.model
    def check_dependencies(self, feature_code, company=None):
        """Return commercial dependency status for a feature."""
        company = company or self.env.company
        feature = self._get_feature_record(feature_code)
        if not feature or not feature.module_id:
            return {"ok": True, "missing": []}

        missing = []
        visited = set()
        self._collect_missing_module_deps(
            feature.module_id, company, missing, visited
        )
        return {"ok": not missing, "missing": missing}

    @api.model
    def activate_feature(self, feature_code, company=None):
        self._require_activation_admin()
        company = company or self.env.company
        feature = self._get_feature_record(feature_code)
        if not feature:
            raise JustechLicenseError(
                _("Unknown feature '%(code)s'.") % {"code": feature_code}
            )
        if feature.always_on:
            return True

        deps = self.check_dependencies(feature_code, company=company)
        if not deps["ok"]:
            missing_codes = ", ".join(item["module_code"] for item in deps["missing"])
            raise JustechLicenseError(
                _("Cannot activate '%(code)s': missing dependencies: %(missing)s.")
                % {"code": feature_code, "missing": missing_codes}
            )

        if feature.license_required:
            license_rec = self._get_active_license_for_company(company)
            if not license_rec:
                raise JustechLicenseError(
                    _("No active license for company '%(company)s'.")
                    % {"company": company.name}
                )
            license_rec._check_max_users()
            if not self._feature_granted_to_company(feature, company):
                raise JustechLicenseError(
                    _("Feature '%(code)s' is not included in the active license.")
                    % {"code": feature_code}
                )

        self._set_feature_company_active(
            feature, company, active=True, reason="api_activate"
        )
        return True

    @api.model
    def deactivate_feature(self, feature_code, company=None):
        self._require_activation_admin()
        company = company or self.env.company
        feature = self._get_feature_record(feature_code)
        if not feature:
            raise JustechLicenseError(
                _("Unknown feature '%(code)s'.") % {"code": feature_code}
            )
        if feature.always_on:
            raise JustechLicenseError(
                _("Feature '%(code)s' is always-on and cannot be deactivated.")
                % {"code": feature_code}
            )
        self._set_feature_company_active(
            feature, company, active=False, reason="api_deactivate"
        )
        return True

    # ----------------------------------------------------------- registration
    @api.model
    def register_platform_seed(self):
        module = self._upsert_module(
            {
                "code": "justech_modules",
                "name": "Justech Modules",
                "version": "19.0.1.5.0",
                "category": "platform",
                "license_required": False,
                "tier_minimum": "STD",
                "state": "registered",
            }
        )
        self._upsert_feature(
            {
                "code": "platform_core",
                "name": "Platform Core",
                "module_id": module.id,
                "license_required": False,
                "always_on": True,
                "default_active": True,
            }
        )
        ir_module = self.env["ir.module.module"].search(
            [("name", "=", "justech_modules")], limit=1
        )
        if ir_module:
            module.ir_module_id = ir_module.id
        self.clear_license_cache()

    @api.model
    def register_from_manifest(self, module_name, register_data, manifest=None):
        """Register module catalog entry + features from __manifest__ justech_register."""
        manifest = manifest or {}
        always_enabled = register_data.get("always_enabled", True)
        module_code = (
            register_data.get("module_code")
            or register_data.get("code")
            or module_name
        )
        ir_module = self.env["ir.module.module"].search(
            [("name", "=", module_name)], limit=1
        )
        raw_category = (register_data.get("category") or "platform").strip().lower()
        allowed = {k for k, _v in self.env["justech.module"]._fields["category"].selection}
        category = raw_category if raw_category in allowed else "other" if "other" in allowed else "platform"
        module_vals = {
            "code": module_code,
            "name": register_data.get("module_name")
            or register_data.get("name")
            or module_name,
            "version": register_data.get("version") or manifest.get("version"),
            "description": register_data.get("description")
            or manifest.get("summary")
            or manifest.get("description"),
            "category": category,
            "country": register_data.get("country"),
            "localization": register_data.get("localization"),
            "required_module": register_data.get("required_module", False),
            "license_required": False
            if always_enabled
            else register_data.get("license_required", True),
            "tier_minimum": register_data.get("tier_minimum", "STD"),
            "state": "registered",
        }
        module = self._upsert_module(module_vals)
        if ir_module:
            module.ir_module_id = ir_module.id

        self._register_manifest_dependencies(module, register_data.get("dependencies", []))

        features_data = self._normalize_manifest_features(register_data)
        features = self.env["justech.feature"]
        for feat in features_data:
            feature = self._upsert_feature(
                {
                    "code": feat["code"],
                    "name": feat.get("name") or feat["code"],
                    "description": feat.get("description"),
                    "module_id": module.id,
                    "license_required": False
                    if always_enabled
                    else feat.get("license_required", True),
                    "always_on": feat.get("always_on", False),
                    "default_active": True
                    if always_enabled
                    else feat.get("default_active", False),
                }
            )
            features |= feature

        self._audit(
            "register",
            feature_id=features[:1].id if features else False,
            details={
                "module_name": module_name,
                "module_code": module_code,
                "register": register_data,
            },
        )
        self.clear_license_cache()
        return module, features

    @api.model
    def _normalize_manifest_features(self, register_data):
        features = register_data.get("features")
        if features:
            normalized = []
            for feat in features:
                if isinstance(feat, str):
                    normalized.append({"code": feat, "name": feat})
                elif isinstance(feat, dict) and feat.get("code"):
                    normalized.append(feat)
            if normalized:
                return normalized
        if register_data.get("feature_code"):
            return [
                {
                    "code": register_data["feature_code"],
                    "name": register_data.get("name") or register_data["feature_code"],
                    "description": register_data.get("description"),
                }
            ]
        code = register_data.get("module_code") or register_data.get("code")
        return [{"code": f"{code}_core", "name": register_data.get("module_name") or code}]

    @api.model
    def _register_manifest_dependencies(self, module, dependency_codes):
        Dependency = self.env["justech.module.dependency"]
        Module = self.env["justech.module"]
        for dep_code in dependency_codes:
            depends_on = Module.search([("code", "=", dep_code)], limit=1)
            if not depends_on:
                continue
            existing = Dependency.search(
                [
                    ("module_id", "=", module.id),
                    ("depends_on_module_id", "=", depends_on.id),
                ],
                limit=1,
            )
            if not existing:
                Dependency.create(
                    {
                        "module_id": module.id,
                        "depends_on_module_id": depends_on.id,
                        "dependency_type": "required",
                    }
                )

    # --------------------------------------------------------- activation UI
    @api.model
    def get_activation_catalog(self, company=None):
        """Return module/feature activation rows for admin wizard (API v1)."""
        self.env["justech.admin.access.service"].require_justech_settings_access()
        if not self.env.su:
            self.env["justech.admin.access.service"].require_session(
                self.env["justech.admin.access.service"].SCOPE_PLATFORM
            )
        company = company or self.env.company
        internal = self._sudo_internal()
        catalog = []
        for module in internal["justech.module"].search([], order="category, code"):
            deps = module.dependency_ids.filtered(
                lambda dep: dep.dependency_type == "required"
            )
            feature_rows = []
            module_active = True
            for feature in module.feature_ids:
                activation = internal["justech.feature.company"].search(
                    [
                        ("feature_id", "=", feature.id),
                        ("company_id", "=", company.id),
                    ],
                    limit=1,
                )
                active = self.is_active(feature.code, company=company)
                module_active = module_active and active
                feature_rows.append(
                    {
                        "feature_code": feature.code,
                        "feature_name": feature.name,
                        "description": feature.description,
                        "license_required": feature.license_required,
                        "always_on": feature.always_on,
                        "default_active": feature.default_active,
                        "is_active": active,
                        "activated_at": activation.activated_at,
                        "activated_by_name": activation.activated_by_id.name
                        if activation.activated_by_id
                        else False,
                    }
                )
            catalog.append(
                {
                    "module_code": module.code,
                    "module_name": module.name,
                    "description": module.description,
                    "category": module.category,
                    "country": module.country,
                    "localization": module.localization,
                    "state": module.state,
                    "required_module": module.required_module,
                    "license_required": module.license_required,
                    "dependencies": [
                        {
                            "module_code": dep.depends_on_module_id.code,
                            "module_name": dep.depends_on_module_id.name,
                            "dependency_type": dep.dependency_type,
                        }
                        for dep in deps
                    ],
                    "features": feature_rows,
                    "is_active": module_active if feature_rows else True,
                }
            )
        return catalog

    @api.model
    def get_license_wizard_catalog(self, license_rec=None):
        """Real Hellenia/Justech customizations for license wizard (strict whitelist)."""
        self.env["justech.admin.access.service"].require_justech_settings_access()
        internal = self._sudo_internal()
        Product = internal["justech.commercial.product"]
        Feature = internal["justech.feature"]
        product_cache = {p.code: p for p in Product.search([("active", "=", True)])}
        licensed_codes = set()
        if license_rec and license_rec.exists():
            licensed_feature_ids = set(
                license_rec.feature_line_ids.mapped("feature_id").ids
            )
            for code in self.LICENSE_WIZARD_CUSTOMIZATION_CODES:
                customization = self.get_customization_definition(code)
                if not customization:
                    continue
                primary = customization.get("primary_product_code") or ""
                if not primary:
                    continue
                product = product_cache.get(primary) or Product.search(
                    [("code", "=", primary)], limit=1
                )
                if not product:
                    continue
                product_feature_ids = set()
                for line in product.line_ids:
                    feature = Feature.search(
                        [("code", "=", line.feature_code)], limit=1
                    )
                    if feature:
                        product_feature_ids.add(feature.id)
                if product_feature_ids and product_feature_ids.issubset(
                    licensed_feature_ids
                ):
                    licensed_codes.add(primary)
        rows = []
        for code in self.LICENSE_WIZARD_CUSTOMIZATION_CODES:
            customization = self.get_customization_definition(code)
            if not customization:
                continue
            if not self._customization_is_visible(
                customization, product_cache, internal
            ):
                continue
            primary = customization.get("primary_product_code")
            rows.append(
                {
                    "customization_code": code,
                    "product_code": primary or "",
                    "product_name": customization["name"],
                    "description": customization.get("description") or "",
                    "sequence": customization.get("sequence", 10),
                    "selected": primary in licensed_codes if license_rec else True,
                }
            )
        return rows

    @api.model
    def get_commercial_catalog(self, company=None):
        """Return commercial product catalog for Control Center (API v1 extension)."""
        self.env["justech.admin.access.service"].require_justech_settings_access()
        if not self.env.su:
            svc = self.env["justech.admin.access.service"]
            if not svc.is_session_valid(svc.SCOPE_ADMIN) and not svc.is_session_valid(
                svc.SCOPE_PLATFORM
            ):
                svc.require_session(svc.SCOPE_ADMIN)
        company = company or self.env.company
        internal = self._sudo_internal()
        Product = internal["justech.commercial.product"]
        tier_labels = dict(Product._fields["license_tier"].selection)
        category_labels = dict(Product._fields["category"].selection)
        catalog = []
        for product in Product.search([("active", "=", True)], order="sequence, name"):
            feature_rows = []
            active_count = 0
            configured_count = 0
            for line in product.line_ids:
                feature = internal["justech.feature"].search(
                    [("code", "=", line.feature_code)], limit=1
                )
                if feature:
                    configured_count += 1
                    active = self.is_active(line.feature_code, company=company)
                    if active:
                        active_count += 1
                    always_on = feature.always_on
                else:
                    active = False
                    always_on = False
                feature_rows.append(
                    {
                        "commercial_name": line.commercial_name,
                        "description": line.description,
                        "feature_code": line.feature_code,
                        "icon": line.icon or "fa-circle",
                        "is_active": active,
                        "always_on": always_on,
                        "configured": bool(feature),
                    }
                )
            if feature_rows:
                if active_count == len(feature_rows):
                    status = "active"
                elif active_count > 0:
                    status = "partial"
                elif configured_count == 0:
                    status = "unavailable"
                else:
                    status = "inactive"
            else:
                status = "unavailable"
            dep_names = []
            for dep_product in Product.search([]):
                if dep_product.id == product.id:
                    continue
                if product.module_map_ids.filtered(
                    lambda m: m.technical_module_code
                    in dep_product.module_map_ids.mapped("technical_module_code")
                ):
                    dep_names.append(dep_product.name)
            catalog.append(
                {
                    "product_code": product.code,
                    "name": product.name,
                    "description": product.description,
                    "icon": product.icon or "fa-cube",
                    "category": product.category,
                    "category_label": category_labels.get(product.category, product.category),
                    "license_tier": product.license_tier,
                    "license_tier_label": tier_labels.get(
                        product.license_tier, product.license_tier
                    ),
                    "version": product.version_display or "—",
                    "status": status,
                    "is_active": status == "active",
                    "features": feature_rows,
                    "dependencies": dep_names,
                    "company_name": company.name,
                }
            )
        return catalog

    @api.model
    def commercial_name_for_feature(self, feature_code):
        """Resolve commercial display name for a technical feature code."""
        internal = self._sudo_internal()
        line = internal["justech.commercial.product.line"].search(
            [("feature_code", "=", feature_code)], limit=1
        )
        if line:
            return line.commercial_name
        feature = internal["justech.feature"].search(
            [("code", "=", feature_code)], limit=1
        )
        return feature.name if feature else feature_code

    # ------------------------------------------------------ client module control
    HIDDEN_PRODUCT_CODES = frozenset(
        {
            "comprobantes_fiscales",
            "ux_fiscal",
            "contabilidad_rd",
            "marketplace",
            "ia",
            "crm",
            "rrhh",
            "activos_fijos",
            "ventas",
            "compras",
        }
    )

    # License wizard — strict whitelist (Hellenia v1.0 real customizations only).
    LICENSE_WIZARD_CUSTOMIZATION_CODES = (
        "fiscal_rd",
        "reportes_documentos_corporativos",
        "ux_fiscal_contactos_facturas",
        "multicurrency_commercial",
        "global_audit",
        "control_justech_interno",
        "pos_fiscal_si_instalado",
    )

    # Explicit whitelist — only real Justech/Hellenia customizations (never Odoo native).
    REAL_JUSTECH_CUSTOMIZATIONS = (
        {
            "code": "fiscal_rd",
            "name": "Fiscal RD / NCF / DGII",
            "description": (
                "Motor fiscal dominicano: NCF serie B completa (B01–B04, B11–B17), secuencias, "
                "DGII 606/607/608/609/623, ITBIS, retenciones y validaciones fiscales RD."
            ),
            "primary_product_code": "contabilidad_rd",
            "technical_modules_any": (
                "justech_l10n_do_base",
                "justech_l10n_do_ncf",
                "justech_l10n_do_reports",
            ),
            "includes": [
                "NCF",
                "B01/B02/B03/B04/B11/B12/B13/B14/B15/B16/B17",
                "Secuencias fiscales",
                "DGII 606",
                "DGII 607",
                "DGII 608",
                "DGII 609",
                "DGII 623",
                "ITBIS",
                "Retenciones si aplica",
                "Validaciones fiscales RD",
            ],
            "commercial_features": [
                {"key": "b01", "label": "B01 Crédito Fiscal", "section": "comprobantes", "section_label": "COMPROBANTES", "section_sequence": 10, "sequence": 10, "description": "Emite comprobantes válidos para crédito fiscal.", "default_on": True},
                {"key": "b02", "label": "B02 Consumidor Final", "section": "comprobantes", "section_label": "COMPROBANTES", "section_sequence": 10, "sequence": 20, "description": "Comprobantes para consumidor final.", "default_on": True},
                {"key": "b03", "label": "B03 Nota de Débito", "section": "comprobantes", "section_label": "COMPROBANTES", "section_sequence": 10, "sequence": 30, "description": "Notas de débito fiscales.", "default_on": True},
                {"key": "b04", "label": "B04 Nota de Crédito", "section": "comprobantes", "section_label": "COMPROBANTES", "section_sequence": 10, "sequence": 40, "description": "Notas de crédito fiscales.", "default_on": True},
                {"key": "b11", "label": "B11 Comprobante Compras", "section": "comprobantes", "section_label": "COMPROBANTES", "section_sequence": 10, "sequence": 45, "description": "Compras a proveedores informales.", "default_on": True},
                {"key": "b12", "label": "B12 Registro Único Ingresos", "section": "comprobantes", "section_label": "COMPROBANTES", "section_sequence": 10, "sequence": 46, "description": "Ingresos no operacionales.", "default_on": True},
                {"key": "b13", "label": "B13 Gastos Menores", "section": "comprobantes", "section_label": "COMPROBANTES", "section_sequence": 10, "sequence": 47, "description": "Gastos menores sin factura formal.", "default_on": True},
                {"key": "b14", "label": "B14 Regímenes Especiales", "section": "comprobantes", "section_label": "COMPROBANTES", "section_sequence": 10, "sequence": 48, "description": "Zonas francas y regímenes especiales.", "default_on": True},
                {"key": "b15", "label": "B15 Gubernamental", "section": "comprobantes", "section_label": "COMPROBANTES", "section_sequence": 10, "sequence": 49, "description": "Ventas a entidades gubernamentales.", "default_on": True},
                {"key": "b16", "label": "B16 Exportaciones", "section": "comprobantes", "section_label": "COMPROBANTES", "section_sequence": 10, "sequence": 50, "description": "Ventas al exterior.", "default_on": True},
                {"key": "b17", "label": "B17 Pagos al Exterior", "section": "comprobantes", "section_label": "COMPROBANTES", "section_sequence": 10, "sequence": 51, "description": "Pagos a no residentes (606/609).", "default_on": True},
                {"key": "ncf", "label": "NCF", "section": "comprobantes", "section_label": "COMPROBANTES", "section_sequence": 10, "sequence": 60, "description": "Numeración de comprobantes fiscales.", "default_on": True},
                {"key": "secuencias", "label": "Secuencias fiscales", "section": "comprobantes", "section_label": "COMPROBANTES", "section_sequence": 10, "sequence": 70, "description": "Secuencias autorizadas por DGII.", "default_on": True},
                {"key": "dgii_606", "label": "606", "section": "dgii", "section_label": "DGII", "section_sequence": 20, "sequence": 10, "description": "Reporte de compras DGII 606.", "default_on": True},
                {"key": "dgii_607", "label": "607", "section": "dgii", "section_label": "DGII", "section_sequence": 20, "sequence": 20, "description": "Reporte de ventas DGII 607.", "default_on": True},
                {"key": "dgii_608", "label": "608", "section": "dgii", "section_label": "DGII", "section_sequence": 20, "sequence": 25, "description": "NCF anulados.", "default_on": True},
                {"key": "dgii_609", "label": "609", "section": "dgii", "section_label": "DGII", "section_sequence": 20, "sequence": 28, "description": "Pagos al exterior.", "default_on": True},
                {"key": "dgii_623", "label": "623", "section": "dgii", "section_label": "DGII", "section_sequence": 20, "sequence": 30, "description": "Reporte DGII 623.", "default_on": True},
                {"key": "itbis", "label": "ITBIS", "section": "impuestos", "section_label": "IMPUESTOS", "section_sequence": 30, "sequence": 10, "description": "Cálculo y declaración de ITBIS.", "default_on": True},
                {"key": "retenciones", "label": "Retenciones", "section": "impuestos", "section_label": "IMPUESTOS", "section_sequence": 30, "sequence": 20, "description": "Retenciones fiscales aplicables.", "default_on": True},
                {"key": "validaciones_rd", "label": "Validaciones fiscales RD", "section": "validaciones", "section_label": "VALIDACIONES", "section_sequence": 40, "sequence": 10, "description": "Validaciones normativas dominicanas.", "default_on": True},
            ],
            "sequence": 10,
            "allow_license_actions": True,
            "visible_to_client": True,
        },
        {
            "code": "ux_fiscal_contactos_facturas",
            "name": "UX Fiscal / Contactos y Facturas",
            "description": (
                "Mejoras fiscales en contactos y facturas: tipo de comprobante, "
                "validación RNC/Cédula y campos fiscales."
            ),
            "primary_product_code": "ux_fiscal",
            "technical_modules_all": ("hellenia_ux",),
            "includes": [
                "Tipo de comprobante en contacto",
                "Validación RNC/Cédula duplicada",
                "Pestaña fiscal",
                "Campos fiscales en factura/contacto",
                "Mejoras visuales fiscales",
            ],
            "commercial_features": [
                {"key": "tipo_comprobante", "label": "Tipo de comprobante en contacto", "section": "contactos", "section_label": "CONTACTOS", "section_sequence": 10, "sequence": 10, "description": "Selección de tipo de comprobante en el contacto.", "default_on": True},
                {"key": "rnc_duplicado", "label": "Validación RNC/Cédula duplicada", "section": "contactos", "section_label": "CONTACTOS", "section_sequence": 10, "sequence": 20, "description": "Evita RNC o cédula duplicados.", "default_on": True},
                {"key": "pestana_fiscal", "label": "Pestaña fiscal", "section": "facturas", "section_label": "FACTURAS", "section_sequence": 20, "sequence": 10, "description": "Pestaña fiscal en formularios de factura.", "default_on": True},
                {"key": "campos_fiscales", "label": "Campos fiscales en factura", "section": "facturas", "section_label": "FACTURAS", "section_sequence": 20, "sequence": 20, "description": "Campos fiscales en factura y contacto.", "default_on": True},
                {"key": "mejoras_visuales", "label": "Mejoras visuales fiscales", "section": "facturas", "section_label": "FACTURAS", "section_sequence": 20, "sequence": 30, "description": "Mejoras de usabilidad en pantallas fiscales.", "default_on": True},
            ],
            "sequence": 20,
            "allow_license_actions": True,
            "visible_to_client": True,
        },
        {
            "code": "reportes_documentos_corporativos",
            "name": "Reportes y Documentos Corporativos",
            "description": (
                "PDF corporativos para cotizaciones, facturas, órdenes de compra y conduces."
            ),
            "primary_product_code": "reportes_corporativos",
            "technical_modules_all": ("justech_report_design",),
            "includes": [
                "PDF cotización",
                "PDF factura",
                "PDF orden de compra",
                "Conduces",
                "Diseño corporativo",
                "Branding Hellenia",
            ],
            "commercial_features": [
                {"key": "pdf_cotizacion", "label": "PDF Cotización", "section": "documentos", "section_label": "DOCUMENTOS", "section_sequence": 10, "sequence": 10, "description": "Cotización con diseño corporativo.", "default_on": True},
                {"key": "pdf_factura", "label": "PDF Factura", "section": "documentos", "section_label": "DOCUMENTOS", "section_sequence": 10, "sequence": 20, "description": "Factura PDF con branding Hellenia.", "default_on": True},
                {"key": "pdf_oc", "label": "PDF Orden de Compra", "section": "documentos", "section_label": "DOCUMENTOS", "section_sequence": 10, "sequence": 30, "description": "Orden de compra en formato corporativo.", "default_on": True},
                {"key": "pdf_conduce", "label": "PDF Conduce", "section": "documentos", "section_label": "DOCUMENTOS", "section_sequence": 10, "sequence": 40, "description": "Conduce / guía de entrega corporativa.", "default_on": True},
                {"key": "branding", "label": "Branding Hellenia", "section": "diseno", "section_label": "DISEÑO", "section_sequence": 20, "sequence": 10, "description": "Identidad visual Hellenia en documentos.", "default_on": True},
                {"key": "diseno", "label": "Diseño corporativo", "section": "diseno", "section_label": "DISEÑO", "section_sequence": 20, "sequence": 20, "description": "Plantillas y layout corporativo.", "default_on": True},
            ],
            "sequence": 30,
            "allow_license_actions": True,
            "visible_to_client": True,
        },
        {
            "code": "pos_fiscal_si_instalado",
            "name": "POS Fiscal",
            "description": "Punto de venta fiscal integrado con NCF, tickets y caja.",
            "primary_product_code": "punto_de_venta",
            "technical_modules_all": ("hellenia_pos",),
            "requires_product_configured": True,
            "includes": [
                "POS fiscal",
                "Ticket",
                "Caja",
                "Cliente con RNC",
                "Factura fiscal desde POS",
            ],
            "commercial_features": [
                {"key": "pos_fiscal", "label": "POS fiscal", "section": "pos", "section_label": "PUNTO DE VENTA", "section_sequence": 10, "sequence": 10, "description": "Terminal de venta fiscal integrado.", "default_on": True},
                {"key": "ticket", "label": "Ticket", "section": "pos", "section_label": "PUNTO DE VENTA", "section_sequence": 10, "sequence": 20, "description": "Impresión de ticket fiscal.", "default_on": True},
                {"key": "caja", "label": "Caja", "section": "pos", "section_label": "PUNTO DE VENTA", "section_sequence": 10, "sequence": 30, "description": "Control de caja y sesiones POS.", "default_on": True},
                {"key": "cliente_rnc", "label": "Cliente con RNC", "section": "pos", "section_label": "PUNTO DE VENTA", "section_sequence": 10, "sequence": 40, "description": "Captura de RNC del cliente en POS.", "default_on": True},
                {"key": "factura_pos", "label": "Factura fiscal desde POS", "section": "pos", "section_label": "PUNTO DE VENTA", "section_sequence": 10, "sequence": 50, "description": "Emisión de factura fiscal desde caja.", "default_on": True},
            ],
            "sequence": 40,
            "allow_license_actions": True,
            "visible_to_client": True,
        },
        {
            "code": "multicurrency_commercial",
            "name": "Motor Comercial Multimoneda",
            "description": (
                "Política comercial multimoneda, tasas, precios por moneda "
                "y administración corporativa de divisas."
            ),
            "primary_product_code": "multicurrency_commercial",
            "technical_modules_all": ("justech_multicurrency",),
            "includes": [
                "Política multimoneda por empresa",
                "Precios en moneda comercial",
                "Dashboard de tasas",
            ],
            "commercial_features": [
                {
                    "key": "multicurrency",
                    "label": "Motor Multimoneda",
                    "section": "multimoneda",
                    "section_label": "MULTIMONEDA",
                    "section_sequence": 10,
                    "sequence": 10,
                    "description": "Capa comercial multimoneda Justech.",
                    "default_on": True,
                },
            ],
            "sequence": 35,
            "allow_license_actions": True,
            "visible_to_client": True,
        },
        {
            "code": "global_audit",
            "name": "Auditoría",
            "description": (
                "Histórico de cambios, trazabilidad empresarial y exportación de auditoría."
            ),
            "primary_product_code": "global_audit",
            "technical_modules_all": ("justech_global_audit_log",),
            "includes": [
                "Histórico de cambios",
                "Trazabilidad por usuario",
                "Exportación de auditoría",
            ],
            "commercial_features": [
                {
                    "key": "global_audit",
                    "label": "Auditoría Global",
                    "section": "auditoria",
                    "section_label": "AUDITORÍA",
                    "section_sequence": 10,
                    "sequence": 10,
                    "description": "Registro global de cambios empresariales.",
                    "default_on": True,
                },
            ],
            "sequence": 45,
            "allow_license_actions": True,
            "visible_to_client": True,
        },
        {
            "code": "control_justech_interno",
            "name": "Centro de Administración / Módulos del Cliente",
            "description": (
                "Administración interna Justech: módulos del cliente, licencias, "
                "clave administrativa, auditoría y governance."
            ),
            "primary_product_code": None,
            "technical_modules_all": ("hellenia_governance", "justech_modules"),
            "internal_only": True,
            "includes": [
                "Módulos del Cliente",
                "Licencias",
                "Clave Administrativa Justech",
                "Auditoría",
                "Governance/Admin interno",
            ],
            "commercial_features": [
                {"key": "modulos_cliente", "label": "Módulos del Cliente", "section": "plataforma", "section_label": "PLATAFORMA", "section_sequence": 10, "sequence": 10, "description": "Consola de personalizaciones del cliente.", "default_on": True},
                {"key": "licencias", "label": "Licencias", "section": "plataforma", "section_label": "PLATAFORMA", "section_sequence": 10, "sequence": 20, "description": "Gestión de licencias comerciales.", "default_on": True},
                {"key": "clave_admin", "label": "Clave Administrativa Justech", "section": "plataforma", "section_label": "PLATAFORMA", "section_sequence": 10, "sequence": 30, "description": "Clave para acciones críticas.", "default_on": True},
                {"key": "auditoria", "label": "Auditoría", "section": "plataforma", "section_label": "PLATAFORMA", "section_sequence": 10, "sequence": 40, "description": "Historial de cambios de plataforma.", "default_on": True},
                {"key": "governance", "label": "Governance/Admin interno", "section": "plataforma", "section_label": "PLATAFORMA", "section_sequence": 10, "sequence": 50, "description": "Gobierno y permisos internos Justech.", "default_on": True},
            ],
            "sequence": 50,
            "allow_license_actions": False,
            "visible_to_client": False,
        },
    )

    JUSTECH_REAL_CUSTOMIZATIONS = REAL_JUSTECH_CUSTOMIZATIONS

    COMMERCIAL_ICON_MAP = {
        "fiscal": "🧾",
        "sales": "💰",
        "purchase": "🛒",
        "inventory": "📦",
        "pos": "🛒",
        "crm": "👥",
        "reports": "📊",
        "assets": "🏢",
        "hr": "👥",
        "platform": "⚙️",
        "integration": "🔗",
        "ai": "🤖",
    }

    @api.model
    def _tier_commercial_label(self, tier_code):
        labels = {
            "TRIAL": _("Trial"),
            "STD": _("Standard"),
            "PRO": _("Professional"),
            "ENT": _("Enterprise"),
        }
        return labels.get(tier_code, tier_code or "—")

    @api.model
    def get_commercial_clients(self):
        """Active commercial clients derived from valid licenses."""
        self.env["justech.admin.access.service"].require_justech_settings_access()
        internal = self._sudo_internal()
        License = internal["justech.license"]
        today = date.today()
        licenses = License.search([("state", "=", "active")])
        clients = []
        for lic in licenses:
            if lic.expires_at and lic.expires_at < today:
                continue
            companies = lic.company_line_ids.mapped("company_id")
            primary = companies[:1] or self.env.company
            clients.append(
                {
                    "license_id": lic.id,
                    "client_name": lic.name,
                    "plan_label": self._tier_commercial_label(lic.tier),
                    "tier_code": lic.tier,
                    "primary_company_id": primary.id,
                    "company_ids": companies.ids,
                    "company_count": len(companies),
                    "expires_at": lic.expires_at,
                    "max_companies": lic.max_companies,
                }
            )
        if not clients:
            company = self.env.company
            lic = self._get_active_license_for_company(company)
            clients.append(
                {
                    "license_id": lic.id if lic else False,
                    "client_name": lic.name if lic else company.name,
                    "plan_label": self._tier_commercial_label(lic.tier) if lic else "—",
                    "tier_code": lic.tier if lic else False,
                    "primary_company_id": company.id,
                    "company_ids": [company.id],
                    "company_count": 1,
                    "expires_at": lic.expires_at if lic else False,
                    "max_companies": lic.max_companies if lic else 0,
                }
            )
        return clients

    @api.model
    def get_client_dashboard(self, license_id=None, company=None):
        clients = self.get_commercial_clients()
        selected = next(
            (c for c in clients if c["license_id"] == license_id),
            clients[0] if clients else {},
        )
        if not selected:
            return {}
        company = (
            self.env["res.company"].browse(selected["primary_company_id"])
            if selected.get("primary_company_id")
            else (company or self.env.company)
        )
        rows = self.get_client_module_rows(
            company=company, license_id=license_id, view_only=True
        )
        last_modified = False
        for row in rows:
            mod = row.get("last_modified_at")
            if mod and (not last_modified or mod > last_modified):
                last_modified = mod
        return {
            **selected,
            "total_count": len(rows),
            "active_count": len([r for r in rows if r.get("is_active")]),
            "pending_count": len(
                [
                    r
                    for r in rows
                    if not r.get("is_paid") and r.get("status") != "coming_soon"
                ]
            ),
            "last_modified_at": last_modified,
        }

    @api.model
    def _product_enabled_companies(self, product, license_rec):
        if not license_rec:
            return []
        names = []
        for comp in license_rec.company_line_ids.mapped("company_id"):
            if self._product_is_active_for_company(product, comp):
                names.append(comp.name)
        return names

    @api.model
    def _product_companies_checklist(self, product, license_rec):
        if not license_rec:
            return []
        rows = []
        for comp in license_rec.company_line_ids.mapped("company_id"):
            rows.append(
                {
                    "company_id": comp.id,
                    "company_name": comp.name,
                    "enabled": self._product_is_active_for_company(product, comp),
                }
            )
        return rows

    @api.model
    def _client_name_for_company(self, company):
        lic = self._get_active_license_for_company(company)
        return lic.name if lic else company.name

    @api.model
    def _client_module_status(self, product, company, state, configured, is_active):
        license_rec = self._get_active_license_for_company(company)
        if license_rec and license_rec.expires_at:
            if license_rec.expires_at < date.today():
                return "expired", _("Expirado")
        if not configured:
            return "coming_soon", _("Disponible")
        if state.is_blocked:
            return "blocked", _("Bloqueado")
        if not state.is_paid:
            return "not_paid", _("Pendiente")
        if is_active:
            return "paid_active", _("Activo")
        return "paid_inactive", _("Disponible")

    @api.model
    def _product_is_active_for_company(self, product, company):
        internal = self._sudo_internal()
        lines = product.line_ids
        if not lines:
            return False
        configured = [
            ln
            for ln in lines
            if internal["justech.feature"].search([("code", "=", ln.feature_code)], limit=1)
        ]
        if not configured:
            return False
        return all(self.is_active(ln.feature_code, company=company) for ln in configured)

    @api.model
    def _product_activation_meta(self, product, company):
        internal = self._sudo_internal()
        activated_at = False
        activated_by = False
        for ln in product.line_ids:
            feat = internal["justech.feature"].search(
                [("code", "=", ln.feature_code)], limit=1
            )
            if not feat:
                continue
            act = internal["justech.feature.company"].search(
                [("feature_id", "=", feat.id), ("company_id", "=", company.id)],
                limit=1,
            )
            if act and act.activated_at:
                if not activated_at or act.activated_at > activated_at:
                    activated_at = act.activated_at
                    activated_by = act.activated_by_id.name if act.activated_by_id else False
        state = internal["justech.client.module.state"].search(
            [("product_id", "=", product.id), ("company_id", "=", company.id)],
            limit=1,
        )
        if state and state.activated_at and (not activated_at or state.activated_at > activated_at):
            activated_at = state.activated_at
            activated_by = state.activated_by_id.name if state.activated_by_id else activated_by
        return activated_at, activated_by

    @api.model
    def _product_last_change_meta(self, product, company):
        Audit = self.env["justech.client.module.audit"].sudo()
        audit = Audit.search(
            [
                ("product_code", "=", product.code),
                ("company_id", "=", company.id),
            ],
            order="create_date desc",
            limit=1,
        )
        if audit:
            user_name = audit.user_id.name if audit.user_id else "—"
            return audit.create_date, user_name
        state = self.env["justech.client.module.state"].sudo().search(
            [("product_id", "=", product.id), ("company_id", "=", company.id)],
            limit=1,
        )
        if state:
            return state.write_date, "—"
        return False, "—"

    @api.model
    def _origin_label(self, origin_code):
        labels = {
            "justech": _("Justech"),
            "marketplace": _("Marketplace"),
            "partner": _("Partner"),
            "client": _("Cliente"),
        }
        return labels.get(origin_code, origin_code or "—")

    @api.model
    def _commercial_icon_for_category(self, category, name):
        emoji = self.COMMERCIAL_ICON_MAP.get(category, "📌")
        return f"{emoji} {name}"

    @api.model
    def _commercial_icon(self, product):
        return self._commercial_icon_for_category(product.category, product.name)

    @api.model
    def _format_client_datetime(self, dt):
        if not dt:
            return "—"
        local_dt = fields.Datetime.context_timestamp(self, dt)
        return local_dt.strftime("%d/%m/%Y %I:%M %p")

    @api.model
    def _odoo_module_installed(self, module_name):
        return bool(
            self.env["ir.module.module"]
            .sudo()
            .search([("name", "=", module_name), ("state", "=", "installed")], limit=1)
        )

    @api.model
    def _product_configured(self, product, internal):
        if not product:
            return False
        return any(
            internal["justech.feature"].search(
                [("code", "=", ln.feature_code)], limit=1
            )
            for ln in product.line_ids
        )

    @api.model
    def _customization_is_visible(self, customization, product_cache, internal):
        if customization.get("internal_only") and not self.env.user.has_group(
            "justech_modules.group_justech_internal_admin"
        ):
            return False
        mods_all = customization.get("technical_modules_all") or ()
        if mods_all and not all(self._odoo_module_installed(m) for m in mods_all):
            return False
        mods_any = customization.get("technical_modules_any") or ()
        if mods_any and not any(self._odoo_module_installed(m) for m in mods_any):
            return False
        if customization.get("requires_product_configured"):
            product = product_cache.get(customization.get("primary_product_code"))
            if not product or not self._product_configured(product, internal):
                return False
        return bool(mods_all or mods_any)

    @api.model
    def _customization_technical_status(self, customization):
        labels = []
        for mod in (
            customization.get("technical_modules_all")
            or customization.get("technical_modules_any")
            or ()
        ):
            if self._odoo_module_installed(mod):
                labels.append(f"✓ {mod}")
            else:
                labels.append(f"✗ {mod}")
        return labels

    @api.model
    def get_customization_definition(self, customization_code):
        for customization in self.REAL_JUSTECH_CUSTOMIZATIONS:
            if customization["code"] == customization_code:
                return customization
        return None

    @api.model
    def get_commercial_feature_rows(self, customization_code, company=None):
        """Return ON/OFF feature rows for admin panel (commercial control only)."""
        company = company or self.env.company
        definition = self.get_customization_definition(customization_code)
        if not definition:
            return []
        Flag = self.env["justech.client.module.feature.flag"].sudo()
        rows = []
        for feature in definition.get("commercial_features") or []:
            flag = Flag.search(
                [
                    ("customization_code", "=", customization_code),
                    ("feature_key", "=", feature["key"]),
                    ("company_id", "=", company.id),
                ],
                limit=1,
            )
            default_on = feature.get("default_on", True)
            rows.append(
                {
                    "feature_key": feature["key"],
                    "label": feature["label"],
                    "description": feature.get("description") or "",
                    "section": feature.get("section") or "general",
                    "section_label": feature.get("section_label") or _("GENERAL"),
                    "section_sequence": feature.get("section_sequence", 99),
                    "sequence": feature.get("sequence", 99),
                    "is_active": flag.is_active if flag else default_on,
                    "initial_active": flag.is_active if flag else default_on,
                    "control_type": feature.get("control_type", "commercial"),
                }
            )
        return rows

    @api.model
    def get_commercial_feature_sections(self, customization_code, company=None):
        """Grouped feature sections for dashboard display."""
        rows = self.get_commercial_feature_rows(customization_code, company=company)
        sections = {}
        for row in rows:
            key = row["section_label"]
            if key not in sections:
                sections[key] = {
                    "section_label": key,
                    "section_sequence": row["section_sequence"],
                    "features": [],
                }
            sections[key]["features"].append(row)
        return sorted(sections.values(), key=lambda s: s["section_sequence"])

    @api.model
    def _commercial_feature_audit(
        self,
        customization_code,
        feature_key,
        feature_label,
        company,
        state_before,
        state_after,
        result="success",
        reason=None,
    ):
        definition = self.get_customization_definition(customization_code)
        product_code = (definition or {}).get("primary_product_code") or customization_code
        commercial_name = (definition or {}).get("name") or customization_code
        ip = self.env["justech.admin.access.service"]._get_request_ip()
        self.env["justech.client.module.audit"].sudo().create(
            {
                "user_id": self.env.uid,
                "company_id": company.id,
                "client_name": self._client_name_for_company(company),
                "ip_address": ip,
                "action": "feature_toggle",
                "origin": "justech",
                "product_code": product_code,
                "commercial_name": commercial_name,
                "state_before": state_before,
                "state_after": state_after,
                "result": result,
                "reason": reason,
                "details": {
                    "customization_code": customization_code,
                    "feature_key": feature_key,
                    "feature_label": feature_label,
                    "control_type": "commercial",
                },
            }
        )

    @api.model
    def set_commercial_feature(self, customization_code, feature_key, company, is_active):
        """Persist a commercial feature toggle (does not change fiscal runtime)."""
        self._require_activation_admin()
        self = self.with_context(justech_skip_critical_step_up=True)
        company = company or self.env.company
        definition = self.get_customization_definition(customization_code)
        if not definition:
            raise JustechLicenseError(
                _("Unknown customization '%(code)s'.") % {"code": customization_code}
            )
        feature_def = next(
            (
                feature
                for feature in definition.get("commercial_features") or []
                if feature["key"] == feature_key
            ),
            None,
        )
        if not feature_def:
            raise JustechLicenseError(
                _("Unknown feature '%(key)s' for '%(code)s'.")
                % {"key": feature_key, "code": customization_code}
            )
        Flag = self.env["justech.client.module.feature.flag"].sudo()
        flag = Flag.search(
            [
                ("customization_code", "=", customization_code),
                ("feature_key", "=", feature_key),
                ("company_id", "=", company.id),
            ],
            limit=1,
        )
        default_on = feature_def.get("default_on", True)
        before_active = flag.is_active if flag else default_on
        before_label = "ON" if before_active else "OFF"
        after_label = "ON" if is_active else "OFF"
        if flag:
            flag.write({"is_active": is_active, "feature_label": feature_def["label"]})
        else:
            Flag.create(
                {
                    "customization_code": customization_code,
                    "feature_key": feature_key,
                    "feature_label": feature_def["label"],
                    "company_id": company.id,
                    "is_active": is_active,
                    "control_type": "commercial",
                }
            )
        self._commercial_feature_audit(
            customization_code,
            feature_key,
            feature_def["label"],
            company,
            before_label,
            after_label,
        )
        return True

    @api.model
    def apply_commercial_feature_changes(self, customization_code, company, changes):
        for change in changes or []:
            self.set_commercial_feature(
                customization_code,
                change["key"],
                company,
                bool(change.get("active")),
            )

    @api.model
    def get_visible_justech_customizations_report(self, company=None, license_id=None):
        """Summary for validation: visible customizations and hidden native/future modules."""
        rows = self.get_client_module_rows(
            company=company, license_id=license_id, view_only=True
        )
        visible = [
            {
                "code": r["main_module_code"],
                "name": r["name"],
                "product_code": r.get("product_code"),
            }
            for r in rows
        ]
        hidden_native = []
        forbidden = [
            "CRM",
            "IA",
            "RRHH",
            "Marketplace",
            "Manufactura",
            "Nómina",
            "Activos Fijos",
            "Ventas (Odoo nativo)",
            "Compras (Odoo nativo)",
            "Inventario (Odoo nativo)",
        ]
        return {
            "visible_count": len(visible),
            "visible": visible,
            "hidden_forbidden_labels": forbidden,
            "max_expected": 5,
        }

    @api.model
    def _product_row_data(self, product, company, license_rec, client_name, tier_label):
        internal = self._sudo_internal()
        State = internal["justech.client.module.state"]
        configured = any(
            internal["justech.feature"].search(
                [("code", "=", ln.feature_code)], limit=1
            )
            for ln in product.line_ids
        )
        state = State.get_or_create(product, company)
        is_active = self._product_is_active_for_company(product, company)
        status, status_label = self._client_module_status(
            product, company, state, configured, is_active
        )
        activated_at, activated_by = self._product_activation_meta(product, company)
        last_modified_at, last_modified_by = self._product_last_change_meta(
            product, company
        )
        enabled_companies = self._product_enabled_companies(product, license_rec)
        if license_rec:
            license_label = tier_label
        elif is_active:
            license_label = _("Licencia pendiente de configurar")
        else:
            license_label = _("Licencia pendiente de configurar")
        return {
            "product_code": product.code,
            "is_paid": state.is_paid,
            "is_active": is_active,
            "is_blocked": state.is_blocked,
            "client_name": client_name,
            "company_name": company.name,
            "plan_label": tier_label,
            "license_label": license_label,
            "companies_enabled_text": ", ".join(enabled_companies) or "—",
            "activated_at": activated_at,
            "activated_by_name": activated_by or "—",
            "last_modified_at": last_modified_at,
            "last_modified_by_name": last_modified_by or "—",
            "last_modified_display": self._format_client_datetime(last_modified_at),
            "origin": state.origin or "justech",
            "origin_label": self._origin_label(state.origin or "justech"),
            "status": status,
            "status_label": status_label,
            "configured": configured,
        }

    @api.model
    def _platform_customization_row(
        self, customization, company, license_rec, client_name, tier_label
    ):
        tech = self._customization_technical_status(customization)
        return {
            "product_code": customization["code"],
            "is_paid": False,
            "is_active": True,
            "is_blocked": False,
            "client_name": client_name,
            "company_name": company.name,
            "plan_label": tier_label,
            "license_label": "Plataforma interna",
            "companies_enabled_text": "—",
            "activated_at": False,
            "activated_by_name": "—",
            "last_modified_at": False,
            "last_modified_by_name": "—",
            "last_modified_display": "—",
            "origin": "justech",
            "origin_label": self._origin_label("justech"),
            "status": "paid_active",
            "status_label": _("Activo"),
            "configured": True,
            "technical_status_text": ", ".join(tech),
            "allow_license_actions": False,
        }

    @api.model
    def get_client_module_rows(self, company=None, license_id=None, view_only=False):
        """Justech real customizations only (installed technical modules)."""
        self.env["justech.admin.access.service"].require_justech_settings_access()
        if not view_only and not self.env.su:
            svc = self.env["justech.admin.access.service"]
            if not svc.is_session_valid(svc.SCOPE_ADMIN):
                svc.require_session(svc.SCOPE_ADMIN)
        internal = self._sudo_internal()
        License = internal["justech.license"]
        license_rec = License.browse(license_id) if license_id else False
        if license_rec and license_rec.exists():
            company = license_rec.company_line_ids[:1].company_id or company
        company = company or self.env.company
        if not license_rec or not license_rec.exists():
            license_rec = self._get_active_license_for_company(company)
        tier_label = self._tier_commercial_label(license_rec.tier) if license_rec else "—"
        client_name = license_rec.name if license_rec else company.name
        Product = internal["justech.commercial.product"]
        product_cache = {
            p.code: p for p in Product.search([("active", "=", True)])
        }
        rows = []
        for customization in sorted(
            self.REAL_JUSTECH_CUSTOMIZATIONS, key=lambda c: c.get("sequence", 99)
        ):
            if not self._customization_is_visible(
                customization, product_cache, internal
            ):
                continue
            primary_code = customization.get("primary_product_code")
            product = product_cache.get(primary_code) if primary_code else False
            if product:
                base = self._product_row_data(
                    product, company, license_rec, client_name, tier_label
                )
            else:
                base = self._platform_customization_row(
                    customization, company, license_rec, client_name, tier_label
                )
            tech_status = self._customization_technical_status(customization)
            rows.append(
                {
                    **base,
                    "main_module_code": customization["code"],
                    "name": customization["name"],
                    "display_name": customization["name"],
                    "description": customization["description"],
                    "includes": customization["includes"],
                    "includes_summary": ", ".join(customization["includes"]),
                    "section": "available",
                    "is_development": False,
                    "product_code": primary_code or customization["code"],
                    "technical_status_text": ", ".join(tech_status),
                    "allow_license_actions": customization.get(
                        "allow_license_actions", True
                    ),
                }
            )
        return rows

    @api.model
    def _client_module_audit(
        self,
        action,
        product,
        company,
        state_before,
        state_after,
        result="success",
        reason=None,
        details=None,
    ):
        ip = self.env["justech.admin.access.service"]._get_request_ip()
        state = self.env["justech.client.module.state"].sudo().search(
            [("product_id", "=", product.id), ("company_id", "=", company.id)],
            limit=1,
        )
        self.env["justech.client.module.audit"].sudo().create(
            {
                "user_id": self.env.uid,
                "company_id": company.id,
                "client_name": self._client_name_for_company(company),
                "ip_address": ip,
                "action": action,
                "origin": state.origin if state else "justech",
                "product_code": product.code,
                "commercial_name": product.name,
                "state_before": state_before,
                "state_after": state_after,
                "result": result,
                "reason": reason,
                "details": details or {},
            }
        )

    @api.model
    def execute_client_module_action(
        self, action, product_code, company=None, target_company=None, reason=None
    ):
        self._require_activation_admin()
        self = self.with_context(justech_skip_critical_step_up=True)
        company = company or self.env.company
        internal = self._sudo_internal()
        product = internal["justech.commercial.product"].search(
            [("code", "=", product_code), ("active", "=", True)], limit=1
        )
        if not product:
            raise JustechLicenseError(
                _("Unknown commercial module '%(code)s'.") % {"code": product_code}
            )
        state = internal["justech.client.module.state"].get_or_create(product, company)
        status_before, _status_label = self._client_module_status(
            product,
            company,
            state,
            bool(product.line_ids),
            self._product_is_active_for_company(product, company),
        )

        if action == "mark_paid":
            state.sudo().write({"is_paid": True})
        elif action == "mark_unpaid":
            state.sudo().write({"is_paid": False})
        elif action == "block":
            state.sudo().write({"is_blocked": True})
        elif action == "unblock":
            state.sudo().write({"is_blocked": False})
        elif action == "activate":
            license_rec = self._get_active_license_for_company(company)
            if not license_rec:
                self._client_module_audit(
                    action,
                    product,
                    company,
                    status_before,
                    status_before,
                    result="fail",
                    reason="no_active_license",
                )
                raise JustechLicenseError(
                    _(
                        "Esta empresa no tiene una licencia activa. "
                        "Cree o active una licencia desde Configuración → Justech → Licencias."
                    )
                )
            if not state.is_paid:
                self._client_module_audit(
                    action,
                    product,
                    company,
                    status_before,
                    status_before,
                    result="fail",
                    reason="not_paid",
                )
                raise JustechLicenseError(
                    _(
                        "Este módulo no está incluido en la licencia contratada."
                    )
                )
            if state.is_blocked:
                raise JustechLicenseError(_("Este módulo está bloqueado."))
            for ln in product.line_ids:
                feat = internal["justech.feature"].search(
                    [("code", "=", ln.feature_code)], limit=1
                )
                if feat:
                    self.activate_feature(ln.feature_code, company=company)
            state.sudo().write(
                {
                    "activated_at": fields.Datetime.now(),
                    "activated_by_id": self.env.uid,
                }
            )
        elif action == "deactivate":
            for ln in product.line_ids:
                feat = internal["justech.feature"].search(
                    [("code", "=", ln.feature_code)], limit=1
                )
                if feat and not feat.always_on:
                    self.deactivate_feature(ln.feature_code, company=company)
        elif action == "add_company":
            target = target_company or company
            if not target:
                raise JustechLicenseError(_("Seleccione la empresa a habilitar."))
            license_rec = self._get_active_license_for_company(company)
            if not license_rec:
                self._client_module_audit(
                    action,
                    product,
                    target or company,
                    status_before,
                    status_before,
                    result="fail",
                    reason="no_active_license",
                )
                raise JustechLicenseError(
                    _(
                        "Esta empresa no tiene una licencia activa. "
                        "Cree o active una licencia desde Configuración → Justech → Licencias "
                        "antes de agregar empresas."
                    )
                )
            if license_rec.max_companies > 0:
                current = len(license_rec.company_line_ids)
                enabled_ids = license_rec.company_line_ids.mapped("company_id").ids
                if target.id not in enabled_ids and current >= license_rec.max_companies:
                    self._client_module_audit(
                        action,
                        product,
                        target,
                        status_before,
                        status_before,
                        result="fail",
                        reason="max_companies",
                    )
                    raise JustechLicenseError(
                        _(
                            "Esta licencia no permite habilitar más empresas. Contacte a Justech."
                        )
                    )
            if target.id not in license_rec.company_line_ids.mapped("company_id").ids:
                internal["justech.license.company"].create(
                    {"license_id": license_rec.id, "company_id": target.id}
                )
            if state.is_paid:
                for ln in product.line_ids:
                    feat = internal["justech.feature"].search(
                        [("code", "=", ln.feature_code)], limit=1
                    )
                    if feat:
                        self.activate_feature(ln.feature_code, company=target)
        elif action == "remove_company":
            target = target_company
            if not target:
                raise JustechLicenseError(_("Target company required."))
            license_rec = self._get_active_license_for_company(company)
            if license_rec:
                line = license_rec.company_line_ids.filtered(
                    lambda l: l.company_id.id == target.id
                )
                line.unlink()
        elif action == "change_license":
            license_rec = self._get_active_license_for_company(company)
            new_tier = (reason or "").strip().upper()
            allowed = {"TRIAL", "STD", "PRO", "ENT"}
            if not license_rec or new_tier not in allowed:
                raise JustechLicenseError(_("Plan de licencia no válido."))
            license_rec.sudo().write({"tier": new_tier})
        else:
            raise JustechLicenseError(_("Unknown action '%(a)s'.") % {"a": action})

        status_after, _status_label = self._client_module_status(
            product,
            company,
            state,
            bool(product.line_ids),
            self._product_is_active_for_company(product, company),
        )
        self._client_module_audit(
            action,
            product,
            company,
            status_before,
            status_after,
            reason=reason,
        )
        return True

    @api.model
    def activate_module(self, module_code, company=None):
        """Activate all features of a commercial module for a company."""
        self._require_activation_admin()
        company = company or self.env.company
        module = self._sudo_internal()["justech.module"].search(
            [("code", "=", module_code)], limit=1
        )
        if not module:
            raise JustechLicenseError(
                _("Unknown module '%(code)s'.") % {"code": module_code}
            )
        for feature in module.feature_ids:
            self.activate_feature(feature.code, company=company)
        return True

    @api.model
    def deactivate_module(self, module_code, company=None):
        """Deactivate all non-always-on features of a module for a company."""
        self._require_activation_admin()
        company = company or self.env.company
        module = self._sudo_internal()["justech.module"].search(
            [("code", "=", module_code)], limit=1
        )
        if not module:
            raise JustechLicenseError(
                _("Unknown module '%(code)s'.") % {"code": module_code}
            )
        for feature in module.feature_ids.filtered(lambda f: not f.always_on):
            self.deactivate_feature(feature.code, company=company)
        return True

    @api.model
    def _set_feature_company_active(
        self, feature, company, active=True, reason="manual"
    ):
        activation = self._sudo_internal()["justech.feature.company"].search(
            [
                ("feature_id", "=", feature.id),
                ("company_id", "=", company.id),
            ],
            limit=1,
        )
        vals = {
            "is_active": active,
            "activated_at": fields.Datetime.now() if active else False,
            "activated_by_id": self.env.uid if active else False,
        }
        FeatureCompany = self._sudo_internal()["justech.feature.company"]
        if activation:
            activation.write(vals)
        else:
            FeatureCompany.create(
                {
                    "feature_id": feature.id,
                    "company_id": company.id,
                    **vals,
                }
            )
        self._audit(
            "activate" if active else "deactivate",
            feature_id=feature.id,
            company_id=company.id,
            details={"reason": reason},
        )
        self.clear_license_cache()

    # -------------------------------------------------------------- internals
    @api.model
    def _get_feature_record(self, feature_code):
        return self.get_feature(feature_code)

    @api.model
    def _company_has_valid_license(self, company):
        return bool(self._get_valid_licenses_for_company(company))

    @api.model
    def _get_valid_licenses_for_company(self, company):
        """All non-expired active licenses explicitly assigned to company."""
        today = date.today()
        company_lines = self._sudo_internal()["justech.license.company"].search(
            [
                ("company_id", "=", company.id),
                ("license_id.state", "=", "active"),
            ]
        )
        valid = self.env["justech.license"]
        for line in company_lines:
            license_rec = line.license_id
            if license_rec.expires_at and license_rec.expires_at < today:
                continue
            valid |= license_rec
        return valid

    @api.model
    def _get_active_license_for_company(self, company):
        """Primary license for company (most recent valid assignment)."""
        valid = self._get_valid_licenses_for_company(company)
        return valid.sorted(key=lambda lic: lic.id, reverse=True)[:1]

    @api.model
    def _feature_granted_to_company(self, feature, company):
        if not feature.license_required:
            return True
        valid_licenses = self._get_valid_licenses_for_company(company)
        if not valid_licenses:
            return False
        for license_rec in valid_licenses:
            if license_rec.feature_line_ids.filtered(
                lambda line: line.feature_id.id == feature.id
            ):
                return True
        return False

    @api.model
    def _feature_is_active_for_company(self, feature_id, company_id):
        activation = self._sudo_internal()["justech.feature.company"].search(
            [
                ("feature_id", "=", feature_id),
                ("company_id", "=", company_id),
            ],
            limit=1,
        )
        if activation:
            return activation.is_active
        feature = self._sudo_internal()["justech.feature"].browse(feature_id)
        return feature.default_active

    @api.model
    def _order_features_by_module_dependencies(self, features):
        if not features:
            return features
        modules = features.mapped("module_id")
        ordered_modules = self._topological_sort_modules(modules)
        ordered = self.env["justech.feature"]
        for module in ordered_modules:
            ordered |= features.filtered(lambda f, m=module: f.module_id.id == m.id)
        ordered |= features.filtered(lambda f: not f.module_id)
        return ordered

    @api.model
    def _topological_sort_modules(self, modules):
        module_ids = set(modules.ids)
        ordered = self.env["justech.module"]
        remaining = modules
        while remaining:
            progressed = False
            for module in list(remaining):
                required = module.dependency_ids.filtered(
                    lambda dep: dep.dependency_type == "required"
                )
                pending = required.filtered(
                    lambda dep: dep.depends_on_module_id.id in module_ids
                    and dep.depends_on_module_id not in ordered
                )
                if not pending:
                    ordered |= module
                    remaining -= module
                    progressed = True
            if not progressed:
                ordered |= remaining
                break
        return ordered

    @api.model
    def _collect_missing_module_deps(self, module, company, missing, visited):
        if module.id in visited:
            return
        visited.add(module.id)
        for dep in module.dependency_ids.filtered(
            lambda record: record.dependency_type == "required"
        ):
            depends_on = dep.depends_on_module_id
            if not self._module_is_satisfied(depends_on, company):
                missing.append(
                    {
                        "module_code": depends_on.code,
                        "module_name": depends_on.name,
                        "dependency_type": dep.dependency_type,
                    }
                )
            self._collect_missing_module_deps(depends_on, company, missing, visited)

    @api.model
    def _module_is_satisfied(self, module, company):
        if not module.feature_ids:
            return True
        for feature in module.feature_ids:
            if self.is_active(feature.code, company=company):
                return True
        return False

    @api.model
    def _upsert_module(self, vals):
        module = self.env["justech.module"].search([("code", "=", vals["code"])], limit=1)
        if module:
            module.write(vals)
        else:
            module = self.env["justech.module"].create(vals)
        return module

    @api.model
    def _upsert_feature(self, vals):
        feature = self.env["justech.feature"].search(
            [("code", "=", vals["code"])], limit=1
        )
        if feature:
            feature.write(vals)
        else:
            feature = self.env["justech.feature"].create(vals)
        return feature

    @api.model
    def _audit(self, action, feature_id=False, license_id=False, company_id=False, details=None):
        self.env["justech.license.audit"].sudo().create(
            {
                "action": action,
                "feature_id": feature_id,
                "license_id": license_id,
                "company_id": company_id or self.env.company.id,
                "user_id": self.env.uid,
                "details": details or {},
            }
        )

    @api.model
    def _collect_feature_ids_for_products(self, product_codes):
        internal = self._sudo_internal()
        Product = internal["justech.commercial.product"]
        Feature = internal["justech.feature"]
        feature_ids = set()
        for code in product_codes or []:
            product = Product.search([("code", "=", code), ("active", "=", True)], limit=1)
            if not product:
                continue
            for line in product.line_ids:
                feature = Feature.search([("code", "=", line.feature_code)], limit=1)
                if feature:
                    feature_ids.add(feature.id)
        return list(feature_ids)

    @api.model
    def admin_upsert_license(
        self,
        company,
        tier="STD",
        target_state="draft",
        company_ids=None,
        starts_at=None,
        expires_at=None,
        max_companies=0,
        product_codes=None,
        license_id=None,
        name=None,
    ):
        """Create or update a commercial license (internal API — requires step-up)."""
        self._require_license_admin()
        internal = self._sudo_internal()
        License = internal["justech.license"]
        LicenseCompany = internal["justech.license.company"]
        LicenseFeature = internal["justech.license.feature"]
        company = company or self.env.company
        company_ids = list(company_ids or [company.id])
        if company.id not in company_ids:
            company_ids.insert(0, company.id)

        license_rec = License.browse(license_id) if license_id else License.browse()
        if license_rec and not license_rec.exists():
            license_rec = License.browse()
        if not license_rec:
            license_rec = License.search(
                [
                    ("company_line_ids.company_id", "in", company_ids),
                    ("state", "in", ("draft", "active")),
                ],
                limit=1,
                order="id desc",
            )
        created = False
        if not license_rec:
            license_rec = License.create(
                {
                    "name": name or company.name,
                    "tier": tier,
                    "state": "draft",
                    "starts_at": starts_at,
                    "expires_at": expires_at,
                    "max_companies": max_companies,
                }
            )
            created = True
            self._audit(
                "register",
                license_id=license_rec.id,
                company_id=company.id,
                details={
                    "tier": tier,
                    "company_ids": company_ids,
                    "product_codes": product_codes or [],
                },
            )
        else:
            license_rec.write(
                {
                    "tier": tier,
                    "starts_at": starts_at or license_rec.starts_at,
                    "expires_at": expires_at,
                    "max_companies": max_companies,
                    **({"name": name} if name else {}),
                }
            )

        existing_company_ids = set(license_rec.company_line_ids.mapped("company_id").ids)
        for cid in company_ids:
            if cid not in existing_company_ids:
                LicenseCompany.create({"license_id": license_rec.id, "company_id": cid})

        feature_ids = self._collect_feature_ids_for_products(product_codes)
        if feature_ids:
            license_rec.feature_line_ids.unlink()
            for feature_id in feature_ids:
                LicenseFeature.create(
                    {"license_id": license_rec.id, "feature_id": feature_id}
                )

        if target_state == "active":
            license_rec.action_activate()
            self._audit(
                "activate",
                license_id=license_rec.id,
                company_id=company.id,
                details={"product_codes": product_codes or [], "created": created},
            )
        elif target_state and license_rec.state != target_state:
            license_rec.write({"state": target_state})

        self.clear_license_cache()
        return license_rec

    @api.model
    def admin_activate_license(self, license_id, company=None):
        self._require_license_admin()
        internal = self._sudo_internal()
        license_rec = internal["justech.license"].browse(license_id)
        if not license_rec.exists():
            raise JustechLicenseError(_("Licencia no encontrada."))
        if not license_rec.company_line_ids:
            raise JustechLicenseError(
                _("Asigne al menos una empresa antes de activar la licencia.")
            )
        license_rec.action_activate()
        self._audit(
            "activate",
            license_id=license_rec.id,
            company_id=(company or self.env.company).id,
            details={"via": "admin_activate"},
        )
        self.clear_license_cache()
        return license_rec

    @api.model
    def admin_change_plan(self, license_id, tier, company=None):
        self._require_license_admin()
        allowed = {"TRIAL", "STD", "PRO", "ENT"}
        tier = (tier or "").upper()
        if tier not in allowed:
            raise JustechLicenseError(_("Plan de licencia no válido."))
        internal = self._sudo_internal()
        license_rec = internal["justech.license"].browse(license_id)
        if not license_rec.exists():
            raise JustechLicenseError(_("Licencia no encontrada."))
        before = license_rec.tier
        license_rec.write({"tier": tier})
        self._audit(
            "validate",
            license_id=license_rec.id,
            company_id=(company or self.env.company).id,
            details={"action": "change_plan", "before": before, "after": tier},
        )
        self.clear_license_cache()
        return license_rec

    @api.model
    def admin_add_company_to_license(self, license_id, target_company, company=None):
        self._require_license_admin()
        if not target_company:
            raise JustechLicenseError(_("Seleccione la empresa a habilitar."))
        internal = self._sudo_internal()
        license_rec = internal["justech.license"].browse(license_id)
        if not license_rec.exists() or license_rec.state != "active":
            raise JustechLicenseError(
                _(
                    "No hay una licencia activa. "
                    "Cree o active una licencia desde Configuración → Justech → Licencias."
                )
            )
        enabled_ids = license_rec.company_line_ids.mapped("company_id").ids
        if target_company.id in enabled_ids:
            return license_rec
        if license_rec.max_companies > 0 and len(enabled_ids) >= license_rec.max_companies:
            raise JustechLicenseError(
                _("Esta licencia no permite habilitar más empresas. Ajuste el límite o el plan.")
            )
        internal["justech.license.company"].create(
            {"license_id": license_rec.id, "company_id": target_company.id}
        )
        self._audit(
            "validate",
            license_id=license_rec.id,
            company_id=(company or self.env.company).id,
            details={
                "action": "add_company",
                "target_company_id": target_company.id,
                "target_company_name": target_company.name,
            },
        )
        self.clear_license_cache()
        return license_rec
