# -*- coding: utf-8 -*-
"""Wizard simple PO → Vincular a venta (29.32 hotfix ACL + UX)."""
from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools.float_utils import float_compare

from ..models.margin_acl import (
    assert_po_link_authorized,
    execute_po_to_sale_link,
    user_can_read_customer_invoices,
)
from ..services.line_allocation_service import LineAllocationService, _is_product_line

LINK_STATUS = [
    ("linked", "Vinculada"),
    ("partial", "Parcial"),
    ("unlinked", "Sin vincular"),
]


class PurchaseSaleLinkSaleWizard(models.TransientModel):
    _name = "purchase.sale.link.sale.wizard"
    _description = "Vincular orden de compra a venta"

    state = fields.Selection(
        [("client", "Cliente"), ("match", "Artículos")],
        default="client",
        required=True,
    )
    company_id = fields.Many2one(
        "res.company",
        default=lambda self: self.env.company,
        required=True,
    )
    purchase_order_id = fields.Many2one(
        "purchase.order", string="Orden de compra", required=True
    )
    supplier_label = fields.Char(
        string="Proveedor", compute="_compute_supplier_label", readonly=True
    )
    customer_id = fields.Many2one("res.partner", string="Cliente")
    customer_commercial_id_int = fields.Integer(
        compute="_compute_customer_commercial_id_int"
    )
    sale_order_id = fields.Many2one("sale.order", string="Cotización / Orden de venta")
    sale_order_label = fields.Char(
        related="sale_order_id.name", string="Venta", readonly=True
    )
    customer_invoice_id = fields.Many2one(
        "account.move", string="Factura de cliente (opcional)"
    )
    show_customer_invoice = fields.Boolean(
        compute="_compute_show_customer_invoice", readonly=True
    )
    sale_order_domain = fields.Char(compute="_compute_domains")
    customer_invoice_domain = fields.Char(compute="_compute_domains")
    sale_hint = fields.Char(readonly=True)
    line_ids = fields.One2many(
        "purchase.sale.link.sale.wizard.line", "wizard_id", string="Artículos"
    )
    can_confirm = fields.Boolean(compute="_compute_can_confirm")

    @api.depends("purchase_order_id")
    def _compute_supplier_label(self):
        for wiz in self:
            po = wiz.purchase_order_id
            wiz.supplier_label = po.partner_id.display_name if po and po.partner_id else "—"

    @api.depends("customer_id")
    def _compute_customer_commercial_id_int(self):
        svc = LineAllocationService(self.env)
        for wiz in self:
            wiz.customer_commercial_id_int = (
                svc.commercial_id(wiz.customer_id) if wiz.customer_id else 0
            )

    def _compute_show_customer_invoice(self):
        can = user_can_read_customer_invoices(self.env)
        for wiz in self:
            wiz.show_customer_invoice = can

    @api.depends("company_id", "customer_id")
    def _compute_domains(self):
        for wiz in self:
            wiz.sale_order_domain = repr(wiz._sale_domain_list())
            wiz.customer_invoice_domain = repr(wiz._invoice_domain_list())
            if wiz.customer_id:
                wiz.sale_hint = _("Mostrando únicamente documentos de %s") % (
                    wiz.customer_id.display_name
                )
            else:
                wiz.sale_hint = _("Seleccione un cliente para filtrar ventas.")

    @api.depends("line_ids.qty_to_assign", "line_ids.sale_line_id", "sale_order_id")
    def _compute_can_confirm(self):
        for wiz in self:
            wiz.can_confirm = bool(
                wiz.sale_order_id
                and any(
                    l.sale_line_id
                    and float_compare(l.qty_to_assign or 0.0, 0.0, precision_digits=4) > 0
                    for l in wiz.line_ids
                )
            )

    def _sale_domain_list(self):
        self.ensure_one()
        if not self.company_id or not self.customer_id:
            return [("id", "=", False)]
        cid = LineAllocationService(self.env).commercial_id(self.customer_id)
        return [
            ("company_id", "=", self.company_id.id),
            ("partner_id", "child_of", cid),
            ("state", "!=", "cancel"),
        ]

    def _invoice_domain_list(self):
        self.ensure_one()
        if not self.company_id or not self.customer_id:
            return [("id", "=", False)]
        cid = LineAllocationService(self.env).commercial_id(self.customer_id)
        return [
            ("company_id", "=", self.company_id.id),
            ("move_type", "in", ("out_invoice", "out_refund")),
            ("state", "=", "posted"),
            ("partner_id", "child_of", cid),
        ]

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        po_id = self.env.context.get("default_purchase_order_id") or self.env.context.get(
            "active_id"
        )
        if self.env.context.get("active_model") == "purchase.order" and self.env.context.get(
            "active_id"
        ):
            po_id = self.env.context["active_id"]
        po = self.env["purchase.order"].browse(po_id) if po_id else self.env["purchase.order"]
        if po:
            res["purchase_order_id"] = po.id
            res["company_id"] = po.company_id.id
            customer = po._justech_guess_link_customer()
            if customer:
                res["customer_id"] = customer.id
            sale = po._justech_guess_link_sale_order()
            if sale:
                res["sale_order_id"] = sale.id
                if not customer:
                    res["customer_id"] = sale.partner_id.commercial_partner_id.id
        return res

    @api.onchange("customer_id", "company_id")
    def _onchange_customer_id(self):
        svc = LineAllocationService(self.env)
        if self.customer_id:
            cid = svc.commercial_id(self.customer_id)
            if self.sale_order_id and svc.commercial_id(self.sale_order_id.partner_id) != cid:
                self.sale_order_id = False
            if self.customer_invoice_id and svc.commercial_id(
                self.customer_invoice_id.partner_id
            ) != cid:
                self.customer_invoice_id = False
        else:
            self.sale_order_id = False
            self.customer_invoice_id = False

    @api.onchange("sale_order_id")
    def _onchange_sale_order_id(self):
        if self.sale_order_id and not self.customer_id:
            self.customer_id = self.sale_order_id.partner_id.commercial_partner_id
        if self.sale_order_id and user_can_read_customer_invoices(self.env):
            invs = LineAllocationService(self.env).customer_invoices_for_sale_orders(
                self.sale_order_id, company=self.company_id
            )
            self.customer_invoice_id = invs[:1] if len(invs) == 1 else False

    def _validate_client_step(self):
        self.ensure_one()
        if not self.customer_id:
            raise UserError(_("Seleccione un cliente."))
        if not self.sale_order_id:
            raise UserError(_("Seleccione una cotización u orden de venta."))
        inv = (
            self.customer_invoice_id
            if self.show_customer_invoice and self.customer_invoice_id
            else self.env["account.move"]
        )
        assert_po_link_authorized(
            self.env,
            self.purchase_order_id,
            self.sale_order_id,
            self.customer_id,
            customer_invoice=inv,
        )

    def _eligible_sale_lines(self, sale_order):
        if not sale_order:
            return self.env["sale.order.line"]
        # Hub operators may lack Sales ACL; lines are validated via assert_po_link.
        return sale_order.sudo().order_line.filtered(_is_product_line)

    def _suggest_sale_line(self, pol, sols, invoices):
        svc = LineAllocationService(self.env)
        if not pol or not sols:
            return self.env["sale.order.line"], 0.0

        if pol.sale_line_id and pol.sale_line_id in sols:
            sol = pol.sale_line_id
            qty = min(
                svc.pol_qty_available(pol),
                svc.sol_qty_available_for_margin(sol, invoice_moves=invoices or None),
            )
            return sol, qty

        by_product = sols.filtered(lambda s, p=pol: s.product_id == p.product_id)
        if len(by_product) == 1:
            sol = by_product
            qty = min(
                svc.pol_qty_available(pol),
                svc.sol_qty_available_for_margin(sol, invoice_moves=invoices or None),
            )
            return sol, qty

        tmpl_id = pol.product_id.product_tmpl_id.id if pol.product_id else False
        if tmpl_id:
            by_tmpl = sols.filtered(
                lambda s, tid=tmpl_id: s.product_id.product_tmpl_id.id == tid
            )
            if len(by_tmpl) == 1:
                sol = by_tmpl
                qty = min(
                    svc.pol_qty_available(pol),
                    svc.sol_qty_available_for_margin(sol, invoice_moves=invoices or None),
                )
                return sol, qty

        if len(sols) == 1:
            sol = sols
            qty = min(
                svc.pol_qty_available(pol),
                svc.sol_qty_available_for_margin(sol, invoice_moves=invoices or None),
            )
            return sol, qty

        return self.env["sale.order.line"], 0.0

    def _rebuild_match_lines(self):
        self.ensure_one()
        po = self.purchase_order_id
        so = self.sale_order_id
        invoices = (
            self.customer_invoice_id
            if self.show_customer_invoice and self.customer_invoice_id
            else self.env["account.move"]
        )
        pols = po.order_line.filtered(_is_product_line)
        sols = self._eligible_sale_lines(so)
        commands = [(5, 0, 0)]

        for pol in pols:
            product_label = pol.product_id.display_name or pol.name or "—"
            sale_line, qty_assign = self._suggest_sale_line(pol, sols, invoices)
            ambiguous = (
                not sale_line
                and len(sols.filtered(lambda s, p=pol: s.product_id == p.product_id)) > 1
            )

            if ambiguous:
                commands.append(
                    (
                        0,
                        0,
                        {
                            "purchase_line_id": pol.id,
                            "product_po_label": product_label,
                            "sale_line_id": False,
                            "qty_po": pol.product_qty,
                            "qty_to_assign": 0.0,
                            "needs_selection": True,
                        },
                    )
                )
                continue

            commands.append(
                (
                    0,
                    0,
                    {
                        "purchase_line_id": pol.id,
                        "product_po_label": product_label,
                        "sale_line_id": sale_line.id if sale_line else False,
                        "qty_po": pol.product_qty,
                        "qty_to_assign": max(qty_assign, 0.0) if sale_line else 0.0,
                        "needs_selection": not bool(sale_line),
                    },
                )
            )
        self.line_ids = commands

    def action_next_match(self):
        self.ensure_one()
        self._validate_client_step()
        self._rebuild_match_lines()
        self.state = "match"
        return self._reopen()

    def action_back_client(self):
        self.ensure_one()
        self.state = "client"
        return self._reopen()

    def _validate_allocation_lines(self):
        self.ensure_one()
        svc = LineAllocationService(self.env)
        invoices = (
            self.customer_invoice_id
            if self.show_customer_invoice and self.customer_invoice_id
            else None
        )
        alloc_rows = []
        # Track wizard-internal consumption so two rows cannot claim the same SOL.
        claimed = {}
        for line in self.line_ids:
            if float_compare(line.qty_to_assign or 0.0, 0.0, precision_digits=4) <= 0:
                continue
            if not line.sale_line_id:
                raise UserError(
                    _("Seleccione la línea de venta para %(prod)s.")
                    % {"prod": line.product_po_label or "—"}
                )
            sol = line.sale_line_id
            qty_avail_sol = svc.sol_qty_available_for_margin(
                sol, invoice_moves=invoices
            )
            already = claimed.get(sol.id, 0.0)
            qty_avail_sol = max(qty_avail_sol - already, 0.0)
            if float_compare(qty_avail_sol, 0.0, precision_digits=4) <= 0:
                raise UserError(
                    _("Esta venta ya tiene cubierta la cantidad requerida para %(prod)s.")
                    % {"prod": line.product_po_label or sol.product_id.display_name}
                )
            if float_compare(line.qty_to_assign, qty_avail_sol, precision_digits=4) > 0:
                raise UserError(
                    _(
                        "No puede asignar %(qty)s a %(prod)s: pendiente de cubrir %(avail)s."
                    )
                    % {
                        "qty": line.qty_to_assign,
                        "prod": line.product_po_label or "—",
                        "avail": qty_avail_sol,
                    }
                )
            avail_pol = svc.pol_qty_available(line.purchase_line_id)
            if float_compare(line.qty_to_assign, avail_pol, precision_digits=4) > 0:
                raise UserError(
                    _(
                        "Cantidad excedida en OC para %(prod)s: disponible %(avail)s."
                    )
                    % {
                        "prod": line.product_po_label or "—",
                        "avail": avail_pol,
                    }
                )
            claimed[sol.id] = already + (line.qty_to_assign or 0.0)
            alloc_rows.append(
                {
                    "sale_line": sol,
                    "purchase_line": line.purchase_line_id,
                    "quantity": line.qty_to_assign,
                }
            )
        if not alloc_rows:
            raise UserError(_("Indique al menos una cantidad a asignar."))
        return alloc_rows

    def action_confirm_link(self):
        self.ensure_one()
        self._validate_client_step()
        alloc_rows = self._validate_allocation_lines()
        inv = (
            self.customer_invoice_id
            if self.show_customer_invoice and self.customer_invoice_id
            else self.env["account.move"]
        )
        execute_po_to_sale_link(
            self.env,
            purchase_order=self.purchase_order_id,
            sale_order=self.sale_order_id,
            customer=self.customer_id,
            allocation_rows=alloc_rows,
            customer_invoice=inv,
        )
        po = self.purchase_order_id
        return {
            "type": "ir.actions.act_window",
            "name": _("Orden de compra"),
            "res_model": "purchase.order",
            "res_id": po.id,
            "view_mode": "form",
            "target": "current",
        }

    def _reopen(self):
        return {
            "type": "ir.actions.act_window",
            "name": _("Vincular a venta"),
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }


