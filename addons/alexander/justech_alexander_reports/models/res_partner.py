from odoo import fields, models
from odoo.tools.misc import format_amount


class ResPartner(models.Model):
    _inherit = "res.partner"

    def _dx_statement_bundles(self, company=None):
        self.ensure_one()
        Move = self.env["account.move"].sudo()
        domain = [
            ("partner_id", "child_of", self.commercial_partner_id.id),
            ("move_type", "in", ("out_invoice", "out_refund")),
            ("state", "in", ("draft", "posted")),
        ]
        if company:
            domain.append(("company_id", "=", company.id))
        moves = Move.search(domain, order="company_id, date, id")
        bundles = []
        today = fields.Date.context_today(self)
        for co in moves.mapped("company_id"):
            docs = moves.filtered(lambda m, cid=co.id: m.company_id.id == cid)
            currency = co.currency_id
            rows = []
            running = 0.0
            overdue = 0.0
            age_30 = age_60 = age_90 = age_90p = 0.0
            for move in docs:
                date = move.invoice_date or move.date
                due = move.invoice_date_due or date
                raw_name = move.name or ""
                if raw_name in ("/", "", False):
                    label = "Borrador"
                else:
                    label = raw_name
                ncf = False
                if "l10n_latam_document_number" in move._fields:
                    ncf = move.l10n_latam_document_number
                if ncf:
                    label = "%s · %s" % (label, ncf)
                if move.move_type == "out_invoice":
                    debit = move.amount_total
                    credit = 0.0
                    running += debit
                else:
                    debit = 0.0
                    credit = move.amount_total
                    running -= credit
                residual = abs(move.amount_residual_signed or 0.0)
                if residual and due and due < today and move.move_type == "out_invoice":
                    overdue += residual
                    days = (today - due).days
                    if days <= 30:
                        age_30 += residual
                    elif days <= 60:
                        age_60 += residual
                    elif days <= 90:
                        age_90 += residual
                    else:
                        age_90p += residual
                state_label = {
                    "draft": "Borrador",
                    "posted": "Publicado",
                    "cancel": "Anulado",
                }.get(move.state, move.state)
                rows.append(
                    {
                        "date": date.strftime("%d/%m/%Y") if date else "—",
                        "document": label,
                        "due": due.strftime("%d/%m/%Y") if due else "—",
                        "state": state_label,
                        "debit": (self._dx_fmt_money(debit, currency) if debit else ""),
                        "credit": (
                            self._dx_fmt_money(credit, currency) if credit else ""
                        ),
                        "balance": self._dx_fmt_money(running, currency),
                    }
                )
            bundles.append(
                {
                    "company": co,
                    "anchor": docs[:1],
                    "rows": rows,
                    "cutoff": today.strftime("%Y-%m-%d"),
                    "overdue": self._dx_fmt_money(overdue, currency),
                    "age_30": self._dx_fmt_money(age_30, currency),
                    "age_60": self._dx_fmt_money(age_60, currency),
                    "age_90": self._dx_fmt_money(age_90, currency),
                    "age_90p": self._dx_fmt_money(age_90p, currency),
                    "balance_disp": self._dx_fmt_money(running, currency),
                    "balance": running,
                }
            )
        return bundles

    def _dx_fmt_money(self, amount, currency):
        return format_amount(self.env, amount, currency)
