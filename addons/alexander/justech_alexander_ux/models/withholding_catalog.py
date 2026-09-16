"""Catálogo Alexander 2026 (Ley 30-26). No pisa tasas antiguas del módulo."""

from odoo import api, fields, models

from odoo.addons.justech_alexander_base.models.withholding_math import money

# Cuentas existentes del plan l10n_do (lookup por nombre, nunca por id).
ACCOUNT_ISR_OTHER = "Other Withholdings (N07-07)"
ACCOUNT_ISR_OTHER_ALT = "Other Withholdings"
ACCOUNT_ISR_RENT = "ISR withheld on rent paid to individuals"
ACCOUNT_ISR_INTEREST = "ISR withheld on interest paid"
ACCOUNT_ISR_INTEREST_ABROAD = "ISR Withheld on Interest Paid Abroad"
ACCOUNT_ISR_ABROAD = "ISR Withheld on Remittances Abroad (L253-12)"
ACCOUNT_ITBIS_PJ = "ITBIS Withheld from Legal Entity (N02-05)"
ACCOUNT_ITBIS_PF = "ITBIS Withheld from Individuals (R293-11)"
ACCOUNT_ITBIS_ESFL = "ITBIS Withheld from Non-Profit Entities (N01-11)"
ACCOUNT_ITBIS_PROF = "ITBIS Withheld for Professional Services (N02-05)"
ACCOUNT_ITBIS_INF = "ITBIS Withheld from Informal Goods (N08-10)"

# CONFIG ACTUAL (impuestos l10n_do ya instalados) vs NORMA VIGENTE 01/07/2026.
LEGACY_VS_2026 = (
    {
        "config_actual": "-10% ISR Fee / RET-HON-10",
        "norma_vigente": "15% ISR honorarios PF desde 01/07/2026 (Art. 309 b, Ley 30-26)",
        "cambio_propuesto": "Usar DX-ISR-PROF-PF-15. No modificar el impuesto -10%.",
    },
    {
        "config_actual": "-10% ISR Rent. / RET-HON-10",
        "norma_vigente": "15% ISR alquiler PF desde 01/07/2026 (Art. 309 a)",
        "cambio_propuesto": "Usar DX-ISR-ALQ-PF-15. No modificar el impuesto -10%.",
    },
    {
        "config_actual": "-2% ISR (N07-07) / RET-ISR-2",
        "norma_vigente": "15% sobre renta presunta 20% = 3% efectivo (técnicos PF)",
        "cambio_propuesto": "Usar DX-ISR-TEC-PF-15. No modificar el impuesto -2%.",
    },
    {
        "config_actual": "-27% ISR (L253-12) para todo pago al exterior",
        "norma_vigente": "15% regalías/software/publicidad/datos; 27% resto Art. 305",
        "cambio_propuesto": "Usar DX-ISR-EXT-* según concepto. No cambiar -27%.",
    },
)


