# 09 — NCF (carga Excel 2026-09-07)

Fuente: `Plantilla_PENDIENTES_Alexander_Odoo_1e80.xlsx` hoja `02_Secuencias_NCF` (34 filas).
Instrucción Alexander: vencimiento Excel tal cual; al facturar un rango ya vencido debe salir error para validarlo.

`NCF_SAFE_ACTIVE = 25` · `NCF_EXPIRED_EXCEL = 9` · `NCF_QA_CANCELLED_RANGES = 12` · `NCF_CONSUMED = 0`

Los 9 con Excel `2024-12-31` / `2025-12-31` tienen esa `date_to` y `state=expired`. Al postear factura el error es:
`El rango NCF B01 de … está vencido (vence 2025-12-31). No se puede facturar hasta validarlo.`
`N/A` no tiene fecha: `date_to` = `2099-12-31` (siguen activos).

No se reemiten NCF ya existentes en el lote de apertura.

## 34 rangos activos (prod, company 8–13)

| COMPANY | TIPO | FROM | TO | NEXT | AUTH | EXCEL VENCE | DATE_TO ODOO |
|---|---|---|---|---|---|---|---|
| DORALEX | B01 | 52 | 87 | B0100000054 | 6005372487 | 2027-12-31 | 2027-12-31 |
| DORALEX | B02 | 1 | 10 | B0200000001 | 1002741918 | N/A | 2099-12-31 |
| DORALEX | B04 | 502 | 502 | B0400000502 | 6005472045 | N/A | 2099-12-31 |
| DORALEX | B11 | 1 | 5 | B1100000001 | 3003703072 | 2024-12-31 | 2024-12-31 expired |
| DORALEX | B13 | 11 | 17 | B1300000017 | 6005031086 | 2027-12-31 | 2027-12-31 |
| DORALEX | B15 | 141 | 160 | B1500000152 | 6005109381 | 2027-12-31 | 2027-12-31 |
| PIÑARIA | B01 | 6 | 10 | B0100000009 | 4004196168 | 2025-12-31 | 2025-12-31 expired |
| PIÑARIA | B04 | 1 | 10 | B0400000001 | 3003875941 | N/A | 2099-12-31 |
| PIÑARIA | B11 | 1 | 5 | B1100000001 | 4004017760 | 2025-12-31 | 2025-12-31 expired |
| PIÑARIA | B13 | 18 | 27 | B1300000018 | 5004579811 | 2026-12-31 | 2026-12-31 |
| PIÑARIA | B15 | 93 | 103 | B1500000093 | 6005464536 | 2028-01-01 | 2028-01-01 |
| DOMINION | B01 | 91 | 100 | B0100000094 | 4004196172 | 2025-12-31 | 2025-12-31 expired |
| DOMINION | B02 | 1 | 500 | B0200000001 | 2003411708 | N/A | 2099-12-31 |
| DOMINION | B04 | 1 | 50 | B0400000001 | 2003411709 | N/A | 2099-12-31 |
| DOMINION | B11 | 1 | 10 | B1100000001 | 4003974422 | 2025-12-31 | 2025-12-31 expired |
| DOMINION | B13 | 57 | 96 | B1300000057 | 5004440728 | 2026-12-31 | 2026-12-31 |
| DOMINION | B15 | 140 | 163 | B1500000145 | 5004909756 | 2026-12-31 | 2026-12-31 |
| EL MAYUMA | B01 | 6 | 10 | B0100000006 | 5004743980 | 2026-12-31 | 2026-12-31 |
| EL MAYUMA | B02 | 1 | 100 | B0200000001 | 3003508919 | N/A | 2099-12-31 |
| EL MAYUMA | B04 | 1 | 5 | B0400000001 | 6005472703 | N/A | 2099-12-31 |
| EL MAYUMA | B11 | 1 | 5 | B1100000001 | 4003974363 | 2025-12-31 | 2025-12-31 expired |
| EL MAYUMA | B13 | 1 | 5 | B1300000001 | 4003974364 | 2025-12-31 | 2025-12-31 expired |
| EL MAYUMA | B15 | 109 | 118 | B1500000111 | 5004942280 | 2026-12-31 | 2026-12-31 |
| REMPART | B01 | 16 | 30 | B0100000016 | 5004684660 | 2026-12-31 | 2026-12-31 |
| REMPART | B04 | 1 | 5 | B0400000001 | 6005474633 | N/A | 2099-12-31 |
| REMPART | B11 | 1 | 5 | B1100000001 | 4004004172 | 2025-12-31 | 2025-12-31 expired |
| REMPART | B13 | 6 | 12 | B1300000006 | 4004004197 | 2025-12-31 | 2025-12-31 expired |
| REMPART | B15 | 106 | 113 | B1500000111 | 5004942351 | 2027-01-03 | 2027-01-03 |
| BLUE ELITE | B01 | 1 | 15 | B0100000001 | 6005109961 | 2027-12-31 | 2027-12-31 |
| BLUE ELITE | B02 | 1 | 500 | B0200000001 | 6005109965 | N/A | 2099-12-31 |
| BLUE ELITE | B04 | 1 | 15 | B0400000001 | 6005109966 | N/A | 2099-12-31 |
| BLUE ELITE | B11 | 1 | 5 | B1100000001 | 6005109962 | 2027-12-31 | 2027-12-31 |
| BLUE ELITE | B13 | 1 | 5 | B1300000001 | 6005109963 | 2027-12-31 | 2027-12-31 |
| BLUE ELITE | B15 | 1 | 102 | B1500000102 | 6005109964 | 2027-12-31 | 2027-12-31 |

## Ajustes inevitables (Excel internamente inconsistente o NCF ya emitido)

| CASO | EXCEL | ODOO | POR QUÉ |
|---|---|---|---|
| Doralex B01 last/next | B1500000156 / B1500000157 | next B0100000054 | la planilla pegó last/next B15 en la fila B01; el rango es 52–87; histórico B01 máx. 53 |
| Doralex B15 next | B1500000151 | B1500000152 | 0151 ya existe en apertura; no se reemite |
| Doralex B13 to/next | to 15 / next vacío | to 17 / B1300000017 | 0015 last Excel + 0016 ya posteado (MISSING_PDF); sin ampliar el to el rango queda agotado |
| Blue Elite B15 to | 1–20 last 101 next 102 | to 102 / B1500000102 | Odoo no admite next > to; se honra el próximo 102 de la planilla |

QA 9910/9911: 12 rangos `cancelled`, auth `DX-TEST-NO-DGII-360`. No son DGII.

Evidencia: `op_ready_ncf_dump.json`, `op_ready_ncf_excel_compare.json`, `op_ready_ncf_expired_error.json`, `op_ready_ncf_prod_expired_invoice.json`.

Prueba prod (Piñaria B01, sin consumir NCF): posteo bloqueado con
`El rango NCF B01 de COMERCIALIZADORA DE ALIMENTOS PIÑARIA, S.R.L. está vencido (vence 2025-12-31). No se puede facturar hasta validarlo.`
`justech_alexander_base` 19.0.1.0.5.
