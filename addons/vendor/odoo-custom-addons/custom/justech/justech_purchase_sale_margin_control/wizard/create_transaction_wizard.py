# -*- coding: utf-8 -*-
"""Crear/vincular operación with document + line qty allocation (29.15+) + filter UX (29.16)."""
import json
import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools.float_utils import float_compare
from odoo.tools.safe_eval import safe_eval

from ..models.margin_acl import user_can_read_customer_invoices
from ..models.margin_transaction import TRANSACTION_TYPES
from ..services.line_allocation_service import LineAllocationService, _is_product_line

_logger = logging.getLogger(__name__)


class PurchaseSaleCreateTransactionWizard(models.TransientModel):
    """Create/link MTX with optional SOL↔POL quantity allocation.

    Never creates accounting moves. Never writes SO/PO quantities or NCF.
    """

    _name = "purchase.sale.create.transaction.wizard"
    _description = "Crear/vincular operación de margen"

    state = fields.Selection(
        [
            ("docs", "Documentos"),
            ("purchase_pick", "Artículos de compra"),
            ("sale_match", "Relacionar con venta"),
            ("summary", "Resumen"),
        ],
        default="docs",
        required=True,
        string="Paso",
    )
    company_id = fields.Many2one(
        "res.company",
        string="Empresa",
        default=lambda self: self.env.company,
        required=True,
    )
    name = fields.Char(string="Descripción")
    transaction_type = fields.Selection(
        TRANSACTION_TYPES, string="Tipo de operación", default="manual", required=True
    )
    transaction_date = fields.Date(
        string="Fecha", default=fields.Date.context_today, required=True
    )
    customer_id = fields.Many2one("res.partner", string="Cliente")
    supplier_id = fields.Many2one(
        "res.partner",
        string="Proveedor activo",
        domain="[('supplier_rank', '>', 0)]",
        help="Proveedor en curso del asistente (paso compras). Preferir Proveedores.",
    )
    supplier_ids = fields.Many2many(
        "res.partner",
        "create_tx_wizard_supplier_rel",
        "wizard_id",
        "partner_id",
        string="Proveedores",
        domain="[('supplier_rank', '>', 0)]",
        help="Uno o varios proveedores que abastecen esta venta.",
    )
    active_supplier_id = fields.Many2one(
        "res.partner",
        string="Proveedor en curso",
    )
    supplier_step_index = fields.Integer(string="Índice proveedor", default=0)
    supplier_step_label = fields.Char(compute="_compute_supplier_step_label")
    is_last_supplier_step = fields.Boolean(compute="_compute_supplier_step_label")
    working_purchase_order_ids = fields.Many2many(
        "purchase.order",
        "create_tx_wizard_working_po_rel",
        "wizard_id",
        "purchase_order_id",
        string="Órdenes de compra (proveedor en curso)",
    )
    active_purchase_order_domain = fields.Char(compute="_compute_doc_domains")
    supplier_isolation_hint = fields.Char(compute="_compute_supplier_step_label")
    # JSON stash: {"<pol_id>": qty_to_relate, ...} — survives supplier step navigation
    pick_qty_stash = fields.Text(string="Stash cantidades compra", default="{}")
    existing_assignment_html = fields.Html(
        string="Ya relacionado",
        compute="_compute_existing_assignment_html",
        sanitize=False,
    )
    # Commercial partner ids for domains that survive "Buscar más…"
    customer_commercial_id = fields.Many2one(
        "res.partner",
        compute="_compute_commercial_partners",
        string="Cliente comercial",
    )
    supplier_commercial_id = fields.Many2one(
        "res.partner",
        compute="_compute_commercial_partners",
        string="Proveedor comercial",
    )
    # Plain ints for OWL context (never NewId / recordset)
    company_id_int = fields.Integer(compute="_compute_commercial_partners")
    customer_commercial_id_int = fields.Integer(compute="_compute_commercial_partners")
    supplier_commercial_id_int = fields.Integer(compute="_compute_commercial_partners")
    # Char domains evaluated by the web client (stick on Search More)
    sale_order_domain = fields.Char(compute="_compute_doc_domains")
    purchase_order_domain = fields.Char(compute="_compute_doc_domains")
    customer_invoice_domain = fields.Char(compute="_compute_doc_domains")
    vendor_bill_domain = fields.Char(compute="_compute_doc_domains")
    customer_filter_hint = fields.Char(compute="_compute_filter_hints")
    supplier_filter_hint = fields.Char(compute="_compute_filter_hints")
    show_customer_invoices = fields.Boolean(
        compute="_compute_show_customer_invoices",
        string="Puede ver facturas cliente",
    )

    sale_order_ids = fields.Many2many(
        "sale.order",
        string="Cotizaciones / Órdenes de venta",
    )
    purchase_order_ids = fields.Many2many(
        "purchase.order",
        string="Órdenes de compra",
    )
    customer_invoice_ids = fields.Many2many(
        "account.move",
        "create_tx_wizard_customer_invoice_rel",
        "wizard_id",
        "move_id",
        string="Facturas de cliente",
        context={"justech_margin_show_ncf": True},
    )
    vendor_bill_ids = fields.Many2many(
        "account.move",
        "create_tx_wizard_vendor_bill_rel",
        "wizard_id",
        "move_id",
        string="Facturas de proveedor",
        context={"justech_margin_show_ncf": True},
    )
    salesperson_id = fields.Many2one("res.users", string="Vendedor comercial")
    registered_by_id = fields.Many2one(
        "res.users",
        string="Registrado por",
        default=lambda self: self.env.user,
        readonly=True,
    )
    purchase_responsible_id = fields.Many2one("res.users", string="Responsable de compras")
    finance_responsible_id = fields.Many2one("res.users", string="Responsable de finanzas")
    notes = fields.Text(string="Notas")
    show_fully_assigned = fields.Boolean(
        string="Mostrar líneas ya asignadas",
        default=False,
        help="Por defecto solo se listan líneas con cantidad disponible para relacionar.",
    )

    purchase_pick_line_ids = fields.One2many(
        "purchase.sale.create.transaction.wizard.purchase.line",
        "wizard_id",
        string="Artículos de compra",
    )
    allocation_line_ids = fields.One2many(
        "purchase.sale.create.transaction.wizard.line",
        "wizard_id",
        string="Relación con venta",
    )
    purchase_pick_summary_html = fields.Html(
        string="Resumen compra seleccionada",
        compute="_compute_purchase_pick_summary",
        sanitize=False,
    )
    purchase_pick_status_html = fields.Html(
        string="Estado artículos de compra",
        compute="_compute_purchase_pick_status",
        sanitize=False,
    )
    purchase_pick_load_error = fields.Text(
        string="Error carga artículos",
        readonly=True,
    )
    can_advance_purchase_pick = fields.Boolean(
        compute="_compute_can_advance_purchase_pick",
        string="Puede avanzar desde compras",
    )
    selected_purchase_line_ids = fields.Many2many(
        "purchase.order.line",
        compute="_compute_selected_purchase_line_ids",
        string="Líneas OC seleccionadas",
    )
    summary_html = fields.Html(string="Resumen", compute="_compute_summary_html")
    remaining_po_qty_info = fields.Char(compute="_compute_summary_html")

    @api.depends("customer_id", "supplier_id", "supplier_ids", "active_supplier_id", "company_id")
    def _compute_commercial_partners(self):
        for wiz in self:
            cid = wiz._commercial_db_id(wiz.customer_id)
            wiz.customer_commercial_id = cid or False
            wiz.customer_commercial_id_int = cid or 0
            active_sid = wiz._active_supplier_commercial_id()
            wiz.supplier_commercial_id = active_sid or False
            wiz.supplier_commercial_id_int = active_sid or 0
            wiz.company_id_int = wiz._company_db_id() or 0

    @api.depends(
        "company_id",
        "customer_id",
        "supplier_id",
        "supplier_ids",
        "active_supplier_id",
        "customer_commercial_id",
        "supplier_commercial_id",
    )
    def _compute_doc_domains(self):
        for wiz in self:
            wiz.sale_order_domain = repr(wiz._sale_domain())
            wiz.purchase_order_domain = repr(wiz._purchase_domain())
            wiz.customer_invoice_domain = repr(wiz._customer_invoice_domain())
            wiz.vendor_bill_domain = repr(wiz._vendor_bill_domain())
            wiz.active_purchase_order_domain = repr(wiz._active_purchase_domain())

    @api.depends("customer_id", "supplier_id", "supplier_ids")
    def _compute_filter_hints(self):
        for wiz in self:
            wiz.customer_filter_hint = (
                _("Mostrando únicamente documentos de %s") % wiz.customer_id.display_name
                if wiz.customer_id
                else _("Seleccione un cliente para filtrar ventas y facturas.")
            )
            if wiz.supplier_ids:
                names = ", ".join(wiz.supplier_ids.mapped("display_name"))
                wiz.supplier_filter_hint = _(
                    "Proveedores seleccionados: %s. Las OC se eligen por proveedor en el siguiente paso."
                ) % names
            elif wiz.supplier_id:
                wiz.supplier_filter_hint = (
                    _("Mostrando únicamente documentos de %s") % wiz.supplier_id.display_name
                )
            else:
                wiz.supplier_filter_hint = _(
                    "Seleccione uno o varios proveedores. Luego elegirá OC por proveedor."
                )

    def _compute_show_customer_invoices(self):
        can = user_can_read_customer_invoices(self.env)
        for wiz in self:
            wiz.show_customer_invoices = can

    @api.depends("supplier_ids", "supplier_step_index", "active_supplier_id")
    def _compute_supplier_step_label(self):
        for wiz in self:
            ordered = wiz._ordered_suppliers()
            total = len(ordered)
            idx = max(0, min(wiz.supplier_step_index or 0, max(total - 1, 0)))
            if total:
                current = ordered[idx] if idx < total else ordered[:1]
                name = current.display_name if current else "—"
                wiz.supplier_step_label = _(
                    "Proveedor %(n)s de %(total)s — %(name)s"
                ) % {"n": idx + 1, "total": total, "name": name}
                wiz.is_last_supplier_step = idx >= total - 1
                wiz.supplier_isolation_hint = _(
                    "Mostrando únicamente órdenes y artículos de %s."
                ) % name
            else:
                wiz.supplier_step_label = _("Sin proveedores seleccionados")
                wiz.is_last_supplier_step = True
                wiz.supplier_isolation_hint = False

    @api.depends("sale_order_ids", "customer_invoice_ids")
    def _compute_existing_assignment_html(self):
        Assign = (
            self.env["justech.purchase.sale.qty.assignment"]
            if "justech.purchase.sale.qty.assignment" in self.env
            else None
        )
        for wiz in self:
            if not Assign or not wiz.sale_order_ids:
                wiz.existing_assignment_html = False
                continue
            asgs = Assign.search(
                [
                    ("sale_order_id", "in", wiz.sale_order_ids.ids),
                    ("state", "=", "active"),
                ]
            )
            if not asgs:
                wiz.existing_assignment_html = False
                continue
            rows = []
            for a in asgs:
                rows.append(
                    "<tr><td>%s</td><td>%s</td><td>%s</td><td>%.2f</td></tr>"
                    % (
                        a.purchase_order_id.partner_id.display_name or "",
                        a.purchase_order_id.name or "",
                        a.sale_line_id.product_id.display_name or "",
                        a.quantity or 0.0,
                    )
                )
            wiz.existing_assignment_html = (
                "<p><b>Ya relacionado (qty.assignment activo)</b></p>"
                "<table class='table table-sm'><thead><tr>"
                "<th>Proveedor</th><th>OC</th><th>Producto</th><th>Cant.</th>"
                "</tr></thead><tbody>%s</tbody></table>"
            ) % "".join(rows)

    def _sale_domain(self):
        self.ensure_one()
        if not self.company_id or not self.customer_id:
            return [("id", "=", False)]
        return [
            ("company_id", "=", self.company_id.id),
            ("partner_id", "child_of", self.customer_id.commercial_partner_id.id),
            ("state", "!=", "cancel"),
        ]

    def _db_id(self, record):
        """Integer DB id only — never NewId (breaks OWL domain serialization)."""
        if not record:
            return False
        rid = record.id
        if isinstance(rid, int):
            return rid
        # NewId / virtual: prefer origin / _origin
        origin = getattr(rid, "origin", None)
        if isinstance(origin, int):
            return origin
        try:
            orig = record._origin
            if orig and isinstance(orig.id, int):
                return orig.id
        except Exception:
            pass
        return False

    def _db_ids(self, records):
        return [i for i in (self._db_id(r) for r in records) if i]

    def _commercial_db_id(self, partner):
        """Commercial partner id as plain int (or False)."""
        pid = self._db_id(partner)
        if not pid:
            return False
        partner = self.env["res.partner"].browse(pid)
        if not partner.exists():
            return False
        return self._db_id(partner.commercial_partner_id) or pid

    def _company_db_id(self):
        return self._db_id(self.company_id)

    def _ordered_suppliers(self):
        self.ensure_one()
        # Browse by real ids so sorting/stepping never carries NewId into domains
        real_ids = self._db_ids(self.supplier_ids)
        return self.env["res.partner"].browse(real_ids).sorted(
            key=lambda p: (p.display_name or "", p.id)
        )

    def _supplier_commercial_ids(self):
        self.ensure_one()
        return list(
            {
                cid
                for cid in (
                    self._commercial_db_id(s) for s in (self.supplier_ids or [])
                )
                if cid
            }
        )

    def _active_supplier_commercial_id(self):
        self.ensure_one()
        active = self.active_supplier_id or self.supplier_id
        return self._commercial_db_id(active)

    def _purchase_domain(self):
        """Session-wide PO domain (hidden accumulator) — real int ids only."""
        self.ensure_one()
        company_id = self._company_db_id()
        commercial_ids = self._supplier_commercial_ids()
        if not company_id or not commercial_ids:
            return [("id", "=", False)]
        return [
            ("company_id", "=", company_id),
            ("partner_id", "child_of", commercial_ids),
            ("state", "!=", "cancel"),
        ]

    def _active_purchase_domain(self):
        """POs for the supplier currently on screen — single commercial id."""
        self.ensure_one()
        company_id = self._company_db_id()
        sid = self._active_supplier_commercial_id()
        if not company_id or not sid:
            return [("id", "=", False)]
        return [
            ("company_id", "=", company_id),
            ("partner_id", "child_of", sid),
            ("state", "!=", "cancel"),
        ]

    def _customer_invoice_domain(self):
        self.ensure_one()
        company_id = self._company_db_id()
        cid = self._commercial_db_id(self.customer_id)
        if not company_id or not cid:
            return [("id", "=", False)]
        return [
            ("company_id", "=", company_id),
            ("move_type", "in", ("out_invoice", "out_refund")),
            ("state", "=", "posted"),
            ("partner_id", "child_of", cid),
        ]

    def _vendor_bill_domain(self):
        """Vendor bills: prefer current supplier; else all selected (int ids only)."""
        self.ensure_one()
        company_id = self._company_db_id()
        if not company_id:
            return [("id", "=", False)]
        # On purchase_pick (or when active set): isolate to current supplier
        active_sid = self._active_supplier_commercial_id()
        if active_sid and self.state == "purchase_pick":
            commercial_ids = [active_sid]
        else:
            commercial_ids = self._supplier_commercial_ids()
            if not commercial_ids and active_sid:
                commercial_ids = [active_sid]
        if not commercial_ids:
            return [("id", "=", False)]
        # Single id → scalar child_of (clearest); multi → list of ints
        partner_clause = (
            ("partner_id", "child_of", commercial_ids[0])
            if len(commercial_ids) == 1
            else ("partner_id", "child_of", commercial_ids)
        )
        return [
            ("company_id", "=", company_id),
            ("move_type", "in", ("in_invoice", "in_refund")),
            ("state", "=", "posted"),
            partner_clause,
        ]

    def _wizard_doc_context(self, extra=None):
        """Context keys for name_search — only plain ints (never recordsets/NewId)."""
        self.ensure_one()
        commercial_ids = self._supplier_commercial_ids()
        active_sid = self._active_supplier_commercial_id()
        ctx = {
            "justech_margin_wizard": True,
            "justech_margin_wizard_company_id": self._company_db_id() or False,
            "justech_margin_wizard_customer_id": self._commercial_db_id(self.customer_id)
            or False,
            "justech_margin_wizard_supplier_ids": commercial_ids,
            "justech_margin_wizard_supplier_id": active_sid
            or (commercial_ids[0] if commercial_ids else False),
            "default_company_id": self._company_db_id() or False,
        }
        if extra:
            ctx.update(extra)
        return ctx

    @api.onchange("customer_id", "company_id")
    def _onchange_customer_company(self):
        svc = LineAllocationService(self.env)
        if self.customer_id:
            cid = svc.commercial_id(self.customer_id)
            bad_so = self.sale_order_ids.filtered(
                lambda s: svc.commercial_id(s.partner_id) != cid
                or s.company_id != self.company_id
            )
            bad_inv = self.customer_invoice_ids.filtered(
                lambda m: svc.commercial_id(m.partner_id) != cid
                or m.company_id != self.company_id
            )
            if bad_so:
                self.sale_order_ids = self.sale_order_ids - bad_so
            if bad_inv:
                self.customer_invoice_ids = self.customer_invoice_ids - bad_inv
            if self.sale_order_ids[:1].user_id:
                self.salesperson_id = self.sale_order_ids[:1].user_id
        else:
            self.sale_order_ids = [(5, 0, 0)]
            self.customer_invoice_ids = [(5, 0, 0)]
        self.allocation_line_ids = [(5, 0, 0)]

    @api.onchange("supplier_ids", "company_id")
    def _onchange_supplier_ids(self):
        svc = LineAllocationService(self.env)
        if self.supplier_ids:
            if not self.supplier_id or self.supplier_id not in self.supplier_ids:
                self.supplier_id = self.supplier_ids[:1]
            allowed = {svc.commercial_id(s) for s in self.supplier_ids}
            bad_po = self.purchase_order_ids.filtered(
                lambda p: svc.commercial_id(p.partner_id) not in allowed
                or p.company_id != self.company_id
            )
            bad_bill = self.vendor_bill_ids.filtered(
                lambda m: svc.commercial_id(m.partner_id) not in allowed
                or m.company_id != self.company_id
            )
            if bad_po:
                self.purchase_order_ids = self.purchase_order_ids - bad_po
            if bad_bill:
                self.vendor_bill_ids = self.vendor_bill_ids - bad_bill
        else:
            self.purchase_order_ids = [(5, 0, 0)]
            self.vendor_bill_ids = [(5, 0, 0)]
            self.working_purchase_order_ids = [(5, 0, 0)]
            self.supplier_id = False
            self.active_supplier_id = False

    @api.onchange("supplier_id", "company_id")
    def _onchange_supplier_company(self):
        # Compat: single supplier_id still syncs into supplier_ids
        if self.supplier_id and self.supplier_id not in self.supplier_ids:
            self.supplier_ids = self.supplier_ids | self.supplier_id
        self._onchange_supplier_ids()

    @api.onchange("sale_order_ids")
    def _onchange_sale_orders(self):
        if self.sale_order_ids and not self.customer_id:
            self.customer_id = self.sale_order_ids[:1].partner_id.commercial_partner_id
        if self.sale_order_ids[:1].user_id:
            self.salesperson_id = self.sale_order_ids[:1].user_id
        self._autoload_customer_invoices()

    def _autoload_customer_invoices(self):
        """Replace wizard customer invoices with those linked to selected SOs."""
        self.ensure_one()
        if not user_can_read_customer_invoices(self.env):
            self.customer_invoice_ids = [(5, 0, 0)]
            return
        svc = LineAllocationService(self.env)
        linked = svc.customer_invoices_for_sale_orders(
            self.sale_order_ids, company=self.company_id
        )
        # Keep only invoices that still belong to selected SOs (or clear if no SO)
        self.customer_invoice_ids = linked

    @api.onchange("purchase_order_ids")
    def _onchange_purchase_orders(self):
        if self.purchase_order_ids and not self.supplier_ids:
            partners = self.purchase_order_ids.mapped("partner_id.commercial_partner_id")
            self.supplier_ids = partners
            self.supplier_id = partners[:1]
        # Do not wipe allocation lines here — multi-vendor navigation must preserve state.

    @api.onchange("working_purchase_order_ids", "show_fully_assigned")
    def _onchange_working_purchase_orders(self):
        """Autoload POL candidates when the user selects/changes POs (no extra button)."""
        if self.state and self.state != "purchase_pick":
            return
        self.purchase_pick_load_error = False
        try:
            self._commit_working_pos_to_session()
            self._rebuild_purchase_pick_lines(preserve=True, only_current_supplier=True)
        except Exception as exc:  # noqa: BLE001 — never leave a silent empty table
            _logger.exception("Margins wizard: failed to autoload purchase lines")
            names = ", ".join(self.working_purchase_order_ids.mapped("name")) or "—"
            self.purchase_pick_line_ids = [(5, 0, 0)]
            self.purchase_pick_load_error = _(
                "No fue posible cargar los artículos de %(pos)s. Causa técnica: %(err)s"
            ) % {"pos": names, "err": str(exc)}

    @api.depends(
        "purchase_pick_line_ids.qty_to_relate",
        "pick_qty_stash",
        "working_purchase_order_ids",
        "is_last_supplier_step",
    )
    def _compute_can_advance_purchase_pick(self):
        for wiz in self:
            visible = any(
                float_compare(l.qty_to_relate or 0.0, 0.0, precision_digits=4) > 0
                for l in wiz.purchase_pick_line_ids
            )
            if visible:
                wiz.can_advance_purchase_pick = True
                continue
            # Allow advancing past a supplier with no POs selected (skip).
            if not wiz.working_purchase_order_ids:
                stash = wiz._load_pick_stash()
                has_stash = any(
                    float_compare(float(v or 0.0), 0.0, precision_digits=4) > 0
                    for v in stash.values()
                )
                # Last step still needs some pick somewhere to go to sale_match.
                wiz.can_advance_purchase_pick = (
                    (not wiz.is_last_supplier_step) or has_stash
                )
            else:
                wiz.can_advance_purchase_pick = False

    @api.depends(
        "working_purchase_order_ids",
        "purchase_pick_line_ids",
        "purchase_pick_line_ids.qty_available",
        "show_fully_assigned",
        "active_supplier_id",
        "purchase_pick_load_error",
    )
    def _compute_purchase_pick_status(self):
        svc = LineAllocationService(self.env)
        for wiz in self:
            if wiz.purchase_pick_load_error:
                wiz.purchase_pick_status_html = _(
                    "<div class='alert alert-danger' role='alert'>"
                    "<p class='mb-0'><b>%s</b></p>"
                    "</div>"
                ) % wiz.purchase_pick_load_error
                continue
            pos = wiz.working_purchase_order_ids
            if not pos:
                wiz.purchase_pick_status_html = _(
                    "<div class='alert alert-secondary' role='status'>"
                    "Seleccione una o más órdenes de compra. "
                    "Los artículos se cargan automáticamente."
                    "</div>"
                )
                continue
            pols = pos.mapped("order_line").filtered(_is_product_line)
            if not pols:
                wiz.purchase_pick_status_html = _(
                    "<div class='alert alert-warning' role='status'>"
                    "Las órdenes seleccionadas no tienen líneas de producto."
                    "</div>"
                )
                continue
            purchased = sum(pols.mapped("product_qty"))
            available = sum(svc.pol_qty_available(p) for p in pols)
            assigned = max(purchased - available, 0.0)
            visible = len(wiz.purchase_pick_line_ids)
            po_names = ", ".join(pos.mapped("name"))
            if visible:
                wiz.purchase_pick_status_html = _(
                    "<div class='text-muted mb-2'>"
                    "Órdenes: <b>%(pos)s</b> · "
                    "Líneas visibles: %(vis)s · "
                    "Comprado: %(bought).0f · Ya relacionado: %(asg).0f · "
                    "Disponible: %(avail).0f"
                    "</div>"
                ) % {
                    "pos": po_names,
                    "vis": visible,
                    "bought": purchased,
                    "asg": assigned,
                    "avail": available,
                }
                continue
            # Product lines exist but none shown → explain (fully assigned / cancelled)
            asg_bits = []
            if "justech.purchase.sale.qty.assignment" in wiz.env:
                Assign = wiz.env["justech.purchase.sale.qty.assignment"]
                for a in Assign.search(
                    [
                        ("purchase_line_id", "in", pols.ids),
                        ("state", "=", "active"),
                    ],
                    limit=12,
                ):
                    asg_bits.append(
                        "<li>%s · %s · %s · cant. %.0f</li>"
                        % (
                            a.purchase_line_id.product_id.display_name or "",
                            a.purchase_order_id.name or "",
                            a.sale_order_id.name or "—",
                            a.quantity or 0.0,
                        )
                    )
            detail = (
                "<ul class='mb-2'>%s</ul>" % "".join(asg_bits) if asg_bits else ""
            )
            hint = ""
            if float_compare(available, 0.0, precision_digits=4) <= 0:
                hint = _(
                    "<p class='mb-1'>Active «Mostrar líneas ya asignadas» para ver el detalle, "
                    "o elija otra OC con cantidad disponible.</p>"
                )
            wiz.purchase_pick_status_html = _(
                "<div class='alert alert-warning' role='status'>"
                "<p><b>Esta orden de compra no tiene cantidades disponibles para relacionar.</b></p>"
                "<p>Órdenes: %(pos)s<br/>"
                "Comprado: %(bought).0f · Ya relacionado: %(asg).0f · Disponible: %(avail).0f</p>"
                "%(detail)s%(hint)s"
                "</div>"
            ) % {
                "pos": po_names,
                "bought": purchased,
                "asg": assigned,
                "avail": available,
                "detail": detail,
                "hint": hint,
            }

    @api.depends(
        "allocation_line_ids.qty_to_assign",
        "allocation_line_ids.allocated_cost",
        "allocation_line_ids.allocated_sale",
        "allocation_line_ids.allocated_margin",
        "allocation_line_ids.sale_product_id",
        "allocation_line_ids.purchase_product_id",
        "purchase_order_ids",
        "sale_order_ids",
        "customer_id",
        "supplier_id",
        "customer_invoice_ids",
        "vendor_bill_ids",
    )
    def _compute_summary_html(self):
        svc = LineAllocationService(self.env)
        for wiz in self:
            lines = wiz.allocation_line_ids.filtered(
                lambda l: float_compare(l.qty_to_assign, 0.0, precision_digits=4) > 0
            )
            sale = sum(lines.mapped("allocated_sale"))
            cost = sum(lines.mapped("allocated_cost"))
            margin = sale - cost
            pct = (margin / sale * 100.0) if sale else 0.0
            cost_label = (
                _("REAL / FACTURA")
                if wiz.vendor_bill_ids
                else _("COMPROMETIDO / OC")
            )
            remaining_bits = []
            for po in wiz.purchase_order_ids:
                for pol in po.order_line.filtered(_is_product_line):
                    avail = svc.pol_qty_available(pol)
                    assigned_here = sum(
                        lines.filtered(lambda l, p=pol: l.purchase_line_id == p).mapped(
                            "qty_to_assign"
                        )
                    )
                    left = max(avail - assigned_here, 0.0)
                    if float_compare(left, 0.0, precision_digits=4) > 0:
                        remaining_bits.append(
                            _("%(prod)s: %(qty)s uds")
                            % {
                                "prod": pol.product_id.display_name or pol.name,
                                "qty": left,
                            }
                        )
            wiz.remaining_po_qty_info = (
                _("Quedan disponibles para otras ventas: %s") % ", ".join(remaining_bits)
                if remaining_bits
                else _("Sin cantidades pendientes en las OC seleccionadas (según esta asignación).")
            )
            rows = "".join(
                _(
                    "<tr>"
                    "<td>%(sp)s</td><td>%(sq).2f</td>"
                    "<td>%(pp)s</td><td>%(aq).2f</td>"
                    "<td>%(cost).2f</td>"
                    "</tr>"
                )
                % {
                    "sp": l.sale_product_id.display_name or "",
                    "sq": l.qty_sold or 0.0,
                    "pp": l.purchase_product_id.display_name or "",
                    "aq": l.qty_to_assign or 0.0,
                    "cost": l.allocated_cost or 0.0,
                }
                for l in lines
            )
            wiz.summary_html = _(
                "<p><b>Cliente:</b> %(cust)s<br/>"
                "<b>Venta:</b> %(so)s<br/>"
                "<b>Factura cliente:</b> %(cinv)s</p>"
                "<p><b>Proveedor:</b> %(supp)s<br/>"
                "<b>OC:</b> %(po)s<br/>"
                "<b>Factura proveedor:</b> %(vb)s</p>"
                "<table class='table table-sm'>"
                "<thead><tr>"
                "<th>Producto vendido</th><th>Cant. venta</th>"
                "<th>Producto comprado</th><th>Cant. asignada</th>"
                "<th>Costo atribuible</th>"
                "</tr></thead><tbody>%(rows)s</tbody></table>"
                "<ul>"
                "<li><b>Venta atribuible:</b> %(sale).2f</li>"
                "<li><b>Costo (%(cost_label)s):</b> %(cost).2f</li>"
                "<li><b>Margen:</b> %(margin).2f (%(pct).1f%%)</li>"
                "</ul>"
            ) % {
                "cust": wiz.customer_id.display_name or "—",
                "so": ", ".join(wiz.sale_order_ids.mapped("name")) or "—",
                "cinv": ", ".join(wiz.customer_invoice_ids.mapped("name")) or "—",
                "supp": wiz.supplier_id.display_name or "—",
                "po": ", ".join(wiz.purchase_order_ids.mapped("name")) or "—",
                "vb": ", ".join(wiz.vendor_bill_ids.mapped("name")) or "—",
                "rows": rows or "<tr><td colspan='5'>—</td></tr>",
                "sale": sale,
                "cost": cost,
                "cost_label": cost_label,
                "margin": margin,
                "pct": pct,
            }

    def _validate_documents(self):
        self.ensure_one()
        svc = LineAllocationService(self.env)
        suppliers = self.supplier_ids or self.supplier_id
        svc.assert_sale_docs_match_customer(
            self.company_id, self.customer_id, self.sale_order_ids, self.customer_invoice_ids
        )
        svc.assert_purchase_docs_match_suppliers(
            self.company_id, suppliers, self.purchase_order_ids, self.vendor_bill_ids
        )
        for so in self.sale_order_ids:
            if so.company_id and so.company_id != self.company_id:
                raise ValidationError(_("Todos los documentos deben ser de la misma empresa."))
        for po in self.purchase_order_ids:
            if po.company_id and po.company_id != self.company_id:
                raise ValidationError(_("Todos los documentos deben ser de la misma empresa."))
        for move in self.customer_invoice_ids | self.vendor_bill_ids:
            if move.company_id and move.company_id != self.company_id:
                raise ValidationError(_("Todos los documentos deben ser de la misma empresa."))

    def _needs_line_allocation(self):
        """True when SO+PO product lines exist — must not silent-confirm docs-only."""
        self.ensure_one()
        sols = self.sale_order_ids.mapped("order_line").filtered(_is_product_line)
        pols = self.purchase_order_ids.mapped("order_line").filtered(_is_product_line)
        return bool(sols and pols)

    def action_next_to_purchase_pick(self):
        """Paso 1 → Paso 2 (compras por proveedor)."""
        self.ensure_one()
        if not (
            self.sale_order_ids
            or self.purchase_order_ids
            or self.customer_invoice_ids
            or self.vendor_bill_ids
            or self.name
            or self.supplier_ids
        ):
            raise UserError(
                _("Agregue al menos un documento relacionado, proveedores o una descripción.")
            )
        if self.sale_order_ids:
            self._autoload_customer_invoices()
        if not self.supplier_ids and self.supplier_id:
            self.supplier_ids = self.supplier_id
        if not self.supplier_ids:
            raise UserError(
                _("Seleccione al menos un proveedor. Puede agregar varios en la misma sesión.")
            )
        # Validate sale side only; POs are chosen per supplier in step 2
        svc = LineAllocationService(self.env)
        svc.assert_sale_docs_match_customer(
            self.company_id, self.customer_id, self.sale_order_ids, self.customer_invoice_ids
        )
        for so in self.sale_order_ids:
            if so.company_id and so.company_id != self.company_id:
                raise ValidationError(_("Todos los documentos deben ser de la misma empresa."))
        self.supplier_step_index = 0
        self._enter_supplier_step(0)
        self.state = "purchase_pick"
        return self._reopen()

    # Backwards-compatible alias
    def action_next_to_alloc(self):
        return self.action_next_to_purchase_pick()

    def _enter_supplier_step(self, index):
        """Set active supplier and load its already-selected POs into working set."""
        self.ensure_one()
        self._stash_visible_picks()
        ordered = self._ordered_suppliers()
        if not ordered:
            raise UserError(_("Seleccione al menos un proveedor."))
        index = max(0, min(index, len(ordered) - 1))
        self.supplier_step_index = index
        active = ordered[index]
        # Always bind Many2one to browsed DB record (plain int id)
        self.active_supplier_id = active.id
        self.supplier_id = active.id
        svc = LineAllocationService(self.env)
        sid = svc.commercial_id(active)
        current_pos = self.purchase_order_ids.filtered(
            lambda p: svc.commercial_id(p.partner_id) == sid
        )
        self.working_purchase_order_ids = current_pos
        self.purchase_pick_load_error = False
        # Visible table: ONLY this supplier (stash keeps other suppliers' qtys)
        try:
            self._rebuild_purchase_pick_lines(preserve=True, only_current_supplier=True)
        except Exception as exc:  # noqa: BLE001
            _logger.exception("Margins wizard: failed to rebuild purchase pick lines")
            names = ", ".join(current_pos.mapped("name")) or "—"
            self.purchase_pick_line_ids = [(5, 0, 0)]
            self.purchase_pick_load_error = _(
                "No fue posible cargar los artículos de %(pos)s. Causa técnica: %(err)s"
            ) % {"pos": names, "err": str(exc)}

    def _commit_working_pos_to_session(self):
        """Merge working POs for active supplier into session purchase_order_ids."""
        self.ensure_one()
        self._stash_visible_picks()
        svc = LineAllocationService(self.env)
        active = self.active_supplier_id or self.supplier_id
        if not active:
            return
        sid = svc.commercial_id(active)
        others = self.purchase_order_ids.filtered(
            lambda p: svc.commercial_id(p.partner_id) != sid
        )
        working = self.working_purchase_order_ids.filtered(
            lambda p: p.state != "cancel"
            and p.company_id == self.company_id
            and svc.commercial_id(p.partner_id) == sid
        )
        self.purchase_order_ids = others | working
        self.working_purchase_order_ids = working

    def action_load_working_purchase_lines(self):
        """Backend/compat: reload product lines (autoload normally replaces the button)."""
        self.ensure_one()
        self.purchase_pick_load_error = False
        try:
            self._commit_working_pos_to_session()
            if not self.working_purchase_order_ids:
                raise UserError(
                    _("Seleccione al menos una orden de compra de %s.")
                    % (self.active_supplier_id.display_name or _("este proveedor"))
                )
            self._rebuild_purchase_pick_lines(preserve=True, only_current_supplier=True)
        except UserError:
            raise
        except Exception as exc:  # noqa: BLE001
            _logger.exception("Margins wizard: failed to load purchase lines")
            names = ", ".join(self.working_purchase_order_ids.mapped("name")) or "—"
            self.purchase_pick_line_ids = [(5, 0, 0)]
            self.purchase_pick_load_error = _(
                "No fue posible cargar los artículos de %(pos)s. Causa técnica: %(err)s"
            ) % {"pos": names, "err": str(exc)}
        return self._reopen()

    def _load_pick_stash(self):
        self.ensure_one()
        try:
            data = json.loads(self.pick_qty_stash or "{}")
        except (TypeError, ValueError, json.JSONDecodeError):
            data = {}
        return {str(k): float(v) for k, v in data.items()}

    def _save_pick_stash(self, data):
        self.ensure_one()
        self.pick_qty_stash = json.dumps(data or {})

    def _stash_visible_picks(self):
        """Merge currently visible purchase_pick lines into JSON stash."""
        self.ensure_one()
        data = self._load_pick_stash()
        for line in self.purchase_pick_line_ids:
            pol_id = self._db_id(line.purchase_line_id)
            if not pol_id:
                continue
            data[str(pol_id)] = float(line.qty_to_relate or 0.0)
        self._save_pick_stash(data)

    def _stash_pick_qtys(self):
        """Compat: return stash dict keyed by int pol id."""
        self.ensure_one()
        self._stash_visible_picks()
        raw = self._load_pick_stash()
        return {int(k): v for k, v in raw.items() if str(k).isdigit()}

    def _rebuild_purchase_pick_lines(self, preserve=True, only_current_supplier=True):
        """Visible POL rows. By default ONLY current supplier (session stash keeps rest)."""
        self.ensure_one()
        if preserve:
            self._stash_visible_picks()
        stash = self._stash_pick_qtys() if preserve else {}
        svc = LineAllocationService(self.env)
        if only_current_supplier:
            active = self.active_supplier_id or self.supplier_id
            sid = svc.commercial_id(active) if active else False
            pos = (self.working_purchase_order_ids or self.purchase_order_ids).filtered(
                lambda p: sid and svc.commercial_id(p.partner_id) == sid
            )
        else:
            pos = self.purchase_order_ids
        commands = [(5, 0, 0)]
        for pol in pos.mapped("order_line").filtered(_is_product_line):
            avail = svc.pol_qty_available(pol)
            if (
                not self.show_fully_assigned
                and float_compare(avail, 0.0, precision_digits=4) <= 0
            ):
                continue
            unit = (
                (pol.price_subtotal or 0.0) / pol.product_qty
                if pol.product_qty
                else (pol.price_unit or 0.0)
            )
            qty_prev = stash.get(pol.id, 0.0)
            commands.append(
                (
                    0,
                    0,
                    {
                        "purchase_line_id": pol.id,
                        "selected": float_compare(qty_prev, 0.0, precision_digits=4) > 0,
                        "qty_to_relate": qty_prev,
                        "is_fully_assigned": float_compare(avail, 0.0, precision_digits=4)
                        <= 0,
                        "unit_cost_stored": unit,
                    },
                )
            )
        self.purchase_pick_line_ids = commands

    def _rebuild_purchase_pick_lines_all_suppliers(self):
        """Before sale_match/summary: materialize ALL stashed picks across suppliers."""
        self.ensure_one()
        self._stash_visible_picks()
        self._rebuild_purchase_pick_lines(preserve=True, only_current_supplier=False)

    def action_next_supplier(self):
        """Save current supplier picks and advance to next supplier."""
        self.ensure_one()
        self._commit_working_pos_to_session()
        # Require at least one pick qty for current supplier before leaving,
        # OR allow skip if no PO selected (user may skip a supplier)
        picks_here = self._selected_purchase_picks().filtered(
            lambda l: l.purchase_line_id.order_id.partner_id.commercial_partner_id
            == (self.active_supplier_id.commercial_partner_id if self.active_supplier_id else False)
        )
        if self.working_purchase_order_ids and not picks_here:
            # POs selected but no qty — force user to set qty or clear POs
            raise UserError(
                _(
                    "Indique cantidades a relacionar para las OC de %s, "
                    "o quite las OC si este proveedor no aporta costos en esta sesión."
                )
                % (self.active_supplier_id.display_name or "")
            )
        if self.working_purchase_order_ids:
            self._validate_purchase_pick_for_orders(self.working_purchase_order_ids)
        ordered = self._ordered_suppliers()
        idx = self.supplier_step_index or 0
        if idx >= len(ordered) - 1:
            return self.action_next_to_sale_match()
        self._enter_supplier_step(idx + 1)
        return self._reopen()

    def action_prev_supplier(self):
        """Go back to previous supplier without losing picks."""
        self.ensure_one()
        self._commit_working_pos_to_session()
        idx = self.supplier_step_index or 0
        if idx <= 0:
            self.state = "docs"
            return self._reopen()
        self._enter_supplier_step(idx - 1)
        return self._reopen()

    def action_toggle_fully_assigned(self):
        self.ensure_one()
        self.show_fully_assigned = not self.show_fully_assigned
        if self.state == "purchase_pick":
            self._rebuild_purchase_pick_lines(preserve=True, only_current_supplier=True)
        elif self.state == "sale_match":
            self._rebuild_sale_match_lines()
        return self._reopen()

    def _selected_purchase_picks(self):
        # qty_to_relate > 0 implies selection (checkbox auto-set on onchange)
        return self.purchase_pick_line_ids.filtered(
            lambda l: float_compare(l.qty_to_relate, 0.0, precision_digits=4) > 0
        )

    def _validate_purchase_pick_for_orders(self, purchase_orders):
        self.ensure_one()
        picks = self._selected_purchase_picks().filtered(
            lambda l: l.purchase_line_id.order_id in purchase_orders
        )
        if not picks:
            raise UserError(
                _("Seleccione al menos un artículo de compra con cantidad a relacionar.")
            )
        svc = LineAllocationService(self.env)
        for pick in picks:
            if not pick.purchase_line_id:
                raise ValidationError(_("Falta la línea de compra."))
            avail = svc.pol_qty_available(pick.purchase_line_id)
            if float_compare(pick.qty_to_relate, 0.0, precision_digits=4) <= 0:
                raise UserError(_("La cantidad a relacionar debe ser positiva."))
            if float_compare(pick.qty_to_relate, avail, precision_digits=4) > 0:
                raise UserError(
                    _(
                        "No se puede relacionar %(qty)s de %(prod)s: disponible %(avail)s."
                    )
                    % {
                        "qty": pick.qty_to_relate,
                        "prod": pick.purchase_line_id.product_id.display_name,
                        "avail": avail,
                    }
                )

    def _validate_purchase_pick(self):
        self.ensure_one()
        if not self.purchase_order_ids:
            raise UserError(
                _("Seleccione al menos una orden de compra de los proveedores elegidos.")
            )
        self._validate_purchase_pick_for_orders(self.purchase_order_ids)

    def action_next_to_sale_match(self):
        """Último proveedor → asignar a ventas (materializa todas las picks del stash)."""
        self.ensure_one()
        self._commit_working_pos_to_session()
        self._rebuild_purchase_pick_lines_all_suppliers()
        self._validate_purchase_pick()
        if self.sale_order_ids:
            self._autoload_customer_invoices()
        if not self.sale_order_ids:
            raise UserError(
                _("Seleccione al menos una orden de venta para relacionar las compras.")
            )
        self._rebuild_sale_match_lines()
        self.state = "sale_match"
        return self._reopen()

    def _rebuild_sale_match_lines(self):
        """Sale lines; one allocation row per (SOL, matching POL pick) for multi-vendor."""
        self.ensure_one()
        svc = LineAllocationService(self.env)
        invoices = self.customer_invoice_ids
        picks = self._selected_purchase_picks()
        selected_pols = picks.mapped("purchase_line_id")
        budget = {p.purchase_line_id.id: p.qty_to_relate for p in picks}
        commands = [(5, 0, 0)]
        sols = self.sale_order_ids.mapped("order_line").filtered(_is_product_line)
        for sol in sols:
            final = svc.sol_final_sale_qty(sol, invoice_moves=invoices or None)
            if float_compare(final, 0.0, precision_digits=4) <= 0:
                continue
            assigned = svc.sol_qty_assigned_to_purchase(sol)
            available = max(final - assigned, 0.0)
            if (
                not self.show_fully_assigned
                and float_compare(available, 0.0, precision_digits=4) <= 0
            ):
                continue
            matches = selected_pols.filtered(lambda p, s=sol: p.product_id == s.product_id)
            if not matches:
                commands.append(
                    (
                        0,
                        0,
                        {
                            "sale_line_id": sol.id,
                            "purchase_line_id": False,
                            "qty_to_assign": 0.0,
                            "selected": False,
                            "is_fully_assigned": float_compare(available, 0.0, precision_digits=4)
                            <= 0,
                        },
                    )
                )
                continue
            rem_sale = available
            for pol in matches:
                if float_compare(rem_sale, 0.0, precision_digits=4) <= 0:
                    break
                rem_po = budget.get(pol.id, 0.0)
                if float_compare(rem_po, 0.0, precision_digits=4) <= 0:
                    continue
                qty_suggest = min(rem_sale, rem_po)
                budget[pol.id] = max(rem_po - qty_suggest, 0.0)
                rem_sale = max(rem_sale - qty_suggest, 0.0)
                commands.append(
                    (
                        0,
                        0,
                        {
                            "sale_line_id": sol.id,
                            "purchase_line_id": pol.id,
                            "qty_to_assign": qty_suggest,
                            "selected": float_compare(qty_suggest, 0.0, precision_digits=4) > 0,
                            "is_fully_assigned": float_compare(available, 0.0, precision_digits=4)
                            <= 0,
                        },
                    )
                )
        self.allocation_line_ids = commands

    def action_suggest_lines(self):
        self.ensure_one()
        if self.state == "purchase_pick":
            self._rebuild_purchase_pick_lines(preserve=True, only_current_supplier=True)
        else:
            self._rebuild_sale_match_lines()
        return self._reopen()

    def _validate_sale_match_balance(self):
        """Sum assigned per POL in 2B must be <= qty chosen in 2A."""
        self.ensure_one()
        picks = {p.purchase_line_id.id: p.qty_to_relate for p in self._selected_purchase_picks()}
        used = {}
        for line in self.allocation_line_ids.filtered(
            lambda l: l.selected
            and float_compare(l.qty_to_assign, 0.0, precision_digits=4) > 0
        ):
            line._validate_qty()
            pol_id = line.purchase_line_id.id
            if pol_id not in picks:
                raise UserError(
                    _(
                        "La línea de compra %(prod)s no fue seleccionada en el paso anterior."
                    )
                    % {"prod": line.purchase_line_id.product_id.display_name}
                )
            used[pol_id] = used.get(pol_id, 0.0) + line.qty_to_assign
        for pol_id, qty_used in used.items():
            allowed = picks[pol_id]
            if float_compare(qty_used, allowed, precision_digits=4) > 0:
                pol = self.env["purchase.order.line"].browse(pol_id)
                raise UserError(
                    _(
                        "Asignó %(used)s de %(prod)s pero en compra solo seleccionó %(allowed)s."
                    )
                    % {
                        "used": qty_used,
                        "prod": pol.product_id.display_name,
                        "allowed": allowed,
                    }
                )
        if not used:
            raise UserError(
                _("Asigne al menos una cantidad de compra a una línea de venta.")
            )

    @api.depends(
        "purchase_pick_line_ids.selected",
        "purchase_pick_line_ids.qty_to_relate",
        "purchase_pick_line_ids.purchase_line_id",
    )
    def _compute_selected_purchase_line_ids(self):
        for wiz in self:
            wiz.selected_purchase_line_ids = wiz._selected_purchase_picks().mapped(
                "purchase_line_id"
            )

    @api.depends(
        "purchase_pick_line_ids.selected",
        "purchase_pick_line_ids.qty_to_relate",
        "purchase_pick_line_ids.purchase_line_id",
        "purchase_pick_line_ids.unit_cost",
    )
    def _compute_purchase_pick_summary(self):
        for wiz in self:
            rows = []
            for p in wiz._selected_purchase_picks():
                pol = p.purchase_line_id
                unit = p.unit_cost or 0.0
                cost = (p.qty_to_relate or 0.0) * unit
                partner = (
                    pol.order_id.partner_id.commercial_partner_id.display_name
                    or pol.order_id.partner_id.display_name
                    or ""
                )
                rows.append(
                    _(
                        "<tr>"
                        "<td>%(prod)s</td>"
                        "<td>%(partner)s / %(doc)s</td>"
                        "<td>%(qty).2f</td>"
                        "<td>%(cost).2f</td>"
                        "</tr>"
                    )
                    % {
                        "prod": pol.product_id.display_name or pol.name,
                        "partner": partner,
                        "qty": p.qty_to_relate,
                        "doc": pol.order_id.name,
                        "cost": cost,
                    }
                )
            wiz.purchase_pick_summary_html = (
                _(
                    "<p><b>COMPRA SELECCIONADA</b></p>"
                    "<table class='table table-sm'><thead><tr>"
                    "<th>Producto</th><th>Proveedor / OC</th>"
                    "<th>Cantidad</th><th>Costo</th>"
                    "</tr></thead><tbody>%(rows)s</tbody></table>"
                    "<p class='text-muted mb-0'>↓ ASIGNAR A líneas de venta abajo</p>"
                )
                % {"rows": "".join(rows) or "<tr><td colspan='4'>—</td></tr>"}
            )

    def action_next_to_summary(self):
        self.ensure_one()
        self._validate_documents()
        self._validate_sale_match_balance()
        self.state = "summary"
        return self._reopen()

    def action_back_docs(self):
        self.ensure_one()
        self._commit_working_pos_to_session()
        self.state = "docs"
        return self._reopen()

    def action_back_purchase_pick(self):
        self.ensure_one()
        # From sale match → last supplier step (preserve picks)
        ordered = self._ordered_suppliers()
        if ordered:
            self._enter_supplier_step(len(ordered) - 1)
        self.state = "purchase_pick"
        return self._reopen()

    def action_back_sale_match(self):
        self.ensure_one()
        self.state = "sale_match"
        return self._reopen()

    def action_back_alloc(self):
        """Compatibility: from summary go back to sale match."""
        return self.action_back_sale_match()

    def _reopen(self):
        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
            "context": dict(self.env.context),
        }

    def action_create(self):
        """Docs-only shortcut — blocked when SO+PO need quantity allocation."""
        self.ensure_one()
        if self._needs_line_allocation():
            raise UserError(
                _(
                    "Hay venta y compra con artículos. Use «Siguiente: asignar artículos» "
                    "para indicar qué cantidades de la OC corresponden a la venta. "
                    "Así se evita cargar el 100%% del costo de la compra."
                )
            )
        return self.action_confirm_relation()

    def action_confirm_relation(self):
        self.ensure_one()
        self._validate_documents()
        alloc_rows = []
        for line in self.allocation_line_ids.filtered(
            lambda l: l.selected
            and float_compare(l.qty_to_assign, 0.0, precision_digits=4) > 0
        ):
            line._validate_qty()
            alloc_rows.append(
                {
                    "sale_line": line.sale_line_id,
                    "purchase_line": line.purchase_line_id,
                    "quantity": line.qty_to_assign,
                }
            )

        suppliers = self.supplier_ids or self.supplier_id
        salesperson = self.salesperson_id
        if not salesperson and self.sale_order_ids[:1].user_id:
            salesperson = self.sale_order_ids[:1].user_id

        vals = {
            "company_id": self.company_id.id,
            "name": self.name,
            "transaction_type": self.transaction_type,
            "transaction_date": self.transaction_date,
            "customer_id": self.customer_id.id,
            # Append-friendly: canonical attach extracts ids and (4,) merges
            "supplier_ids": [(4, s.id) for s in suppliers],
            "sale_order_ids": [(4, s.id) for s in self.sale_order_ids],
            "purchase_order_ids": [(4, p.id) for p in self.purchase_order_ids],
            "customer_invoice_ids": [(4, i.id) for i in self.customer_invoice_ids],
            "vendor_bill_ids": [(4, b.id) for b in self.vendor_bill_ids],
            "salesperson_id": salesperson.id if salesperson else False,
            "purchase_responsible_id": self.purchase_responsible_id.id,
            "finance_responsible_id": self.finance_responsible_id.id,
            "notes": self.notes,
            "source": "manual",
            "state": "draft",
        }
        Transaction = self.env["purchase.sale.margin.transaction"]
        so = self.sale_order_ids[:1]
        inv = self.customer_invoice_ids[:1]
        ctx = {"skip_line_sync": True} if alloc_rows else {}
        if not alloc_rows and self.sale_order_ids and self.purchase_order_ids:
            ctx = {"skip_line_sync": True, "margin_safe_po_sync": True}

        if so or inv:
            transaction = Transaction.with_context(**ctx).find_or_create_canonical_transaction(
                sale_order=so or None,
                customer_invoice=inv or None,
                vals=vals,
            )
            transaction.with_context(skip_line_sync=True).write(
                {
                    "supplier_ids": [(4, s.id) for s in suppliers],
                    "purchase_order_ids": [(4, p.id) for p in self.purchase_order_ids],
                    "vendor_bill_ids": [(4, b.id) for b in self.vendor_bill_ids],
                    "customer_invoice_ids": [(4, i.id) for i in self.customer_invoice_ids],
                    "sale_order_ids": [(4, s.id) for s in self.sale_order_ids],
                    "salesperson_id": salesperson.id
                    if salesperson and not transaction.salesperson_id
                    else transaction.salesperson_id.id,
                }
            )
        else:
            transaction = Transaction.with_context(**ctx).create(vals)

        svc = LineAllocationService(self.env)
        if alloc_rows:
            svc.apply_allocations_to_transaction(transaction, alloc_rows, replace=False)
            transaction.with_context(
                skip_line_sync=False, margin_skip_unsafe_po_cost=True
            )._sync_lines_from_documents()
        else:
            transaction.with_context(margin_skip_unsafe_po_cost=True)._sync_lines_from_documents()

        if hasattr(transaction, "_compute_cost_allocation_pending"):
            transaction.invalidate_recordset(["cost_allocation_pending"])

        # Bulk path opened from hub: return to hub (preserve context)
        hub_id = self.env.context.get("manage_purchases_wizard_id")
        if hub_id and "purchase.sale.manage.purchases.wizard" in self.env:
            hub = self.env["purchase.sale.manage.purchases.wizard"].browse(hub_id)
            if hub.exists():
                return hub.action_reopen_hub(refresh=True)

        return {
            "type": "ir.actions.act_window",
            "name": _("Operación de margen"),
            "res_model": "purchase.sale.margin.transaction",
            "view_mode": "form",
            "res_id": transaction.id,
        }

    # Public helpers for UAT / RPC domain checks
    def get_sale_order_domain_list(self):
        self.ensure_one()
        return safe_eval(self.sale_order_domain or "[('id', '=', False)]")