def _dx_2026_specs():
    return (
        {
            "code": "DX-ISR-ESTADO-5",
            "name": "RET ISR — Proveedor del Estado — 5%",
            "withholding_type": "isr",
            "rate": 5.0,
            "base_type": "untaxed",
            "category": "isr_estado",
            "account_name": ACCOUNT_ISR_OTHER,
            "account_name_alt": ACCOUNT_ISR_OTHER_ALT,
            "partner_scope": "supplier",
            "move_scope": "purchase",
            "affects_606": True,
            "affects_623": True,
            "dgii_withholding_code": "05",
            "date_from": "2026-07-01",
            "legal_source": "Art. 309 e) CT, modificado por Art. 17 Ley 30-26",
            "condition": (
                "Solo cuando el pagador es entidad del Estado y no prevalece "
                "una retención específica de Persona Física."
            ),
            "notes": "Selección controlada. No aplicar automáticamente a PF.",
        },
        {
            "code": "DX-ISR-PROF-PF-15",
            "name": "RET ISR — Servicios Profesionales PF — 15%",
            "withholding_type": "isr",
            "rate": 15.0,
            "base_type": "untaxed",
            "category": "isr_profesional",
            "account_name": ACCOUNT_ISR_OTHER,
            "account_name_alt": ACCOUNT_ISR_OTHER_ALT,
            "partner_scope": "supplier",
            "move_scope": "purchase",
            "affects_606": True,
            "affects_623": True,
            "dgii_withholding_code": "02",
            "date_from": "2026-07-01",
            "legal_source": "Art. 309 b) CT / Art. 17 Ley 30-26. Aviso DGII 10-26.",
            "condition": (
                "Honorarios, comisiones, asesorías u otros servicios de Persona "
                "Física que requieren intervención humana. No entre PJ-PJ."
            ),
            "notes": "Base = monto sujeto SIN ITBIS. Pago a cuenta IR-17.",
        },
        {
            "code": "DX-ISR-TEC-PF-15",
            "name": "RET ISR — Servicios Técnicos PF — 15% sobre 20% presunto",
            "withholding_type": "isr",
            "rate": 15.0,
            "base_type": "untaxed",
            "presumed_income_pct": 20.0,
            "category": "isr_tecnico",
            "account_name": ACCOUNT_ISR_OTHER,
            "account_name_alt": ACCOUNT_ISR_OTHER_ALT,
            "partner_scope": "supplier",
            "move_scope": "purchase",
            "affects_606": True,
            "affects_623": True,
            "dgii_withholding_code": "03",
            "date_from": "2026-07-01",
            "legal_source": (
                "Art. 309 CT + Art. 70 Regl. 139-98 + Art. 17 Ley 30-26. "
                "Comunidad DGII CA59 / Aviso 10-26."
            ),
            "condition": (
                "Albañilería, fumigación, limpieza, carpintería, pintura, "
                "ebanistería, plomería, transporte y oficios técnicos PF."
            ),
            "notes": "Base original × 20% presunta × 15% = 3% efectivo del bruto.",
        },
        {
            "code": "DX-ISR-ALQ-PF-15",
            "name": "RET ISR — Alquiler Persona Física — 15%",
            "withholding_type": "isr",
            "rate": 15.0,
            "base_type": "untaxed",
            "category": "isr_alquiler",
            "account_name": ACCOUNT_ISR_RENT,
            "partner_scope": "supplier",
            "move_scope": "purchase",
            "affects_606": True,
            "affects_623": True,
            "dgii_withholding_code": "01",
            "date_from": "2026-07-01",
            "legal_source": "Art. 309 a) CT / Art. 17 Ley 30-26. Único y definitivo.",
            "condition": (
                "Alquiler de bien mueble o inmueble pagado a Persona Física. "
                "ITBIS se analiza aparte (vivienda exenta vs comercial)."
            ),
            "notes": "No confundir con retención de ITBIS.",
        },
        {
            "code": "DX-ITBIS-30-PJ",
            "name": "RET ITBIS — 30% entre Personas Jurídicas",
            "withholding_type": "itbis",
            "rate": 30.0,
            "base_type": "itbis",
            "category": "itbis_30",
            "account_name": ACCOUNT_ITBIS_PJ,
            "partner_scope": "supplier",
            "move_scope": "purchase",
            "affects_606": True,
            "dgii_withholding_code": "02",
            "date_from": "2005-01-01",
            "legal_source": "Norma General 02-05. Base = ITBIS facturado.",
            "condition": (
                "Servicios profesionales liberales o alquiler de muebles entre "
                "PJ cuando la norma lo contempla. No automático a toda factura. "
                "Revisar e-CF del proveedor antes de aplicar."
            ),
            "notes": "100,000 + ITBIS 18,000 → retención 5,400. Nunca 30% del subtotal.",
        },
        {
            "code": "DX-ITBIS-100-PF",
            "name": "RET ITBIS — 100% Servicios Persona Física",
            "withholding_type": "itbis",
            "rate": 100.0,
            "base_type": "itbis",
            "category": "itbis_100",
            "account_name": ACCOUNT_ITBIS_PF,
            "partner_scope": "supplier",
            "move_scope": "purchase",
            "affects_606": True,
            "dgii_withholding_code": "03",
            "date_from": "2011-01-01",
            "legal_source": "R293-11 / guía DGII IT-1. 100% del ITBIS facturado.",
            "condition": "PF presta servicio gravado a PJ/NUD. ISR se calcula aparte.",
            "notes": "Servicio 100,000 + ITBIS 18,000 → retención ITBIS 18,000.",
        },
        {
            "code": "DX-ITBIS-100-SEG",
            "name": "RET ITBIS — 100% Seguridad y vigilancia",
            "withholding_type": "itbis",
            "rate": 100.0,
            "base_type": "itbis",
            "category": "itbis_100",
            "account_name": ACCOUNT_ITBIS_PROF,
            "partner_scope": "supplier",
            "move_scope": "purchase",
            "affects_606": True,
            "dgii_withholding_code": "03",
            "legal_source": "Supuestos especiales 100% ITBIS (seguridad/vigilancia).",
            "condition": "Solo seguridad y vigilancia cuando la norma aplicable lo exija.",
            "notes": "Selección manual. No automatizar.",
        },
        {
            "code": "DX-ITBIS-100-ESFL",
            "name": "RET ITBIS — 100% Entidades sin fines de lucro",
            "withholding_type": "itbis",
            "rate": 100.0,
            "base_type": "itbis",
            "category": "itbis_100",
            "account_name": ACCOUNT_ITBIS_ESFL,
            "partner_scope": "supplier",
            "move_scope": "purchase",
            "affects_606": True,
            "dgii_withholding_code": "03",
            "legal_source": "Norma General 01-11.",
            "condition": "Servicios gravados prestados por ESFL cuando corresponda.",
            "notes": "Selección manual.",
        },
        {
            "code": "DX-ITBIS-100-INF",
            "name": "RET ITBIS — Informal / RST (cuando aplique)",
            "withholding_type": "itbis",
            "rate": 100.0,
            "base_type": "itbis",
            "category": "itbis_100",
            "account_name": ACCOUNT_ITBIS_INF,
            "partner_scope": "supplier",
            "move_scope": "purchase",
            "affects_606": True,
            "dgii_withholding_code": "04",
            "legal_source": "N08-10 / RST según normativa vigente del caso.",
            "condition": "Proveedor informal o RST solo si la norma del caso lo establece.",
            "notes": "No automatizar por tipo de contacto.",
        },
        {
            "code": "DX-ISR-DIV-10",
            "name": "RET ISR — Dividendos — 10% (IR-17 / otras)",
            "withholding_type": "isr",
            "rate": 10.0,
            "base_type": "untaxed",
            "category": "ir17_otras",
            "account_name": ACCOUNT_ISR_OTHER_ALT,
            "account_name_alt": ACCOUNT_ISR_OTHER,
            "partner_scope": "supplier",
            "move_scope": "purchase",
            "affects_623": True,
            "dgii_withholding_code": "08",
            "legal_source": "Art. 308 CT. Único y definitivo.",
            "condition": "Distribución de dividendos. No mezclar con retenciones de proveedores.",
            "notes": "IR-17 otras retenciones.",
        },
        {
            "code": "DX-ISR-INT-PF-10",
            "name": "RET ISR — Intereses PF residente — 10%",
            "withholding_type": "isr",
            "rate": 10.0,
            "base_type": "untaxed",
            "category": "ir17_otras",
            "account_name": ACCOUNT_ISR_INTEREST,
            "partner_scope": "supplier",
            "move_scope": "purchase",
            "affects_623": True,
            "legal_source": "Art. 306 bis CT.",
            "condition": "Intereses pagados a persona física residente.",
            "notes": "Único y definitivo, con excepciones legales.",
        },
        {
            "code": "DX-ISR-INT-EXT-10",
            "name": "RET ISR — Intereses al exterior — 10%",
            "withholding_type": "isr",
            "rate": 10.0,
            "base_type": "untaxed",
            "category": "exterior",
            "account_name": ACCOUNT_ISR_INTEREST_ABROAD,
            "partner_scope": "supplier",
            "move_scope": "purchase",
            "affects_623": True,
            "legal_source": "Art. 306 CT.",
            "condition": "Intereses de fuente dominicana pagados a no residentes.",
            "notes": "Revisar CDI si existe.",
        },
        {
            "code": "DX-ISR-EXT-REG-15",
            "name": "RET ISR — Exterior regalías — 15%",
            "withholding_type": "isr",
            "rate": 15.0,
            "base_type": "untaxed",
            "category": "exterior",
            "account_name": ACCOUNT_ISR_ABROAD,
            "partner_scope": "supplier",
            "move_scope": "purchase",
            "affects_623": True,
            "date_from": "2026-07-01",
            "legal_source": "Art. 305-1 CT, Art. 21 Ley 30-26.",
            "condition": "Regalías o derechos pagados al exterior.",
            "notes": "No usar 27% automático.",
        },
        {
            "code": "DX-ISR-EXT-SW-15",
            "name": "RET ISR — Exterior software / licencia — 15%",
            "withholding_type": "isr",
            "rate": 15.0,
            "base_type": "untaxed",
            "category": "exterior",
            "account_name": ACCOUNT_ISR_ABROAD,
            "partner_scope": "supplier",
            "move_scope": "purchase",
            "affects_623": True,
            "date_from": "2026-07-01",
            "legal_source": "Art. 305-2 CT, Art. 22 Ley 30-26.",
            "condition": "Licencia de software. Excluye cesión de propiedad.",
            "notes": "Suscripciones SaaS / licencias. No 27% automático.",
        },
        {
            "code": "DX-ISR-EXT-ADS-15",
            "name": "RET ISR — Exterior publicidad en línea — 15%",
            "withholding_type": "isr",
            "rate": 15.0,
            "base_type": "untaxed",
            "category": "exterior",
            "account_name": ACCOUNT_ISR_ABROAD,
            "partner_scope": "supplier",
            "move_scope": "purchase",
            "affects_623": True,
            "date_from": "2026-07-01",
            "legal_source": "Art. 305-2 CT, Art. 22 Ley 30-26.",
            "condition": "Publicidad en línea pagada al exterior.",
            "notes": "No 27% automático.",
        },
        {
            "code": "DX-ISR-EXT-DATA-15",
            "name": "RET ISR — Exterior datos / nube — 15%",
            "withholding_type": "isr",
            "rate": 15.0,
            "base_type": "untaxed",
            "category": "exterior",
            "account_name": ACCOUNT_ISR_ABROAD,
            "partner_scope": "supplier",
            "move_scope": "purchase",
            "affects_623": True,
            "date_from": "2026-07-01",
            "legal_source": "Art. 305-2 CT, Art. 22 Ley 30-26.",
            "condition": "Uso o almacenamiento de datos / hosting pagado al exterior.",
            "notes": "No 27% automático.",
        },
        {
            "code": "DX-ISR-EXT-27",
            "name": "RET ISR — Exterior otras rentas — 27%",
            "withholding_type": "isr",
            "rate": 27.0,
            "base_type": "untaxed",
            "category": "exterior",
            "account_name": ACCOUNT_ISR_ABROAD,
            "partner_scope": "supplier",
            "move_scope": "purchase",
            "affects_623": True,
            "legal_source": "Art. 305 CT (regla general residual).",
            "condition": (
                "Pagos al exterior de fuente dominicana SIN tasa especial "
                "(no regalías, software, ads ni datos)."
            ),
            "notes": "Último recurso. No usar para todos los pagos al exterior.",
        },
        {
            "code": "DX-ISR-PREMIO-25",
            "name": "RET ISR — Premios generales — 25%",
            "withholding_type": "isr",
            "rate": 25.0,
            "base_type": "untaxed",
            "category": "ir17_otras",
            "account_name": ACCOUNT_ISR_OTHER_ALT,
            "account_name_alt": ACCOUNT_ISR_OTHER,
            "partner_scope": "supplier",
            "move_scope": "purchase",
            "affects_623": True,
            "date_from": "2026-07-01",
            "legal_source": "Art. 309 c) CT / Art. 17 Ley 30-26.",
            "condition": "Loterías, sorteos, campañas promocionales. No bancas (escala propia).",
            "notes": "IR-17 otras retenciones.",
        },
        {
            "code": "DX-ISR-OTRAS-15",
            "name": "RET ISR — Otras rentas Art. 309 f) — 15%",
            "withholding_type": "isr",
            "rate": 15.0,
            "base_type": "untaxed",
            "category": "ir17_otras",
            "account_name": ACCOUNT_ISR_OTHER,
            "account_name_alt": ACCOUNT_ISR_OTHER_ALT,
            "partner_scope": "supplier",
            "move_scope": "purchase",
            "affects_623": True,
            "date_from": "2026-07-01",
            "legal_source": "Art. 309 f) CT / Art. 17 Ley 30-26.",
            "condition": "Rentas no contempladas expresamente. Selección jurídica.",
            "notes": "No usar como comodín operativo de proveedores.",
        },
    )


