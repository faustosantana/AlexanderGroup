# Fiscal QA — motor Justech NCF en DEV

Motor real: `justech_l10n_do_ncf` 19.0.2.31.0 + `l10n_do_accounting`.  
`l10n_latam_invoice_document`: no instalado. e-CF / QR / sello: **no configurados** (no inventados).

## Regla

El NCF sale de `justech.do.ncf.assignment.service` → `justech.do.ncf.range.consume_next`.  
No se escribió NCF a mano.

## Protección

Al auditar: **0 rangos** en DEV (nada clonado de PROD).  
Rangos QA creados con `authorization_number` `DX-QA-NOT-DGII-*` y banda `99000xxx` por empresa.

`NCF_QA_RESET_SAFE`: no se ejecutó un reset. Los rangos QA siguen activos.  
Lenguaje correcto: **QA RANGE LEFT ACTIVE**. No es un reset de NCF real.

## Resultados

| Company | Journal ventas | B01 QA | B04 QA | Estado |
| --- | --- | --- | --- | --- |
| DOR | Ventas · DOR (NCF on) | B0199000001–00005 usados | B0499000121–0123 | PASS |
| PIN | Ventas · PIN | B0199001001 | B0499001121 | PASS |
| DOM | Ventas · DOM | B0199002001 | B0499002121 | PASS |
| MAY | Ventas · MAY | B0199003001 | B0499003121 | PASS |
| REM | Ventas · REM | B0199004001 | B0499004121 | PASS |
| BLU | Ventas · BLU | B0199005001 | B0499005121 | PASS |

Tipos instalados (no inventados): B01, B02, B03, B04, B11, B12, B13, B14, B15, B16, B17.  
QA activó ventas: B01 / B02 / B03 / B04 por compañía. B02 DOR probado (`B0299000081`). B15/B16/gobierno: NOT_TESTED.

## Bordes

| Caso | Resultado |
| --- | --- |
| Rango vencido (`date_to` pasado) | `action_activate` bloquea. PASS |
| Rango agotado (segundo B03 aislado) | `consume_next` no aceptó el rango extra. NOT_TESTED de punta a punta. El motor sí lanza UserError si `next > end` o estado ≠ active |
| Concurrencia | Motor: `pg_advisory_xact_lock(company_id, doc_code)`. NOT_TESTED en dos sesiones simultáneas |
| Rollback post-asignación | Consume y post están en la misma transacción; un rollback de QA restauró NCF no confirmados. Documentado, no es reset DGII |
| NC | Flujo `account.move.reversal` + motor B04. Exige `assert_can_recover_accounting_document` |
| USD | NOT_TESTED — `res.currency.rate` vacío |

## Carga de rangos de producción (NO ejecutar aún)

1. Autorización escrita del rango DGII.
2. Backup.
3. Crear `justech.do.ncf.range` por empresa / tipo / diario.
4. `sequence_start` / `sequence_end` / `next_sequence` / `date_to` reales.
5. Activar. Smoke de una factura de prueba **solo si el rango es el autorizado de PROD**.
6. Nunca reutilizar un número ya emitido.
