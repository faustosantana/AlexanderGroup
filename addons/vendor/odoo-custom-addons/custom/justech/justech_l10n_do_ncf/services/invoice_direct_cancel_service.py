# -*- coding: utf-8 -*-
"""Cancelación directa atómica: factura + asiento (sin crear NC).

Caso A: sin NC → void NCF + button_cancel.
Caso B: con NC total (payment_state=reversed por NC) → desconciliar,
cancelar NC y factura atómicamente.
"""
from odoo import _, fields, models
from odoo.exceptions import AccessError, UserError

from odoo.addons.justech_accounting_recovery.models.accounting_recovery_guard import (
    authorized_reversal_enter,
    authorized_reversal_exit,
)


class JustechDoInvoiceDirectCancelService(models.AbstractModel):
    _name = "justech.do.invoice.direct.cancel.service"
    _description = "Justech DO — cancelación directa factura/asiento"

    def assert_can_direct_cancel(self, move, *, delivery_unknown_ok=False):
        move.ensure_one()
        user = self.env.user
        user.assert_can_recover_accounting_document(move.company_id)

        ncf = move._justech_get_issued_ncf()
        if ncf and not move._justech_user_has_fiscal_admin_authority():
            raise AccessError(
                _(
                    "PERMISO_FISCAL_NCF|%(company)s|"
                    "Administrador Fiscal / Contable / Sistema|"
                    "Cancelar factura con NCF no entregado"
                )
                % {"company": move.company_id.display_name}
            )

        analysis = move._justech_direct_cancel_analysis()
        if analysis.get("error"):
            raise UserError(analysis["error"])

        delivery = move.justech_do_customer_delivery_state or "unknown"
        if delivery == "unknown" and not delivery_unknown_ok:
            if not move._justech_user_has_fiscal_admin_authority():
                raise UserError(
                    _(
                        "Estado de entrega «Desconocido»: se requiere Administrador "
                        "Fiscal/Contable/Sistema y justificación explícita."
                    )
                )

        if (
            move.justech_do_included_in_607
            and not move._justech_user_has_fiscal_admin_authority()
        ):
            raise AccessError(
                _(
                    "Documento marcado como incluido en 607: se requiere "
                    "autorización fiscal reforzada."
                )
            )
        return analysis

    def _session_info(self):
        ctx = self.env.context
        parts = []
        for key in ("uid", "login", "client_addr", "remote_addr"):
            if ctx.get(key):
                parts.append("%s=%s" % (key, ctx[key]))
        try:
            from odoo.http import request

            if request and getattr(request, "httprequest", None):
                parts.append("ip=%s" % request.httprequest.remote_addr)
        except Exception:
            pass
        return "; ".join(parts) if parts else False

    def _void_ncf_if_needed(self, move, *, reason, cancel_type):
        issued = move._justech_get_issued_ncf()
        if not issued:
            return False
        if move.justech_do_ncf_voided:
            return True
        move.write(
            {
                "justech_do_ncf_void_reason": reason,
                "justech_do_ncf_cancel_type": cancel_type or "01",
            }
        )
        move.with_context(
            justech_void_from_direct_cancel=True,
            justech_void_cancel_label=_("Cancelación directa (NCF no entregado)"),
        ).action_void_ncf()
        return True

    def _apply_post_cancel_meta(
        self,
        move,
        *,
        reason,
        fiscal_treatment,
        fiscal_treatment_other,
        issued_ncf,
        prev_state,
        prev_payment,
        prev_total,
        evidence_txt,
        method_label="direct_cancel",
    ):
        reg_state = "pending_regularization" if issued_ncf else "none"
        vals = {
            "justech_do_cancellation_method": "direct_cancel",
            "justech_do_fiscal_regularization_state": reg_state,
            "justech_do_fiscal_treatment_planned": fiscal_treatment,
            "justech_do_fiscal_treatment_other": fiscal_treatment_other or False,
            "justech_do_direct_cancel_reason": reason,
            "justech_do_direct_cancel_user_id": self.env.user.id,
            "justech_do_direct_cancel_datetime": fields.Datetime.now(),
            "justech_do_not_delivered_declared": True,
            "justech_do_customer_delivery_state": "not_delivered",
            "justech_do_regularization_responsible_id": self.env.user.id,
        }
        if issued_ncf:
            vals.update(
                {
                    # Excluir del 607; el exportador 608 incluye anulados por voided.
                    "justech_do_include_in_dgii": False,
                    "justech_do_dgii_line_status": "2",
                    "justech_do_dgii_fiscal_state": "cancelled",
                    "justech_do_ncf_voided": True,
                }
            )
        move.write(vals)
        self.env["justech.do.fiscal.regularization.log"].sudo().create(
            {
                "move_id": move.id,
                "move_name": move.name or move.display_name,
                "company_id": move.company_id.id,
                "partner_id": move.partner_id.id,
                "ncf": issued_ncf or False,
                "user_id": self.env.user.id,
                "event_datetime": fields.Datetime.now(),
                "previous_state": prev_state,
                "previous_payment_state": prev_payment,
                "previous_amount_total": prev_total,
                "reason": reason,
                "not_delivered_declared": True,
                "fiscal_treatment": fiscal_treatment,
                "fiscal_treatment_other": fiscal_treatment_other or False,
                "evidence_reviewed": evidence_txt,
                "method": method_label
                if method_label in ("direct_cancel", "regularization_update")
                else "direct_cancel",
                "fiscal_state_after": move.justech_do_fiscal_regularization_state,
                "session_info": self._session_info(),
            }
        )

    def _create_fiscal_regularizations(
        self,
        moves,
        *,
        reason,
        cancel_type,
        source_operation="direct_cancel",
    ):
        """Una línea 608 por NCF, período original, actividad al responsable."""
        svc = self.env["justech.do.fiscal.regularization.service"]
        regs = self.env["justech.do.fiscal.regularization"]
        for move in moves:
            ncf = (
                move._justech_get_issued_ncf()
                if hasattr(move, "_justech_get_issued_ncf")
                else move.justech_do_ncf
            )
            if not ncf and not move.justech_do_ncf_voided:
                continue
            reg = svc.ensure_regularization_for_move(
                move,
                reason=reason,
                cancel_type=cancel_type,
                source_operation=source_operation,
                cancelled_by=self.env.user,
                linked_moves=moves - move,
            )
            if reg:
                move.justech_do_fiscal_regularization_id = reg.id
                regs |= reg
        return regs

    def _unreconcile_invoice_cn_only(self, invoice, refunds):
        """Desconcilia únicamente líneas factura ↔ NC vinculadas."""
        refund_ids = set(refunds.ids)
        lines = invoice.line_ids.filtered(
            lambda l: l.matched_debit_ids or l.matched_credit_ids
        )
        to_unreconcile = self.env["account.move.line"]
        for line in lines:
            for partial in line.matched_debit_ids | line.matched_credit_ids:
                other = (
                    partial.debit_move_id
                    if partial.credit_move_id == line
                    else partial.credit_move_id
                )
                if other and other.move_id.id in refund_ids:
                    to_unreconcile |= line
                    break
        if to_unreconcile:
            to_unreconcile.remove_move_reconcile()

    def execute_direct_cancel(
        self,
        move,
        *,
        reason,
        fiscal_treatment,
        fiscal_treatment_other=None,
        cancel_type="01",
        not_delivered_confirmed=False,
        delivery_unknown_justification=None,
        confirm_cn_cancel=False,
    ):
        """Cancela factura/asiento. Si hay NC total elegible, la cancela también."""
        move.ensure_one()
        reason = (reason or "").strip()
        if not reason:
            raise UserError(_("Debe indicar el motivo de la cancelación."))
        if fiscal_treatment not in ("format_608", "rectify_607"):
            raise UserError(
                _(
                    "El tratamiento fiscal previsto debe ser «Incluir en Formato 608» "
                    "o «Rectificar Formato 607»."
                )
            )
        if not not_delivered_confirmed:
            raise UserError(
                _(
                    "Debe confirmar que el cliente no recibió ni tuvo acceso "
                    "a este comprobante."
                )
            )

        analysis = self.assert_can_direct_cancel(
            move,
            delivery_unknown_ok=bool(
                (delivery_unknown_justification or "").strip()
                or move._justech_user_has_fiscal_admin_authority()
            ),
        )

        if move.justech_do_included_in_607 and fiscal_treatment not in (
            "rectify_607",
            "format_608",
        ):
            raise UserError(
                _(
                    "Documento incluido en 607: el tratamiento fiscal previsto "
                    "debe ser 608 o rectificar 607."
                )
            )

        needs_cn = analysis.get("needs_cn_conversion")
        refunds = analysis.get("refunds") or self.env["account.move"]
        if needs_cn and not confirm_cn_cancel:
            raise UserError(
                _(
                    "Debe confirmar la cancelación de la factura y de la "
                    "Nota de Crédito vinculada."
                )
            )

        issued_ncf = move._justech_get_issued_ncf()
        prev_state = move.state
        prev_payment = move.payment_state
        prev_total = move.amount_total
        evidence = move._justech_collect_delivery_evidence()
        evidence_txt = (
            "; ".join(evidence)
            if evidence
            else _("Sin evidencia automática de entrega (declaración del usuario).")
        )
        if delivery_unknown_justification:
            evidence_txt = "%s | Justificación unknown: %s" % (
                evidence_txt,
                delivery_unknown_justification.strip(),
            )
        if needs_cn:
            evidence_txt = "%s | Conversión NC→cancel: %s" % (
                evidence_txt,
                ", ".join(refunds.mapped("name")),
            )

        authorized_reversal_enter()
        try:
            with self.env.cr.savepoint():
                cancelled_refunds = self.env["account.move"]

                if needs_cn:
                    # 1) Desconciliar solo factura ↔ NC
                    self._unreconcile_invoice_cn_only(move, refunds)
                    move.invalidate_recordset()
                    refunds.invalidate_recordset()

                    # 2) Void + cancel cada NC
                    for cn in refunds:
                        cn_ncf = cn._justech_get_issued_ncf()
                        cn_prev_state = cn.state
                        cn_prev_pay = cn.payment_state
                        cn_prev_total = cn.amount_total
                        self._void_ncf_if_needed(
                            cn, reason=reason, cancel_type=cancel_type
                        )
                        cn.button_cancel()
                        if cn.state != "cancel":
                            raise UserError(
                                _(
                                    "No se pudo cancelar la Nota de Crédito %(cn)s."
                                )
                                % {"cn": cn.display_name}
                            )
                        self._apply_post_cancel_meta(
                            cn,
                            reason=reason,
                            fiscal_treatment=fiscal_treatment,
                            fiscal_treatment_other=fiscal_treatment_other,
                            issued_ncf=cn_ncf,
                            prev_state=cn_prev_state,
                            prev_payment=cn_prev_pay,
                            prev_total=cn_prev_total,
                            evidence_txt=evidence_txt,
                        )
                        cn.message_post(
                            body=_(
                                "Nota de Crédito y asiento cancelados en conversión "
                                "atómica desde %(origin)s por %(user)s. "
                                "NCF %(ncf)s anulado / no reutilizable. Motivo: %(reason)s."
                            )
                            % {
                                "origin": move.display_name,
                                "user": self.env.user.display_name,
                                "ncf": cn_ncf or _("(sin NCF)"),
                                "reason": reason,
                            }
                        )
                        cancelled_refunds |= cn

                # 3) Void + cancel factura origen
                voided = self._void_ncf_if_needed(
                    move, reason=reason, cancel_type=cancel_type
                )
                move.button_cancel()
                if move.state != "cancel":
                    raise UserError(
                        _(
                            "La cancelación directa no dejó el asiento en estado "
                            "«cancel». Operación abortada."
                        )
                    )

                self._apply_post_cancel_meta(
                    move,
                    reason=reason,
                    fiscal_treatment=fiscal_treatment,
                    fiscal_treatment_other=fiscal_treatment_other,
                    issued_ncf=issued_ncf,
                    prev_state=prev_state,
                    prev_payment=prev_payment,
                    prev_total=prev_total,
                    evidence_txt=evidence_txt,
                )

                if needs_cn:
                    body = _(
                        "Factura y asiento cancelados directamente por %(user)s "
                        "(conversión desde Nota de Crédito %(cn)s). "
                        "El usuario confirmó que el comprobante no fue entregado al cliente. "
                        "NCF %(ncf)s marcado como anulado y pendiente de regularización. "
                        "Motivo: %(reason)s."
                    ) % {
                        "user": self.env.user.display_name,
                        "cn": ", ".join(cancelled_refunds.mapped("name")),
                        "ncf": issued_ncf or _("(sin NCF)"),
                        "reason": reason,
                    }
                else:
                    body = _(
                        "Factura y asiento cancelados directamente por %(user)s. "
                        "El usuario confirmó que el comprobante no fue entregado al cliente. "
                        "NCF %(ncf)s marcado como anulado y pendiente de regularización fiscal. "
                        "Motivo: %(reason)s."
                    ) % {
                        "user": self.env.user.display_name,
                        "ncf": issued_ncf or _("(sin NCF)"),
                        "reason": reason,
                    }
                move.message_post(body=body)

                all_cancelled = move | cancelled_refunds
                regs = self._create_fiscal_regularizations(
                    all_cancelled,
                    reason=reason,
                    cancel_type=cancel_type,
                    source_operation=(
                        "cn_conversion" if needs_cn else "direct_cancel"
                    ),
                )

                return {
                    "origin": move,
                    "voided_ncf": voided or bool(issued_ncf),
                    "ncf": issued_ncf,
                    "regularization_state": move.justech_do_fiscal_regularization_state,
                    "cancelled_refunds": cancelled_refunds,
                    "needs_cn_conversion": needs_cn,
                    "regularizations": regs,
                }
        finally:
            authorized_reversal_exit()
