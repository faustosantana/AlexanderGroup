# Alexander Group — Production Readiness (cierre STAGING)

Fecha: 2026-09-16.
**PROD TOUCHED: NO. NO DESPLEGAR.**

## FINAL READINESS

H01 ITBIS 16: PASS
H01 CREDIT NOTE: PASS (importes 1000/160/1160 en borrador; post bloqueado: rango B04 cancelado)
H02 DESCRIPTIONS: PASS
H03 PROPET: PASS
H04 SALES USER: PASS (`dxuat.sales.only@example.invalid` creado, probado y desactivado)
H05 TRACKING: PASS
H06 CRM: PASS
H07/H10 DRAFT CANCEL: PASS
H08 PROFORMA: PASS

APPROVAL FLOW: DISABLED
APPROVAL BLOCKING SALES: NO

DGII PADRON: DISABLED
DGII CRON: OFF
DGII BLOCKING PARTNERS: NO

H12 CUSTOMER PO: PASS

H13 RD WITHHOLDINGS: PARTIAL (catálogo + fórmulas + cuentas PASS; pago publicado BLOCKED)
H13 ISR PROFESSIONAL: PASS (15000 sobre 100000)
H13 ISR TECHNICAL: PASS (3000 = 15% × 20%)
H13 GOVERNMENT 5: PASS (5000)
H13 ITBIS 30: PASS (5400 sobre 18000, no sobre 100000)
H13 ITBIS 100: PASS (18000)
H13 FOREIGN PAYMENTS: CONFIGURED (catálogo DX-ISR-EXT-*; no pago real)
H13 MULTI PAYMENT: PASS (lado cliente, UAT previo PBNK1/2026/00081); con retenciones BLOCKED
H13 WITHHOLDING RECEIPT: BLOCKED (sin factura proveedor publicada)
H13 PARTIAL PAYMENT: PASS (cálculo 2700 sobre 50% de 118000)
H13 CREDIT NOTE: PASS (ITBIS 16% 1000/160/1160)
H13 ACCOUNT MAPPING: PASS (empresas 8 y 11, cuentas l10n_do existentes)

H14 DELIVERY: PASS
H15 EMAIL: PASS (infra SMTP/Graph inválida, no código)
H16 SIGNATURE: PASS
H17 HOME: PASS

TESTS: PASS (204 pytest `tests/`)
RESTORE: PASS (temp `doralex_restore_test_20260916`, luego drop)
MULTICOMPANY: PASS (cálculo 8 y 11)
ACCOUNTING: PASS (ITBIS 16 asiento previo; retenciones mapeadas)
PROD TOUCHED: NO
READY FOR PROD: **NO**

## Bloqueadores para YES

1. Empresa 11 **sin rango B11/B13/B17 activo** → no se publica factura de proveedor ni se prueba el asiento de pago+retención.
2. Rango **B04 cancelado** → la nota de crédito 16% no se contabiliza (importes sí correctos en borrador).
3. Correo: SMTP `invalid` / Graph sin credenciales (ya documentado; no bloquea código).

## ID / ESTADO / PRUEBA / EVIDENCIA / RIESGO PROD

| ID | ESTADO FINAL | PRUEBA | EVIDENCIA | RIESGO PROD |
| --- | --- | --- | --- | --- |
| H11 | DISABLED | Cotización editar qty/precio/dto/términos → confirmar | `DOR/SO/00093` state=sale approval=none | Bajo si flags permanecen False |
| H09 | DISABLED | Partner `pending_new` + factura | `INV/2026/00074` NCF B0100000061; cron 31 OFF; 0 filas | Bajo; no validar RNC contra padrón |
| H07/H10 | PASS | Draft cancel/unlink; posted reset | Facturación cancela/elimina draft; `INV/2026/00067` reset bloqueado | Medio si se espera recovery en posted |
| H13 | PARTIAL | Fórmulas 15/3/5/30/100 + cuentas 8/11 | Catálogo 19 códigos DX-*; 15000/3000/5400/18000/5000 | Alto publicar sin B11 y sin UAT de asiento |
| H01 CN | PASS* | NC 16% | Draft 1000/160/1160; post: falta B04 | Medio |
| H04 | PASS | Usuario solo Ventas | `DOR/SO/00095`; usuario desactivado | Bajo |
| RESTORE | PASS | Temp DB + filestore | TOC 33983; 1761 tablas; 372 módulos; 754 files; drop OK | Bajo |

