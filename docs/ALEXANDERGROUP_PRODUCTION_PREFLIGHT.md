# Alexander Group / Doralex — PRODUCTION PRE-FLIGHT

Fecha de auditoría READ-ONLY: 2026-09-16.
**PROD TOUCHED: NO.**
**NO se ejecutó backup. NO se sincronizó código. NO se ejecutó `-u`. NO se reinició PROD. NO se cambiaron NCF ni cuentas. NO se desplegó.**

STAGING está aprobado. READY FOR PROD técnico (código/UAT): YES.
Autorización humana para ejecutar el deployment: **NO RECIBIDA.**

---

## PRODUCTION PRE-FLIGHT

PROD DB: `doralex_prod`
PROD CONTAINER: `doralex-production-odoo`
CURRENT COMMIT: N/A (el host PROD no tiene `.git`; estado conocido por manifiestos en disco)
TARGET COMMIT: `1599d132ce019a7d3c47e6c722acbc9139c80759` (`1599d13` — cierre fiscal STAGING)

CURRENT MODULE VERSIONS:

| Módulo | Archivo PROD | Instalado DB |
| --- | --- | --- |
| justech_alexander_base | 19.0.1.0.5 | 19.0.1.0.5 |
| justech_alexander_ux | 19.0.1.4.0 | 19.0.1.4.0 |
| justech_alexander_reports | 19.0.3.8.5 | 19.0.3.8.5 |

TARGET MODULE VERSIONS:

| Módulo | Target |
| --- | --- |
| justech_alexander_base | 19.0.1.0.7 |
| justech_alexander_ux | 19.0.1.6.0 |
| justech_alexander_reports | 19.0.3.9.1 |

COMPANIES: 8 BLU · 9 PIN · 10 DOM · 11 DOR · 12 MAY · 13 REM (1 = plantilla, no operativa)
NCF AUDIT: PASS (inventario real). Completitud operativa: GAPS (ver tabla)
ACCOUNT MAPPING: PASS — 0 MISSING ACCOUNT — 0 cruce entre empresas — CODE=EMPTY
DX RULES: 19 CREATE (PROD=0 / STAGING=19) · legacy KEEP
APPROVAL: hoy company flags ON; después del `-u` autorizado → OFF
DGII: PADRON=OFF · CRON=OFF · ROWS=0 · PARTNER BLOCK=NO · INVOICE BLOCK=NO
EMAIL: configuración entendida (Graph + mailbox; SMTP=0). Live send no re-verificado hoy
BACKUP PLAN: diseñado, **no ejecutado**
ROLLBACK PLAN: contra el backup fresco pre-deploy (aún no existe)
DEPLOY COMMAND: generado, **no ejecutado**
POST-DEPLOY TESTS: listados, **no ejecutados**

GO BLOCKERS:

1. Autorización humana de ejecución ausente.
2. Fresh backup pre-deploy no creado / no verificado (`pg_restore --list`, tar, SHA256, filestore).
3. NCF oficial incompleto para varias operaciones emitidas (B11 vencido salvo BLU; B01 PIN/DOM vencidos; B17 ausente; DOR B04/B13 con 1 número; BLU B15 agotado).
4. Criterio GO «git clean/known» en host: no hay checkout git; el sync debe ser copia exacta de tres directorios desde `1599d13`.

WARNINGS:

- `justech_sale_purchase_trace` FILE 19.0.1.2.10 vs INSTALLED 19.0.1.2.11 — no tocar.
- `account.code` / `code_store` = False en el plan l10n_do Odoo 19 (CODE=EMPTY).
- Flags de aprobación de compañía hoy True; el overlay 19.0.1.6.0 los pone False.
- `justech_alexander_microsoft_mail` se queda en 19.0.1.0.4 (fuera del `-u` autorizado).
- `16% ITBIS` existe solo como impuesto **purchase**, no sale.
- `web.base.url` = `http://doralexgroup.cloud` (público de aprobación ya es https).
- Proceso Odoo PROD corre como root dentro del contenedor; el `-u` propuesto usa uid `100:101` (usuario `odoo`).
- Backup `production_20260907_122013` y `/opt/odoo-backups/*20260827*` son históricos. **ROLLBACK PRIMARY = backup fresco aún no creado.**
- Rangos QA `9910xxxx` / `9911xxxx` cancelados existen: no reactivar, no copiar STAGING.

PROD TOUCHED: NO

READY TO EXECUTE DEPLOYMENT: **NO**

---

## 1. PRECHECK READ-ONLY PROD

| Dato | Valor real |
| --- | --- |
| hostname | `Doralexgroup` (`ssh doralex-server`) |
| Contenedor Odoo | `doralex-production-odoo` · healthy · image `doralex-odoo-enterprise:19.0.20260324` · Started `2026-09-07T20:52:56Z` · Up 8 days |
| Contenedor DB | `doralex-production-db` · healthy · `postgres:16` |
| Database | `doralex_prod` · `dbfilter = ^doralex_prod$` |
| Odoo | `Odoo Server 19.0-20260324` · módulo `base` 19.0.1.3 · Enterprise montado `/mnt/enterprise` |
| PostgreSQL | 16.15 (Debian 16.15-1.pgdg13+2) |
| CURRENT COMMIT | N/A — no hay `.git` en `/opt/doralex`, `/opt/doralex/production`, `/opt/doralex/production/custom-addons` |
| git status | N/A (sin repositorio en el host). Estado de archivos: manifiestos listados arriba |
| TARGET COMMIT | `1599d132ce019a7d3c47e6c722acbc9139c80759` |
| addons_path | `/mnt/custom-addons,/usr/lib/odoo/enterprise,/usr/lib/odoo/custom-addons` |
| Bind-mount overlay | `/opt/doralex/production/custom-addons` → `/mnt/custom-addons` **ro** |
| Filestore | `/var/lib/odoo/filestore/doralex_prod` · 63M · 816 archivos |
| workers | 4 · `max_cron_threads=2` |
| Usuario `-u` | contenedor `doralex-production-odoo` · `docker exec -u 100:101` · DB user `doralex_prod` vía `$USER`/`$PASSWORD` del env (no se documenta el secreto) |

