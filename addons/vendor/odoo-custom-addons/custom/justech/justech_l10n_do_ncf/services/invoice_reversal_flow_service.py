# -*- coding: utf-8 -*-
"""Flujo atómico de anulación/reversión fiscal (Corregir o Anular).

Responsabilidad única: orquestar NC + conciliación + void NCF (+ sustituta)
en una sola transacción controlada. No calcula impuestos ni redefine reportes.

Secuencia (cancelación / corrección total):
1) validar permisos (NC fiscal + revertir; sin sudo indiscriminado)
2) crear y publicar nota de crédito
3) conciliar y exigir residual 0 cuando la operación lo requiere
4) anular NCF original cuando aplique (tradicional; no e-CF transmitido)
5) opcionalmente vincular factura sustituta en borrador
6) trazabilidad en chatter

Rollback: ``env.cr.savepoint()`` envuelve la mutación. Cualquier excepción
(UserError/AccessError/otras) aborta el savepoint y no deja estado parcial.
``authorized_reversal_enter/exit`` (finally) solo marca el SoD temporal; no
sustituye el savepoint.

Excepciones esperadas:
- AccessError: permisos insuficientes (NC, reverse, void, pagadas)
- UserError: precondiciones de negocio o residual no neutralizado
"""
from odoo import _, fields, models
from odoo.exceptions import AccessError, UserError
from odoo.tools import float_compare

from odoo.addons.justech_accounting_recovery.models.accounting_recovery_guard import (
    authorized_reversal_enter,
    authorized_reversal_exit,
)


