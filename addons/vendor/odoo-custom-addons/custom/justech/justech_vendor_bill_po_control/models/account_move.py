# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError

from odoo.addons.justech_vendor_bill_po_control.models.po_exception_rule import (
    APPROVAL_LEVEL_SELECTION,
)
from odoo.addons.justech_vendor_bill_po_control.models.constants import (
    VENDOR_BILL_MOVE_TYPES,
)
from odoo.addons.justech_vendor_bill_po_control.models import approval_helpers as ah

APPROVAL_STATE_SELECTION = [
    ("draft", "Borrador"),
    ("pending_validation", "Pendiente de Validación"),
    ("approved", "Aprobada"),
    ("rejected", "Rechazada"),
    ("returned", "Devuelta para Corrección"),
    ("legacy_approved", "Aprobada (histórico)"),
]

BLOCK_MSG = (
    "Esta factura está pendiente de validación y no puede contabilizarse, "
    "pagarse ni enviarse a Tesorería."
)

NO_PO_ALERT = (
    "Esta factura no tiene una Orden de Compra válida. "
    "Guárdela y utilice ‘Enviar a aprobación’."
)

MISSING_REASON_MSG = (
    "Debe completar el Motivo de no tener Orden de Compra "
    "en el asistente ‘Enviar a aprobación’."
)

FISCAL_POST_ALERT_INTRO = (
    "La factura fue aprobada, pero no pudo contabilizarse porque faltan "
    "datos fiscales obligatorios. Complete la información indicada y pulse Confirmar."
)

# Keywords in UserError → human labels (no technical field/model names).
_FISCAL_ERROR_HINTS = (
    (("ncf", "número de comprobante", "comprobante fiscal", "l10n_latam_document_number"), "NCF"),
    (("tipo de comprobante", "document type", "l10n_latam_document_type", "fiscal type", "latam"), "tipo de comprobante"),
    (("fecha de factura", "invoice date", "invoice_date"), "fecha de factura"),
    (("fecha contable", "accounting date", "date "), "fecha contable"),
    (("diario", "journal"), "diario"),
    (
        (
            "falta el proveedor",
            "proveedor es obligatorio",
            "seleccione un proveedor",
            "partner is required",
            "missing partner",
        ),
        "proveedor",
    ),
    (("moneda", "currency"), "moneda"),
    (
        (
            "tipo de costos",
            "expense type",
            "gasto dgii",
            "justech_do_expense",
            "clasificación fiscal",
            "localización",
        ),
        "campos fiscales de la localización dominicana",
    ),
)