class PurchaseSaleCreateTransactionWizardPurchaseLine(models.TransientModel):
    """Paso 2A — selección de cantidades desde OC."""

    _name = "purchase.sale.create.transaction.wizard.purchase.line"
    _description = "Línea de compra a relacionar"

    wizard_id = fields.Many2one(
        "purchase.sale.create.transaction.wizard", required=True, ondelete="cascade"
    )
    selected = fields.Boolean(string="Seleccionar", default=False)
    is_fully_assigned = fields.Boolean(string="Completamente asignada", readonly=True)
    purchase_line_id = fields.Many2one(
        "purchase.order.line", string="Línea de compra", required=True
    )
    purchase_doc = fields.Char(compute="_compute_qtys", string="OC")
    product_id = fields.Many2one(
        related="purchase_line_id.product_id", string="Producto", readonly=True
    )
    qty_purchased = fields.Float(compute="_compute_qtys", string="Comprado")
    qty_assigned = fields.Float(compute="_compute_qtys", string="Ya relacionado")
    qty_available = fields.Float(compute="_compute_qtys", string="Disponible")
    unit_cost = fields.Float(compute="_compute_qtys", string="Costo unitario")
    unit_cost_stored = fields.Float()
    qty_to_relate = fields.Float(string="A relacionar")

    @api.depends("purchase_line_id")
    def _compute_qtys(self):
        svc = LineAllocationService(self.env)
        for rec in self:
            pol = rec.purchase_line_id
            if not pol:
                rec.purchase_doc = ""
                rec.qty_purchased = 0.0
                rec.qty_assigned = 0.0
                rec.qty_available = 0.0
                rec.unit_cost = 0.0
                continue
            avail = svc.pol_qty_available(pol)
            rec.purchase_doc = pol.order_id.name
            rec.qty_purchased = pol.product_qty or 0.0
            rec.qty_available = avail
            rec.qty_assigned = max((pol.product_qty or 0.0) - avail, 0.0)
            rec.unit_cost = (
                rec.unit_cost_stored
                or (
                    (pol.price_subtotal or 0.0) / pol.product_qty
                    if pol.product_qty
                    else (pol.price_unit or 0.0)
                )
            )

    @api.onchange("qty_to_relate")
    def _onchange_qty_to_relate(self):
        # qty > 0 → selected; qty == 0 → not selected (no separate checkbox needed)
        self.selected = (
            float_compare(self.qty_to_relate or 0.0, 0.0, precision_digits=4) > 0
        )
        if float_compare(self.qty_to_relate or 0.0, self.qty_available or 0.0, precision_digits=4) > 0:
            return {
                "warning": {
                    "title": _("Cantidad excedida"),
                    "message": _(
                        "La cantidad a relacionar no puede superar el disponible (%s)."
                    )
                    % (self.qty_available or 0.0),
                }
            }


