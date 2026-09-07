# 02 — Contabilidad

Entorno: prod `doralex_prod`. No se rehizo el plan de cuentas. No se duplicaron cuentas.

| COMPANY | ACCOUNTING_READY | MISSING_CONFIGURATION | RISK |
|---|---|---|---|
| INVERSIONES DORALEX,S.RL. | PASS | saldo banco no posteado (banca, no CoA); caja 0 diarios | LOW |
| COMERCIALIZADORA DE ALIMENTOS PIÑARIA, S.R.L. | PASS | igual | LOW |
| DOMINION BUSINESS,S.R.L. | PASS | igual | LOW |
| INVERSIONES EL MAYUMA, S.R.L. | PASS | igual | LOW |
| REMPART GROUP S.R.L. | PASS | igual | LOW |
| BLUE ELITE, S.R.L. | PASS | igual | LOW |

Hallazgos medidos:

- Las 6 tienen diario de ventas y de compras propios (`Ventas · XXX` / `Compras · XXX`).
- ITBIS 18% venta presente en las 6 (`18% ITBIS`, `Restaurant`).
- Impuestos de compra l10n_do presentes (ITBIS, servicios, importación, retenciones estándar del localization).
- No hay asientos de apertura bancaria.
- `UNBALANCED_IMPORTED_MOVES = 0` (lote `ALEXANDER_OPENING_2026-09-04`).
- Compañía 1: 0 movimientos; no se usó para operar.
- Localización fiscal DO ya instalada (no se reinstaló).
- Cuentas receivable/payable existen (el probe de `code` devolvió False por campo company-dependent; no se interpreta como CoA vacío).

No se inventaron cuentas especiales ni retenciones extra.