Frozen (no tocar):

| Módulo | Archivo | DB |
| --- | --- | --- |
| justech_l10n_do_payments_withholding | 19.0.1.7.2 | 19.0.1.7.2 |
| justech_purchase_sale_margin_control | 19.0.8.29.38 | 19.0.8.29.38 |
| multi_invoice_manual_payment_prod | 19.0.1.5.4 | 19.0.1.5.4 |
| justech_sale_purchase_trace | 19.0.1.2.10 | **19.0.1.2.11** |

`-u` **no ejecutado**.

---

## 2. AUDITORÍA NCF PROD (rangos REALES)

No se creó ni copió nada. No se reactivaron cancelados. No se usaron rangos STAGING (`99114xxx` / `STAGING-UAT-NO-DGII-*`).

### 2.1 Rangos oficiales (excluye QA 991* cancelados)

| COMPANY | COMPANY_ID | TIPO | RANGO id | DESDE | HASTA | NEXT | ESTADO | VENCIMIENTO | AUTH | USO |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| BLUE ELITE | 8 | B01 | 31 | 1 | 15 | 1 | active | 2027-12-31 | 6005109961 | Ventas crédito fiscal |
| BLUE ELITE | 8 | B02 | 54 | 1 | 500 | 1 | active | 2099-12-31 | 6005109965 | Consumo |
| BLUE ELITE | 8 | B04 | 55 | 1 | 15 | 1 | active | 2099-12-31 | 6005109966 | Notas de crédito |
| BLUE ELITE | 8 | B11 | 56 | 1 | 5 | 1 | active | 2027-12-31 | 6005109962 | Compras emitidas informal |
| BLUE ELITE | 8 | B13 | 57 | 1 | 5 | 1 | active | 2027-12-31 | 6005109963 | Gastos menores emitidos |
| BLUE ELITE | 8 | B15 | 58 | 1 | 102 | 102 | active | 2027-12-31 | 6005109964 | Régimen especial — **AGOTADO** (next=hasta) |
| PIÑARIA | 9 | B01 | 36 | 6 | 10 | 9 | **expired** | 2025-12-31 | 4004196168 | Ventas B01 — **no usable** |
| PIÑARIA | 9 | B04 | 37 | 1 | 10 | 1 | active | 2099-12-31 | 3003875941 | Notas de crédito |
| PIÑARIA | 9 | B11 | 38 | 1 | 5 | 1 | **expired** | 2025-12-31 | 4004017760 | Informal emitido — **no usable** |
| PIÑARIA | 9 | B13 | 39 | 18 | 27 | 18 | active | 2026-12-31 | 5004579811 | Gastos menores |
| PIÑARIA | 9 | B15 | 29 | 93 | 103 | 93 | active | 2028-01-01 | 6005464536 | Régimen especial |
| DOMINION | 10 | B01 | 40 | 91 | 100 | 94 | **expired** | 2025-12-31 | 4004196172 | Ventas B01 — **no usable** |
| DOMINION | 10 | B02 | 41 | 1 | 500 | 1 | active | 2099-12-31 | 2003411708 | Consumo |
| DOMINION | 10 | B04 | 42 | 1 | 50 | 1 | active | 2099-12-31 | 2003411709 | Notas de crédito |
| DOMINION | 10 | B11 | 43 | 1 | 10 | 1 | **expired** | 2025-12-31 | 4003974422 | Informal emitido — **no usable** |
| DOMINION | 10 | B13 | 44 | 57 | 96 | 57 | active | 2026-12-31 | 5004440728 | Gastos menores |
| DOMINION | 10 | B15 | 30 | 140 | 163 | 145 | active | 2026-12-31 | 5004909756 | Régimen especial |
| DORALEX | 11 | B01 | 25 | 52 | 87 | 54 | active | 2027-12-31 | 6005372487 | Ventas crédito fiscal |
| DORALEX | 11 | B02 | 32 | 1 | 10 | 1 | active | 2099-12-31 | 1002741918 | Consumo |
| DORALEX | 11 | B04 | 33 | 502 | 502 | 502 | active | 2099-12-31 | 6005472045 | NC — **1 número** |
| DORALEX | 11 | B11 | 34 | 1 | 5 | 1 | **expired** | 2024-12-31 | 3003703072 | Informal emitido — **no usable** |
| DORALEX | 11 | B13 | 35 | 11 | 17 | 17 | active | 2027-12-31 | 6005031086 | Gastos menores — **1 número** |
| DORALEX | 11 | B15 | 26 | 141 | 160 | 152 | active | 2027-12-31 | 6005109381 | Régimen especial |
| MAYUMA | 12 | B01 | 45 | 6 | 10 | 6 | active | 2026-12-31 | 5004743980 | Ventas crédito fiscal |
| MAYUMA | 12 | B02 | 46 | 1 | 100 | 1 | active | 2099-12-31 | 3003508919 | Consumo |
| MAYUMA | 12 | B04 | 47 | 1 | 5 | 1 | active | 2099-12-31 | 6005472703 | Notas de crédito |
| MAYUMA | 12 | B11 | 48 | 1 | 5 | 1 | **expired** | 2025-12-31 | 4003974363 | Informal emitido — **no usable** |
| MAYUMA | 12 | B13 | 49 | 1 | 5 | 1 | **expired** | 2025-12-31 | 4003974364 | Gastos menores — **no usable** |
| MAYUMA | 12 | B15 | 27 | 109 | 118 | 111 | active | 2026-12-31 | 5004942280 | Régimen especial |
| REMPART | 13 | B01 | 50 | 16 | 30 | 16 | active | 2026-12-31 | 5004684660 | Ventas crédito fiscal |
| REMPART | 13 | B04 | 51 | 1 | 5 | 1 | active | 2099-12-31 | 6005474633 | Notas de crédito |
| REMPART | 13 | B11 | 52 | 1 | 5 | 1 | **expired** | 2025-12-31 | 4004004172 | Informal emitido — **no usable** |
| REMPART | 13 | B13 | 53 | 6 | 12 | 6 | **expired** | 2025-12-31 | 4004004197 | Gastos menores — **no usable** |
| REMPART | 13 | B15 | 28 | 106 | 113 | 111 | active | 2027-01-03 | 5004942351 | Régimen especial |

