from odoo import api, fields, models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    justech_do_document_type_id = fields.Many2one(
        "justech.do.fiscal.document.type",
        string="Tipo de comprobante fiscal",
        domain="[('is_sale_document', '=', True), ('move_type', '=', 'out_invoice')]",
        help="Tipo de comprobante sugerido para la factura de esta cotización.",
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("justech_do_document_type_id") and vals.get("partner_id"):
                partner = self.env["res.partner"].browse(vals["partner_id"])
                doc = partner.justech_do_get_default_sale_document_type()
                if doc:
                    vals["justech_do_document_type_id"] = doc.id
        return super().create(vals_list)

    def write(self, vals):
        if vals.get("partner_id") and "justech_do_document_type_id" not in vals:
            partner = self.env["res.partner"].browse(vals["partner_id"])
            doc = partner.justech_do_get_default_sale_document_type()
            vals["justech_do_document_type_id"] = doc.id if doc else False
        return super().write(vals)

    @api.onchange("partner_id")
    def _onchange_partner_justech_do_document_type(self):
        if not self.partner_id:
            self.justech_do_document_type_id = False
            return
        doc = self.partner_id.justech_do_get_default_sale_document_type()
        self.justech_do_document_type_id = doc

    def _prepare_invoice(self):
        invoice_vals = super()._prepare_invoice()
        if self.justech_do_document_type_id:
            invoice_vals["justech_do_document_type_id"] = self.justech_do_document_type_id.id
        return invoice_vals