class JustechDoInvoiceReversalFlowService(models.AbstractModel):
    _name = "justech.do.invoice.reversal.flow.service"
    _description = "Justech DO — flujo atómico de reversión fiscal"

    def assert_can_issue_fiscal_credit_note(self, move):
        """NC fiscal DO: misma autorización consolidada (sin grupos técnicos extra)."""
        move.ensure_one()
        is_do = getattr(move, "l10n_latam_country_code", False) == "DO"
        if not is_do:
            return
        self.env.user.assert_can_recover_accounting_document(move.company_id)

    def assert_can_void_ncf(self, move):
        """Anulación 608: misma autorización; no-op si ya anulado."""
        move.ensure_one()
        if move.justech_do_ncf_voided or not move._justech_get_issued_ncf():
            return
        if move._justech_void_ncf_gate_error():
            return
        self.env.user.assert_can_recover_accounting_document(move.company_id)

    def assert_can_reverse_invoice(self, move, *, replace=False, paid_ok=False):
        """Única puerta: Recuperación Contable / roles superiores + empresa.

        ``replace`` / ``paid_ok`` se conservan por compatibilidad de firma; la
        consolidación no exige grupos técnicos secundarios (NC fiscal, reverse_*).
        """
        move.ensure_one()
        self.env.user.assert_can_recover_accounting_document(move.company_id)
        # NC fiscal (DO) cubierta por la misma autoridad consolidada.
        self.assert_can_issue_fiscal_credit_note(move)

    def list_historical_voided_open_residual(self, companies=None, limit=500):
        """Detecta NCF anulado + posted + residual abierto. No modifica datos.

        Usa ``sudo()`` solo para inventario de auditoría cross-company/ACL;
        no escribe ni publica documentos.
        """
        domain = [
            ("justech_do_ncf_voided", "=", True),
            ("state", "=", "posted"),
            ("amount_residual", ">", 0),
            ("move_type", "in", ("out_invoice", "in_invoice")),
        ]
        if companies:
            domain.append(("company_id", "in", companies.ids))
        moves = self.env["account.move"].sudo().search(domain, limit=limit, order="id")
        rows = []
        for move in moves:
            rows.append(
                {
                    "id": move.id,
                    "name": move.name,
                    "ncf": move._justech_get_issued_ncf(),
                    "company": move.company_id.display_name,
                    "partner": move.partner_id.display_name,
                    "amount_residual": move.amount_residual,
                    "currency": move.currency_id.name,
                    "payment_state": move.payment_state,
                }
            )
        return rows

    def _build_reversal_wizard(self, move, *, reason, is_modify=False):
        Reversal = self.env["account.move.reversal"]
        ctx = {
            "active_model": "account.move",
            "active_id": move.id,
            "active_ids": move.ids,
        }
        if is_modify:
            ctx["justech_reverse_and_replace"] = True
        defaults = Reversal.with_context(**ctx).default_get(
            list(Reversal._fields.keys())
        )
        vals = {
            "move_ids": [(6, 0, move.ids)],
            "journal_id": defaults.get("journal_id") or move.journal_id.id,
            "date": defaults.get("date") or fields.Date.context_today(move),
            "reason": reason
            or _("Reversión fiscal controlada Justech (flujo atómico)"),
        }
        # Document type B04 / E34 cuando el wizard lo expone
        if defaults.get("l10n_latam_document_type_id"):
            vals["l10n_latam_document_type_id"] = defaults["l10n_latam_document_type_id"]
        elif "l10n_latam_document_type_id" in Reversal._fields:
            credit = self._credit_document_type_for(move)
            if credit:
                vals["l10n_latam_document_type_id"] = credit.id
        return Reversal.with_context(**ctx).create(vals)

    def _credit_document_type_for(self, move):
        # Catálogo fiscal de solo lectura (tipos latam); sudo evita falsos negativos
        # por ACL de catálogo sin ampliar permisos de escritura del usuario.
        Doc = self.env["l10n_latam.document.type"].sudo()
        ncf = ""
        try:
            ncf = (move._justech_get_issued_ncf() or "").upper()
        except Exception:
            ncf = ""
        prefix = "E34" if ncf.startswith("E") or move._justech_is_ecf_document() else "B04"
        credit = Doc.search(
            [
                ("doc_code_prefix", "=", prefix),
                ("internal_type", "=", "credit_note"),
            ],
            limit=1,
        )
        if credit:
            return credit
        return Doc.search([("doc_code_prefix", "=", prefix)], limit=1)

    def _ensure_refunds_posted(self, refunds):
        for refund in refunds.filtered(lambda m: m.state == "draft"):
            # Asignar tipo NC si falta
            if (
                "l10n_latam_document_type_id" in refund._fields
                and not refund.l10n_latam_document_type_id
            ):
                credit = self._credit_document_type_for(
                    refund.reversed_entry_id or refund
                )
                if credit:
                    refund.l10n_latam_document_type_id = credit.id
            refund.action_post()

    def _reconcile_origin_with_refunds(self, move, refunds):
        """Conciliar residual de la factura original con las NC creadas."""
        move.invalidate_recordset(["amount_residual", "payment_state"])
        if float_compare(
            move.amount_residual, 0.0, precision_rounding=move.currency_id.rounding
        ) == 0:
            return
        lines = (move.line_ids + refunds.line_ids).filtered(
            lambda l: not l.reconciled
            and l.account_id.account_type
            in ("asset_receivable", "liability_payable")
            and l.partner_id == move.commercial_partner_id
        )
        if lines:
            lines.reconcile()
        move.invalidate_recordset(["amount_residual", "payment_state"])

    def _void_original_ncf_if_applicable(self, move, *, reason, cancel_type="04"):
        """Anula NCF tradicional tras NC; no reutiliza número; no toca e-CF transmitido."""
        move.ensure_one()
        if move.justech_do_ncf_voided:
            return False
        if move._justech_void_ncf_gate_error():
            # e-CF ya transmitido: no 608; la NC es el camino
            move.message_post(
                body=_(
                    "Reversión atómica: NCF original no anulado en 608 porque el "
                    "documento es e-CF transmitido/aceptado. Neutralización vía NC."
                )
            )
            return False
        if not move._justech_get_issued_ncf():
            return False
        move.write(
            {
                "justech_do_ncf_void_reason": reason
                or _("Anulación fiscal tras nota de crédito total (flujo atómico)"),
                "justech_do_ncf_cancel_type": cancel_type or "04",
            }
        )
        move.action_void_ncf()
        return True

    def _copy_attachments_to_replacement(self, origin, replacement):
        """Copia adjuntos del origen a la sustituta cuando aplica (sin reutilizar NCF).

        ``sudo()`` limitado a ir.attachment: lectura/copia del adjunto ya ligado
        a la factura origen; no altera ACL de account.move.
        """
        if not origin or not replacement:
            return
        Attach = self.env["ir.attachment"].sudo()
        atts = Attach.search(
            [
                ("res_model", "=", "account.move"),
                ("res_id", "=", origin.id),
            ]
        )
        for att in atts:
            att.copy({"res_id": replacement.id})

    def _assert_residual_neutralized(self, move, *, allow_credit_from_payments=False):
        move.invalidate_recordset(["amount_residual", "payment_state"])
        residual = float(move.amount_residual or 0.0)
        rounding = move.currency_id.rounding
        if float_compare(residual, 0.0, precision_rounding=rounding) == 0:
            return
        # Pagada: residual ya era 0; NC deja crédito en NC, no abre residual en origen
        if allow_credit_from_payments and move.payment_state in (
            "paid",
            "in_payment",
            "reversed",
        ):
            return
        raise UserError(
            _(
                "La reversión atómica no dejó residual en cero "
                "(%(name)s residual=%(residual)s %(currency)s). "
                "Se revirtió la operación; no se permiten estados parciales."
            )
            % {
                "name": move.display_name,
                "residual": residual,
                "currency": move.currency_id.name,
            }
        )

    def execute_full_reversal(
        self,
        move,
        *,
        reason=None,
        cancel_type="04",
        void_original_ncf=True,
        create_replacement=False,
    ):
        """Ejecuta reversión total (y opcionalmente sustituta) en una transacción."""
        move.ensure_one()
        if move.state != "posted":
            raise UserError(_("Solo documentos publicados pueden revertirse."))
        if move.payment_state == "reversed" and float(move.amount_residual or 0) <= 0:
            raise UserError(_("Esta factura ya está completamente revertida."))

        self.assert_can_reverse_invoice(
            move,
            replace=create_replacement,
            paid_ok=False,
        )
        if void_original_ncf and not move.justech_do_ncf_voided:
            self.assert_can_void_ncf(move)

        reason = reason or _(
            "Reversión fiscal total controlada (Corregir o Anular)"
        )
        paid_like = move.payment_state in ("paid", "partial", "in_payment")
        original_ncf = move._justech_get_issued_ncf()
        refunds_before_ids = set(
            self.env["account.move"].search(
                [
                    ("reversed_entry_id", "=", move.id),
                    ("move_type", "in", ("out_refund", "in_refund")),
                ]
            ).ids
        )

        authorized_reversal_enter()
        try:
            with self.env.cr.savepoint():
                wiz = self._build_reversal_wizard(
                    move, reason=reason, is_modify=create_replacement
                )
                if create_replacement:
                    wiz.modify_moves()
                else:
                    wiz.refund_moves()

                new_moves = wiz.new_move_ids
                refunds = new_moves.filtered(
                    lambda m: m.move_type in ("out_refund", "in_refund")
                )
                # Odoo 19 modify_moves: new_move_ids suele traer solo la sustituta;
                # la NC queda vinculada por reversed_entry_id.
                if not refunds:
                    refunds = self.env["account.move"].search(
                        [
                            ("reversed_entry_id", "=", move.id),
                            ("move_type", "in", ("out_refund", "in_refund")),
                            ("state", "!=", "cancel"),
                            ("id", "not in", list(refunds_before_ids)),
                        ]
                    )
                if not refunds:
                    raise UserError(
                        _("No se generó la nota de crédito fiscal esperada.")
                    )

                self._ensure_refunds_posted(refunds)
                self._reconcile_origin_with_refunds(move, refunds)
                self._assert_residual_neutralized(
                    move, allow_credit_from_payments=paid_like
                )

                voided = False
                if void_original_ncf:
                    voided = self._void_original_ncf_if_applicable(
                        move, reason=reason, cancel_type=cancel_type
                    )

                replacement = new_moves.filtered(
                    lambda m: m.move_type in ("out_invoice", "in_invoice")
                    and m.state == "draft"
                )[:1]
                if create_replacement and replacement:
                    if "justech_do_replacement_move_id" in move._fields:
                        move.justech_do_replacement_move_id = replacement.id
                    self._copy_attachments_to_replacement(move, replacement)

                # Trazabilidad
                refund_names = ", ".join(refunds.mapped("display_name"))
                body = _(
                    "<p><b>Reversión fiscal atómica completada</b></p>"
                    "<ul>"
                    "<li>NCF original: %(ncf)s</li>"
                    "<li>Nota(s) de crédito: %(refunds)s</li>"
                    "<li>NCF original anulado (608): %(voided)s</li>"
                    "<li>Residual tras operación: %(residual)s %(currency)s</li>"
                    "%(repl)s"
                    "</ul>"
                ) % {
                    "ncf": original_ncf or "—",
                    "refunds": refund_names,
                    "voided": _("Sí") if voided else _("No / ya anulado / e-CF"),
                    "residual": move.amount_residual,
                    "currency": move.currency_id.name,
                    "repl": (
                        "<li>%s: %s</li>"
                        % (
                            _("Factura sustituta (borrador)"),
                            replacement.display_name,
                        )
                        if replacement
                        else ""
                    ),
                }
                move.message_post(body=body)
                for refund in refunds:
                    refund.message_post(
                        body=_(
                            "Nota de crédito generada por flujo atómico Justech "
                            "desde %(origin)s (NCF origen %(ncf)s)."
                        )
                        % {
                            "origin": move.display_name,
                            "ncf": original_ncf or "—",
                        }
                    )

                # Estados visibles: anulación mediante NC (no «Revertido» ambiguo)
                if "justech_do_cancellation_method" in move._fields:
                    move.write(
                        {
                            "justech_do_cancellation_method": "credit_note",
                            "justech_do_fiscal_regularization_state": (
                                "cancelled_via_credit_note"
                                if (voided or move.justech_do_ncf_voided)
                                else move.justech_do_fiscal_regularization_state
                            ),
                        }
                    )

                return {
                    "origin": move,
                    "refunds": refunds,
                    "replacement": replacement,
                    "voided_original_ncf": voided,
                }
        finally:
            authorized_reversal_exit()

    def execute_historical_repair_voided_open_residual(
        self, move, *, reason=None, cancel_type="04"
    ):
        """API reservada: repara NCF anulado + residual abierto (no usada por el wizard).

        La fase unificada solo lista estos casos. Este método reutiliza
        ``execute_full_reversal`` con ``void_original_ncf=False`` para una
        reparación controlada futura — no se invoca automáticamente.
        """
        move.ensure_one()
        if not move.justech_do_ncf_voided:
            raise UserError(
                _(
                    "Esta reparación solo aplica cuando el NCF ya está anulado "
                    "y el residual contable sigue abierto."
                )
            )
        if float_compare(
            move.amount_residual, 0.0, precision_rounding=move.currency_id.rounding
        ) <= 0:
            raise UserError(_("El residual ya está en cero; no hay nada que reparar."))
        reason = reason or _(
            "Reparación histórica LAB: NCF anulado con residual abierto → NC fiscal"
        )
        # No volver a anular el NCF (ya anulado)
        return self.execute_full_reversal(
            move,
            reason=reason,
            cancel_type=cancel_type,
            void_original_ncf=False,
            create_replacement=False,
        )
