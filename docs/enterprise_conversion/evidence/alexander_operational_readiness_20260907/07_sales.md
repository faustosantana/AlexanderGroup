# 07 — Ventas (staging, no prod)

Tag: `DXQA-OPREADY-20260907`. Facturas de venta dejadas en **draft**. `NCF_CONSUMED = 0`. `MAIL_SENT = 0`.

| COMPANY | SO | STATE | DRAFT INVOICE | NCF | SALE_OK |
|---|---|---|---|---|---|
| BLUE ELITE | BLU/SO/00029 | sale | 1821 draft | none | YES |
| PIÑARIA | PIN/SO/00029 | sale | 1822 draft | none | YES |
| DOMINION | DOM/SO/00029 | sale | 1823 draft | none | YES |
| DORALEX | DOR/SO/00041 | sale | 1824 draft | none | YES |
| EL MAYUMA | MAY/SO/00029 | sale | 1825 draft | none | YES |
| REMPART | REM/SO/00029 | sale | 1826 draft | none | YES |

NCF activos staging antes/después: 54 / 152 / 111 / 111 sin cambio.

Flujo servicios: cliente → cotización/SO confirmada → factura draft. No se posteó (evitar B15/B01 productivos).

Prod: no se creó SO ni factura real.