class PurchaseSaleLinkSaleWizardLine(models.TransientModel):
    _name = "purchase.sale.link.sale.wizard.line"
    _description = "Línea vincular PO a venta"

    wizard_id = fields.Many2one(
        "purchase.sale.link.sale.wizard", required=True, ondelete="cascade"
    )
    purchase_line_id = fields.Many2one(
        "purchase.order.line", string="Línea compra", required=True
    )
    product_po_label = fields.Char(string="Artículo OC", readonly=True)
    qty_po = fields.Float(string="Cant. OC", digits="Product Unit of Measure")
    sale_line_id = fields.Many2one("sale.order.line", string="Línea venta")
    sale_line_label = fields.Char(
        string="Línea venta", compute="_compute_sale_line_label"
    )
    qty_sold = fields.Float(
        string="Vendido", compute="_compute_qtys", digits="Product Unit of Measure"
    )
    qty_covered = fields.Float(
        string="Ya cubierto", compute="_compute_qtys", digits="Product Unit of Measure"
    )
    qty_to_assign = fields.Float(string="Asignar", digits="Product Unit of Measure")
    link_status = fields.Selection(LINK_STATUS, compute="_compute_link_status")
    status_label = fields.Char(string="Estado", compute="_compute_link_status")
    needs_selection = fields.Boolean(default=False)
    sale_line_domain = fields.Char(compute="_compute_sale_line_domain")

    @api.depends("sale_line_id")
    def _compute_sale_line_label(self):
        for rec in self:
            if rec.sale_line_id:
                rec.sale_line_label = rec.sale_line_id.product_id.display_name or rec.sale_line_id.name
            else:
                rec.sale_line_label = ""

    @api.depends("wizard_id.sale_order_id", "purchase_line_id")
    def _compute_sale_line_domain(self):
        """All product lines of selected SO — product match is suggestion only."""
        for rec in self:
            so = rec.wizard_id.sale_order_id
            if not so:
                rec.sale_line_domain = repr([("id", "=", False)])
                continue
            rec.sale_line_domain = repr(
                [
                    ("order_id", "=", so.id),
                    ("display_type", "=", False),
                    ("product_id", "!=", False),
                ]
            )

    @api.depends(
        "sale_line_id",
        "qty_to_assign",
        "qty_sold",
        "qty_covered",
        "wizard_id.customer_invoice_id",
        "wizard_id.show_customer_invoice",
    )
    def _compute_qtys(self):
        svc = LineAllocationService(self.env)
        for rec in self:
            sol = rec.sale_line_id
            if not sol:
                rec.qty_sold = 0.0
                rec.qty_covered = 0.0
                continue
            wiz = rec.wizard_id
            invoices = (
                wiz.customer_invoice_id
                if wiz.show_customer_invoice and wiz.customer_invoice_id
                else None
            )
            rec.qty_sold = svc.sol_final_sale_qty(sol, invoice_moves=invoices)
            rec.qty_covered = svc.sol_qty_assigned_to_purchase(sol)

    @api.depends(
        "sale_line_id",
        "qty_to_assign",
        "qty_sold",
        "qty_covered",
        "qty_po",
    )
    def _compute_link_status(self):
        for rec in self:
            if not rec.sale_line_id:
                rec.link_status = "unlinked"
                rec.status_label = "🔴 Sin vincular"
                continue
            if float_compare(rec.qty_to_assign or 0.0, 0.0, precision_digits=4) <= 0:
                if float_compare(rec.qty_covered or 0.0, rec.qty_sold or 0.0, precision_digits=4) >= 0:
                    rec.link_status = "linked"
                    rec.status_label = "🟢 Cubierta"
                else:
                    rec.link_status = "unlinked"
                    rec.status_label = "🔴 Sin vincular"
                continue
            pending_after = max(
                (rec.qty_sold or 0.0) - (rec.qty_covered or 0.0) - (rec.qty_to_assign or 0.0),
                0.0,
            )
            pol_covered = float_compare(
                rec.qty_to_assign or 0.0, rec.qty_po or 0.0, precision_digits=4
            ) >= 0
            sol_covered = float_compare(pending_after, 0.0, precision_digits=4) <= 0
            if pol_covered and sol_covered:
                rec.link_status = "linked"
                rec.status_label = "🟢 Vinculada"
            else:
                rec.link_status = "partial"
                rec.status_label = "🟠 Parcial"
