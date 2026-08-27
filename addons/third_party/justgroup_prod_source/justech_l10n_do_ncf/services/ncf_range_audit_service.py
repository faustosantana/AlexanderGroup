"""Auditoría de rangos NCF — métricas read-only."""
from datetime import timedelta

from odoo import _, fields, models


class JustechDoNcfRangeAuditService(models.AbstractModel):
    _name = "justech.do.ncf.range.audit.service"
    _description = "NCF Range Audit Service"

    def _alert_days(self, company):
        company = company or self.env.company
        days = company.justech_do_ncf_alert_days or 30
        return max(1, days)

    def summary_for_company(self, company=None):
        company = company or self.env.company
        Range = self.env["justech.do.ncf.range"]
        today = fields.Date.context_today(self)
        alert_limit = today + timedelta(days=self._alert_days(company))

        ranges = Range.search([("company_id", "=", company.id)])
        active = ranges.filtered(lambda r: r.state == "active")
        depleted = ranges.filtered(lambda r: r.state == "depleted")
        expired = ranges.filtered(lambda r: r.state == "expired")
        expiring = active.filtered(lambda r: r.date_to and r.date_to <= alert_limit)
        low = active.filtered(
            lambda r: r.sequence_end
            and r.next_sequence
            and (r.sequence_end - r.next_sequence + 1) <= max(10, (r.sequence_end - r.sequence_start + 1) * 0.05)
        )

        Consumption = self.env["justech.do.ncf.consumption"]
        voided = Consumption.search_count(
            [("company_id", "=", company.id), ("state", "=", "voided")]
        )
        consumed = Consumption.search_count(
            [("company_id", "=", company.id), ("state", "=", "consumed")]
        )

        return {
            "company_id": company.id,
            "total_ranges": len(ranges),
            "active_ranges": len(active),
            "depleted_ranges": len(depleted),
            "expired_ranges": len(expired),
            "expiring_ranges": len(expiring),
            "low_stock_ranges": len(low),
            "consumption_consumed": consumed,
            "consumption_voided": voided,
            "alert_days": self._alert_days(company),
        }

    def range_health_rows(self, company=None):
        """Filas detalladas por rango para el centro administrativo."""
        company = company or self.env.company
        today = fields.Date.context_today(self)
        alert_limit = today + timedelta(days=self._alert_days(company))
        rows = []
        for ncf_range in self.env["justech.do.ncf.range"].search(
            [("company_id", "=", company.id)], order="state, date_to"
        ):
            total = max(1, ncf_range.sequence_end - ncf_range.sequence_start + 1)
            used = max(0, ncf_range.next_sequence - ncf_range.sequence_start)
            pct = min(100.0, round(100.0 * used / total, 1))
            status = ncf_range.state
            if status == "active" and ncf_range.date_to and ncf_range.date_to < today:
                status = "expired_pending"
            elif status == "active" and ncf_range.date_to and ncf_range.date_to <= alert_limit:
                status = "expiring"
            elif status == "active" and ncf_range.remaining_count <= max(10, total * 0.05):
                status = "low_stock"
            rows.append(
                {
                    "range_id": ncf_range.id,
                    "name": ncf_range.name,
                    "prefix": ncf_range.prefix,
                    "state": ncf_range.state,
                    "health_status": status,
                    "remaining_count": ncf_range.remaining_count,
                    "pct_used": pct,
                    "date_to": ncf_range.date_to,
                }
            )
        return rows
