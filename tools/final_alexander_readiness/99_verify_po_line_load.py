# -*- coding: utf-8 -*-
"""Staging: selecting a PO via write() must load lines (OWL path)."""
company = env["res.company"].browse(11)
e = env(context=dict(env.context, allowed_company_ids=[company.id]))
so = e["sale.order"].browse(151)
po1 = e["purchase.order"].search([("name", "=", "DOR/OC/00035")], limit=1)
po2 = e["purchase.order"].search([("name", "=", "DOR/OC/00036")], limit=1)
print("SO", so.name, so.state, so.company_id.id)
print("PO1", po1.name, len(po1.order_line), "PO2", po2.name, len(po2.order_line))
hub = (
    e["purchase.sale.manage.purchases.wizard"]
    .with_context(
        active_model="sale.order",
        active_id=so.id,
        active_ids=[so.id],
        default_sale_order_ids=[(6, 0, [so.id])],
        default_company_id=company.id,
    )
    .create({})
)
print(
    "HUB_LINES",
    [
        (l.product_name, l.sold_qty, l.pending_qty, l.selected)
        for l in hub.line_ids
    ],
)
pending = hub.line_ids.filtered(lambda l: l.pending_qty > 0)
if pending:
    pending[0].selected = True
link = e["purchase.sale.cost.link.wizard"].create(
    {
        "hub_wizard_id": hub.id,
        "company_id": company.id,
        "mode": "po",
        "sale_line_ids": [(6, 0, pending.mapped("sale_line_id").ids)],
        "supplier_id": po1.partner_id.id,
    }
)
print("LINK_CREATED_LINES", len(link.pol_line_ids))
link.write({"purchase_order_id": po1.id})
print(
    "AFTER_PO1",
    [
        (l.product_id.display_name, l.qty_available, l.qty_needed, l.qty_to_use)
        for l in link.pol_line_ids
    ],
)
link.write({"purchase_order_id": po2.id})
print(
    "AFTER_PO2",
    [
        (l.product_id.display_name, l.qty_available, l.qty_needed, l.qty_to_use)
        for l in link.pol_line_ids
    ],
)
mod = e["ir.module.module"].search(
    [("name", "=", "justech_purchase_sale_margin_control")], limit=1
)
print("MARGIN_VERSION", mod.latest_version)
print(
    "QWEB",
    e["ir.ui.view"].search_count(
        [("key", "like", "justech_alexander%"), ("type", "=", "qweb")]
    ),
)
env.cr.rollback()