B17: **ninguna empresa tiene rango.** No se propone crear 9911xxxx ni copiar UAT.

### 2.2 QA cancelados (NO TOCAR)

Todas las compañías 8–13 tienen B01 `99100xxx` y B04 `99110xxx` en `cancelled` (auth `DX-TEST-NO-DGII-360`). No reactivar. No copiar next. No usar en smoke PROD.

### 2.3 Qué configuración REAL necesitaría cada empresa

No se asume que todas necesiten todos los tipos. Solo si la operación está habilitada:

| Operación | Requisito de rango de la compañía | Quién lo tiene hoy |
| --- | --- | --- |
| Factura cliente B01 | B01 active no vencido con next ≤ hasta | BLU, DOR, MAY, REM. **PIN y DOM: no** |
| Factura cliente B02 | B02 active | BLU, DOM, DOR, MAY. PIN/REM: no hay B02 |
| Nota de crédito B04 | B04 active | Todas. **DOR: 1 comprobante** |
| Factura proveedor **recibida** (B01 del vendor LATAM) | No usa rango de la compañía | Todas (modo received) |
| Factura proveedor **emitida** informal B11 | B11 active | **Solo BLU**. PIN/DOM/DOR/MAY/REM vencidos |
| Gastos menores emitidos B13 | B13 active | BLU, PIN, DOM, DOR (1). **MAY/REM vencidos** |
| Régimen especial B15 | B15 active con cupo | PIN/DOM/DOR/MAY/REM. **BLU agotado** |
| Pagos al exterior B17 | B17 active | **Nadie** — no crear hasta autorización DGII real |

El `-u` de overlay **no copia ni crea rangos**. Smoke post-deploy debe usar solo secuencias reales activas (p. ej. DOR B01, BLU B11, B04 no-UAT).

---

## 3. CUENTAS DE RETENCIONES PROD

Resolución auditada: `company_id` + `account.code` + `account_type`. El nombre es referencia humana.

Hallazgo: en este plan l10n_do Odoo 19, `account.code` y `code_store` son `False` (CODE=EMPTY). La única clave única real es `company_ids` (exactamente una empresa) + `account_type=liability_non_current` + nombre del plan.

Ninguna cuenta requerida está compartida con otra empresa (`shared_other=[]`).
**MISSING ACCOUNT: 0.** No se crea ninguna cuenta.

El overlay `dx_sync_2026_catalog` (solo si se autoriza el `-u`) busca `company_ids` + nombre; `tax_id=False` (no auto-aplica).

### 3.1 Cuentas existentes por compañía (ids reales)

