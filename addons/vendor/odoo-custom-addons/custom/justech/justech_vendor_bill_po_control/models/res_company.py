# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError


class ResCompany(models.Model):
    _inherit = "res.company"

    vendor_bill_po_policy = fields.Selection(
        [
            ("disabled", "Desactivado"),
            ("warning", "Advertencia"),
            ("block", "Bloqueo al contabilizar"),
        ],
        string="Exigir Orden de Compra en facturas de proveedor",
        default="disabled",
        help="Controla si se exige OC al contabilizar facturas de proveedor. "
        "Los borradores siempre se pueden guardar sin OC.",
        tracking=True,
    )
    purchase_order_required = fields.Boolean(
        string="OC requerida (activa)",
        compute="_compute_purchase_order_required",
        help="True cuando la política no está Desactivada.",
    )
    vendor_bill_strict_approval = fields.Boolean(
        string="Control estricto de aprobación",
        default=False,
        tracking=True,
        help="Si está activo: sin OC válida (salvo regla) → Pendiente de Validación; "
        "bloquea contabilización, pagos, Tesorería y retenciones hasta aprobar.",
    )
    vendor_bill_require_classification = fields.Boolean(
        string="Exigir Tipo de costos y gastos al validar",
        default=True,
        tracking=True,
        help="Si está activo, Enviar a Validación exige el campo fiscal "
        "Tipo de costos y gastos. No decide si se requiere OC.",
    )
    vendor_bill_block_payment = fields.Boolean(
        string="Bloquear pagos si no aprobada",
        default=True,
    )
    vendor_bill_block_treasury = fields.Boolean(
        string="Bloquear Tesorería si no aprobada",
        default=True,
    )
    vendor_bill_block_withholding = fields.Boolean(
        string="Bloquear retenciones si no aprobada",
        default=True,
    )
    vendor_bill_amount_finance_limit = fields.Monetary(
        string="Tope aprobación Finanzas",
        currency_field="currency_id",
        default=25000.0,
        help="Hasta este monto (moneda compañía) basta Finanzas.",
    )
    vendor_bill_amount_management_limit = fields.Monetary(
        string="Tope aprobación Gerencia",
        currency_field="currency_id",
        default=250000.0,
        help="Entre tope Finanzas y este monto: Gerencia. Superior: doble aprobación.",
    )
    vendor_bill_default_finance_approver_id = fields.Many2one(
        "res.users",
        string="Aprobador predeterminado Finanzas",
        help="Sugerido al enviar facturas que requieren nivel Finanzas.",
    )
    vendor_bill_default_mgmt_approver_id = fields.Many2one(
        "res.users",
        string="Aprobador predeterminado Gerencia",
        help="Sugerido cuando el nivel requerido es Gerencia o doble aprobación.",
    )
    vendor_bill_default_substitute_id = fields.Many2one(
        "res.users",
        string="Aprobador suplente",
        help="Puede decidir si el asignado no está disponible.",
    )
    vendor_bill_approval_deadline_hours = fields.Integer(
        string="Plazo de aprobación (horas)",
        default=24,
        help="Fecha límite de la actividad de aprobación. Por defecto 24 horas.",
    )
    vendor_bill_notify_internal = fields.Boolean(
        string="Notificación interna al aprobador",
        default=True,
    )
    vendor_bill_notify_email = fields.Boolean(
        string="Correo al aprobador",
        default=True,
        help="En DEV use catchall/mailhog. No envía si el aprobador no tiene email.",
    )
    vendor_bill_allow_reassign = fields.Boolean(
        string="Permitir reasignación",
        default=True,
    )
    vendor_bill_allow_admin_override = fields.Boolean(
        string="Administrador puede decidir cualquier solicitud",
        default=True,
    )
    vendor_bill_require_sod = fields.Boolean(
        string="Exigir separación de funciones (doble aprobación)",
        default=True,
        help="Si está activo, la misma persona no puede completar ambos niveles de doble aprobación.",
    )
    vendor_bill_no_po_auto_classification = fields.Selection(
        [
            ("direct", "Compra directa"),
            ("internal", "Gasto interno"),
        ],
        string="Clasificación automática sin OC",
        default="direct",
        help="Al aprobar una factura sin Orden de Compra se asigna automáticamente "
        "esta clasificación (no crea asientos adicionales).",
    )
    vendor_bill_approval_effective_from = fields.Datetime(
        string="Vigencia del control de aprobación",
        help="La política estricta aplica solo a facturas de proveedor creadas "
        "en o después de esta fecha/hora. Los documentos anteriores conservan "
        "su flujo original (legacy_exempt técnico).",
        tracking=True,
        copy=False,
    )
    vendor_bill_allow_self_approval = fields.Boolean(
        string="Permitir autoaprobación",
        default=False,
        tracking=True,
        help="Si está desactivado, el usuario que envió la factura no puede "
        "aprobarla salvo Administrador de Contabilidad / Administrador del sistema.",
    )

    @api.depends("vendor_bill_po_policy")
    def _compute_purchase_order_required(self):
        for company in self:
            company.purchase_order_required = (
                company.vendor_bill_po_policy or "disabled"
            ) != "disabled"

    def write(self, vals):
        sensitive = {
            "vendor_bill_strict_approval",
            "vendor_bill_po_policy",
            "vendor_bill_block_payment",
            "vendor_bill_block_treasury",
            "vendor_bill_block_withholding",
            "vendor_bill_approval_effective_from",
            "vendor_bill_allow_self_approval",
        }
        if sensitive.intersection(vals) and not self.env.su:
            if not (
                self.env.user.has_group("base.group_system")
                or self.env.user.has_group(
                    "justech_vendor_bill_po_control.group_vendor_bill_approver_management"
                )
            ):
                raise AccessError(
                    _(
                        "Solo Administrador o Gerencia pueden cambiar la política "
                        "de control de facturas de proveedor."
                    )
                )
        return super().write(vals)
