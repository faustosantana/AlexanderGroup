import ast
import logging
import os

from odoo import _, api, fields, models
from odoo.modules.module import get_module_path, get_modules

_logger = logging.getLogger(__name__)

CATEGORY_MAP = {
    "fiscal": "fiscal",
    "accounting": "fiscal",
    "platform": "platform",
    "reports": "reports",
    "payments": "payments",
    "treasury": "treasury",
    "audit": "audit",
    "ux": "ux",
    "integrations": "integrations",
    "pos": "other",
    "inventory": "other",
}

PRODUCT_CODE_MAP = {
    "platform": "core",
    "fiscal": "fiscal",
    "reports": "fiscal",
    "payments": "finance",
    "treasury": "finance",
    "audit": "audit",
    "integrations": "integrations",
    "other": "core",
    "ux": "core",
}

# Nombres y descripciones funcionales (nunca usar el technical name como título)
FUNCTIONAL_CATALOG = {
    "justech_admin_center": {
        "functional_name": "Administración Justech",
        "short_description": (
            "Consola central para administrar productos Justech, empresas, permisos, "
            "diagnósticos y auditoría. Es el punto de entrada de administración."
        ),
        "product_code": "core",
        "what_it_does": "Centraliza la administración del ecosistema Justech.",
        "processes_affected": "Configuración, seguridad, diagnóstico y auditoría.",
        "users_who_use_it": "Administradores Justech y del sistema.",
        "risk_activate": "Habilita la consola de administración.",
        "risk_deactivate": "Impide administrar productos Justech desde la consola.",
    },
    "justech_modules": {
        "functional_name": "Seguridad y roles",
        "short_description": (
            "Define el registro de módulos Justech, roles base y la sesión administrativa "
            "compartida entre productos."
        ),
        "product_code": "core",
    },
    "justech_l10n_do_ncf": {
        "functional_name": "Motor Fiscal NCF",
        "short_description": (
            "Genera y controla los números de comprobantes fiscales utilizados por la empresa. "
            "Administra secuencias, rangos, validaciones y evita duplicados."
        ),
        "product_code": "fiscal",
        "fiscal_engine_capable": True,
        "what_it_does": "Controla la emisión y validación de NCF.",
        "processes_affected": "Facturación, notas de crédito/débito y reportes DGII.",
        "users_who_use_it": "Contabilidad y facturación.",
        "risk_activate": "Habilita emisión controlada de NCF por empresa.",
        "risk_deactivate": "Puede bloquear nuevas facturas fiscales; conserva histórico.",
    },
    "justech_fiscal_admin": {
        "functional_name": "Centro Fiscal",
        "short_description": (
            "Panel de supervisión fiscal por empresa: estado NCF, alertas, permisos "
            "y acceso a herramientas fiscales."
        ),
        "product_code": "fiscal",
    },
    "justech_l10n_do_dgii_reports": {
        "functional_name": "Reportes DGII",
        "short_description": (
            "Genera reportes fiscales 606, 607, 608, 609 y 623 para cumplimiento DGII."
        ),
        "product_code": "fiscal",
    },
    "justech_l10n_do_padron": {
        "functional_name": "Padrón DGII",
        "short_description": (
            "Consulta y valida datos del padrón de contribuyentes DGII para clientes y proveedores."
        ),
        "product_code": "fiscal",
    },
    "justech_l10n_do_withholding": {
        "functional_name": "Retenciones fiscales",
        "short_description": (
            "Capacidad compartida de retenciones. Puede abrirse desde Justech Fiscal "
            "y Justech Finanzas, con una sola fuente funcional."
        ),
        "product_code": "fiscal",
    },
    "justech_l10n_do_treasury": {
        "functional_name": "Tesorería",
        "short_description": (
            "Administra cobros, pagos, pagos abiertos y flujos de tesorería por empresa."
        ),
        "product_code": "finance",
    },
    "justech_warranty": {
        "functional_name": "Registro de garantías",
        "short_description": (
            "Permite registrar, consultar y dar seguimiento a las garantías de productos "
            "vendidos a clientes."
        ),
        "product_code": "warranty",
    },
    "justech_core": {
        "functional_name": "Configuración multiempresa",
        "short_description": (
            "Servicios compartidos del núcleo Justech para operar varias empresas "
            "sobre la misma plataforma."
        ),
        "product_code": "core",
    },
    "justech_l10n_do_adel_freeze": {
        "functional_name": "Auditoría y Salud Fiscal",
        "short_description": (
            "Controles de salud fiscal y congelamiento preventivo para proteger "
            "la integridad de comprobantes y reportes."
        ),
        "product_code": "fiscal",
    },
    "justech_l10n_do_base": {
        "functional_name": "Padrón DGII",
        "short_description": (
            "Padrón de contribuyentes DGII compartido por todas las empresas. "
            "Se carga y actualiza una sola vez (cada 45 días). No se activa por empresa."
        ),
        "product_code": "fiscal",
        "activation_scope": "global",
        "open_action_xmlid": "justech_admin_center.action_justech_admin_padron_hub",
        "supports_activate": False,
        "supports_deactivate": False,
        "critical": True,
    },
    "justech_modules": {
        "functional_name": "Seguridad y roles",
        "short_description": (
            "Define el registro de módulos Justech, roles base y la sesión administrativa "
            "compartida entre productos."
        ),
        "product_code": "core",
        "activation_scope": "global",
    },
    "justech_core": {
        "functional_name": "Configuración multiempresa",
        "short_description": (
            "Servicios compartidos del núcleo Justech para operar varias empresas "
            "sobre la misma plataforma."
        ),
        "product_code": "core",
        "activation_scope": "global",
    },
    "justech_admin_center": {
        "functional_name": "Administración Justech",
        "short_description": (
            "Consola central para administrar productos Justech, empresas, permisos, "
            "diagnósticos y auditoría."
        ),
        "product_code": "core",
        "activation_scope": "global",
        "supports_activate": False,
        "supports_deactivate": False,
        "critical": True,
    },
    "justech_global_audit_log": {
        "functional_name": "Auditoría global",
        "short_description": (
            "Registra cambios funcionales y técnicos relevantes del ecosistema Justech."
        ),
        "product_code": "audit",
        "activation_scope": "global",
    },
    "justech_l10n_do_reports": {
        "functional_name": "Reportes DGII",
        "short_description": (
            "Genera reportes fiscales 606, 607, 608, 609 y 623 para cumplimiento DGII."
        ),
        "product_code": "fiscal",
    },
    "justech_ecf_admin": {
        "functional_name": "Facturación electrónica e-CF",
        "short_description": (
            "Facturación electrónica e-CF DGII: configuración por empresa, certificados, "
            "XML/XSD oficiales, firma, colas, contingencia y Gate de Producción."
        ),
        "product_code": "fiscal",
        "fiscal_engine_capable": True,
        "activation_scope": "company",
        "open_action_xmlid": "justech_ecf_admin.action_justech_ecf_admin_hub",
        "what_it_does": "Emite y administra comprobantes fiscales electrónicos e-CF.",
        "processes_affected": "Facturación electrónica, certificación DGII, colas y auditoría e-CF.",
        "users_who_use_it": "Contabilidad, facturación y administradores fiscales.",
        "risk_activate": "Habilita el motor e-CF en el ambiente configurado (mock/certificación).",
        "risk_deactivate": "Bloquea nuevos envíos e-CF; conserva histórico y documentos.",
        "critical": True,
    },
    "justech_ecf_core": {
        "functional_name": "Justech e-CF (núcleo)",
        "short_description": "Núcleo de datos e-CF (config, documentos, eventos).",
        "product_code": "fiscal",
        "activation_scope": "company",
    },
    "justech_l10n_do_payments_withholding": {
        "functional_name": "Retenciones",
        "short_description": (
            "Capacidad compartida de retenciones en cobros y pagos. Puede abrirse desde "
            "Justech Fiscal y Justech Finanzas, con una sola fuente funcional."
        ),
        "product_code": "fiscal",
    },
}


