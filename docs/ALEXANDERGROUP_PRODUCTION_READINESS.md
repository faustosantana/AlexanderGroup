# Alexander Group — Production Readiness (cierre fiscal STAGING)

Fecha: 2026-09-16.
**PROD TOUCHED: NO. NO DESPLEGAR.**

## FINAL READINESS

H01 ITBIS 16: PASS
H01 CREDIT NOTE: PASS (`RINV/2026/00001` POSTED NCF `B0499114001`)
H01 CREDIT NOTE ACCOUNTING: PASS (motor: −1 000 / −160 / −1 160 vía asiento inverso)
H02 DESCRIPTIONS: PASS
H03 PROPET: PASS
H04 SALES USER: PASS
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

H13 RD WITHHOLDINGS CALCULATION: PASS
H13 ISR PROFESSIONAL CALC: PASS (15 000)
H13 ISR PROFESSIONAL E2E: PASS (`BILL/2026/09/0001` + `PBNK1/2026/00082`, residual 0)
H13 ISR TECHNICAL CALC: PASS (3 000 = 15% × 20 000)
H13 ISR TECHNICAL E2E: PASS (`BILL/2026/09/0002`)
H13 GOVERNMENT 5 CALC: PASS (5 000)
H13 GOVERNMENT 5 E2E: PASS (`BILL/2026/09/0003` B01 recibido)
H13 ITBIS 30 CALC: PASS (5 400, no 30 000)
H13 ITBIS 30 E2E: PASS (`BILL/2026/09/0004`)
H13 ITBIS 100 CALC: PASS (18 000)
H13 ITBIS 100 E2E: PASS (mismo pago profesional)
H13 FOREIGN PAYMENTS: CONFIGURED (catálogo; sin B17 ni pago exterior)
H13 MULTI PAYMENT: PASS (cliente previo PBNK1/2026/00081)
H13 MULTI-INVOICE WITHHOLDING: PASS (3 B11 + `PBNK1/2026/00086`)
H13 WITHHOLDING RECEIPT: PASS (PDF/HTML 19.0.3.9.1)
H13 PARTIAL PAYMENT: PASS (2 700 + 2 700 → residual 0)
H13 ACCOUNT MAPPING: PASS (cuentas l10n_do existentes)
H13 CREDIT NOTE: PASS (posted)

H14 DELIVERY: PASS
H15 EMAIL APPLICATION: PASS
H15 EMAIL LIVE DELIVERY: PROD CONFIGURATION REQUIRED
H16 SIGNATURE: PASS
H17 HOME: PASS

TESTS: PASS (pytest `tests/` + receipt compose)
RESTORE: PASS (temp `doralex_restore_test_20260916`, no repetido)
MULTICOMPANY: PASS
ACCOUNTING: PASS
PROD TOUCHED: NO
READY FOR PROD: **YES**

## Clasificación corregida

Hasta publicar, H01 NC y H13 E2E eran **PARTIAL — CALCULATION PASS /
POSTING BLOCKED**. Eso ya no aplica: B04/B11 UAT existen y los asientos
están posted.

EMAIL no bloquea READY FOR PROD (lógica de aplicación PASS; entrega live
es pre-GO de producción).

## ID / ESTADO / PRUEBA / EVIDENCIA / RIESGO PROD

| ID | ESTADO FINAL | PRUEBA | EVIDENCIA | RIESGO PROD |
| --- | --- | --- | --- | --- |
| H11 | DISABLED | Cotización editar + confirmar | `DOR/SO/00093` approval=none | Bajo si flags False |
| H09 | DISABLED | Partner pending_new + factura | `INV/2026/00074`; cron 31 OFF | Bajo |
| H07/H10 | PASS | Draft cancel/unlink; posted reset | Recovery bloquea posted | Medio |
| H13 | PASS | Fórmulas + E2E asiento/pago/recibo | Ver `ALEXANDERGROUP_RD_WITHHOLDINGS.md` | Alto si se copian rangos UAT a PROD |
| H01 CN | PASS | NC 16% posted | `RINV/2026/00001` B0499114001 | Medio: PROD necesita B04 real |
| H04 | PASS | Usuario solo Ventas | desactivado | Bajo |
| RESTORE | PASS | Temp DB + filestore | TOC 33983; drop OK | Bajo |
| EMAIL | CODE PASS | SMTP invalid / Graph vacío | intencional STAGING | Pre-GO PROD |

## APPROVAL MODULE

APPROVAL MODULE: `justech_approval_flow` 19.0.1.3.8 (instalado)
APPROVAL DEPENDENCIES: overlay UX; no desinstalado
APPROVAL BLOCKS REMOVED: flags company False; app fuera del launcher
HISTORICAL DATA PRESERVED: sí
ALEXANDER APPROVAL ACTIVE: **NO**

## DGII PADRON

DGII PADRON ACTIVE: **NO**
DGII CRON ACTIVE: **NO** (id 31)
DGII REQUIRED FOR PARTNERS: **NO**
DGII REQUIRED FOR INVOICING: **NO**

