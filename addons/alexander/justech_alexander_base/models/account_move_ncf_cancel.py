"""When a Doralex invoice is cancelled, void its NCF in the same operation."""

from odoo import fields, models
from odoo.exceptions import UserError


class AccountMove(models.Model):
    _inherit = "account.move"

    def _dx_void_ncf_before_cancel(self):
        """Mark issued NCF as voided (608) before the move is cancelled."""
        now = fields.Datetime.now()
        Consumption = (
            self.env["justech.do.ncf.consumption"]
            if "justech.do.ncf.consumption" in self.env
            else False
        )
        for move in self:
            if move.state != "posted":
                continue
            if move.move_type not in (
                "out_invoice",
                "in_invoice",
                "out_refund",
                "in_refund",
            ):
                continue
            if not hasattr(move, "_justech_get_issued_ncf"):
                continue
            issued = move._justech_get_issued_ncf()
            if not issued or move.justech_do_ncf_voided:
                continue
            if hasattr(move, "_justech_void_ncf_gate_error"):
                gate = move._justech_void_ncf_gate_error()
                if gate:
                    raise UserError(gate)
            reason = move.justech_do_ncf_void_reason or "Anulación de factura"
            cancel_type = move.justech_do_ncf_cancel_type or "04"
            vals = {
                "justech_do_ncf_void_reason": reason,
                "justech_do_ncf_cancel_type": cancel_type,
                "justech_do_ncf_voided": True,
                "justech_do_ncf_void_date": fields.Date.context_today(move),
                "justech_do_dgii_line_status": "2",
                "justech_do_dgii_fiscal_state": "cancelled",
                "justech_do_include_in_dgii": False,
            }
            if not move.justech_do_ncf:
                vals["justech_do_ncf"] = issued
            move.with_context(justech_ncf_engine=True).write(vals)
            if Consumption:
                consumption = Consumption.sudo().search(
                    [
                        ("move_id", "=", move.id),
                        ("ncf", "=", issued),
                        ("state", "=", "consumed"),
                    ],
                    limit=1,
                )
                if consumption:
                    consumption.sudo().with_context(justech_ncf_engine=True).write(
                        {
                            "state": "voided",
                            "void_user_id": self.env.user.id,
                            "void_datetime": now,
                            "void_reason": reason,
                        }
                    )
            if "justech.do.fiscal.regularization.service" in self.env:
                try:
                    self.env[
                        "justech.do.fiscal.regularization.service"
                    ].ensure_regularization_for_move(
                        move,
                        reason=reason,
                        cancel_type=cancel_type,
                        source_operation="direct_cancel",
                        cancelled_by=self.env.user,
                    )
                except Exception:
                    move.message_post(
                        body="NCF %s anulado con la factura. Revise regularización 608."
                        % issued
                    )
