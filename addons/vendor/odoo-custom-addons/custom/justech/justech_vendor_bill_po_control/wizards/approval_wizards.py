# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError, AccessError

from odoo.addons.justech_vendor_bill_po_control.models import approval_helpers as ah


class VendorBillApprovalRequestWizard(models.TransientModel):
    _name = "vendor.bill.approval.request.wizard"
    _description = "Enviar factura proveedor para aprobación (sin OC)"

    move_id = fields.Many2one("account.move", string="Factura", required=True, readonly=True)
    company_id = fields.Many2one(related="move_id.company_id", string="Empresa", readonly=True)
    partner_id = fields.Many2one(related="move_id.partner_id", string="Proveedor", readonly=True)
    amount_total = fields.Monetary(related="move_id.amount_total", string="Total", readonly=True)
    currency_id = fields.Many2one(related="move_id.currency_id", readonly=True)
    expense_type_id = fields.Many2one(
        related="move_id.justech_do_expense_type_id",
        readonly=True,
        string="Tipo de costos y gastos",
    )
    related_purchase_order_ids = fields.Many2many(
        related="move_id.related_purchase_order_ids",
        readonly=True,
        string="Órdenes de Compra relacionadas",
    )
    has_valid_purchase_order = fields.Boolean(related="move_id.has_valid_purchase_order", readonly=True)
    approval_level_required = fields.Selection(
        related="move_id.vendor_bill_approval_level_required",
        readonly=True,
        string="Nivel requerido",
    )
    approver_id = fields.Many2one(
        "res.users",
        string="Aprobador",
        # Obligatorio en vista/action_submit (no SQL NOT NULL) para poder abrir el wizard vacío.
        domain="[]",
        help="Usuario autorizado que debe revisar y decidir esta solicitud.",
    )
    finance_approver_id = fields.Many2one(
        "res.users",
        string="Aprobador Finanzas",
        help="Obligatorio cuando el nivel requerido es doble aprobación.",
    )
    management_approver_id = fields.Many2one(
        "res.users",
        string="Aprobador Gerencia",
        help="Obligatorio cuando el nivel requerido es doble aprobación.",
    )
    po_missing_reason = fields.Text(
        string="Motivo de no tener Orden de Compra",
    )
    purchase_justification = fields.Text(string="Justificación de la compra/gasto")
    additional_comment = fields.Text(string="Comentario adicional")
    attachment_ids = fields.Many2many(
        "ir.attachment",
        string="Adjuntos / soportes",
        help="Soportes de la solicitud de aprobación.",
    )
    show_dual_approvers = fields.Boolean(compute="_compute_show_dual_approvers")

    @api.depends("approval_level_required")
    def _compute_show_dual_approvers(self):
        for wiz in self:
            wiz.show_dual_approvers = wiz.approval_level_required == "dual"

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        move = self.env["account.move"].browse(self.env.context.get("active_id"))
        if move:
            move.invalidate_recordset()
            move._compute_vendor_bill_evaluation()
            res["move_id"] = move.id
            res["po_missing_reason"] = move.po_missing_reason or move.vendor_bill_no_po_reason or False
            res["purchase_justification"] = move.vendor_bill_approval_notes or False
            level = move.vendor_bill_approval_level_required or "finance"
            company = move.company_id
            if level == "dual":
                fin = company.vendor_bill_default_finance_approver_id
                mgmt = company.vendor_bill_default_mgmt_approver_id
                res["finance_approver_id"] = fin.id if fin else False
                res["management_approver_id"] = mgmt.id if mgmt else False
                res["approver_id"] = fin.id if fin else False
            else:
                default = ah.default_approver_for_level(company, level)
                if default and ah.user_meets_approval_level(default, level):
                    res["approver_id"] = default.id
        return res

    @api.onchange("company_id", "approval_level_required", "move_id")
    def _onchange_approver_domain(self):
        level = self.approval_level_required or "finance"
        company = self.company_id
        domain = ah.authorized_approver_domain(self.env, company, level=level)
        fin_domain = ah.authorized_approver_domain(self.env, company, level="finance")
        mgmt_domain = ah.authorized_approver_domain(self.env, company, level="management")
        return {
            "domain": {
                "approver_id": domain,
                "finance_approver_id": fin_domain,
                "management_approver_id": mgmt_domain,
            }
        }

    def _justech_validate_approvers(self):
        self.ensure_one()
        level = self.approval_level_required or "finance"
        if level == "dual":
            if not self.finance_approver_id or not self.management_approver_id:
                raise UserError(
                    _("Doble aprobación: debe indicar aprobador de Finanzas y de Gerencia.")
                )
            if not ah.user_meets_approval_level(self.finance_approver_id, "finance"):
                raise UserError(_("El aprobador de Finanzas no tiene el nivel autorizado."))
            if not ah.user_meets_approval_level(self.management_approver_id, "management"):
                raise UserError(_("El aprobador de Gerencia no tiene el nivel autorizado."))
            if (
                self.move_id.company_id.vendor_bill_require_sod
                and self.finance_approver_id == self.management_approver_id
            ):
                raise UserError(
                    _(
                        "Separación de funciones: Finanzas y Gerencia deben ser personas distintas."
                    )
                )
            for user in (self.finance_approver_id, self.management_approver_id):
                if not ah.user_has_company_access(user, self.company_id):
                    raise UserError(
                        _("El aprobador %(u)s no tiene acceso a la empresa de la factura.")
                        % {"u": user.display_name}
                    )
            return
        if not self.approver_id:
            raise UserError(_("Debe seleccionar un Aprobador."))
        check_level = "management" if level == "management" else "finance"
        if not ah.user_meets_approval_level(self.approver_id, check_level):
            raise UserError(
                _(
                    "El aprobador seleccionado no cumple el nivel requerido (%(level)s)."
                )
                % {"level": level}
            )
        if not ah.user_has_company_access(self.approver_id, self.company_id):
            raise UserError(_("El aprobador no tiene acceso a la empresa de la factura."))

    def action_submit(self):
        self.ensure_one()
        move = self.move_id
        if not isinstance(move.id, int):
            raise UserError(_("Primero debe guardar la factura antes de enviarla para aprobación."))
        if move.state != "draft":
            raise UserError(_("Solo borradores pueden enviarse para aprobación."))
        move.invalidate_recordset()
        move._compute_related_purchase_orders()
        move._compute_vendor_bill_evaluation()
        if move.has_valid_purchase_order:
            raise UserError(
                _(
                    "Esta factura ya tiene una Orden de Compra válida. "
                    "Cierre este asistente y use Confirmar."
                )
            )
        move.env.cr.execute(
            """
            SELECT COUNT(*) FROM account_move_line
            WHERE move_id = %s
              AND (display_type IS NULL OR display_type IN ('', 'product'))
              AND coalesce(tax_line_id, 0) = 0
            """,
            [move.id],
        )
        if not move.env.cr.fetchone()[0]:
            raise UserError(_("Debe agregar líneas a la factura antes de enviar para aprobación."))
        if not self.po_missing_reason or not str(self.po_missing_reason).strip():
            raise UserError(_("Debe indicar el Motivo de no tener Orden de Compra."))
        self._justech_validate_approvers()

        level = move.vendor_bill_approval_level_required or "finance"
        if level == "dual":
            current = self.finance_approver_id
            fin_id = self.finance_approver_id.id
            mgmt_id = self.management_approver_id.id
        else:
            current = self.approver_id
            fin_id = current.id if level != "management" else False
            mgmt_id = current.id if level == "management" else (
                self.management_approver_id.id if self.management_approver_id else False
            )
            if level == "finance":
                mgmt_id = False

        notes_parts = [
            self.purchase_justification and self.purchase_justification.strip(),
            self.additional_comment and self.additional_comment.strip(),
        ]
        deadline = ah.approval_deadline(move.company_id)
        move.write(
            {
                "vendor_bill_no_po_reason": self.po_missing_reason.strip(),
                "vendor_bill_approval_notes": "\n".join(p for p in notes_parts if p) or False,
                "vendor_bill_approver_id": current.id,
                "vendor_bill_finance_approver_id": fin_id or False,
                "vendor_bill_mgmt_approver_id": mgmt_id or False,
                "vendor_bill_approval_deadline": deadline,
            }
        )
        if self.attachment_ids:
            self.attachment_ids.write({"res_model": "account.move", "res_id": move.id})
        move.action_vendor_bill_submit_validation()
        move.message_post(
            body=_(
                "%(user)s envió esta factura para aprobación de %(approver)s."
            )
            % {
                "user": self.env.user.display_name,
                "approver": current.display_name,
            }
        )
        move._justech_schedule_approval_activity(current)
        warning = move._justech_notify_approver(current)
        action = {"type": "ir.actions.act_window_close"}
        if warning:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("Solicitud enviada"),
                    "message": warning,
                    "type": "warning",
                    "sticky": False,
                    "next": action,
                },
            }
        return action