class JustechDoWithholdingCatalog(models.Model):
    _inherit = "justech.do.withholding.catalog"

    dx_presumed_income_pct = fields.Float(
        string="Renta neta presunta (%)",
        help="Si > 0, la tasa legal se aplica sobre este % del bruto (técnicos PF).",
    )
    dx_category = fields.Selection(
        [
            ("isr_estado", "ISR Estado"),
            ("isr_profesional", "ISR profesional PF"),
            ("isr_tecnico", "ISR técnico PF"),
            ("isr_alquiler", "ISR alquiler PF"),
            ("itbis_30", "ITBIS 30% PJ"),
            ("itbis_100", "ITBIS 100%"),
            ("ir17_otras", "Otras / IR-17"),
            ("exterior", "Pagos al exterior"),
        ],
        string="Categoría Alexander",
    )
    dx_legal_source = fields.Char(string="Fuente normativa")
    dx_condition = fields.Text(string="Condición de aplicación")

    def _base_label(self):
        self.ensure_one()
        if self.dx_presumed_income_pct:
            return "Base presunta (%s%% del bruto)" % int(self.dx_presumed_income_pct)
        return super()._base_label()

    def _base_amount(self, move, applied_amount=None):
        base = super()._base_amount(move, applied_amount=applied_amount)
        if self.dx_presumed_income_pct:
            return float(money(base) * money(self.dx_presumed_income_pct) / money(100))
        return base

    def compute_withholding_amount(self, move, applied_amount=None):
        # La base presunta ya entra por `_base_amount`; la tasa legal sigue en rate.
        return super().compute_withholding_amount(move, applied_amount=applied_amount)

    @api.model
    def _dx_find_account(self, company, name, alt=None):
        Account = self.env["account.account"].sudo().with_company(company)
        domain = [("name", "=", name), ("company_ids", "in", [company.id])]
        rec = Account.search(domain, limit=1)
        if rec:
            return rec
        if alt:
            rec = Account.search(
                [("name", "=", alt), ("company_ids", "in", [company.id])],
                limit=1,
            )
        return rec

    @api.model
    def dx_sync_2026_catalog(self, companies=None):
        """Crea/actualiza códigos DX-* 2026. No toca tasas de impuestos viejos."""
        Catalog = self.sudo().with_context(active_test=False)
        Config = self.env["justech.do.withholding.company.config"].sudo()
        if companies is None:
            companies = (
                self.env["res.company"].sudo().search([("dx_short_code", "!=", False)])
            )
        created = []
        for spec in _dx_2026_specs():
            rec = Catalog.search(
                [("code", "=", spec["code"]), ("company_id", "=", False)],
                limit=1,
            )
            vals = {
                "name": spec["name"],
                "code": spec["code"],
                "withholding_type": spec["withholding_type"],
                "rate": spec["rate"],
                "base_type": spec["base_type"],
                "partner_scope": spec["partner_scope"],
                "move_scope": spec["move_scope"],
                "affects_606": spec.get("affects_606", False),
                "affects_607": spec.get("affects_607", False),
                "affects_623": spec.get("affects_623", False),
                "dgii_withholding_code": spec.get("dgii_withholding_code"),
                "date_from": spec.get("date_from"),
                "notes": spec.get("notes"),
                "dx_category": spec.get("category"),
                "dx_legal_source": spec.get("legal_source"),
                "dx_condition": spec.get("condition"),
                "dx_presumed_income_pct": spec.get("presumed_income_pct", 0.0),
                "company_id": False,
                "tax_id": False,
                "pending_confirmation": False,
                "active": True,
            }
            if rec:
                rec.write({k: v for k, v in vals.items() if k != "active"})
                if not rec.active:
                    rec.active = True
            else:
                rec = Catalog.create(vals)
            for company in companies:
                account = self._dx_find_account(
                    company,
                    spec["account_name"],
                    spec.get("account_name_alt"),
                )
                cfg = Config.search(
                    [
                        ("catalog_id", "=", rec.id),
                        ("company_id", "=", company.id),
                    ],
                    limit=1,
                )
                cfg_vals = {
                    "catalog_id": rec.id,
                    "company_id": company.id,
                    "account_id": account.id if account else False,
                    "active_config": bool(account),
                    "date_from": spec.get("date_from"),
                    "notes": spec.get("legal_source"),
                }
                if cfg:
                    cfg.write(cfg_vals)
                else:
                    Config.create(cfg_vals)
            created.append(rec.code)
        return created
