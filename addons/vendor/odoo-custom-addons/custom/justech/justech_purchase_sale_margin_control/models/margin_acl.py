# -*- coding: utf-8 -*-
"""ACL isolation helpers — technical Margin access vs standard Odoo flows.

Standard documents (invoice / SO / PO) must remain operable for users who
only have Accounting / Sales / Purchase rights. Margin ACLs still gate the
Costos y Márgenes app, MTX UI, and managerial actions.

``sudo()`` is allowed ONLY on Margin-owned models for internal hooks and
parent-document computes. Never elevate ``account.move`` / ``sale.order`` /
``purchase.order`` themselves.
"""
from __future__ import annotations

from odoo.exceptions import AccessError, UserError
from odoo.tools.translate import _

MARGIN_GROUP_XMLIDS = (
    "justech_purchase_sale_margin_control.group_margin_readonly",
    "justech_purchase_sale_margin_control.group_margin_auditor",
    "justech_purchase_sale_margin_control.group_margin_sales",
    "justech_purchase_sale_margin_control.group_margin_purchase",
    "justech_purchase_sale_margin_control.group_margin_finance",
    "justech_purchase_sale_margin_control.group_margin_admin",
)

# Users allowed to launch Gestionar compras / relate costs for authorized docs.
HUB_OPERATOR_XMLIDS = (
    "justech_purchase_sale_margin_control.group_margin_sales",
    "justech_purchase_sale_margin_control.group_margin_purchase",
    "justech_purchase_sale_margin_control.group_margin_finance",
    "justech_purchase_sale_margin_control.group_margin_admin",
    "justech_purchase_sale_margin_control.group_margin_sec_ops_manage",
    "justech_purchase_sale_margin_control.group_margin_sec_margins_manage",
)


def user_has_margin_access(env):
    """True if the real user belongs to any Costos y Márgenes group."""
    user = env.user
    return any(user.has_group(xmlid) for xmlid in MARGIN_GROUP_XMLIDS)


def user_is_hub_operator(env):
    """True if user may open Gestionar compras for an authorized sale."""
    user = env.user
    if user.has_group("base.group_system"):
        return True
    return any(user.has_group(xmlid) for xmlid in HUB_OPERATOR_XMLIDS)


def margin_transaction(env):
    """Technical sudo access to MTX for parent-document hooks/computes."""
    return env["purchase.sale.margin.transaction"].sudo()


def margin_transaction_line(env):
    return env["purchase.sale.margin.transaction.line"].sudo()


def margin_cost_link(env):
    return env["purchase.sale.cost.link"].sudo()


def margin_cost_allocation(env):
    return env["purchase.sale.cost.allocation"].sudo()


def margin_payable_auxiliary(env):
    return env["purchase.sale.payable.auxiliary"].sudo()


def margin_snapshot(env):
    """Technical elevate for snapshot writes from Calcular margen (service)."""
    return env["purchase.sale.margin.snapshot"].sudo()


def _assert_company_allowed(env, company):
    if company and company.id not in env.user.company_ids.ids:
        raise UserError(
            _("No puedes gestionar costos de una compañía a la que no perteneces.")
        )


def _assert_doc_readable(record, label):
    """Raise functional UserError if the real user cannot read the document."""
    if not record:
        return
    record.ensure_one()
    try:
        record.check_access("read")
    except AccessError as err:
        raise UserError(
            _("No tienes permiso para gestionar costos de esta operación.")
        ) from err
    _assert_company_allowed(record.env, record.company_id)


def _user_can_read(record):
    if not record:
        return False
    try:
        record.check_access("read")
        return True
    except AccessError:
        return False


def user_can_read_customer_invoices(env):
    """True when the real user may read posted customer invoices (optional wizard field)."""
    Move = env["account.move"]
    try:
        Move.check_access("read")
        Move.search(
            [("move_type", "in", ("out_invoice", "out_refund")), ("state", "=", "posted")],
            limit=1,
        )
        return True
    except AccessError:
        return False


