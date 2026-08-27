from odoo import fields, models


class JustechModule(models.Model):
    _name = "justech.module"
    _description = "Justech Module Catalog Entry"
    _order = "code"

    code = fields.Char(required=True, index=True)
    name = fields.Char(required=True, translate=True)
    description = fields.Text(translate=True)
    version = fields.Char()
    category = fields.Selection(
        [
            ("platform", "Platform"),
            ("fiscal", "Fiscal"),
            ("reports", "Reports"),
            ("payments", "Payments"),
            ("treasury", "Treasury"),
            ("audit", "Audit"),
            ("pos", "POS"),
            ("integration", "Integration"),
            ("integrations", "Integrations"),
            ("accounting", "Accounting"),
            ("inventory", "Inventory"),
            ("ux", "UX"),
            ("other", "Other"),
        ],
        default="platform",
    )
    country = fields.Char(help="ISO country code, e.g. DO")
    localization = fields.Char(help="Localization package code")
    required_module = fields.Boolean(
        default=False,
        help="Mandatory module for a standard Hellenia deployment",
    )
    license_required = fields.Boolean(default=True)
    tier_minimum = fields.Selection(
        [
            ("TRIAL", "Trial"),
            ("STD", "Standard"),
            ("PRO", "Professional"),
            ("ENT", "Enterprise"),
        ],
        default="STD",
    )
    ir_module_id = fields.Many2one("ir.module.module", string="Odoo Module", index=True)
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("registered", "Registered"),
            ("deprecated", "Deprecated"),
        ],
        default="registered",
    )
    feature_ids = fields.One2many("justech.feature", "module_id", string="Features")
    dependency_ids = fields.One2many(
        "justech.module.dependency",
        "module_id",
        string="Dependencies",
    )

    _code_unique = models.Constraint(
        "UNIQUE(code)",
        "Module code must be unique.",
    )
