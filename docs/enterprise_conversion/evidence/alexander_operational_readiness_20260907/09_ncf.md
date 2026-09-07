# 09 — NCF

Baseline opening: `NCF_SEQUENCE_AUDIT_TOTAL = 34` / `CORRECTED = 4` / `BLOCKED = 30`.
No se activaron los 30 bloqueados.

Rangos **vivos** en prod hoy: 16 (`justech.do.ncf.range`, company != 1).

## SAFE_ACTIVE (7) — incluye activación 2026-09-07 desde planilla Pendientes

| COMPANY | NCF_TYPE | AUTHORIZED_FROM | AUTHORIZED_TO | MAX_HISTORICAL | NEXT_CONFIGURED | ACTIVE | EVIDENCE | STATUS | REASON |
|---|---|---|---|---|---|---|---|---|---|
| DORALEX | B15 | 141 | 160 | B1500000151 | B1500000152 | YES | auth 6005109381 + CxC | SAFE_ACTIVE | next = max+1 dentro de rango |
| DORALEX | B01 | 52 | 87 | B0100000053 | B0100000054 | YES | auth 6005372487 + CxC | SAFE_ACTIVE | planilla B15 errónea ignorada; hist. 35-51 bajo rango |
| EL MAYUMA | B15 | 109 | 118 | B1500000110 | B1500000111 | YES | auth 5004942280 + CxC | SAFE_ACTIVE | |
| REMPART | B15 | 106 | 113 | B1500000110 | B1500000111 | YES | auth 5004942351 + CxC | SAFE_ACTIVE | |
| PIÑARIA | B15 | 93 | 103 | (sin CxC) | B1500000093 | YES | auth 6005464536 planilla | SAFE_ACTIVE | last 092 bajo rango; next = inicio |
| DOMINION | B15 | 140 | 163 | (sin CxC) | B1500000145 | YES | auth 5004909756 planilla | SAFE_ACTIVE | last 144 / next 145 |
| BLUE ELITE | B01 | 1 | 15 | (sin CxC) | B0100000001 | YES | auth 6005109961 planilla | SAFE_ACTIVE | B15 de Blue Elite sigue bloqueado |

## QA cancelados (12) — no son DGII

Todos `state=cancelled` auth `DX-TEST-NO-DGII-360` series 9910xxxx / 9911xxxx (B01 y B04 × 6). `STATUS = QA_CANCELLED`.

## Bloqueados / no creados como rango real (universo 30)

| COMPANY | NCF_TYPE | STATUS | REASON |
|---|---|---|---|
| DORALEX | B13 | BLOCKED_CONFLICT | max histórico B1300000016 > rango declarado B1300000011–B1300000015; no se inventó 0017 |
| DORALEX | B04 | BLOCKED_MISSING_AUTHORIZATION | planilla last 0501 bajo rango 0502–0502; sin histórico suficiente |
| PIÑARIA | B15 | BLOCKED_MISSING_AUTHORIZATION | last 092 bajo rango 93–103; sin CxC histórica |
| PIÑARIA | B01/B02/B04/B11/B13 | NOT_USED / BLOCKED_MISSING_AUTHORIZATION | sin evidencia DGII + sin histórico |
| DOMINION | todos | BLOCKED_MISSING_AUTHORIZATION | 0 SAFE_ACTIVE |
| EL MAYUMA | no-B15 | NOT_USED | no activar sin evidencia |
| REMPART | no-B15 | NOT_USED | no activar sin evidencia |
| BLUE ELITE | B15 | BLOCKED_CONFLICT | planilla last/next 101/102 encima del rango 1–20; sin histórico |
| BLUE ELITE | resto | BLOCKED_MISSING_AUTHORIZATION | 0 SAFE_ACTIVE |

`NCF_NEEDS_DGII_CONFIRMATION = 1` (Doralex B13).
`NCF_NEEDS_ALEXANDER = 3` (Piñaria, Dominion, Blue Elite si van a facturar pronto).

QA esta fase: `NCF_CONSUMED = 0`. Doralex B15 sigue en 152.
