# 05 — Productos y servicios

Baseline de apertura (no se reimportó, no se fusionó):

```
PRODUCTS_CREATED = 152
PRODUCTS_REUSED = 5
PRODUCT_DUPLICATES_CREATED = 0
```

Ventana create_date 2026-09-04..2026-09-06 en prod: 152 productos.

| FIELD | OBSERVED |
|---|---|
| sale_ok | 152 |
| purchase_ok | 0 |
| type consu | 133 |
| type service | 19 |

`purchase_ok = 0` se deja: son líneas de facturas históricas. Activarlos masivamente rompería la semántica de “solo venta histórica”. No se cambiaron nombres.

Duplicados semánticos: no se ejecutó fusión. `PRODUCT_DUPLICATES = 0` (exactos del import). Clustering de nombres = NOT_RUN.

Company ownership: productos de apertura siguen el diseño multi-company del import (no se tocó).

QA products `DXQA*` en prod: 0 en `product.product` por nombre/código DXQA. Existe `[DX-TEST-STK] DX TEST PRODUCTO INVENTARIABLE — NO FISCAL REAL` (stock, ver 06).