def assert_hub_open_authorized(env, sale_order=None, customer_invoice=None, transaction=None):
    """Validate hub launch before showing Gestionar compras.

    Hub operators may open when they can read the sale/invoice, or (ops/margins
    manage) an existing MTX for the same company. Never opens cross-company.
    """
    if not user_is_hub_operator(env) and not env.su:
        raise UserError(
            _("No tienes permiso para modificar costos de esta operación.")
        )

    so = sale_order[:1] if sale_order else env["sale.order"]
    inv = customer_invoice[:1] if customer_invoice else env["account.move"]
    tx = transaction[:1] if transaction else env["purchase.sale.margin.transaction"]

    company = False
    if so:
        company = so.sudo().company_id
    if not company and inv:
        company = inv.sudo().company_id
    if not company and tx:
        company = margin_transaction(env).browse(tx.id).company_id
    _assert_company_allowed(env, company)

    so_co = so.sudo().company_id if so else False
    inv_co = inv.sudo().company_id if inv else False
    if so and inv and so_co and inv_co and so_co != inv_co:
        raise UserError(
            _("La factura y la venta pertenecen a compañías distintas.")
        )

    if _user_can_read(so) or _user_can_read(inv):
        return True

    # Hub operators with an existing same-company MTX may open without Sales ACL
    # (Márgenes / Operaciones / Finanzas working from the operación).
    if tx and user_is_hub_operator(env):
        tx_s = margin_transaction(env).browse(tx.id)
        if tx_s.exists() and (
            not company or tx_s.company_id.id == company.id
        ):
            return True

    raise UserError(
        _("No tienes permiso para gestionar costos de esta operación.")
    )


def ensure_canonical_mtx_for_authorized_docs(env, sale_order=None, customer_invoice=None, vals=None):
    """Find or create the canonical MTX for Gestionar compras.

    Privilege elevation is limited to MTX create/reuse on the Margin model
    after validating the user can read the source sale/invoice.

    Does NOT sudo the hub wizard, sale.order, purchase.order, or allocations.
    """
    so = sale_order[:1] if sale_order else env["sale.order"]
    inv = customer_invoice[:1] if customer_invoice else env["account.move"]
    if not so and not inv:
        raise UserError(_("No hay venta/factura para gestionar costos."))

    if not user_is_hub_operator(env) and not env.su:
        raise UserError(
            _("No tienes permiso para modificar costos de esta operación.")
        )

    # Creating/locating MTX requires real read on the source document.
    _assert_doc_readable(so, "venta")
    if inv:
        _assert_doc_readable(inv, "factura")
        if so and inv.company_id and so.company_id and inv.company_id != so.company_id:
            raise UserError(
                _("La factura y la venta pertenecen a compañías distintas.")
            )

    # Technical find/create only — never elevate the caller's document models.
    Tx = margin_transaction(env)
    tx = Tx.find_or_create_canonical_transaction(
        sale_order=so or None,
        customer_invoice=inv or None,
        vals=vals,
    )
    # Return in the caller env so subsequent ACL still applies to the user.
    return env["purchase.sale.margin.transaction"].browse(tx.id)


def functional_access_denied(exc=None):
    """User-facing message without technical model names."""
    return UserError(
        _("No tienes permiso para modificar costos de esta operación.")
    )


def assert_po_link_authorized(
    env, purchase_order, sale_order, customer, customer_invoice=None
):
    """Validate Vincular a venta — hub operator + PO write; SO company-safe.

    Purchase/finance hub operators may link PO→SO without Sales ACL. The sale is
    validated for existence + same company via sudo; never grant admin rights.
    """
    if not user_is_hub_operator(env) and not env.su:
        raise UserError(_("No tienes permiso para vincular compras con ventas."))
    po = purchase_order[:1] if purchase_order else env["purchase.order"]
    so = sale_order[:1] if sale_order else env["sale.order"]
    if not po or not so:
        raise UserError(_("Faltan la orden de compra o la venta."))
    _assert_doc_readable(po, "orden de compra")
    try:
        po.check_access("write")
    except AccessError as err:
        raise UserError(
            _("No tienes permiso para modificar esta orden de compra.")
        ) from err
    # Hub operators (Compras/Responsable) link from PO — do not require Sales ACL
    # on the target quotation. Validate company on sudo copy only.
    so_s = so.sudo()
    if not so_s.exists():
        raise UserError(_("La venta seleccionada no existe o no es accesible."))
    _assert_company_allowed(env, so_s.company_id)
    if po.company_id != so_s.company_id:
        raise UserError(
            _("La orden de compra y la venta deben ser de la misma compañía.")
        )
    if po.state == "cancel":
        raise UserError(_("No se puede vincular una orden de compra cancelada."))
    if so_s.state == "cancel":
        raise UserError(_("No se puede vincular con una venta cancelada."))
    from odoo.addons.justech_purchase_sale_margin_control.services.line_allocation_service import (
        LineAllocationService,
    )

    inv = customer_invoice if customer_invoice else env["account.move"]
    LineAllocationService(env).assert_sale_docs_match_customer(
        po.company_id, customer, so_s, inv
    )