| COMPANY_ID | KEY | ACC_ID | CODE | NAME | TYPE |
| --- | --- | --- | --- | --- | --- |
| 8 | ISR_OTHER | 1897 | EMPTY | Other Withholdings (N07-07) | liability_non_current |
| 8 | ISR_OTHER_ALT | 1898 | EMPTY | Other Withholdings | liability_non_current |
| 8 | ISR_RENT | 1891 | EMPTY | ISR withheld on rent paid to individuals | liability_non_current |
| 8 | ISR_INT | 1894 | EMPTY | ISR withheld on interest paid | liability_non_current |
| 8 | ISR_INT_EXT | 1893 | EMPTY | ISR Withheld on Interest Paid Abroad | liability_non_current |
| 8 | ISR_EXT | 1896 | EMPTY | ISR Withheld on Remittances Abroad (L253-12) | liability_non_current |
| 8 | ITBIS_PJ | 1885 | EMPTY | ITBIS Withheld from Legal Entity (N02-05) | liability_non_current |
| 8 | ITBIS_PF | 1886 | EMPTY | ITBIS Withheld from Individuals (R293-11) | liability_non_current |
| 8 | ITBIS_ESFL | 1887 | EMPTY | ITBIS Withheld from Non-Profit Entities (N01-11) | liability_non_current |
| 8 | ITBIS_PROF | 1888 | EMPTY | ITBIS Withheld for Professional Services (N02-05) | liability_non_current |
| 8 | ITBIS_INF | 1889 | EMPTY | ITBIS Withheld from Informal Goods (N08-10) | liability_non_current |
| 9 | ISR_OTHER | 2185 | EMPTY | Other Withholdings (N07-07) | liability_non_current |
| 9 | ISR_OTHER_ALT | 2186 | EMPTY | Other Withholdings | liability_non_current |
| 9 | ISR_RENT | 2179 | EMPTY | ISR withheld on rent paid to individuals | liability_non_current |
| 9 | ISR_INT | 2182 | EMPTY | ISR withheld on interest paid | liability_non_current |
| 9 | ISR_INT_EXT | 2181 | EMPTY | ISR Withheld on Interest Paid Abroad | liability_non_current |
| 9 | ISR_EXT | 2184 | EMPTY | ISR Withheld on Remittances Abroad (L253-12) | liability_non_current |
| 9 | ITBIS_PJ | 2173 | EMPTY | ITBIS Withheld from Legal Entity (N02-05) | liability_non_current |
| 9 | ITBIS_PF | 2174 | EMPTY | ITBIS Withheld from Individuals (R293-11) | liability_non_current |
| 9 | ITBIS_ESFL | 2175 | EMPTY | ITBIS Withheld from Non-Profit Entities (N01-11) | liability_non_current |
| 9 | ITBIS_PROF | 2176 | EMPTY | ITBIS Withheld for Professional Services (N02-05) | liability_non_current |
| 9 | ITBIS_INF | 2177 | EMPTY | ITBIS Withheld from Informal Goods (N08-10) | liability_non_current |
| 10 | ISR_OTHER | 2473 | EMPTY | Other Withholdings (N07-07) | liability_non_current |
| 10 | ISR_OTHER_ALT | 2474 | EMPTY | Other Withholdings | liability_non_current |
| 10 | ISR_RENT | 2467 | EMPTY | ISR withheld on rent paid to individuals | liability_non_current |
| 10 | ISR_INT | 2470 | EMPTY | ISR withheld on interest paid | liability_non_current |
| 10 | ISR_INT_EXT | 2469 | EMPTY | ISR Withheld on Interest Paid Abroad | liability_non_current |
| 10 | ISR_EXT | 2472 | EMPTY | ISR Withheld on Remittances Abroad (L253-12) | liability_non_current |
| 10 | ITBIS_PJ | 2461 | EMPTY | ITBIS Withheld from Legal Entity (N02-05) | liability_non_current |
| 10 | ITBIS_PF | 2462 | EMPTY | ITBIS Withheld from Individuals (R293-11) | liability_non_current |
| 10 | ITBIS_ESFL | 2463 | EMPTY | ITBIS Withheld from Non-Profit Entities (N01-11) | liability_non_current |
| 10 | ITBIS_PROF | 2464 | EMPTY | ITBIS Withheld for Professional Services (N02-05) | liability_non_current |
| 10 | ITBIS_INF | 2465 | EMPTY | ITBIS Withheld from Informal Goods (N08-10) | liability_non_current |
| 11 | ISR_OTHER | 2761 | EMPTY | Other Withholdings (N07-07) | liability_non_current |
| 11 | ISR_OTHER_ALT | 2762 | EMPTY | Other Withholdings | liability_non_current |
| 11 | ISR_RENT | 2755 | EMPTY | ISR withheld on rent paid to individuals | liability_non_current |
| 11 | ISR_INT | 2758 | EMPTY | ISR withheld on interest paid | liability_non_current |
| 11 | ISR_INT_EXT | 2757 | EMPTY | ISR Withheld on Interest Paid Abroad | liability_non_current |
| 11 | ISR_EXT | 2760 | EMPTY | ISR Withheld on Remittances Abroad (L253-12) | liability_non_current |
| 11 | ITBIS_PJ | 2749 | EMPTY | ITBIS Withheld from Legal Entity (N02-05) | liability_non_current |
| 11 | ITBIS_PF | 2750 | EMPTY | ITBIS Withheld from Individuals (R293-11) | liability_non_current |
| 11 | ITBIS_ESFL | 2751 | EMPTY | ITBIS Withheld from Non-Profit Entities (N01-11) | liability_non_current |
| 11 | ITBIS_PROF | 2752 | EMPTY | ITBIS Withheld for Professional Services (N02-05) | liability_non_current |
| 11 | ITBIS_INF | 2753 | EMPTY | ITBIS Withheld from Informal Goods (N08-10) | liability_non_current |
| 12 | ISR_OTHER | 3049 | EMPTY | Other Withholdings (N07-07) | liability_non_current |
| 12 | ISR_OTHER_ALT | 3050 | EMPTY | Other Withholdings | liability_non_current |
| 12 | ISR_RENT | 3043 | EMPTY | ISR withheld on rent paid to individuals | liability_non_current |
| 12 | ISR_INT | 3046 | EMPTY | ISR withheld on interest paid | liability_non_current |
| 12 | ISR_INT_EXT | 3045 | EMPTY | ISR Withheld on Interest Paid Abroad | liability_non_current |
| 12 | ISR_EXT | 3048 | EMPTY | ISR Withheld on Remittances Abroad (L253-12) | liability_non_current |
| 12 | ITBIS_PJ | 3037 | EMPTY | ITBIS Withheld from Legal Entity (N02-05) | liability_non_current |
| 12 | ITBIS_PF | 3038 | EMPTY | ITBIS Withheld from Individuals (R293-11) | liability_non_current |
| 12 | ITBIS_ESFL | 3039 | EMPTY | ITBIS Withheld from Non-Profit Entities (N01-11) | liability_non_current |
| 12 | ITBIS_PROF | 3040 | EMPTY | ITBIS Withheld for Professional Services (N02-05) | liability_non_current |
| 12 | ITBIS_INF | 3041 | EMPTY | ITBIS Withheld from Informal Goods (N08-10) | liability_non_current |
| 13 | ISR_OTHER | 3337 | EMPTY | Other Withholdings (N07-07) | liability_non_current |
| 13 | ISR_OTHER_ALT | 3338 | EMPTY | Other Withholdings | liability_non_current |
| 13 | ISR_RENT | 3331 | EMPTY | ISR withheld on rent paid to individuals | liability_non_current |
| 13 | ISR_INT | 3334 | EMPTY | ISR withheld on interest paid | liability_non_current |
| 13 | ISR_INT_EXT | 3333 | EMPTY | ISR Withheld on Interest Paid Abroad | liability_non_current |
| 13 | ISR_EXT | 3336 | EMPTY | ISR Withheld on Remittances Abroad (L253-12) | liability_non_current |
| 13 | ITBIS_PJ | 3325 | EMPTY | ITBIS Withheld from Legal Entity (N02-05) | liability_non_current |
| 13 | ITBIS_PF | 3326 | EMPTY | ITBIS Withheld from Individuals (R293-11) | liability_non_current |
| 13 | ITBIS_ESFL | 3327 | EMPTY | ITBIS Withheld from Non-Profit Entities (N01-11) | liability_non_current |
| 13 | ITBIS_PROF | 3328 | EMPTY | ITBIS Withheld for Professional Services (N02-05) | liability_non_current |
| 13 | ITBIS_INF | 3329 | EMPTY | ITBIS Withheld from Informal Goods (N08-10) | liability_non_current |

