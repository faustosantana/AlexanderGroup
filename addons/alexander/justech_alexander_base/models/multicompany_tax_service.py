import csv
import io
import logging

from odoo import api, models

from .catalog import operational_companies

_logger = logging.getLogger(__name__)

OPERATING_STATES = {
    "sale.order": ("draft", "sent", "sale"),
    "purchase.order": ("draft", "sent", "to approve", "purchase"),
}


class MulticompanyTaxService(models.AbstractModel):
    _name = "justech.alexander.multicompany.tax.service"
    _description = "Diagnóstico de impuestos multiempresa Doralex"

    def _dx_operational_company_ids(self):
        return set(operational_companies(self.env).ids)

    def _dx_cross_tax_rows(self, model, line_model, tax_field, company_from):
        rows = []
        if line_model not in self.env:
            return rows
        Line = self.env[line_model].sudo()
        domain = []
        if model == "sale.order":
            domain = [("order_id.state", "in", OPERATING_STATES["sale.order"])]
        elif model == "purchase.order":
            domain = [("order_id.state", "in", OPERATING_STATES["purchase.order"])]
        elif model == "account.move":
            domain = [
                ("move_id.state", "=", "draft"),
                (
                    "move_id.move_type",
                    "in",
                    ("out_invoice", "out_refund", "in_invoice", "in_refund"),
                ),
            ]
        lines = Line.search(domain)
        for line in lines:
            if line.display_type:
                continue
            parent = line[company_from]
            company = parent.company_id if company_from != "company_id" else parent
            if company_from == "order_id":
                company = line.order_id.company_id
            elif company_from == "move_id":
                company = line.move_id.company_id
            else:
                company = line.company_id
            taxes = (
                line[tax_field]
                if tax_field in line._fields
                else line.env["account.tax"]
            )
            for tax in taxes:
                if tax.company_id and tax.company_id != company:
                    rows.append(
                        {
                            "MODEL": line_model,
                            "RECORD_ID": line.id,
                            "DOCUMENT": (
                                parent.name
                                if company_from != "company_id"
                                else line.display_name
                            ),
                            "DOCUMENT_COMPANY": company.name,
                            "PRODUCT_ID": (
                                line.product_id.id
                                if "product_id" in line._fields
                                else ""
                            ),
                            "PRODUCT": (
                                line.product_id.display_name
                                if "product_id" in line._fields
                                else ""
                            ),
                            "CURRENT_TAX_ID": tax.id,
                            "CURRENT_TAX": tax.name,
                            "CURRENT_TAX_COMPANY": tax.company_id.name,
                            "EXPECTED_TAX_ID": "",
                            "EXPECTED_TAX": "",
                            "EXPECTED_TAX_COMPANY": company.name,
                            "ACTION": (
                                "NO_CHANGE"
                                if model == "account.move"
                                and line.move_id.state == "posted"
                                else "FIX_DRAFT_%s_TAX"
                                % (
                                    "SALE_LINE"
                                    if model == "sale.order"
                                    else (
                                        "PURCHASE_LINE"
                                        if model == "purchase.order"
                                        else "INVOICE"
                                    )
                                )
                            ),
                            "REASON": "CROSS_COMPANY_TAX",
                            "CONFIDENCE": "HIGH",
                        }
                    )
        return rows

    def _dx_product_cleanup_rows(self):
        rows = []
        operational = operational_companies(self.env)
        templates = self.env["product.template"].sudo().search([("active", "=", True)])
        for tmpl in templates:
            for field_name in ("taxes_id", "supplier_taxes_id"):
                taxes = tmpl[field_name]
                for tax in taxes:
                    if tax.company_id and tax.company_id not in operational:
                        rows.append(
                            {
                                "MODEL": "product.template",
                                "RECORD_ID": tmpl.id,
                                "DOCUMENT": tmpl.display_name,
                                "DOCUMENT_COMPANY": tmpl.company_id.name or "SHARED",
                                "PRODUCT_ID": tmpl.id,
                                "PRODUCT": tmpl.display_name,
                                "CURRENT_TAX_ID": tax.id,
                                "CURRENT_TAX": tax.name,
                                "CURRENT_TAX_COMPANY": tax.company_id.name,
                                "EXPECTED_TAX_ID": "",
                                "EXPECTED_TAX": "",
                                "EXPECTED_TAX_COMPANY": tmpl.company_id.name
                                or "OPERATIONAL",
                                "ACTION": "FIX_PRODUCT_COMPANY_TAX_CONTEXT",
                                "REASON": "NON_OPERATIONAL_TAX",
                                "CONFIDENCE": "HIGH",
                            }
                        )
                    elif (
                        tmpl.company_id
                        and tax.company_id
                        and tax.company_id != tmpl.company_id
                    ):
                        rows.append(
                            {
                                "MODEL": "product.template",
                                "RECORD_ID": tmpl.id,
                                "DOCUMENT": tmpl.display_name,
                                "DOCUMENT_COMPANY": tmpl.company_id.name,
                                "PRODUCT_ID": tmpl.id,
                                "PRODUCT": tmpl.display_name,
                                "CURRENT_TAX_ID": tax.id,
                                "CURRENT_TAX": tax.name,
                                "CURRENT_TAX_COMPANY": tax.company_id.name,
                                "EXPECTED_TAX_ID": "",
                                "EXPECTED_TAX": tmpl.company_id.name,
                                "EXPECTED_TAX_COMPANY": tmpl.company_id.name,
                                "ACTION": "FIX_PRODUCT_COMPANY_TAX_CONTEXT",
                                "REASON": "COMPANY_SPECIFIC_PRODUCT_FOREIGN_TAX",
                                "CONFIDENCE": "HIGH",
                            }
                        )
        return rows

    def _dx_fiscal_position_rows(self):
        rows = []
        if "account.fiscal.position" not in self.env:
            return rows
        positions = self.env["account.fiscal.position"].sudo().search([])
        for position in positions:
            if not position.company_id:
                continue
            for tax in position.tax_ids:
                if tax.company_id and tax.company_id != position.company_id:
                    rows.append(
                        {
                            "MODEL": "account.fiscal.position",
                            "RECORD_ID": position.id,
                            "DOCUMENT": position.name,
                            "DOCUMENT_COMPANY": position.company_id.name,
                            "PRODUCT_ID": "",
                            "PRODUCT": "",
                            "CURRENT_TAX_ID": tax.id,
                            "CURRENT_TAX": tax.name,
                            "CURRENT_TAX_COMPANY": tax.company_id.name,
                            "EXPECTED_TAX_ID": "",
                            "EXPECTED_TAX": "",
                            "EXPECTED_TAX_COMPANY": position.company_id.name,
                            "ACTION": "FIX_FISCAL_POSITION_MAPPING",
                            "REASON": "FP_CROSS_COMPANY_TAX",
                            "CONFIDENCE": "HIGH",
                        }
                    )
        return rows

    def _dx_posted_cross_rows(self):
        rows = []
        if "account.move.line" not in self.env:
            return rows
        lines = (
            self.env["account.move.line"]
            .sudo()
            .search(
                [
                    ("move_id.state", "=", "posted"),
                    (
                        "move_id.move_type",
                        "in",
                        ("out_invoice", "out_refund", "in_invoice", "in_refund"),
                    ),
                ]
            )
        )
        for line in lines:
            company = line.move_id.company_id
            for tax in line.tax_ids:
                if tax.company_id and tax.company_id != company:
                    rows.append(
                        {
                            "MODEL": "account.move.line",
                            "RECORD_ID": line.id,
                            "DOCUMENT": line.move_id.name,
                            "DOCUMENT_COMPANY": company.name,
                            "PRODUCT_ID": line.product_id.id,
                            "PRODUCT": line.product_id.display_name,
                            "CURRENT_TAX_ID": tax.id,
                            "CURRENT_TAX": tax.name,
                            "CURRENT_TAX_COMPANY": tax.company_id.name,
                            "EXPECTED_TAX_ID": "",
                            "EXPECTED_TAX": "",
                            "EXPECTED_TAX_COMPANY": company.name,
                            "ACTION": "NO_CHANGE",
                            "REASON": "POSTED_CROSS_COMPANY_TAX",
                            "CONFIDENCE": "HIGH",
                        }
                    )
        return rows

    @api.model
    def check_multicompany_tax_integrity(self):
        """Idempotent diagnostic. Does not write."""
        product_rows = self._dx_product_cleanup_rows()
        sale_rows = self._dx_cross_tax_rows(
            "sale.order", "sale.order.line", "tax_ids", "order_id"
        )
        purchase_rows = self._dx_cross_tax_rows(
            "purchase.order", "purchase.order.line", "tax_ids", "order_id"
        )
        draft_rows = self._dx_cross_tax_rows(
            "account.move", "account.move.line", "tax_ids", "move_id"
        )
        fp_rows = self._dx_fiscal_position_rows()
        posted_rows = self._dx_posted_cross_rows()
        report = {
            "shared_products_with_bad_taxes": [
                row
                for row in product_rows
                if row["REASON"]
                in (
                    "NON_OPERATIONAL_TAX",
                    "COMPANY_SPECIFIC_PRODUCT_FOREIGN_TAX",
                )
            ],
            "sale_lines_with_bad_taxes": sale_rows,
            "purchase_lines_with_bad_taxes": purchase_rows,
            "draft_invoices_with_bad_taxes": draft_rows,
            "fiscal_position_bad_mappings": fp_rows,
            "posted_cross_company_tax_moves": posted_rows,
        }
        report["counts"] = {key: len(value) for key, value in report.items()}
        return report

    @api.model
    def dry_run_csv(self):
        rows = []
        rows.extend(self._dx_product_cleanup_rows())
        rows.extend(
            self._dx_cross_tax_rows(
                "sale.order", "sale.order.line", "tax_ids", "order_id"
            )
        )
        rows.extend(
            self._dx_cross_tax_rows(
                "purchase.order", "purchase.order.line", "tax_ids", "order_id"
            )
        )
        rows.extend(
            self._dx_cross_tax_rows(
                "account.move", "account.move.line", "tax_ids", "move_id"
            )
        )
        rows.extend(self._dx_fiscal_position_rows())
        rows.extend(self._dx_posted_cross_rows())
        if not rows:
            rows.append(
                {
                    "MODEL": "",
                    "RECORD_ID": "",
                    "DOCUMENT": "",
                    "DOCUMENT_COMPANY": "",
                    "PRODUCT_ID": "",
                    "PRODUCT": "",
                    "CURRENT_TAX_ID": "",
                    "CURRENT_TAX": "",
                    "CURRENT_TAX_COMPANY": "",
                    "EXPECTED_TAX_ID": "",
                    "EXPECTED_TAX": "",
                    "EXPECTED_TAX_COMPANY": "",
                    "ACTION": "NO_CHANGE",
                    "REASON": "CLEAN",
                    "CONFIDENCE": "HIGH",
                }
            )
        buffer = io.StringIO()
        writer = csv.DictWriter(
            buffer,
            fieldnames=[
                "MODEL",
                "RECORD_ID",
                "DOCUMENT",
                "DOCUMENT_COMPANY",
                "PRODUCT_ID",
                "PRODUCT",
                "CURRENT_TAX_ID",
                "CURRENT_TAX",
                "CURRENT_TAX_COMPANY",
                "EXPECTED_TAX_ID",
                "EXPECTED_TAX",
                "EXPECTED_TAX_COMPANY",
                "ACTION",
                "REASON",
                "CONFIDENCE",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)
        return buffer.getvalue()

    @api.model
    def _dx_apply_safe_product_tax_cleanup(self):
        """Remove template-company taxes and foreign taxes on company-only products."""
        Product = self.env["product.template"].sudo()
        if not hasattr(Product, "_dx_unlink_non_operational_product_taxes"):
            return False
        dirty_ids = self._dx_dirty_product_ids()
        if dirty_ids:
            Product.browse(dirty_ids)._dx_unlink_non_operational_product_taxes()
            _logger.info(
                "justech_alexander_base: cleaned taxes on %s product templates",
                len(dirty_ids),
            )
        return True

    def _dx_dirty_product_ids(self):
        cr = self.env.cr
        operational = tuple(self._dx_operational_company_ids()) or (0,)
        cr.execute(
            """
            SELECT DISTINCT pt.id
            FROM product_template pt
            JOIN product_taxes_rel rel ON rel.prod_id = pt.id
            JOIN account_tax tax ON tax.id = rel.tax_id
            WHERE (tax.company_id IS NOT NULL AND tax.company_id NOT IN %s)
               OR (pt.company_id IS NOT NULL AND tax.company_id IS NOT NULL
                   AND tax.company_id <> pt.company_id)
            UNION
            SELECT DISTINCT pt.id
            FROM product_template pt
            JOIN product_supplier_taxes_rel rel ON rel.prod_id = pt.id
            JOIN account_tax tax ON tax.id = rel.tax_id
            WHERE (tax.company_id IS NOT NULL AND tax.company_id NOT IN %s)
               OR (pt.company_id IS NOT NULL AND tax.company_id IS NOT NULL
                   AND tax.company_id <> pt.company_id)
            """,
            (operational, operational),
        )
        return [row[0] for row in cr.fetchall()]

    @api.model
    def fix_draft_cross_company_taxes(self):
        """Recompute taxes on draft documents only. Never posted moves."""
        fixed = {"sale.order.line": 0, "purchase.order.line": 0, "account.move.line": 0}
        sale_rows = self._dx_cross_tax_rows(
            "sale.order", "sale.order.line", "tax_ids", "order_id"
        )
        sale_ids = {
            row["RECORD_ID"]
            for row in sale_rows
            if row["ACTION"] == "FIX_DRAFT_SALE_LINE_TAX"
        }
        if sale_ids:
            lines = self.env["sale.order.line"].browse(list(sale_ids))
            drafts = lines.filtered(
                lambda line: line.order_id.state in ("draft", "sent")
            )
            drafts._compute_tax_ids()
            fixed["sale.order.line"] = len(drafts)
        purchase_rows = self._dx_cross_tax_rows(
            "purchase.order", "purchase.order.line", "tax_ids", "order_id"
        )
        purchase_ids = {
            row["RECORD_ID"]
            for row in purchase_rows
            if row["ACTION"] == "FIX_DRAFT_PURCHASE_LINE_TAX"
        }
        if purchase_ids:
            lines = self.env["purchase.order.line"].browse(list(purchase_ids))
            drafts = lines.filtered(
                lambda line: line.order_id.state in ("draft", "sent", "to approve")
            )
            if hasattr(drafts, "_compute_tax_id"):
                drafts._compute_tax_id()
            fixed["purchase.order.line"] = len(drafts)
        draft_rows = self._dx_cross_tax_rows(
            "account.move", "account.move.line", "tax_ids", "move_id"
        )
        move_ids = {
            row["RECORD_ID"]
            for row in draft_rows
            if row["ACTION"] == "FIX_DRAFT_INVOICE_TAX"
        }
        if move_ids:
            lines = self.env["account.move.line"].browse(list(move_ids))
            drafts = lines.filtered(lambda line: line.move_id.state == "draft")
            if hasattr(drafts, "_compute_tax_ids"):
                drafts._compute_tax_ids()
            for move in drafts.mapped("move_id"):
                if hasattr(move, "_compute_amount"):
                    move._compute_amount()
            fixed["account.move.line"] = len(drafts)
        return fixed