def execute_po_to_sale_link(
    env,
    *,
    purchase_order,
    sale_order,
    customer,
    allocation_rows,
    customer_invoice=None,
    transaction_vals=None,
):
    """Persist PO↔SO link with minimal sudo on Margin-owned models only.

    Purchase users (group_margin_purchase) have read-only MTX ACL; this helper
    validates PO/SO access then elevates find/create/write on MTX + MTX lines
    exclusively — same pattern as Gestionar compras hub.
    """
    from odoo import fields

    assert_po_link_authorized(
        env, purchase_order, sale_order, customer, customer_invoice=customer_invoice
    )
    po = purchase_order
    so = sale_order
    supplier = po.partner_id
    salesperson = so.user_id
    inv = customer_invoice if customer_invoice else env["account.move"]

    vals = dict(transaction_vals or {})
    vals.update(
        {
            "company_id": po.company_id.id,
            "transaction_type": vals.get("transaction_type") or "resale",
            "transaction_date": vals.get("transaction_date")
            or fields.Date.context_today(po),
            "customer_id": customer.id,
            "supplier_ids": [(4, supplier.id)] if supplier else False,
            "sale_order_ids": [(4, so.id)],
            "purchase_order_ids": [(4, po.id)],
            "salesperson_id": salesperson.id if salesperson else False,
            "purchase_responsible_id": env.user.id,
            "source": "manual",
            "state": "draft",
        }
    )
    if inv:
        vals.setdefault("customer_invoice_ids", [(4, inv.id)])

    Tx = margin_transaction(env)
    tx = Tx.with_context(skip_line_sync=True).find_or_create_canonical_transaction(
        sale_order=so,
        customer_invoice=inv or None,
        vals=vals,
    )
    write_vals = {
        "supplier_ids": [(4, supplier.id)] if supplier else False,
        "purchase_order_ids": [(4, po.id)],
        "sale_order_ids": [(4, so.id)],
        "purchase_responsible_id": env.user.id,
    }
    if salesperson and not tx.salesperson_id:
        write_vals["salesperson_id"] = salesperson.id
    if inv:
        write_vals["customer_invoice_ids"] = [(4, inv.id)]
    tx.with_context(skip_line_sync=True).write(write_vals)

    from odoo.addons.justech_purchase_sale_margin_control.services.line_allocation_service import (
        LineAllocationService,
    )

    elevated_env = env(
        context=dict(
            env.context,
            margin_hub_mtx_elevate=True,
            margin_allow_cross_product_link=True,
        )
    )
    svc = LineAllocationService(elevated_env)
    svc.apply_allocations_to_transaction(tx, allocation_rows, replace=False)
    tx.with_context(
        skip_line_sync=False,
        margin_hub_mtx_elevate=True,
        margin_skip_unsafe_po_cost=True,
    )._sync_lines_from_documents()

    for row in allocation_rows:
        pol = row["purchase_line"]
        sol = row["sale_line"]
        if pol and sol and not pol.sale_line_id:
            pol.with_context(skip_margin_live_cost_refresh=True).write(
                {"sale_line_id": sol.id}
            )

    if hasattr(svc, "confirm_unequivocal_cost_relations"):
        svc.confirm_unequivocal_cost_relations(tx)

    return env["purchase.sale.margin.transaction"].browse(tx.id)


def cache_set_m2m(record, field_name, ids):
    """Set computed M2M cache without comodel ACL checks (parent stays non-sudo)."""
    field = record._fields[field_name]
    record.env.cache.set(record, field, tuple(ids or ()))


def cache_set_m2o(record, field_name, res_id):
    """Set computed M2O cache without comodel ACL checks."""
    field = record._fields[field_name]
    record.env.cache.set(record, field, res_id or None)


def cache_set_m2m_records(record, field_name, records):
    cache_set_m2m(record, field_name, records.ids if records else ())