class VendorBillApprovalDecisionWizard(models.TransientModel):
    _name = "vendor.bill.approval.decision.wizard"
    _description = "Decisión de aprobación de factura proveedor"

    move_id = fields.Many2one("account.move", string="Factura", required=True, readonly=True)
    decision = fields.Selection(
        [
            ("approve", "Aprobar"),
            ("reject", "Rechazar"),
            ("return", "Devolver"),
        ],
        required=True,
        readonly=True,
        string="Decisión",
    )
    comment = fields.Text(string="Comentario / motivo")

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        move = self.env["account.move"].browse(self.env.context.get("active_id"))
        if move:
            res["move_id"] = move.id
        res["decision"] = self.env.context.get("default_decision") or res.get("decision")
        return res

    def action_confirm(self):
        self.ensure_one()
        move = self.move_id
        if self.decision == "approve":
            if self.comment:
                move.vendor_bill_approval_notes = self.comment
            move.action_vendor_bill_approve()
        elif self.decision == "reject":
            if not self.comment or not self.comment.strip():
                raise UserError(_("El motivo de rechazo es obligatorio."))
            move.vendor_bill_reject_reason = self.comment.strip()
            move.action_vendor_bill_reject()
        elif self.decision == "return":
            if not self.comment or not self.comment.strip():
                raise UserError(_("El motivo de devolución es obligatorio."))
            move.vendor_bill_return_reason = self.comment.strip()
            move.action_vendor_bill_return()
        return {"type": "ir.actions.act_window_close"}


