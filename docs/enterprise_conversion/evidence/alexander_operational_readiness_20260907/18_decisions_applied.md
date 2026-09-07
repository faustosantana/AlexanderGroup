# 18 — Decisiones Alexander 2026-09-07 y estado para iniciar

## Decisiones aplicadas

| Pedido | Decisión | Acción |
|---|---|---|
| Fecha + asiento 18.8M Banreservas | Queda pendiente | No se posteó |
| Pedir autorización B13 Doralex | No es necesario | B13 sigue BLOCKED; no se pide; operan B01/B15 |
| PIN / DOM / BLU van a facturar | Sí | Se activaron NCF de la **planilla que ya enviaron** |
| From = administracion@ dominio empresa | Sí | Ya estaba así; no se tocó Gmail/Hotmail |
| Stock de apertura | No hay stock | Existencias operativas = 0; QA DX-TEST-STK archivado |
| Limpiar QA | Autorizado | Ejecutado |
| PDF B1300000016 | Tarea para ellos | Sigue MISSING_PDF |

Backup previo: `pre_qa_cleanup_operational_20260907_100627` (`pg_restore -l` = 33990).

## ¿Piñaria / Dominion / Blue Elite no mandaron NCF?

**Sí lo mandaron.** Está en `Plantilla_PENDIENTES` hoja `02_Secuencias_NCF` (34 filas).
No estaba en el Levantamiento (`FISCAL_ROWS = 0`).

En la apertura **no se activaron** porque la regla era: solo rangos con histórico CxC en Odoo.
Esas 3 empresas no tenían facturas de apertura, así que quedaron bloqueados a propósito.

Hoy, con la confirmación de que van a facturar, se activó lo **consistente y vigente**:

| COMPANY | TIPO | RANGO | NEXT | AUTH | EXPIRA |
|---|---|---|---|---|---|
| PIÑARIA | B15 | 93–103 | B1500000093 | 6005464536 | 2028-01-01 |
| DOMINION | B15 | 140–163 | B1500000145 | 5004909756 | 2026-12-31 |
| BLUE ELITE | B01 | 1–15 | B0100000001 | 6005109961 | 2027-12-31 |

No se activó:

- **Blue Elite B15**: la planilla se contradice (rango 1–20, last 101, next 102). No se inventa un rango nuevo.
- **Piñaria B01** y **Dominion B01**: vencían 2025-12-31 (ya pasaron).
- B02/B04/B11/B13 de esas empresas: no hacen falta para emitir la primera factura de crédito/consumo gubernamental típica.

Doralex B15 `B1500000152` y B01 `B0100000054` no se tocaron. Mayuma/Rempart B15 `B1500000111` no se tocaron.

## Limpieza QA (prod)

Cancelados: 22 pagos, 48 asientos, 11 SO, 10 OC.
Archivados: 13 partners DX TEST, 3 productos DX-TEST-*, user `dx.test.security@justech.do`.
Quants Existencias DX-TEST-STK = 0. Quedan contrapartidas en ubicación virtual `Inventory adjustment` (rastro del ajuste).
`qa_posted_moves = 0` · `qa_active_partners = 0` · `qa_active_users = 0`

Apertura intacta: 27 / AR 27240211.80 / 0150=294754.56 / Rempart 110=267250.52 / PDFs 26 / QWeb 58 / MAIL=0 / ECF=False / DGII_SENT=0.

## Correos oficiales (From)

| COMPANY | EMAIL |
|---|---|
| DORALEX | administracion@inversionesdoralex.com |
| PIÑARIA | administracion@pinariagroup.com |
| DOMINION | administracion@dominion-business.com |
| EL MAYUMA | administracion@elmayuma.com |
| REMPART | administracion@rempartgroup.com |
| BLUE ELITE | administracion@blueelite.net |

SMTP todavía no está configurado: pueden operar e imprimir; el envío de correo queda para después.
