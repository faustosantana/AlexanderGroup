# ruff: noqa
"""Read-only dump of catalog sale prices + commercial history. No writes."""

import json
import os
from collections import defaultdict

OUT = os.environ.get("PRODUCT_PRICE_DUMP", "/tmp/product_price_dump.json")
ctx = {
    "allowed_company_ids": env["res.company"].sudo().search([]).ids,
    "active_test": False,
}
T = env["product.template"].sudo().with_context(**ctx)
recs = T.search([("name", "not ilike", "DXQA"), ("name", "not ilike", "DX TEST")])

products = []
variant_ids = []
for t in recs:
    vid = t.product_variant_id.id if t.product_variant_id else None
    if vid:
        variant_ids.append(vid)
    if t.company_id and t.company_id.currency_id:
        currency = t.company_id.currency_id.name
    else:
        dop = env["res.currency"].sudo().search([("name", "=", "DOP")], limit=1)
        currency = dop.name if dop else "DOP"
    products.append(
        {
            "product_tmpl_id": t.id,
            "product_id": vid,
            "name": t.name or "",
            "active": bool(t.active),
            "company_id": t.company_id.id or False,
            "company": t.company_id.name if t.company_id else "",
            "type": t.type,
            "is_storable": bool(t.is_storable) if "is_storable" in t._fields else False,
            "sale_ok": bool(t.sale_ok),
            "purchase_ok": bool(t.purchase_ok),
            "list_price": float(t.list_price or 0),
            "standard_price": float(t.standard_price or 0),
            "currency": currency,
            "uom": t.uom_id.name if t.uom_id else "",
            "category": t.categ_id.name if t.categ_id else "",
            "write_date": str(t.write_date or ""),
        }
    )

# Latest commercial lines (untaxed price_unit). Exclude sections/notes.
def _collect(model, domain, extra_fields):
    if model not in env:
        return {}
    Rec = env[model].sudo()
    domain = list(domain) + [("product_id", "in", variant_ids)]
    if "display_type" in env[model]._fields:
        # Odoo 19 invoice/sale product lines use display_type='product'.
        domain.append(("display_type", "in", [False, "", "product"]))
    fields = ["product_id", "price_unit", "discount", "price_subtotal", "create_date"] + extra_fields
    # chunk to stay safe
    out = defaultdict(list)
    recs = Rec.search(domain)
    for rec in recs:
        pid = rec.product_id.id
        row = {
            "price_unit": float(rec.price_unit or 0),
            "discount": float(rec.discount or 0) if "discount" in rec._fields else 0.0,
            "price_subtotal": float(rec.price_subtotal or 0) if "price_subtotal" in rec._fields else 0.0,
            "create_date": str(rec.create_date or ""),
        }
        for f in extra_fields:
            val = rec[f]
            if hasattr(val, "id") and not isinstance(val, bool):
                row[f] = val.id
                row[f + "_name"] = val.display_name
            else:
                row[f] = val if not hasattr(val, "strftime") else str(val)
        out[pid].append(row)
    return out


so_lines = _collect(
    "sale.order.line",
    [("order_id.state", "not in", ["cancel"])],
    ["order_id"],
)
# split quotation vs confirmed using order state
SO = env["sale.order"].sudo()
so_state = {}
if so_lines:
    so_ids = {row["order_id"] for rows in so_lines.values() for row in rows if row.get("order_id")}
    for so in SO.browse(list(so_ids)):
        so_state[so.id] = {
            "state": so.state,
            "date": str(so.date_order or so.create_date or ""),
            "name": so.name,
        }

inv_lines = _collect(
    "account.move.line",
    [
        ("move_id.move_type", "=", "out_invoice"),
        ("move_id.state", "!=", "cancel"),
    ],
    ["move_id"],
)
Move = env["account.move"].sudo()
inv_meta = {}
if inv_lines:
    move_ids = {row["move_id"] for rows in inv_lines.values() for row in rows if row.get("move_id")}
    for mv in Move.browse(list(move_ids)):
        inv_meta[mv.id] = {
            "state": mv.state,
            "date": str(mv.invoice_date or mv.date or mv.create_date or ""),
            "name": mv.name,
        }

