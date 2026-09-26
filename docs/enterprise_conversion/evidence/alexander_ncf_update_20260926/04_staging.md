# 04 — Staging

DB: `doralex_ent_staging`. No facturas creadas. No `consume_next`.

## Apply

`NCF_APPLY_DRY=0` + `env.cr.commit()`. STOP = []. WRITES = DOR, MAY, REM.

Doralex B13: no existe rango oficial en staging. No se creó. Estado efectivo
`BLOCKED_PENDING_AUTHORIZATION`.

## QA lectura (verify + overlay preview)

| COMPANY | RANGE_FROM | RANGE_TO | LAST_USED | NEXT | EXPIRATION | AUTHORIZATION | ACTIVE | REMAINING | BALANCE |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Doralex | B1500000141 | B1500000160 | B1500000151 | B1500000152 | 2027-12-31 | 6005109381 | YES | 9 | WARNING |
| El Mayuma | B1500000109 | B1500000118 | B1500000112 | B1500000113 | 2026-12-31 | 5004942280 | YES | 6 | WARNING |
| Rempart | B1500000106 | B1500000113 | B1500000111 | B1500000112 | 2027-01-03 | 5004942351 | YES | 2 | CRITICAL |

`dx_preview_next_ncf()` devolvió esos next **sin** cambiar `next_sequence`.

Histórico B15 (posted) intacto: DOR max 151, MAY max 110, REM max 110.
152 / 113 / 112 no existen como documento.

`justech_alexander_base` 19.0.1.0.16. `-u justech_alexander_base` dirigido.
HTTP `/web/health` 200. Contenedor healthy.

**STAGING_NCF_QA = PASS**