### 3.2 Mapeo propuesto DX-* → cuenta (todas las compañías 8–13)

| COMPANY_ID | RULE CODE | ACCOUNT CODE | ACCOUNT NAME | ACCOUNT TYPE | EXISTS | PROPOSED ACTION |
| --- | --- | --- | --- | --- | --- | --- |
| 8–13 | DX-ISR-ESTADO-5 | EMPTY | Other Withholdings (N07-07) | liability_non_current | YES | MAP on `-u` |
| 8–13 | DX-ISR-PROF-PF-15 | EMPTY | Other Withholdings (N07-07) | liability_non_current | YES | MAP on `-u` |
| 8–13 | DX-ISR-TEC-PF-15 | EMPTY | Other Withholdings (N07-07) | liability_non_current | YES | MAP on `-u` |
| 8–13 | DX-ISR-ALQ-PF-15 | EMPTY | ISR withheld on rent paid to individuals | liability_non_current | YES | MAP on `-u` |
| 8–13 | DX-ITBIS-30-PJ | EMPTY | ITBIS Withheld from Legal Entity (N02-05) | liability_non_current | YES | MAP on `-u` |
| 8–13 | DX-ITBIS-100-PF | EMPTY | ITBIS Withheld from Individuals (R293-11) | liability_non_current | YES | MAP on `-u` |
| 8–13 | DX-ITBIS-100-SEG | EMPTY | ITBIS Withheld for Professional Services (N02-05) | liability_non_current | YES | MAP on `-u` |
| 8–13 | DX-ITBIS-100-ESFL | EMPTY | ITBIS Withheld from Non-Profit Entities (N01-11) | liability_non_current | YES | MAP on `-u` |
| 8–13 | DX-ITBIS-100-INF | EMPTY | ITBIS Withheld from Informal Goods (N08-10) | liability_non_current | YES | MAP on `-u` |
| 8–13 | DX-ISR-DIV-10 | EMPTY | Other Withholdings | liability_non_current | YES | MAP on `-u` |
| 8–13 | DX-ISR-INT-PF-10 | EMPTY | ISR withheld on interest paid | liability_non_current | YES | MAP on `-u` |
| 8–13 | DX-ISR-INT-EXT-10 | EMPTY | ISR Withheld on Interest Paid Abroad | liability_non_current | YES | MAP on `-u` |
| 8–13 | DX-ISR-EXT-REG-15 | EMPTY | ISR Withheld on Remittances Abroad (L253-12) | liability_non_current | YES | MAP on `-u` |
| 8–13 | DX-ISR-EXT-SW-15 | EMPTY | ISR Withheld on Remittances Abroad (L253-12) | liability_non_current | YES | MAP on `-u` |
| 8–13 | DX-ISR-EXT-ADS-15 | EMPTY | ISR Withheld on Remittances Abroad (L253-12) | liability_non_current | YES | MAP on `-u` |
| 8–13 | DX-ISR-EXT-DATA-15 | EMPTY | ISR Withheld on Remittances Abroad (L253-12) | liability_non_current | YES | MAP on `-u` |
| 8–13 | DX-ISR-EXT-27 | EMPTY | ISR Withheld on Remittances Abroad (L253-12) | liability_non_current | YES | MAP on `-u` |
| 8–13 | DX-ISR-PREMIO-25 | EMPTY | Other Withholdings | liability_non_current | YES | MAP on `-u` |
| 8–13 | DX-ISR-OTRAS-15 | EMPTY | Other Withholdings (N07-07) | liability_non_current | YES | MAP on `-u` |

MISSING ACCOUNT: **ninguna**. No crear cuentas.

---

## 4. CATÁLOGO DX-* STAGING vs PROD

STAGING: 19 reglas, `active=True`, `tax_id=False` (selection-only).
PROD: `DX_COUNT 0`.

