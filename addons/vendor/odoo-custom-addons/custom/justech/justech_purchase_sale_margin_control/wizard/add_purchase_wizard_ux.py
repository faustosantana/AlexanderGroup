# -*- coding: utf-8 -*-
"""19.0.8.1.0 — Asistente: Proveedor → Documentos (sin preselección) → Confirmar.

Carga OC al elegir proveedor (todas sin marcar).
Facturas solo contextuales (ligadas a OC seleccionadas o acción explícita).
Nunca crea líneas de artículo sin documento origen.
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools.float_utils import float_is_zero

from .margin_labels import (
    label_invoice_state,
    label_move_type,
    label_payment_state,
    label_po_state,
)


def _move_ncf(move):
    if not move:
        return ""
    for fname in ("l10n_do_fiscal_number", "l10n_latam_document_number"):
        if fname in move._fields and move[fname]:
            return move[fname]
    return move.ref or ""


class PurchaseSaleAddPurchaseWizard(models.TransientModel):
    _inherit = "purchase.sale.add.purchase.wizard"

    partner_id = fields.Many2one(
        "res.partner",
        string="Proveedor",
        help="Al seleccionar el proveedor se cargan sus órdenes de compra disponibles (sin marcar).",
    )
    search_ncf = fields.Char(string="Buscar NCF / e-CF")
    search_product_id = fields.Many2one("product.product", string="Filtrar producto")

    vendor_bill_ids = fields.Many2many(
        "account.move",
        "psm_add_po_wiz_bill_rel",
        "wizard_id",
        "move_id",
        string="Facturas de proveedor relacionadas",
        domain="[('company_id', '=', company_id), ('move_type', 'in', ('in_invoice', 'in_refund')), "
               "('state', '!=', 'cancel')]",
    )

    header_customer = fields.Char(compute="_compute_header")
    header_sale_invoice = fields.Char(compute="_compute_header")
    header_sale_untaxed = fields.Monetary(
        compute="_compute_header", currency_field="company_currency_id"
    )
    header_current_cost = fields.Monetary(
        compute="_compute_header", currency_field="company_currency_id"
    )
    header_current_margin = fields.Monetary(
        compute="_compute_header", currency_field="company_currency_id"
    )
    company_currency_id = fields.Many2one(
        related="company_id.currency_id", string="Moneda compañía"
    )

    po_candidate_ids = fields.One2many(
        "purchase.sale.add.purchase.wizard.po.cand",
        "wizard_id",
        string="Órdenes de compra disponibles",
    )
    bill_candidate_ids = fields.One2many(
        "purchase.sale.add.purchase.wizard.bill.cand",
        "wizard_id",
        string="Facturas relacionadas",
    )

    show_article_detail = fields.Boolean(string="Ver detalle de artículos")
    show_direct_bills = fields.Boolean(string="Mostrar facturas directas", default=False)
    selection_counter = fields.Char(string="Resumen", compute="_compute_selection_counter")
    vendor_bill_pending_note = fields.Char(compute="_compute_selection_counter")
    po_selection_help = fields.Char(compute="_compute_selection_counter")
    vendor_bill_open_count = fields.Integer(
        string="Facturas abiertas del proveedor", compute="_compute_vendor_bill_open_count"
    )
    bill_section_title = fields.Char(compute="_compute_selection_counter")
    # Compat Sprint 5/6 tests & domains
    available_po_ids = fields.Many2many(
        "purchase.order",
        string="OC disponibles (compat)",
        compute="_compute_available_pos_compat",
    )

    @api.depends("po_candidate_ids", "po_candidate_ids.purchase_order_id", "partner_id", "company_id")
    def _compute_available_pos_compat(self):
        for wiz in self:
            if wiz.po_candidate_ids:
                wiz.available_po_ids = wiz.po_candidate_ids.mapped("purchase_order_id")
            elif wiz.partner_id:
                wiz.available_po_ids = wiz._search_vendor_pos()
            else:
                wiz.available_po_ids = False

    def _partner_domain_exclude_own_company(self):
        own_partners = self.env.companies.mapped("partner_id").ids
        return [
            ("id", "not in", own_partners),
            "|",
            ("supplier_rank", ">", 0),
            ("is_company", "=", True),
        ]

    @api.depends(
        "transaction_id",
        "sale_order_id",
        "customer_invoice_id",
        "transaction_id.customer_id",
        "transaction_id.sale_real_amount",
        "transaction_id.cost_real_amount",
        "transaction_id.display_margin_amount",
        "transaction_id.customer_invoice_ids",
    )
    def _compute_header(self):
        for wiz in self:
            tx = wiz.transaction_id
            inv = wiz.customer_invoice_id or (tx.customer_invoice_ids[:1] if tx else False)
            so = wiz.sale_order_id or (tx.sale_order_ids[:1] if tx else False)
            wiz.header_customer = (
                (tx.customer_id.display_name if tx and tx.customer_id else False)
                or (so.partner_id.display_name if so else False)
                or (inv.partner_id.display_name if inv else "")
            )
            wiz.header_sale_invoice = (
                (inv.display_name if inv else False)
                or (so.name if so else False)
                or (tx.display_name if tx else "")
            )
            if tx:
                wiz.header_sale_untaxed = tx.sale_real_amount or tx.sale_estimated_amount or 0.0
                wiz.header_current_cost = tx.cost_real_amount or tx.cost_estimated_amount or 0.0
                wiz.header_current_margin = tx.display_margin_amount or 0.0
            elif inv:
                wiz.header_sale_untaxed = inv.amount_untaxed
                wiz.header_current_cost = 0.0
                wiz.header_current_margin = inv.amount_untaxed
            elif so:
                wiz.header_sale_untaxed = so.amount_untaxed
                wiz.header_current_cost = 0.0
                wiz.header_current_margin = so.amount_untaxed
            else:
                wiz.header_sale_untaxed = 0.0
                wiz.header_current_cost = 0.0
                wiz.header_current_margin = 0.0

    @api.depends("partner_id", "company_id", "search_ncf")
    def _compute_vendor_bill_open_count(self):
        for wiz in self:
            if not wiz.partner_id:
                wiz.vendor_bill_open_count = 0
            else:
                wiz.vendor_bill_open_count = len(wiz._search_vendor_bills_raw())

    @api.depends(
        "po_candidate_ids.selected",
        "bill_candidate_ids.selected",
        "bill_candidate_ids",
        "line_ids",
        "line_ids.selected",
        "line_ids.available_amount",
        "show_direct_bills",
        "partner_id",
    )
    def _compute_selection_counter(self):
        for wiz in self:
            pos = wiz.po_candidate_ids.filtered("selected")
            bills = wiz.bill_candidate_ids.filtered("selected")
            arts = wiz.line_ids.filtered("selected")
            cost = sum(arts.mapped("available_amount"))
            wiz.selection_counter = _(
                "%(pos)s OC seleccionadas · %(bills)s facturas seleccionadas · "
                "%(arts)s artículos · RD$%(cost).2f"
            ) % {
                "pos": len(pos),
                "bills": len(bills),
                "arts": len(arts),
                "cost": cost,
            }
            wiz.po_selection_help = _(
                "Seleccione las órdenes de compra que corresponden a esta operación."
            ) if wiz.partner_id else False
            if pos and not bills:
                wiz.vendor_bill_pending_note = _(
                    "Sin factura de proveedor seleccionada: se usará el costo comprometido de la OC."
                )
            elif wiz.partner_id and not pos and not wiz.show_direct_bills:
                wiz.vendor_bill_pending_note = _(
                    "Marque una o más OC para ver facturas relacionadas, "
                    "o use «Agregar factura directa del proveedor»."
                )
            else:
                wiz.vendor_bill_pending_note = False
            if pos:
                wiz.bill_section_title = _("Facturas relacionadas con las OC seleccionadas")
            elif wiz.show_direct_bills:
                wiz.bill_section_title = _("Facturas directas del proveedor")
            else:
                wiz.bill_section_title = _("Facturas relacionadas")

    def _search_vendor_pos(self):
        self.ensure_one()
        if not self.partner_id:
            return self.env["purchase.order"]
        domain = [
            ("company_id", "=", self.company_id.id),
            ("partner_id", "child_of", self.partner_id.commercial_partner_id.id),
            ("state", "!=", "cancel"),
        ]
        if self.search_product_id:
            domain.append(("order_line.product_id", "=", self.search_product_id.id))
        if self.search_ncf:
            bills = self._search_vendor_bills_raw()
            po_ids = bills.invoice_line_ids.mapped("purchase_line_id.order_id").ids
            domain.append(("id", "in", po_ids or [0]))
        pos = self.env["purchase.order"].search(domain, order="date_order desc", limit=200)
        # Keep POs with at least one line commercially available (qty.assignment residual)
        from odoo.addons.justech_purchase_sale_margin_control.services.line_allocation_service import (
            LineAllocationService,
            _is_product_line,
        )
        from odoo.tools.float_utils import float_compare

        svc = LineAllocationService(self.env)
        usable = self.env["purchase.order"]
        for po in pos:
            for pol in po.order_line.filtered(_is_product_line):
                if float_compare(svc.pol_qty_available(pol), 0.0, precision_digits=4) > 0:
                    usable |= po
                    break
        return usable

    def _search_vendor_bills_raw(self):
        self.ensure_one()
        if not self.partner_id:
            return self.env["account.move"]
        domain = [
            ("company_id", "=", self.company_id.id),
            ("partner_id", "=", self.partner_id.id),
            ("move_type", "in", ("in_invoice", "in_refund")),
            ("state", "!=", "cancel"),
        ]
        if self.search_ncf:
            domain = domain + [
                "|",
                "|",
                ("ref", "ilike", self.search_ncf),
                ("name", "ilike", self.search_ncf),
                ("payment_reference", "ilike", self.search_ncf),
            ]
        bills = self.env["account.move"].search(domain, order="invoice_date desc", limit=200)
        if self.search_ncf:
            for fname in ("l10n_do_fiscal_number", "l10n_latam_document_number"):
                if fname in self.env["account.move"]._fields:
                    bills |= self.env["account.move"].search(
                        [
                            ("company_id", "=", self.company_id.id),
                            ("partner_id", "=", self.partner_id.id),
                            ("move_type", "in", ("in_invoice", "in_refund")),
                            ("state", "!=", "cancel"),
                            (fname, "ilike", self.search_ncf),
                        ],
                        limit=200,
                    )
        Tx = self.env["purchase.sale.margin.transaction"]
        usable = self.env["account.move"]
        for bill in bills:
            owners = Tx.search([("vendor_bill_ids", "in", bill.id)])
            if self.transaction_id:
                owners = owners - self.transaction_id
            if owners:
                continue
            usable |= bill
        return usable

    def _build_po_candidates(self, pos):
        rows = []
        for po in pos:
            bills = po.invoice_ids.filtered(
                lambda m: m.move_type in ("in_invoice", "in_refund") and m.state != "cancel"
            )
            pending = max(po.amount_untaxed - sum(bills.mapped("amount_untaxed")), 0.0)
            rows.append(
                (
                    0,
                    0,
                    {
                        "purchase_order_id": po.id,
                        "selected": False,
                        "date_order": po.date_order,
                        "origin": po.origin or "",
                        "state_label": label_po_state(po.state),
                        "amount_total": po.amount_total,
                        "currency_id": po.currency_id.id,
                        "amount_to_invoice": pending,
                        "existing_bills": ", ".join([(b.name or b.ref or str(b.id)) for b in bills]) or "",
                    },
                )
            )
        return rows

    def _build_bill_candidates(self, bills, selected_ids=None):
        selected_ids = set(selected_ids or [])
        rows = []
        for bill in bills:
            pos = bill.invoice_line_ids.mapped("purchase_line_id.order_id")
            rows.append(
                (
                    0,
                    0,
                    {
                        "vendor_bill_id": bill.id,
                        "selected": bill.id in selected_ids,
                        "ncf": _move_ncf(bill),
                        "invoice_date": bill.invoice_date,
                        "po_names": ", ".join(pos.mapped("name")) or "",
                        "amount_untaxed": bill.amount_untaxed,
                        "amount_tax": bill.amount_tax,
                        "amount_total": bill.amount_total,
                        "amount_residual": bill.amount_residual,
                        "payment_state": bill.payment_state,
                        "payment_state_label": label_payment_state(bill.payment_state),
                        "invoice_state_label": label_invoice_state(bill.state),
                        "currency_id": bill.currency_id.id,
                        "move_type": bill.move_type,
                        "move_type_label": label_move_type(bill.move_type),
                    },
                )
            )
        return rows

    def _filter_usable_bills(self, bills):
        self.ensure_one()
        Tx = self.env["purchase.sale.margin.transaction"]
        usable = self.env["account.move"]
        for bill in bills:
            if bill.move_type not in ("in_invoice", "in_refund") or bill.state == "cancel":
                continue
            if self.partner_id and bill.partner_id != self.partner_id:
                continue
            if bill.company_id != self.company_id:
                continue
            owners = Tx.search([("vendor_bill_ids", "in", bill.id)])
            if self.transaction_id:
                owners = owners - self.transaction_id
            if owners:
                continue
            usable |= bill
        return usable

    def _bills_related_to_pos(self, pos):
        if not pos:
            return self.env["account.move"]
        bills = pos.mapped("invoice_ids")
        bills |= pos.order_line.mapped("invoice_lines.move_id")
        names = [n for n in pos.mapped("name") if n]
        if names and self.partner_id:
            domain = [
                ("company_id", "=", self.company_id.id),
                ("partner_id", "=", self.partner_id.id),
                ("move_type", "in", ("in_invoice", "in_refund")),
                ("state", "!=", "cancel"),
                ("invoice_origin", "in", names),
            ]
            bills |= self.env["account.move"].search(domain, limit=100)
        return self._filter_usable_bills(bills)

    def _reload_documents_from_partner(self):
        """Carga OC del proveedor sin marcar; no despliega tabla masiva de facturas."""
        self.ensure_one()
        prev_selected_po = self.po_candidate_ids.filtered("selected").mapped("purchase_order_id")
        prev_selected_bills = self.bill_candidate_ids.filtered("selected").mapped("vendor_bill_id")
        self.po_candidate_ids = [(5, 0, 0)]
        self.bill_candidate_ids = [(5, 0, 0)]
        self.line_ids = [(5, 0, 0)]
        self.purchase_order_ids = [(5, 0, 0)]
        self.vendor_bill_ids = [(5, 0, 0)]
        self.show_direct_bills = False
        if not self.partner_id:
            return
        pos = self._search_vendor_pos()
        self.po_candidate_ids = self._build_po_candidates(pos)
        if prev_selected_po:
            keep = prev_selected_po.filtered(lambda p: p.partner_id == self.partner_id)
            for cand in self.po_candidate_ids:
                if cand.purchase_order_id in keep:
                    cand.selected = True
            related = self._bills_related_to_pos(
                self.po_candidate_ids.filtered("selected").mapped("purchase_order_id")
            )
            keep_bills = prev_selected_bills & related
            self.bill_candidate_ids = self._build_bill_candidates(
                related, selected_ids=keep_bills.ids
            )
            self._sync_selection_to_legacy_and_articles()

    def _sync_bills_from_selected_pos(self):
        self.ensure_one()
        selected_pos = self.po_candidate_ids.filtered("selected").mapped("purchase_order_id")
        prev_selected = self.bill_candidate_ids.filtered("selected").mapped("vendor_bill_id")
        if not selected_pos and not self.show_direct_bills:
            self.bill_candidate_ids = [(5, 0, 0)]
            return
        if selected_pos:
            related = self._bills_related_to_pos(selected_pos)
            keep = prev_selected & related
            self.bill_candidate_ids = self._build_bill_candidates(related, selected_ids=keep.ids)
        elif self.show_direct_bills:
            bills = self._search_vendor_bills_raw()[:50]
            keep = prev_selected & bills
            self.bill_candidate_ids = self._build_bill_candidates(bills, selected_ids=keep.ids)

    def _sync_selection_to_legacy_and_articles(self):
        self.ensure_one()
        if not self.po_candidate_ids and not self.bill_candidate_ids:
            # Legacy / API path: keep purchase_order_ids and rebuild articles
            if self.purchase_order_ids or self.vendor_bill_ids:
                self._rebuild_article_lines(self.purchase_order_ids, self.vendor_bill_ids)
            return
        selected_pos = self.po_candidate_ids.filtered("selected").mapped("purchase_order_id")
        selected_bills = self.bill_candidate_ids.filtered("selected").mapped("vendor_bill_id")
        bill_pos = selected_bills.invoice_line_ids.mapped("purchase_line_id.order_id")
        all_pos = selected_pos | bill_pos
        self.purchase_order_ids = [(6, 0, all_pos.ids)]
        self.vendor_bill_ids = [(6, 0, selected_bills.ids)]
        if selected_pos or selected_bills:
            self._rebuild_article_lines(all_pos, selected_bills)
        else:
            self.line_ids = [(5, 0, 0)]

    def _rebuild_article_lines(self, pos, bills):
        self.ensure_one()
        Line = self.env["purchase.sale.add.purchase.wizard.line"]
        new_lines = []
        seen_pol = set()
        for po in pos:
            for po_line in po.order_line.filtered(lambda l: not l.display_type):
                if po_line.id in seen_pol:
                    continue
                seen_pol.add(po_line.id)
                qty_elsewhere = Line._qty_assigned_elsewhere(
                    po_line, exclude_transaction=self.transaction_id
                )
                qty_available = max(po_line.product_qty - qty_elsewhere, 0.0)
                new_lines.append(
                    (
                        0,
                        0,
                        {
                            "purchase_order_id": po.id,
                            "purchase_line_id": po_line.id,
                            "vendor_bill_id": False,
                            "product_id": po_line.product_id.id,
                            "description": po_line.name,
                            "product_qty": po_line.product_qty,
                            "qty_received": po_line.qty_received,
                            "qty_invoiced": po_line.qty_invoiced,
                            "qty_available": qty_available,
                            "qty_to_assign": qty_available,
                            "price_unit": po_line.price_unit,
                            "price_subtotal": po_line.price_subtotal,
                            "price_tax": po_line.price_tax,
                            "price_total": po_line.price_total,
                            "currency_id": po.currency_id.id,
                            "cost_usage_type": getattr(po_line, "cost_usage_type", False),
                            "selected": True,
                            "assigned_amount_elsewhere": qty_elsewhere * po_line.price_unit,
                            "available_amount": qty_available * po_line.price_unit,
                        },
                    )
                )
        for bill in bills:
            linked_pol = bill.invoice_line_ids.mapped("purchase_line_id")
            if linked_pol:
                continue
            for aml in bill.invoice_line_ids.filtered(
                lambda l: l.display_type not in ("line_section", "line_note") and l.product_id
            ):
                new_lines.append(
                    (
                        0,
                        0,
                        {
                            "purchase_order_id": False,
                            "purchase_line_id": False,
                            "vendor_bill_id": bill.id,
                            "product_id": aml.product_id.id,
                            "description": aml.name,
                            "product_qty": aml.quantity,
                            "qty_received": 0.0,
                            "qty_invoiced": aml.quantity,
                            "qty_available": aml.quantity,
                            "qty_to_assign": aml.quantity,
                            "price_unit": aml.price_unit,
                            "price_subtotal": aml.price_subtotal,
                            "price_tax": aml.price_total - aml.price_subtotal,
                            "price_total": aml.price_total,
                            "currency_id": bill.currency_id.id,
                            "selected": True,
                            "assigned_amount_elsewhere": 0.0,
                            "available_amount": aml.price_subtotal,
                        },
                    )
                )
        self.line_ids = [(5, 0, 0)] + new_lines

    @api.onchange("partner_id", "search_ncf", "search_product_id", "company_id")
    def _onchange_partner_autoload(self):
        warning = {}
        if self.partner_id and self.partner_id in self.env.companies.mapped("partner_id"):
            warning = {
                "warning": {
                    "title": _("Proveedor = empresa"),
                    "message": _(
                        "Ha seleccionado la propia compañía como proveedor. "
                        "Úselo solo para operaciones intercompany reales."
                    ),
                }
            }
        self._reload_documents_from_partner()
        return warning

    @api.onchange("po_candidate_ids")
    def _onchange_po_candidates_selection(self):
        self._sync_bills_from_selected_pos()
        self._sync_selection_to_legacy_and_articles()

    @api.onchange("bill_candidate_ids")
    def _onchange_bill_candidates_selection(self):
        self._sync_selection_to_legacy_and_articles()

    def action_toggle_article_detail(self):
        self.ensure_one()
        self.show_article_detail = not self.show_article_detail
        return self._reopen()

    def action_show_vendor_bills_summary(self):
        self.ensure_one()
        if not self.partner_id:
            raise UserError(_("Seleccione un proveedor para consultar sus documentos disponibles."))
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Facturas del proveedor"),
                "message": _(
                    "%(count)s factura(s) abierta(s) de este proveedor. "
                    "Use «Agregar factura directa del proveedor» para listarlas, "
                    "o marque una OC para ver solo las relacionadas."
                )
                % {"count": self.vendor_bill_open_count},
                "type": "info",
                "sticky": False,
            },
        }

    def action_add_direct_vendor_bills(self):
        self.ensure_one()
        if not self.partner_id:
            raise UserError(_("Seleccione un proveedor para consultar sus documentos disponibles."))
        self.show_direct_bills = True
        bills = self._search_vendor_bills_raw()[:50]
        prev = self.bill_candidate_ids.filtered("selected").mapped("vendor_bill_id")
        self.bill_candidate_ids = self._build_bill_candidates(bills, selected_ids=prev.ids)
        return self._reopen()

    def action_search_bill_without_partner(self):
        raise UserError(
            _(
                "Para buscar una factura sin proveedor, use Contabilidad → Facturas de proveedor "
                "y luego relaciónela desde la operación. "
                "En este asistente seleccione primero el proveedor."
            )
        )

    def action_search_more_documents(self):
        self.ensure_one()
        if not self.partner_id:
            raise UserError(_("Seleccione primero un proveedor."))
        self._reload_documents_from_partner()
        return self._reopen()

    def action_load_selected_articles(self):
        self.ensure_one()
        if not self.partner_id and not self.purchase_order_ids:
            raise UserError(_("Seleccione primero el proveedor."))
        if self.partner_id and self.purchase_order_ids:
            wrong = self.purchase_order_ids.filtered(lambda p: p.partner_id != self.partner_id)
            if wrong:
                raise UserError(
                    _("Estas OC no pertenecen al proveedor seleccionado: %s")
                    % ", ".join(wrong.mapped("name"))
                )
        if not self.purchase_order_ids and not self.po_candidate_ids and not self.bill_candidate_ids:
            raise UserError(_("Seleccione una o varias órdenes de compra del proveedor."))
        if self.po_candidate_ids or self.bill_candidate_ids:
            self._sync_selection_to_legacy_and_articles()
        else:
            self._onchange_purchase_order_ids()
        if not self.line_ids and self.purchase_order_ids:
            self._onchange_purchase_order_ids()
        if not self.line_ids:
            raise UserError(_("Las OC seleccionadas no tienen líneas de producto cargables."))
        return self._reopen()

    def _onchange_partner_filter(self):
        """Compat Sprint 5 tests."""
        return self._onchange_partner_autoload()

    def action_suggest_related_pos(self):
        self.ensure_one()
        tx = self.transaction_id
        so = self.sale_order_id or (tx.sale_order_ids[:1] if tx else self.env["sale.order"])
        products = so.order_line.mapped("product_id") if so else self.env["product.product"]
        domain = [
            ("company_id", "=", self.company_id.id),
            ("state", "!=", "cancel"),
        ]
        if self.partner_id:
            domain.append(
                ("partner_id", "child_of", self.partner_id.commercial_partner_id.id)
            )
        candidates = self.env["purchase.order"]
        if so:
            candidates |= self.env["purchase.order"].search(
                domain + ["|", ("origin", "ilike", so.name), ("origin", "=", so.name)],
                limit=40,
            )
        if products:
            candidates |= self.env["purchase.order"].search(
                domain + [("order_line.product_id", "in", products.ids)], limit=40
            )
        if not candidates:
            raise UserError(
                _("No se encontraron documentos adicionales. Revise el proveedor o el NCF.")
            )
        if not self.partner_id:
            partners = candidates.mapped("partner_id")
            if len(partners) == 1:
                self.partner_id = partners
        self._reload_documents_from_partner()
        # Sugerencias visibles: el usuario debe marcar expresamente cada OC.
        return self._reopen()

    def action_refresh_lines(self):
        self.ensure_one()
        self._sync_selection_to_legacy_and_articles()
        return self._reopen()

    def _reopen(self):
        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }

    def action_confirm(self):
        self.ensure_one()
        if self.po_candidate_ids or self.bill_candidate_ids:
            self._sync_selection_to_legacy_and_articles()
        elif self.purchase_order_ids:
            # Legacy / tests: lines from selected POs without candidate UI
            if not self.line_ids:
                self._onchange_purchase_order_ids()
        selected_pos = self.po_candidate_ids.filtered("selected").mapped("purchase_order_id")
        selected_bills = self.bill_candidate_ids.filtered("selected").mapped("vendor_bill_id")
        if (
            not selected_pos
            and not selected_bills
            and not self.purchase_order_ids
            and not self.vendor_bill_ids
        ):
            raise UserError(
                _(
                    "No se seleccionó ninguna Orden de Compra. "
                    "Seleccione una OC o una factura de proveedor para continuar."
                )
            )
        if selected_bills and not self.purchase_order_ids and not selected_pos:
            return self._confirm_bill_only(selected_bills)
        if not self.purchase_order_ids and selected_pos:
            self.purchase_order_ids = [(6, 0, selected_pos.ids)]
        if selected_bills:
            self.vendor_bill_ids = [(6, 0, selected_bills.ids)]
        bad = self.line_ids.filtered(lambda l: not l.purchase_order_id and not l.vendor_bill_id)
        if bad:
            self.line_ids = [(6, 0, (self.line_ids - bad).ids)]
        try:
            result = super().action_confirm()
        except UserError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise UserError(
                _(
                    "No se pudo agregar los costos. Verifique que seleccionó "
                    "una OC o una factura de proveedor válida."
                )
            ) from exc
        tx_id = result.get("res_id") if isinstance(result, dict) else False
        tx = self.env["purchase.sale.margin.transaction"].browse(tx_id) if tx_id else self.transaction_id
        if selected_bills and tx:
            tx.with_context(skip_line_sync=True).write(
                {"vendor_bill_ids": [(4, b.id) for b in selected_bills]}
            )
            tx._sync_lines_from_documents()
        return result

    def _confirm_bill_only(self, bills):
        self.ensure_one()
        transaction = self._get_or_create_transaction()
        transaction.with_context(skip_line_sync=True).write(
            {"vendor_bill_ids": [(4, b.id) for b in bills]}
        )
        Allocation = self.env["purchase.sale.cost.allocation"]
        Line = self.env["purchase.sale.margin.transaction.line"]
        sale_target = self._resolve_single_sale_order(transaction)
        for bill in bills:
            for aml in bill.invoice_line_ids.filtered(
                lambda l: l.display_type not in ("line_section", "line_note")
                and not float_is_zero(l.price_subtotal, precision_digits=2)
            ):
                po_line = aml.purchase_line_id
                po = po_line.order_id if po_line else self.env["purchase.order"]
                if po:
                    transaction.with_context(skip_line_sync=True).write(
                        {"purchase_order_ids": [(4, po.id)]}
                    )
                existing = Line.search(
                    [
                        ("transaction_id", "=", transaction.id),
                        ("account_move_id", "=", bill.id),
                        ("product_id", "=", aml.product_id.id),
                        ("line_type", "=", "cost"),
                    ],
                    limit=1,
                )
                vals = {
                    "transaction_id": transaction.id,
                    "line_type": "cost",
                    "data_origin": "accounting",
                    "account_move_id": bill.id,
                    "account_move_line_id": aml.id,
                    "purchase_order_id": po.id if po else False,
                    "purchase_order_line_id": po_line.id if po_line else False,
                    "partner_id": bill.partner_id.id,
                    "product_id": aml.product_id.id,
                    "description": aml.name,
                    "currency_id": bill.currency_id.id,
                    "quantity": aml.quantity,
                    "amount_untaxed": abs(aml.price_subtotal),
                    "amount_tax": abs(aml.price_total - aml.price_subtotal),
                    "amount_total": abs(aml.price_total),
                    "is_manual": False,
                }
                if existing:
                    existing.with_context(skip_line_sync=True).write(vals)
                else:
                    Line.create(vals)
                if sale_target:
                    Allocation.create(
                        {
                            "company_id": self.company_id.id,
                            "transaction_id": transaction.id,
                            "vendor_bill_id": bill.id,
                            "purchase_order_id": po.id if po else False,
                            "purchase_order_line_id": po_line.id if po_line else False,
                            "sale_order_id": sale_target.id,
                            "partner_id": sale_target.partner_id.id,
                            "supplier_id": bill.partner_id.id,
                            "product_id": aml.product_id.id,
                            "currency_id": bill.currency_id.id,
                            "source_amount": abs(aml.price_subtotal),
                            "allocated_amount": abs(aml.price_subtotal),
                            "allocation_method": "amount",
                            "source": "manual",
                            "confidence": 75,
                            "is_manual": False,
                            "state": "suggested",
                        }
                    )
        transaction._sync_lines_from_documents()
        transaction.message_post(
            body=_(
                "%(user)s agregó facturas de proveedor %(bills)s a la operación."
            )
            % {
                "user": self.env.user.display_name,
                "bills": ", ".join([(b.name or b.ref or str(b.id)) for b in bills]),
            }
        )
        return {
            "type": "ir.actions.act_window",
            "name": _("Operación de margen"),
            "res_model": "purchase.sale.margin.transaction",
            "view_mode": "form",
            "res_id": transaction.id,
        }


class PurchaseSaleAddPurchaseWizardPoCand(models.TransientModel):
    _name = "purchase.sale.add.purchase.wizard.po.cand"
    _description = "OC candidata del asistente de costos"
    _order = "date_order desc, id"

    wizard_id = fields.Many2one(
        "purchase.sale.add.purchase.wizard", required=True, ondelete="cascade"
    )
    selected = fields.Boolean(string="Seleccionar", default=False)
    purchase_order_id = fields.Many2one("purchase.order", string="OC", required=True)
    date_order = fields.Datetime(string="Fecha")
    origin = fields.Char(string="Origen")
    state = fields.Selection(
        related="purchase_order_id.state",
        string="Estado",
        readonly=True,
    )
    state_label = fields.Char(string="Estado legible")
    amount_total = fields.Monetary(string="Total", currency_field="currency_id")
    currency_id = fields.Many2one("res.currency", string="Moneda")
    amount_to_invoice = fields.Monetary(string="Pendiente de facturar", currency_field="currency_id")
    existing_bills = fields.Char(string="Facturas relacionadas")


class PurchaseSaleAddPurchaseWizardBillCand(models.TransientModel):
    _name = "purchase.sale.add.purchase.wizard.bill.cand"
    _description = "Factura proveedor candidata del asistente de costos"
    _order = "invoice_date desc, id"

    wizard_id = fields.Many2one(
        "purchase.sale.add.purchase.wizard", required=True, ondelete="cascade"
    )
    selected = fields.Boolean(string="Seleccionar", default=False)
    vendor_bill_id = fields.Many2one("account.move", string="Factura", required=True)
    ncf = fields.Char(string="NCF / e-CF")
    invoice_date = fields.Date(string="Fecha")
    po_names = fields.Char(string="OC")
    amount_untaxed = fields.Monetary(string="Subtotal", currency_field="currency_id")
    amount_tax = fields.Monetary(string="ITBIS", currency_field="currency_id")
    amount_total = fields.Monetary(string="Total", currency_field="currency_id")
    amount_residual = fields.Monetary(string="Saldo", currency_field="currency_id")
    payment_state = fields.Char(string="Pago técnico")
    payment_state_label = fields.Char(string="Pago")
    invoice_state_label = fields.Char(string="Estado")
    currency_id = fields.Many2one("res.currency", string="Moneda")
    move_type = fields.Char(string="Tipo técnico")
    move_type_label = fields.Char(string="Tipo")


class PurchaseSaleAddPurchaseWizardLine(models.TransientModel):
    _inherit = "purchase.sale.add.purchase.wizard.line"

    vendor_bill_id = fields.Many2one("account.move", string="Factura proveedor")
    purchase_order_id = fields.Many2one(required=False)
    purchase_line_id = fields.Many2one(required=False)

    @api.model_create_multi
    def create(self, vals_list):
        clean = []
        for vals in vals_list:
            if not vals.get("purchase_order_id") and not vals.get("vendor_bill_id"):
                continue
            clean.append(vals)
        if not clean:
            return self.browse()
        return super().create(clean)
