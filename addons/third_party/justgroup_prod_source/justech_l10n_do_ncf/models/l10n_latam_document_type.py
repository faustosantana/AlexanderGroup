"""Administración de documentos RECIBIDOS en Compras (catálogo LATAM)."""
from odoo import api, fields, models

_RECEIVED_PREFIXES = (
    "B01",
    "B02",
    "B03",
    "B04",
    "B14",
    "B15",
    "B16",
    "E31",
    "E32",
    "E33",
    "E34",
    "E41",
    "E43",
    "E44",
    "E45",
    "E46",
    "E47",
)


class L10nLatamDocumentType(models.Model):
    _inherit = "l10n_latam.document.type"

    justech_do_is_purchase_received = fields.Boolean(
        string="Recibido en Compras",
        compute="_compute_justech_do_received_admin",
    )
    justech_do_document_category = fields.Char(
        string="Categoría B / e-CF",
        compute="_compute_justech_do_received_admin",
    )
    justech_do_received_help = fields.Char(
        string="Ayuda funcional",
        compute="_compute_justech_do_received_admin",
    )
    justech_do_usage_count = fields.Integer(
        string="Documentos",
        compute="_compute_justech_do_usage_stats",
    )
    justech_do_last_used = fields.Datetime(
        string="Último uso",
        compute="_compute_justech_do_usage_stats",
    )
    justech_do_participates_606 = fields.Boolean(
        string="Participa en 606",
        compute="_compute_justech_do_received_admin",
    )

    @api.depends("doc_code_prefix", "name", "active")
    def _compute_justech_do_received_admin(self):
        received = set(_RECEIVED_PREFIXES)
        for rec in self:
            prefix = (rec.doc_code_prefix or "").strip().upper()
            is_recv = prefix in received
            rec.justech_do_is_purchase_received = is_recv
            if prefix.startswith("E"):
                rec.justech_do_document_category = "e-CF"
            elif prefix.startswith("B"):
                rec.justech_do_document_category = "B"
            else:
                rec.justech_do_document_category = False
            rec.justech_do_participates_606 = is_recv
            if is_recv:
                rec.justech_do_received_help = (
                    "Documento recibido del proveedor. El NCF se digita manualmente. "
                    "No consume rangos ni secuencias Justech. No es emisión desde Compras."
                )
            else:
                rec.justech_do_received_help = False

    def _compute_justech_do_usage_stats(self):
        Move = self.env["account.move"]
        for rec in self:
            domain = [
                ("l10n_latam_document_type_id", "=", rec.id),
                ("move_type", "in", ("in_invoice", "in_refund")),
            ]
            moves = Move.search(domain, order="write_date desc, id desc", limit=1)
            rec.justech_do_usage_count = Move.search_count(domain)
            rec.justech_do_last_used = moves.write_date if moves else False
