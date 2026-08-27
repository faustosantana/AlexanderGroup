"""Registra la personalización oficial Justech "Pagos y Retenciones Dominicanas".

Etapa A (no destructiva): extiende el catálogo comercial `justech.license.service`
para exponer `payments_withholding_rd` en Crear Licencia, Licencias y
Personalizaciones y Módulos del Cliente, con interruptores ON/OFF comerciales.

No modifica el motor de retenciones (sigue viviendo en `justech_l10n_do_payments_withholding`).
La visibilidad depende de que este módulo técnico esté instalado
(`technical_modules_all`), de modo que la personalización NO aparece si el
módulo no está presente.
"""
from odoo import models

from odoo.addons.justech_modules.models.justech_license_service import (
    JustechLicenseService as _BaseLicenseService,
)

PAYMENTS_WITHHOLDING_CUSTOMIZATION = {
    "code": "payments_withholding_rd",
    "name": "Pagos y Retenciones Dominicanas",
    "description": (
        "Gestión de pagos con retenciones fiscales dominicanas, ITBIS retenido, "
        "ISR retenido, conciliación y trazabilidad fiscal."
    ),
    "primary_product_code": "payments_withholding_rd",
    "technical_modules_all": ("justech_l10n_do_payments_withholding",),
    "includes": [
        "Pagos con retención",
        "Retención ITBIS",
        "Retención ISR",
        "Retención a proveedores",
        "Retenciones gubernamentales",
        "Comprobantes de retención",
        "Reporte 623",
        "Trazabilidad de retenciones",
    ],
    "commercial_features": [
        {"key": "pagos_retencion", "label": "Pagos con retención", "section": "pagos", "section_label": "PAGOS", "section_sequence": 10, "sequence": 10, "description": "Registro de cobros/pagos con retención fiscal aplicada.", "default_on": True},
        {"key": "validaciones_pago", "label": "Validaciones fiscales de pago", "section": "pagos", "section_label": "PAGOS", "section_sequence": 10, "sequence": 20, "description": "Controles fiscales en el registro de pagos con retención.", "default_on": True},
        {"key": "ret_itbis", "label": "Retención ITBIS", "section": "retenciones", "section_label": "RETENCIONES", "section_sequence": 20, "sequence": 10, "description": "Retención de ITBIS (30%, 75%, 100%).", "default_on": True},
        {"key": "ret_isr", "label": "Retención ISR", "section": "retenciones", "section_label": "RETENCIONES", "section_sequence": 20, "sequence": 20, "description": "Retención de ISR (2%, 10%, honorarios).", "default_on": True},
        {"key": "ret_proveedor", "label": "Retención a proveedores", "section": "retenciones", "section_label": "RETENCIONES", "section_sequence": 20, "sequence": 30, "description": "Retenciones aplicadas al pagar a proveedores.", "default_on": True},
        {"key": "ret_cliente", "label": "Retención a clientes (si aplica)", "section": "retenciones", "section_label": "RETENCIONES", "section_sequence": 20, "sequence": 40, "description": "Retenciones aplicadas en cobros a clientes cuando aplica.", "default_on": True},
        {"key": "ret_gobierno", "label": "Retenciones gubernamentales", "section": "retenciones", "section_label": "RETENCIONES", "section_sequence": 20, "sequence": 50, "description": "Retención 5% del Estado (alimenta 623).", "default_on": True},
        {"key": "comprobante_retencion", "label": "Comprobantes de retención", "section": "documentos", "section_label": "DOCUMENTOS", "section_sequence": 30, "sequence": 10, "description": "Comprobante/recibo de retención del pago.", "default_on": True},
        {"key": "reporte_623", "label": "Reporte 623", "section": "documentos", "section_label": "DOCUMENTOS", "section_sequence": 30, "sequence": 20, "description": "Formato DGII 623 de retenciones del Estado.", "default_on": True},
        {"key": "trazabilidad", "label": "Trazabilidad de retenciones", "section": "documentos", "section_label": "DOCUMENTOS", "section_sequence": 30, "sequence": 30, "description": "Trazabilidad pago ↔ factura ↔ retención ↔ conciliación.", "default_on": True},
    ],
    "sequence": 38,
    "allow_license_actions": True,
    "visible_to_client": True,
}


class JustechLicenseServiceWithholding(models.AbstractModel):
    _inherit = "justech.license.service"

    REAL_JUSTECH_CUSTOMIZATIONS = _BaseLicenseService.REAL_JUSTECH_CUSTOMIZATIONS + (
        PAYMENTS_WITHHOLDING_CUSTOMIZATION,
    )
    JUSTECH_REAL_CUSTOMIZATIONS = REAL_JUSTECH_CUSTOMIZATIONS
    LICENSE_WIZARD_CUSTOMIZATION_CODES = (
        _BaseLicenseService.LICENSE_WIZARD_CUSTOMIZATION_CODES
        + ("payments_withholding_rd",)
    )