class JustechAdminRegistryService(models.AbstractModel):
    _name = "justech.admin.registry.service"
    _description = "Registro dinámico de módulos Justech Admin"

    @api.model
    def discover_and_sync(self):
        """Scan justech_* addons + installed modules; upsert catalog without hardcoded branches."""
        Module = self.env["justech.admin.module"].sudo()
        IrModule = self.env["ir.module.module"].sudo()
        seen = set()
        payloads = []

        for tech_name, manifest in self._iter_justech_manifests():
            payload = self._payload_from_manifest(tech_name, manifest)
            payloads.append(payload)
            seen.add(tech_name)

        # Installed justech_* without local admin_center block still appear
        installed = IrModule.search([("name", "=like", "justech_%"), ("state", "=", "installed")])
        for irm in installed:
            if irm.name in seen:
                continue
            payloads.append(self._payload_from_ir_module(irm))
            seen.add(irm.name)

        for payload in payloads:
            rec = self._upsert(Module, IrModule, payload)
            if rec.technical_state == "installed":
                self.env["justech.admin.company.activation.service"].ensure_lines_for_module(rec)

        # Mark missing physical modules
        orphans = Module.search([("technical_name", "not in", list(seen or [""]))])
        if orphans and seen:
            orphans.write({"technical_state": "unavailable", "is_installable": False})
        return Module.search([])

    @api.model
    def _iter_justech_manifests(self):
        """Yield (technical_name, manifest_dict) for justech_* packages on addons path."""
        for name in sorted(get_modules()):
            if not name.startswith("justech_") or name.endswith("_test"):
                continue
            mod_path = get_module_path(name)
            if not mod_path:
                continue
            manifest_path = os.path.join(mod_path, "__manifest__.py")
            if not os.path.isfile(manifest_path):
                continue
            try:
                with open(manifest_path, "r", encoding="utf-8") as fh:
                    content = fh.read()
            except OSError:
                continue
            try:
                manifest = ast.literal_eval(content)
            except (SyntaxError, ValueError) as exc:
                _logger.warning("Manifest inválido %s: %s", name, exc)
                continue
            yield name, manifest

    @api.model
    def _functional_override(self, tech_name):
        if tech_name in FUNCTIONAL_CATALOG:
            return FUNCTIONAL_CATALOG[tech_name]
        # Heurísticas suaves por familia (sin exponer technical name)
        if "ncf" in tech_name:
            return FUNCTIONAL_CATALOG.get("justech_l10n_do_ncf", {})
        if "dgii" in tech_name and "report" in tech_name:
            return FUNCTIONAL_CATALOG.get("justech_l10n_do_dgii_reports", {})
        if "padron" in tech_name or "padrón" in tech_name:
            return FUNCTIONAL_CATALOG.get("justech_l10n_do_padron", {})
        if "withhold" in tech_name or "retencion" in tech_name:
            return FUNCTIONAL_CATALOG.get(
                "justech_l10n_do_payments_withholding",
                FUNCTIONAL_CATALOG.get("justech_l10n_do_withholding", {}),
            )
        if "treasury" in tech_name:
            return {"product_code": "finance"}
        if "payment" in tech_name:
            return {"product_code": "finance"}
        if "warranty" in tech_name:
            return FUNCTIONAL_CATALOG.get("justech_warranty", {})
        if "audit" in tech_name or "health" in tech_name:
            return {"product_code": "audit"}
        return {}

    @api.model
    def _payload_from_manifest(self, tech_name, manifest):
        register = manifest.get("justech_register") or {}
        center = manifest.get("justech_admin_center") or {}
        override = self._functional_override(tech_name)
        category = center.get("category") or CATEGORY_MAP.get(
            (register.get("category") or "").lower(), "other"
        )
        product_code = (
            center.get("product_code")
            or override.get("product_code")
            or PRODUCT_CODE_MAP.get(category, "core")
        )
        if tech_name in FUNCTIONAL_CATALOG and FUNCTIONAL_CATALOG[tech_name].get("product_code"):
            product_code = FUNCTIONAL_CATALOG[tech_name]["product_code"]
        if "warranty" in tech_name:
            product_code = center.get("product_code") or "warranty"
        activation_scope = (
            override.get("activation_scope")
            or center.get("activation_scope")
            or "company"
        )
        open_action = (
            override.get("open_action_xmlid")
            or center.get("open_action_xmlid")
            or False
        )
        supports_activate = override.get(
            "supports_activate",
            center.get("supports_activate", True),
        )
        supports_deactivate = override.get(
            "supports_deactivate",
            center.get("supports_deactivate", True),
        )
        deps = manifest.get("depends") or []
        justech_deps = [d for d in deps if d.startswith("justech_")]
        short = (
            override.get("short_description")
            or center.get("short_description")
            or register.get("description")
            or manifest.get("summary")
            or _("Sin descripción funcional — complete el contrato justech_admin_center.")
        )
        long_desc = (
            override.get("long_description")
            or center.get("long_description")
            or short
        )
        functional_name = (
            override.get("functional_name")
            or center.get("functional_name")
            or register.get("module_name")
            or manifest.get("name")
            or tech_name
        )
        # Nunca dejar el technical name como título visible
        if functional_name == tech_name and override.get("functional_name"):
            functional_name = override["functional_name"]
        return {
            "technical_name": tech_name,
            "functional_name": functional_name,
            "short_description": short,
            "long_description": long_desc,
            "what_it_does": center.get("what_it_does")
            or override.get("what_it_does")
            or short,
            "processes_affected": center.get("processes_affected")
            or override.get("processes_affected")
            or "",
            "users_who_use_it": center.get("users_who_use_it")
            or override.get("users_who_use_it")
            or "",
            "risk_activate": center.get("risk_activate")
            or override.get("risk_activate")
            or "",
            "risk_deactivate": center.get("risk_deactivate")
            or override.get("risk_deactivate")
            or "",
            "product_code": product_code,
            "activation_scope": activation_scope,
            "fiscal_engine_capable": bool(
                center.get("fiscal_engine_capable", override.get("fiscal_engine_capable", False))
            ),
            "category": category if category in dict(self.env["justech.admin.module"]._fields["category"].selection) else "other",
            "icon": center.get("icon") or ("fa-shield" if "warranty" in tech_name else "fa-cube"),
            "sequence": int(center.get("sequence") or (40 if "warranty" in tech_name else 100)),
            "version": register.get("version") or manifest.get("version") or "",
            "dependency_names": ", ".join(justech_deps),
            "open_action_xmlid": open_action,
            "health_method": center.get("health_method") or False,
            "feature_flag_codes": ",".join(center.get("feature_flag_codes") or []),
            "supports_activate": bool(supports_activate),
            "supports_deactivate": bool(supports_deactivate),
            "is_critical": bool(override.get("critical", center.get("critical", False))),
            "is_installable": True,
            "odoo_depends": deps,
        }

    @api.model
    def _payload_from_ir_module(self, irm):
        cat = "other"
        if "warranty" in (irm.name or ""):
            return {
                "technical_name": irm.name,
                "functional_name": "Justech Garantías",
                "short_description": "Gestión de garantías: registro, seguimiento, aprobaciones y reportes.",
                "long_description": (
                    "Qué es: producto de garantías Justech. Para qué sirve: registrar y dar seguimiento a garantías. "
                    "Procesos: postventa y RMA. Crítico: no. Ámbito: por empresa. Al desactivar: bloquea nuevas; conserva histórico."
                ),
                "what_it_does": "Administra garantías de producto por empresa.",
                "processes_affected": "Postventa, RMA, aprobaciones y alertas.",
                "users_who_use_it": "Administrador y usuario de Garantías.",
                "risk_activate": "Habilita operaciones nuevas de garantías.",
                "risk_deactivate": "Bloquea nuevas; conserva histórico y lectura.",
                "product_code": "warranty",
                "activation_scope": "company",
                "fiscal_engine_capable": False,
                "category": "other",
                "icon": "fa-shield",
                "sequence": 40,
                "version": irm.latest_version or "",
                "dependency_names": "",
                "open_action_xmlid": False,
                "health_method": False,
                "feature_flag_codes": "",
                "supports_activate": True,
                "supports_deactivate": True,
                "is_critical": False,
                "is_installable": irm.state in ("uninstalled", "to install"),
                "odoo_depends": [],
            }
        return {
            "technical_name": irm.name,
            "functional_name": irm.shortdesc or irm.name,
            "short_description": irm.summary or _("Módulo Justech instalado — complete su descripción funcional."),
            "long_description": irm.summary or "",
            "what_it_does": irm.summary or "",
            "processes_affected": "",
            "users_who_use_it": "",
            "risk_activate": "",
            "risk_deactivate": "",
            "product_code": PRODUCT_CODE_MAP.get(cat, "core"),
            "activation_scope": "company",
            "fiscal_engine_capable": False,
            "category": cat,
            "icon": "fa-cube",
            "sequence": 200,
            "version": irm.latest_version or "",
            "dependency_names": "",
            "open_action_xmlid": False,
            "health_method": False,
            "feature_flag_codes": "",
            "supports_activate": True,
            "supports_deactivate": True,
            "is_critical": False,
            "is_installable": irm.state in ("uninstalled", "to install"),
            "odoo_depends": [],
        }

    @api.model
    def _resolve_product(self, product_code):
        Product = self.env["justech.admin.product"].sudo()
        product = Product.search([("code", "=", product_code)], limit=1)
        return product

    @api.model
    def _upsert(self, Module, IrModule, payload):
        tech = payload["technical_name"]
        irm = IrModule.search([("name", "=", tech)], limit=1)
        tech_state = "unavailable"
        if irm:
            if irm.state == "installed":
                tech_state = "installed"
            elif irm.state in ("to upgrade", "to remove"):
                tech_state = "to_upgrade" if irm.state == "to upgrade" else "installed"
            elif irm.state in ("uninstalled", "to install"):
                tech_state = "not_installed"
            else:
                tech_state = "not_installed"
        else:
            tech_state = "unavailable"

        functional = "inactive"
        if tech_state == "installed":
            functional = self._resolve_functional_state(tech, payload)

        product = self._resolve_product(payload.get("product_code") or "core")
        vals = {
            "technical_name": tech,
            "functional_name": payload["functional_name"],
            "short_description": payload["short_description"],
            "long_description": payload.get("long_description") or payload["short_description"],
            "what_it_does": payload.get("what_it_does") or "",
            "processes_affected": payload.get("processes_affected") or "",
            "users_who_use_it": payload.get("users_who_use_it") or "",
            "risk_activate": payload.get("risk_activate") or "",
            "risk_deactivate": payload.get("risk_deactivate") or "",
            "product_id": product.id if product else False,
            "activation_scope": payload.get("activation_scope") or "company",
            "fiscal_engine_capable": bool(payload.get("fiscal_engine_capable")),
            "category": payload["category"],
            "icon": payload["icon"],
            "sequence": payload["sequence"],
            "version": payload["version"],
            "dependency_names": payload["dependency_names"],
            "open_action_xmlid": payload["open_action_xmlid"],
            "health_method": payload["health_method"],
            "feature_flag_codes": payload["feature_flag_codes"],
            "supports_activate": payload["supports_activate"],
            "supports_deactivate": payload["supports_deactivate"],
            "is_critical": payload["is_critical"],
            "is_installable": payload["is_installable"] and tech_state != "unavailable",
            "technical_state": tech_state if irm else "unavailable",
            "functional_state": functional if tech_state == "installed" else "inactive",
            "ir_module_id": irm.id if irm else False,
            "last_sync_at": fields.Datetime.now(),
        }
        existing = Module.search([("technical_name", "=", tech)], limit=1)
        if existing:
            existing.write(vals)
            return existing
        return Module.create(vals)

    @api.model
    def _resolve_functional_state(self, tech_name, payload):
        """Resolve active/inactive via feature flags when available — no module-name branching."""
        codes = [c.strip() for c in (payload.get("feature_flag_codes") or "").split(",") if c.strip()]
        if codes and "justech.fiscal.feature.flag" in self.env:
            Flag = self.env["justech.fiscal.feature.flag"].sudo()
            flags = Flag.search([("code", "in", codes)])
            if flags:
                if any(getattr(f, "is_enabled", getattr(f, "enabled", True)) is False for f in flags):
                    return "inactive"
                return "active"
        # Company fiscal enable as soft signal when fiscal category
        if payload.get("category") == "fiscal" and "justech_do_fiscal_enabled" in self.env["res.company"]._fields:
            companies = self.env["res.company"].sudo().search([])
            if companies and all(not c.justech_do_fiscal_enabled for c in companies):
                return "inactive"
            return "active"
        return "active"
