from odoo import fields, models


class DxSalePrintWizard(models.TransientModel):
    _name = "dx.sale.print.wizard"
    _description = "Imprimir cotización o pedido"

    order_id = fields.Many2one("sale.order", required=True, ondelete="cascade")

    def action_print_quotation(self):
        self.ensure_one()
        return self.env.ref("sale.action_report_saleorder").report_action(self.order_id)

    def action_print_proforma(self):
        self.ensure_one()
        return self.env.ref("sale.action_report_pro_forma_invoice").report_action(
            self.order_id
        )

    def action_print_propet(self):
        self.ensure_one()
        return self.env.ref(
            "justech_alexander_reports.action_report_saleorder_propet"
        ).report_action(self.order_id)


class SaleOrderPrintMenu(models.Model):
    _inherit = "sale.order"

    def action_dx_print_formats(self):
        """Single Imprimir entry. Formats stay reports, not header shortcuts."""
        self.ensure_one()
        wizard = self.env["dx.sale.print.wizard"].create({"order_id": self.id})
        return {
            "type": "ir.actions.act_window",
            "name": "Imprimir",
            "res_model": "dx.sale.print.wizard",
            "res_id": wizard.id,
            "view_mode": "form",
            "target": "new",
        }


class DxInvoicePrintWizard(models.TransientModel):
    _name = "dx.invoice.print.wizard"
    _description = "Imprimir factura"

    move_id = fields.Many2one("account.move", required=True, ondelete="cascade")

    def action_print_propet(self):
        self.ensure_one()
        return self.env.ref(
            "justech_alexander_reports.action_report_invoice_propet"
        ).report_action(self.move_id)


class AccountMovePrintMenu(models.Model):
    _inherit = "account.move"

    def action_dx_print_formats(self):
        """Invoice Imprimir only lists formats that apply to account.move."""
        self.ensure_one()
        wizard = self.env["dx.invoice.print.wizard"].create({"move_id": self.id})
        return {
            "type": "ir.actions.act_window",
            "name": "Imprimir",
            "res_model": "dx.invoice.print.wizard",
            "res_id": wizard.id,
            "view_mode": "form",
            "target": "new",
        }
