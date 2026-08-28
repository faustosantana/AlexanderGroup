# -*- coding: utf-8 -*-
"""19.0.6.0.0 — Automatización de vínculos SO→OC→factura (sin asientos nuevos).

Solo crea/actualiza operaciones de control gerencial. Contabilidad estándar
permanece como fuente de verdad para importes, impuestos y pagos.
"""
import logging

from odoo import _, api, fields, models

from . import margin_acl

_logger = logging.getLogger(__name__)

LINK_MODES = [
    ("automatic", "Automática"),
    ("historical", "Histórica/manual"),
    ("suggested", "Sugerida"),
    ("corrected", "Corregida"),
]


class PurchaseSaleMarginTransactionAuto(models.Model):
    _inherit = "purchase.sale.margin.transaction"

    link_mode = fields.Selection(
        LINK_MODES,
        string="Origen de relación",
        default="historical",
        index=True,
        help="Automática = creada por trazabilidad Odoo. Histórica/manual = carga o relación manual.",
    )
    vendor_cost_summary = fields.Html(
        string="Costos por proveedor",
        compute="_compute_vendor_cost_summary",
        groups="justech_purchase_sale_margin_control.group_margin_sec_margins_view",
    )

    @api.depends(
        "line_ids.partner_id",
        "line_ids.line_type",
        "line_ids.amount_company_currency",
        "line_ids.product_id",
        "line_ids.quantity",
        "line_ids.data_origin",
        "line_ids.state",
        "line_ids.exclude_from_margin",
        "purchase_order_ids",
        "vendor_bill_ids",
        "supplier_ids",
    )
    def _compute_vendor_cost_summary(self):
        for rec in self:
            cost_lines = rec.line_ids.filtered(
                lambda l: l.line_type == "cost" and l.state != "excluded" and not l.exclude_from_margin
            )
            by_partner = {}
            for line in cost_lines:
                partner = line.partner_id or line.purchase_order_id.partner_id
                key = partner.id if partner else 0
                bucket = by_partner.setdefault(
                    key,
                    {
                        "name": partner.display_name if partner else _("Sin proveedor"),
                        "committed": 0.0,
                        "real": 0.0,
                        "lines": [],
                    },
                )
                amt = line.amount_company_currency or line.amount_untaxed or 0.0
                if line.data_origin == "estimated":
                    bucket["committed"] += amt
                else:
                    bucket["real"] += amt
                bucket["lines"].append(
                    "%s × %s — %s"
                    % (
                        line.quantity or 0,
                        line.product_id.display_name or line.description or "",
                        "{:,.2f}".format(amt),
                    )
                )
            html = []
            for data in by_partner.values():
                html.append("<div class='mb-2'><strong>%s</strong>" % data["name"])
                html.append(
                    "<div class='text-muted'>Comprometido: %s · Real: %s</div>"
                    % ("{:,.2f}".format(data["committed"]), "{:,.2f}".format(data["real"]))
                )
                html.append("<ul>%s</ul></div>" % "".join("<li>%s</li>" % x for x in data["lines"][:12]))
            rec.vendor_cost_summary = "".join(html) if html else False


class PurchaseOrderAutoLink(models.Model):
    _inherit = "purchase.order"

    def button_confirm(self):
        res = super().button_confirm()
        self._justech_auto_link_margin_from_sale()
        return res

    def _justech_auto_link_margin_from_sale(self):
        """Idempotent: if PO comes from a SO, ensure margin transaction exists."""
        # Technical MTX write — sudo on Transaction only; PO confirm stays as user.
        Transaction = margin_acl.margin_transaction(self.env)
        for po in self:
            if po.state not in ("purchase", "done"):
                continue
            sale_orders = self.env["sale.order"]
            if hasattr(po, "_get_sale_orders"):
                sale_orders = po._get_sale_orders()
            if not sale_orders and po.origin:
                sale_orders = self.env["sale.order"].search(
                    [("name", "=", po.origin), ("company_id", "=", po.company_id.id)], limit=1
                )
            if not sale_orders:
                continue
            so = sale_orders[:1]
            tx = Transaction.find_or_create_canonical_transaction(
                sale_order=so,
                vals={
                    "company_id": po.company_id.id,
                    "name": so.name,
                    "customer_id": so.partner_id.id,
                    "sale_order_ids": [(4, so.id)],
                    "purchase_order_ids": [(4, po.id)],
                    "supplier_ids": [(4, po.partner_id.id)] if po.partner_id else False,
                    "transaction_type": "resale",
                    "source": "auto_detected",
                    "link_mode": "automatic",
                    "state": "draft",
                },
            )
            if tx.state in ("approved", "closed") and po.id in tx.purchase_order_ids.ids:
                continue
            if tx.link_mode == "historical":
                tx.link_mode = "automatic"
            _logger.info("Margin auto-link canonical %s for SO %s / PO %s", tx.transaction_number, so.name, po.name)


class AccountMoveAutoLink(models.Model):
    _inherit = "account.move"

    def action_post(self):
        res = super().action_post()
        self._justech_auto_link_margin_documents()
        return res

    def _justech_auto_link_margin_documents(self):
        """Link posted invoices to existing margin operations. Never creates journal entries."""
        # Technical MTX write — sudo on Transaction only; never elevate account.move.
        Transaction = margin_acl.margin_transaction(self.env)
        for move in self.filtered(lambda m: m.state == "posted"):
            if move.move_type in ("in_invoice", "in_refund"):
                pos = move.invoice_line_ids.mapped("purchase_line_id.order_id")
                domain = [("company_id", "=", move.company_id.id)]
                if pos:
                    domain = domain + [
                        "|",
                        ("purchase_order_ids", "in", pos.ids),
                        ("vendor_bill_ids", "in", move.id),
                    ]
                else:
                    domain.append(("vendor_bill_ids", "in", move.id))
                domain = domain + Transaction._operational_domain()
                txs = Transaction.search(domain)
                for tx in txs:
                    if tx.state in ("approved", "closed") and move.id in tx.vendor_bill_ids.ids:
                        continue
                    writes = {"vendor_bill_ids": [(4, move.id)]}
                    if move.partner_id:
                        writes["supplier_ids"] = [(4, move.partner_id.id)]
                    if pos:
                        writes["purchase_order_ids"] = [(4, p.id) for p in pos if p.id not in tx.purchase_order_ids.ids]
                        if not writes["purchase_order_ids"]:
                            writes.pop("purchase_order_ids", None)
                    tx.write(writes)
            elif move.move_type in ("out_invoice", "out_refund"):
                sos = move.invoice_line_ids.mapped("sale_line_ids.order_id")
                if not sos:
                    continue
                for so in sos:
                    Transaction.find_or_create_canonical_transaction(
                        sale_order=so,
                        customer_invoice=move,
                        vals={
                            "company_id": move.company_id.id,
                            "customer_invoice_ids": [(4, move.id)],
                            "sale_order_ids": [(4, so.id)],
                            "source": "invoice",
                        },
                    )
        return True
