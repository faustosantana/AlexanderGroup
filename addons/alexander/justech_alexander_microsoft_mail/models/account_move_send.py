from odoo import api, fields, models


class AccountMoveSend(models.AbstractModel):
    _inherit = "account.move.send"

    def _send_mail(self, move, mail_template, **kwargs):
        company = move.company_id
        if company and company.dx_mail_domain:
            addr = company._dx_outgoing_address()
            if addr:
                kwargs["email_from"] = addr
                kwargs["reply_to"] = addr
        return super()._send_mail(move, mail_template, **kwargs)


class AccountMoveSendWizard(models.TransientModel):
    _inherit = "account.move.send.wizard"

    dx_email_from = fields.Char(
        string="From", compute="_compute_dx_mail_identity", readonly=True
    )
    dx_reply_to = fields.Char(
        string="Reply-To", compute="_compute_dx_mail_identity", readonly=True
    )

    @api.depends("move_id", "company_id")
    def _compute_dx_mail_identity(self):
        for wizard in self:
            addr = ""
            move = wizard.move_id
            company = move.company_id if move else wizard.company_id
            if company and company.dx_mail_domain:
                addr = company._dx_outgoing_address()
            wizard.dx_email_from = addr
            wizard.dx_reply_to = addr
