from email.utils import parseaddr

from odoo import models

from .catalog import belongs_to_domain


class MailMail(models.Model):
    _inherit = "mail.mail"

    def _dx_related_company(self):
        self.ensure_one()
        if not self.exists():
            return self.env["res.company"]
        if self.model and self.res_id:
            record = self.env[self.model].sudo().browse(self.res_id)
            if record.exists() and "company_id" in record._fields and record.company_id:
                return record.company_id
        from_addr = parseaddr(self.email_from or "")[1]
        return self.env["res.company"]._dx_company_for_email(from_addr)

    def _dx_apply_company_from(self):
        for mail in self.exists():
            company = mail._dx_related_company()
            if not company or not company.dx_mail_domain:
                continue
            role = company._dx_role_for_document(mail.model, mail.res_id)
            address = company._dx_address_for_role(role)
            if not address or not belongs_to_domain(address, company.dx_mail_domain):
                continue
            mail.email_from = address
            mail.reply_to = address

    def _dx_uses_graph(self):
        self.ensure_one()
        if not self.exists():
            return False
        from_addr = parseaddr(self.email_from or "")[1]
        company = self.env["res.company"]._dx_company_for_email(from_addr)
        return bool(company and company.dx_mail_mailbox)

    def send(self, auto_commit=False, raise_exception=False, post_send_callback=None):
        self = self.exists()
        if not self:
            return True
        self._dx_apply_company_from()
        graph = self.filtered(lambda mail: mail._dx_uses_graph())
        smtp = self - graph
        for mail in graph:
            mail._send(
                auto_commit=auto_commit,
                raise_exception=raise_exception,
                smtp_session=None,
                post_send_callback=post_send_callback,
            )
        if smtp:
            super(MailMail, smtp).send(
                auto_commit=auto_commit,
                raise_exception=raise_exception,
                post_send_callback=post_send_callback,
            )
        return True