class AccountMove(models.Model):
    _inherit = "account.move"

    related_purchase_order_ids = fields.Many2many(
        "purchase.order",
        string="Órdenes de Compra relacionadas",
        compute="_compute_related_purchase_orders",
        store=False,
    )
    related_purchase_order_count = fields.Integer(
        string="OC relacionadas",
        compute="_compute_related_purchase_orders",
        store=True,
    )
    has_valid_purchase_order = fields.Boolean(
        string="Tiene OC válida",
        compute="_compute_related_purchase_orders",
        store=True,
        index=True,
    )
    po_requirement_exception = fields.Boolean(
        string="Excepción de requisito OC (legacy)",
        tracking=True,
        copy=False,
        readonly=True,
    )
    po_exception_reason = fields.Text(
        string="Motivo de excepción OC (legacy)",
        tracking=True,
        copy=False,
    )
    po_exception_approved_by = fields.Many2one(
        "res.users",
        string="Excepción aprobada por (legacy)",
        tracking=True,
        copy=False,
        readonly=True,
    )
    po_exception_approved_at = fields.Datetime(
        string="Excepción aprobada el (legacy)",
        tracking=True,
        copy=False,
        readonly=True,
    )
    po_exception_rule_id = fields.Many2one(
        "justech.vendor.bill.po.exception.rule",
        string="Regla de excepción aplicada",
        compute="_compute_po_exception_rule",
        store=True,
    )
    purchase_order_required = fields.Boolean(
        string="Exige OC",
        related="company_id.purchase_order_required",
        store=False,
    )
    po_control_state = fields.Selection(
        [
            ("ok_po", "Con OC"),
            ("ok_exception", "Exceptuada"),
            ("warning", "Sin OC (advertencia)"),
            ("blocked", "Sin OC (bloqueable)"),
            ("n/a", "No aplica"),
        ],
        string="Estado control OC",
        compute="_compute_po_control_state",
        store=True,
        index=True,
    )

    vendor_bill_classification = fields.Selection(
        [
            ("direct", "Compra directa"),
            ("resale", "Reventa"),
            ("inventory", "Inventario"),
            ("project", "Proyecto"),
            ("admin", "Gasto administrativo"),
            ("bank", "Gasto bancario"),
            ("rent", "Alquiler"),
            ("utilities", "Servicios públicos"),
            ("tax", "Impuestos"),
            ("asset", "Activo"),
            ("internal", "Gasto interno / Servicio interno"),
            ("insurance", "Seguro"),
            ("telecom", "Telecomunicaciones"),
            ("customs", "Aduana"),
            ("logistics", "Logística"),
            ("other", "Otro"),
        ],
        string="Clasificación de compra/gasto",
        tracking=True,
        copy=False,
        index=True,
        help="Clasificación automática al aprobar sin OC (Compra directa / Gasto interno). "
        "No crea asientos adicionales.",
    )
    vendor_bill_approved_without_po = fields.Boolean(
        string="Aprobada sin OC",
        compute="_compute_vendor_bill_button_flags",
        store=False,
    )
    vendor_bill_show_confirm = fields.Boolean(
        string="Mostrar Confirmar",
        compute="_compute_vendor_bill_button_flags",
    )
    vendor_bill_show_submit_validation = fields.Boolean(
        string="Mostrar Enviar a aprobación",
        compute="_compute_vendor_bill_button_flags",
    )
    vendor_bill_show_resubmit = fields.Boolean(
        string="Mostrar Reenviar a aprobación",
        compute="_compute_vendor_bill_button_flags",
    )
    vendor_bill_show_approver_actions = fields.Boolean(
        string="Mostrar acciones de aprobador",
        compute="_compute_vendor_bill_button_flags",
    )
    vendor_bill_approval_request_count = fields.Integer(
        string="Solicitudes de aprobación",
        compute="_compute_vendor_bill_approval_request_count",
    )
    vendor_bill_approval_state = fields.Selection(
        APPROVAL_STATE_SELECTION,
        string="Estado de validación",
        default="draft",
        tracking=True,
        copy=False,
        index=True,
    )
    vendor_bill_legacy_exempt = fields.Boolean(
        string="Exento legado (técnico)",
        compute="_compute_vendor_bill_legacy_exempt",
        store=True,
        index=True,
        help="Marca técnica de compatibilidad: la factura se creó antes de la "
        "fecha efectiva de la política. No es una aprobación humana y no "
        "altera asientos, pagos ni saldos.",
    )
    vendor_bill_no_po_reason = fields.Text(
        string="Motivo de no tener Orden de Compra",
        tracking=True,
        copy=False,
        help="Obligatorio al enviar a aprobación cuando no hay OC válida. "
        "Sección: Orden de Compra y Aprobación.",
    )
    po_missing_reason = fields.Text(
        related="vendor_bill_no_po_reason",
        string="Motivo de no tener Orden de Compra",
        readonly=False,
    )
    vendor_bill_reason_readonly = fields.Boolean(
        compute="_compute_vendor_bill_button_flags",
    )
    vendor_bill_approval_notes = fields.Text(string="Observación de validación", copy=False)
    vendor_bill_approval_level_required = fields.Selection(
        APPROVAL_LEVEL_SELECTION,
        string="Nivel requerido",
        compute="_compute_vendor_bill_evaluation",
        store=True,
        readonly=True,
    )
    vendor_bill_requires_po = fields.Boolean(
        string="Sistema exige OC",
        compute="_compute_vendor_bill_evaluation",
        store=True,
        readonly=True,
    )
    vendor_bill_requires_approval = fields.Boolean(
        string="Sistema exige validación",
        compute="_compute_vendor_bill_evaluation",
        store=True,
        readonly=True,
    )
    vendor_bill_applied_rule_id = fields.Many2one(
        "justech.vendor.bill.po.exception.rule",
        string="Regla aplicada",
        compute="_compute_vendor_bill_evaluation",
        store=True,
        readonly=True,
    )
    vendor_bill_submitted_by = fields.Many2one("res.users", string="Enviado por", readonly=True, copy=False)
    vendor_bill_submitted_at = fields.Datetime(string="Enviado el", readonly=True, copy=False)
    vendor_bill_approved_by = fields.Many2one("res.users", string="Aprobado por", readonly=True, copy=False)
    vendor_bill_approved_at = fields.Datetime(string="Aprobado el", readonly=True, copy=False)
    vendor_bill_finance_approved_by = fields.Many2one(
        "res.users", string="Aprobado Finanzas", readonly=True, copy=False
    )
    vendor_bill_finance_approved_at = fields.Datetime(readonly=True, copy=False)
    vendor_bill_mgmt_approved_by = fields.Many2one(
        "res.users", string="Aprobado Gerencia", readonly=True, copy=False
    )
    vendor_bill_mgmt_approved_at = fields.Datetime(readonly=True, copy=False)
    vendor_bill_rejected_by = fields.Many2one("res.users", string="Rechazado por", readonly=True, copy=False)
    vendor_bill_rejected_at = fields.Datetime(readonly=True, copy=False)
    vendor_bill_reject_reason = fields.Text(string="Motivo de rechazo", copy=False)
    vendor_bill_returned_by = fields.Many2one("res.users", string="Devuelto por", readonly=True, copy=False)
    vendor_bill_returned_at = fields.Datetime(readonly=True, copy=False)
    vendor_bill_return_reason = fields.Text(string="Motivo de devolución", copy=False)
    vendor_bill_approver_id = fields.Many2one(
        "res.users",
        string="Aprobador asignado",
        copy=False,
        index=True,
        tracking=True,
        help="Usuario actualmente responsable de aprobar/rechazar/devolver.",
    )
    vendor_bill_finance_approver_id = fields.Many2one(
        "res.users",
        string="Aprobador Finanzas (asignado)",
        copy=False,
        tracking=True,
    )
    vendor_bill_mgmt_approver_id = fields.Many2one(
        "res.users",
        string="Aprobador Gerencia (asignado)",
        copy=False,
        tracking=True,
    )
    vendor_bill_approval_deadline = fields.Datetime(
        string="Fecha límite aprobación",
        copy=False,
        index=True,
    )
    vendor_bill_approval_days_pending = fields.Integer(
        string="Días pendientes",
        compute="_compute_vendor_bill_approval_days_pending",
    )
    vendor_bill_approval_overdue = fields.Boolean(
        string="Aprobación vencida",
        compute="_compute_vendor_bill_approval_days_pending",
        search="_search_vendor_bill_approval_overdue",
    )
    vendor_bill_reassign_count = fields.Integer(
        string="Reasignaciones",
        default=0,
        copy=False,
        readonly=True,
    )
    vendor_bill_reassign_reason = fields.Text(string="Último motivo de reasignación", copy=False)
    vendor_bill_fiscal_post_alert = fields.Text(
        string="Alerta de contabilización fiscal",
        copy=False,
        readonly=True,
        help="Mensaje funcional cuando la aprobación no pudo contabilizar por datos fiscales incompletos.",
    )

    @api.depends(
        "invoice_line_ids.purchase_line_id",
        "invoice_line_ids.purchase_line_id.order_id",
        "invoice_line_ids.purchase_line_id.order_id.state",
        "partner_id",
        "company_id",
        "move_type",
    )
    def _compute_related_purchase_orders(self):
        for move in self:
            orders = move.invoice_line_ids.mapped("purchase_line_id.order_id")
            move.related_purchase_order_ids = orders
            move.related_purchase_order_count = len(orders)
            move.has_valid_purchase_order = bool(move._justech_valid_purchase_orders(orders))

    def _justech_valid_purchase_orders(self, orders=None):
        self.ensure_one()
        orders = orders if orders is not None else self.related_purchase_order_ids
        valid = self.env["purchase.order"]
        for po in orders:
            if po.state == "cancel":
                continue
            if po.company_id != self.company_id:
                continue
            if (
                po.partner_id.commercial_partner_id
                != self.partner_id.commercial_partner_id
                and not self.env.context.get("justech_allow_po_partner_mismatch")
            ):
                continue
            if not po.order_line:
                continue
            linked = self.invoice_line_ids.filtered(
                lambda l: l.purchase_line_id and l.purchase_line_id.order_id == po
            )
            if not linked:
                continue
            # At least one linked line must still map to a real PO line
            if not any(linked.mapped("purchase_line_id")):
                continue
            valid |= po
        return valid

    @api.depends(
        "company_id",
        "has_valid_purchase_order",
        "move_type",
        "invoice_line_ids.product_id",
        "invoice_line_ids.account_id",
        "partner_id",
        "journal_id",
        "justech_do_expense_type_id",
        "amount_total",
    )
    def _compute_po_exception_rule(self):
        Rule = self.env["justech.vendor.bill.po.exception.rule"]
        for move in self:
            if move.move_type not in VENDOR_BILL_MOVE_TYPES:
                move.po_exception_rule_id = False
                continue
            move.po_exception_rule_id = Rule.find_matching_rule(move)

    @api.depends(
        "move_type",
        "has_valid_purchase_order",
        "po_requirement_exception",
        "po_exception_approved_by",
        "po_exception_rule_id",
        "company_id.vendor_bill_po_policy",
    )
    def _compute_po_control_state(self):
        for move in self:
            if move.move_type not in VENDOR_BILL_MOVE_TYPES:
                move.po_control_state = "n/a"
                continue
            if move.has_valid_purchase_order:
                move.po_control_state = "ok_po"
                continue
            if move._justech_po_exception_ok():
                move.po_control_state = "ok_exception"
                continue
            policy = move.company_id.vendor_bill_po_policy or "disabled"
            if policy == "warning":
                move.po_control_state = "warning"
            elif policy == "block":
                move.po_control_state = "blocked"
            else:
                move.po_control_state = "n/a"

    def _justech_po_exception_ok(self):
        self.ensure_one()
        rule = self.po_exception_rule_id or self.vendor_bill_applied_rule_id
        if rule and not rule.requires_purchase_order:
            return True
        if self.po_requirement_exception and self.po_exception_approved_by and self.po_exception_reason:
            return True
        return False

    @api.depends(
        "move_type",
        "company_id.vendor_bill_strict_approval",
        "company_id.vendor_bill_po_policy",
        "company_id.vendor_bill_amount_finance_limit",
        "company_id.vendor_bill_amount_management_limit",
        "has_valid_purchase_order",
        "justech_do_expense_type_id",
        "po_exception_rule_id",
        "amount_total_signed",
        "amount_total",
        "partner_id",
        "journal_id",
        "invoice_line_ids.product_id",
        "invoice_line_ids.account_id",
    )
    def _compute_vendor_bill_evaluation(self):
        for move in self:
            if move.move_type not in VENDOR_BILL_MOVE_TYPES:
                move.vendor_bill_requires_po = False
                move.vendor_bill_requires_approval = False
                move.vendor_bill_approval_level_required = "none"
                move.vendor_bill_applied_rule_id = False
                continue
            rule = move.po_exception_rule_id
            move.vendor_bill_applied_rule_id = rule
            if rule:
                move.vendor_bill_requires_po = bool(rule.requires_purchase_order)
                move.vendor_bill_requires_approval = bool(rule.requires_approval)
                move.vendor_bill_approval_level_required = rule.approval_level or "finance"
            else:
                policy = move.company_id.vendor_bill_po_policy or "disabled"
                strict = move.company_id.vendor_bill_strict_approval
                move.vendor_bill_requires_po = policy != "disabled"
                move.vendor_bill_requires_approval = bool(strict) or policy == "block"
                move.vendor_bill_approval_level_required = move._justech_amount_based_approval_level()
            if move.has_valid_purchase_order:
                move.vendor_bill_requires_po = False
                if not rule:
                    move.vendor_bill_requires_approval = False
                    move.vendor_bill_approval_level_required = "none"


    @api.depends(
        "move_type",
        "state",
        "has_valid_purchase_order",
        "vendor_bill_approval_state",
        "vendor_bill_requires_po",
        "vendor_bill_requires_approval",
        "vendor_bill_legacy_exempt",
        "company_id.vendor_bill_strict_approval",
        "company_id.vendor_bill_po_policy",
        "company_id.vendor_bill_approval_effective_from",
    )
    def _compute_vendor_bill_button_flags(self):
        for move in self:
            if move.move_type not in VENDOR_BILL_MOVE_TYPES or move.state != "draft":
                move.vendor_bill_show_confirm = True
                move.vendor_bill_show_submit_validation = False
                move.vendor_bill_show_resubmit = False
                move.vendor_bill_show_approver_actions = False
                move.vendor_bill_approved_without_po = False
                move.vendor_bill_reason_readonly = True
                continue
            strict = move._justech_strict_enabled()
            approved = move.vendor_bill_approval_state in ("approved", "legacy_approved")
            has_po = move.has_valid_purchase_order
            state = move.vendor_bill_approval_state
            move.vendor_bill_approved_without_po = bool(approved and not has_po)
            move.vendor_bill_reason_readonly = state not in ("draft", "returned")
            move.vendor_bill_show_approver_actions = state == "pending_validation"
            move.vendor_bill_show_resubmit = state in ("returned", "rejected")
            # Pre-effective bills: preserve original Confirm UX (no forced approval tray).
            if move.vendor_bill_legacy_exempt:
                move.vendor_bill_show_confirm = True
                move.vendor_bill_show_submit_validation = False
                move.vendor_bill_show_resubmit = False
                move.vendor_bill_show_approver_actions = False
                continue
            if not strict and (move.company_id.vendor_bill_po_policy or "disabled") != "block":
                move.vendor_bill_show_confirm = True
                move.vendor_bill_show_submit_validation = False
                continue
            if has_po:
                move.vendor_bill_show_confirm = True
                move.vendor_bill_show_submit_validation = False
            elif approved:
                # Prefer auto-post; Confirm only as fallback if still draft
                move.vendor_bill_show_confirm = True
                move.vendor_bill_show_submit_validation = False
            elif state == "pending_validation":
                move.vendor_bill_show_confirm = False
                move.vendor_bill_show_submit_validation = False
            elif state == "returned":
                move.vendor_bill_show_confirm = False
                move.vendor_bill_show_submit_validation = False
            elif state == "rejected":
                move.vendor_bill_show_confirm = False
                move.vendor_bill_show_submit_validation = False
            else:
                # draft without valid PO → only Enviar a aprobación
                move.vendor_bill_show_confirm = False
                move.vendor_bill_show_submit_validation = True

    def _compute_vendor_bill_approval_request_count(self):
        for move in self:
            if move.move_type not in VENDOR_BILL_MOVE_TYPES:
                move.vendor_bill_approval_request_count = 0
                continue
            has_request = bool(
                move.vendor_bill_submitted_by
                or move.vendor_bill_approver_id
                or move.vendor_bill_no_po_reason
                or move.vendor_bill_approval_state
                not in (False, "draft")
            )
            move.vendor_bill_approval_request_count = 1 if has_request else 0

    @api.depends(
        "vendor_bill_submitted_at",
        "vendor_bill_approval_state",
        "vendor_bill_approval_deadline",
    )
    def _compute_vendor_bill_approval_days_pending(self):
        now = fields.Datetime.now()
        for move in self:
            if (
                move.vendor_bill_approval_state == "pending_validation"
                and move.vendor_bill_submitted_at
            ):
                delta = now - move.vendor_bill_submitted_at
                move.vendor_bill_approval_days_pending = max(delta.days, 0)
            else:
                move.vendor_bill_approval_days_pending = 0
            move.vendor_bill_approval_overdue = bool(
                move.vendor_bill_approval_state == "pending_validation"
                and move.vendor_bill_approval_deadline
                and move.vendor_bill_approval_deadline < now
            )

    def _search_vendor_bill_approval_overdue(self, operator, value):
        now = fields.Datetime.now()
        overdue_domain = [
            ("vendor_bill_approval_state", "=", "pending_validation"),
            ("vendor_bill_approval_deadline", "!=", False),
            ("vendor_bill_approval_deadline", "<", now),
        ]
        if (operator in ("=", "==") and value) or (operator == "!=" and not value):
            return overdue_domain
        return [
            "|",
            ("vendor_bill_approval_state", "!=", "pending_validation"),
            "|",
            ("vendor_bill_approval_deadline", "=", False),
            ("vendor_bill_approval_deadline", ">=", now),
        ]

    def _justech_amount_based_approval_level(self):
        self.ensure_one()
        company = self.company_id
        amount = abs(self.amount_total_signed or self.amount_total or 0.0)
        fin = company.vendor_bill_amount_finance_limit or 25000.0
        mgmt = company.vendor_bill_amount_management_limit or 250000.0
        if amount <= fin:
            return "finance"
        if amount <= mgmt:
            return "management"
        return "dual"

    def _justech_strict_enabled(self):
        self.ensure_one()
        if not bool(self.company_id.vendor_bill_strict_approval):
            return False
        # Forward-only: documents created before the company effective datetime
        # keep the original flow (legacy_exempt).
        if self._justech_is_legacy_exempt():
            return False
        return True

    def _justech_is_legacy_exempt(self):
        """Technical compatibility: pre-effective bills keep original behavior."""
        self.ensure_one()
        if self.move_type not in VENDOR_BILL_MOVE_TYPES:
            return False
        effective = self.company_id.vendor_bill_approval_effective_from
        if not effective:
            return False
        created = self.create_date
        if not created:
            return True
        return created < effective

    @api.depends(
        "move_type",
        "create_date",
        "company_id",
        "company_id.vendor_bill_approval_effective_from",
    )
    def _compute_vendor_bill_legacy_exempt(self):
        for move in self:
            move.vendor_bill_legacy_exempt = bool(move._justech_is_legacy_exempt())

    def _justech_is_financially_approved(self):
        self.ensure_one()
        if self.move_type not in VENDOR_BILL_MOVE_TYPES:
            return True
        if not self._justech_strict_enabled():
            return True
        if self.vendor_bill_approval_state in ("approved", "legacy_approved"):
            return True
        # Con OC válida (o excepción) ya contabilizada: no exige bandeja de aprobación.
        if self.state == "posted" and (
            self.has_valid_purchase_order or self._justech_po_exception_ok()
        ):
            return True
        return False

    def _check_vendor_bill_approved_for_financial_processing(self, action_label=None):
        label = action_label or _("procesamiento financiero")
        for move in self:
            if move.move_type not in VENDOR_BILL_MOVE_TYPES:
                continue
            if not move._justech_strict_enabled():
                continue
            if move.company_id.vendor_bill_block_payment is False and label in (
                _("registro de pago"),
                _("creación de pagos"),
                _("propuesta de pagos"),
            ):
                # Still block if not posted/approved when company wants — defaults True
                pass
            if move._justech_is_financially_approved() and move.state == "posted":
                continue
            if not move._justech_is_financially_approved():
                move.message_post(
                    body=_(
                        "Intento bloqueado (%(action)s): estado %(state)s."
                    )
                    % {
                        "action": label,
                        "state": dict(APPROVAL_STATE_SELECTION).get(
                            move.vendor_bill_approval_state, move.vendor_bill_approval_state
                        ),
                    }
                )
                raise UserError(_(BLOCK_MSG))
            if move.state != "posted":
                raise UserError(_(BLOCK_MSG))

    def _justech_wf_write(self, vals):
        return self.with_context(justech_vendor_bill_workflow=True).write(vals)

    def write(self, vals):
        # Block manual/state bypass even for admin/su; only workflow/migration context allowed.
        if not self.env.context.get("justech_vendor_bill_workflow") and not self.env.context.get(
            "install_mode"
        ):
            if "vendor_bill_approval_state" in vals or "po_requirement_exception" in vals:
                raise AccessError(
                    _("No puede alterar el estado de aprobación ni marcar excepción manual.")
                )
        res = super().write(vals)
        if self.env.context.get("justech_skip_po_approval_cancel"):
            return res
        bills = self.filtered(lambda m: m.move_type in VENDOR_BILL_MOVE_TYPES)
        if bills and any(
            k in vals
            for k in ("invoice_line_ids", "partner_id", "company_id")
        ):
            bills.invalidate_recordset(
                ["has_valid_purchase_order", "related_purchase_order_ids", "related_purchase_order_count"]
            )
            bills._compute_related_purchase_orders()
            bills.with_context(justech_skip_po_approval_cancel=True)._justech_cancel_approval_request_due_to_po()
        return res

    def action_justech_view_related_purchase_orders(self):
        self.ensure_one()
        orders = self.related_purchase_order_ids
        if not orders:
            return False
        action = {
            "type": "ir.actions.act_window",
            "name": _("Órdenes de Compra relacionadas"),
            "res_model": "purchase.order",
            "view_mode": "list,form",
            "domain": [("id", "in", orders.ids)],
        }
        if len(orders) == 1:
            action.update({"view_mode": "form", "res_id": orders.id})
        return action

    def action_justech_view_approval_request(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Aprobación"),
            "res_model": "account.move",
            "res_id": self.id,
            "view_mode": "form",
            "views": [
                (
                    self.env.ref(
                        "justech_vendor_bill_po_control.view_move_form_vendor_bill_approval_consult"
                    ).id,
                    "form",
                )
            ],
            "target": "new",
        }

    def action_vendor_bill_open_submit_wizard(self):
        self.ensure_one()
        if not isinstance(self.id, int):
            raise UserError(_("Primero debe guardar la factura antes de enviarla para aprobación."))
        if self.state != "draft":
            raise UserError(_("Solo borradores pueden enviarse para aprobación."))
        self.invalidate_recordset()
        self._compute_related_purchase_orders()
        if self.has_valid_purchase_order:
            raise UserError(
                _("Esta factura ya tiene una Orden de Compra válida. Use Confirmar.")
            )
        if not self.partner_id:
            raise UserError(_("Debe indicar el proveedor antes de enviar para aprobación."))
        if (
            "justech_do_expense_type_id" in self._fields
            and self.company_id.vendor_bill_require_classification
            and not self.justech_do_expense_type_id
        ):
            raise UserError(_("Debe indicar el Tipo de costos y gastos antes de enviar para aprobación."))
        return {
            "type": "ir.actions.act_window",
            "name": _("Enviar a aprobación"),
            "res_model": "vendor.bill.approval.request.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "active_id": self.id,
                "active_model": "account.move",
                "default_move_id": self.id,
            },
        }

    def action_vendor_bill_open_decision_wizard(self):
        self.ensure_one()
        decision = self.env.context.get("default_decision") or "approve"
        titles = {
            "approve": _("Aprobar factura"),
            "reject": _("Rechazar factura"),
            "return": _("Devolver factura"),
        }
        return {
            "type": "ir.actions.act_window",
            "name": titles.get(decision, _("Decisión")),
            "res_model": "vendor.bill.approval.decision.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "active_id": self.id,
                "active_model": "account.move",
                "default_move_id": self.id,
                "default_decision": decision,
            },
        }

    def _justech_schedule_approval_activity(self, user=None):
        """Schedule review activity for the assigned approver (or legacy group fallback)."""
        for move in self:
            assignee = user or move.vendor_bill_approver_id
            if not assignee:
                # Legacy fallback: finance group (first users)
                group = self.env.ref(ah.XMLID_FINANCE, raise_if_not_found=False)
                users = group.all_user_ids if group else self.env["res.users"]
                users = users.filtered(
                    lambda u: ah.user_has_company_access(u, move.company_id)
                    and u != move.vendor_bill_submitted_by
                )
                assignee = users[:1]
            if not assignee:
                continue
            try:
                move.activity_unlink([ah.XMLID_ACTIVITY, "mail.mail_activity_data_todo"])
            except Exception:  # noqa: BLE001
                pass
            note_parts = [
                _("Proveedor: %s") % (move.partner_id.display_name or "-"),
                _("Importe: %(amount)s %(currency)s")
                % {
                    "amount": move.amount_total,
                    "currency": move.currency_id.name or "",
                },
                _("Motivo sin OC: %s")
                % (move.po_missing_reason or move.vendor_bill_no_po_reason or "-"),
            ]
            deadline = move.vendor_bill_approval_deadline or ah.approval_deadline(move.company_id)
            act_xmlid = ah.XMLID_ACTIVITY
            if not self.env.ref(act_xmlid, raise_if_not_found=False):
                act_xmlid = "mail.mail_activity_data_todo"
            move.activity_schedule(
                act_type_xmlid=act_xmlid,
                user_id=assignee.id,
                date_deadline=fields.Datetime.to_datetime(deadline).date()
                if deadline
                else False,
                summary=_("Aprobar factura %s") % (move.name or move.display_name or _("borrador")),
                note="<br/>".join(note_parts),
            )

    def _justech_notify_approver(self, user):
        """Internal inbox notification + optional email; never blocks submit."""
        self.ensure_one()
        if not user:
            return False
        company = self.company_id
        # Follower (avoid duplicates)
        partner = user.partner_id
        if partner and partner not in self.message_partner_ids:
            self.message_subscribe(partner_ids=partner.ids)
        warning = False
        if company.vendor_bill_notify_internal:
            self.message_post(
                body=_(
                    "Solicitud de aprobación asignada a %(approver)s."
                )
                % {"approver": user.display_name},
                partner_ids=partner.ids if partner else [],
                subtype_xmlid="mail.mt_note",
            )
        if company.vendor_bill_notify_email:
            email = (user.email or user.partner_id.email or "").strip()
            if not email:
                warning = _(
                    "El aprobador fue notificado en Odoo, pero no tiene correo electrónico configurado."
                )
            else:
                template = self.env.ref(ah.XMLID_MAIL, raise_if_not_found=False)
                if template:
                    try:
                        template.send_mail(self.id, force_send=False, raise_exception=False)
                    except Exception:  # noqa: BLE001
                        warning = _(
                            "No se pudo encolar el correo al aprobador; la solicitud permanece en Odoo."
                        )
        return warning

    def _justech_notify_submitter(self, body):
        self.ensure_one()
        partner = self.vendor_bill_submitted_by.partner_id if self.vendor_bill_submitted_by else False
        partner_ids = partner.ids if partner else []
        self.message_post(body=body, partner_ids=partner_ids, subtype_xmlid="mail.mt_comment")

    def _justech_close_approval_activities(self):
        for move in self:
            try:
                move.activity_feedback([ah.XMLID_ACTIVITY, "mail.mail_activity_data_todo"])
            except Exception:  # noqa: BLE001
                try:
                    move.activity_unlink([ah.XMLID_ACTIVITY, "mail.mail_activity_data_todo"])
                except Exception:  # noqa: BLE001
                    pass

    def _justech_cancel_approval_request_due_to_po(self):
        """If a valid PO appears while pending/returned/rejected, return to normal flow."""
        for move in self:
            if move.move_type not in VENDOR_BILL_MOVE_TYPES:
                continue
            if not move.has_valid_purchase_order:
                continue
            if move.vendor_bill_approval_state not in (
                "pending_validation",
                "returned",
                "rejected",
            ):
                continue
            move._justech_close_approval_activities()
            move._justech_wf_write(
                {
                    "vendor_bill_approval_state": "draft",
                    "vendor_bill_submitted_by": False,
                    "vendor_bill_submitted_at": False,
                    "vendor_bill_approver_id": False,
                    "vendor_bill_finance_approver_id": False,
                    "vendor_bill_mgmt_approver_id": False,
                    "vendor_bill_approval_deadline": False,
                }
            )
            move.message_post(
                body=_(
                    "Solicitud de aprobación cancelada automáticamente: "
                    "se vinculó una Orden de Compra válida."
                )
            )

    def action_justech_approve_po_exception(self):
        self.ensure_one()
        if self._justech_strict_enabled():
            raise UserError(
                _(
                    "En modo estricto no se permite marcar excepción manual. "
                    "Use Enviar a Validación / Aprobar, o configure una regla."
                )
            )
        if not self.env.user.has_group("account.group_account_manager"):
            raise UserError(_("Solo Finanzas (Account Manager) puede aprobar excepciones OC."))
        if not self.po_exception_reason:
            raise UserError(_("Debe indicar el motivo de la excepción OC."))
        self._justech_wf_write(
            {
                "po_requirement_exception": True,
                "po_exception_approved_by": self.env.user.id,
                "po_exception_approved_at": fields.Datetime.now(),
            }
        )
        self.message_post(
            body=_(
                "Excepción de requisito OC aprobada por %(user)s.<br/>Motivo: %(reason)s"
            )
            % {"user": self.env.user.display_name, "reason": self.po_exception_reason}
        )
        return True

    def action_vendor_bill_submit_validation(self):
        for move in self:
            if move.move_type not in VENDOR_BILL_MOVE_TYPES:
                continue
            if move.state != "draft":
                raise UserError(_("Solo borradores pueden enviarse a validación."))
            if "justech_do_expense_type_id" in move._fields and not move.justech_do_expense_type_id:
                if move.company_id.vendor_bill_require_classification:
                    raise UserError(_("Debe indicar el Tipo de costos y gastos antes de enviar a validación."))
            needs_po = move.vendor_bill_requires_po and not move.has_valid_purchase_order
            if needs_po and not (move.po_missing_reason or move.vendor_bill_no_po_reason):
                raise UserError(_(MISSING_REASON_MSG))
            rule = move.vendor_bill_applied_rule_id
            if rule and rule.require_attachment:
                attachments = self.env["ir.attachment"].search(
                    [("res_model", "=", "account.move"), ("res_id", "=", move.id)], limit=1
                )
                if not attachments:
                    raise UserError(_("La regla exige un soporte adjunto antes de validar."))
            if not move.vendor_bill_requires_approval and not needs_po:
                move._justech_wf_write(
                    {
                        "vendor_bill_approval_state": "approved",
                        "vendor_bill_approved_by": self.env.user.id,
                        "vendor_bill_approved_at": fields.Datetime.now(),
                        "vendor_bill_submitted_by": self.env.user.id,
                        "vendor_bill_submitted_at": fields.Datetime.now(),
                    }
                )
                move.message_post(body=_("Validación automática: cumple reglas configuradas."))
                continue
            move._justech_wf_write(
                {
                    "vendor_bill_approval_state": "pending_validation",
                    "vendor_bill_submitted_by": self.env.user.id,
                    "vendor_bill_submitted_at": fields.Datetime.now(),
                    "vendor_bill_rejected_by": False,
                    "vendor_bill_rejected_at": False,
                    "vendor_bill_returned_by": False,
                    "vendor_bill_returned_at": False,
                    "vendor_bill_finance_approved_by": False,
                    "vendor_bill_finance_approved_at": False,
                    "vendor_bill_mgmt_approved_by": False,
                    "vendor_bill_mgmt_approved_at": False,
                }
            )
            move.message_post(
                body=_(
                    "Enviada para aprobación por %(user)s. Tipo costos/gastos: %(exp)s. "
                    "Nivel: %(level)s. Regla: %(rule)s. Motivo sin OC: %(reason)s."
                )
                % {
                    "user": self.env.user.display_name,
                    "exp": (
                        move.justech_do_expense_type_id.display_name
                        if "justech_do_expense_type_id" in move._fields and move.justech_do_expense_type_id
                        else "-"
                    ),
                    "level": move.vendor_bill_approval_level_required or "-",
                    "rule": move.vendor_bill_applied_rule_id.display_name or _("(sin regla)"),
                    "reason": move.po_missing_reason or move.vendor_bill_no_po_reason or "-",
                }
            )
        return True

    def action_vendor_bill_resubmit(self):
        return self.action_vendor_bill_open_submit_wizard()

    def action_vendor_bill_open_reassign_wizard(self):
        self.ensure_one()
        if not self.company_id.vendor_bill_allow_reassign:
            raise UserError(_("La reasignación está deshabilitada para esta compañía."))
        if self.vendor_bill_approval_state != "pending_validation":
            raise UserError(_("Solo se pueden reasignar solicitudes pendientes."))
        return {
            "type": "ir.actions.act_window",
            "name": _("Reasignar aprobación"),
            "res_model": "vendor.bill.approval.reassign.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "active_id": self.id,
                "active_model": "account.move",
                "default_move_id": self.id,
            },
        }

    def _justech_assert_can_approve(self):
        """Return role for level logic; also enforce assigned-approver restriction."""
        user = self.env.user
        company = self.company_id
        unauthorized_msg = _(
            "No tiene permisos para aprobar facturas de proveedor sin Orden de Compra. "
            "Esta acción está limitada a los Administradores de Contabilidad y "
            "aprobadores autorizados."
        )
        # Role for dual/level checks
        if user.has_group("base.group_system"):
            role = "admin"
        elif user.has_group(ah.XMLID_MGMT):
            role = "management"
        elif user.has_group(ah.XMLID_FINANCE) or user.has_group("account.group_account_manager"):
            role = "finance"
        elif user.has_group(ah.XMLID_APPROVER):
            role = "finance"
        else:
            raise AccessError(unauthorized_msg)

        # Assigned-approver gate (legacy bills without assignee keep group-based access)
        assigned = self.vendor_bill_approver_id
        if assigned:
            allowed = user == assigned
            substitute = company.vendor_bill_default_substitute_id
            if substitute and user == substitute:
                allowed = True
            if (
                company.vendor_bill_allow_admin_override
                and user.has_group("base.group_system")
            ):
                allowed = True
            if user.has_group("account.group_account_manager") and company.vendor_bill_allow_admin_override:
                allowed = True
            if not allowed:
                raise AccessError(
                    _(
                        "Esta solicitud está asignada a %(name)s. "
                        "No tiene permiso para aprobarla."
                    )
                    % {"name": assigned.display_name}
                )
        return role

    def action_vendor_bill_approve(self):
        for move in self:
            if move.vendor_bill_approval_state not in ("pending_validation", "returned"):
                raise UserError(_("Solo facturas pendientes o devueltas pueden aprobarse."))
            role = move._justech_assert_can_approve()
            submitter = move.vendor_bill_submitted_by
            if submitter and submitter == self.env.user:
                may_self = (
                    role == "admin"
                    or self.env.user.has_group("base.group_system")
                    or self.env.user.has_group("account.group_account_manager")
                    or bool(move.company_id.vendor_bill_allow_self_approval)
                )
                if not may_self:
                    raise AccessError(
                        _("No puede autoaprobar una factura que usted envió a validación.")
                    )
            level = move.vendor_bill_approval_level_required or "finance"
            if level == "dual":
                vals = {}
                if role in ("finance", "admin") and not move.vendor_bill_finance_approved_by:
                    if (
                        move.company_id.vendor_bill_require_sod
                        and move.vendor_bill_mgmt_approved_by
                        and move.vendor_bill_mgmt_approved_by == self.env.user
                        and role != "admin"
                    ):
                        raise AccessError(
                            _("Separación de funciones: no puede completar ambos niveles.")
                        )
                    vals.update(
                        {
                            "vendor_bill_finance_approved_by": self.env.user.id,
                            "vendor_bill_finance_approved_at": fields.Datetime.now(),
                        }
                    )
                if role in ("management", "admin") and not move.vendor_bill_mgmt_approved_by:
                    if (
                        move.company_id.vendor_bill_require_sod
                        and move.vendor_bill_finance_approved_by
                        and move.vendor_bill_finance_approved_by == self.env.user
                        and role != "admin"
                    ):
                        raise AccessError(
                            _("Separación de funciones: no puede completar ambos niveles.")
                        )
                    vals.update(
                        {
                            "vendor_bill_mgmt_approved_by": self.env.user.id,
                            "vendor_bill_mgmt_approved_at": fields.Datetime.now(),
                        }
                    )
                if vals:
                    move._justech_wf_write(vals)
                move.invalidate_recordset()
                if move.vendor_bill_finance_approved_by and move.vendor_bill_mgmt_approved_by:
                    move._justech_close_approval_activities()
                    move._justech_wf_write(
                        {
                            "vendor_bill_approval_state": "approved",
                            "vendor_bill_approved_by": self.env.user.id,
                            "vendor_bill_approved_at": fields.Datetime.now(),
                        }
                    )
                    move.message_post(body=_("Doble aprobación completada. Factura Aprobada."))
                    move._justech_notify_submitter(
                        _("Su factura %(bill)s fue aprobada.")
                        % {"bill": move.display_name}
                    )
                    move._justech_finalize_approval_and_post()
                else:
                    # Advance to next assigned approver when finance just signed
                    if move.vendor_bill_finance_approved_by and not move.vendor_bill_mgmt_approved_by:
                        next_user = move.vendor_bill_mgmt_approver_id or ah.default_approver_for_level(
                            move.company_id, "management"
                        )
                        if next_user:
                            move._justech_wf_write(
                                {
                                    "vendor_bill_approver_id": next_user.id,
                                    "vendor_bill_approval_deadline": ah.approval_deadline(
                                        move.company_id
                                    ),
                                }
                            )
                            move._justech_schedule_approval_activity(next_user)
                            move._justech_notify_approver(next_user)
                    move.message_post(
                        body=_("Aprobación parcial registrada (%(role)s). Falta segundo nivel.")
                        % {"role": role}
                    )
                continue
            if level == "management" and role == "finance":
                raise AccessError(_("Esta factura requiere aprobación de Gerencia."))
            move._justech_close_approval_activities()
            move._justech_wf_write(
                {
                    "vendor_bill_approval_state": "approved",
                    "vendor_bill_approved_by": self.env.user.id,
                    "vendor_bill_approved_at": fields.Datetime.now(),
                }
            )
            move.message_post(
                body=_("Factura aprobada por %(user)s (nivel %(level)s).")
                % {"user": self.env.user.display_name, "level": level}
            )
            move._justech_notify_submitter(
                _("Su factura %(bill)s fue aprobada por %(user)s.")
                % {"bill": move.display_name, "user": self.env.user.display_name}
            )
            move._justech_finalize_approval_and_post()
        return True

    def _justech_apply_no_po_classification(self):
        """Classify approved bills without PO as Compra directa / Gasto interno."""
        for move in self:
            if move.move_type not in VENDOR_BILL_MOVE_TYPES:
                continue
            if move.has_valid_purchase_order:
                continue
            if move.vendor_bill_classification:
                continue
            choice = move.company_id.vendor_bill_no_po_auto_classification or "direct"
            if choice not in ("direct", "internal"):
                choice = "direct"
            move._justech_wf_write({"vendor_bill_classification": choice})
            move.message_post(
                body=_(
                    "Clasificación automática sin OC: %(label)s."
                )
                % {
                    "label": dict(move._fields["vendor_bill_classification"].selection).get(
                        choice, choice
                    ),
                }
            )

    def _justech_missing_fiscal_labels(self):
        """Return human labels for missing required fiscal/accounting fields."""
        self.ensure_one()
        missing = []
        if not self.partner_id:
            missing.append(_("proveedor"))
        if not self.journal_id:
            missing.append(_("diario"))
        if not self.invoice_date:
            missing.append(_("fecha de factura"))
        if not self.date:
            missing.append(_("fecha contable"))
        if not self.currency_id:
            missing.append(_("moneda"))
        # Dominican localization / NCF fields when present on the model.
        ncf_fields = (
            "l10n_latam_document_number",
            "l10n_do_ncf",
            "justech_do_ncf",
            "justech_ncf",
            "l10n_do_fiscal_number",
        )
        ncf_present = any(
            fname in self._fields and self[fname] for fname in ncf_fields
        )
        if not ncf_present and any(fname in self._fields for fname in ncf_fields):
            missing.append(_("NCF"))
        doc_type_fields = ("l10n_latam_document_type_id", "justech_do_document_type_id")
        doc_present = any(
            fname in self._fields and self[fname] for fname in doc_type_fields
        )
        if not doc_present and any(fname in self._fields for fname in doc_type_fields):
            missing.append(_("tipo de comprobante"))
        for fname, label in (
            ("justech_do_expense_type_id", _("campos fiscales de la localización dominicana")),
            ("l10n_do_expense_type_id", _("campos fiscales de la localización dominicana")),
        ):
            if fname not in self._fields:
                continue
            if not self[fname]:
                if label not in missing:
                    missing.append(label)
        return missing

    def _justech_humanize_post_block_error(self, err):
        """Build a clear Spanish fiscal alert; never expose traceback/tech names."""
        self.ensure_one()
        raw = ""
        if isinstance(err, Exception):
            raw = err.args[0] if err.args else str(err)
        else:
            raw = str(err or "")
        raw_l = (raw or "").lower()
        hinted = []
        for keys, label in _FISCAL_ERROR_HINTS:
            if any(k in raw_l for k in keys):
                if label not in hinted:
                    hinted.append(label)
        detected = [str(x) for x in self._justech_missing_fiscal_labels()]
        labels = []
        for item in hinted + detected:
            if item not in labels:
                labels.append(item)
        msg = _(FISCAL_POST_ALERT_INTRO)
        if labels:
            msg = "%s\n%s" % (
                msg,
                _("Datos a completar: %s.") % ", ".join(labels),
            )
        return msg

    def _justech_finalize_approval_and_post(self):
        """After approval: classify + standard action_post() (no parallel accounting)."""
        for move in self:
            move._justech_apply_no_po_classification()
            if move.state != "draft":
                continue
            try:
                move.with_context(justech_vendor_bill_auto_post=True).action_post()
                move._justech_wf_write({"vendor_bill_fiscal_post_alert": ""})
                move.message_post(
                    body=_(
                        "Contabilización automática tras aprobación "
                        "(flujo estándar de Odoo / action_post)."
                    )
                )
                move._justech_notify_submitter(
                    _("Su factura %(bill)s fue aprobada y contabilizada.")
                    % {"bill": move.display_name}
                )
            except UserError as err:
                alert = move._justech_humanize_post_block_error(err)
                move._justech_wf_write({"vendor_bill_fiscal_post_alert": alert})
                move.message_post(body=alert)
            except Exception:  # noqa: BLE001
                alert = move._justech_humanize_post_block_error(
                    UserError(_("datos fiscales incompletos"))
                )
                move._justech_wf_write({"vendor_bill_fiscal_post_alert": alert})
                move.message_post(body=alert)

    def action_vendor_bill_reject(self):
        for move in self:
            move._justech_assert_can_approve()
            if not move.vendor_bill_reject_reason:
                raise UserError(_("El motivo de rechazo es obligatorio."))
            move._justech_close_approval_activities()
            # Keep rejected state for bandeja filters; bill remains editable (draft accounting).
            move._justech_wf_write(
                {
                    "vendor_bill_approval_state": "rejected",
                    "vendor_bill_rejected_by": self.env.user.id,
                    "vendor_bill_rejected_at": fields.Datetime.now(),
                    "vendor_bill_fiscal_post_alert": "",
                }
            )
            body = _(
                "Factura rechazada por %(user)s y devuelta a borrador editable. Motivo: %(reason)s"
            ) % {
                "user": self.env.user.display_name,
                "reason": move.vendor_bill_reject_reason,
            }
            move.message_post(body=body)
            move._justech_notify_submitter(body)
        return True

    def action_vendor_bill_return(self):
        for move in self:
            move._justech_assert_can_approve()
            if not move.vendor_bill_return_reason:
                raise UserError(_("El motivo de devolución es obligatorio."))
            move._justech_close_approval_activities()
            move._justech_wf_write(
                {
                    "vendor_bill_approval_state": "returned",
                    "vendor_bill_returned_by": self.env.user.id,
                    "vendor_bill_returned_at": fields.Datetime.now(),
                    "vendor_bill_finance_approved_by": False,
                    "vendor_bill_finance_approved_at": False,
                    "vendor_bill_mgmt_approved_by": False,
                    "vendor_bill_mgmt_approved_at": False,
                }
            )
            body = _(
                "Devuelta para corrección por %(user)s. Motivo: %(reason)s"
            ) % {
                "user": self.env.user.display_name,
                "reason": move.vendor_bill_return_reason,
            }
            move.message_post(body=body)
            # Activity for submitter to correct (feeds future Centro de Trabajo / Mis Pendientes)
            submitter = move.vendor_bill_submitted_by
            if submitter:
                act_xmlid = ah.XMLID_ACTIVITY
                if not self.env.ref(act_xmlid, raise_if_not_found=False):
                    act_xmlid = "mail.mail_activity_data_todo"
                move.activity_schedule(
                    act_type_xmlid=act_xmlid,
                    user_id=submitter.id,
                    summary=_("Corregir factura devuelta: %s") % (move.display_name,),
                    note=move.vendor_bill_return_reason or "",
                )
            move._justech_notify_submitter(body)
        return True

    def _justech_check_vendor_bill_po_requirement(self):
        for move in self:
            if move.move_type not in VENDOR_BILL_MOVE_TYPES:
                continue
            if move.move_type == "in_refund" and move.reversed_entry_id:
                continue
            # Pre-effective documents keep the original flow (no new blocks).
            if move._justech_is_legacy_exempt():
                continue
            if move._justech_strict_enabled():
                if move.vendor_bill_approval_state in ("pending_validation", "rejected", "returned"):
                    raise UserError(_(BLOCK_MSG))
                if move.vendor_bill_approval_state == "draft":
                    if move.vendor_bill_requires_approval or (
                        move.vendor_bill_requires_po and not move.has_valid_purchase_order
                    ):
                        move._justech_wf_write({"vendor_bill_approval_state": "pending_validation"})
                        raise UserError(_(NO_PO_ALERT))
                    continue
                if move.vendor_bill_approval_state not in ("approved", "legacy_approved"):
                    raise UserError(_(BLOCK_MSG))
                continue
            policy = move.company_id.vendor_bill_po_policy or "disabled"
            if policy == "disabled":
                continue
            if move.has_valid_purchase_order or move._justech_po_exception_ok():
                continue
            msg = _(
                "No puede contabilizar esta factura porque la compañía exige "
                "una Orden de Compra asociada."
            )
            if policy == "warning":
                move.message_post(
                    body=_("Advertencia OC: la factura se contabiliza sin OC válida. %(detail)s")
                    % {"detail": msg}
                )
                continue
            if policy == "block":
                raise UserError(msg)

    def _justech_lock_purchase_lines_for_post(self):
        """Transactional lock to prevent concurrent double-billing of the same PO lines."""
        line_ids = self.mapped("invoice_line_ids.purchase_line_id").ids
        if not line_ids:
            return
        self.env.cr.execute(
            "SELECT id FROM purchase_order_line WHERE id = ANY(%s) FOR UPDATE",
            [list(line_ids)],
        )

    def _justech_assert_po_qty_still_available(self):
        """After locking, ensure quantities do not exceed remaining to-invoice (+ this bill)."""
        from odoo.tools import float_compare

        precision = self.env["decimal.precision"].precision_get("Product Unit of Measure")
        for move in self.filtered(lambda m: m.move_type in VENDOR_BILL_MOVE_TYPES):
            for aml in move.invoice_line_ids.filtered(lambda l: l.purchase_line_id and not l.display_type):
                po_line = aml.purchase_line_id
                # qty_to_invoice excludes posted invoices; draft siblings still reserve.
                reserved = move._justech_po_line_draft_reserved_qty(po_line, exclude_move=move)
                free = po_line.qty_to_invoice - reserved
                if float_compare(aml.quantity, free, precision_digits=precision) > 0:
                    raise UserError(
                        _(
                            "La línea de OC %(po)s no tiene cantidad disponible suficiente "
                            "(solicitado %(qty)s, disponible %(free)s). "
                            "Puede estar reservada por otra factura activa."
                        )
                        % {
                            "po": po_line.order_id.display_name,
                            "qty": aml.quantity,
                            "free": free,
                        }
                    )

    def action_post(self):
        bills = self.filtered(lambda m: m.move_type in VENDOR_BILL_MOVE_TYPES)
        if bills:
            bills._justech_lock_purchase_lines_for_post()
            for move in bills:
                for po in move._justech_valid_purchase_orders():
                    if (
                        move.partner_id
                        and po.partner_id.commercial_partner_id
                        != move.partner_id.commercial_partner_id
                    ):
                        raise UserError(
                            _("La Orden de Compra seleccionada pertenece a un proveedor diferente.")
                        )
            bills._justech_assert_po_qty_still_available()
        self._justech_check_vendor_bill_po_requirement()
        res = super().action_post()
        for move in bills:
            if move.vendor_bill_fiscal_post_alert:
                move._justech_wf_write({"vendor_bill_fiscal_post_alert": ""})
            if not move._justech_strict_enabled():
                continue
            # OC / excepción: marcar aprobada tras post para alinear barra UX y pagos.
            if (
                move.vendor_bill_approval_state == "draft"
                and (move.has_valid_purchase_order or move._justech_po_exception_ok())
            ):
                move._justech_wf_write({"vendor_bill_approval_state": "approved"})
                move.message_post(
                    body=_(
                        "Factura contabilizada con Orden de Compra válida "
                        "(sin bandeja de aprobación)."
                    )
                )
            elif move.vendor_bill_approval_state == "approved":
                move.message_post(body=_("Factura contabilizada tras aprobación."))
        return res

    def action_register_payment(self):
        bills = self.filtered(lambda m: m.move_type in VENDOR_BILL_MOVE_TYPES)
        if bills:
            bills._check_vendor_bill_approved_for_financial_processing(_("registro de pago"))
            for move in bills:
                if move._justech_strict_enabled() and move.state != "posted":
                    raise UserError(_(BLOCK_MSG))
        return super().action_register_payment()
