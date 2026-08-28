from odoo import models


class MailThread(models.AbstractModel):
    _inherit = "mail.thread"

    def _dx_document_company(self):
        self.ensure_one()
        if "company_id" in self._fields and self.company_id:
            return self.company_id
        return self.env["res.company"]

    def _message_compute_author(self, author_id=None, email_from=None):
        author_id, email_from = super()._message_compute_author(
            author_id=author_id, email_from=email_from
        )
        if len(self) == 1:
            company = self._dx_document_company()
            addr = company._dx_outgoing_address() if company else ""
            if addr:
                email_from = addr
        return author_id, email_from


class Base(models.AbstractModel):
    _inherit = "base"

    def _notify_get_reply_to(self, default=None, author_id=False):
        result = super()._notify_get_reply_to(default=default, author_id=author_id)
        if not self or "company_id" not in self._fields:
            return result
        for record in self:
            company = record.company_id
            addr = company._dx_outgoing_address() if company else ""
            if addr:
                result[record.id] = record._notify_get_reply_to_formatted_email(
                    addr, author_id=author_id
                )
        return result
