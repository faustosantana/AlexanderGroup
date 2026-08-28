# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class JustechWarrantyLineConfigWizard(models.TransientModel):
    _name = "justech.warranty.line.config.wizard"
    _description = "Configurar garantía de línea"

    line_model = fields.Selection(
        [
            ("sale.order.line", "Línea de cotización"),
            ("account.move.line", "Línea de factura"),
        ],
        required=True,
    )
    # 0 = línea sin guardar (NewId): el wizard no puede escribir en el servidor
    # y devuelve los valores al front para que OWL los aplique con record.update.
    line_id = fields.Integer(required=False, default=0)
    product_id = fields.Many2one("product.product", string="Producto", readonly=True)
    warranty_apply = fields.Boolean(string="Aplica garantía", default=True)
    warranty_months = fields.Integer(string="Meses de garantía", default=12)
    warranty_type_id = fields.Many2one(
        "justech.warranty.type",
        string="Tipo de garantía",
    )
    warranty_vendor_id = fields.Many2one(
        "res.partner",
        string="Proveedor de la garantía",
    )
    warranty_expected_units = fields.Integer(
        string="Unidades esperadas",
        default=1,
        help="Cantidad de unidades físicas a cubrir (una unidad = un serial).",
    )
    warranty_planned_serials = fields.Text(
        string="Seriales planificados",
        help="Un serial por renglón. Se usarán para crear unidades al postear "
        "la factura.",
    )
    company_id = fields.Many2one(
        "res.company",
        string="Compañía",
        compute="_compute_company_id",
    )
    warranty_notes = fields.Text(string="Observaciones / condiciones")
    warranty_status = fields.Selection(
        [
            ("none", "Sin garantía"),
            ("pending", "Pendiente de configurar"),
            ("configured", "Configurada"),
        ],
        string="Estado",
        compute="_compute_warranty_status",
    )
    warranty_status_label = fields.Char(
        string="Estado garantía",
        compute="_compute_warranty_status",
    )
    is_draft_line = fields.Boolean(
        string="Línea sin guardar",
        compute="_compute_is_draft_line",
        help="Verdadero cuando el wizard fue abierto para una línea nueva "
        "(NewId): al aceptar, los valores se devuelven al frontend.",
    )

    @api.depends("warranty_apply", "warranty_months")
    def _compute_warranty_status(self):
        labels = {
            "none": _("Sin garantía"),
            "pending": _("Pendiente de configurar"),
            "configured": _("Configurada"),
        }
        for wizard in self:
            if not wizard.warranty_apply:
                status = "none"
            elif wizard.warranty_months <= 0:
                status = "pending"
            else:
                status = "configured"
            wizard.warranty_status = status
            wizard.warranty_status_label = labels[status]

    @api.depends("line_id")
    def _compute_is_draft_line(self):
        for wizard in self:
            wizard.is_draft_line = not wizard.line_id

    @api.depends("line_model", "line_id")
    def _compute_company_id(self):
        for wizard in self:
            company = self.env.company
            if wizard.line_model and wizard.line_id:
                line = self.env[wizard.line_model].browse(wizard.line_id).exists()
                if line and hasattr(line, "company_id") and line.company_id:
                    company = line.company_id
                elif line and hasattr(line, "order_id") and line.order_id.company_id:
                    company = line.order_id.company_id
                elif line and hasattr(line, "move_id") and line.move_id.company_id:
                    company = line.move_id.company_id
            wizard.company_id = company

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        line_model = res.get("line_model")
        line_id = res.get("line_id")
        if line_model and line_id:
            line = self.env[line_model].browse(line_id).exists()
            if line:
                months = line.warranty_months or line.product_id._get_warranty_months()
                expected = line.warranty_expected_units or int(
                    getattr(line, "product_uom_qty", 0)
                    or getattr(line, "quantity", 0)
                    or 1
                )
                res.update(
                    {
                        "product_id": line.product_id.id,
                        "warranty_apply": line.warranty_apply,
                        "warranty_months": months if months > 0 else 12,
                        "warranty_type_id": line.warranty_type_id.id,
                        "warranty_notes": line.warranty_notes,
                        "warranty_expected_units": expected if expected > 0 else 1,
                        "warranty_vendor_id": line.warranty_vendor_id.id or False,
                        "warranty_planned_serials": line.warranty_planned_serials or False,
                    }
                )
        else:
            if "warranty_expected_units" in fields_list and not res.get(
                "warranty_expected_units"
            ):
                res["warranty_expected_units"] = 1
        return res

    @api.constrains("warranty_months", "warranty_apply")
    def _check_warranty_months(self):
        for wizard in self:
            if wizard.warranty_apply and wizard.warranty_months <= 0:
                raise ValidationError(_("Los meses de garantía deben ser mayores que cero."))

    @api.constrains("warranty_expected_units", "warranty_apply")
    def _check_expected_units(self):
        for wizard in self:
            if wizard.warranty_apply and wizard.warranty_expected_units < 0:
                raise ValidationError(
                    _("Las unidades esperadas deben ser cero o positivas.")
                )

    # ------------------------------------------------------------------
    # Helpers de payload
    # ------------------------------------------------------------------
    def _line_payload(self):
        """Diccionario con los valores actuales a aplicar en la línea."""
        self.ensure_one()
        if not self.warranty_apply:
            return {
                "warranty_apply": False,
                "warranty_months": 0,
                "warranty_type_id": False,
                "warranty_notes": False,
                "warranty_expected_units": 0,
                "warranty_vendor_id": False,
                "warranty_planned_serials": False,
            }
        return {
            "warranty_apply": True,
            "warranty_months": self.warranty_months,
            "warranty_type_id": self.warranty_type_id.id or False,
            "warranty_notes": self.warranty_notes or False,
            "warranty_expected_units": self.warranty_expected_units or 0,
            "warranty_vendor_id": self.warranty_vendor_id.id or False,
            "warranty_planned_serials": self.warranty_planned_serials or False,
        }

    def _frontend_payload(self):
        """Igual a `_line_payload` pero con m2o serializados como
        ``[id, display_name]`` para que OWL pueda aplicarlos con
        `record.update` sin llamadas extra al servidor.
        """
        self.ensure_one()
        payload = self._line_payload()
        if payload.get("warranty_type_id"):
            payload["warranty_type_id"] = [
                self.warranty_type_id.id,
                self.warranty_type_id.display_name or "",
            ]
        if payload.get("warranty_vendor_id"):
            payload["warranty_vendor_id"] = [
                self.warranty_vendor_id.id,
                self.warranty_vendor_id.display_name or "",
            ]
        return payload

    def get_line_values(self):
        """Devuelve al frontend los valores calculados por el wizard.

        Usado por el widget OWL cuando la línea aún no tiene id (`NewId`).
        """
        self.ensure_one()
        return self._frontend_payload()

    def action_apply(self):
        self.ensure_one()
        if not self.line_id:
            # Línea sin guardar: no podemos escribir, devolvemos los valores
            # como `infos` para que OWL los aplique con `record.update`.
            return {
                "type": "ir.actions.act_window_close",
                "infos": {
                    "applied": True,
                    "vals": self._frontend_payload(),
                },
            }
        line = self.env[self.line_model].browse(self.line_id).exists()
        if not line:
            raise ValidationError(_("La línea ya no existe."))
        line.write(self._line_payload())
        return {"type": "ir.actions.act_window_close"}

    def action_cancel(self):
        return {"type": "ir.actions.act_window_close"}
