# -*- coding: utf-8 -*-
"""Server-side gate: final Purchase Order PDF only when Justech-approved."""

from odoo import models


class IrActionsReport(models.Model):
    _inherit = "ir.actions.report"

    def _justech_is_final_purchase_order_report(self):
        """True only for the final OC report (Orden de compra), not RFQ/quotation."""
        self.ensure_one()
        report_name = (self.report_name or "").split(",")[0].strip()
        xmlids = self.get_external_id()
        xmlid = xmlids.get(self.id) or ""
        if xmlid in (
            "purchase.action_report_purchase_order",
            "purchase.report_purchase_order",
        ):
            return True
        low = report_name.lower()
        # RFQ / solicitud de cotización — not the final OC.
        if "quotation" in low or "rfq" in low:
            return False
        # Canonical Odoo final PO QWeb: purchase.report_purchaseorder
        if report_name == "purchase.report_purchaseorder":
            return True
        compact = low.replace("_", "").replace(".", "")
        if "purchaseorder" in compact and "quotation" not in compact:
            return True
        return False

    def _justech_docids_as_list(self, docids):
        if not docids:
            return []
        if isinstance(docids, models.Model):
            return docids.ids
        if isinstance(docids, int):
            return [docids]
        if isinstance(docids, (list, tuple)):
            return [int(i) for i in docids if i]
        return []

    def _justech_gate_purchase_final_pdf(self, report_ref, res_ids):
        if not res_ids:
            return
        report = self._get_report(report_ref)
        if not report or not report._justech_is_final_purchase_order_report():
            return
        orders = self.env["purchase.order"].browse(self._justech_docids_as_list(res_ids)).exists()
        if orders:
            orders._justech_assert_final_po_print_allowed()

    def report_action(self, docids, data=None, config=True):
        # Fail fast in UI before /report/pdf download (workers must load this inherit).
        ids = self._justech_docids_as_list(docids)
        for report in self:
            if report._justech_is_final_purchase_order_report() and ids:
                self.env["purchase.order"].browse(ids)._justech_assert_final_po_print_allowed()
        return super().report_action(docids, data=data, config=config)

    def _render_qweb_pdf_prepare_streams(self, report_ref, data, res_ids=None):
        self._justech_gate_purchase_final_pdf(report_ref, res_ids)
        return super()._render_qweb_pdf_prepare_streams(report_ref, data, res_ids=res_ids)

    def _render_qweb_pdf(self, report_ref, res_ids=None, data=None):
        self._justech_gate_purchase_final_pdf(report_ref, res_ids)
        return super()._render_qweb_pdf(report_ref, res_ids=res_ids, data=data)

    def _render_qweb_html(self, report_ref, docids=None, data=None):
        # Odoo 19 base signature uses docids (not res_ids).
        self._justech_gate_purchase_final_pdf(report_ref, docids)
        return super()._render_qweb_html(report_ref, docids, data=data)
