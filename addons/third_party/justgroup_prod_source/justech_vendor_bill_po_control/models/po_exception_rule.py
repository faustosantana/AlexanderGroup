# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


CLASSIFICATION_SELECTION = [
    ("resale", "Reventa"),
    ("inventory", "Inventario"),
    ("project", "Proyecto"),
    ("admin", "Gasto administrativo"),
    ("bank", "Gasto bancario"),
    ("rent", "Alquiler"),
    ("utilities", "Servicios públicos"),
    ("tax", "Impuestos"),
    ("asset", "Activo"),
    ("internal", "Servicio interno"),
    ("insurance", "Seguro"),
    ("telecom", "Telecomunicaciones"),
    ("customs", "Aduana"),
    ("logistics", "Logística"),
    ("other", "Otro"),
]

APPROVAL_LEVEL_SELECTION = [
    ("none", "Sin aprobación adicional"),
    ("finance", "Finanzas"),
    ("management", "Gerencia"),
    ("dual", "Doble aprobación (Finanzas + Gerencia)"),
]


class JustechVendorBillPoExceptionRule(models.Model):
    _name = "justech.vendor.bill.po.exception.rule"
    _description = "Regla de excepción / política OC en facturas proveedor"
    _order = "sequence, id"

    name = fields.Char(required=True)
    active = fields.Boolean(default=True)
    sequence = fields.Integer(default=10)
    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    exception_category = fields.Selection(
        [
            ("admin", "Gastos administrativos"),
            ("utilities", "Servicios públicos"),
            ("telecom", "Internet y telecomunicaciones"),
            ("rent", "Alquileres"),
            ("tax", "Impuestos y tasas"),
            ("fees", "Honorarios"),
            ("bank", "Cargos bancarios"),
            ("payroll", "Nómina"),
            ("asset", "Activos"),
            ("internal", "Servicios internos"),
            ("customs", "Importaciones y aduanas"),
            ("other", "Otras categorías aprobadas"),
        ],
        string="Tipo de excepción",
        required=True,
        default="admin",
    )
    classification = fields.Selection(
        [
            ("resale", "Reventa"),
            ("inventory", "Inventario"),
            ("project", "Proyecto"),
            ("admin", "Gasto administrativo"),
            ("bank", "Gasto bancario"),
            ("rent", "Alquiler"),
            ("utilities", "Servicios públicos"),
            ("tax", "Impuestos"),
            ("asset", "Activo"),
            ("internal", "Servicio interno"),
            ("insurance", "Seguro"),
            ("telecom", "Telecomunicaciones"),
            ("customs", "Aduana"),
            ("logistics", "Logística"),
            ("other", "Otro"),
        ],
        string="Clasificación (legado)",
        help="Legado. Preferir Tipo de costos y gastos (expense_type_id).",
    )
    expense_type_id = fields.Many2one(
        "justech.do.dgii.expense.type",
        string="Tipo de costos y gastos",
        help="Filtro opcional sobre el campo fiscal existente. No permite evadir OC.",
    )
    partner_id = fields.Many2one("res.partner", string="Proveedor")
    product_id = fields.Many2one("product.product", string="Producto")
    product_categ_id = fields.Many2one("product.category", string="Categoría de producto")
    account_id = fields.Many2one("account.account", string="Cuenta contable")
    journal_id = fields.Many2one("account.journal", string="Diario")
    requires_purchase_order = fields.Boolean(
        string="Exige OC",
        default=False,
        help="Si False, la factura puede no tener OC (excepción configurada).",
    )
    requires_approval = fields.Boolean(
        string="Requiere validación",
        default=True,
        help="Aunque no exija OC, puede requerir aprobación de Finanzas/Gerencia.",
    )
    approval_level = fields.Selection(
        APPROVAL_LEVEL_SELECTION,
        string="Nivel de aprobación",
        default="finance",
    )
    require_attachment = fields.Boolean(string="Exige soporte adjunto", default=False)
    amount_min = fields.Float(string="Monto mínimo (compañía)", default=0.0)
    amount_max = fields.Float(
        string="Monto máximo (compañía)",
        default=0.0,
        help="0 = sin tope superior.",
    )
    notes = fields.Char(string="Notas")

    @api.constrains(
        "partner_id",
        "product_id",
        "product_categ_id",
        "account_id",
        "journal_id",
        "classification",
        "expense_type_id",
    )
    def _check_has_filter(self):
        for rule in self:
            if not any(
                [
                    rule.partner_id,
                    rule.product_id,
                    rule.product_categ_id,
                    rule.account_id,
                    rule.journal_id,
                    rule.classification,
                    rule.expense_type_id,
                ]
            ):
                raise ValidationError(
                    _(
                        "La regla %(name)s debe tener al menos un filtro "
                        "(tipo de costos y gastos, proveedor, producto, categoría, cuenta o diario).",
                        name=rule.name,
                    )
                )

    @api.model
    def _rule_matches_move(self, rule, move):
        if rule.company_id and rule.company_id != move.company_id:
            return False
        if rule.expense_type_id:
            move_exp = (
                move.justech_do_expense_type_id
                if "justech_do_expense_type_id" in move._fields
                else False
            )
            if not move_exp or move_exp != rule.expense_type_id:
                return False
        if rule.classification and getattr(move, "vendor_bill_classification", False) != rule.classification:
            return False
        if rule.partner_id:
            commercial = move.partner_id.commercial_partner_id
            if rule.partner_id not in (move.partner_id, commercial):
                return False
        if rule.journal_id and rule.journal_id != move.journal_id:
            return False
        lines = move.invoice_line_ids
        if rule.product_id and not lines.filtered(lambda l: l.product_id == rule.product_id):
            return False
        if rule.product_categ_id and not lines.filtered(
            lambda l: l.product_id and l.product_id.categ_id == rule.product_categ_id
        ):
            return False
        if rule.account_id and not lines.filtered(lambda l: l.account_id == rule.account_id):
            return False
        amount = abs(move.amount_total_signed or move.amount_total or 0.0)
        if rule.amount_min and amount < rule.amount_min:
            return False
        if rule.amount_max and amount > rule.amount_max:
            return False
        if not any(
            [
                rule.partner_id,
                rule.product_id,
                rule.product_categ_id,
                rule.account_id,
                rule.journal_id,
                rule.classification,
                rule.expense_type_id,
            ]
        ):
            return False
        return True

    @api.model
    def find_matching_rule(self, move):
        rules = self.search(
            [
                ("active", "=", True),
                ("company_id", "=", move.company_id.id),
            ]
        )
        for rule in rules:
            if self._rule_matches_move(rule, move):
                return rule
        return self.browse()