| RULE | STAGING | PROD | ACTION |
| --- | --- | --- | --- |
| DX-ISR-ALQ-PF-15 | 15% untaxed · auto_tax=NO | ausente | CREATE |
| DX-ISR-DIV-10 | 10% untaxed · auto_tax=NO | ausente | CREATE |
| DX-ISR-ESTADO-5 | 5% untaxed · auto_tax=NO | ausente | CREATE |
| DX-ISR-EXT-27 | 27% untaxed · auto_tax=NO | ausente | CREATE |
| DX-ISR-EXT-ADS-15 | 15% untaxed · auto_tax=NO | ausente | CREATE |
| DX-ISR-EXT-DATA-15 | 15% untaxed · auto_tax=NO | ausente | CREATE |
| DX-ISR-EXT-REG-15 | 15% untaxed · auto_tax=NO | ausente | CREATE |
| DX-ISR-EXT-SW-15 | 15% untaxed · auto_tax=NO | ausente | CREATE |
| DX-ISR-INT-EXT-10 | 10% untaxed · auto_tax=NO | ausente | CREATE |
| DX-ISR-INT-PF-10 | 10% untaxed · auto_tax=NO | ausente | CREATE |
| DX-ISR-OTRAS-15 | 15% untaxed · auto_tax=NO | ausente | CREATE |
| DX-ISR-PREMIO-25 | 25% untaxed · auto_tax=NO | ausente | CREATE |
| DX-ISR-PROF-PF-15 | 15% untaxed · auto_tax=NO | ausente | CREATE |
| DX-ISR-TEC-PF-15 | 15% × 20% presunta · auto_tax=NO | ausente | CREATE |
| DX-ITBIS-100-ESFL | 100% base=itbis · auto_tax=NO | ausente | CREATE |
| DX-ITBIS-100-INF | 100% base=itbis · auto_tax=NO | ausente | CREATE |
| DX-ITBIS-100-PF | 100% base=itbis · auto_tax=NO | ausente | CREATE |
| DX-ITBIS-100-SEG | 100% base=itbis · auto_tax=NO | ausente | CREATE |
| DX-ITBIS-30-PJ | 30% base=itbis · auto_tax=NO | ausente | CREATE |

Legacy (KEEP — no archivar, no modificar, no cambiar defaults):

| Impuesto | Compañías 8–13 | ACTION |
| --- | --- | --- |
| `-10% ISR Fee` | active purchase | KEEP |
| `-10% ISR Rent.` | active purchase | KEEP |
| `-2% ISR (N07-07)` | active purchase | KEEP |
| `-27% ISR (L253-12)` | active purchase | KEEP |

DX-* **no se aplica automáticamente**: `tax_id=False`, selección en wizard. No ejecutado todavía.

---

## 5. APROBACIONES

Estado actual PROD (antes del update):

| Flag | Valor |
| --- | --- |
| `justech_alexander.approval_flow_enabled` | False (parámetro) |
| `justech_approval_sale_enabled` compañías 8–13 | **True** |
| `justech_approval_purchase_enabled` 8–13 | **True** |
| `justech_approval_invoice_enabled` 8–13 | **True** |
| `justech.approval.request` | 1 registro |
| `justech.approval.user.rule` | 6 reglas |
| Módulo | `justech_approval_flow` 19.0.1.3.8 instalado |

Después del `-u` autorizado, migración `justech_alexander_ux/migrations/19.0.1.6.0/end-apply_catalog.py` llama `apply_approval_overlay`:

- pone los tres flags de compañía en **False**
- deja el módulo instalado
- no borra requests, chatter ni reglas
- mueve el menú a «Aprobaciones (histórico)»

Resultado esperado:

APPROVAL FLOW = OFF
SALES CONFIRM BLOCKED BY APPROVAL: **NO**

(`sale.order._justech_sale_approval_required` retorna False si `justech_approval_sale_enabled` es False.)

No desinstalar el módulo.

---

## 6. PADRÓN DGII

| Check | Valor actual | Tras `-u` |
| --- | --- | --- |
| PADRON | param `justech_alexander.dgii_padron_enabled` False | OFF (`apply_padron_disabled`) |
| CRON | id 31 `active=False`; config `auto_update_enabled=False` | OFF |
| ROWS | 0 | no relevante |
| PARTNER BLOCK | overlay base 19.0.1.0.7 omite exigencia de padrón | NO |
| INVOICE BLOCK | mismos marcadores + `validate_before_post` | NO |

No descargar. No importar. No sincronizar.

Partners: 5 `confirmed_history`, 46 `pending_new`, 1 `validated_padron`. No bloquean posteo tras overlay base.

---

## 7. EMAIL (READ-ONLY)

SMTP_COUNT = 0. FETCH_COUNT = 0.
Graph: secretos en `/opt/doralex/secrets/microsoft` montado `/mnt/ms-graph` ro (`DX_MS_GRAPH_DIR`). Archivos presentes (nombres, no secretos): `client_id`, `tenant_id`, `thumbprint`, `app.crt`, `app.cer`, `app.pfx`, `organization`, `meta.json`, y un `.pass` por mailbox `administracion@` de las 6 empresas.
Módulo instalado: `justech_alexander_microsoft_mail` **19.0.1.0.4** (target repo 19.0.1.0.5 — **fuera** del `-u` autorizado).
Alias domains: inversionesdoralex.com, pinariagroup.com, dominion-business.com, elmayuma.com, rempartgroup.com, blueelite.net.
`mail.catchall.domain` = `doralexgroup.cloud`.

