# -*- coding: utf-8 -*-
from odoo import _, api, fields, models

from .cost_link import COST_USAGE

TRACE_METHODS = [
    ("purchase_line", "Línea de compra (factura → OC → venta)"),
    ("procurement", "Grupo de aprovisionamiento"),
    ("origin", "Origen de la OC"),
    ("product_qty_company", "Producto + cantidad + compañía"),
    ("ref", "Referencia cruzada"),
    ("analytic", "Cuenta analítica"),
    ("heuristic", "Heurística general"),
]

RULE_TYPES = [
    ("trace_priority", "Prioridad de trazabilidad"),
    ("classification", "Clasificación de costo"),
    ("prorate_default", "Prorrateo por defecto"),
]


class PurchaseSaleReconciliationRule(models.Model):
    _name = "purchase.sale.reconciliation.rule"
    _description = "Regla de conciliación / clasificación compra-venta"
    _order = "sequence, id"
    _check_company_auto = True

    name = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        "res.company", default=lambda self: self.env.company, index=True
    )
    rule_type = fields.Selection(RULE_TYPES, required=True, default="classification")

    trace_method = fields.Selection(TRACE_METHODS, string="Método de trazabilidad")

    product_categ_ids = fields.Many2many(
        "product.category", string="Categorías de producto aplicables"
    )
    product_ids = fields.Many2many("product.product", string="Productos aplicables")
    partner_ids = fields.Many2many("res.partner", string="Proveedores aplicables")

    cost_usage_type = fields.Selection(COST_USAGE, string="Clasificación objetivo")
    min_confidence = fields.Integer(string="Confianza mínima", default=0)
    max_confidence = fields.Integer(string="Confianza máxima", default=100)
    auto_confirm = fields.Boolean(
        string="Auto-confirmar si ≥90 y sin ambigüedad", default=False
    )

    notes = fields.Text(string="Notas")

    def matches_purchase_line(self, purchase_line):
        """Return True if this rule applies to a given purchase.order.line."""
        self.ensure_one()
        if not self.active:
            return False
        if self.company_id and purchase_line.company_id != self.company_id:
            return False
        if self.product_ids and purchase_line.product_id not in self.product_ids:
            return False
        if (
            self.product_categ_ids
            and purchase_line.product_id.categ_id not in self.product_categ_ids
        ):
            return False
        if self.partner_ids and purchase_line.order_id.partner_id not in self.partner_ids:
            return False
        return True

    @api.model
    def get_classification_rules(self, company):
        return self.search(
            [
                ("rule_type", "=", "classification"),
                ("active", "=", True),
                "|",
                ("company_id", "=", False),
                ("company_id", "=", company.id),
            ]
        )

    @api.model
    def get_trace_priority(self, company):
        """Return the ordered list of trace_method codes configured for the company,
        falling back to the audit-approved default order."""
        rules = self.search(
            [
                ("rule_type", "=", "trace_priority"),
                ("active", "=", True),
                ("trace_method", "!=", False),
                "|",
                ("company_id", "=", False),
                ("company_id", "=", company.id),
            ],
            order="sequence, id",
        )
        methods = rules.mapped("trace_method")
        default_order = [code for code, _label in TRACE_METHODS]
        for code in default_order:
            if code not in methods:
                methods.append(code)
        return methods