## H07 matriz

| ESTADO | ACCIÓN | ODOO NATIVO | CUSTOM ACTUAL | GRUPO NECESARIO | RESULTADO FINAL |
| --- | --- | --- | --- | --- | --- |
| BORRADOR | cancelar | invoice/user | overlay salta recovery | Facturación | PASS |
| BORRADOR | eliminar | invoice/user | overlay salta recovery | Facturación | PASS |
| PUBLICADA | reset draft | manager + lock | recovery | Recuperación Contable | bloqueado sin grupo |
| PUBLICADA | cancel | — | recovery | Recuperación Contable | no liberado |
| PUBLICADA | reversión | reverse invoice | recovery o revertir factura | recovery / Opción C | sin cambio |

## Restore

RESTORE: PASS. No repetido en este cierre.

Backup: `/opt/doralex/backups/enterprise-staging/pre_alexander_staging_uat_20260916_183140`

## Overlay aplicado en STAGING

| Módulo | Versión |
| --- | --- |
| justech_alexander_base | 19.0.1.0.7 |
| justech_alexander_ux | 19.0.1.6.0 |
| justech_alexander_reports | 19.0.3.9.1 |
| justech_alexander_microsoft_mail | 19.0.1.0.5 |

`-u justech_alexander_reports` EXIT 0 (recibo). Nunca `-u all`.
PROD `doralex-production-odoo` Up 8 days — no escrito.

## PRODUCTION PRE-FLIGHT (2026-09-16)

Pre-flight READ-ONLY entregado en
[`docs/ALEXANDERGROUP_PRODUCTION_PREFLIGHT.md`](ALEXANDERGROUP_PRODUCTION_PREFLIGHT.md).

PROD DB `doralex_prod` · contenedor `doralex-production-odoo` ·
CURRENT COMMIT N/A (sin `.git` en host) · TARGET `1599d13`.
CURRENT modules 19.0.1.0.5 / 19.0.1.4.0 / 19.0.3.8.5.
TARGET 19.0.1.0.7 / 19.0.1.6.0 / 19.0.3.9.1.

**READY TO EXECUTE DEPLOYMENT: NO.** PROD TOUCHED: NO.
No backup fresco. No `-u`. No sync. No restart.

PRE-GO FINAL (bloqueadores documentales):
[`docs/ALEXANDERGROUP_PRODUCTION_PREGO.md`](ALEXANDERGROUP_PRODUCTION_PREGO.md).
READY FOR HUMAN GO: **NO** — falta ITBIS 16% SALE (el overlay no lo crea).
Traza FILE/DB: SAFE TO LEAVE FROZEN. DX uniqueness PASS.

## PRODUCTION DEPLOYMENT PLAN

**NO AUTORIZADO. NO EJECUTAR. DETENERSE.**

Incluso con READY FOR PROD = YES:

1. Backup PROD (db + filestore + custom-addons) con `backup.sh production` y verificar SHA256.
2. Copiar **solo** overlay Alexander: `justech_alexander_base` 19.0.1.0.7,
   `justech_alexander_ux` 19.0.1.6.0, `justech_alexander_reports` 19.0.3.9.1
   (y microsoft_mail si el GO de correo está autorizado).
3. `-u` **solo** esos módulos (nunca `-u all`, nunca core, nunca Justgroup).
4. Confirmar flags aprobación False y cron padrón OFF.
5. Catálogo DX-* / cuentas **por nombre** (migración UX 19.0.1.6.0).
6. **Rangos NCF de PROD:** auditar y configurar **secuencias reales DGII
   por cada empresa operativa** (B01/B04/B11/B13/B15/B17 según el flujo
   real). **NO** crear en PROD los rangos UAT 99114xxx / 99111xxx.
   **NO** copiar `next_sequence` ni autorizaciones `STAGING-UAT-NO-DGII-*`.
   **NO** reactivar rangos cancelados de prueba.
7. Correo: configurar Graph/SMTP reales en PROD. No copiar secretos de
   PROD a STAGING ni al revés. EMAIL LIVE es requisito PRE-GO, no de código.
8. Smoke: cotización sin aprobación; partner `pending_new`; draft cancel;
   NC con B04 **real**; factura proveedor B11 emitido o B01 recibido según
   caso; wizard retención 15/3/30/100; recibo con ISR/ITBIS; residual 0.
9. Downtime: reinicio corto Odoo PROD + `-u`.
10. Rollback: tarball módulos previos + restore del backup del paso 1.
    Punto estable previo: `/opt/odoo-backups/prod-release-B-margins-POST-20260827_134919`.
11. GO: rangos fiscales reales auditados; SMTP/Graph; flags OFF; DX-* con cuentas.
12. NO-GO: `-u all`; flags aprobación True; cron padrón ON; copiar NCF UAT;
    inventar cuentas; tocar módulos frozen de pagos/márgenes/traza sin
    autorización expresa.

DETENERSE. PROD no se toca hasta autorización expresa.
