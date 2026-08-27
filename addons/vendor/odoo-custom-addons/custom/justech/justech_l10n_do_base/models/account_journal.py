from odoo import fields, models


class AccountJournal(models.Model):
    _inherit = "account.journal"

    justech_do_use_ncf = fields.Boolean(
        string="Use NCF",
        help="Enable NCF assignment and validation on this journal.",
    )
    justech_do_document_type_ids = fields.Many2many(
        "justech.do.fiscal.document.type",
        string="Allowed Document Types",
    )
    justech_do_default_document_type_id = fields.Many2one(
        "justech.do.fiscal.document.type",
        string="Default Document Type",
        domain="[('id', 'in', justech_do_document_type_ids)]",
    )
