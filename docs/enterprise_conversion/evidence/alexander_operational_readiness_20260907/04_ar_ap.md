# 04 — CxC / CxP

## Apertura (baseline, no tocada)

```
CUSTOMER_INVOICES = 27
PROD_AR_TOTAL = 27240211.80
PROD_AR_DIFFERENCE = 0.00
AR_LEDGER_DIFFERENCE = 0.00
ARTIFICIAL_AP_RECORDS = 0
EXCEL_CXP_ROWS = 0
VENDOR_BILLS_OPENING = 0
B1500000150 = 294754.56
REMPART B1500000110 = 267250.52
B1300000016 = 44800.00 MISSING_PDF
```

Por empresa (residual lote):

| COMPANY | OPENING_AR |
|---|---|
| INVERSIONES DORALEX,S.RL. | 16491966.46 |
| INVERSIONES EL MAYUMA, S.R.L. | 2668855.73 |
| REMPART GROUP S.R.L. | 8079389.61 |
| PIÑARIA / DOMINION / BLUE ELITE | 0.00 |

Pagos históricos de apertura (sin inventar Banreservas): 2 aplicaciones vía 11030205 (B0100000035 y Mayuma B1500000109). No se regeneraron.

## B1300000016

Identificación ya existente en `narration`:

`SOURCE_DOCUMENT_STATUS=MISSING_PDF`

No se inventó PDF. No se reconstruyó original. No bloquea operación.

## Aged / partner ledger

El lote de apertura cuadra. El Aged operativo de prod **también ve** residual QA (no es del lote):

- 6 notas B04 `B0499110xxx` residual 2159.40 c/u
- varias INV `B019910xxxx` residual 106.20 / 472.00
- `QA residual invoices+refunds = 16000.80`

No se modificaron facturas históricas para “cuadrar” reportes. Limpieza QA requiere autorización (anular ahora implicaría 608 / impacto contable).

## CxP operativa

Flujo de proveedor listo (staging E2E: 6 OC confirmadas). Sin facturas proveedor de apertura. Bills QA `BILL/2026/08/0001` ×6 residual 0.00 — no son CxP de Alexander; no se borraron a ciegas.