## APPROVAL MODULE

APPROVAL MODULE: `justech_approval_flow` 19.0.1.3.8 (instalado)
APPROVAL DEPENDENCIES: overlay UX; no desinstalado
APPROVAL BLOCKS REMOVED: flags company False; app fuera del launcher; menú histórico bajo Administración
HISTORICAL DATA PRESERVED: sí (requests, chatter, reglas no borradas)
ALEXANDER APPROVAL ACTIVE: **NO**

## DGII PADRON

DGII PADRON ACTIVE: **NO**
DGII CRON ACTIVE: **NO** (id 31)
DGII REQUIRED FOR PARTNERS: **NO**
DGII REQUIRED FOR INVOICING: **NO**
Botón Validar RNC/padrón: oculto en overlay Alexander

## H07 matriz

| ESTADO | ACCIÓN | ODOO NATIVO | CUSTOM ACTUAL | GRUPO NECESARIO | RESULTADO FINAL |
| --- | --- | --- | --- | --- | --- |
| BORRADOR | cancelar | invoice/user | overlay salta recovery | Facturación | PASS |
| BORRADOR | eliminar | invoice/user | overlay salta recovery | Facturación | PASS |
| PUBLICADA | reset draft | manager + lock | recovery | Recuperación Contable | bloqueado sin grupo |
| PUBLICADA | cancel | — | recovery | Recuperación Contable | no liberado |
| PUBLICADA | reversión | reverse invoice | recovery o revertir factura | recovery / Opción C | sin cambio |

## Restore

Backup usado: `/opt/doralex/backups/enterprise-staging/pre_alexander_staging_uat_20260916_183140`

- `pg_restore -l` TOC **33983**
- DB temporal `doralex_restore_test_20260916`
- Carga ~13.6 min (incluye espera por lock de workers; se detuvo solo STAGING Odoo)
- 1761 tablas; attachments SQL 1271; filestore 754
- Shell: 7 compañías, 10 users, 372 módulos, registry 1290, `RESTORE_REGISTRY_OK`
- Drop **solo** temp DB + `/var/lib/odoo/filestore/doralex_restore_test_20260916`
- `doralex_ent_staging` y `doralex_prod` intactos

Backup previo a este overlay:
`/opt/doralex/backups/enterprise-staging/pre_alexander_closeout_20260916_185959`

## Overlay aplicado en STAGING

| Módulo | Versión |
| --- | --- |
| justech_alexander_base | 19.0.1.0.7 |
| justech_alexander_ux | 19.0.1.6.0 |
| reports / microsoft_mail | sin `-u` (ya UAT PASS) |

`-u justech_alexander_base,justech_alexander_ux` EXIT 0. Nunca `-u all`.

## PRODUCTION DEPLOYMENT PLAN

**NO AUTORIZADO. NO EJECUTAR.**

Cuando exista autorización expresa y los bloqueadores B11/B04/correo estén resueltos:

1. Backup PROD (db + filestore + custom-addons) con `backup.sh production` y verificar SHA256.
2. Copiar **solo** `justech_alexander_base` 19.0.1.0.7 y `justech_alexander_ux` 19.0.1.6.0.
3. `-u justech_alexander_base,justech_alexander_ux` (nunca `-u all`, nunca core).
4. Confirmar flags aprobación False y cron padrón OFF.
5. `dx_sync_2026_catalog` / migración 19.0.1.6.0 crea DX-* y mapea cuentas **por nombre**.
6. Smoke: cotización confirmar sin aprobación; partner `pending_new` factura; draft cancel; seleccionar retención 30%/15%/100% en wizard.
7. Downtime estimado: reinicio corto de Odoo PROD + `-u` (~1–2 min de registry).
8. Rollback: tarball de módulos previos + restore del backup del paso 1.
9. GO: B11/B04 activos por empresa operativa; SMTP/Graph reales; flags OFF; catálogo DX-* con cuentas.
10. NO-GO: cualquier `-u all`; flags de aprobación True; cron padrón ON; cuentas nuevas inventadas; copiar NCF/saldos de Justgroup.

DETENERSE. PROD no se toca hasta autorización expresa.