| COMPANY | SMTP/GRAPH | MAILBOX | FROM DOMAIN | STATUS | ACTION REQUIRED |
| --- | --- | --- | --- | --- | --- |
| BLUE ELITE (8) | GRAPH (sin SMTP) | administracion@blueelite.net | blueelite.net | mailbox+alias+credencial presentes | No cambiar credenciales. Envío controlado solo si se autoriza el GO |
| PIÑARIA (9) | GRAPH | administracion@pinariagroup.com | pinariagroup.com | idem | idem |
| DOMINION (10) | GRAPH | administracion@dominion-business.com | dominion-business.com | idem | idem |
| DORALEX (11) | GRAPH | administracion@inversionesdoralex.com | inversionesdoralex.com | idem | idem |
| MAYUMA (12) | GRAPH | administracion@elmayuma.com | elmayuma.com | idem | idem |
| REMPART (13) | GRAPH | administracion@rempartgroup.com | rempartgroup.com | idem | idem |

EMAIL LIVE listo antes del GO: **configuración entendida; envío live no re-probado en este pre-flight.** Histórico 2026-08-29: Graph 6/6 a buzón controlado. No modificar credenciales ahora.

---

## 8. BACKUP PRE-DEPLOY (diseñado, NO EJECUTADO)

ROLLBACK PRIMARY de **este** deployment = backup creado inmediatamente antes del deploy.
El de 2026-08-27 (`/opt/odoo-backups/prod-release-B-margins-POST-20260827_134919` y `production_20260827_162032`) se conserva como histórico. **No es el rollback principal.**
Último backup oficial existente: `/opt/doralex/backups/production/production_20260907_122013/` (db.dump 20M, filestore 22M). Insuficiente como primary de este release.

### 8.1 Comando propuesto (NO EJECUTAR hasta autorización)

```bash
# En Doralexgroup, como root operativo:
TS="$(date +%Y%m%d_%H%M%S)"
DEST="/opt/doralex/backups/prod/pre_alexander_release_${TS}"
mkdir -p /opt/doralex/backups/prod

bash /opt/doralex/scripts/backup.sh production
# Crea /opt/doralex/backups/production/production_${TS}/
# Incluye: db.dump (pg_dump -Fc doralex_prod), filestore.tar.gz,
# custom-addons.tar.gz, config.tar.gz, odoo.conf, docker-compose.yml, env.backup,
# SHA256SUMS, MANIFEST. Llama verify_backup.sh.

LATEST="$(ls -1d /opt/doralex/backups/production/production_* | tail -1)"
cp -a "${LATEST}" "${DEST}"

# Metadatos extra de este release (no secretos):
{
  echo "target_commit=1599d132ce019a7d3c47e6c722acbc9139c80759"
  echo "current_commit=N/A_no_git_on_host"
  echo "justech_alexander_base_file=19.0.1.0.5"
  echo "justech_alexander_ux_file=19.0.1.4.0"
  echo "justech_alexander_reports_file=19.0.3.8.5"
  echo "target_base=19.0.1.0.7"
  echo "target_ux=19.0.1.6.0"
  echo "target_reports=19.0.3.9.1"
  echo "db=doralex_prod"
  echo "container=doralex-production-odoo"
} > "${DEST}/RELEASE_META"

# Validaciones obligatorias:
docker exec -i doralex-production-db pg_restore --list < "${DEST}/db.dump" | head
tar -tzf "${DEST}/filestore.tar.gz" | head
tar -tzf "${DEST}/custom-addons.tar.gz" | head
( cd "${DEST}" && sha256sum -c SHA256SUMS )
du -h "${DEST}/db.dump" "${DEST}/filestore.tar.gz" "${DEST}/custom-addons.tar.gz"
test -s "${DEST}/filestore.tar.gz"
# Filestore vivo debe existir antes de cortar:
docker exec doralex-production-odoo bash -lc 'test -d /var/lib/odoo/filestore/doralex_prod && du -sh /var/lib/odoo/filestore/doralex_prod'
bash /opt/doralex/scripts/verify_backup.sh "${DEST}"
```

GO de backup solo si: `pg_restore --list` OK, tar lista archivos, SHA256 OK, tamaños >0, filestore presente.

---

## 9. MÓDULOS AUTORIZABLES

Solo:

- `justech_alexander_base` 19.0.1.0.7
- `justech_alexander_ux` 19.0.1.6.0
- `justech_alexander_reports` 19.0.3.9.1

No tocar: márgenes, traza, pagos frozen, core Odoo, otros Justech, `justech_alexander_microsoft_mail`.
**Nunca `-u all`.**

UX `depends` incluye pagos/traza/approval: `-u` listado **no** actualiza dependencias no nombradas.

---

## 10. COMANDO PROPUESTO — NO EJECUTAR

Valores reales: contenedor `doralex-production-odoo`, DB `doralex_prod`, usuario odoo `100:101`, host DB `$HOST` (compose: `db`), user `$USER` (`doralex_prod`). Password solo desde env del contenedor.

```bash
docker exec -u 100:101 doralex-production-odoo bash -lc \
  'python3 /usr/bin/odoo -d doralex_prod --db_host="$HOST" --db_port=5432 --db_user="$USER" --db_password="$PASSWORD" \
   -u justech_alexander_base,justech_alexander_ux,justech_alexander_reports \
   --stop-after-init --no-http'
echo "EXIT:$?"
```

Luego (solo si EXIT 0):

```bash
docker restart doralex-production-odoo
```

Nunca `-u all`. Nunca incluir frozen modules.

---

## 11. ORDEN DEL DEPLOYMENT (cuando se autorice)

