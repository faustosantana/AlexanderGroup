# 04 — Products

See scorecard and `PRODUCT_TYPE_FINAL_AUDIT.csv`.

- product.template: 1750 total / 1749 active / 1 archived
- product.product: 1750 total / 1744 active / 6 archived
- Shared active templates: 1736
- Piñaria-only: 11 (foods/meats, type=consu)
- Shared active excluding DX-named rows: 1733
- Catalog active excluding DX: 1746
- DX-named templates: 3+
- Goods (consu) active shared: 1715
- Services active shared: 21 + 2 company-scoped smoke services
- Duplicates active: product 1613 `Servicios profesionales` (consu, list_price 1.00) besides canonical 168
- Duplicates archived: product 138 `(AGREGADO GRUESO) GRAVA 3/4`
- Canonical grava: product 21 type=consu sale_ok/purchase_ok/active True, list_price 2054.91
- Servicios profesionales 168: service, 0.00, sale_ok True

## EXPLAIN_1601_VS_1736

1601 was the **product-master import closeout** count (2026-09-07): 1590 shared + 11 Piñaria.

1736 is the **current active shared template** count (`company_id IS NULL AND active=True`). It includes system rows (Event Registration, Field Service, Service on Timesheets), DX/smoke fixtures, and products created after the master (phase 2 and later).

Do not change data for this difference.
