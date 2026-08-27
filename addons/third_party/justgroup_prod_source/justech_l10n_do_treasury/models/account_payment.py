"""Campos de visualización para Pagos abiertos (sin alterar lógica contable)."""
from __future__ import annotations

from odoo import api, fields, models


class AccountPayment(models.Model):
    _inherit = "account.payment"

    treasury_amount_applied = fields.Monetary(
        string="Aplicado (pago abierto)",
        currency_field="currency_id",
        compute="_compute_treasury_open_metrics",
        store=True,
    )
    treasury_amount_available = fields.Monetary(
        string="Saldo disponible",
        currency_field="currency_id",
        compute="_compute_treasury_open_metrics",
        store=True,
    )
    treasury_open_state = fields.Selection(
        [
            ("open", "Abierto"),
            ("partial", "Aplicado parcialmente"),
            ("applied", "Aplicado completamente"),
            ("cancelled", "Anulado"),
        ],
        string="Estado pago abierto",
        compute="_compute_treasury_open_metrics",
        store=True,
    )
    treasury_is_open = fields.Boolean(
        string="Es pago abierto",
        compute="_compute_treasury_open_metrics",
        store=True,
        index=True,
    )
    treasury_concept = fields.Char(
        string="Concepto",
        compute="_compute_treasury_concept",
    )
    treasury_bank_state = fields.Selection(
        [
            ("not_posted", "No requiere conciliación bancaria"),
            ("bank_pending", "Pendiente de conciliación bancaria"),
            ("bank_reconciled", "Conciliado con el banco"),
        ],
        string="Estado bancario",
        compute="_compute_treasury_bank_state",
        store=True,
    )
    treasury_payment_reference = fields.Char(
        string="Referencia",
        related="justech_payment_reference",
        readonly=True,
    )

    @api.model
    def _treasury_counterpart_lines(self, payment):
        if not payment.move_id:
            return payment.env["account.move.line"]
        valid_types = payment._get_valid_payment_account_types()
        return payment.move_id.line_ids.filtered(
            lambda line: line.account_id.account_type in valid_types
        )

    @api.model
    def _treasury_available_amount(self, payment):
        lines = self._treasury_counterpart_lines(payment)
        if not lines:
            return 0.0
        return sum(abs(line.amount_residual) for line in lines)

    @api.model
    def _treasury_search_open_for_partner(self, partner, partner_type):
        payment_type = "inbound" if partner_type == "customer" else "outbound"
        candidates = self.search(
            [
                ("partner_id", "=", partner.id),
                ("partner_type", "=", partner_type),
                ("payment_type", "=", payment_type),
                ("treasury_is_open", "=", True),
            ]
        )
        return candidates

    @api.depends("memo", "payment_reference", "name")
    def _compute_treasury_concept(self):
        """Concepto de pago — solo campos reales de account.payment en Odoo 19.

        Odoo 19 no tiene ``ref`` en account.payment; la fuente principal es ``memo``.
        """
        for pay in self:
            concept = ""
            if "memo" in pay._fields:
                concept = (pay.memo or "").strip()
            if not concept and "payment_reference" in pay._fields:
                concept = (pay.payment_reference or "").strip()
            if not concept and "name" in pay._fields:
                concept = (pay.name or "").strip()
            pay.treasury_concept = concept

    @api.depends(
        "state",
        "amount",
        "currency_id",
        "outstanding_account_id",
        "move_id.line_ids.reconciled",
        "move_id.line_ids.account_id",
        "move_id.line_ids.account_id.account_type",
    )
    def _compute_treasury_bank_state(self):
        """Estado bancario vs conciliación de liquidez / outstanding.

        Con cuentas outstanding (estándar Odoo), la partida a conciliar con el
        extracto suele ser ``asset_current`` (u otro tipo), no ``asset_cash``.
        Antes solo se miraba cash/credit_card → ``bank_pending`` falso tras conciliar.

        HOTFIX 2026.1.4: monto <= 0 nunca es «Conciliado con el banco».
        Líneas a cero quedan ``reconciled=True`` sin extracto bancario real.
        """
        liquidity_types = ("asset_cash", "asset_credit_card")
        for pay in self:
            if pay.state not in ("in_process", "paid"):
                pay.treasury_bank_state = "not_posted"
                continue
            currency = pay.currency_id or pay.company_id.currency_id
            if currency.compare_amounts(pay.amount or 0.0, 0.0) <= 0:
                pay.treasury_bank_state = "bank_pending"
                continue
            if not pay.move_id:
                pay.treasury_bank_state = "bank_pending"
                continue
            liquidity_lines = pay.move_id.line_ids.filtered(
                lambda line: line.account_id.account_type in liquidity_types
            )
            if pay.outstanding_account_id:
                outstanding_lines = pay.move_id.line_ids.filtered(
                    lambda line: line.account_id == pay.outstanding_account_id
                )
                if outstanding_lines:
                    liquidity_lines = outstanding_lines
            if not liquidity_lines:
                pay.treasury_bank_state = "bank_pending"
            elif all(line.reconciled for line in liquidity_lines):
                pay.treasury_bank_state = "bank_reconciled"
            else:
                pay.treasury_bank_state = "bank_pending"

    @api.depends(
        "state",
        "amount",
        "currency_id",
        "move_id.line_ids.amount_residual",
        "move_id.line_ids.matched_debit_ids",
        "move_id.line_ids.matched_credit_ids",
    )
    def _compute_treasury_open_metrics(self):
        for pay in self:
            rounding = pay.currency_id.rounding or 0.01
            if pay.state == "canceled":
                pay.treasury_open_state = "cancelled"
                pay.treasury_amount_applied = 0.0
                pay.treasury_amount_available = 0.0
                pay.treasury_is_open = False
                continue

            if pay.state not in ("in_process", "paid"):
                pay.treasury_open_state = "open"
                pay.treasury_amount_applied = 0.0
                pay.treasury_amount_available = 0.0
                pay.treasury_is_open = False
                continue

            available = self._treasury_available_amount(pay)
            applied = max(pay.amount - available, 0.0)
            pay.treasury_amount_available = available
            pay.treasury_amount_applied = applied

            if available <= rounding:
                pay.treasury_open_state = "applied" if applied > rounding else "applied"
                pay.treasury_is_open = False
            elif applied <= rounding:
                pay.treasury_open_state = "open"
                pay.treasury_is_open = True
            else:
                pay.treasury_open_state = "partial"
                pay.treasury_is_open = True

    def action_treasury_apply_to_invoice(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Aplicar pago abierto",
            "res_model": "treasury.open.payment.apply.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_payment_id": self.id,
                "default_partner_id": self.partner_id.id,
                "default_partner_type": self.partner_type,
            },
        }

    def action_treasury_view_move(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Asiento contable",
            "res_model": "account.move",
            "res_id": self.move_id.id,
            "view_mode": "form",
        }

    def _treasury_outstanding_lines(self):
        """Líneas de liquidez/outstanding pendientes de conciliación bancaria."""
        self.ensure_one()
        if not self.move_id:
            return self.env["account.move.line"]
        liquidity_types = ("asset_cash", "asset_credit_card")
        lines = self.move_id.line_ids.filtered(
            lambda line: line.account_id.account_type in liquidity_types and not line.reconciled
        )
        if self.outstanding_account_id:
            outstanding = self.move_id.line_ids.filtered(
                lambda line: line.account_id == self.outstanding_account_id and not line.reconciled
            )
            if outstanding:
                return outstanding
        return lines

    def action_justech_open_bank_reconciliation(self):
        """Abre extractos del diario para conciliación bancaria (no re-concilia CxC/CxP).

        Odoo 19: en acciones dinámicas (no BD) no se puede combinar
        ``view_mode`` multi-modo con un único ``view_id``. Usar ``views``.
        """
        self.ensure_one()
        outstanding = self._treasury_outstanding_lines()
        search_view = self.env.ref(
            "account_accountant.view_bank_statement_line_search_bank_rec_widget",
            raise_if_not_found=False,
        )
        kanban_view = self.env.ref(
            "account_accountant.view_bank_statement_line_kanban_bank_rec_widget",
            raise_if_not_found=False,
        )
        list_view = self.env.ref(
            "account_accountant.view_bank_statement_line_tree_bank_rec_widget",
            raise_if_not_found=False,
        )
        views = []
        if kanban_view:
            views.append((kanban_view.id, "kanban"))
        views.append((list_view.id if list_view else False, "list"))
        action = {
            "type": "ir.actions.act_window",
            "name": "Conciliar con extracto bancario",
            "res_model": "account.bank.statement.line",
            "view_mode": "kanban,list" if kanban_view else "list",
            "views": views,
            "domain": [
                ("journal_id", "=", self.journal_id.id),
                ("is_reconciled", "=", False),
                ("state", "!=", "cancel"),
            ],
            "context": {
                "default_journal_id": self.journal_id.id,
                "search_default_journal_id": self.journal_id.id,
                "justech_payment_id": self.id,
                "justech_outstanding_line_ids": outstanding.ids,
            },
        }
        if search_view:
            action["search_view_id"] = [search_view.id]
        return action

    def action_justech_view_reconciliation_status(self):
        """Ver líneas ya conciliadas (factura y/o banco) sin intentar re-conciliar."""
        self.ensure_one()
        lines = self.env["account.move.line"]
        if self.move_id:
            lines = self.move_id.line_ids.filtered(lambda l: l.reconciled)
        return {
            "type": "ir.actions.act_window",
            "name": "Líneas conciliadas",
            "res_model": "account.move.line",
            "view_mode": "list,form",
            "domain": [("id", "in", lines.ids)],
        }

    def action_treasury_view_reconciliation(self):
        """Navega según estado real: banco pendiente vs ya aplicado a factura."""
        self.ensure_one()
        counterpart = self._treasury_counterpart_lines(self)
        counterpart_open = counterpart.filtered(lambda l: not l.reconciled and l.amount_residual)

        # Caso PBNK1: CxC ya conciliada con factura; falta solo banco.
        if self.is_reconciled and self.treasury_bank_state == "bank_pending":
            return self.action_justech_open_bank_reconciliation()

        if self.treasury_bank_state == "bank_reconciled" and self.is_reconciled:
            return self.action_justech_view_reconciliation_status()

        if counterpart_open:
            return {
                "type": "ir.actions.act_window",
                "name": "Aplicar a factura / conciliación contable",
                "res_model": "account.move.line",
                "view_mode": "list,form",
                "domain": [("id", "in", counterpart_open.ids)],
            }

        outstanding = self._treasury_outstanding_lines()
        if outstanding:
            return self.action_justech_open_bank_reconciliation()

        return self.action_justech_view_reconciliation_status()