# Pricelist items touching specific products
pl_items = defaultdict(list)
if "product.pricelist.item" in env:
    for it in env["product.pricelist.item"].sudo().search(
        ["|", ("product_tmpl_id", "!=", False), ("product_id", "!=", False)]
    ):
        key = it.product_id.id or False
        tmpl = it.product_tmpl_id.id or False
        rec = {
            "pricelist": it.pricelist_id.name,
            "applied_on": it.applied_on,
            "compute_price": it.compute_price,
            "fixed_price": float(it.fixed_price or 0) if "fixed_price" in it._fields else None,
        }
        if key:
            pl_items[("p", key)].append(rec)
        if tmpl:
            pl_items[("t", tmpl)].append(rec)

for row in products:
    pid = row["product_id"]
    quotes = []
    sales = []
    for ln in so_lines.get(pid, []):
        meta = so_state.get(ln.get("order_id"), {})
        item = {
            "price_unit": ln["price_unit"],
            "discount": ln["discount"],
            "price_subtotal": ln["price_subtotal"],
            "date": meta.get("date") or ln["create_date"],
            "name": meta.get("name"),
            "state": meta.get("state"),
        }
        if meta.get("state") in {"sale", "done"}:
            sales.append(item)
        else:
            quotes.append(item)
    invoices = []
    for ln in inv_lines.get(pid, []):
        meta = inv_meta.get(ln.get("move_id"), {})
        invoices.append(
            {
                "price_unit": ln["price_unit"],
                "discount": ln["discount"],
                "price_subtotal": ln["price_subtotal"],
                "date": meta.get("date") or ln["create_date"],
                "name": meta.get("name"),
                "state": meta.get("state"),
            }
        )

    def _latest(items):
        if not items:
            return None
        return sorted(items, key=lambda x: x.get("date") or "", reverse=True)[0]

    last_q = _latest(quotes)
    last_s = _latest(sales)
    last_i = _latest(invoices)
    hist_prices = [
        x["price_unit"]
        for x in (quotes + sales + invoices)
        if x.get("price_unit") not in (None, "")
    ]
    row.update(
        {
            "quotation_count": len(quotes),
            "sale_count": len(sales),
            "invoice_count": len(invoices),
            "last_quotation_price": last_q["price_unit"] if last_q else None,
            "last_quotation_date": last_q["date"] if last_q else "",
            "last_quotation_discount": last_q["discount"] if last_q else None,
            "last_sale_order_price": last_s["price_unit"] if last_s else None,
            "last_sale_order_date": last_s["date"] if last_s else "",
            "last_invoice_price": last_i["price_unit"] if last_i else None,
            "last_invoice_date": last_i["date"] if last_i else "",
            "recent_avg_price": (
                round(sum(hist_prices) / len(hist_prices), 2) if hist_prices else None
            ),
            "pricelist_items": pl_items.get(("p", pid), []) + pl_items.get(("t", row["product_tmpl_id"]), []),
        }
    )

payload = {
    "DATABASE": env.cr.dbname,
    "PRODUCTS_AUDITED": len(products),
    "POSTED_INVOICES": env["account.move"]
    .sudo()
    .search_count([("move_type", "=", "out_invoice"), ("state", "=", "posted")]),
    "products": products,
}
with open(OUT, "w", encoding="utf-8") as fh:
    json.dump(payload, fh, ensure_ascii=False, indent=2)
print(
    json.dumps(
        {
            "wrote": OUT,
            "PRODUCTS_AUDITED": len(products),
            "with_quote": sum(1 for p in products if p["quotation_count"]),
            "with_sale": sum(1 for p in products if p["sale_count"]),
            "with_invoice": sum(1 for p in products if p["invoice_count"]),
            "zero_price": sum(1 for p in products if abs(p["list_price"]) < 0.005),
        },
        indent=2,
    )
)
