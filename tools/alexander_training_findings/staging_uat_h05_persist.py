# Persist lot+serial flow on company 8. Never Prod.
assert env.cr.dbname == "doralex_ent_staging"
e = env(context=dict(env.context, allowed_company_ids=[8], justech_approval_skip=True, mail_notrack=True, tracking_disable=True))
tax = e["account.tax"].search([("company_id", "=", 8), ("type_tax_use", "=", "sale"), ("amount", "=", 18), ("name", "ilike", "ITBIS")], limit=1)
ptn = e["res.partner"].search([("name", "=", "DXUAT TEST ITBIS16")], limit=1)
if not ptn:
    ptn = e["res.partner"].create({"name": "DXUAT TEST ITBIS16", "company_id": 8, "customer_rank": 1, "country_id": env.ref("base.do").id})
wh = e["stock.warehouse"].search([("company_id", "=", 8)], limit=1)
itype = wh.in_type_id


def flow(code, tracking, lot_name, qty_in, qty_out):
    prod = e["product.product"].search([("default_code", "=", code)], limit=1)
    vals = {"name": code, "default_code": code, "type": "consu", "is_storable": True, "tracking": tracking, "company_id": 8, "list_price": 100, "taxes_id": [(6, 0, tax.ids)]}
    prod = prod or e["product.product"].create(vals)
    prod.write({"tracking": tracking, "is_storable": True})
    lot = e["stock.lot"].search([("name", "=", lot_name), ("product_id", "=", prod.id)], limit=1) or e["stock.lot"].create({"name": lot_name, "product_id": prod.id, "company_id": 8})
    pin = e["stock.picking"].create({
        "picking_type_id": itype.id,
        "location_id": itype.default_location_src_id.id,
        "location_dest_id": itype.default_location_dest_id.id,
        "company_id": 8,
        "move_ids": [(0, 0, {"product_id": prod.id, "product_uom_qty": qty_in, "product_uom": prod.uom_id.id, "location_id": itype.default_location_src_id.id, "location_dest_id": itype.default_location_dest_id.id, "company_id": 8, "description_picking": prod.display_name})],
    })
    pin.action_confirm(); pin.action_assign()
    mv = pin.move_ids[0]
    if mv.move_line_ids:
        mv.move_line_ids[0].write({"lot_id": lot.id, "quantity": qty_in})
    else:
        e["stock.move.line"].create({"picking_id": pin.id, "move_id": mv.id, "product_id": prod.id, "product_uom_id": prod.uom_id.id, "quantity": qty_in, "lot_id": lot.id, "location_id": itype.default_location_src_id.id, "location_dest_id": itype.default_location_dest_id.id, "company_id": 8})
    pin.button_validate()
    so = e["sale.order"].create({"partner_id": ptn.id, "company_id": 8, "order_line": [(0, 0, {"product_id": prod.id, "product_uom_qty": qty_out, "price_unit": 100, "tax_ids": [(6, 0, tax.ids)]})]})
    so.action_confirm()
    pout = so.picking_ids[:1]
    pout.action_assign()
    for mv in pout.move_ids:
        if mv.move_line_ids:
            mv.move_line_ids.write({"lot_id": lot.id, "quantity": qty_out})
        else:
            e["stock.move.line"].create({"picking_id": pout.id, "move_id": mv.id, "product_id": prod.id, "product_uom_id": prod.uom_id.id, "quantity": qty_out, "lot_id": lot.id, "location_id": mv.location_id.id, "location_dest_id": mv.location_dest_id.id, "company_id": 8})
    pout.button_validate()
    return pin.name, pin.state, pout.name, pout.state, so.name, lot.name

print("LOT", flow("DXUAT-LOT-P", "lot", "DXUAT-LOT-P1", 2, 1))
print("SER", flow("DXUAT-SER-P", "serial", "DXUAT-SER-P1", 1, 1))
env.cr.commit()
print("H05_COMMITTED")
