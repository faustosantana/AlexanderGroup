# 17 — STILL_REQUIRED_FROM_ALEXANDER

Revisado antes de pedir: Levantamiento Excel, plantilla pendientes, PDFs de apertura, prod, staging, evidence opening 2026-09-05, configuración actual.

**No se vuelve a pedir:** RNC, direcciones, bancos, números de cuenta, representantes, cédulas, oficinas, actividad, moneda, logos, clientes/productos/facturas de apertura, NCF de la planilla (ya cargados), permiso para usar rangos vencidos, autorización extra B13 Doralex, From Gmail vs administracion@, stock de apertura, limpieza QA.

`STILL_REQUIRED_FROM_ALEXANDER_COUNT = 2`

| ITEM | COMPANY | SEVERITY | BLOCKS_GO_LIVE | WHO_MUST_RESOLVE | EXACT_INFORMATION_NEEDED |
|---|---|---|---|---|---|
| Fecha válida + autorización para asiento de banco | ALL6 | HIGH | NO (opera sin caja inicial) | Alexander + contador | Fecha real del saldo Excel (no `05//08/2026`) y OK para postear 5.0M / 2.45M / 1.5M / 3.0M / 4.6M / 1.25M |
| Personas / roles extra | ALL6 | MEDIUM | NO | Alexander | Lista nombre / login / empresas / rol cuando existan. Hoy basta Alexander |
| PDF original B1300000016 | DORALEX | LOW | NO | Alexander | Adjuntar original cuando exista. Mientras: MISSING_PDF |

No pedido (ya existe o no aplica):

- Números Banreservas
- SMTP password (técnico Justech; hoy 0 mail servers)
- Retenciones 606 de apertura (Excel CxP=0)
- e-CF (proyecto aparte)
- Rangos 9910 (cancelados; no son DGII)
- Seis usuarios Alexander (modelo correcto: uno solo)
- Confirmación de rangos vencidos
- NCF Piñaria / Dominion / Blue Elite

## Pendiente real para iniciar

No bloquean el arranque de Alexander en las 6 empresas:

1. PDF original B1300000016 cuando lo tengan.
2. Usuarios/roles extra cuando existan nombres (hoy basta Alexander).
3. Fecha de banco 18.8M más adelante (no postear ahora).

## HIGH / MEDIUM / LOW (errores de esta fase)

CRITICAL = 0

HIGH (3):

1. Backup automático inexistente (técnico Justech, no Alexander)
2. Saldos banco no posteados / fecha inválida
3. Sin `ir.mail_server`

MEDIUM (4):

1. Compañía técnica no archivable aún
2. Logo débil en header PDF
3. Matriz de roles de equipo pendiente
4. Enterprise expiration 2026-10-06

LOW (2):

1. Rempart 110: 0.01 histórico ya aceptado
2. Layout dual EN/ES de QWeb (diseño existente)
3. B1300000016 MISSING_PDF
