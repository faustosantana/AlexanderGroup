# -*- coding: utf-8 -*-
"""Wizard unificado: Corregir o Anular (2 decisiones).

1) Anular mediante Nota de Crédito
2) Cancelar factura y asiento

«Corregir» y «NC parcial» permanecen en código/acciones separadas;
no se muestran en este wizard.
"""
from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError


class JustechDoInvoiceCorrectWizard(models.TransientModel):
    _name = "justech.do.invoice.correct.wizard"
    _description = "Corregir o Anular"

    move_id = fields.Many2one(
        "account.move",
        string="Documento",
        required=True,
        readonly=True,
        ondelete="cascade",
    )
    partner_id = fields.Many2one(related="move_id.partner_id", readonly=True)
    state = fields.Selection(related="move_id.state", readonly=True)
    payment_state = fields.Selection(related="move_id.payment_state", readonly=True)
    amount_total = fields.Monetary(related="move_id.amount_total", readonly=True)
    amount_residual = fields.Monetary(related="move_id.amount_residual", readonly=True)
    currency_id = fields.Many2one(related="move_id.currency_id", readonly=True)
    ncf = fields.Char(compute="_compute_context_fields", readonly=True)
    fiscal_ui_status = fields.Selection(
        related="move_id.justech_do_fiscal_ui_status", readonly=True
    )
    operational_ui_status = fields.Selection(
        related="move_id.justech_do_operational_ui_status", readonly=True
    )
    delivery_state = fields.Selection(
        related="move_id.justech_do_customer_delivery_state",
        readonly=True,
        string="Estado de entrega al cliente",
    )
    recommended_action = fields.Selection(
        selection=[
            ("cancel_complete", "Anular mediante Nota de Crédito"),
            ("cancel_entry", "Cancelar factura y asiento"),
            ("blocked", "Sin acción automática — revisar"),
        ],
        string="Acción recomendada",
        compute="_compute_context_fields",
    )
    recommendation_reason = fields.Text(
        string="Por qué se recomienda",
        compute="_compute_context_fields",
    )
    effect_accounting = fields.Text(compute="_compute_option_effects")
    effect_fiscal = fields.Text(compute="_compute_option_effects")
    effect_payments = fields.Text(compute="_compute_option_effects")
    effect_documents = fields.Text(compute="_compute_option_effects")
    effect_reports = fields.Text(compute="_compute_option_effects")
    confirmation_summary = fields.Text(
        string="Resumen automático",
        compute="_compute_option_effects",
    )
    payment_warning = fields.Char(compute="_compute_context_fields")
    historical_alert = fields.Char(compute="_compute_context_fields")
    delivery_block_alert = fields.Char(compute="_compute_context_fields")
    cn_conversion_warning = fields.Text(compute="_compute_context_fields")
    needs_cn_conversion = fields.Boolean(compute="_compute_context_fields")
    can_reverse = fields.Boolean(compute="_compute_context_fields")
    can_direct_cancel = fields.Boolean(compute="_compute_context_fields")
    permission_warning = fields.Char(compute="_compute_context_fields")
    permission_blocked = fields.Boolean(compute="_compute_context_fields")
    permission_title = fields.Char(compute="_compute_context_fields")
    permission_message = fields.Text(compute="_compute_context_fields")
    permission_company = fields.Char(compute="_compute_context_fields")
    permission_required = fields.Char(compute="_compute_context_fields")
    permission_role = fields.Char(compute="_compute_context_fields")

    action_choice = fields.Selection(
        selection=[
            ("cancel_complete", "1. Anular mediante Nota de Crédito"),
            ("cancel_entry", "2. Cancelar factura y asiento"),
        ],
        string="¿Qué desea hacer?",
        required=True,
        default="cancel_complete",
    )
    user_confirmed = fields.Boolean(
        string="Confirmo que deseo continuar con esta operación automática",
        default=False,
    )

    # --- Cancelación directa ---
    not_delivered_declaration = fields.Boolean(
        string=(
            "Confirmo que el cliente no recibió ni tuvo acceso a este comprobante"
        ),
        default=False,
    )
    confirm_cn_cancel = fields.Boolean(
        string=(
            "Confirmo la cancelación de la factura y de la Nota de Crédito vinculada"
        ),
        default=False,
    )
    direct_cancel_reason = fields.Text(string="Motivo de la cancelación")
    fiscal_treatment_planned = fields.Selection(
        selection=[
            ("format_608", "Incluir en Formato 608"),
            ("rectify_607", "Rectificar Formato 607"),
        ],
        string="Tratamiento fiscal previsto",
    )
    direct_cancel_type = fields.Selection(
        selection=[
            ("01", "01 — Secuencia no utilizada"),
            ("04", "04 — Corrección de información"),
        ],
        string="Tipo anulación DGII (608)",
        default="01",
    )
    included_in_607_warning = fields.Char(compute="_compute_context_fields")
    unknown_delivery_justification = fields.Text(
        string="Justificación (entrega desconocida)",
    )

    def _clear_permission_ux(self, wiz):
        wiz.permission_warning = False
        wiz.permission_blocked = False
        wiz.permission_title = False
        wiz.permission_message = False
        wiz.permission_company = False
        wiz.permission_required = False
        wiz.permission_role = False

    def _apply_permission_ux(self, wiz, exc):
        raw = str(exc)
        company = wiz.move_id.company_id.display_name or wiz.move_id.company_id.name
        code = None
        perm = None
        role = None
        if "|" in raw and raw.startswith("PERMISO_"):
            parts = raw.split("|", 3)
            code = parts[0]
            if len(parts) > 1 and parts[1]:
                company = parts[1]
            if len(parts) > 2:
                perm = parts[2]
            if len(parts) > 3:
                role = parts[3]
        labels = {
            "PERMISO_RECUPERACION": (
                _("Recuperación Contable"),
                _("Administrador Contable / Fiscal / Sistema"),
                _(
                    "Necesita autorización para corregir o anular facturas.\n\n"
                    "Solicite «Recuperación Contable» o un Administrador "
                    "Contable / Fiscal.\n\nEmpresa: %(company)s"
                )
                % {"company": company},
            ),
            "PERMISO_EMPRESA": (
                _("Acceso a la empresa"),
                _("Empresas autorizadas del usuario"),
                _(
                    "No tiene acceso a la empresa %(company)s en el selector "
                    "multiempresa."
                )
                % {"company": company},
            ),
            "PERMISO_FISCAL_NCF": (
                _("Administrador Fiscal / Contable / Sistema"),
                _("Administrador Fiscal + Recuperación Contable"),
                _(
                    "Para cancelar una factura con NCF (no entregado) se requiere "
                    "además Administrador Fiscal, Contable o del Sistema.\n\n"
                    "Empresa: %(company)s"
                )
                % {"company": company},
            ),
        }
        if code in labels:
            default_perm, default_role, message = labels[code]
            perm = perm or default_perm
            role = role or default_role
        else:
            message = _(
                "Necesita autorización para corregir o anular facturas.\n\n"
                "Solicite «Recuperación Contable» o un Administrador "
                "Contable / Fiscal."
            )
            perm = perm or _("Recuperación Contable")
            role = role or _("Administrador Contable / Fiscal")
        wiz.permission_blocked = True
        wiz.permission_title = _("Necesita autorización para corregir o anular facturas")
        wiz.permission_message = message
        wiz.permission_company = company
        wiz.permission_required = perm
        wiz.permission_role = role
        wiz.permission_warning = wiz.permission_title

    @api.depends(
        "move_id",
        "move_id.state",
        "move_id.payment_state",
        "move_id.amount_residual",
        "move_id.justech_do_ncf_voided",
        "move_id.justech_do_customer_delivery_state",
        "move_id.justech_do_included_in_607",
        "move_id.is_move_sent",
        "action_choice",
    )
    def _compute_context_fields(self):
        Flow = self.env["justech.do.invoice.reversal.flow.service"]
        Direct = self.env["justech.do.invoice.direct.cancel.service"]
        for wiz in self:
            move = wiz.move_id
            if not move:
                wiz.ncf = False
                wiz.recommended_action = "blocked"
                wiz.recommendation_reason = False
                wiz.payment_warning = False
                wiz.historical_alert = False
                wiz.delivery_block_alert = False
                wiz.cn_conversion_warning = False
                wiz.needs_cn_conversion = False
                wiz.included_in_607_warning = False
                wiz.can_reverse = False
                wiz.can_direct_cancel = False
                self._clear_permission_ux(wiz)
                continue
            wiz.ncf = move._justech_get_issued_ncf()
            analysis = move._justech_direct_cancel_analysis()
            direct_gate = analysis.get("error") or False
            wiz.can_direct_cancel = not bool(direct_gate)
            wiz.needs_cn_conversion = bool(analysis.get("needs_cn_conversion"))
            wiz.can_reverse = (
                move.state == "posted"
                and move.payment_state != "reversed"
                and float(move.amount_residual or 0) > 0
            )

            if wiz.needs_cn_conversion and analysis.get("refunds"):
                cn_names = ", ".join(analysis["refunds"].mapped("display_name"))
                wiz.cn_conversion_warning = _(
                    "Esta factura ya fue neutralizada mediante la Nota de Crédito "
                    "%(cn)s. Para cancelarla directamente, el ERP cancelará también "
                    "esa Nota de Crédito y sus asientos. Ambos comprobantes "
                    "conservarán su numeración y quedarán anulados, no reutilizables "
                    "y pendientes de regularización ante la DGII."
                ) % {"cn": cn_names}
            else:
                wiz.cn_conversion_warning = False

            if direct_gate and wiz.action_choice == "cancel_entry":
                wiz.delivery_block_alert = direct_gate
            else:
                wiz.delivery_block_alert = False

            if move.justech_do_included_in_607:
                wiz.included_in_607_warning = _(
                    "Este documento está marcado como incluido en 607. "
                    "La cancelación directa exige 608 o rectificar 607 "
                    "y autorización fiscal reforzada."
                )
            else:
                wiz.included_in_607_warning = False

            if move.justech_do_ncf_voided and float(move.amount_residual or 0) > 0:
                wiz.historical_alert = _(
                    "El NCF ya está anulado, pero la factura mantiene saldo contable "
                    "abierto. Prefiera «Anular mediante Nota de Crédito»."
                )
            else:
                wiz.historical_alert = False

            # Solo pagos REALES — nunca payment_state=reversed
            if move._justech_has_real_payments() or move.payment_state in (
                "paid",
                "partial",
                "in_payment",
            ):
                if move.payment_state == "reversed" and not move._justech_has_real_payments():
                    wiz.payment_warning = False
                elif move._justech_has_real_payments():
                    wiz.payment_warning = _(
                        "Existe un pago bancario vinculado. "
                        "La cancelación directa está bloqueada."
                    )
                else:
                    wiz.payment_warning = _(
                        "Esta factura tiene pagos (%s). Use Nota de Crédito."
                    ) % (move.payment_state,)
            else:
                wiz.payment_warning = False

            try:
                if wiz.action_choice == "cancel_complete":
                    Flow.assert_can_reverse_invoice(move, replace=False)
                    if not move.justech_do_ncf_voided:
                        Flow.assert_can_void_ncf(move)
                elif wiz.action_choice == "cancel_entry":
                    Direct.assert_can_direct_cancel(move, delivery_unknown_ok=True)
                self._clear_permission_ux(wiz)
            except AccessError as exc:
                self._apply_permission_ux(wiz, exc)
            except Exception:
                self._clear_permission_ux(wiz)

            # Recommendation
            if wiz.can_direct_cancel and wiz.needs_cn_conversion:
                wiz.recommended_action = "cancel_entry"
                wiz.recommendation_reason = _(
                    "Factura neutralizada solo por NC (sin pagos reales): "
                    "puede convertir a cancelación directa de factura + NC."
                )
            elif wiz.can_direct_cancel:
                delivery = move.justech_do_customer_delivery_state or "unknown"
                if delivery == "not_delivered" and not move.is_move_sent:
                    wiz.recommended_action = "cancel_entry"
                    wiz.recommendation_reason = _(
                        "Comprobante no entregado y sin actividad posterior: "
                        "puede cancelar factura y asiento sin emitir NC."
                    )
                else:
                    wiz.recommended_action = "cancel_complete"
                    wiz.recommendation_reason = _(
                        "Prefiera anulación mediante Nota de Crédito salvo "
                        "declaración explícita de no entrega."
                    )
            elif move.justech_do_ncf_voided and float(move.amount_residual or 0) > 0:
                wiz.recommended_action = "cancel_complete"
                wiz.recommendation_reason = _(
                    "NCF anulado + residual abierto: anular mediante Nota de Crédito."
                )
            else:
                wiz.recommended_action = "cancel_complete"
                wiz.recommendation_reason = _(
                    "Anulación mediante Nota de Crédito neutraliza residual, "
                    "ingreso e impuestos."
                )

    @api.depends("action_choice", "move_id", "needs_cn_conversion")
    def _compute_option_effects(self):
        for wiz in self:
            if wiz.action_choice == "cancel_entry":
                if wiz.needs_cn_conversion:
                    wiz.effect_accounting = _(
                        "Desconcilia factura↔NC, cancela ambos asientos "
                        "(button_cancel). No crea NC nueva."
                    )
                    wiz.effect_fiscal = _(
                        "Ambos NCF quedan anulados / no reutilizables y "
                        "pendientes de regularización (608 / rectificar 607)."
                    )
                    wiz.effect_documents = _(
                        "Factura + NC conservan numeración; estado Cancelado."
                    )
                else:
                    wiz.effect_accounting = _(
                        "Cancela directamente la factura y su asiento. "
                        "No crea Nota de Crédito."
                    )
                    wiz.effect_fiscal = _(
                        "NCF anulado, no reutilizable; pendiente de regularización."
                    )
                    wiz.effect_documents = _(
                        "La factura permanece (Cancelado). No se elimina."
                    )
                wiz.effect_payments = _(
                    "Bloqueado si existen pagos bancarios reales o retenciones."
                )
                wiz.effect_reports = _(
                    "Sale de CxC / ingresos vigentes. Obligación 608 o rectificar 607."
                )
                wiz.confirmation_summary = _(
                    "Confirmo que esta factura y su NCF no fueron entregados, enviados, "
                    "comunicados ni puestos a disposición del cliente. Entiendo que la "
                    "empresa deberá gestionar la anulación o rectificación "
                    "correspondiente ante la DGII.\n\n¿Desea continuar?"
                )
            else:
                wiz.effect_accounting = _(
                    "Nota de crédito total + asiento inverso + conciliación. "
                    "Residual = 0. Estado: Neutralizado mediante NC."
                )
                wiz.effect_fiscal = _(
                    "Emite NC fiscal y anula el NCF original cuando corresponde. "
                    "Estado fiscal: Anulado mediante Nota de Crédito."
                )
                wiz.effect_payments = _(
                    "No borra pagos. Puede dejar crédito a favor si había cobros."
                )
                wiz.effect_documents = _("Factura original + NC vinculada.")
                wiz.effect_reports = _("607/606 con NC; 608 si se anula el NCF original.")
                wiz.confirmation_summary = _(
                    "Anulación mediante Nota de Crédito:\n"
                    "✔ Emitir y publicar NC fiscal\n"
                    "✔ Conciliar y residual = 0\n"
                    "✔ Trazabilidad completa\n\n"
                    "¿Desea continuar?"
                )

    def _flow(self):
        return self.env["justech.do.invoice.reversal.flow.service"]

    def _direct(self):
        return self.env["justech.do.invoice.direct.cancel.service"]

    def action_continue(self):
        self.ensure_one()
        if self.permission_blocked:
            raise UserError(
                self.permission_message
                or _("No tiene autorización fiscal para continuar.")
            )
        if not self.user_confirmed:
            raise UserError(
                _(
                    "Debe confirmar el resumen automático antes de continuar. "
                    "Marque la casilla de confirmación."
                )
            )
        move = self.move_id
        choice = self.action_choice
        Flow = self._flow()

        if choice == "cancel_entry":
            if not self.can_direct_cancel:
                raise UserError(
                    self.delivery_block_alert
                    or _(
                        "Esta factura no es elegible para cancelación directa."
                    )
                )
            if not self.not_delivered_declaration:
                raise UserError(
                    _(
                        "Debe marcar: «Confirmo que el cliente no recibió ni tuvo "
                        "acceso a este comprobante»."
                    )
                )
            if self.needs_cn_conversion and not self.confirm_cn_cancel:
                raise UserError(
                    _(
                        "Debe confirmar la cancelación de la factura y de la "
                        "Nota de Crédito vinculada."
                    )
                )
            if not (self.direct_cancel_reason or "").strip():
                raise UserError(_("Debe indicar el motivo de la cancelación."))
            if self.fiscal_treatment_planned not in ("format_608", "rectify_607"):
                raise UserError(
                    _(
                        "Seleccione tratamiento fiscal: Incluir en Formato 608 "
                        "o Rectificar Formato 607."
                    )
                )
            result = self._direct().execute_direct_cancel(
                move,
                reason=self.direct_cancel_reason,
                fiscal_treatment=self.fiscal_treatment_planned,
                cancel_type=self.direct_cancel_type or "01",
                not_delivered_confirmed=True,
                delivery_unknown_justification=self.unknown_delivery_justification,
                confirm_cn_cancel=self.confirm_cn_cancel
                if self.needs_cn_conversion
                else True,
            )
            return {
                "type": "ir.actions.act_window",
                "name": _("Factura cancelada"),
                "res_model": "account.move",
                "view_mode": "form",
                "res_id": result["origin"].id,
                "target": "current",
            }

        if choice == "cancel_complete":
            if not self.can_reverse:
                raise UserError(
                    _(
                        "No es posible anular mediante NC este documento "
                        "(ya neutralizado o no publicado)."
                    )
                )
            result = Flow.execute_full_reversal(
                move,
                reason=_("Anulación mediante Nota de Crédito (Corregir o Anular)"),
                void_original_ncf=True,
                create_replacement=False,
            )
            refunds = result["refunds"]
            return {
                "type": "ir.actions.act_window",
                "name": _("Nota de crédito"),
                "res_model": "account.move",
                "view_mode": "form",
                "res_id": refunds[:1].id,
                "target": "current",
            }

        raise UserError(_("Seleccione una acción válida."))

    # --- Acciones separadas (no visibles en radio del wizard) ---
    def action_correct_invoice_separate(self):
        """Corregir con sustituta — API interna / botón separado."""
        self.ensure_one()
        Flow = self._flow()
        move = self.move_id
        Flow.assert_can_reverse_invoice(move, replace=True)
        result = Flow.execute_full_reversal(
            move,
            reason=_("Corrección con factura sustituta"),
            void_original_ncf=True,
            create_replacement=True,
        )
        replacement = result.get("replacement")
        target = replacement or result["refunds"][:1]
        return {
            "type": "ir.actions.act_window",
            "res_model": "account.move",
            "view_mode": "form",
            "res_id": target.id,
            "target": "current",
        }

    def action_credit_partial_separate(self):
        """NC parcial — API interna / botón separado."""
        self.ensure_one()
        move = self.move_id
        Flow = self._flow()
        Flow.assert_can_reverse_invoice(move, replace=False)
        action = move.action_justech_reverse_invoice()
        if isinstance(action, dict):
            ctx = move._justech_parse_action_context(action)
            ctx["justech_reverse_partial"] = True
            ctx.setdefault("active_model", "account.move")
            ctx.setdefault("active_id", move.id)
            ctx.setdefault("active_ids", [move.id])
            action["context"] = ctx
            action["name"] = _("Nota de crédito parcial")
        return action
