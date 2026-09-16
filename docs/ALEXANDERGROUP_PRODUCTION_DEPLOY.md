# ALEXANDERGROUP / DORALEX — FINAL DEPLOYMENT REPORT

Fecha: 2026-09-16.
Entorno: **PRODUCCIÓN** (`doralex_prod` / `doralex-production-odoo`).
**PROD TOUCHED: YES.**
**DEPLOYMENT COMPLETED: YES.**
**FINAL STATUS: SUCCESS.**

Hotfix posterior (mismo día): pantalla blanca en `/odoo` — ver
[`ALEXANDERGROUP_PRODUCTION_WHITESCREEN.md`](ALEXANDERGROUP_PRODUCTION_WHITESCREEN.md).
Login 19.0.1.6.1 + OWL EnterpriseNavBar 19.0.1.6.2. Sin rollback.

---

```
ALEXANDERGROUP / DORALEX — FINAL DEPLOYMENT REPORT

PRECHECK: PASS
BACKUP: /opt/doralex/backups/prod/pre_alexander_release_20260916_160915
BACKUP VERIFIED: YES (SHA256 OK · pg_restore --list 33990 · filestore 1315 · addons 2258 · 83G libres)
TARGET COMMIT: 1599d132ce019a7d3c47e6c722acbc9139c80759
CODE SYNC: PASS (solo justech_alexander_{base,ux,reports})

MODULES BEFORE:
  justech_alexander_base     19.0.1.0.5
  justech_alexander_ux       19.0.1.4.0
  justech_alexander_reports  19.0.3.8.5

MODULES AFTER:
  justech_alexander_base     19.0.1.0.7
  justech_alexander_ux       19.0.1.6.0
  justech_alexander_reports  19.0.3.9.1

ITBIS 16 SALE: PASS (creado 8–13; no asignado a productos)
DX RULES: PASS (19 códigos globales DX-*; tax_id=False; 114 configs 8–13 unique)
ACCOUNT MAPPING: PASS (0 foreign · 0 ambiguous · company 1 plantilla sin cuentas)
LEGACY TAXES: UNCHANGED (-10% ISR Fee/Rent · -2% ISR · -27% ISR activos, no default)

APPROVAL FLOW: OFF (sale/po/inv False en 8–13 · param vacío/False)
DGII PADRON: OFF (param · cron · auto-download · 0 filas · sin block partner/invoice)

DRAFT CANCEL: PASS (Billing / alexander.pina · state=cancel en draft 8 y 11)
PROPET: PASS (HTML render BLU + DOR)
PROFORMA: PASS
DELIVERY: PASS (conduce existente BLU/OUT/00002 · DOR/OUT/00016)
SIGNATURE: PASS (logo + identidad por compañía en compose)
EMAIL: PASS (Graph/mailbox por empresa intacto · render OK · sin envío a clientes)

RET ISR PROFESSIONAL: PASS (100,000 → 15,000)
RET ISR TECHNICAL: PASS (100,000 → base 20,000 × 15% = 3,000)
RET GOVERNMENT 5: PASS (100,000 → 5,000)
RET ITBIS 30: PASS (18,000 → 5,400)
RET ITBIS 100: PASS (18,000 → 18,000)

MULTICOMPANY: PASS (BLU 8 + DOR 11: impuestos, firmas, reportes, retenciones, cuentas)

NCF CHANGES: NONE
NCF OPERATIONAL WARNINGS: ver sección 7 (no son fallo de software)

TRACE MODULE: FROZEN (DB 19.0.1.2.11 · FILE 19.0.1.2.10 · SAFE)
MARGINS: UNCHANGED 19.0.8.29.38
PAYMENTS: UNCHANGED 19.0.1.7.2
FROZEN MODULES: withholding 19.0.1.7.2 · multi_invoice 19.0.1.5.4 · recovery 19.0.1.4.0 · approval_flow 19.0.1.3.8 · microsoft_mail 19.0.1.0.4

ODOO HEALTH: PASS (container healthy · /web/health 200 {"status":"pass"} · 375 módulos)
DB HEALTH: PASS (PostgreSQL 16.15 accepting · doralex_prod)
ERROR LOGS: NONE críticos post-20:10 (sin ERROR/CRITICAL/ParseError/QWeb)

POST-DEPLOY TESTS: 40 PASS / 0 FAIL
PASS: precheck, backup, sync, -u, restart, ITBIS16, DX, mapping, approval, padron, draft cancel, quote confirm, Propet, Proforma, Conduce, Recibo, retenciones, multicompany, NCF intactos
FAIL: (ninguno)

ROLLBACK REQUIRED: NO
ROLLBACK EXECUTED: NO

PROD TOUCHED: YES
DEPLOYMENT COMPLETED: YES

FINAL STATUS: SUCCESS
```

