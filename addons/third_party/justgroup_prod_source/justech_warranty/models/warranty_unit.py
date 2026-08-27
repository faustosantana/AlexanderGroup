# -*- coding: utf-8 -*-
from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class JustechWarrantyUnit(models.Model):
    """Unidad física trazable dentro de una garantía comercial.

    RC6.2: una línea comercial (venta/factura) puede desglosarse en varias unidades
    de garantía independientes, cada una con su serial de fabricante, historial de
    entrega y ciclo de reclamos propio. El seguimiento por lote de inventario
    (`stock.lot`) es opcional y no se crea automáticamente.
    """

    _name = "justech.warranty.unit"
    _description = "Unidad de garantía"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "warranty_id, unit_number, id"

    name = fields.Char(
        string="Referencia",
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _("Nueva"),
        tracking=True,
    )
    unit_number = fields.Integer(
        string="N° de unidad",
        default=1,
        help="Número secuencial dentro de la línea comercial (1..N).",
    )
    active = fields.Boolean(default=True)

    warranty_id = fields.Many2one(
        "justech.warranty",
        string="Garantía",
        ondelete="cascade",
        index=True,
        tracking=True,
    )
    company_id = fields.Many2one(
        "res.company",
        string="Compañía",
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )

    product_id = fields.Many2one(
        "product.product",
        string="Producto",
        required=True,
        ondelete="restrict",
        index=True,
    )
    product_description = fields.Char(string="Descripción")

    partner_id = fields.Many2one(
        "res.partner",
        string="Cliente",
        index=True,
        ondelete="restrict",
        tracking=True,
    )
    vendor_id = fields.Many2one(
        "res.partner",
        string="Proveedor / Fabricante",
        index=True,
        ondelete="restrict",
        tracking=True,
        help="Proveedor que cubre la garantía origen (fabricante o distribuidor).",
    )

    serial_manufacturer = fields.Char(
        string="Serial del fabricante",
        tracking=True,
        help="Número de serie principal grabado en la unidad física por el fabricante.",
    )
    serial_internal = fields.Char(
        string="Serial interno",
        help="Serial interno / etiqueta comercial adicional (opcional).",
    )
    serial_state = fields.Selection(
        [
            ("planned", "Planificado"),
            ("pending", "Pendiente"),
            ("confirmed", "Confirmado"),
        ],
        string="Estado del serial",
        default="pending",
        required=True,
        tracking=True,
    )

    # Origen comercial (venta/factura de cliente)
    sale_order_id = fields.Many2one(
        "sale.order",
        string="Pedido de venta",
        ondelete="set null",
        index=True,
        copy=False,
    )
    sale_line_id = fields.Many2one(
        "sale.order.line",
        string="Línea de venta",
        ondelete="set null",
        index=True,
        copy=False,
    )
    invoice_id = fields.Many2one(
        "account.move",
        string="Factura de cliente",
        ondelete="set null",
        index=True,
        copy=False,
        domain="[('move_type', 'in', ('out_invoice', 'out_refund'))]",
    )
    invoice_line_id = fields.Many2one(
        "account.move.line",
        string="Línea de factura",
        ondelete="set null",
        index=True,
        copy=False,
    )

    # Origen de compra / factura de proveedor (opcional)
    purchase_order_id = fields.Many2one(
        "purchase.order",
        string="Pedido de compra",
        ondelete="set null",
        copy=False,
    )
    purchase_line_id = fields.Many2one(
        "purchase.order.line",
        string="Línea de compra",
        ondelete="set null",
        copy=False,
    )
    vendor_bill_id = fields.Many2one(
        "account.move",
        string="Factura de proveedor",
        ondelete="set null",
        copy=False,
        domain="[('move_type', 'in', ('in_invoice', 'in_refund'))]",
    )
    vendor_bill_line_id = fields.Many2one(
        "account.move.line",
        string="Línea de factura de proveedor",
        ondelete="set null",
        copy=False,
    )

    # NOTA: la integración con `stock.lot` se ofrece a través de un módulo
    # puente opcional (`justech_warranty_stock`, no incluido en esta versión).
    # El serial primario vive en `serial_manufacturer`.

    # Fechas y modo de entrega
    purchase_date = fields.Date(string="Fecha de compra")
    delivery_date = fields.Date(string="Fecha de entrega")
    delivery_mode = fields.Selection(
        [
            ("pending", "Pendiente"),
            ("justech", "Entrega directa"),
            ("vendor_direct", "Entrega desde proveedor"),
            ("customer_pickup", "Retiro del cliente"),
            ("partial", "Entrega parcial"),
            ("completed", "Completada"),
            ("cancelled", "Cancelada"),
        ],
        string="Modo de entrega",
        default="pending",
        tracking=True,
    )
    delivered_by = fields.Char(string="Entregado por")
    received_by = fields.Char(string="Recibido por")
    delivery_notes = fields.Text(string="Notas de entrega")

    # Coberturas (cliente vs proveedor)
    customer_warranty_months = fields.Integer(
        string="Meses cobertura cliente",
        default=0,
    )
    customer_date_start = fields.Date(string="Inicio cobertura cliente")
    customer_date_end = fields.Date(
        string="Vencimiento cliente",
        compute="_compute_customer_dates",
        store=True,
    )
    vendor_warranty_months = fields.Integer(
        string="Meses cobertura proveedor",
        default=0,
    )
    vendor_date_start = fields.Date(string="Inicio cobertura proveedor")
    vendor_date_end = fields.Date(
        string="Vencimiento proveedor",
        compute="_compute_vendor_dates",
        store=True,
    )
    coverage_gap_months = fields.Integer(
        string="Gap de cobertura (meses)",
        compute="_compute_coverage_gap",
        store=True,
        help="Meses de riesgo entre el fin de la cobertura del proveedor y la del cliente.",
    )
    coverage_risk = fields.Selection(
        [
            ("low", "Bajo"),
            ("medium", "Medio"),
            ("high", "Alto"),
        ],
        string="Riesgo de cobertura",
        compute="_compute_coverage_gap",
        store=True,
    )

    state = fields.Selection(
        [
            ("draft", "Borrador"),
            ("planned", "Planificada"),
            ("pending_serial", "Pendiente de serial"),
            ("active", "Activa"),
            ("claimed", "Reclamada"),
            ("expired", "Vencida"),
            ("void", "Anulada"),
        ],
        string="Estado",
        default="draft",
        required=True,
        tracking=True,
        index=True,
    )

    note = fields.Text(string="Notas")
    claim_ids = fields.Many2many(
        "justech.warranty.claim",
        "justech_warranty_claim_unit_rel",
        "unit_id",
        "claim_id",
        string="Reclamos",
    )
    claim_count = fields.Integer(
        string="Nº reclamos", compute="_compute_claim_count"
    )

    # ------------------------------------------------------------------
    # Constraints
    # ------------------------------------------------------------------
    # No usamos un SQL constraint parcial (PostgreSQL exige `WHERE` con
    # expresión inmutable en índices únicos). Lo aplicamos a nivel Python
    # sobre el serial de fabricante cuando existe.
    @api.constrains("company_id", "serial_manufacturer")
    def _check_serial_manufacturer_unique(self):
        for unit in self:
            if not unit.serial_manufacturer:
                continue
            serial = unit.serial_manufacturer.strip()
            if not serial:
                continue
            duplicate = self.search_count(
                [
                    ("id", "!=", unit.id),
                    ("company_id", "=", unit.company_id.id),
                    ("serial_manufacturer", "=ilike", serial),
                    ("active", "=", True),
                ]
            )
            if duplicate:
                raise ValidationError(
                    _(
                        "El serial de fabricante '%(serial)s' ya está registrado en "
                        "otra unidad de garantía de esta compañía."
                    )
                    % {"serial": serial}
                )

    # ------------------------------------------------------------------
    # Computes
    # ------------------------------------------------------------------
    @api.depends("customer_date_start", "customer_warranty_months")
    def _compute_customer_dates(self):
        for unit in self:
            if unit.customer_date_start and unit.customer_warranty_months:
                unit.customer_date_end = unit.customer_date_start + relativedelta(
                    months=unit.customer_warranty_months
                )
            else:
                unit.customer_date_end = False

    @api.depends("vendor_date_start", "vendor_warranty_months")
    def _compute_vendor_dates(self):
        for unit in self:
            if unit.vendor_date_start and unit.vendor_warranty_months:
                unit.vendor_date_end = unit.vendor_date_start + relativedelta(
                    months=unit.vendor_warranty_months
                )
            else:
                unit.vendor_date_end = False

    @api.depends(
        "customer_date_end",
        "vendor_date_end",
        "customer_warranty_months",
        "vendor_warranty_months",
    )
    def _compute_coverage_gap(self):
        for unit in self:
            gap = 0
            if unit.customer_date_end and unit.vendor_date_end:
                if unit.customer_date_end > unit.vendor_date_end:
                    delta = relativedelta(unit.customer_date_end, unit.vendor_date_end)
                    gap = delta.years * 12 + delta.months
            elif unit.customer_warranty_months and not unit.vendor_warranty_months:
                gap = unit.customer_warranty_months
            elif unit.customer_warranty_months and unit.vendor_warranty_months:
                gap = max(
                    0, unit.customer_warranty_months - unit.vendor_warranty_months
                )
            unit.coverage_gap_months = gap
            if gap <= 0:
                unit.coverage_risk = "low"
            elif gap <= 6:
                unit.coverage_risk = "medium"
            else:
                unit.coverage_risk = "high"

    def _compute_claim_count(self):
        for unit in self:
            unit.claim_count = len(unit.claim_ids)

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", _("Nueva")) == _("Nueva"):
                vals["name"] = self.env["ir.sequence"].next_by_code(
                    "justech.warranty.unit"
                ) or _("Nueva")
        units = super().create(vals_list)
        units._sync_serial_state()
        return units

    def write(self, vals):
        res = super().write(vals)
        if {"serial_manufacturer", "state"} & set(vals):
            self._sync_serial_state()
        return res

    # ------------------------------------------------------------------
    # Business helpers
    # ------------------------------------------------------------------
    def _sync_serial_state(self):
        for unit in self:
            if unit.state in ("void", "expired", "claimed"):
                continue
            has_serial = bool(unit.serial_manufacturer and unit.serial_manufacturer.strip())
            new_serial_state = "confirmed" if has_serial else (
                "planned" if unit.state in ("draft", "planned") else "pending"
            )
            if unit.serial_state != new_serial_state:
                super(JustechWarrantyUnit, unit).write({"serial_state": new_serial_state})
            if unit.state == "pending_serial" and has_serial:
                super(JustechWarrantyUnit, unit).write({"state": "active"})

    def action_confirm_serial(self):
        for unit in self:
            if not unit.serial_manufacturer:
                raise UserError(
                    _(
                        "Registre el serial de fabricante antes de confirmarlo "
                        "(unidad %s)."
                    )
                    % unit.display_name
                )
            unit.write(
                {
                    "serial_state": "confirmed",
                    "state": "active" if unit.state in ("draft", "planned", "pending_serial") else unit.state,
                }
            )
        return True

    def action_mark_claimed(self):
        self.write({"state": "claimed"})
        return True

    def action_void(self):
        self.write({"state": "void"})
        return True

    def action_view_claims(self):
        self.ensure_one()
        return {
            "name": _("Reclamos"),
            "type": "ir.actions.act_window",
            "res_model": "justech.warranty.claim",
            "view_mode": "list,form",
            "domain": [("unit_ids", "in", self.ids)],
            "context": {
                "default_warranty_id": self.warranty_id.id,
                "default_unit_ids": [(6, 0, self.ids)],
            },
        }
