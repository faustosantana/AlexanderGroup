# -*- coding: utf-8 -*-
"""Cancelación directa de factura/asiento (NCF no entregado al cliente).

Campos de entrega, regularización fiscal y helpers de elegibilidad.
La orquestación vive en ``justech.do.invoice.direct.cancel.service``.
"""
from odoo import _, fields, models
from odoo.exceptions import AccessError, UserError
from odoo.tools import float_compare, float_is_zero


DELIVERY_BLOCKING = frozenset(
    {
        "delivered",
        "emailed",
        "portal_available",
        "printed_delivered",
        "acknowledged",
    }
)

FISCAL_ADMIN_XMLIDS = (
    "base.group_system",
    "account.group_account_manager",
    "justech_l10n_do_base.group_justech_do_fiscal_manager",
    "justech_fiscal_admin.group_justech_fiscal_admin_manager",
)


class AccountMove(models.Model):
    _inherit = "account.move"

    justech_do_customer_delivery_state = fields.Selection(
        selection=[
            ("not_delivered", "No entregado"),
            ("delivered", "Entregado"),
            ("emailed", "Enviado por correo"),
            ("portal_available", "Disponible en portal"),
            ("printed_delivered", "Impreso y entregado"),
            ("acknowledged", "Acuse / recepción confirmada"),
            ("unknown", "Desconocido"),
        ],
        string="Estado de entrega al cliente",
        default="unknown",
        copy=False,
        tracking=True,
        help="Traza de entrega/comunicación del comprobante al cliente. "
        "Bloquea «Cancelar factura y asiento» si hubo entrega.",
    )
    justech_do_cancellation_method = fields.Selection(
        selection=[
            ("none", "Ninguno"),
            ("credit_note", "Anulación mediante Nota de Crédito"),
            ("direct_cancel", "Cancelación directa de factura y asiento"),
        ],
        string="Método de anulación/cancelación",
        default="none",
        copy=False,
        tracking=True,
    )
    justech_do_fiscal_regularization_state = fields.Selection(
        selection=[
            ("none", "No aplica"),
            ("pending_regularization", "Pendiente de regularización"),
            ("voided_internal", "Anulado internamente"),
            ("reported_608", "Reportado en 608"),
            ("rectificative_pending", "Rectificativa pendiente"),
            ("regularized_dgii", "Regularizado en DGII"),
            ("cancelled_via_credit_note", "Anulado mediante Nota de Crédito"),
        ],
        string="Estado de regularización fiscal",
        default="none",
        copy=False,
        index=True,
        tracking=True,
    )
    justech_do_fiscal_treatment_planned = fields.Selection(
        selection=[
            ("format_608", "Incluir en Formato 608"),
            ("rectify_607", "Rectificar Formato 607"),
            # Históricos (ya no se ofrecen en el wizard)
            ("rectify_declaration", "Rectificar declaración fiscal"),
            ("pending_accounting", "Pendiente de validación por Contabilidad"),
            ("other", "Otro"),
        ],
        string="Tratamiento fiscal previsto",
        copy=False,
    )
    justech_do_fiscal_treatment_other = fields.Char(
        string="Detalle tratamiento fiscal",
        copy=False,
    )
    justech_do_direct_cancel_reason = fields.Text(
        string="Motivo de cancelación directa",
        copy=False,
    )
    justech_do_direct_cancel_user_id = fields.Many2one(
        "res.users",
        string="Cancelado directamente por",
        copy=False,
        readonly=True,
    )
    justech_do_direct_cancel_datetime = fields.Datetime(
        string="Fecha/hora cancelación directa",
        copy=False,
        readonly=True,
    )
    justech_do_not_delivered_declared = fields.Boolean(
        string="Declaró no entrega al cliente",
        copy=False,
        readonly=True,
    )
    justech_do_included_in_607 = fields.Boolean(
        string="Incluida previamente en 607",
        copy=False,
        help="Marcar si el NCF ya formó parte de un 607 presentado. "
        "Exige advertencia y autorización fiscal reforzada para cancelación directa.",
    )
    justech_do_regularization_deadline = fields.Date(
        string="Fecha límite regularización",
        copy=False,
    )
    justech_do_regularization_responsible_id = fields.Many2one(
        "res.users",
        string="Responsable regularización",
        copy=False,
    )
    justech_do_original_fiscal_period = fields.Char(
        string="Período fiscal original",
        size=6,
        copy=False,
        index=True,
        help="YYYYMM del comprobante (no la fecha de cancelación interna).",
    )
    justech_do_608_reporting_period = fields.Char(
        string="Período 608 a reportar",
        size=6,
        copy=False,
        index=True,
        help="Igual a período fiscal original. Fuente del generador 608.",
    )
    justech_do_cancellation_execution_date = fields.Datetime(
        string="Fecha ejecución cancelación interna",
        copy=False,
        readonly=True,
    )
    justech_do_fiscal_regularization_id = fields.Many2one(
        "justech.do.fiscal.regularization",
        string="Línea de regularización",
        copy=False,
    )
    justech_do_regularization_treatment_summary = fields.Char(
        related="justech_do_fiscal_regularization_id.treatment_summary",
        string="Acción de regularización",
    )

    def _justech_has_group_safe(self, xmlid):
        if not self.env.ref(xmlid, raise_if_not_found=False):
            return False
        return self.env.user.has_group(xmlid)

    def _justech_user_has_fiscal_admin_authority(self):
        """Administrador Fiscal / Contable / Sistema (sin implied_ids)."""
        return any(self._justech_has_group_safe(x) for x in FISCAL_ADMIN_XMLIDS)

    def _justech_linked_credit_notes(self, *, include_cancel=False):
        """NC vinculadas por ``reversed_entry_id``."""
        self.ensure_one()
        if not self.ids:
            return self.env["account.move"]
        domain = [
            ("reversed_entry_id", "=", self.id),
            ("move_type", "in", ("out_refund", "in_refund")),
        ]
        if not include_cancel:
            domain.append(("state", "!=", "cancel"))
        return self.env["account.move"].search(domain)

    def _justech_reconcile_counterpart_moves(self):
        """Asientos contraparte de conciliaciones parciales (no self)."""
        self.ensure_one()
        counterparts = self.env["account.move"]
        if not self.ids:
            return counterparts
        for line in self.line_ids:
            for partial in line.matched_debit_ids | line.matched_credit_ids:
                other = (
                    partial.debit_move_id
                    if partial.credit_move_id.move_id == self
                    else partial.credit_move_id
                )
                if other and other.move_id and other.move_id != self:
                    counterparts |= other.move_id
        return counterparts

    def _justech_has_real_payments(self):
        """Pagos reales (account.payment / payment_id), NO payment_state=reversed."""
        self.ensure_one()
        if not self.ids:
            return False
        if "payment_id" in self.line_ids._fields:
            if any(self.line_ids.mapped("payment_id")):
                return True
        Payment = self.env["account.payment"]
        # reconciled_invoice_ids suele ser stored/computed searchable en Odoo 19;
        # si no es searchable, caer a inspección de líneas/contrapartes.
        if "reconciled_invoice_ids" in Payment._fields:
            try:
                if Payment.search(
                    [("reconciled_invoice_ids", "in", self.ids)], limit=1
                ):
                    return True
            except ValueError:
                pass
        for other in self._justech_reconcile_counterpart_moves():
            if getattr(other, "payment_id", False):
                return True
            # Líneas de la contraparte con payment_id
            if "payment_id" in other.line_ids._fields and any(
                other.line_ids.mapped("payment_id")
            ):
                return True
        return False

    def _justech_has_bank_reconciliation(self):
        """Conciliación con banco/caja (no NC)."""
        self.ensure_one()
        if not self.ids:
            return False
        for other in self._justech_reconcile_counterpart_moves():
            if other.move_type in ("out_refund", "in_refund"):
                continue
            journal = other.journal_id
            if journal and journal.type in ("bank", "cash"):
                return True
            if getattr(other, "statement_line_ids", False) and other.statement_line_ids:
                return True
        return False

    def _justech_has_withholdings(self):
        self.ensure_one()
        if not self.ids:
            return False
        if "justech_withholding_line_ids" in self.env["account.payment"]._fields:
            Payment = self.env["account.payment"]
            domain = [("justech_withholding_line_ids", "!=", False)]
            if "reconciled_invoice_ids" in Payment._fields:
                domain = [
                    ("reconciled_invoice_ids", "in", self.ids),
                    ("justech_withholding_line_ids", "!=", False),
                ]
            if Payment.search(domain, limit=1):
                return True
        for line in self.line_ids:
            tax = getattr(line, "tax_line_id", False)
            if tax and (
                "retenc" in (tax.name or "").lower()
                or "withhold" in (tax.name or "").lower()
            ):
                return True
        return False

    def _justech_has_credit_note_reconciliation(self):
        self.ensure_one()
        cns = self._justech_linked_credit_notes()
        if not cns:
            return False
        counterparts = self._justech_reconcile_counterpart_moves()
        return bool(counterparts & cns)

    def _justech_has_other_reconciliations(self):
        self.ensure_one()
        cns = self._justech_linked_credit_notes()
        counterparts = self._justech_reconcile_counterpart_moves()
        return bool(counterparts - cns)

    def _justech_has_posted_replacement(self):
        self.ensure_one()
        repl = self.justech_do_replacement_move_id
        return bool(repl and repl.state == "posted")

    def _justech_cn_conversion_eligible(self):
        """Caso B: reversed solo por NC total ↔ factura, sin pagos reales.

        Returns: (ok: bool, refunds: recordset, error: str|False)
        """
        self.ensure_one()
        refunds = self._justech_linked_credit_notes()
        if not refunds:
            return False, refunds, False
        if len(refunds) > 1:
            return (
                False,
                refunds,
                _(
                    "Esta factura tiene múltiples Notas de Crédito; "
                    "no puede convertirse en cancelación directa."
                ),
            )
        cn = refunds[:1]
        if cn.state != "posted":
            return (
                False,
                refunds,
                _("La Nota de Crédito vinculada no está publicada."),
            )
        if not float_is_zero(
            self.amount_residual, precision_rounding=self.currency_id.rounding
        ):
            return (
                False,
                refunds,
                _(
                    "Esta factura tiene una Nota de Crédito parcial; "
                    "no puede convertirse en cancelación directa."
                ),
            )
        if float_compare(
            abs(cn.amount_total),
            abs(self.amount_total),
            precision_rounding=self.currency_id.rounding,
        ) < 0:
            return (
                False,
                refunds,
                _(
                    "Esta factura tiene una Nota de Crédito parcial; "
                    "no puede convertirse en cancelación directa."
                ),
            )
        if self._justech_has_real_payments():
            return (
                False,
                refunds,
                _(
                    "Existe un pago bancario vinculado; no puede cancelar "
                    "directamente la factura."
                ),
            )
        if self._justech_has_bank_reconciliation():
            return (
                False,
                refunds,
                _(
                    "Existe conciliación bancaria o de caja; no puede cancelar "
                    "directamente la factura."
                ),
            )
        if self._justech_has_withholdings() or cn._justech_has_withholdings():
            return (
                False,
                refunds,
                _("Existen retenciones vinculadas; no puede cancelar directamente."),
            )
        if self._justech_has_other_reconciliations():
            return (
                False,
                refunds,
                _(
                    "La Nota de Crédito fue utilizada en una conciliación distinta "
                    "de la factura original."
                ),
            )
        if cn._justech_has_real_payments() or cn._justech_has_bank_reconciliation():
            return (
                False,
                refunds,
                _(
                    "La Nota de Crédito tiene pagos o conciliaciones bancarias; "
                    "no puede convertirse en cancelación directa."
                ),
            )
        cn_counterparts = cn._justech_reconcile_counterpart_moves()
        if cn_counterparts - self:
            return (
                False,
                refunds,
                _(
                    "La Nota de Crédito fue utilizada en una conciliación distinta "
                    "de la factura original."
                ),
            )
        if self._justech_has_posted_replacement():
            return (
                False,
                refunds,
                _(
                    "Existe una factura sustituta publicada. "
                    "No se permite cancelación directa."
                ),
            )
        return True, refunds, False

    def _justech_collect_delivery_evidence(self):
        """Evidencia objetiva de comunicación/entrega (solo lectura)."""
        self.ensure_one()
        evidence = []
        delivery = self.justech_do_customer_delivery_state or "unknown"
        if delivery in DELIVERY_BLOCKING:
            evidence.append(_("Estado de entrega: %s") % delivery)
        if self.is_move_sent:
            evidence.append(_("Marcada como enviada (is_move_sent)"))
        if self.ids:
            Mail = self.env["mail.message"]
            email_msgs = Mail.search(
                [
                    ("model", "=", "account.move"),
                    ("res_id", "=", self.id),
                    ("message_type", "=", "email"),
                ],
                limit=3,
            )
            if email_msgs:
                evidence.append(
                    _("Correo(s) asociados en chatter (%s)") % len(email_msgs)
                )
        if "invoice_sent" in self._fields and self.invoice_sent:
            evidence.append(_("Indicador invoice_sent activo"))
        return evidence

    def _justech_direct_cancel_analysis(self):
        """Análisis de elegibilidad. No usa payment_state=reversed como pago real."""
        self.ensure_one()
        result = {
            "error": False,
            "needs_cn_conversion": False,
            "refunds": self.env["account.move"],
            "has_real_payments": False,
            "has_bank_reconciliation": False,
            "has_withholdings": False,
            "has_credit_note_reconciliation": False,
            "has_other_reconciliations": False,
        }
        if self.state != "posted":
            result["error"] = _(
                "Solo documentos publicados pueden cancelarse directamente."
            )
            return result
        if self.move_type not in (
            "out_invoice",
            "in_invoice",
            "out_refund",
            "in_refund",
        ):
            result["error"] = _(
                "Esta acción solo aplica a facturas y notas de crédito."
            )
            return result

        result["has_real_payments"] = self._justech_has_real_payments()
        result["has_bank_reconciliation"] = self._justech_has_bank_reconciliation()
        result["has_withholdings"] = self._justech_has_withholdings()
        result["has_credit_note_reconciliation"] = (
            self._justech_has_credit_note_reconciliation()
        )
        result["has_other_reconciliations"] = self._justech_has_other_reconciliations()

        if result["has_real_payments"]:
            result["error"] = _(
                "Existe un pago bancario vinculado; no puede cancelar "
                "directamente la factura."
            )
            return result
        if result["has_bank_reconciliation"]:
            result["error"] = _(
                "Existe conciliación bancaria o de caja; no puede cancelar "
                "directamente la factura."
            )
            return result
        if result["has_withholdings"]:
            result["error"] = _(
                "Existen retenciones vinculadas; no puede cancelar directamente."
            )
            return result
        if self._justech_has_posted_replacement():
            result["error"] = _(
                "Existe una factura sustituta publicada. "
                "No se permite cancelación directa."
            )
            return result

        refunds = self._justech_linked_credit_notes()
        if refunds:
            ok, refunds, err = self._justech_cn_conversion_eligible()
            result["refunds"] = refunds
            if not ok:
                result["error"] = err or _(
                    "Las Notas de Crédito vinculadas no permiten cancelación directa."
                )
                return result
            result["needs_cn_conversion"] = True
        elif result["has_other_reconciliations"]:
            result["error"] = _(
                "Existen conciliaciones con terceros; no puede cancelar "
                "directamente la factura."
            )
            return result
        elif self.payment_state in ("paid", "partial", "in_payment"):
            result["error"] = _(
                "Existe un pago bancario vinculado; no puede cancelar "
                "directamente la factura."
            )
            return result

        delivery = self.justech_do_customer_delivery_state or "unknown"
        if delivery in DELIVERY_BLOCKING:
            result["error"] = _(
                "Esta factura presenta evidencia de haber sido comunicada al cliente. "
                "Debe anularse mediante Nota de Crédito."
            )
            return result

        evidence = self._justech_collect_delivery_evidence()
        if evidence and not result["needs_cn_conversion"]:
            result["error"] = _(
                "Esta factura presenta evidencia de haber sido comunicada al cliente. "
                "Debe anularse mediante Nota de Crédito.\n\nEvidencia:\n- %s"
            ) % ("\n- ".join(evidence))
            return result

        if self.ids:
            try:
                is_ecf = self._justech_is_ecf_document()
            except Exception:
                is_ecf = False
            if is_ecf:
                send_state = ""
                try:
                    send_state = self._justech_ecf_send_state() or ""
                except Exception:
                    send_state = ""
                if send_state in (
                    "delivered_accepted",
                    "conditionally_accepted",
                    "accepted",
                    "delivered_pending",
                    "processing",
                    "delivered_refused",
                ):
                    result["error"] = _(
                        "e-CF enviado o en proceso ante la DGII. "
                        "No se permite cancelación directa; use el mecanismo electrónico."
                    )
                    return result

        if delivery == "unknown" and not self._justech_user_has_fiscal_admin_authority():
            result["error"] = _(
                "El estado de entrega es «Desconocido». "
                "Se requiere Administrador Fiscal/Contable/Sistema y justificación."
            )
            return result

        return result

    def _justech_direct_cancel_gate_error(self):
        """Bloqueo de negocio para cancelación directa. False si elegible."""
        self.ensure_one()
        return self._justech_direct_cancel_analysis().get("error") or False

    def action_mark_fiscal_regularization(self, new_state, *, attachment=False):
        """Transiciones manuales del Centro de Regularización Fiscal."""
        allowed = {
            "reported_608",
            "rectificative_pending",
            "regularized_dgii",
            "voided_internal",
            "pending_regularization",
        }
        if new_state not in allowed:
            raise UserError(_("Estado de regularización no permitido: %s") % new_state)
        if new_state == "regularized_dgii" and not attachment:
            if not self.env.context.get("justech_regularization_evidence_ok"):
                raise UserError(
                    _(
                        "No se puede marcar «Regularizado en DGII» sin evidencia. "
                        "Adjunte el acuse DGII o confirme con evidencia."
                    )
                )
        for move in self:
            if not self.env.user.can_recover_accounting_document(move.company_id):
                raise AccessError(
                    _("Sin autorización para actualizar la regularización fiscal.")
                )
            if not move._justech_user_has_fiscal_admin_authority():
                raise AccessError(
                    _(
                        "Actualizar regularización fiscal requiere Administrador "
                        "Fiscal, Contable o del Sistema."
                    )
                )
            move.justech_do_fiscal_regularization_state = new_state
            reg = move.justech_do_fiscal_regularization_id
            if reg:
                if new_state == "reported_608":
                    reg.write(
                        {
                            "status_608": "presented",
                            "general_status": "in_progress",
                        }
                    )
                elif new_state == "regularized_dgii":
                    reg.write(
                        {
                            "status_608": "accepted",
                            "general_status": "regularized",
                        }
                    )
                elif new_state == "rectificative_pending":
                    reg.write(
                        {
                            "status_608": "rectification_required",
                            "general_status": "in_progress",
                        }
                    )
            move.message_post(
                body=_(
                    "Regularización fiscal actualizada a «%(state)s» por %(user)s."
                )
                % {
                    "state": dict(
                        move._fields[
                            "justech_do_fiscal_regularization_state"
                        ]._description_selection(self.env)
                    ).get(new_state, new_state),
                    "user": self.env.user.display_name,
                }
            )
        return True

    def action_mark_reported_608(self):
        return self.action_mark_fiscal_regularization("reported_608")

    def action_mark_607_rectified(self):
        return self.action_mark_fiscal_regularization("rectificative_pending")

    def action_mark_declaration_rectified(self):
        return self.action_mark_fiscal_regularization("rectificative_pending")

    def action_mark_regularized_dgii(self):
        return self.with_context(
            justech_regularization_evidence_ok=True
        ).action_mark_fiscal_regularization("regularized_dgii", attachment=True)
