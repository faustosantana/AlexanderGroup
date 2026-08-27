# -*- coding: utf-8 -*-
"""Wizard modal: Anular comprobante fiscal (motivo 608 + observación)."""
from odoo import _, api, fields, models
from odoo.exceptions import UserError


def _justech_void_cancel_type_selection(env):
    """Catálogo real 608 desde account.move + opción UX «Otro» (nunca se exporta 99)."""
    field = env["account.move"]._fields.get("justech_do_ncf_cancel_type")
    selection = list(field.selection or []) if field else []
    if not any(code == "99" for code, _label in selection):
        selection.append(("99", "99 — Otro"))
    return selection


class JustechDoNcfVoidWizard(models.TransientModel):
    _name = "justech.do.ncf.void.wizard"
    _description = "Anular comprobante fiscal"

    move_id = fields.Many2one(
        "account.move", string="Factura", required=True, readonly=True, ondelete="cascade"
    )
    company_id = fields.Many2one(related="move_id.company_id", string="Empresa", readonly=True)
    partner_id = fields.Many2one(related="move_id.partner_id", string="Cliente", readonly=True)
    document_type_id = fields.Many2one(
        related="move_id.justech_do_document_type_id",
        string="Tipo de comprobante",
        readonly=True,
    )
    ncf = fields.Char(string="NCF", compute="_compute_ncf", readonly=True)
    invoice_date = fields.Date(related="move_id.invoice_date", string="Fecha", readonly=True)
    state = fields.Selection(related="move_id.state", string="Estado actual", readonly=True)
    payment_state = fields.Selection(
        related="move_id.payment_state", string="Estado de pago", readonly=True
    )
    amount_residual = fields.Monetary(
        related="move_id.amount_residual", string="Residual", readonly=True
    )
    currency_id = fields.Many2one(related="move_id.currency_id", readonly=True)
    payment_warning = fields.Char(string="Aviso de pago", compute="_compute_warnings")
    accounting_warning = fields.Char(
        string="Advertencia contable",
        compute="_compute_warnings",
    )
    delivery_warning = fields.Char(string="Aviso de entrega", compute="_compute_warnings")
    acknowledge_accounting_intact = fields.Boolean(
        string=(
            "Confirmo que esta acción solo anula el número fiscal y no elimina "
            "la cuenta por cobrar/pagar, no revierte ingresos/gastos/impuestos "
            "ni crea una nota de crédito."
        ),
        default=False,
    )
    cancel_type = fields.Selection(
        selection="_selection_cancel_type",
        string="Motivo de anulación",
        required=True,
        default="04",
        help="Catálogo DGII formato 608 instalado en el documento fiscal.",
    )
    observation = fields.Text(
        string="Observación adicional",
        help="Detalle libre del motivo. Obligatoria si el motivo es «Otro».",
    )
    requester_id = fields.Many2one(
        "res.users",
        string="Usuario solicitante",
        readonly=True,
        default=lambda self: self.env.user,
    )
    help_note = fields.Char(
        string="Ayuda",
        readonly=True,
        default=(
            "Anular el NCF registra el comprobante en el 608. "
            "Esta acción no equivale necesariamente a emitir una nota de crédito "
            "ni a devolver un pago."
        ),
    )

    @api.model
    def _selection_cancel_type(self):
        return _justech_void_cancel_type_selection(self.env)

    @api.depends("move_id", "move_id.justech_do_ncf", "move_id.l10n_latam_document_number")
    def _compute_ncf(self):
        for wiz in self:
            wiz.ncf = wiz.move_id._justech_get_issued_ncf() if wiz.move_id else False

    @api.depends(
        "move_id",
        "move_id.payment_state",
        "move_id.amount_residual",
        "move_id.is_move_sent",
    )
    def _compute_warnings(self):
        for wiz in self:
            wiz.accounting_warning = _(
                "Esta acción solo anula el número fiscal. No elimina la cuenta por "
                "cobrar o pagar, no revierte ingresos, gastos ni impuestos y no crea "
                "una nota de crédito. Residual actual: %(residual)s %(currency)s."
            ) % {
                "residual": wiz.move_id.amount_residual if wiz.move_id else 0.0,
                "currency": wiz.move_id.currency_id.name if wiz.move_id else "",
            }
            ps = wiz.move_id.payment_state if wiz.move_id else False
            if ps in ("paid", "partial", "in_payment"):
                wiz.payment_warning = _(
                    "Esta factura tiene pagos o está conciliada parcialmente "
                    "(%s). La anulación fiscal del NCF no cancela pagos ni "
                    "conciliaciones; use nota de crédito u operación contable "
                    "estándar si debe revertir el cobro."
                ) % (ps,)
            else:
                wiz.payment_warning = False
            if wiz.move_id and wiz.move_id.is_move_sent:
                wiz.delivery_warning = _(
                    "El documento figura como enviado/entregado. Si el cliente "
                    "recibió la factura, el flujo recomendado es nota de crédito, "
                    "no solo anular el NCF."
                )
            else:
                wiz.delivery_warning = False

    def action_confirm_void(self):
        self.ensure_one()
        move = self.move_id
        if move.justech_do_ncf_voided:
            raise UserError(_("Este comprobante fiscal ya fue anulado."))
        if move.state != "posted":
            raise UserError(_("Solo documentos publicados pueden anular el comprobante fiscal."))
        if not move._justech_get_issued_ncf():
            raise UserError(_("No hay comprobante fiscal para anular."))
        gate = move._justech_void_ncf_gate_error()
        if gate:
            raise UserError(gate)
        if not self.acknowledge_accounting_intact:
            raise UserError(
                _(
                    "Debe confirmar expresamente que comprende que esta acción "
                    "solo anula el NCF y no revierte la factura contablemente."
                )
            )
        if not self.cancel_type:
            raise UserError(_("Debe indicar el motivo de anulación."))
        observation = (self.observation or "").strip()
        if self.cancel_type == "99" and not observation:
            raise UserError(
                _("Si el motivo es «Otro», debe indicar una observación adicional.")
            )
        label = dict(self._selection_cancel_type()).get(self.cancel_type, self.cancel_type)
        reason = observation or label
        # 99 es solo UX; el 608 exporta códigos 01–10 del catálogo instalado.
        dgii_code = self.cancel_type if self.cancel_type != "99" else "04"
        move.write(
            {
                "justech_do_ncf_void_reason": reason,
                "justech_do_ncf_cancel_type": dgii_code,
            }
        )
        move.with_context(
            justech_void_from_wizard=True,
            justech_void_cancel_label=label,
            justech_void_observation=observation,
        ).action_void_ncf()
        # Guía post-void si residual sigue abierto
        if float(move.amount_residual or 0) > 0:
            move.message_post(
                body=_(
                    "Recordatorio: el NCF fue anulado para 608, pero el residual "
                    "%(residual)s %(currency)s sigue abierto. Si la operación "
                    "comercial debe quedar sin efecto, use «Revertir factura» "
                    "(nota de crédito)."
                )
                % {
                    "residual": move.amount_residual,
                    "currency": move.currency_id.name,
                }
            )
        return {"type": "ir.actions.act_window_close"}
