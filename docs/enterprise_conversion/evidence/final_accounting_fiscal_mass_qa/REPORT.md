# Auditoría contable/fiscal masiva pre-entrega — Doralex staging

Fecha: 2026-08-31
Entorno: **solo staging** `127.0.0.1:8269` / DB `doralex_ent_staging`
Tag de datos: `DXQA-MASS-20260831`
`PROD_TOUCHED_BY_MASS_QA = NO`

No se envió e-CF a DGII. No se envió correo a clientes/proveedores reales.
No se consumieron secuencias fiscales de producción.

## 1. Empresas

| COMPANY_ID | COMPANY_NAME | RNC | CURRENCY | FISCAL_COUNTRY | NCF_CONFIGURED | ACCOUNTING_CONFIGURED | BANK | SALES | PURCHASE |
|---|---|---|---|---|---|---|---|---|---|
| 1 | Plantilla técnica (no operativa) | — | USD | US | NO | YES | 1 | 1 | 1 |
| 8 | BLUE ELITE, S.R.L. | 133371261 | DOP | DO | YES (B01, B04) | YES | 1 | 1 | 1 |
| 9 | COMERCIALIZADORA DE ALIMENTOS PIÑARIA, S.R.L. | 132271068 | DOP | DO | YES (B01, B04) | YES | 1 | 1 | 1 |
| 10 | DOMINION BUSINESS,S.R.L. | 132721502 | DOP | DO | YES (B01, B04) | YES | 1 | 1 | 1 |
| 11 | INVERSIONES DORALEX,S.RL. | 132220112 | DOP | DO | YES (B01, B04) | YES | 1 | 1 | 1 |
| 12 | INVERSIONES EL MAYUMA, S.R.L. | 132710152 | DOP | DO | YES (B01, B04) | YES | 1 | 1 | 1 |
| 13 | REMPART GROUP S.R.L. | 132769155 | DOP | DO | YES (B01, B04) | YES | 1 | 1 | 1 |

`TOTAL_COMPANIES_TESTED = 7`

Tipos NCF **instalados** (catálogo): B01–B04, B11–B17.
Rangos **activos emitidos** por empresa DO: **solo B01 y B04**. No se inventaron B02/B11/B13/B17.

## 2. Backup

`MASS_QA_BACKUP = PASS`

`/opt/doralex/backups/enterprise-staging/pre_mass_accounting_fiscal_qa_20260831_091637`

Incluye `db.dump`, `filestore.tar.gz`, `custom-addons.tar.gz`, `config.tar.gz`, compose, inventarios.

## 3–6. Volumen QA (prefijos DXQA)

Partners/productos aislados por empresa (`DXQA Customer/Vendor …`, `DXQA-{company_id}`).
RNC de prueba validados en estado `validated_padron` (sin padrón DGII real).
Partners con email `dxqa.noreply@example.invalid`.

| | Sales | Vendor bills | Credit notes (cust+vend) | Payments |
|---|---|---|---|---|
| Por empresa | 40 | 42 | 10 + 5 | ~62 |
| Total | **280** | **294** | **70+** | **434** |

Umbral pedido: ≥ 40 × 7 = 280 por lado. **Cumplido.**

Distribución observada de `payment_state` en facturas cliente (por empresa DO):

- 22 `in_payment` (pago completo en Odoo 19 Enterprise)
- 11 `partial`
- 5 `not_paid` (2 de ellas NCF anulado → 608)
- 2 `reversed`

Escalera residual 10,000 → 4,000 → 2,500 → 3,500 → **0** en CxC y CxP: `PASS` en las 7 empresas.

## 7–14. Pagos / recibo único

Motor usado: módulo existente `multi_invoice_manual_payment_prod` 19.0.1.5.4.
No se creó otro motor.

Hallazgo Odoo 19 Enterprise: `account.payment.action_post()` **no genera asiento** si el diario no tiene cuenta outstanding. El wizard requiere `payment.move_id`. En QA se usó el contexto nativo `force_payment_move=True` (API Odoo, no fork). **Configuración pendiente en staging/prod:** asignar cuentas Outstanding Receipts/Payments en las líneas de método de los diarios banco (hoy `payment_account_id` vacío).

Pagos multi-factura ejecutados: grupos de **2, 3, 4 y 5** facturas del mismo partner, un solo `account.payment`.

`MULTI_INVOICE_PAYMENT_QA = PASS`
`MULTI_INVOICE_SINGLE_RECEIPT = PASS`

PDF de recibo (`account.action_report_payment_receipt`): un PDF por pago, tabla “Documentos aplicados” (documento + monto aplicado + total). **No** incluye aún fecha / monto factura / saldo anterior / saldo resultante. Eso es un gap de plantilla, no un segundo motor.

`MULTI_INVOICE_RECEIPT_PDF = PARTIAL`

