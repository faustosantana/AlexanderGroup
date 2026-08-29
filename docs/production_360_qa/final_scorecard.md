# Scorecard 360 — producción Doralex

Fecha: 2026-08-29. Backup previo: `production_20260829_112927` (`PROD_360_BACKUP = PASS`).
Datos: únicamente `DX TEST` / `DX-TEST-NO-DGII-360`. **Nada enviado a DGII.**

```
PROD_360_BACKUP                 = PASS
PROD_360_AUDIT                  = PASS   (stack instalado)
ADMIN_FULL                      = PASS   (login admin, 6/6 compañías, group_system)
FAUSTO_LOGIN                    = NOT_CONFIGURED   (no existe res.users fausto@justech.do)

MODULE_INVENTORY                = PASS

SALES_FLOW                      = PASS
PURCHASE_FLOW                   = PASS
INVENTORY_FLOW                  = PASS
ACCOUNTING_FLOW                 = PASS
PAYMENTS_FLOW                   = PASS

NCF_TEST_B01                    = PASS
NCF_TEST_B04                    = PASS

DGII_606_GENERATION             = NOT_INSTALLED   (extracto QA DATA = PASS)
DGII_607_GENERATION             = NOT_INSTALLED   (extracto QA DATA = PASS)
DGII_608_GENERATION             = NOT_INSTALLED   (void wizard + extracto DATA = PASS)
DGII_EXTERNAL_SUBMISSION        = NOT_PERFORMED
DGII_EXTERNAL_SUBMISSION_STATE  = DISABLED_FOR_TEST

APPROVAL_FLOW                   = NOT_INSTALLED   justech_approval_flow
APPROVAL_TRACEABILITY           = NOT_INSTALLED

COST_MARGIN_MODULE              = NOT_INSTALLED   justech_purchase_sale_margin_control
ESTIMATED_MARGIN                = NOT_INSTALLED
REAL_MARGIN                     = NOT_INSTALLED
MULTIPLE_PO_PER_SALE            = NOT_IMPLEMENTED (sin módulo margen; bi_convert crea 1 PO)
VENDOR_BILL_LINKING             = NOT_INSTALLED
CXP_REPORT                      = PASS            (6 vendor bills TEST, listado CxP)

SALE_PURCHASE_TRACE             = NOT_INSTALLED
VENDOR_BILL_PO_CONTROL          = NOT_INSTALLED

WARRANTY                        = PASS
GLOBAL_AUDIT_LOG                = FAIL            MEDIUM — módulo instalado, 0 filas justech.audit.log
REPORT_IDENTITY_GUARD           = PASS
SALE_TERMS_GUARD                = NOT_INSTALLED
CLIENT_DEDUP                    = NOT_INSTALLED

CRM                             = PASS

MULTICOMPANY                    = PASS
CROSS_COMPANY_FISCAL            = PASS
CROSS_COMPANY_REPORTS           = PASS
CROSS_COMPANY_EMAIL             = PASS

REPORT_SUITE                    = PASS
EMAIL                           = 6/6

SECURITY_ACL                    = PASS
RECORD_RULES                    = PASS

QA_DATA_CATALOGUED              = YES
QA_CLEANUP_PREPARED             = YES
QA_CLEANUP_EXECUTED             = NO
TEST_NCF_CLEANUP_PREPARED       = YES
TEST_NCF_CLEANUP_EXECUTED       = NO

SYSTEM_OPERATIONAL              = YES
PRODUCTION_VALIDATED_360        = YES
FISCAL_REAL_GO_LIVE_READY       = NO

CODE_READY                      = YES
MODULES_READY                   = YES   (solo los instalados)
WORKFLOWS_READY                 = YES
REPORTS_READY                   = YES
APPROVALS_READY                 = NO
MARGIN_COST_READY               = NO
DGII_FILE_GENERATION_READY      = NO    (no hay exporter 606/607/608 en el registry)
MULTICOMPANY_READY              = YES
EMAIL_READY                     = YES
CLEANUP_READY                   = YES
```

## Hallazgos clasificados

| Hallazgo | Severidad | BLOCKS_GO_LIVE |
| --- | --- | --- |
| Rangos NCF reales / secuencias / vencimientos vacíos | CRITICAL | YES — facturación real |
| Exporter DGII 606/607/608 no instalado (flag `dgii_reports` ON, 0 modelos) | HIGH | YES — si se exige archivo DGII nativo |
| `justech_approval_flow` no instalado | HIGH | YES — si UAT aprobaciones es go-live |
| `justech_purchase_sale_margin_control` no instalado | HIGH | YES — si margen/CxP analítico es go-live |
| `justech_sale_purchase_trace` / `justech_vendor_bill_po_control` no instalados | HIGH | NO si no son alcance de lunes |
| `fausto@justech.do` no es usuario admin | MEDIUM | NO |
| `justech.audit.log` = 0 filas tras QA | MEDIUM | NO |
| NC exige grupo Recuperación Contable (también para admin) | MEDIUM | NO — grupo otorgado a `__system__` / admin para QA |
| `justech_sale_terms_guard` / `justech_quotation_client_dedup` no instalados | LOW | NO |
| `multi_invoice_manual_payment_prod` no instalado | LOW | NO — pagos nativos 6/6 OK |

## No deploy adicional

PNG de factura TEST coinciden con V5.3. Sin rediseño. Sin rangos reales.
