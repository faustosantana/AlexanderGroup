# 05 — Producción

Backup previo (obligatorio):

`/opt/odoo-backups/pre_ncf_b15_sequence_update_20260926_142408`

| Artefacto | Verificación |
| --- | --- |
| `db/doralex_prod.dump` | 27 117 541 bytes |
| `db/pg_restore.list` | 34 029 líneas · `pg_restore -l` OK |
| `filestore/odoo_data.tar` | 194M |
| `custom-addons/custom-addons.tar` | 19M |
| `config/odoo.conf` | presente |

**PRE_NCF_UPDATE_BACKUP = PASS**

No se restauró staging sobre prod.

## Apply

DRY: STOP = [] · WRITES DOR/MAY/REM.
LIVE: STOP = [] · WRITES DOR/MAY/REM · `env.cr.commit()`.

## QA lectura

| COMPANY | TYPE | RANGE_FROM | RANGE_TO | LAST_USED | NEXT | EXPIRATION | AUTHORIZATION | ACTIVE | REMAINING | BALANCE |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| INVERSIONES DORALEX | B15 | B1500000141 | B1500000160 | B1500000151 | B1500000152 | 2027-12-31 | 6005109381 | YES | 9 | WARNING |
| INVERSIONES EL MAYUMA | B15 | B1500000109 | B1500000118 | B1500000112 | B1500000113 | 2026-12-31 | 5004942280 | YES | 6 | WARNING |
| REMPART GROUP | B15 | B1500000106 | B1500000113 | B1500000111 | B1500000112 | 2027-01-03 | 5004942351 | YES | 2 | CRITICAL |

Doralex B13: `state=cancelled`, next display `B1300000017` **no activo**.
MAX_REAL B1300000016 intacto. B1300000017 no existe como documento.
**DORALEX_B13_STATUS = BLOCKED_PENDING_AUTHORIZATION**

Blue Elite B15 id 58: active, next 102, end 102. **UNCHANGED_BLOCKED**.
B17 count = 0. **UNCHANGED_NOT_CONFIGURED**.

Fingerprint `all_ranges` (46 rangos): solo 3 cambian
MAY B15 next 111→113, REM B15 next 111→112, DOR B13 active→cancelled.
Doralex B15 ya coincidía (141–160 next 152).

Histórico posted B15: DOR 151, MAY 110, REM 110. Ningún 152/113/112 emitido.

`justech_alexander_base` 19.0.1.0.16. HTTP 200. Contenedor healthy.

**PROD_NCF_QA = PASS**
**NCF_NUMBERS_CONSUMED_DURING_UPDATE = 0**
**CROSS_COMPANY_NCF_SEQUENCE = 0**
**HISTORICAL_NCF_CHANGED = 0**
**POSTED_MOVES_CHANGED = 0**
**NCF_DOCUMENTS_RENUMBERED = 0**
