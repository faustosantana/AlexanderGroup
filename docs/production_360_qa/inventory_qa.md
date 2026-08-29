# Inventario QA

Almacenes por empresa ya existían (DOR/PIN/…). Producto storable `DX-TEST-STK`.

## Recepción parcial DOR

PO qty 10 → `DOR/IN/00006` done (6) + `DOR/IN/00007` assigned (backorder 4). PASS.

## Entrega parcial DOR

SO qty 10 → `DOR/OUT/00006` done + `DOR/OUT/00007` confirmed (pendiente). PASS.

Entregas completas de las cotizaciones 6/6: `*/OUT/0000x` done.
