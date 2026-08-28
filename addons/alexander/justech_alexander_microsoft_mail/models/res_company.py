from odoo import api, fields, models
from odoo.exceptions import ValidationError

from .catalog import (
    address_for,
    belongs_to_domain,
    domain_of,
    profile_for_code,
    profile_for_company_name,
    role_for_model,
)


class ResCompany(models.Model):
    _inherit = "res.company"

    dx_mail_domain = fields.Char(string="Dominio de correo")
    dx_mail_mailbox = fields.Char(string="Mailbox principal")
    dx_mail_alias_admin = fields.Char(string="Alias administración")
    dx_mail_alias_sales = fields.Char(string="Alias ventas")
    dx_mail_alias_purchase = fields.Char(string="Alias compras")
    dx_mail_alias_invoice = fields.Char(string="Alias facturación")
    dx_mail_alias_accounting = fields.Char(string="Alias contabilidad")
    dx_mail_alias_info = fields.Char(string="Alias info")

    def _dx_mail_profile(self):
        self.ensure_one()
        return profile_for_code(self.dx_short_code) or profile_for_company_name(
            self.name
        )

    def _dx_alias_map(self):
        self.ensure_one()
        return {
            "admin": self.dx_mail_alias_admin,
            "sales": self.dx_mail_alias_sales,
            "purchase": self.dx_mail_alias_purchase,
            "invoice": self.dx_mail_alias_invoice,
            "accounting": self.dx_mail_alias_accounting,
            "info": self.dx_mail_alias_info,
        }

    def _dx_address_for_role(self, role):
        self.ensure_one()
        mapping = self._dx_alias_map()
        addr = mapping.get(role) or mapping.get("admin")
        if addr and belongs_to_domain(addr, self.dx_mail_domain):
            return addr
        profile = self._dx_mail_profile()
        if profile:
            return address_for(profile, role if role in mapping else "admin")
        return self.email or ""

    def _dx_role_for_document(self, model, res_id=None):
        move_type = None
        if model == "account.move" and res_id:
            move = self.env["account.move"].sudo().browse(res_id)
            if move.exists():
                move_type = move.move_type
        return role_for_model(model, move_type=move_type)

    @api.constrains(
        "dx_mail_domain",
        "dx_mail_mailbox",
        "dx_mail_alias_admin",
        "dx_mail_alias_sales",
        "dx_mail_alias_purchase",
        "dx_mail_alias_invoice",
        "dx_mail_alias_accounting",
        "dx_mail_alias_info",
    )
    def _check_dx_mail_isolation(self):
        for company in self:
            domain = (company.dx_mail_domain or "").lower()
            if not domain:
                continue
            others = self.search(
                [
                    ("id", "!=", company.id),
                    ("dx_mail_domain", "=", domain),
                ],
                limit=1,
            )
            if others:
                raise ValidationError(
                    "El dominio de correo %s ya está asignado a otra empresa." % domain
                )
            addrs = [
                company.dx_mail_mailbox,
                company.dx_mail_alias_admin,
                company.dx_mail_alias_sales,
                company.dx_mail_alias_purchase,
                company.dx_mail_alias_invoice,
                company.dx_mail_alias_accounting,
                company.dx_mail_alias_info,
            ]
            for addr in addrs:
                if addr and not belongs_to_domain(addr, domain):
                    raise ValidationError(
                        "La dirección %s no pertenece al dominio %s." % (addr, domain)
                    )

    def _dx_apply_mail_profile(self):
        for company in self:
            profile = company._dx_mail_profile()
            if not profile:
                continue
            vals = {
                "dx_mail_domain": profile["domain"],
                "dx_mail_mailbox": profile["mailbox"],
                "dx_mail_alias_admin": address_for(profile, "admin"),
                "dx_mail_alias_sales": address_for(profile, "sales"),
                "dx_mail_alias_purchase": address_for(profile, "purchase"),
                "dx_mail_alias_invoice": address_for(profile, "invoice"),
                "dx_mail_alias_accounting": address_for(profile, "accounting"),
                "dx_mail_alias_info": address_for(profile, "info"),
                "email": profile["mailbox"],
            }
            company.write(vals)
            if company.partner_id and company.partner_id.email != profile["mailbox"]:
                company.partner_id.sudo().write({"email": profile["mailbox"]})
            company._dx_ensure_alias_domain(profile)
            company._dx_ensure_functional_inboxes(profile)

    def _dx_ensure_alias_domain(self, profile):
        self.ensure_one()
        AliasDomain = self.env["mail.alias.domain"].sudo()
        domain = AliasDomain.search([("name", "=", profile["domain"])], limit=1)
        if not domain:
            domain = AliasDomain.create(
                {
                    "name": profile["domain"],
                    "bounce_alias": "bounce",
                    "catchall_alias": "catchall",
                    "default_from": "administracion",
                    "sequence": self.dx_sequence or 10,
                }
            )
        if self.alias_domain_id != domain:
            self.write({"alias_domain_id": domain.id})
        return domain

    def _dx_ensure_functional_inboxes(self, profile):
        self.ensure_one()
        Inbox = self.env["dx.ms.functional.inbox"].sudo()
        roles = {
            "admin": "administracion",
            "purchase": "compras",
            "invoice": "facturacion",
            "accounting": "contabilidad",
            "info": "info",
        }
        for role, local in roles.items():
            inbox = Inbox.search(
                [("company_id", "=", self.id), ("role", "=", role)], limit=1
            )
            if not inbox:
                Inbox.create(
                    {
                        "name": "%s · %s"
                        % (
                            {
                                "admin": "Administración",
                                "purchase": "Compras",
                                "invoice": "Facturación",
                                "accounting": "Contabilidad",
                                "info": "Contacto",
                            }[role],
                            self.dx_trade_name or self.name,
                        ),
                        "company_id": self.id,
                        "role": role,
                        "alias_name": local,
                    }
                )
        self._dx_ensure_sales_alias(profile)

    def _dx_ensure_sales_alias(self, profile):
        self.ensure_one()
        if "crm.lead" not in self.env:
            return
        Alias = self.env["mail.alias"].sudo()
        domain = self.alias_domain_id
        if not domain:
            return
        existing = Alias.search(
            [("alias_name", "=", "ventas"), ("alias_domain_id", "=", domain.id)],
            limit=1,
        )
        model = self.env["ir.model"]._get("crm.lead")
        defaults = "{'company_id': %s, 'type': 'lead'}" % self.id
        if existing:
            existing.write(
                {
                    "alias_model_id": model.id,
                    "alias_defaults": defaults,
                    "alias_contact": "everyone",
                }
            )
            return
        Alias.create(
            {
                "alias_name": "ventas",
                "alias_domain_id": domain.id,
                "alias_model_id": model.id,
                "alias_defaults": defaults,
                "alias_contact": "everyone",
            }
        )

    @api.model
    def _dx_bootstrap_microsoft_mail(self):
        companies = self.sudo().search([])
        targets = companies.filtered(lambda c: c._dx_mail_profile())
        targets._dx_apply_mail_profile()
        return True

    @api.model
    def _dx_company_for_email(self, email):
        domain = domain_of(email)
        if not domain:
            return self.browse()
        return self.sudo().search([("dx_mail_domain", "=", domain)], limit=1)