class VendorBillApprovalReassignWizard(models.TransientModel):
    _name = "vendor.bill.approval.reassign.wizard"
    _description = "Reasignar aprobación de factura proveedor"

    move_id = fields.Many2one("account.move", string="Factura", required=True, readonly=True)
    current_approver_id = fields.Many2one(
        related="move_id.vendor_bill_approver_id",
        string="Aprobador actual",
        readonly=True,
    )
    new_approver_id = fields.Many2one("res.users", string="Nuevo aprobador", required=True)
    reason = fields.Text(string="Motivo de reasignación", required=True)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        move = self.env["account.move"].browse(self.env.context.get("active_id"))
        if move:
            res["move_id"] = move.id
        return res

    @api.onchange("move_id")
    def _onchange_domain(self):
        level = self.move_id.vendor_bill_approval_level_required or "finance"
        if level == "dual" and self.move_id.vendor_bill_finance_approved_by:
            level = "management"
        domain = ah.authorized_approver_domain(self.env, self.move_id.company_id, level=level)
        return {"domain": {"new_approver_id": domain}}

    def _justech_assert_can_reassign(self):
        user = self.env.user
        move = self.move_id
        if not move.company_id.vendor_bill_allow_reassign:
            raise UserError(_("La reasignación está deshabilitada."))
        if user.has_group("base.group_system") or user.has_group(ah.XMLID_MGMT):
            return
        if user.has_group("justech_vendor_bill_po_control.group_vendor_bill_reassign"):
            return
        if move.vendor_bill_approver_id and user == move.vendor_bill_approver_id:
            return
        raise AccessError(_("No tiene permiso para reasignar esta solicitud."))

    def action_reassign(self):
        self.ensure_one()
        self._justech_assert_can_reassign()
        move = self.move_id
        if move.vendor_bill_approval_state != "pending_validation":
            raise UserError(_("Solo se pueden reasignar solicitudes pendientes."))
        new_user = self.new_approver_id
        level = move.vendor_bill_approval_level_required or "finance"
        if level == "dual" and move.vendor_bill_finance_approved_by:
            check = "management"
        elif level == "management":
            check = "management"
        else:
            check = "finance"
        if not ah.user_meets_approval_level(new_user, check):
            raise UserError(_("El nuevo aprobador no cumple el nivel requerido."))
        old = move.vendor_bill_approver_id
        move._justech_close_approval_activities()
        vals = {
            "vendor_bill_approver_id": new_user.id,
            "vendor_bill_approval_deadline": ah.approval_deadline(move.company_id),
            "vendor_bill_reassign_count": (move.vendor_bill_reassign_count or 0) + 1,
            "vendor_bill_reassign_reason": self.reason.strip(),
        }
        if check == "finance":
            vals["vendor_bill_finance_approver_id"] = new_user.id
        elif check == "management":
            vals["vendor_bill_mgmt_approver_id"] = new_user.id
        move._justech_wf_write(vals)
        move.message_post(
            body=_(
                "Reasignada de %(old)s a %(new)s por %(user)s. Motivo: %(reason)s"
            )
            % {
                "old": old.display_name if old else "-",
                "new": new_user.display_name,
                "user": self.env.user.display_name,
                "reason": self.reason.strip(),
            }
        )
        move._justech_schedule_approval_activity(new_user)
        move._justech_notify_approver(new_user)
        if old and old.partner_id:
            move.message_post(
                body=_("Ya no es el aprobador asignado de %(bill)s.")
                % {"bill": move.display_name},
                partner_ids=old.partner_id.ids,
                subtype_xmlid="mail.mt_note",
            )
        return {"type": "ir.actions.act_window_close"}