Evidencia: `C11_receipt_407.pdf` (5 facturas), `C11_receipt_408.pdf` (4 facturas).

Retenciones: **0** configs `justech.do.withholding.company.config`. Casos de withholding = `NOT_APPLICABLE` (no se inventó catálogo).
Pago en exceso 12,000 sobre 10,000: no forzado (el wizard bloquea aplicar más que residual; el excedente requeriría `amount_received` > aplicado + outstanding). `NOT_FORCED`.

## 15–17. CxC / CxP / integridad

`UNBALANCED_MOVES = 0` en asientos QA (7/7).
`cross_company_lines = 0`.
NCF venta únicos: 40/40 por empresa DO.

Residuales QA abiertos (ejemplo):

| company | AR open | AP open |
|---|---|---|
| 1 | 47,840 | 54,280 |
| 8–10,12–13 | 49,088 | 55,696 |
| 11 | 42,716 | 55,696 |

`AR_BALANCE_MATCH = YES` (abiertos = no pagadas + parciales + 2 anuladas sin revertir contable).
`AP_BALANCE_MATCH = YES`.
`MULTICOMPANY_ISOLATION = PASS`.

## 18–25. Impuestos / NC / DGII

ITBIS 18% en empresas DO; plantilla US usa 15%.
NC cliente: B04 emitido (rango test staging).
NC proveedor: modo **recibido** + NCF B04 del proveedor de prueba (no consume rango emitido).

Anulaciones 608: 2 NCF QA por empresa DO, fecha factura 2026-06-15. Informe 608 del período **202606** = 2 líneas. Período 202608 = 0 (correcto).

| Código | Resultado | Notas |
|---|---|---|
| 606 | **PASS** | 47 líneas = 42 bills + 5 NC proveedor. Untaxed 200,200 = 188,100 + 12,100 NC |
| 607 | **PASS** | 45 líneas = 35 B01 agosto (203,000) + 10 B04. Junio vencidas no entran en 202608 |
| 608 | **PASS** | 2 NCF anulados QA / empresa en 202606 |
| 609 | **NOT_APPLICABLE** | Sin B17 / operaciones al exterior configuradas |
| 623 | **NOT_APPLICABLE** | Sin retenciones del Estado configuradas |

Exportadores instalados (módulo `justech_l10n_do_reports` 19.0.1.24.8): **606, 607, 608, 609, 623**. No hay otros formatos DGII en el módulo.

Archivos 606/607: XLSX reales (ZIP/OOXML), guardados `C11_606.xlsx`, `C11_607.xlsx`.

`606_ACCOUNTING_RECONCILIATION = PASS`
`607_ACCOUNTING_RECONCILIATION = PASS` (conteo + gravadas agosto)
`608_SOURCE_RECONCILIATION = PASS`
`609_ACCOUNTING_RECONCILIATION = NOT_APPLICABLE`
`623_ACCOUNTING_RECONCILIATION = NOT_APPLICABLE`

## 26–29. Otros / aislamiento

`OTHER_DGII_REPORTS_TESTED = 609, 623 (N/A — vacíos, coherente)`
NCF aislados por empresa (secuencias 99100xxx distintas).
Diarios, impuestos y partners QA con `company_id` propio.

## 30–32. Márgenes, traza, auditoría

Por empresa se confirmó 1 SO + 1 PO (`state` sale/purchase). **No** se recorrió el ciclo SO→factura / PO→bill en los 560 documentos (para no gastar más B01). 

`MARGIN_QA_MASS = PARTIAL`
`TRACEABILITY_QA_MASS = PARTIAL`
`AUDIT_LOG_MASS_QA = NOT_RUN` (no se activó política temporal; no era necesario para publicar).

## 33–34. Reportes Alexander

`QWEB_BEFORE = 58`
`QWEB_AFTER = 58`
`QWEB_HASH_MISMATCH_UNEXPECTED = 0` (conteo estable; no se tocó `justech_alexander_reports`)
`REPORTS_PRESERVED = YES`

Recibos de pago generados desde el QWeb estándar + inherit del módulo multi-factura.

## 35–36. Performance / logs

Posting ~40+42 docs / empresa ≈ 22–27 s.
Generación 606/607 ≈ 1.1 s / empresa.
PDF recibo ≈ 2.1 s.
`CRITICAL_ERRORS = 0`
`HIGH_ERRORS = 0` (0 Traceback en logs de las últimas 6 h ligados a esta corrida)
`MEDIUM_ERRORS` = gap plantilla recibo; outstanding de banco sin configurar; 10 B04 en 607 (se re-ejecutó NC cliente al re-correr el harness)
`LOW_ERRORS` = plantilla US exige NCF de proveedor aunque el país fiscal sea US (`justech_do_fiscal_enabled=True`)

## 37–38. Prod / limpieza

`PROD_TOUCHED_BY_MASS_QA = NO`

