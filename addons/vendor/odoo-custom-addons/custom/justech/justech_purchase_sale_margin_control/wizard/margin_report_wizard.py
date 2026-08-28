# -*- coding: utf-8 -*-
"""PDF / wizard de reportes históricos multiempresa (control gerencial)."""
from odoo import _, api, fields, models


class PurchaseSaleMarginReportWizard(models.TransientModel):
    _name = "purchase.sale.margin.report.wizard"
    _description = "Reporte histórico de márgenes"

    company_ids = fields.Many2many(
        "res.company",
        string="Compañías",
        default=lambda self: self.env.companies,
        required=True,
    )
    date_from = fields.Date(required=True, default=lambda self: fields.Date.context_today(self).replace(month=1, day=1))
    date_to = fields.Date(required=True, default=fields.Date.context_today)
    report_type = fields.Selection(
        [
            ("operations", "Histórico de operaciones"),
            ("margins", "Márgenes por operación"),
            ("sales_no_cost", "Ventas sin costos"),
            ("purchases_no_sale", "Compras sin venta"),
            ("by_customer", "Margen por cliente"),
            ("by_vendor", "Margen por proveedor"),
            ("payables", "Cuentas por pagar por operación"),
        ],
        default="operations",
        required=True,
        string="Tipo de reporte",
    )
    line_ids = fields.One2many(
        "purchase.sale.margin.report.wizard.line", "wizard_id", string="Vista previa"
    )
    header_company_id = fields.Many2one(
        "res.company",
        string="Empresa del encabezado",
        help="Logo y datos legales del PDF. Vacío = grupo / primera compañía.",
    )

    def action_generate_preview(self):
        self.ensure_one()
        self.line_ids = [(5, 0, 0)]
        Transaction = self.env["purchase.sale.margin.transaction"]
        domain = [
            ("company_id", "in", self.company_ids.ids),
            ("transaction_date", ">=", self.date_from),
            ("transaction_date", "<=", self.date_to),
        ]
        if self.report_type == "sales_no_cost":
            domain.append(("sale_without_cost", "=", True))
        elif self.report_type == "purchases_no_sale":
            domain += [("has_related_cost", "=", True), ("has_related_sale", "=", False)]
        txs = Transaction.search(domain, limit=2000)
        lines = []
        for tx in txs:
            lines.append(
                (
                    0,
                    0,
                    {
                        "transaction_id": tx.id,
                        "company_id": tx.company_id.id,
                        "customer_id": tx.customer_id.id,
                        "sale_amount": tx.display_sale_amount,
                        "cost_amount": tx.display_cost_amount,
                        "margin_amount": tx.display_margin_amount,
                        "margin_pct": tx.display_margin_pct,
                        "next_action": tx.next_action,
                        "margin_band": tx.margin_band,
                    },
                )
            )
        self.line_ids = lines
        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }

    def action_print_pdf(self):
        self.ensure_one()
        if not self.line_ids:
            self.action_generate_preview()
        return self.env.ref(
            "justech_purchase_sale_margin_control.action_report_margin_historical_pdf"
        ).report_action(self)

    def _get_report_header_company(self):
        self.ensure_one()
        return self.header_company_id or self.company_ids[:1] or self.env.company


class PurchaseSaleMarginReportWizardLine(models.TransientModel):
    _name = "purchase.sale.margin.report.wizard.line"
    _description = "Línea de vista previa de reporte de márgenes"

    wizard_id = fields.Many2one("purchase.sale.margin.report.wizard", required=True, ondelete="cascade")
    transaction_id = fields.Many2one("purchase.sale.margin.transaction", string="Operación")
    company_id = fields.Many2one("res.company", string="Empresa")
    customer_id = fields.Many2one("res.partner", string="Cliente")
    sale_amount = fields.Float(string="Venta")
    cost_amount = fields.Float(string="Costo")
    margin_amount = fields.Float(string="Margen")
    margin_pct = fields.Float(string="Margen %")
    next_action = fields.Char(string="Próxima acción")
    margin_band = fields.Char(string="Clasificación")