---

## 1. PRECHECK

| Item | Valor | Resultado |
| --- | --- | --- |
| PROD DB | `doralex_prod` | PASS |
| CONTAINER | `doralex-production-odoo` | healthy |
| POSTGRES | `doralex-production-db` | healthy · PG 16.15 |
| TARGET CODE | `1599d132ce019a7d3c47e6c722acbc9139c80759` | PASS |
| Host git | no hay `.git` en el host | esperado · sync por tarball |
| Disk | 83G libres | PASS |

No se actualizó: `justech_sale_purchase_trace`, `justech_purchase_sale_margin_control`, `multi_invoice_manual_payment_prod`, `justech_accounting_recovery`, `justech_l10n_do_payments_withholding`, `justech_approval_flow`, core Odoo, `justech_alexander_microsoft_mail`.

## 2. BACKUP

Ruta primaria (rollback):

`/opt/doralex/backups/prod/pre_alexander_release_20260916_160915`

| Artefacto | Tamaño | Verificación |
| --- | --- | --- |
| `db.dump` | 20M | `sha256sum -c` OK · `pg_restore --list` 33990 líneas |
| `filestore.tar.gz` | 25M | SHA OK · `tar -tzf` 1315 entradas |
| `custom-addons.tar.gz` | 7.4M | SHA OK · 2258 entradas |
| `config.tar.gz` / `odoo.conf` / `docker-compose.yml` / `env.backup` | — | SHA OK |
| `overlay_dirs_before/` | copia de los 3 módulos pre-sync | presente |
| `RELEASE_META` | target `1599d13` · before 1.0.5 / 1.4.0 / 3.8.5 | presente |

**BACKUP_STATUS = VERIFIED** (antes de sync/`-u`).

Rollback preparado (no ejecutado): maintenance → stop `doralex-production-odoo` → drain backends PG → `pg_restore --clean` → restore filestore **sobre el volumen (no `docker exec` con contenedor stopped)** → restore addons desde `overlay_dirs_before` o `custom-addons.tar.gz` → start Odoo → health/smoke.

## 3. CODE SYNC + `-u`

Host sin git. Copia exclusiva de:

- `justech_alexander_base`
- `justech_alexander_ux`
- `justech_alexander_reports`

desde el árbol exacto de `1599d13`. Overlay dirs actuales respaldados en el backup.

`-u` ejecutado 2026-09-16 20:10:10–20:10:39 UTC:

```
-u justech_alexander_base,justech_alexander_ux,justech_alexander_reports
--stop-after-init --no-http
```

EXIT 0. Migración `justech_alexander_ux [$19.0.1.6.0] end-apply_catalog` completada. Luego `docker restart doralex-production-odoo` únicamente. Registry 375 módulos. HTTP 200.

## 4. ITBIS 16% SALE

No existía en PROD (solo purchase). Creado por compañía 8–13 clonando el `18% ITBIS` **sale de esa misma empresa**. No se copiaron ids de STAGING. No se hardcodearon `account_id`. No se compartió impuesto entre compañías. 0 productos con 16% venta.

