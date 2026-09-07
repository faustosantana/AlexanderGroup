# 17 — STILL_REQUIRED_FROM_ALEXANDER

Revisado antes de pedir: Levantamiento Excel, plantilla pendientes, PDFs de apertura, prod, staging, evidence opening 2026-09-05, configuración actual.

**No se vuelve a pedir:** RNC, direcciones, bancos, números de cuenta, representantes, cédulas, oficinas, actividad, moneda, logos ya cargados en `res.company`, clientes/productos/facturas de apertura.

`STILL_REQUIRED_FROM_ALEXANDER_COUNT = 3`  (actualizado 2026-09-07 tarde; ver `18_decisions_applied.md`)

| ITEM | COMPANY | SEVERITY | BLOCKS_GO_LIVE | WHO_MUST_RESOLVE | EXACT_INFORMATION_NEEDED |
|---|---|---|---|---|---|
| Fecha válida + autorización para asiento de banco | ALL6 | HIGH | NO (opera sin caja inicial) | Alexander + contador | Fecha real del saldo Excel (no `05//08/2026`) y OK para postear 5.0M / 2.45M / 1.5M / 3.0M / 4.6M / 1.25M |
| Rango B13 DGII que cubra 0016 y el próximo | DORALEX | HIGH | NO (B01/B15 sí operan) | Alexander + DGII | Autorización, from/to, vencimiento; no inventar B1300000017 |
| ¿Facturarán pronto Piñaria / Dominion / Blue Elite? | PIN, DOM, BLU | HIGH | YES para factura fiscal de esas 3 | Alexander | Si sí: tipos NCF + from/to + auth + vencimiento reales. Si no: se dejan BLOCKED |
| Correo From oficial | ALL6 | MEDIUM | NO | Alexander | Confirmar si outbound es `administracion@…` (Odoo) o el Gmail/Hotmail del Excel |
| Personas / roles extra | ALL6 | MEDIUM | NO | Alexander | Lista nombre / login / empresas / rol (Gerencia, Ventas, Compras, Contabilidad, CxC, CxP, Almacén, Consulta). Hoy solo Alexander |
| Inventario de apertura o confirmar cero | ALL6 | MEDIUM | NO | Alexander | Cantidades reales por producto/almacén **o** confirmación de stock 0. Autorizar limpieza de `DX-TEST-STK` |
| Limpieza QA prod | ALL6 | HIGH | NO (Aged operativo sí se contamina) | Alexander (autoriza) | ¿Archivar/anular 14 docs 9910/9911 + user `dx.test.security`? No se toca sin OK (608) |
| PDF original B1300000016 | DORALEX | LOW | NO | Alexander | Adjuntar original cuando exista. Mientras: MISSING_PDF |

No pedido (ya existe o no aplica):

- Números Banreservas
- SMTP password (solo si quieren enviar correo; hoy 0 mail servers — pedir credenciales **después** de confirmar From)
- Retenciones 606 de apertura (Excel CxP=0)
- e-CF (proyecto aparte)
- Rangos 9910 (cancelados; no son DGII)
- Seis usuarios Alexander (modelo correcto: uno solo)

## Pendiente real para iniciar (2026-09-07 tarde)

No bloquean el arranque de Alexander en las 6 empresas:

1. Blue Elite B15: si facturan B15 (no B01), enviar rango que cubra el 101+ o confirmar que el 1–20 nunca se usó.
2. PDF original B1300000016 cuando lo tengan.
3. Usuarios/roles extra cuando existan nombres (hoy basta Alexander).

Banco 18.8M y B13 Doralex: aplazados a propósito.

## HIGH / MEDIUM / LOW (errores de esta fase)

CRITICAL = 0

HIGH (7):

1. Backup automático inexistente (técnico Justech, no Alexander)
2. Documentos QA posteados en prod (Aged + residual 16000.80)
3. Piñaria/Dominion/Blue Elite sin NCF real SAFE_ACTIVE
4. Saldos banco no posteados / fecha inválida
5. Doralex B13 bloqueado
6. Sin `ir.mail_server`
7. Stock QA (Doralex −23 DX-TEST-STK)

MEDIUM (6):

1. Compañía técnica no archivable aún
2. Logo débil en header PDF
3. Email Excel vs `administracion@`
4. Matriz de roles de equipo pendiente
5. Productos históricos `purchase_ok=0`
6. Enterprise expiration 2026-10-06

LOW (2):

1. Rempart 110: 0.01 histórico ya aceptado
2. Layout dual EN/ES de QWeb (diseño existente)
