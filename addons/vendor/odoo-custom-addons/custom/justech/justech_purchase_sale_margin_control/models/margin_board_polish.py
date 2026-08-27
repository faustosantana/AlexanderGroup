# -*- coding: utf-8 -*-
"""19.0.8.1.0 — Dashboard sin NewId, sin dirty save, display_name limpio."""
from odoo import _, api, fields, models


class PurchaseSaleMarginBoardPolish(models.TransientModel):
    _inherit = "purchase.sale.margin.board"

    display_name = fields.Char(compute="_compute_board_display_name")

    @api.depends_context("uid")
    def _compute_board_display_name(self):
        for rec in self:
            rec.display_name = _("Resumen financiero")

    @api.model
    def name_create(self, name):
        # Never create from autocomplete with technical labels
        rec = self.create({})
        return rec.id, _("Resumen financiero")

    @api.model
    def get_board_action(self, res_id=False):
        if not res_id:
            board = self.create({})
            board.action_refresh_silent()
            res_id = board.id
        else:
            board = self.browse(res_id)
            if board.exists():
                board.action_refresh_silent()
        return {
            "type": "ir.actions.act_window",
            "name": _("Resumen financiero"),
            "res_model": "purchase.sale.margin.board",
            "res_id": res_id,
            "view_mode": "form",
            "view_id": self.env.ref(
                "justech_purchase_sale_margin_control.view_purchase_sale_margin_board_form"
            ).id,
            "target": "current",
            "context": {"form_view_initial_mode": "edit", "create": False},
        }

    def action_refresh_silent(self):
        """Recalcula KPIs sin reabrir la ventana (evita dirty / NewId)."""
        for board in self:
            vals = board._compute_kpis(
                board._get_scope_companies(), board.date_from, board.date_to
            )
            board.write(vals)
        return True

    def action_refresh(self):
        self.ensure_one()
        self.action_refresh_silent()
        return {
            "type": "ir.actions.act_window",
            "name": _("Resumen financiero"),
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "view_id": self.env.ref(
                "justech_purchase_sale_margin_control.view_purchase_sale_margin_board_form"
            ).id,
            "target": "current",
            "context": dict(self.env.context, create=False),
        }

    @api.onchange("date_from", "date_to", "company_id")
    def _onchange_board_filters(self):
        vals = self._compute_kpis(self._get_scope_companies(), self.date_from, self.date_to)
        for key, value in vals.items():
            if key in self._fields:
                self[key] = value
