# 06 — Inventario

Las facturas históricas no crearon stock. Correcto.

| COMPANY | WAREHOUSE | LOCATIONS (nonzero QA) | STOCK_OPENING |
|---|---|---|---|
| BLUE ELITE | Almacén Principal | BLU/Existencias qty=1 DX-TEST-STK | PENDING_BUSINESS_DATA |
| PIÑARIA | Almacén Principal | PIN/Existencias qty=1 DX-TEST-STK | PENDING_BUSINESS_DATA |
| DOMINION | Almacén Principal | DOM/Existencias qty=1 DX-TEST-STK | PENDING_BUSINESS_DATA |
| DORALEX | Almacén Principal | DOR/Existencias qty=-23 DX-TEST-STK | PENDING_BUSINESS_DATA |
| EL MAYUMA | Almacén Principal | MAY/Existencias qty=1 DX-TEST-STK | PENDING_BUSINESS_DATA |
| REMPART | Almacén Principal | REM/Existencias qty=1 DX-TEST-STK | PENDING_BUSINESS_DATA |

Excel solo entregó oficina principal. No se inventaron almacenes físicos extra ni existencias reales.

El único quant ≠0 por empresa es el producto QA `[DX-TEST-STK]`. Doralex quedó en −23 por entregas QA. No se ajustó: no es inventario de Alexander.

Operation types / receipts / deliveries: almacén técnico estándar Odoo presente. E2E de esta fase usó **servicios** (sin picking) para no tocar stock real ni NCF.

`STOCK_OPENING = PENDING_BUSINESS_DATA`
