from email.utils import parseaddr

from odoo import models
from odoo.addons.base.models.ir_mail_server import MailDeliveryException

from .catalog import all_domains, belongs_to_domain, domain_of


class IrMailServer(models.Model):
    _inherit = "ir.mail_server"

    def send_email(self, message, *args, **kwargs):
        from_addr = parseaddr(message.get("From") or "")[1]
        domain = domain_of(from_addr)
        mapped = domain in all_domains()
        client = self.env["dx.ms.graph.client"]
        if mapped:
            company = self.env["res.company"]._dx_company_for_email(from_addr)
            if not company:
                raise MailDeliveryException(
                    "Microsoft Mail",
                    "No hay empresa Doralex para el dominio de envío.",
                )
            if not belongs_to_domain(from_addr, company.dx_mail_domain):
                raise MailDeliveryException(
                    "Microsoft Mail",
                    "Aislamiento multiempresa: el remitente no coincide con la empresa.",
                )
            if not client.configured():
                raise MailDeliveryException(
                    "Microsoft Mail",
                    "Credenciales Microsoft no disponibles en este entorno.",
                )
            return client.send_email_message(
                message, company.dx_mail_mailbox, from_addr
            )
        return super().send_email(message, *args, **kwargs)
