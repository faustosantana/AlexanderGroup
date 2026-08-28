# -*- coding: utf-8 -*-

from collections import defaultdict

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class JustechApprovalUserRule(models.Model):
    _name = "justech.approval.user.rule"
    _description = "Configuración de aprobador Justech"
    _order = "company_id, user_id"
    _rec_name = "user_id"

    user_id = fields.Many2one(
        "res.users",
        string="Usuario",
        required=True,
        ondelete="cascade",
        domain="[('share', '=', False), ('active', '=', True)]",
    )
    company_id = fields.Many2one(
        "res.company",
        string="Compañía",
        required=True,
        default=lambda self: self.env.company,
        index=True,
        ondelete="restrict",
    )
    email = fields.Char(related="user_id.email", string="Email", readonly=True)
    active = fields.Boolean(default=True)
    approve_sale = fields.Boolean(string="Aprueba cotizaciones / ventas")
    approve_purchase = fields.Boolean(string="Aprueba órdenes de compra")
    approve_invoice = fields.Boolean(string="Aprueba facturas de cliente")
    allow_self_approval = fields.Boolean(string="Puede autoaprobar")

    _user_company_unique = models.Constraint(
        "UNIQUE(user_id, company_id)",
        "Cada usuario solo puede tener una fila de configuración por compañía.",
    )

    @api.constrains("approve_sale", "approve_purchase", "approve_invoice", "active")
    def _check_at_least_one_category(self):
        for rule in self.filtered("active"):
            if not (rule.approve_sale or rule.approve_purchase or rule.approve_invoice):
                raise ValidationError(
                    _(
                        "Un aprobador activo debe tener al menos un tipo de documento marcado."
                    )
                )

    @api.model
    def _user_notify_email(self, user):
        email = (user.email or "").strip()
        if email:
            return email
        login = (user.login or "").strip()
        return login if "@" in login else ""

    @api.model
    def approvers_for_type(self, request_type, company=None):
        flag_map = {
            "sale_order": "approve_sale",
            "purchase_order": "approve_purchase",
            "out_invoice": "approve_invoice",
        }
        flag = flag_map.get(request_type)
        if not flag:
            return self.env["res.users"]
        company = company or self.env.company
        domain = [
            ("active", "=", True),
            (flag, "=", True),
            ("company_id", "=", company.id),
        ]
        users = self.search(domain).mapped("user_id")
        return users.filtered(
            lambda u: u.active
            and self._user_notify_email(u)
            and (not company or company in u.company_ids)
        )

    def allows_self_approval(self, user):
        self.ensure_one()
        return bool(self.allow_self_approval and self.user_id == user)

    @api.model
    def normalize_company_rules(self, strict_conflict=True):
        """Normalize duplicates by (user_id, company_id) keeping smallest id.

        If strict_conflict is True, any mismatch in functional flags aborts.
        """
        rules = self.with_context(active_test=False).sudo().search([], order="user_id, id")
        fallback_company = self.env.company or self.env["res.company"].sudo().search([], limit=1)
        grouped = defaultdict(list)
        for rule in rules:
            company = rule.company_id or rule.user_id.company_id or fallback_company
            if not company:
                raise ValidationError(
                    _("No se pudo determinar compañía para la regla de aprobador ID %s.")
                    % rule.id
                )
            grouped[(rule.user_id.id, company.id)].append((rule, company))

        for (user_id, company_id), entries in grouped.items():
            signatures = {
                (
                    bool(rule.active),
                    bool(rule.approve_sale),
                    bool(rule.approve_purchase),
                    bool(rule.approve_invoice),
                    bool(rule.allow_self_approval),
                )
                for rule, _company in entries
            }
            if strict_conflict and len(signatures) > 1:
                details = ", ".join(
                    "id=%s%s"
                    % (
                        rule.id,
                        (
                            bool(rule.active),
                            bool(rule.approve_sale),
                            bool(rule.approve_purchase),
                            bool(rule.approve_invoice),
                            bool(rule.allow_self_approval),
                        ),
                    )
                    for rule, _company in entries
                )
                raise ValidationError(
                    _(
                        "Conflicto en duplicados de configuración para user_id=%s, company_id=%s: %s"
                    )
                    % (user_id, company_id, details)
                )

            canonical_rule, canonical_company = sorted(
                entries, key=lambda item: item[0].id
            )[0]
            if not canonical_rule.company_id:
                canonical_rule.write({"company_id": canonical_company.id})

            for duplicate_rule, _company in sorted(entries, key=lambda item: item[0].id)[1:]:
                duplicate_rule.unlink()

        missing_company = self.with_context(active_test=False).sudo().search(
            [("company_id", "=", False)]
        )
        for rule in missing_company:
            company = rule.user_id.company_id or fallback_company
            if not company:
                raise ValidationError(
                    _("No se pudo asignar compañía a la regla de aprobador ID %s.")
                    % rule.id
                )
            rule.write({"company_id": company.id})
