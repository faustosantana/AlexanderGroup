from odoo import fields, models
from odoo.tools.misc import format_amount

from .statement_math import (
    assert_receivable_invariants,
    classify_open_amount,
    days_status_label,
    residual_after_partials,
)


class ResPartner(models.Model):
    _inherit = "res.partner"

    def _dx_statement_cutoff(self):
        cutoff = self.env.context.get("dx_statement_cutoff")
        if cutoff:
            return fields.Date.to_date(cutoff)
        return fields.Date.context_today(self)

    def _dx_partial_applied_amount(self, partial, line):
        if line.currency_id:
            if (
                line == partial.debit_move_id
                and "debit_amount_currency" in partial._fields
            ):
                return abs(partial.debit_amount_currency or 0.0)
            if (
                line == partial.credit_move_id
                and "credit_amount_currency" in partial._fields
            ):
                return abs(partial.credit_amount_currency or 0.0)
            if "amount_currency" in partial._fields and partial.amount_currency:
                return abs(partial.amount_currency)
        return abs(partial.amount or 0.0)

    def _dx_line_residual_at_cutoff(self, line, cutoff):
        """Open residual considering only reconciliations dated on/before cutoff."""
        if line.currency_id:
            original = line.amount_currency or 0.0
        else:
            original = (line.debit or 0.0) - (line.credit or 0.0)
        applied = 0.0
        partials = line.matched_debit_ids | line.matched_credit_ids
        for partial in partials:
            pr_date = partial.max_date
            if not pr_date and partial.create_date:
                pr_date = partial.create_date.date()
            if pr_date and pr_date > cutoff:
                continue
            applied += self._dx_partial_applied_amount(partial, line)
        return residual_after_partials(original, applied)

    def _dx_move_ncf(self, move):
        if "justech_do_ncf" in move._fields and move.justech_do_ncf:
            return move.justech_do_ncf
        if (
            "l10n_latam_document_number" in move._fields
            and move.l10n_latam_document_number
        ):
            return move.l10n_latam_document_number
        return ""

    def _dx_statement_bundles(self, company=None):
        self.ensure_one()
        Line = self.env["account.move.line"].sudo()
        cutoff = self._dx_statement_cutoff()
        domain = [
            ("partner_id", "child_of", self.commercial_partner_id.id),
            ("parent_state", "=", "posted"),
            ("account_id.account_type", "=", "asset_receivable"),
            ("date", "<=", cutoff),
        ]
        if company:
            domain.append(("company_id", "=", company.id))
        else:
            cid = self.env.context.get("dx_statement_company_id")
            if cid:
                domain.append(("company_id", "=", cid))
        lines = Line.search(domain, order="company_id, date, move_id, id")
        bundles = []
        commercial = self.commercial_partner_id
        companies = lines.mapped("company_id")
        if company and company not in companies:
            companies = company
        for co in companies:
            docs = lines.filtered(lambda m, cid=co.id: m.company_id.id == cid)
            currency = co.currency_id
            grouped = {}
            for line in docs:
                grouped.setdefault(line.move_id, self.env["account.move.line"])
                grouped[line.move_id] |= line
            rows = []
            running = 0.0
            overdue = 0.0
            current = 0.0
            credits = 0.0
            aging = {
                "current": 0.0,
                "d30": 0.0,
                "d60": 0.0,
                "d90": 0.0,
                "d90p": 0.0,
            }
            moves = sorted(
                grouped.keys(),
                key=lambda mv: (
                    mv.date or cutoff,
                    mv.invoice_date or mv.date or cutoff,
                    mv.id,
                ),
            )
            for move in moves:
                move_lines = grouped[move]
                debit = 0.0
                credit = 0.0
                residual = 0.0
                for line in move_lines:
                    if line.currency_id and line.currency_id == currency:
                        signed = line.amount_currency or 0.0
                    else:
                        signed = (line.debit or 0.0) - (line.credit or 0.0)
                    if signed >= 0:
                        debit += signed
                    else:
                        credit += abs(signed)
                    residual += self._dx_line_residual_at_cutoff(line, cutoff)
                date = move.invoice_date or move.date
                due = move.invoice_date_due or date
                raw_name = move.name or ""
                if raw_name in ("/", "", False):
                    label = move.ref or "Documento"
                else:
                    label = raw_name
                running += debit - credit
                ov, cur, bucket, aged, cred = classify_open_amount(
                    residual, due, cutoff
                )
                overdue += ov
                current += cur
                credits += cred
                if bucket != "credit":
                    aging[bucket] += aged
                rows.append(
                    {
                        "date": date.strftime("%d/%m/%Y") if date else "—",
                        "document": label,
                        "ncf": self._dx_move_ncf(move) or "—",
                        "due": due.strftime("%d/%m/%Y") if due else "—",
                        "days": days_status_label(due, cutoff),
                        "debit": (self._dx_fmt_money(debit, currency) if debit else ""),
                        "credit": (
                            self._dx_fmt_money(credit, currency) if credit else ""
                        ),
                        "balance": self._dx_fmt_money(running, currency),
                    }
                )
            receivable = overdue + current
            net = receivable + credits
            assert_receivable_invariants(
                receivable, overdue, current, aging, net, credits
            )
            if net < -0.005:
                kpis = [
                    {
                        "label": "Saldo a favor",
                        "value": self._dx_fmt_money(abs(net), currency),
                        "tone": "credit",
                    },
                    {
                        "label": "Por cobrar",
                        "value": self._dx_fmt_money(receivable, currency),
                        "tone": "overdue" if overdue else "total",
                    },
                    {
                        "label": "Créditos / anticipos",
                        "value": self._dx_fmt_money(abs(credits), currency),
                        "tone": "current",
                    },
                ]
            else:
                kpis = [
                    {
                        "label": "Saldo total",
                        "value": self._dx_fmt_money(net, currency),
                        "tone": "total",
                    },
                    {
                        "label": "Saldo vencido",
                        "value": self._dx_fmt_money(overdue, currency),
                        "tone": "overdue",
                    },
                    {
                        "label": "Saldo no vencido",
                        "value": self._dx_fmt_money(current, currency),
                        "tone": "current",
                    },
                ]
            bundles.append(
                {
                    "company": co,
                    "anchor": moves[0] if moves else self.env["account.move"],
                    "rows": rows,
                    "cutoff": cutoff.strftime("%d/%m/%Y"),
                    "currency": currency.name,
                    "partner_name": commercial.name,
                    "partner_vat": commercial.vat or self.vat or "",
                    "overdue": self._dx_fmt_money(overdue, currency),
                    "current": self._dx_fmt_money(current, currency),
                    "credits": self._dx_fmt_money(abs(credits), currency),
                    "has_credits": abs(credits) >= 0.01,
                    "age_30": self._dx_fmt_money(aging["d30"], currency),
                    "age_60": self._dx_fmt_money(aging["d60"], currency),
                    "age_90": self._dx_fmt_money(aging["d90"], currency),
                    "age_90p": self._dx_fmt_money(aging["d90p"], currency),
                    "balance_disp": self._dx_fmt_money(
                        abs(net) if net < 0 else net, currency
                    ),
                    "balance": net,
                    "kpis": kpis,
                    "layout": co._dx_report_theme().get("layout") or "dor",
                }
            )
        return bundles

    def _dx_fmt_money(self, amount, currency):
        return format_amount(self.env, amount, currency)
