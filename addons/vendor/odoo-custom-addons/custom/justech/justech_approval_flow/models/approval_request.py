# -*- coding: utf-8 -*-

import hashlib
import logging
import secrets
from datetime import timedelta

from markupsafe import Markup, escape

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError

from .snapshot_utils import SNAPSHOT_LINE_LIMIT, format_snapshot_html
from .url_utils import (
    ALLOWED_DOCUMENT_MODELS,
    align_public_url_with_web_base,
    join_public_url,
    normalize_public_base_url,
)

_logger = logging.getLogger(__name__)

REQUEST_TYPE_LABEL = {
    "purchase_order": "Orden de compra",
    "sale_order": "Cotización",
    "out_invoice": "Factura de cliente",
}


class JustechApprovalRequest(models.Model):
    _name = "justech.approval.request"
    _description = "Solicitud de aprobación Justech"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "id desc"
    _rec_name = "display_name"

    document_model = fields.Char(required=True, index=True, readonly=True)
    res_id = fields.Integer(required=True, index=True, readonly=True)
    request_type = fields.Selection(
        [
            ("purchase_order", "Orden de compra"),
            ("sale_order", "Cotización"),
            ("out_invoice", "Factura de cliente"),
        ],
        required=True,
        index=True,
        readonly=True,
    )
    display_name = fields.Char(compute="_compute_display_name", store=True)
    document_name = fields.Char(readonly=True)
    partner_id = fields.Many2one("res.partner", readonly=True)
    requester_id = fields.Many2one("res.users", required=True, readonly=True)
    approver_id = fields.Many2one("res.users", readonly=True)
    approver_ids = fields.Many2many(
        "res.users",
        "justech_approval_request_approver_rel",
        "request_id",
        "user_id",
        string="Aprobadores notificados",
        readonly=True,
    )
    salesperson_id = fields.Many2one("res.users", readonly=True)
    origin = fields.Char(readonly=True)
    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
        index=True,
        readonly=True,
    )
    currency_id = fields.Many2one("res.currency", readonly=True)
    amount_untaxed = fields.Monetary(currency_field="currency_id", readonly=True)
    amount_tax = fields.Monetary(currency_field="currency_id", readonly=True)
    amount_total = fields.Monetary(currency_field="currency_id", readonly=True)
    extra_line_count = fields.Integer(readonly=True)
    state = fields.Selection(
        [
            ("pending", "Pendiente"),
            ("approved", "Aprobada"),
            ("rejected", "Rechazada"),
            ("cancelled", "Cancelada"),
            ("invalidated", "Invalidada"),
        ],
        default="pending",
        required=True,
        index=True,
        tracking=True,
    )
    request_note = fields.Text(string="Comentario de solicitud")
    decision_note = fields.Text(string="Motivo / comentario de decisión")
    requested_at = fields.Datetime(default=fields.Datetime.now, readonly=True)
    decided_at = fields.Datetime(readonly=True)
    decided_by_id = fields.Many2one("res.users", readonly=True)
    token_decision = fields.Boolean(readonly=True)
    fingerprint = fields.Char(readonly=True)
    snapshot_html = fields.Html(sanitize=False, readonly=True)
    token_hash = fields.Char(copy=False, readonly=True, index=True)
    token_used = fields.Boolean(default=False, readonly=True)
    token_expires_at = fields.Datetime(readonly=True)
    activity_id = fields.Many2one("mail.activity", readonly=True)
    email_to = fields.Char(readonly=True)
    mail_error = fields.Text(readonly=True)
    result_mail_sent = fields.Boolean(default=False, readonly=True)
    attachment_ids = fields.Many2many(
        "ir.attachment",
        compute="_compute_attachment_ids",
        string="Adjuntos",
    )
    attachment_count = fields.Integer(string="Adjuntos", compute="_compute_attachment_ids")
    request_note_preview = fields.Char(
        string="Comentario",
        compute="_compute_request_note_preview",
    )

    _sql_constraints = [
        (
            "token_hash_unique",
            "unique(token_hash)",
            "El token de aprobación debe ser único.",
        ),
    ]

    @api.depends("request_type", "document_name")
    def _compute_display_name(self):
        for rec in self:
            kind = REQUEST_TYPE_LABEL.get(rec.request_type, rec.request_type or "")
            rec.display_name = ("%s %s" % (kind, rec.document_name or "")).strip()

    def _compute_attachment_ids(self):
        grouped = {}
        if self.ids:
            attachments = self.env["ir.attachment"].sudo().search(
                [
                    ("res_model", "=", self._name),
                    ("res_id", "in", self.ids),
                ]
            )
            for att in attachments:
                grouped.setdefault(att.res_id, self.env["ir.attachment"])
                grouped[att.res_id] |= att
        for rec in self:
            rec.attachment_ids = grouped.get(rec.id, self.env["ir.attachment"])
            rec.attachment_count = len(rec.attachment_ids)

    @api.depends("request_note")
    def _compute_request_note_preview(self):
        for rec in self:
            note = " ".join((rec.request_note or "").split())
            rec.request_note_preview = (note[:80] + "…") if len(note) > 80 else note

    def get_base_url(self):
        return self.env["ir.config_parameter"].sudo().get_param("web.base.url") or ""

    @api.model
    def get_public_base_url(self):
        icp = self.env["ir.config_parameter"].sudo()
        aligned = align_public_url_with_web_base(
            icp.get_param("justech.approval.public.base.url"),
            icp.get_param("web.base.url") or self.get_base_url(),
        )
        return normalize_public_base_url(aligned)

    def _get_document(self):
        self.ensure_one()
        if not self.document_model or self.document_model not in self.env or not self.res_id:
            return False
        rec = self.env[self.document_model].browse(self.res_id)
        return rec if rec.exists() else False

    def action_open_document(self):
        self.ensure_one()
        doc = self._get_document()
        if not doc:
            raise UserError(_("El documento ya no existe."))
        return {
            "type": "ir.actions.act_window",
            "res_model": self.document_model,
            "res_id": doc.id,
            "view_mode": "form",
            "target": "current",
        }

    def action_open_reject_wizard(self):
        self.ensure_one()
        if self.state != "pending":
            raise UserError(_("La solicitud ya no está pendiente."))
        return {
            "type": "ir.actions.act_window",
            "name": _("Rechazar aprobación"),
            "res_model": "justech.approval.reject.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_request_id": self.id},
        }

    def action_open_approve_wizard(self):
        self.ensure_one()
        if self.state != "pending":
            raise UserError(_("La solicitud ya no está pendiente."))
        return {
            "type": "ir.actions.act_window",
            "name": _("Aprobar solicitud"),
            "res_model": "justech.approval.approve.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_request_id": self.id},
        }

    def _multiline_html(self, text):
        if not text:
            return Markup("")
        return Markup("<br/>").join(escape(line) for line in str(text).splitlines())

    def request_note_html(self):
        self.ensure_one()
        return self._multiline_html(self.request_note)

    def decision_note_html(self):
        self.ensure_one()
        return self._multiline_html(self.decision_note)

    def request_attachment_names_html(self):
        self.ensure_one()
        items = [
            "<li>%s</li>" % escape(att.name or _("archivo"))
            for att in self.attachment_ids
        ]
        if not items:
            return Markup("")
        return Markup(
            "<ul style='margin:8px 0 0 18px;padding:0;'>%s</ul>" % "".join(items)
        )

    def _allowed_request_attachments(self, attachment_ids):
        self.ensure_one()
        if not attachment_ids:
            return self.env["ir.attachment"]
        if not hasattr(attachment_ids, "exists"):
            attachment_ids = self.env["ir.attachment"].browse(attachment_ids)
        allowed_models = {
            False,
            "",
            "justech.approval.sale.confirm.wizard",
            "justech.approval.request",
            self.document_model,
        }
        safe = self.env["ir.attachment"]
        for att in attachment_ids.sudo().exists():
            if att.res_model not in allowed_models:
                continue
            if att.res_model == "justech.approval.request" and att.res_id not in (
                0,
                False,
                self.id,
            ):
                continue
            if att.res_model == self.document_model and att.res_id not in (
                0,
                False,
                self.res_id,
            ):
                continue
            safe |= att
        return safe

    def _link_attachments(self, attachment_ids):
        self.ensure_one()
        safe = self._allowed_request_attachments(attachment_ids)
        if safe:
            safe.sudo().write(
                {"res_model": "justech.approval.request", "res_id": self.id}
            )
        return safe

    def _physical_email_attachments(self):
        self.ensure_one()
        allowed_mimetypes = {
            "application/pdf",
            "image/png",
            "image/jpeg",
            "image/gif",
            "image/webp",
            "text/plain",
            "text/csv",
            "application/vnd.ms-excel",
            "application/msword",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        }
        max_bytes = 5 * 1024 * 1024
        selected = self.env["ir.attachment"]
        total = 0
        for att in self.attachment_ids.sudo():
            mimetype = (att.mimetype or "").split(";")[0].strip()
            if mimetype not in allowed_mimetypes:
                continue
            size = att.file_size or 0
            if size <= 0 or total + size > max_bytes:
                continue
            selected |= att
            total += size
        copies = self.env["ir.attachment"]
        for att in selected:
            copies |= att.copy({"res_model": False, "res_id": 0})
        return copies

    def _user_notify_email(self, user):
        email = (user.email or "").strip()
        if email:
            return email
        login = (user.login or "").strip()
        return login if "@" in login else ""

    def _approver_users(self, company, request_type=None):
        Rule = self.env["justech.approval.user.rule"].sudo()
        has_rules = bool(Rule.search_count([("active", "=", True)]))
        if request_type:
            users = Rule.approvers_for_type(request_type, company=company)
            if users:
                return users
            if has_rules:
                return self.env["res.users"]
        elif has_rules:
            users = Rule.approvers_for_type(
                "sale_order", company=company
            ) | Rule.approvers_for_type(
                "purchase_order", company=company
            ) | Rule.approvers_for_type("out_invoice", company=company)
            if users:
                return users

        def eligible(user_set):
            return user_set.filtered(lambda u: u.active and self._user_notify_email(u))

        users = eligible(company.justech_approval_user_ids)
        if not users:
            group = self.env.ref(
                "justech_approval_flow.group_approver", raise_if_not_found=False
            )
            if group:
                users = eligible(
                    self.env["res.users"].search(
                        [
                            ("group_ids", "in", group.ids),
                            ("share", "=", False),
                            ("active", "=", True),
                        ]
                    )
                )
        return users

    def _generate_token(self):
        self.ensure_one()
        raw = secrets.token_urlsafe(32)
        days = self.company_id.justech_approval_token_days or 14
        self.sudo().write(
            {
                "token_hash": hashlib.sha256(raw.encode()).hexdigest(),
                "token_used": False,
                "token_expires_at": fields.Datetime.now() + timedelta(days=days),
            }
        )
        return raw

    @api.model
    def _find_by_raw_token(self, raw):
        if not raw:
            return self.browse()
        digest = hashlib.sha256(raw.encode()).hexdigest()
        rec = self.sudo().search([("token_hash", "=", digest)], limit=1)
        return rec

    def _token_error(self, raw, expected_action=None):
        rec = self._find_by_raw_token(raw)
        if not rec:
            return _(
                "Esta solicitud de aprobación ya no es válida. "
                "Abra Odoo o utilice la solicitud de aprobación más reciente."
            )
        if rec.state == "invalidated":
            return _(
                "Esta solicitud de aprobación ya no es válida porque la orden fue "
                "modificada. Abra Odoo o utilice la solicitud de aprobación más reciente."
            )
        if rec.token_used or rec.state != "pending":
            return _(
                "Esta solicitud de aprobación ya no es válida. "
                "Abra Odoo o utilice la solicitud de aprobación más reciente."
            )
        if rec.token_expires_at and rec.token_expires_at < fields.Datetime.now():
            return _(
                "Esta solicitud de aprobación ya no es válida porque el enlace expiró. "
                "Abra Odoo o solicite una nueva aprobación."
            )
        doc = rec._get_document()
        if not doc:
            return _("El documento ya no existe.")
        if getattr(doc, "state", None) == "cancel":
            return _("El documento está cancelado.")
        if rec.fingerprint and hasattr(doc, "_justech_approval_fingerprint"):
            if rec.fingerprint != doc._justech_approval_fingerprint():
                return _(
                    "Esta solicitud de aprobación ya no es válida porque la orden fue "
                    "modificada. Abra Odoo o utilice la solicitud de aprobación más reciente."
                )
        return False

    def _mail_brand_label(self):
        """Company-aware email / HTTP page header label."""
        self.ensure_one()
        name = (self.company_id.name or "").upper()
        if "OFFICE" in name:
            return "JUST OFFICE"
        if "PLUGSAFE" in name or "PLUG SAFE" in name:
            return "PLUGSAFE"
        if "OMNI" in name:
            return "OMNI SOLUTIONS"
        return "JUSTECH"

    def _justech_url(self, action):
        self.ensure_one()
        token = self.env.context.get("justech_approval_token") or ""
        return join_public_url(
            self.get_public_base_url(), "justech", "approval", token, action
        )

    def _odoo_document_url(self):
        self.ensure_one()
        if self.document_model not in ALLOWED_DOCUMENT_MODELS:
            return join_public_url(self.get_public_base_url(), "odoo")
        return join_public_url(
            self.get_public_base_url(), "odoo", self.document_model, str(self.res_id)
        )

    def _decision_user(self, token_flow=False):
        self.ensure_one()
        user = self.env.user
        if user._is_public():
            from odoo.exceptions import AccessError

            raise AccessError(_("Debe iniciar sesión para aprobar o rechazar."))
        # Mail link still counts as via_mail for messaging, but actor is the logged-in user.
        via_mail = bool(token_flow)
        return user, via_mail

    def _post_document(self, body, author=None):
        doc = self._get_document()
        if not doc or not hasattr(doc, "message_post"):
            return
        author = author or self.env.user
        if author._is_public():
            from odoo.exceptions import AccessError

            raise AccessError(_("Debe iniciar sesión para publicar la decisión."))
        doc.sudo().message_post(
            body=body,
            author_id=author.partner_id.id,
            message_type="comment",
            subtype_xmlid="mail.mt_note",
        )

    def _complete_activity(self):
        for rec in self:
            activities = rec.activity_id
            doc = rec._get_document()
            if doc:
                act_type = rec.env.ref(
                    "justech_approval_flow.mail_activity_approval", raise_if_not_found=False
                )
                if act_type:
                    activities |= doc.sudo().activity_ids.filtered(
                        lambda a: a.activity_type_id == act_type
                    )
            for activity in activities.exists():
                try:
                    activity.action_feedback(feedback=rec.decision_note or "")
                except Exception:  # noqa: BLE001
                    activity.unlink()

    @api.model
    def _is_approval_admin(self, user):
        """Global approval admins (config menu + override on allowed companies).

        Uses explicit Justech groups — not ``user._is_admin()`` / superuser bypass.
        """
        return user.has_group(
            "justech_approval_flow.group_manager"
        ) or user.has_group("base.group_system")

    @api.model
    def _user_has_company_access(self, user, company):
        if not company:
            return True
        return company.id in user.company_ids.ids

    @api.model
    def _user_rule_for_company(self, user, company):
        if not company:
            return self.env["justech.approval.user.rule"]
        return (
            self.env["justech.approval.user.rule"]
            .sudo()
            .search(
                [
                    ("user_id", "=", user.id),
                    ("company_id", "=", company.id),
                    ("active", "=", True),
                ],
                limit=1,
            )
        )

    @api.model
    def _user_rule_allows_request_type(self, user, company, request_type):
        flag_map = {
            "sale_order": "approve_sale",
            "purchase_order": "approve_purchase",
            "out_invoice": "approve_invoice",
        }
        flag = flag_map.get(request_type)
        if not flag:
            return False
        rule = self._user_rule_for_company(user, company)
        return bool(rule and getattr(rule, flag))

    def _can_decide(self, user=None, token_flow=False):
        self.ensure_one()
        user = user or self.env.user
        # Token/URL alone is never enough — authenticated user with rights required.
        if user._is_public():
            raise AccessError(_("Debe iniciar sesión para aprobar o rechazar."))
        company = self.company_id
        if company and not self._user_has_company_access(user, company):
            raise AccessError(
                _("No puede aprobar o rechazar solicitudes de otra compañía.")
            )
        if self._is_approval_admin(user):
            # Admin: any company in user.company_ids; no per-company rule row required.
            if self.requester_id == user and not self._allows_self_approval(user):
                raise AccessError(
                    _(
                        "No puede autoaprobar esta solicitud. Se requiere un aprobador distinto."
                    )
                )
            return True
        authorized = False
        Rule = self.env["justech.approval.user.rule"].sudo()
        has_any_rules = bool(Rule.search_count([("active", "=", True)]))
        if self._user_rule_allows_request_type(user, company, self.request_type):
            authorized = True
        elif user.has_group("justech_approval_flow.group_approver"):
            if not has_any_rules:
                authorized = True
            elif Rule.approvers_for_type(self.request_type, company=company) & user:
                authorized = True
        elif (
            self.request_type == "purchase_order"
            and user.has_group("purchase.group_purchase_manager")
        ):
            authorized = True
        if not authorized:
            raise AccessError(_("No tiene permiso para aprobar o rechazar."))
        if self.requester_id == user and not self._allows_self_approval(user):
            raise AccessError(
                _("No puede autoaprobar esta solicitud. Se requiere un aprobador distinto.")
            )
        return True

    def _allows_self_approval(self, user):
        self.ensure_one()
        rule = self._user_rule_for_company(user, self.company_id)
        if rule:
            return rule.allow_self_approval
        if self._is_approval_admin(user):
            return True
        return user.has_group("justech_approval_flow.group_self_approve")

    def action_approve(self, note=None, token_flow=False):
        for rec in self:
            if rec.state != "pending":
                raise UserError(_("La solicitud ya no está pendiente."))
            rec._can_decide(token_flow=token_flow)
            doc = rec._get_document()
            if not doc:
                raise UserError(_("El documento ya no existe."))
            if rec.fingerprint and hasattr(doc, "_justech_approval_fingerprint"):
                if rec.fingerprint != doc._justech_approval_fingerprint():
                    rec.action_invalidate(
                        _("La aprobación anterior fue invalidada porque el documento fue modificado.")
                    )
                    raise UserError(
                        _("El documento cambió. Debe solicitar una nueva aprobación.")
                    )
            decided_by, via_mail = rec._decision_user(token_flow=token_flow)
            rec.sudo().write(
                {
                    "state": "approved",
                    "decided_at": fields.Datetime.now(),
                    "decided_by_id": decided_by.id,
                    "decision_note": note or rec.decision_note,
                    "token_used": True,
                    "token_decision": bool(token_flow),
                }
            )
            rec._complete_activity()
            rec._apply_document_approval()
            if via_mail:
                rec._post_document(
                    _("%s aprobó vía enlace de correo.") % decided_by.name,
                    author=decided_by,
                )
            else:
                rec._post_document(_("%s aprobó.") % decided_by.name, author=decided_by)
            rec._send_result_mail()
        return True

    def action_reject(self, note=None, token_flow=False):
        for rec in self:
            if rec.state != "pending":
                raise UserError(_("La solicitud ya no está pendiente."))
            rec._can_decide(token_flow=token_flow)
            if not (note or rec.decision_note):
                raise ValidationError(_("Debe indicar el motivo del rechazo."))
            decided_by, via_mail = rec._decision_user(token_flow=token_flow)
            rec.sudo().write(
                {
                    "state": "rejected",
                    "decided_at": fields.Datetime.now(),
                    "decided_by_id": decided_by.id,
                    "decision_note": note or rec.decision_note,
                    "token_used": True,
                    "token_decision": bool(token_flow),
                }
            )
            rec._complete_activity()
            rec._apply_document_rejection()
            if via_mail:
                rec._post_document(
                    _("%s rechazó vía enlace de correo: %s")
                    % (decided_by.name, rec.decision_note),
                    author=decided_by,
                )
            else:
                rec._post_document(
                    _("%s rechazó: %s") % (decided_by.name, rec.decision_note),
                    author=decided_by,
                )
            rec._send_result_mail()
        return True

    def action_cancel(self):
        for rec in self.filtered(lambda r: r.state == "pending"):
            rec.sudo().write({"state": "cancelled", "token_used": True})
            rec._complete_activity()
            rec._sync_document_state("none")
        return True

    def action_invalidate(self, reason=None):
        reason = reason or _(
            "La aprobación anterior fue invalidada porque el documento fue modificado."
        )
        for rec in self.filtered(lambda r: r.state in ("pending", "approved")):
            rec.sudo().write(
                {
                    "state": "invalidated",
                    "token_used": True,
                    "decision_note": reason,
                }
            )
            rec._complete_activity()
            rec._sync_document_state("invalidated")
            rec._post_document(reason)
        return True

    def _sync_document_state(self, value):
        self.ensure_one()
        doc = self._get_document()
        if doc and "justech_approval_state" in doc._fields:
            doc.with_context(justech_approval_skip_fingerprint=True).sudo().write(
                {"justech_approval_state": value}
            )

    def _apply_document_approval(self):
        self.ensure_one()
        doc = self._get_document()
        if not doc:
            return
        self._sync_document_state("approved")
        # Complete the original gated action (no second click).
        # Context flags prevent re-entering the approval wizard / fingerprint loop.
        if self.request_type == "purchase_order" and hasattr(doc, "button_approve"):
            if doc.state == "to approve":
                doc.with_context(justech_approval_decision=True).button_approve()
        elif self.request_type == "sale_order" and hasattr(doc, "action_confirm"):
            if doc.state in ("draft", "sent"):
                # sudo: email token / approver may lack sale ACL; intent is
                # completing the requester's original Confirm.
                doc.sudo().with_context(
                    justech_approval_decision=True,
                    justech_approval_skip_fingerprint=True,
                ).action_confirm()
                doc.invalidate_recordset()
                if doc.state in ("sale", "done"):
                    self._post_document(
                        _("Aprobada y confirmada mediante Flujo de Aprobaciones.")
                    )

    def _apply_document_rejection(self):
        self.ensure_one()
        doc = self._get_document()
        if not doc:
            return
        self._sync_document_state("rejected")
        if self.request_type == "purchase_order" and doc.state == "to approve":
            doc.with_context(justech_approval_skip_fingerprint=True).write(
                {"state": "draft"}
            )

    def _send_mail(self, raw_token):
        self.ensure_one()
        template = self.env.ref(
            "justech_approval_flow.mail_template_approval_request",
            raise_if_not_found=False,
        )
        if not template or not self.email_to:
            _logger.warning("justech_approval_flow: no template or recipients for %s", self.id)
            return
        email_values = {}
        physical = self._physical_email_attachments()
        if physical:
            email_values["attachment_ids"] = physical.ids
        try:
            template.with_context(justech_approval_token=raw_token).send_mail(
                self.id, force_send=True, email_values=email_values or None
            )
        except Exception as exc:  # noqa: BLE001
            _logger.exception("justech_approval_flow: mail failed for %s", self.id)
            self.sudo().write({"mail_error": str(exc)})

    def _send_result_mail(self):
        self.ensure_one()
        if self.result_mail_sent or self.state not in ("approved", "rejected"):
            return
        template = self.env.ref(
            "justech_approval_flow.mail_template_approval_result",
            raise_if_not_found=False,
        )
        recipient = self._user_notify_email(self.requester_id)
        if not template or not recipient:
            _logger.warning(
                "justech_approval_flow: no result template or requester email for %s",
                self.id,
            )
            return
        try:
            template.send_mail(self.id, force_send=True)
            self.sudo().write({"result_mail_sent": True})
        except Exception as exc:  # noqa: BLE001
            _logger.exception("justech_approval_flow: result mail failed for %s", self.id)
            self.sudo().write({"mail_error": str(exc)})

    def _lock_document(self, document):
        self.env.cr.execute(
            "SELECT id FROM %s WHERE id = %%s FOR UPDATE" % document._table,
            (document.id,),
        )
        self.env.cr.execute(
            """
            SELECT id FROM justech_approval_request
            WHERE document_model = %s AND res_id = %s AND state = 'pending'
            FOR UPDATE
            """,
            (document._name, document.id),
        )

    @api.model
    def _create_for_document(self, document, request_type, note=None, attachment_ids=None):
        document.ensure_one()
        self._lock_document(document)
        company = document.company_id
        approvers = self._approver_users(company, request_type=request_type)
        if not approvers:
            raise UserError(
                _("No hay aprobadores configurados para este tipo de documento.")
            )
        existing = self.search(
            [
                ("document_model", "=", document._name),
                ("res_id", "=", document.id),
                ("state", "=", "pending"),
            ],
            limit=1,
        )
        if existing:
            vals = {}
            if note and not existing.request_note:
                vals["request_note"] = note
            if vals:
                existing.sudo().write(vals)
            existing._link_attachments(attachment_ids)
            return existing
        fingerprint = (
            document._justech_approval_fingerprint()
            if hasattr(document, "_justech_approval_fingerprint")
            else False
        )
        snapshot = (
            document._justech_approval_snapshot_html()
            if hasattr(document, "_justech_approval_snapshot_html")
            else False
        )
        partner = getattr(document, "partner_id", False)
        currency = getattr(document, "currency_id", company.currency_id)
        salesperson = getattr(document, "user_id", False) or getattr(
            document, "invoice_user_id", False
        )
        rec = self.sudo().create(
            {
                "document_model": document._name,
                "res_id": document.id,
                "request_type": request_type,
                "document_name": document.display_name,
                "partner_id": partner.id if partner else False,
                "requester_id": self.env.user.id,
                "approver_id": approvers[:1].id,
                "approver_ids": [(6, 0, approvers.ids)],
                "salesperson_id": salesperson.id if salesperson else False,
                "origin": getattr(document, "origin", False)
                or getattr(document, "invoice_origin", False)
                or False,
                "company_id": company.id,
                "currency_id": currency.id if currency else False,
                "amount_untaxed": getattr(document, "amount_untaxed", 0.0) or 0.0,
                "amount_tax": getattr(document, "amount_tax", 0.0) or 0.0,
                "amount_total": getattr(document, "amount_total", 0.0) or 0.0,
                "request_note": note,
                "fingerprint": fingerprint,
                "snapshot_html": snapshot,
                "email_to": ",".join(
                    filter(None, (self._user_notify_email(u) for u in approvers))
                ),
            }
        )
        rec._link_attachments(attachment_ids)
        rec.invalidate_recordset(["attachment_ids", "attachment_count"])
        raw = rec._generate_token()
        rec._schedule_activity(document)
        rec._send_mail(raw)
        rec._post_document(
            _("%s solicitó aprobación.") % rec.requester_id.name, author=rec.requester_id
        )
        document.sudo().with_context(justech_approval_skip_fingerprint=True).write(
            {"justech_approval_state": "pending"}
        )
        return rec

    def _schedule_activity(self, document):
        self.ensure_one()
        act_type = self.env.ref(
            "justech_approval_flow.mail_activity_approval", raise_if_not_found=False
        )
        if not act_type or not hasattr(document, "activity_schedule"):
            return
        existing = document.sudo().activity_ids.filtered(
            lambda a: a.activity_type_id == act_type
        )
        scheduled = self.env["mail.activity"]
        for approver in self.approver_ids:
            user_existing = existing.filtered(lambda a: a.user_id == approver)
            if user_existing:
                scheduled |= user_existing[:1]
                continue
            try:
                activity = document.sudo().activity_schedule(
                    act_type_xmlid="justech_approval_flow.mail_activity_approval",
                    user_id=approver.id,
                    summary=_("Aprobar %s") % self.display_name,
                    note=self.request_note or "",
                )
            except Exception:  # noqa: BLE001
                _logger.exception(
                    "justech_approval_flow: activity failed for %s user %s",
                    self.id,
                    approver.id,
                )
                continue
            if activity and not isinstance(activity, bool):
                scheduled |= activity[:1] if hasattr(activity, "__getitem__") else activity
        if scheduled:
            self.sudo().activity_id = scheduled[0].id

    @api.model
    def _ensure_cost_link_purchase_read(self):
        """Allow purchase users to open PO forms without AccessError on cost_link compute."""
        if "purchase.sale.cost.link" not in self.env:
            return
        model = self.env["ir.model"]._get("purchase.sale.cost.link")
        group = self.env.ref("purchase.group_purchase_user", raise_if_not_found=False)
        if not model or not group:
            return
        Access = self.env["ir.model.access"].sudo()
        if not Access.search(
            [
                ("model_id", "=", model.id),
                ("group_id", "=", group.id),
                ("perm_read", "=", True),
            ],
            limit=1,
        ):
            Access.create(
                {
                    "name": "purchase.sale.cost.link purchase user read (approval)",
                    "model_id": model.id,
                    "group_id": group.id,
                    "perm_read": True,
                    "perm_write": False,
                    "perm_create": False,
                    "perm_unlink": False,
                }
            )
        Rule = self.env["ir.rule"].sudo()
        if not Rule.search(
            [
                ("model_id", "=", model.id),
                ("name", "=", "Enlace costo: compradores sin datos (approval flow)"),
            ],
            limit=1,
        ):
            Rule.create(
                {
                    "name": "Enlace costo: compradores sin datos (approval flow)",
                    "model_id": model.id,
                    "groups": [(6, 0, [group.id])],
                    "domain_force": "[(0, '=', 1)]",
                    "perm_read": True,
                    "perm_write": False,
                    "perm_create": False,
                    "perm_unlink": False,
                }
            )

    @api.model
    def snapshot_html_from_lines(self, lines, extra_rows=None):
        extra_count = max(0, len(lines) - SNAPSHOT_LINE_LIMIT)
        return format_snapshot_html(lines, extra_rows=extra_rows, extra_line_count=extra_count)