class PurchaseSaleCreateTransactionWizardLine(models.TransientModel):
    _name = "purchase.sale.create.transaction.wizard.line"
    _description = "Línea de asignación venta↔compra"

    wizard_id = fields.Many2one(
        "purchase.sale.create.transaction.wizard", required=True, ondelete="cascade"
    )
    selected = fields.Boolean(string="Usar", default=True)
    is_fully_assigned = fields.Boolean(string="Completamente asignada", readonly=True)
    sale_line_id = fields.Many2one("sale.order.line", string="Línea de venta", required=True)
    purchase_line_id = fields.Many2one(
        "purchase.order.line", string="Línea de compra"
    )
    sale_product_id = fields.Many2one(
        related="sale_line_id.product_id", string="Producto venta", readonly=True
    )
    purchase_product_id = fields.Many2one(
        related="purchase_line_id.product_id", string="Producto compra", readonly=True
    )
    sale_doc = fields.Char(compute="_compute_qtys", string="Documento venta")
    purchase_doc = fields.Char(compute="_compute_qtys", string="Documento compra")
    qty_sold = fields.Float(compute="_compute_qtys", string="Vendido")
    qty_related = fields.Float(compute="_compute_qtys", string="Ya cubierto")
    qty_sale_available = fields.Float(compute="_compute_qtys", string="Pendiente")
    qty_purchased = fields.Float(compute="_compute_qtys", string="Cant. comprada")
    qty_po_assigned = fields.Float(compute="_compute_qtys", string="Ya asignada OC")
    qty_po_available = fields.Float(compute="_compute_qtys", string="Disp. compra")
    qty_to_assign = fields.Float(string="Cantidad a cubrir")
    unit_cost = fields.Float(compute="_compute_amounts", string="Costo unitario")
    allocated_cost = fields.Float(compute="_compute_amounts", string="Costo atribuible")
    unit_sale = fields.Float(compute="_compute_amounts", string="Precio venta")
    allocated_sale = fields.Float(compute="_compute_amounts", string="Venta atribuible")
    allocated_margin = fields.Float(compute="_compute_amounts", string="Margen")
    margin_pct = fields.Float(compute="_compute_amounts", string="Margen %")

    @api.depends(
        "sale_line_id",
        "purchase_line_id",
        "wizard_id.customer_invoice_ids",
    )
    def _compute_qtys(self):
        svc = LineAllocationService(self.env)
        for rec in self:
            sol = rec.sale_line_id
            pol = rec.purchase_line_id
            invoices = rec.wizard_id.customer_invoice_ids
            rec.sale_doc = sol.order_id.name if sol else ""
            rec.purchase_doc = pol.order_id.name if pol else ""
            if sol:
                final = svc.sol_final_sale_qty(sol, invoice_moves=invoices or None)
                assigned = svc.sol_qty_assigned_to_purchase(sol)
                rec.qty_sold = final
                rec.qty_related = assigned
                rec.qty_sale_available = max(final - assigned, 0.0)
            else:
                rec.qty_sold = 0.0
                rec.qty_related = 0.0
                rec.qty_sale_available = 0.0
            if pol:
                avail = svc.pol_qty_available(pol)
                rec.qty_purchased = pol.product_qty or 0.0
                rec.qty_po_available = avail
                rec.qty_po_assigned = max((pol.product_qty or 0.0) - avail, 0.0)
            else:
                rec.qty_purchased = 0.0
                rec.qty_po_available = 0.0
                rec.qty_po_assigned = 0.0

    @api.depends("qty_to_assign", "sale_line_id", "purchase_line_id", "qty_sold")
    def _compute_amounts(self):
        for rec in self:
            pol = rec.purchase_line_id
            sol = rec.sale_line_id
            qty = rec.qty_to_assign or 0.0
            unit_cost = 0.0
            if pol and pol.product_qty:
                unit_cost = (pol.price_subtotal or 0.0) / pol.product_qty
            elif pol:
                unit_cost = pol.price_unit or 0.0
            unit_sale = 0.0
            if sol and rec.qty_sold:
                # Prefer proportional to final sold qty when invoices drive qty_sold
                unit_sale = (sol.price_subtotal or 0.0) / (sol.product_uom_qty or rec.qty_sold)
            elif sol:
                unit_sale = sol.price_unit or 0.0
            rec.unit_cost = unit_cost
            rec.unit_sale = unit_sale
            rec.allocated_cost = qty * unit_cost
            rec.allocated_sale = qty * unit_sale
            rec.allocated_margin = rec.allocated_sale - rec.allocated_cost
            rec.margin_pct = (
                (rec.allocated_margin / rec.allocated_sale * 100.0)
                if rec.allocated_sale
                else 0.0
            )

    def _validate_qty(self):
        self.ensure_one()
        svc = LineAllocationService(self.env)
        if not self.sale_line_id or not self.purchase_line_id:
            raise ValidationError(_("Cada asignación requiere línea de venta y de compra."))
        if self.wizard_id.company_id != self.sale_line_id.company_id:
            raise ValidationError(_("La línea de venta es de otra empresa."))
        if self.wizard_id.company_id != self.purchase_line_id.company_id:
            raise ValidationError(_("La línea de compra es de otra empresa."))
        if (
            self.sale_line_id.product_id
            and self.purchase_line_id.product_id
            and self.sale_line_id.product_id != self.purchase_line_id.product_id
        ):
            raise ValidationError(
                _("Producto venta/compra no coinciden en la asignación.")
            )
        avail = svc.pol_qty_available(self.purchase_line_id)
        if float_compare(self.qty_to_assign, avail, precision_digits=4) > 0:
            raise UserError(
                _(
                    "No se puede asignar %(qty)s: disponible en OC %(avail)s."
                )
                % {"qty": self.qty_to_assign, "avail": avail}
            )
        sale_avail = svc.sol_qty_available_for_margin(
            self.sale_line_id,
            invoice_moves=self.wizard_id.customer_invoice_ids or None,
        )
        if float_compare(self.qty_to_assign, sale_avail, precision_digits=4) > 0:
            raise UserError(
                _(
                    "No se puede asignar %(qty)s: disponible en venta/factura %(avail)s."
                )
                % {"qty": self.qty_to_assign, "avail": sale_avail}
            )
