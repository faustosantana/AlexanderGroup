# Report QA — V5.3 E2E DEV

Módulo `justech_alexander_reports` **19.0.3.8.5**. Solo DEV.

`VISUAL_V5_2 = APPROVED_AS_DESIGN_BASE`. `VISUAL_V5_3 = PASS`.

`PROD_UNTOUCHED = YES` — `doralex-production-odoo` StartedAt `2026-08-27T20:12:21.681221743Z` antes y después.

## Scorecard

| Clave | Valor |
| --- | --- |
| VISUAL_V5_3 | PASS |
| QUOTATION_REPORT | PASS |
| INVOICE_REPORT | PASS |
| CREDIT_NOTE_REPORT | PASS |
| RFQ_REPORT | PASS |
| PURCHASE_ORDER_REPORT | PASS |
| PAYMENT_RECEIPT_REPORT | PASS |
| STATEMENT_REPORT | PASS |
| DELIVERY_REPORT | PASS |
| RECEIPT_REPORT | PASS |
| EMAIL_PDF_MATCH | 6/6 |
| MULTICOMPANY_REPORT_ISOLATION | PASS |
| MULTICOMPANY_FISCAL_ISOLATION | PASS |
| NCF_QA_ENGINE | PASS |
| MULTIPAGE_RENDER | PASS |
| SIGNATURE_LAST_PAGE | PASS |
| PRINT_READABILITY | PASS (A4; A5 recibo; sin fuente 6px) |
| REPORT_SUITE_COMPLETE | YES (DEV) |
| READY_TO_DEPLOY_PRODUCTION | BLOCKED_BY_CONFIGURATION |
| PROD_UNTOUCHED | YES |
| USD_RATE_CONFIGURATION | BLOCKED (0 `res.currency.rate`) |

## Matriz 6 empresas

| Empresa | QUOT | INV_D | INV_P | NC | RFQ | PO | PAY_A | PAY_N | STMT | DEL | REC | EMAIL | NCF | MULTI | RESULT |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| DOR | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| PIN | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| DOM | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| MAY | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| REM | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| BLU | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |

## NCF QA consumidos este ciclo (motor, no manual)

| Empresa | Factura cobro | NC | Origen NC | Cruce |
| --- | --- | --- | --- | --- |
| DOR | B0199000007 | B0499000124 | B0199000008 | — |
| PIN | B0199001003 | B0499001122 | B0199001004 | — |
| DOM | B0199002003 | B0499002122 | B0199002004 | — |
| MAY | B0199003003 | B0499003122 | B0199003004 | — |
| REM | B0199004003 | B0499004122 | B0199004004 | B0199004005 (BLU activa) |
| BLU | B0199005003 | B0499005122 | B0199005004 | — |

Borrador: FACTURA + BORRADOR + Pendiente de NCF. Sin NCF ficticio.

## Email (Graph Sent Items)

FROM = `administracion@dominio` en las seis. Cotización y factura con PDF. Cruce: empresa activa Blue Elite, documento Rempart → FROM `administracion@rempartgroup.com`.

No ventas@ / facturacion@ / Gmail en documentos.

## COMPANY_DATA_MISSING

Las seis: **website**, **términos legales PROD**. No inventados. Website oculto. Términos actuales = texto QA DEV.

## Roles

Usuario operacional `inversionesdoralex@gmail.com` (id 14): no es admin. Grupos: Multi Companies + Role / User. **No puede** imprimir `sale.order`. ROLES = BLOCKED_BY_CONFIGURATION.

## PNG principales

Galería: [`docs/report_previews/index.html`](report_previews/index.html).
