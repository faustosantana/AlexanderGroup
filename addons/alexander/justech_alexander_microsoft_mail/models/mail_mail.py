from email.utils import parseaddr

from odoo import models

from .catalog import belongs_to_domain


class MailMail(models.Model):
    _inherit = "mail.mail"

    def _dx_related_company(self):
        self.ensure_one()
        if self.model and self.res_id:
            record = self.env[self.model].sudo().browse(self.res_id)
            if record.exists() and "company_id" in record._fields and record.company_id:
                return record.company_id
        return self.env["res.company"]

    def _dx_apply_company_from(self):
        for mail in self:
            company = mail._dx_related_company()
            if not company or not company.dx_mail_domain:
                continue
            role = company._dx_role_for_document(mail.model, mail.res_id)
            address = company._dx_address_for_role(role)
            if not address:
                continue
            current = parseaddr(mail.email_from or "")[1]
            if current and not belongs_to_domain(current, company.dx_mail_domain):
                current = ""
            if not current or current.lower() != address.lower():
                mail.email_from = address
            if not mail.reply_to or not belongs_to_domain(
                parseaddr(mail.reply_to)[1], company.dx_mail_domain
            ):
                mail.reply_to = address

    def send(self, auto_commit=False, raise_exception=False, post_send_callback=None):
        self._dx_apply_company_from()
        return super().send(
            auto_commit=auto_commit,
            raise_exception=raise_exception,
            post_send_callback=post_send_callback,
        )