1. **Maintenance/preparation.** Aviso a usuarios. Confirmar `doralex-production-odoo` healthy. Confirmar que el working tree de deploy es exactamente `1599d13` y solo los tres directorios overlay. Quitar cualquier `*.bak_*` de `custom-addons` (un bak previo rompió `-u` en STAGING).
2. **Fresh backup.** Ejecutar la sección 8. No usar el backup de 2026-08-27 como primary.
3. **Verify backup.** `verify_backup.sh` + `pg_restore --list` + `tar -tzf` + `sha256sum -c` + tamaños + filestore. STOP si alguno falla.
4. **Sync exact commit.** Host sin git. Copiar **solo**:

   ```bash
   # Desde el repo en 1599d132ce019a7d3c47e6c722acbc9139c80759 — NO EJECUTAR AHORA
   cd addons/alexander
   tar czf /tmp/alexander_overlay_1599d13.tgz \
     justech_alexander_base justech_alexander_ux justech_alexander_reports
   scp /tmp/alexander_overlay_1599d13.tgz doralex-server:/tmp/
   ssh doralex-server 'tar xzf /tmp/alexander_overlay_1599d13.tgz -C /opt/doralex/production/custom-addons'
   # Verificar manifiestos en disco = 19.0.1.0.7 / 19.0.1.6.0 / 19.0.3.9.1
   ```

   No rsync del árbol completo. No tocar frozen.
5. **Update three modules.** Poner workers en mantenimiento (stop odoo → start → `-u` de la sección 10, o `-u` con el servicio arriba y aceptar un segundo proceso corto). Comando exacto de la sección 10.
6. **Check exit code.** Debe ser 0. Si ≠0: no restart de negocio; rollback (sección 14).
7. **Restart service.** `docker restart doralex-production-odoo`. Esperar healthcheck.
8. **Check logs.** `/opt/doralex/production/logs/odoo.log` y `docker logs --tail 200 doralex-production-odoo`. STOP ante errores de registry / ParseError / FileNotFoundError de módulo.
9. **Fiscal/configuration verification.** Flags aprobación False; padrón/cron OFF; 19 DX-* con cuentas de la misma empresa; legacy -10/-2/-27 intactos; NCF reales sin 9911xxxx nuevos; versiones DB = target.
10. **Smoke tests.** Sección 12, solo rangos reales.
11. **GO / rollback.** GO solo si todos los criterios de la sección 13 pasan. Si no: restore del backup fresco.

---

## 12. SMOKE TEST PROD (después, si se autoriza)

VENTAS

- Crear cotización (compañía con B01 activo, p. ej. DOR 11).
- Descripción / Propet.
- Confirmar **sin** approval (`justech_approval_state` no bloquea).

FACTURACIÓN

- Crear draft.
- Cancelar draft con grupo Billing (overlay recovery no aplica a draft).
- Posted sigue protegido (no reset sin recovery).

ITBIS

- 18% sale/purchase existente en 8–13.
- 16% **disponible como purchase** (`16% ITBIS`). No hay 16% sale.
- **NO** asignación masiva.

RETENCIONES (sin crear transacciones innecesarias si la config basta)

- Catálogo: profesional 15%, técnico 15×20, ITBIS 30%, ITBIS 100%.
- Cuentas por empresa (sección 3). Wizard selection-only.

NCF

- Solo secuencias reales activas. No 9911. No STAGING-UAT.

PROFORMA / CONDUCE

- Render.

MULTIEMPRESA

- Logo / firma / company del documento, no de la compañía activa.

EMAIL

- Render. Envío controlado solo si el GO de correo está autorizado.

---

## 13. GO / NO-GO

GO únicamente si:

- fresh backup PASS
- DB backup PASS (`pg_restore --list`)
- filestore PASS
- git/host known (tres manifiestos exactos; sin suciedad `*.bak_*` en addons)
- modules exact 19.0.1.0.7 / 19.0.1.6.0 / 19.0.3.9.1
- account mapping PASS
- NCF audit PASS **y** el smoke usa solo rangos activos reales
- approval OFF
- padron OFF
- email configuration understood
- no missing mandatory accounts
- no missing mandatory fiscal range **for the operations you will run at GO**

NO-GO si:

- alguna cuenta DX apunta a otra empresa
- NCF inconsistente respecto a la operación intentada
- se requiere `-u all`
- hay modificaciones no identificadas en PROD
- backup no verificable
- filestore no respaldado
- la migración intenta copiar rangos UAT (el código actual **no** lo hace)
- approval vuelve a activarse
- padrón se activa
- aparecen errores de registry

Estado **ahora** (pre-autorización): **NO-GO para ejecutar.**

---

## 14. ROLLBACK (contra el backup fresco — NO EJECUTAR salvo fallo real)

`/opt/doralex/scripts/restore.sh` **no** es el procedimiento aprobado de este release:
verifica el backup con Odoo arriba, no drena backends `odoo-*`, y extrae
filestore con `docker exec` sobre el contenedor ya `stopped`.

Orden aprobado (detalle en `docs/ALEXANDERGROUP_PRODUCTION_PREGO.md`):
mantenimiento → `docker stop` → cero conexiones Odoo a `doralex_prod` →
verificar backup → `pg_restore` → filestore → custom-addons → start → logs → smoke.

No usar: restore DB mientras Odoo sigue conectado.
`restore.sh` sigue exigiendo `CONFIRM=yes ALLOW_PROD=yes` si alguien lo invoca;
este release no lo usa como procedimiento aprobado.

Tras rollback esperado: base 19.0.1.0.5, ux 19.0.1.4.0, reports 19.0.3.8.5.
No usar el backup 2026-08-27 como primary de este release.

---

## 15. CIERRE

PRODUCTION PRE-FLIGHT documentado.
PROD TOUCHED: NO
READY TO EXECUTE DEPLOYMENT: **NO**

DETENERSE hasta autorización expresa.
