"""Proveedor de tipos de comprobante fiscal."""
from odoo import models


class JustechDoDocumentTypeProvider(models.AbstractModel):
    _name = "justech.do.document.type.provider"
    _description = "Justech Fiscal Document Type Provider"

    def get_by_prefix(self, prefix, company=None):
        return self.env["justech.do.fiscal.document.type"].get_by_prefix(prefix, company)

    def format_ncf(self, document_type, sequence_number):
        return document_type.format_ncf(sequence_number)

    def parse_ncf(self, ncf):
        return self.env["justech.do.fiscal.document.type"].parse_ncf(ncf)

    def sale_prefixes(self):
        return self.env["justech.do.fiscal.document.type"].SALE_NCF_PREFIXES

    def purchase_prefixes(self):
        return self.env["justech.do.fiscal.document.type"].PURCHASE_NCF_PREFIXES
