# -*- coding: utf-8 -*-
"""Diagnóstico de trazabilidad histórica (sin backfill automático)."""
from odoo import _, api, fields, models


class JustechTraceDiagnosticWizard(models.TransientModel):
    _name = "justech.trace.diagnostic.wizard"
    _description = "Diagnóstico trazabilidad venta-compra"

    sale_order_id = fields.Many2one("sale.order", string="Orden de venta")
    line_ids = fields.One2many(
        "justech.trace.diagnostic.wizard.line",
        "wizard_id",
        string="Hallazgos",
    )

    def action_run(self):
        self.ensure_one()
        so = self.sale_order_id
        if not so:
            return
        rows = []
        # Direct sale_line_id
        for sol in so.order_line.filtered(lambda l: not l.display_type):
            for pol in sol.purchase_line_ids:
                rows.append(
                    (
                        0,
                        0,
                        {
                            "sale_line_id": sol.id,
                            "purchase_line_id": pol.id,
                            "purchase_order_id": pol.order_id.id,
                            "relation_type": "direct",
                            "confidence": "high",
                            "note": _("Relación directa línea de venta"),
                        },
                    )
                )
            for asg in sol.justech_qty_assignment_ids.filtered(lambda a: a.state == "active"):
                rows.append(
                    (
                        0,
                        0,
                        {
                            "sale_line_id": sol.id,
                            "purchase_line_id": asg.purchase_line_id.id,
                            "purchase_order_id": asg.purchase_order_id.id,
                            "relation_type": "manual",
                            "confidence": "high",
                            "note": _("Asignación qty %s") % asg.quantity,
                        },
                    )
                )
        # Origin-only POs
        origin_pos = self.env["purchase.order"].search(
            [
                ("origin", "=", so.name),
                ("company_id", "=", so.company_id.id),
            ]
        )
        linked_po_ids = {r[2]["purchase_order_id"] for r in rows if r[2].get("purchase_order_id")}
        for po in origin_pos:
            if po.id in linked_po_ids:
                continue
            has_any_sale_line = any(po.order_line.mapped("sale_line_id"))
            rows.append(
                (
                    0,
                    0,
                    {
                        "purchase_order_id": po.id,
                        "relation_type": "origin",
                        "confidence": "medium" if not has_any_sale_line else "probable",
                        "note": _("Solo origin=%s") % so.name,
                    },
                )
            )
        self.line_ids = [(5, 0, 0)] + rows
        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }


class JustechTraceDiagnosticWizardLine(models.TransientModel):
    _name = "justech.trace.diagnostic.wizard.line"
    _description = "Línea diagnóstico trazabilidad"

    wizard_id = fields.Many2one(
        "justech.trace.diagnostic.wizard", required=True, ondelete="cascade"
    )
    sale_line_id = fields.Many2one("sale.order.line", string="Línea venta")
    purchase_line_id = fields.Many2one("purchase.order.line", string="Línea OC")
    purchase_order_id = fields.Many2one("purchase.order", string="OC")
    relation_type = fields.Selection(
        [
            ("direct", "Relación directa"),
            ("origin", "Origin"),
            ("probable", "Probable"),
            ("manual", "Manual"),
        ],
        string="Tipo",
    )
    confidence = fields.Selection(
        [
            ("high", "Alta"),
            ("medium", "Media"),
            ("probable", "Probable"),
            ("low", "Baja"),
        ],
        string="Confianza",
    )
    note = fields.Char(string="Nota")
