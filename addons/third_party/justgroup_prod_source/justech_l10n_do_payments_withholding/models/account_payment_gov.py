"""Stamp campos DGII 623 desde retenciones Justech — sin dependencia Hellenia."""
from odoo import fields, models

GOV_CATALOG_CODES = ("RET-GOB-5", "wh_isr_gov", "RET5%")


class AccountPaymentGov623Justech(models.Model):
    _inherit = "account.payment"

    justech_do_gov_withholding_catalog_id = fields.Many2one(
        "justech.do.withholding.catalog",
        string="Catálogo retención Gobierno",
        copy=False,
    )

    def _justech_stamp_gov_from_withholding(self):
        for pay in self:
            gov_lines = pay.justech_withholding_line_ids.filtered(
                lambda w: w.amount
                and (
                    getattr(w, "affects_623", False)
                    or (w.catalog_id and w.catalog_id.code in GOV_CATALOG_CODES)
                )
            )
            if not gov_lines:
                continue
            amount = sum(gov_lines.mapped("amount"))
            ref = pay.justech_check_number or pay.justech_payment_reference or pay.name or ""
            ref_type = "1" if pay.justech_check_number else "2"
            pay.write(
                {
                    "justech_do_gov_withholding_amount": amount,
                    "justech_do_gov_withholding_catalog_id": gov_lines[:1].catalog_id.id,
                }
            )
            move_vals = {
                "justech_do_gov_withholding_amount": amount,
                "justech_do_gov_retention_date": pay.date,
                "justech_do_gov_retention_ref": ref,
                "justech_do_gov_retention_ref_type": ref_type,
            }
            if pay.justech_check_bank_id:
                move_vals["justech_do_gov_retention_bank_id"] = pay.justech_check_bank_id.id
            moves = pay.reconciled_invoice_ids | pay.reconciled_bill_ids
            if not moves:
                moves = gov_lines.mapped("move_id")
            if moves:
                moves.write(move_vals)
