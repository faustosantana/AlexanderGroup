from odoo import models


class ResPartner(models.Model):
    _inherit = "res.partner"

    def _dx_statement_bundles(self, company=None):
        self.ensure_one()
        Move = self.env["account.move"].sudo()
        domain = [
            ("partner_id", "child_of", self.commercial_partner_id.id),
            ("move_type", "in", ("out_invoice", "out_refund")),
            ("state", "in", ("draft", "posted")),
        ]
        if company:
            domain.append(("company_id", "=", company.id))
        moves = Move.search(domain, order="company_id, invoice_date, id")
        bundles = []
        for co in moves.mapped("company_id"):
            docs = moves.filtered(lambda m, cid=co.id: m.company_id.id == cid)
            debit = sum(
                d.amount_residual_signed
                for d in docs.filtered(
                    lambda m: m.move_type == "out_invoice" and m.state == "posted"
                )
            )
            credit = sum(
                abs(d.amount_residual_signed)
                for d in docs.filtered(
                    lambda m: m.move_type == "out_refund" and m.state == "posted"
                )
            )
            bundles.append(
                {
                    "company": co,
                    "moves": docs,
                    "balance": debit - credit,
                }
            )
        return bundles
