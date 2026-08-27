"""Campos DGII 623 — retenciones del Estado en facturas."""
from odoo import fields, models

GOV_TAX_NAME = "-5% ISR Gov."


class AccountMoveGov623(models.Model):
    _inherit = "account.move"

    justech_do_gov_withholding_amount = fields.Float(
        string="Retención 5% Gobierno (623)",
        digits=(16, 2),
        copy=False,
        help="Monto retenido por entidad del Estado para el formato 623.",
    )
    justech_do_gov_retention_date = fields.Date(
        string="Fecha retención Gobierno (623)",
        copy=False,
    )
    justech_do_gov_retention_ref = fields.Char(
        string="Referencia pago Gobierno (623)",
        copy=False,
        help="Número de cheque, transferencia o comprobante de pago.",
    )
    justech_do_gov_retention_ref_type = fields.Selection(
        selection=[
            ("1", "Cheque"),
            ("2", "Transferencia/Depósito"),
        ],
        string="Tipo referencia Gobierno (623)",
        copy=False,
    )
    justech_do_gov_retention_bank_id = fields.Many2one(
        "res.bank",
        string="Banco retención Gobierno (623)",
        copy=False,
    )

    def _justech_sync_gov_withholding_from_tax(self):
        Tax = self.env["account.tax"]
        for move in self.filtered(
            lambda m: m.state == "posted" and m.move_type == "out_invoice"
        ):
            if move.justech_do_gov_withholding_amount:
                continue
            gov_tax = Tax.search(
                [
                    ("name", "=", GOV_TAX_NAME),
                    ("type_tax_use", "=", "sale"),
                    ("company_id", "=", move.company_id.id),
                ],
                limit=1,
            )
            if not gov_tax:
                continue
            wh_lines = move.line_ids.filtered(lambda l: l.tax_line_id == gov_tax)
            amount = sum(abs(line.balance) for line in wh_lines)
            if amount:
                move.justech_do_gov_withholding_amount = amount
                if not move.justech_do_gov_retention_date:
                    move.justech_do_gov_retention_date = move.invoice_date

    def action_post(self):
        res = super().action_post()
        self._justech_sync_gov_withholding_from_tax()
        return res
