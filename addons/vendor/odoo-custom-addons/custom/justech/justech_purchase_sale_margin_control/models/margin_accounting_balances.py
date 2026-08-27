# -*- coding: utf-8 -*-
"""19.0.8.26.0 — Accounting open balances (CxC/CxP) independent of MTX.

Sales KPIs remain period-based (invoice_date). Receivable/payable KPIs are
open residual AT date_to (cut-off), including documents before date_from.
"""
from odoo import _, api, fields, models
from odoo.tools.float_utils import float_is_zero, float_round


class PurchaseSaleMarginBoardAccountingBalances(models.TransientModel):
    _inherit = "purchase.sale.margin.board"

    commercial_period_label = fields.Char(readonly=True, string="Período comercial")
    balance_as_of_label = fields.Char(readonly=True, string="Saldos al")
    cxc_breakdown_label = fields.Char(readonly=True)
    cxp_breakdown_label = fields.Char(readonly=True)
    cxc_dop_amount = fields.Monetary(currency_field="currency_id", readonly=True)
    cxc_usd_amount = fields.Float(digits=(16, 2), readonly=True)
    cxc_usd_equiv_dop = fields.Monetary(currency_field="currency_id", readonly=True)
    cxp_dop_amount = fields.Monetary(currency_field="currency_id", readonly=True)
    cxp_usd_amount = fields.Float(digits=(16, 2), readonly=True)
    cxp_usd_equiv_dop = fields.Monetary(currency_field="currency_id", readonly=True)
    cxp_other_amount = fields.Monetary(
        currency_field="currency_id",
        readonly=True,
        string="Otras partidas por pagar",
    )
    open_vendor_bills_amount = fields.Monetary(
        currency_field="currency_id",
        readonly=True,
        string="Facturas proveedor abiertas",
    )

    def _usd_currency(self):
        usd = self.env.ref("base.USD", raise_if_not_found=False)
        if usd:
            return usd
        return self.env["res.currency"].search([("name", "=", "USD")], limit=1)

    def _company_currency_map(self, companies):
        return {c.id: c.currency_id for c in companies}

    def _aml_open_rows(self, companies, account_type, date_to=None):
        """Open AML residual in company currency as of ``date_to``.

        Uses current ``amount_residual`` when cut-off is today or later.
        Reconstructs historical residual via ``account.partial.reconcile.max_date``
        (same idea as Aged Receivable / Aged Payable).
        """
        if not companies:
            return []
        date_to = fields.Date.to_date(date_to) if date_to else fields.Date.context_today(self)
        today = fields.Date.context_today(self)
        company_ids = tuple(companies.ids)
        params = {
            "company_ids": company_ids,
            "account_type": account_type,
            "date_to": date_to,
        }
        if date_to >= today:
            self.env.cr.execute(
                """
                SELECT
                    aml.id,
                    aml.company_id,
                    aml.partner_id,
                    aml.move_id,
                    am.name AS move_name,
                    am.move_type,
                    aml.date,
                    COALESCE(aml.date_maturity, am.invoice_date_due, aml.date) AS maturity,
                    aml.currency_id,
                    am.journal_id,
                    aj.type AS journal_type,
                    aj.code AS journal_code,
                    aml.payment_id,
                    aml.amount_residual AS residual_company,
                    aml.amount_residual_currency AS residual_currency
                FROM account_move_line aml
                JOIN account_move am ON am.id = aml.move_id
                JOIN account_account aa ON aa.id = aml.account_id
                JOIN account_journal aj ON aj.id = am.journal_id
                WHERE aml.company_id IN %(company_ids)s
                  AND am.state = 'posted'
                  AND aa.account_type = %(account_type)s
                  AND aml.date <= %(date_to)s
                  AND ABS(COALESCE(aml.amount_residual, 0)) > 0.005
                """,
                params,
            )
        else:
            self.env.cr.execute(
                """
                SELECT
                    aml.id,
                    aml.company_id,
                    aml.partner_id,
                    aml.move_id,
                    am.name AS move_name,
                    am.move_type,
                    aml.date,
                    COALESCE(aml.date_maturity, am.invoice_date_due, aml.date) AS maturity,
                    aml.currency_id,
                    am.journal_id,
                    aj.type AS journal_type,
                    aj.code AS journal_code,
                    aml.payment_id,
                    (
                        aml.balance
                        - COALESCE((
                            SELECT SUM(pr.amount)
                            FROM account_partial_reconcile pr
                            WHERE pr.debit_move_id = aml.id
                              AND pr.max_date <= %(date_to)s
                        ), 0)
                        + COALESCE((
                            SELECT SUM(pr.amount)
                            FROM account_partial_reconcile pr
                            WHERE pr.credit_move_id = aml.id
                              AND pr.max_date <= %(date_to)s
                        ), 0)
                    ) AS residual_company,
                    (
                        aml.amount_currency
                        - COALESCE((
                            SELECT SUM(pr.debit_amount_currency)
                            FROM account_partial_reconcile pr
                            WHERE pr.debit_move_id = aml.id
                              AND pr.max_date <= %(date_to)s
                        ), 0)
                        + COALESCE((
                            SELECT SUM(pr.credit_amount_currency)
                            FROM account_partial_reconcile pr
                            WHERE pr.credit_move_id = aml.id
                              AND pr.max_date <= %(date_to)s
                        ), 0)
                    ) AS residual_currency
                FROM account_move_line aml
                JOIN account_move am ON am.id = aml.move_id
                JOIN account_account aa ON aa.id = aml.account_id
                JOIN account_journal aj ON aj.id = am.journal_id
                WHERE aml.company_id IN %(company_ids)s
                  AND am.state = 'posted'
                  AND aa.account_type = %(account_type)s
                  AND aml.date <= %(date_to)s
                """,
                params,
            )
        rows = self.env.cr.dictfetchall()
        if date_to < today:
            rows = [
                r
                for r in rows
                if not float_is_zero(r.get("residual_company") or 0.0, precision_digits=2)
            ]
        return rows

    def _summarize_balance_rows(self, rows, companies, sign_flip=False, date_to=None):
        """Aggregate AML rows.

        ``sign_flip`` True → report liability as positive "we owe"
        (payable residual is negative in Odoo).
        """
        usd = self._usd_currency()
        usd_id = usd.id if usd else None
        company_ccy = {c.id: c.currency_id.id for c in companies}
        total = dop = usd_amt = usd_equiv = 0.0
        bill_total = other_total = 0.0
        ids = []
        bill_ids = []
        other_ids = []
        aging = {
            "not_due": 0.0,
            "1-30": 0.0,
            "31-60": 0.0,
            "61-90": 0.0,
            "91-120": 0.0,
            ">120": 0.0,
        }
        cut = date_to or fields.Date.context_today(self)

        for row in rows:
            residual = float(row.get("residual_company") or 0.0)
            amount = -residual if sign_flip else residual
            total += amount
            ids.append(row["id"])
            ccy_id = row.get("currency_id")
            company_id = row.get("company_id")
            if ccy_id and company_id and ccy_id == company_ccy.get(company_id):
                dop += amount
            elif usd_id and ccy_id == usd_id:
                usd_res = float(row.get("residual_currency") or 0.0)
                usd_amt += (-usd_res if sign_flip else usd_res)
                usd_equiv += amount
            else:
                dop += amount

            move_type = row.get("move_type")
            journal_code = (row.get("journal_code") or "").upper()
            journal_type = row.get("journal_type")
            is_bill = move_type in ("in_invoice", "in_refund")
            if sign_flip:
                if is_bill:
                    bill_total += amount
                    bill_ids.append(row["id"])
                else:
                    other_total += amount
                    other_ids.append(row["id"])

            maturity = row.get("maturity") or row.get("date")
            bucket = self._aging_bucket(cut, maturity)
            aging[bucket] += amount

        prec = 2
        return {
            "total": float_round(total, prec),
            "dop": float_round(dop, prec),
            "usd": float_round(usd_amt, prec),
            "usd_equiv": float_round(usd_equiv, prec),
            "bills": float_round(bill_total, prec),
            "other": float_round(other_total, prec),
            "ids": ids,
            "bill_ids": bill_ids,
            "other_ids": other_ids,
            "aging": {k: float_round(v, prec) for k, v in aging.items()},
        }

    @api.model
    def _aging_bucket(self, cut_date, maturity):
        if not maturity or maturity >= cut_date:
            return "not_due"
        days = (cut_date - maturity).days
        if days <= 30:
            return "1-30"
        if days <= 60:
            return "31-60"
        if days <= 90:
            return "61-90"
        if days <= 120:
            return "91-120"
        return ">120"

    def _accounting_balance_kpis(self, companies, date_to=None):
        date_to = date_to or fields.Date.context_today(self)
        recv_rows = self._aml_open_rows(companies, "asset_receivable", date_to)
        pay_rows = self._aml_open_rows(companies, "liability_payable", date_to)
        recv = self._summarize_balance_rows(recv_rows, companies, sign_flip=False, date_to=date_to)
        pay = self._summarize_balance_rows(pay_rows, companies, sign_flip=True, date_to=date_to)
        return {
            "amount_to_collect_total": recv["total"],
            "amount_to_pay_total": pay["total"],
            "net_cash_flow": float_round(recv["total"] - pay["total"], 2),
            "committed_vendor_flow": pay["bills"],
            "open_vendor_bills_amount": pay["bills"],
            "cxp_other_amount": pay["other"],
            "cxc_dop_amount": recv["dop"],
            "cxc_usd_amount": recv["usd"],
            "cxc_usd_equiv_dop": recv["usd_equiv"],
            "cxp_dop_amount": pay["dop"],
            "cxp_usd_amount": pay["usd"],
            "cxp_usd_equiv_dop": pay["usd_equiv"],
            "_cxc_aml_ids": recv["ids"],
            "_cxp_aml_ids": pay["ids"],
            "_cxp_bill_aml_ids": pay["bill_ids"],
            "_cxp_other_aml_ids": pay["other_ids"],
            "_cxc_aging": recv["aging"],
        }

    def _format_money(self, amount):
        return "{:,.2f}".format(amount or 0.0)

    def _compute_kpis(self, companies, date_from=None, date_to=None):
        vals = super()._compute_kpis(companies, date_from=date_from, date_to=date_to)
        date_to = fields.Date.to_date(date_to) if date_to else fields.Date.context_today(self)
        if date_from:
            date_from = fields.Date.to_date(date_from)
        else:
            date_from = date_to.replace(month=1, day=1)
        balances = self._accounting_balance_kpis(companies, date_to)
        # Drop internal id lists from writeable KPI dict.
        write_vals = {k: v for k, v in balances.items() if not k.startswith("_")}
        vals.update(write_vals)
        vals["commercial_period_label"] = _("Período comercial: %s – %s") % (
            fields.Date.to_string(date_from),
            fields.Date.to_string(date_to),
        )
        vals["balance_as_of_label"] = _("Saldos al %s") % fields.Date.to_string(date_to)
        vals["cxc_breakdown_label"] = _("DOP %s · USD %s (equiv. RD$ %s)") % (
            self._format_money(balances["cxc_dop_amount"]),
            self._format_money(balances["cxc_usd_amount"]),
            self._format_money(balances["cxc_usd_equiv_dop"]),
        )
        vals["cxp_breakdown_label"] = _(
            "Facturas abiertas RD$ %s · otras partidas RD$ %s"
        ) % (
            self._format_money(balances["open_vendor_bills_amount"]),
            self._format_money(balances["cxp_other_amount"]),
        )
        vals["kpi_collect_help"] = _(
            "Cuentas por cobrar al %s: residual receivable posted (AML), "
            "independiente de MTX e independiente del inicio del período de ventas."
        ) % fields.Date.to_string(date_to)
        vals["kpi_pay_help"] = _(
            "Cuentas por pagar al %s: residual payable posted (AML), "
            "incluye facturas proveedor y otras partidas (p.ej. CXP Accionistas)."
        ) % fields.Date.to_string(date_to)
        return vals

    def _open_aml_ids(self, name, aml_ids):
        self.ensure_one()
        ids = aml_ids or [0]
        return {
            "type": "ir.actions.act_window",
            "name": name,
            "res_model": "account.move.line",
            "view_mode": "list,form",
            "domain": [("id", "in", ids)],
            "context": {"create": False, "edit": False},
        }

    def _balance_snapshot(self):
        self.ensure_one()
        companies = self._get_scope_companies()
        return self._accounting_balance_kpis(companies, self.date_to)

    def action_open_amount_to_collect(self):
        snap = self._balance_snapshot()
        return self._open_aml_ids(
            _("Cuentas por cobrar al %s") % (self.date_to or ""),
            snap.get("_cxc_aml_ids"),
        )

    def action_open_amount_to_pay(self):
        snap = self._balance_snapshot()
        return self._open_aml_ids(
            _("Cuentas por pagar al %s") % (self.date_to or ""),
            snap.get("_cxp_aml_ids"),
        )

    def action_open_vendor_bills_balance(self):
        snap = self._balance_snapshot()
        return self._open_aml_ids(
            _("Facturas proveedor abiertas al %s") % (self.date_to or ""),
            snap.get("_cxp_bill_aml_ids"),
        )

    def action_open_other_payables(self):
        snap = self._balance_snapshot()
        return self._open_aml_ids(
            _("Otras partidas por pagar al %s") % (self.date_to or ""),
            snap.get("_cxp_other_aml_ids"),
        )