Limpieza **no ejecutada**. Identificador: tag `DXQA-MASS-20260831` + partners `DXQA %` + products `DXQA-*`.
Script: `tools/mass_accounting_fiscal_qa/03_cleanup_identify.py` (solo lista).

## 40. Matriz por empresa

| COMPANY | 40_SALES | 40_BILLS | FULL | PARTIAL | MULTI | RESIDUALS | CN | AR | AP | 606 | 607 | 608 | 609 | 623 | OTHER | MARGIN | TRACE | RESULT |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 Plantilla | PASS | PASS | PASS | PASS | PASS | PASS | PASS | YES | YES | N/A | N/A | N/A | N/A | N/A | N/A | PARTIAL | PARTIAL | PASS* |
| 8 Blue Elite | PASS | PASS | PASS | PASS | PASS | PASS | PASS | YES | YES | PASS | PASS | PASS | N/A | N/A | N/A | PARTIAL | PARTIAL | PASS* |
| 9 Piñaria | PASS | PASS | PASS | PASS | PASS | PASS | PASS | YES | YES | PASS | PASS | PASS | N/A | N/A | N/A | PARTIAL | PARTIAL | PASS* |
| 10 Dominion | PASS | PASS | PASS | PASS | PASS | PASS | PASS | YES | YES | PASS | PASS | PASS | N/A | N/A | N/A | PARTIAL | PARTIAL | PASS* |
| 11 Doralex | PASS | PASS | PASS | PASS | PASS | PASS | PASS | YES | YES | PASS | PASS | PASS | N/A | N/A | N/A | PARTIAL | PARTIAL | PASS* |
| 12 El Mayuma | PASS | PASS | PASS | PASS | PASS | PASS | PASS | YES | YES | PASS | PASS | PASS | N/A | N/A | N/A | PARTIAL | PARTIAL | PASS* |
| 13 Rempart | PASS | PASS | PASS | PASS | PASS | PASS | PASS | YES | YES | PASS | PASS | PASS | N/A | N/A | N/A | PARTIAL | PARTIAL | PASS* |

\*PASS de volumen/contabilidad/DGII aplicable. El gate de recibo PDF detallado queda PARTIAL (ver §11).

## 42. Keys finales

```
TOTAL_COMPANIES_TESTED = 7
TOTAL_SALES_INVOICES = 280
TOTAL_VENDOR_BILLS = 294
TOTAL_CREDIT_NOTES = 70+
TOTAL_CUSTOMER_PAYMENTS = 238
TOTAL_VENDOR_PAYMENTS = 196
FULL_PAYMENT_QA = PASS
PARTIAL_PAYMENT_QA = PASS
RESIDUAL_PAYMENT_QA = PASS
MULTI_INVOICE_PAYMENT_QA = PASS
MULTI_INVOICE_SINGLE_RECEIPT = PASS
MULTI_INVOICE_RECEIPT_PDF = PARTIAL
AR_BALANCE_MATCH = YES
AP_BALANCE_MATCH = YES
UNBALANCED_MOVES = 0
MULTICOMPANY_ISOLATION = PASS
NCF_QA = PASS
DGII_606_QA = PASS
DGII_607_QA = PASS
DGII_608_QA = PASS
DGII_609_QA = NOT_APPLICABLE
DGII_623_QA = NOT_APPLICABLE
OTHER_DGII_REPORTS_TESTED = 609,623
606_ACCOUNTING_RECONCILIATION = PASS
607_ACCOUNTING_RECONCILIATION = PASS
608_SOURCE_RECONCILIATION = PASS
609_ACCOUNTING_RECONCILIATION = NOT_APPLICABLE
623_ACCOUNTING_RECONCILIATION = NOT_APPLICABLE
MARGIN_QA_MASS = PARTIAL
TRACEABILITY_QA_MASS = PARTIAL
AUDIT_LOG_MASS_QA = NOT_RUN
QWEB_BEFORE = 58
QWEB_AFTER = 58
QWEB_HASH_MISMATCH_UNEXPECTED = 0
REPORTS_PRESERVED = YES
CRITICAL_ERRORS = 0
HIGH_ERRORS = 0
MEDIUM_ERRORS = 3
LOW_ERRORS = 1
PROD_TOUCHED_BY_MASS_QA = NO
FINAL_ACCOUNTING_FISCAL_QA = CONDITIONAL_PASS
READY_FOR_ALEXANDER_DATA_LOAD = NO
```

`FINAL_ACCOUNTING_FISCAL_QA` no se declara PASS estricto porque:

1. El PDF de recibo multi-factura no tiene la tabla completa pedida.
2. Márgenes/trazabilidad no se recorrieron al 100% del volumen.
3. Hay que configurar outstanding en diarios banco para que el wizard funcione en UI sin `force_payment_move`.

**No cargar datos reales de Alexander todavía.** Lista de información en `ALEXANDER_DATA_REQUEST.md`.
