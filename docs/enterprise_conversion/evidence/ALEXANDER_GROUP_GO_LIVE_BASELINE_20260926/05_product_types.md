# 05 — Product types (Odoo 19)

PRODUCT_TYPE_FIELDS = `type` (selection consu/Goods, service/Service, combo/Combo), `is_storable` (Track Inventory), plus `sale_ok`, `purchase_ok`, `tracking`.

GOODS_IMPLEMENTATION = `type='consu'` (Goods). Inventory tracking is **not** the old `product` type; it is `is_storable=True`. This catalog keeps goods as `is_storable=False` unless a DX test fixture.

SERVICE_IMPLEMENTATION = `type='service'`. `is_storable` ignored/False.

Dry-run: `PRODUCT_TYPE_FINAL_AUDIT.csv` (1750 rows).

- PHYSICAL_AS_SERVICE_FOUND = 1 (archived 138 grava duplicate) — KEEP_ARCHIVED, not reactivated
- SERVICE_AS_PHYSICAL_FOUND = 1 (id 1613 `Servicios profesionales` consu, used on 1 SO + 1 AML, created 2026-09-16). Canonical 168 already service 0.00. Not rewritten (historical document present).
- WRITABLE HIGH/DET this closeout that were **not** applied: 1641 BARRENA purchase_ok=False (1 SO, possible real reason); DX-TEST flags (fixtures). Rule: no change without a concrete case.
- AMBIGUOUS / MANUAL_REVIEW: 167 opening B13 placeholder; DX-PROD-SMOKE SERV 8/11; DX-TEST-SVC
- Piñaria foods/meats: all consu
- Product 168 unchanged
- Product 21 already consu (fixed in prior product-type audit)
- No stock/quants/moves/valuation created
- No product-type writes in this closeout
