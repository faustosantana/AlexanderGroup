# -*- coding: utf-8 -*-
import json

from odoo import _, api, fields, models


class JustechWarrantyLineMixin(models.AbstractModel):
    """Lógica compartida de garantía en líneas de venta/factura.

    RC6.2: la configuración de garantía puede realizarse *antes* de guardar la
    cotización/factura (líneas con `NewId`), por lo que el marcador
    `warranty_config_btn` debe habilitar el botón en cuanto exista producto.
    """

    _name = "justech.warranty.line.mixin"
    _description = "Mixin garantía por línea"

    warranty_notes = fields.Text(
        string="Condiciones / observaciones",
        help="Notas de la condición de garantía para esta línea.",
    )
    warranty_summary = fields.Char(
        string="Resumen garantía",
        compute="_compute_warranty_summary",
        store=True,
        readonly=True,
    )
    warranty_status = fields.Selection(
        [
            ("none", "Sin garantía"),
            ("pending", "Pendiente"),
            ("configured", "Configurada"),
        ],
        string="Estado garantía",
        compute="_compute_warranty_status",
    )
    warranty_config_btn = fields.Char(
        string="Garantía",
        compute="_compute_warranty_config_btn",
    )

    # Nuevos campos RC6.2 en la línea comercial
    warranty_expected_units = fields.Integer(
        string="Unidades esperadas",
        default=0,
        help="Unidades individuales que se planifican como unidades de garantía "
        "distintas (por defecto se toma de la cantidad de la línea).",
    )
    warranty_vendor_id = fields.Many2one(
        "res.partner",
        string="Proveedor de la garantía",
        help="Proveedor/fabricante que respalda la cobertura (opcional).",
    )
    warranty_planned_serials = fields.Text(
        string="Seriales planificados",
        help="Uno por línea. Se usan al generar unidades de garantía al postear "
        "la factura. Formato libre: cada renglón corresponde a una unidad.",
    )
    warranty_units_label = fields.Char(
        string="Unidades/seriales",
        compute="_compute_warranty_units_label",
    )

    SECTION_DISPLAY_TYPES = frozenset({"line_section", "line_note", "line_subsection"})

    @classmethod
    def _is_warranty_product_line(cls, display_type):
        if not display_type or display_type == "product":
            return True
        return display_type not in cls.SECTION_DISPLAY_TYPES

    @api.depends("product_id", "display_type")
    def _compute_warranty_config_btn(self):
        """El botón se habilita en cuanto hay producto (aunque la línea no esté
        guardada). Cuando existe id numérico lo exponemos; para `NewId` usamos
        el marcador ``"draft"`` para que el widget OWL abra el diálogo local
        sin llamar al servidor con un id inválido.
        """
        for line in self:
            if not line._is_warranty_product_line(line.display_type) or not line.product_id:
                line.warranty_config_btn = ""
            elif line.id and isinstance(line.id, int):
                line.warranty_config_btn = str(line.id)
            else:
                line.warranty_config_btn = "draft"

    @api.depends("warranty_apply", "warranty_months", "display_type", "product_id")
    def _compute_warranty_status(self):
        for line in self:
            if not line._is_warranty_product_line(line.display_type) or not line.product_id:
                line.warranty_status = False
            elif not line.warranty_apply:
                line.warranty_status = "none"
            elif line.warranty_months <= 0:
                line.warranty_status = "pending"
            else:
                line.warranty_status = "configured"

    @api.depends("warranty_apply", "warranty_months", "warranty_type_id")
    def _compute_warranty_summary(self):
        for line in self:
            if not line.warranty_apply:
                line.warranty_summary = ""
                continue
            if line.warranty_months <= 0:
                line.warranty_summary = _("Pendiente")
                continue
            type_label = line.warranty_type_id.name if line.warranty_type_id else _("Estándar")
            short = type_label.split()[0] if type_label else _("Estándar")
            line.warranty_summary = f"{line.warranty_months}m · {short}"

    @api.depends(
        "warranty_apply",
        "warranty_expected_units",
        "warranty_planned_serials",
    )
    def _compute_warranty_units_label(self):
        for line in self:
            if not line.warranty_apply:
                line.warranty_units_label = ""
                continue
            expected = line.warranty_expected_units or int(
                getattr(line, "product_uom_qty", 0) or getattr(line, "quantity", 0) or 0
            )
            configured = len(line._parse_planned_serials())
            line.warranty_units_label = _(
                "Unidades/seriales: %(configured)s de %(expected)s"
            ) % {"configured": configured, "expected": expected}

    def _parse_planned_serials(self):
        """Devuelve la lista de descripciones/seriales planificados de la línea.

        Acepta dos formatos:
          * JSON list de dicts ``[{unit_number, serial_manufacturer, note}]``.
          * Texto plano (un serial por renglón). Los renglones vacíos se ignoran.
        """
        self.ensure_one()
        raw = self.warranty_planned_serials or ""
        raw = raw.strip()
        if not raw:
            return []
        if raw.startswith("[") or raw.startswith("{"):
            try:
                data = json.loads(raw)
                if isinstance(data, dict):
                    data = [data]
                if isinstance(data, list):
                    return [item for item in data if item]
            except (ValueError, TypeError):
                pass
        result = []
        for idx, chunk in enumerate(raw.splitlines(), start=1):
            serial = chunk.strip()
            if not serial:
                continue
            result.append({"unit_number": idx, "serial_manufacturer": serial})
        return result

    def _warranty_default_values(self):
        self.ensure_one()
        if not self.product_id:
            return {}
        values = {}
        if not self.warranty_months or self.warranty_months <= 0:
            months = self.product_id._get_warranty_months()
            values["warranty_months"] = months if months > 0 else 12
        product_type = getattr(self.product_id, "warranty_type_id", False)
        if not self.warranty_type_id and product_type:
            values["warranty_type_id"] = product_type.id
        if not self.warranty_expected_units:
            qty = int(getattr(self, "product_uom_qty", 0) or getattr(self, "quantity", 0) or 0)
            values["warranty_expected_units"] = max(qty, 1)
        return values

    def _clear_warranty_details(self):
        self.write(
            {
                "warranty_months": 0,
                "warranty_type_id": False,
                "warranty_notes": False,
                "warranty_expected_units": 0,
                "warranty_vendor_id": False,
                "warranty_planned_serials": False,
            }
        )

    def _apply_warranty_product_defaults(self):
        """Precarga meses/tipo desde el producto (persistido)."""
        for line in self:
            values = line._warranty_default_values()
            if values:
                line.write(values)

    def _apply_warranty_product_defaults_onchange(self):
        """Precarga meses/tipo en memoria (onchange / UI)."""
        self.ensure_one()
        values = self._warranty_default_values()
        for field, value in values.items():
            setattr(self, field, value)

    @api.onchange("warranty_apply")
    def _onchange_warranty_apply(self):
        if not self.warranty_apply:
            self.warranty_months = 0
            self.warranty_type_id = False
            self.warranty_notes = False
            self.warranty_expected_units = 0
            self.warranty_planned_serials = False
            return
        self._apply_warranty_product_defaults_onchange()

    def action_open_warranty_config_wizard(self):
        """Método invocado desde botones de vista (línea ya guardada)."""
        self.ensure_one()
        if self.display_type and not self._is_warranty_product_line(self.display_type):
            return False
        action = self.env["ir.actions.act_window"]._for_xml_id(
            "justech_warranty.action_warranty_line_config_wizard"
        )
        action = dict(action)
        action["context"] = dict(
            self.env.context,
            default_line_model=self._name,
            default_line_id=self.id or 0,
            default_product_id=self.product_id.id,
            default_warranty_apply=self.warranty_apply,
            default_warranty_months=self.warranty_months,
            default_warranty_type_id=self.warranty_type_id.id or False,
            default_warranty_notes=self.warranty_notes or False,
            default_warranty_expected_units=self.warranty_expected_units
            or int(getattr(self, "product_uom_qty", 0) or getattr(self, "quantity", 0) or 1),
            default_warranty_vendor_id=self.warranty_vendor_id.id or False,
            default_warranty_planned_serials=self.warranty_planned_serials or False,
            dialog_size="extra-large",
        )
        return action
