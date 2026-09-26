# 02 — Estado previo (lectura ORM, sin consumo)

Auditoría 2026-09-26. IDs se reportan como hallazgo; los writes resuelven por
compañía + prefijo, nunca por ID de staging.

## Producción `doralex_prod`

| COMPANY | CURRENT_RANGE_FROM | CURRENT_RANGE_TO | CURRENT_LAST_USED | CURRENT_NEXT | CURRENT_EXPIRATION | CURRENT_AUTHORIZATION | CURRENT_ACTIVE | MAX_REAL_B15 | NEXT_EXISTS |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| INVERSIONES DORALEX | B1500000141 | B1500000160 | B1500000151 | B1500000152 | 2027-12-31 | 6005109381 | YES | B1500000151 | NO |
| INVERSIONES EL MAYUMA | B1500000109 | B1500000118 | B1500000110 (Odoo) | B1500000111 | 2026-12-31 | 5004942280 | YES | B1500000110 | NO |
| REMPART GROUP | B1500000106 | B1500000113 | B1500000110 (Odoo) | B1500000111 | 2027-01-03 | 5004942351 | YES | B1500000110 | NO |

### Histórico B15 real en `account.move` (excluye QA / 9910 / DX TEST)

- Doralex: 147, 148, 149, 150, **151**. No existe 152.
- El Mayuma: 109, **110**. No existen 111, 112, 113.
- Rempart: 106, 107, 108, 109, **110**. No existen 111, 112.

### Hueco papel / externo

La fuente autorizada declara último usado Mayuma **112** y Rempart **111**.
Esos NCF no están en Odoo (ni posted, draft, cancelled, ni `justech.do.ncf.consumption`).
Odoo emitiría el siguiente número de su contador (111) y colisionaría con la
autorización. El write avanza el next autorizado para no reutilizar esos números.
No se inventan documentos históricos.

### Doralex B13 (PROD)

- Rango oficial activo: start 11, end 17, next **17** (`B1300000017`), auth 6005031086.
- MAX_REAL = B1300000016 (posted). B1300000017 no existe.
- Inconsistente con NEEDS_DGII_CONFIRMATION. Se cerrará con `action_cancel()`.

### Blue Elite B15 (PROD)

- start 1, end 102, next 102, auth 6005109964, active, remaining 1.
- **No se toca.** `UNCHANGED_BLOCKED`.

### B17

- 0 rangos B17 en las 6 empresas. **No se crea.**

## Staging `doralex_ent_staging`

B15 DOR/MAY/REM: mismos rangos, next y MAX_REAL que producción (IDs distintos:
30 / 31 / 32). NEXT autorizado no existe.

Doralex B13: **0 rangos** en staging. Histórico posted B1300000016 existe.
No se crea rango. Queda no emitible por ausencia de rango activo.

Blue Elite B15 oficial: ausente en staging. No se inventa.
