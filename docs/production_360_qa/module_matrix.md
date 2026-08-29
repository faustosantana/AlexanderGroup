# Matriz de módulos custom en PROD

Fuente: `ir.module.module` state=installed, 2026-08-29. Smoke ≠ `installed`.

| NAME | VERSION | INSTALLED | PURPOSE | MENU | MODELS | SECURITY | QA TEST | RESULT |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| justech_alexander_base | 19.0.1.0.3 | YES | Identidad 6 empresas + guardia NCF | Admin Doralex | res.company dx_* | ACL módulo | NCF guard + company | PASS |
| justech_alexander_reports | 19.0.3.8.5 | YES | Reportes V5.3 | — | QWeb | — | PDF 6/6 + statement | PASS |
| justech_alexander_microsoft_mail | 19.0.1.0.4 | YES | Graph From por empresa | Correo Microsoft | dx.ms.graph.client | — | Factura TEST 6/6 | PASS |
| justech_alexander_admin | 19.0.1.0.1 | YES | Centro admin | Administración Doralex | — | — | menú presente | PASS |
| justech_alexander_website | 19.0.1.0.7 | YES | Website oculto | — | — | — | no publicado | NOT_APPLICABLE |
| justech_l10n_do_ncf | 19.0.2.31.0 | YES | Motor NCF | Fiscal RD / Rangos | justech.do.ncf.* | fiscal groups | B01/B04/void | PASS |
| justech_l10n_do_base | 19.0.1.27.1 | YES | Tipos B01–B17, padrón, 606 expense | Tipos de costos | fiscal.document.type | — | expense type 09 en bills | PASS |
| justech_fiscal_admin | 19.0.1.10.0 | YES | Feature flags | — | justech.fiscal.feature.flag | — | ncf_motor ON | PASS |
| l10n_do | 19.0.2.0 | YES | Localización | — | — | — | taxes 18% | PASS |
| l10n_do_accounting | 19.0.1.0.1 | YES | LATAM docs | Secuencia fiscal | l10n_latam.document.type | — | vendor NCF recibido | PASS |
| justech_accounting_recovery | 19.0.1.4.0 | YES | SoD reversión | — | recovery guard | group_accounting_recovery | NC bloqueada sin grupo; OK con grupo | PASS |
| justech_warranty | 19.0.1.9.1 | YES | Garantías | Justech Garantías | justech.warranty* | — | GAR/2026/00001+ | PASS |
| justech_global_audit_log | 19.0.4.1.4 | YES | Audit trail | Auditoría de Cambios | justech.audit.log | — | 0 filas | FAIL |
| justech_report_identity_guard | 19.0.1.0.0 | YES | Bloquea Hellenia | — | ir.actions.report | — | hellenia blocked | PASS |
| justech_core | 19.0.1.0.0 | YES | Core Justech | — | — | — | dependencia | PASS |
| justech_modules | 19.0.1.8.7 | YES | Licencias/flags | Módulos Justech | justech.license* | — | menú | PASS |
| bi_convert_purchase_from_sales | 19.0.0.0 | YES | PO desde SO | wizard create.purchaseorder | create.purchaseorder | — | DOR/OC desde SO | PASS |

## No instalados (congelados / fuera de este deploy)

| NAME | RESULT |
| --- | --- |
| justech_approval_flow | NOT_INSTALLED |
| justech_purchase_sale_margin_control | NOT_INSTALLED |
| justech_sale_purchase_trace | NOT_INSTALLED |
| justech_vendor_bill_po_control | NOT_INSTALLED |
| multi_invoice_manual_payment_prod | NOT_INSTALLED |
| justech_l10n_do_payments_withholding | NOT_INSTALLED |
| justech_sale_terms_guard | NOT_INSTALLED |
| justech_quotation_client_dedup | NOT_INSTALLED |

No se instalaron en esta fase (regla de freeze justgroup.app + no deploy extra).
