from odoo import api, fields, models


class JustechCommercialProduct(models.Model):
    _name = "justech.commercial.product"
    _description = "Justech Commercial Product Catalog"
    _order = "commercial_group, sequence, name"

    code = fields.Char(required=True, index=True)
    name = fields.Char(required=True)
    description = fields.Text()
    icon = fields.Char(default="fa-cube")
    commercial_icon_display = fields.Char(
        string="Icono comercial",
        help="Emoji o símbolo mostrado en el catálogo de licencias.",
    )
    is_justech_licensable = fields.Boolean(
        string="Licenciable por Justech",
        default=False,
        index=True,
        help="Solo productos marcados aparecen en el catálogo comercial de licencias.",
    )
    commercial_group = fields.Selection(
        [
            ("fiscal", "Fiscal"),
            ("commercial", "Comercial"),
            ("productivity", "Productividad"),
            ("integrations", "Integraciones"),
            ("customizations", "Personalizaciones"),
            ("platform", "Plataforma"),
        ],
        string="Grupo comercial",
        default="fiscal",
        index=True,
    )
    category = fields.Selection(
        [
            ("fiscal", "Fiscal"),
            ("sales", "Ventas"),
            ("purchase", "Compras"),
            ("inventory", "Inventario"),
            ("pos", "Punto de Venta"),
            ("crm", "CRM"),
            ("reports", "Reportes"),
            ("assets", "Activos"),
            ("hr", "RRHH"),
            ("platform", "Plataforma"),
            ("integration", "Integración"),
            ("ai", "Inteligencia Artificial"),
        ],
        default="fiscal",
    )
    sequence = fields.Integer(default=10)
    version_display = fields.Char(string="Version Display")
    license_tier = fields.Selection(
        [("included", "Incluido"), ("std", "Standard"), ("pro", "Professional"), ("ent", "Enterprise")],
        default="ent",
    )
    active = fields.Boolean(default=True)
    line_ids = fields.One2many("justech.commercial.product.line", "product_id")
    module_map_ids = fields.One2many("justech.commercial.product.module", "product_id")

    _justech_commercial_product_code_uniq = models.Constraint(
        "UNIQUE(code)",
        "Commercial product code must be unique.",
    )

    _LICENSE_CATALOG_SYNC = {
        "contabilidad_rd": {
            "is_justech_licensable": True,
            "commercial_group": "fiscal",
            "name": "Contabilidad Dominicana",
            "commercial_icon_display": "📊",
        },
        "comprobantes_fiscales": {
            "is_justech_licensable": True,
            "commercial_group": "fiscal",
            "name": "Comprobantes Fiscales DGII",
            "commercial_icon_display": "📄",
        },
        "ux_fiscal": {
            "is_justech_licensable": True,
            "commercial_group": "fiscal",
            "name": "Experiencia Fiscal RD",
            "commercial_icon_display": "🧾",
        },
        "reportes_corporativos": {
            "is_justech_licensable": True,
            "commercial_group": "customizations",
            "commercial_icon_display": "📑",
        },
        "punto_de_venta": {
            "is_justech_licensable": True,
            "commercial_group": "commercial",
            "name": "Punto de Venta Fiscal Justech",
            "commercial_icon_display": "🛒",
        },
        "ventas": {"is_justech_licensable": False},
        "compras": {"is_justech_licensable": False},
        "crm": {"is_justech_licensable": False},
        "inventario": {"is_justech_licensable": False},
        "activos_fijos": {"is_justech_licensable": False},
        "rrhh": {"is_justech_licensable": False},
        "marketplace": {"is_justech_licensable": False},
        "ia": {"is_justech_licensable": False},
    }

    @api.model
    def sync_license_catalog_flags(self):
        """Apply licensable flags to legacy catalog rows (safe on every upgrade)."""
        for product in self.sudo().search([]):
            patch = self._LICENSE_CATALOG_SYNC.get(product.code)
            if patch:
                product.write(patch)
        return True


class JustechCommercialProductLine(models.Model):
    _name = "justech.commercial.product.line"
    _description = "Commercial Product Feature Line"
    _order = "sequence, commercial_name"

    product_id = fields.Many2one(
        "justech.commercial.product", required=True, ondelete="cascade", index=True
    )
    commercial_name = fields.Char(required=True)
    description = fields.Char()
    feature_code = fields.Char(required=True, index=True)
    sequence = fields.Integer(default=10)
    icon = fields.Char(default="fa-check-circle")


class JustechCommercialProductModule(models.Model):
    _name = "justech.commercial.product.module"
    _description = "Commercial Product Technical Module Mapping"

    product_id = fields.Many2one(
        "justech.commercial.product", required=True, ondelete="cascade", index=True
    )
    technical_module_code = fields.Char(required=True, index=True)