| CO | Tax id | Grupo | Cuenta venta | Tags |
| --- | --- | --- | --- | --- |
| 8 BLU | 461 | ITBIS 87 | 1883 ITBIS on Sale of Goods `[8]` | base.16% / tax.16% |
| 9 PIN | 462 | ITBIS 101 | 2171 `[9]` | base.16% / tax.16% |
| 10 DOM | 463 | ITBIS 115 | 2459 `[10]` | base.16% / tax.16% |
| 11 DOR | 464 | ITBIS 129 | 2747 `[11]` | base.16% / tax.16% |
| 12 MAY | 465 | ITBIS 143 | 3035 `[12]` | base.16% / tax.16% |
| 13 REM | 466 | ITBIS 157 | 3323 `[13]` | base.16% / tax.16% |

`type_tax_use=sale` · `amount=16` · `price_include=False` · invoice/refund 100%+100%.

Smoke (draft, sin postear):

- Base 1,000 / ITBIS 160 / Total 1,160 (BLU + DOR)
- NC draft: Base 1,000 / ITBIS 160 / Total 1,160
- 18% control: 1,000 / 180 / 1,180

Los ids 461–466 coinciden numéricamente con STAGING por secuencia local; **no** se importaron.

## 5. DX-* Y CUENTAS

`dx_sync_2026_catalog()`: 19 códigos globales (`company_id` vacío), `tax_id=False`, selección manual.

114 configs operativas (19 × 6). `candidate_count==1` en todos los nombres usados. 0 cuentas cruzadas. Plantilla (compañía 1) tiene 19 configs sin cuenta — no operativa, no es fallo.

Legacy `-10%` / `-2%` / `-27%` (`account.tax`) siguen activos. No son default. No autoaplican. DX no los convierte.

## 6. APROBACIONES Y PADRÓN

Tras migración 19.0.1.6.0:

- 8–13: `justech_approval_{sale,purchase,invoice}_enabled = False`
- `justech_alexander.approval_flow_enabled` = False
- Histórico / reglas / chatter / menú «Aprobaciones (histórico)» conservados

Smoke: `BLU/SO/00013` y `DOR/SO/00017` confirmadas → `state=sale` · `justech_approval_state=none`. Luego canceladas y eliminadas.

Padrón:

- param OFF · cron 31 inactive · `auto_update_enabled=False` · 0 filas
- sin campos de block partner/invoice a nivel compañía
- no se descargó ni importó

## 7. NCF — SIN CAMBIOS DE SOFTWARE

`next_sequence` / `state` / `authorization_number` idénticos pre/post smoke. No se crearon 9911xxxx ni `STAGING-UAT-NO-DGII`.

Pendientes **operativos** (no fallo del deploy):

- renovar B01 y B11 **Piñaria (9)** — vencidos 2025-12-31
- renovar B01 y B11 **Dominion (10)** — vencidos 2025-12-31
- renovar B11 **Doralex (11)** — vencido 2024-12-31
- Doralex B04 y B13: 1 número restante
- renovar B11 y B13 **Mayuma (12)** — vencidos 2025-12-31
- renovar B13 y B11 **Rempart (13)** — vencidos 2025-12-31
- renovar / ampliar B15 **Blue Elite (8)** — agotado (next=end=102)
- configurar B17 cuando la operación lo requiera (ausente en todas)

Operable hoy (crédito fiscal B01 activo): BLU, DOR, MAY, REM. PIN y DOM: no facturar B01 hasta renovar.

## 8. CORREO

`justech_alexander_microsoft_mail` permanece **19.0.1.0.4**. Secretos no tocados. Alias/mailbox por empresa intactos (`administracion@…`). SMTP clásico = 0 (Graph). Render de plantilla de pedido OK (asunto con razón social). No se envió correo real a clientes. **EMAIL = PASS.**

## 9. SMOKE (no destructivo)

40 checks PASS / 0 FAIL. Documentos de prueba eliminados o archivados (`DX-PROD-SMOKE-20260916`). NCF sin consumo. Secuencias de cotización BLU/SO y DOR/SO avanzaron un número y los SO se borraron.

## 10. ROLLBACK

No requerido. Plan listo sobre el backup fresco de 2026-09-16 16:09 AST / 20:09 UTC.

---

**FINAL STATUS: SUCCESS**
