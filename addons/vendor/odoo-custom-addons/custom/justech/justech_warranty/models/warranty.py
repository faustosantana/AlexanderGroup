# -*- coding: utf-8 -*-
from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class JustechWarranty(models.Model):
    _name = "justech.warranty"
    _description = "Garantía de producto"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "date_start desc, id desc"

    name = fields.Char(
        string="Referencia",
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _("Nueva"),
        tracking=True,
    )
    partner_id = fields.Many2one(
        "res.partner", string="Cliente", required=True, tracking=True,
        index=True, ondelete="restrict",
    )
    vendor_id = fields.Many2one(
        "res.partner",
        string="Proveedor / Fabricante",
        index=True,
        ondelete="restrict",
        tracking=True,
        help="Proveedor cuya garantía respalda a esta unidad (opcional).",
    )
    product_id = fields.Many2one(
        "product.product", string="Producto", required=True, tracking=True,
        index=True, ondelete="restrict",
    )
    # RC6.2: el seguimiento por lote de Odoo (`product.tracking == 'serial'`)
    # ya no es un requisito duro; sólo se usa como sugerencia para exigir
    # serial en las unidades. El serial primario vive en las unidades de
    # garantía (`justech.warranty.unit.serial_manufacturer`).
    tracking = fields.Char(
        string="Seguimiento del producto",
        compute="_compute_product_tracking",
        store=False,
        help="Refleja `product.tracking` de forma segura aunque el módulo stock "
        "no esté instalado.",
    )
    quantity = fields.Float(
        string="Unidades esperadas",
        default=1.0,
        help="Número de unidades cubiertas por esta garantía comercial.",
    )

    invoice_id = fields.Many2one(
        "account.move", string="Factura de origen", copy=False,
        index=True, ondelete="set null",
    )
    invoice_line_id = fields.Many2one(
        "account.move.line", string="Línea de factura", copy=False,
        index=True, ondelete="set null",
    )
    sale_order_id = fields.Many2one(
        "sale.order", string="Pedido de venta", copy=False, ondelete="set null",
    )

    warranty_type = fields.Selection(
        [("store", "Tienda"), ("manufacturer", "Fabricante"), ("extended", "Extendida")],
        string="Tipo", default="store", required=True, tracking=True,
    )
    type_id = fields.Many2one(
        "justech.warranty.type", string="Tipo de garantía", tracking=True,
        domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]",
        ondelete="restrict",
    )
    date_start = fields.Date(
        string="Inicio", required=True, default=fields.Date.context_today, tracking=True,
    )
    warranty_months = fields.Integer(
        string="Meses cliente", required=True, default=0, tracking=True,
        help="Cobertura otorgada al cliente final.",
    )
    date_end = fields.Date(
        string="Vencimiento", compute="_compute_date_end", store=True, tracking=True,
    )
    vendor_warranty_months = fields.Integer(
        string="Meses proveedor",
        default=0,
        tracking=True,
        help="Cobertura otorgada por el proveedor/fabricante.",
    )
    vendor_date_start = fields.Date(string="Inicio cobertura proveedor")
    vendor_date_end = fields.Date(
        string="Vencimiento cobertura proveedor",
        compute="_compute_vendor_date_end",
        store=True,
    )
    coverage_gap_months = fields.Integer(
        string="Gap de cobertura (meses)",
        compute="_compute_coverage_gap",
        store=True,
    )
    days_to_expire = fields.Integer(
        string="Días restantes", compute="_compute_days_to_expire",
    )
    state = fields.Selection(
        [
            ("draft", "Borrador"),
            ("pending_serial", "Pendiente de serie"),
            ("active", "Activa"),
            ("expired", "Vencida"),
            ("claimed", "Reclamada"),
            ("void", "Anulada"),
        ],
        string="Estado", default="draft", required=True, tracking=True, index=True,
    )
    certificate_ready = fields.Boolean(
        string="Lista para certificado",
        compute="_compute_certificate_ready",
        help="La garantía puede emitir certificado cuando está Activa y todas sus "
        "unidades tienen serial de fabricante registrado.",
    )
    terms = fields.Text(string="Términos y condiciones")
    note = fields.Text(string="Notas internas")

    company_id = fields.Many2one(
        "res.company", string="Compañía", required=True,
        default=lambda self: self.env.company, index=True,
    )
    claim_ids = fields.One2many("justech.warranty.claim", "warranty_id", string="Reclamos")
    claim_count = fields.Integer(string="Nº reclamos", compute="_compute_claim_count")

    unit_ids = fields.One2many(
        "justech.warranty.unit", "warranty_id", string="Unidades",
        copy=False,
    )
    unit_count = fields.Integer(
        string="Total unidades", compute="_compute_unit_stats", store=True,
    )
    serial_registered_count = fields.Integer(
        string="Seriales registrados", compute="_compute_unit_stats", store=True,
    )
    serial_pending_count = fields.Integer(
        string="Seriales pendientes", compute="_compute_unit_stats", store=True,
    )

    # ------------------------------------------------------------------
    # Computes
    # ------------------------------------------------------------------
    @api.depends("date_start", "warranty_months")
    def _compute_date_end(self):
        for rec in self:
            if rec.date_start and rec.warranty_months:
                rec.date_end = rec.date_start + relativedelta(months=rec.warranty_months)
            else:
                rec.date_end = False

    @api.depends("vendor_date_start", "vendor_warranty_months")
    def _compute_vendor_date_end(self):
        for rec in self:
            if rec.vendor_date_start and rec.vendor_warranty_months:
                rec.vendor_date_end = rec.vendor_date_start + relativedelta(
                    months=rec.vendor_warranty_months
                )
            else:
                rec.vendor_date_end = False

    @api.depends("warranty_months", "vendor_warranty_months", "date_end", "vendor_date_end")
    def _compute_coverage_gap(self):
        for rec in self:
            gap = 0
            if rec.date_end and rec.vendor_date_end:
                if rec.date_end > rec.vendor_date_end:
                    delta = relativedelta(rec.date_end, rec.vendor_date_end)
                    gap = delta.years * 12 + delta.months
            elif rec.warranty_months and rec.vendor_warranty_months:
                gap = max(0, rec.warranty_months - rec.vendor_warranty_months)
            elif rec.warranty_months and not rec.vendor_warranty_months:
                gap = rec.warranty_months
            rec.coverage_gap_months = gap

    @api.depends("date_end")
    def _compute_days_to_expire(self):
        today = fields.Date.context_today(self)
        for rec in self:
            rec.days_to_expire = (rec.date_end - today).days if rec.date_end else 0

    @api.depends("product_id")
    def _compute_product_tracking(self):
        """Refleja `product.tracking` sin exigir el módulo `stock` instalado."""
        for rec in self:
            product = rec.product_id
            rec.tracking = (
                getattr(product, "tracking", False) if product else False
            ) or "none"

    @api.depends(
        "state",
        "tracking",
        "unit_ids",
        "unit_ids.serial_manufacturer",
    )
    def _compute_certificate_ready(self):
        for rec in self:
            if rec.state != "active":
                rec.certificate_ready = False
                continue
            if rec.tracking != "serial":
                rec.certificate_ready = True
                continue
            if rec.unit_ids:
                rec.certificate_ready = all(
                    unit.serial_manufacturer for unit in rec.unit_ids
                )
            else:
                rec.certificate_ready = False

    @api.depends(
        "unit_ids",
        "unit_ids.serial_manufacturer",
        "unit_ids.serial_state",
    )
    def _compute_unit_stats(self):
        for rec in self:
            units = rec.unit_ids
            rec.unit_count = len(units)
            registered = units.filtered(
                lambda u: u.serial_manufacturer or u.serial_state == "confirmed"
            )
            rec.serial_registered_count = len(registered)
            rec.serial_pending_count = len(units) - len(registered)

    def _compute_claim_count(self):
        data = self.env["justech.warranty.claim"]._read_group(
            [("warranty_id", "in", self.ids)], ["warranty_id"], ["__count"]
        )
        mapped = {warranty.id: count for warranty, count in data}
        for rec in self:
            rec.claim_count = mapped.get(rec.id, 0)

    # ------------------------------------------------------------------
    # Onchange
    # ------------------------------------------------------------------
    @api.onchange("product_id")
    def _onchange_product_id(self):
        if self.product_id and not self.warranty_months:
            self.warranty_months = self.product_id._get_warranty_months()

    @api.onchange("type_id")
    def _onchange_type_id(self):
        if self.type_id:
            self.warranty_type = self.type_id.kind
            if not self.warranty_months and self.type_id.default_months:
                self.warranty_months = self.type_id.default_months

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", _("Nueva")) == _("Nueva"):
                vals["name"] = self.env["ir.sequence"].next_by_code(
                    "justech.warranty"
                ) or _("Nueva")
            if not vals.get("terms"):
                company = self.env["res.company"].browse(
                    vals.get("company_id")
                ) if vals.get("company_id") else self.env.company
                if company.justech_warranty_default_terms:
                    vals["terms"] = company.justech_warranty_default_terms
        return super().create(vals_list)

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def action_activate(self):
        for rec in self:
            if rec.state not in ("draft", "expired", "pending_serial"):
                raise UserError(
                    _("Solo puede activar garantías en borrador, pendientes de serie o vencidas.")
                )
            if not rec.warranty_months:
                raise UserError(_("Defina los meses de garantía antes de activar."))
            new_state = "active"
            if rec.tracking == "serial":
                if rec.unit_ids:
                    if not any(u.serial_manufacturer for u in rec.unit_ids):
                        new_state = "pending_serial"
                else:
                    new_state = "pending_serial"
            rec.state = new_state
        return True

    def action_set_expired(self):
        self.write({"state": "expired"})
        return True

    def action_void(self):
        self.write({"state": "void"})
        return True

    def action_reset_to_draft(self):
        self.write({"state": "draft"})
        return True

    def action_view_claims(self):
        self.ensure_one()
        return {
            "name": _("Reclamos"),
            "type": "ir.actions.act_window",
            "res_model": "justech.warranty.claim",
            "view_mode": "list,form",
            "domain": [("warranty_id", "=", self.id)],
            "context": {"default_warranty_id": self.id},
        }

    def action_view_units(self):
        self.ensure_one()
        return {
            "name": _("Unidades / seriales"),
            "type": "ir.actions.act_window",
            "res_model": "justech.warranty.unit",
            "view_mode": "list,form",
            "domain": [("warranty_id", "=", self.id)],
            "context": {"default_warranty_id": self.id},
        }

    @api.model
    def _cron_expire_warranties(self):
        today = fields.Date.context_today(self)
        expiring = self.search(
            [("state", "=", "active"), ("date_end", "<", today)]
        )
        if expiring:
            expiring.write({"state": "expired"})
        return True
