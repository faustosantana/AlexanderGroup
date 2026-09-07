# 18 — Decisiones Alexander 2026-09-07 y estado para iniciar

## Decisiones aplicadas

| Pedido | Decisión | Acción |
|---|---|---|
| Fecha + asiento 18.8M Banreservas | Queda pendiente | No se posteó |
| Pedir autorización B13 Doralex | No es necesario | B13 quedó **activo** con next `B1300000017` (0016 ya existe) |
| PIN / DOM / BLU van a facturar | Sí | Los 34 NCF de la planilla están activos |
| Rangos vencidos (2024/2025) | DGII no es problema; no dejar inactivo | Activos; `date_to` operativo 2099 para que Odoo no los marque expired |
| From = administracion@ dominio empresa | Sí | Ya estaba así; no se tocó Gmail/Hotmail |
| Stock de apertura | No hay stock | Existencias operativas = 0; QA DX-TEST-STK archivado |
| Limpiar QA | Autorizado | Ejecutado |
| PDF B1300000016 | Tarea para ellos | Sigue MISSING_PDF |
| Cargar NCF tal cual Excel | Sí | Auth/from/next de las 34 filas; ver `09_ncf.md` por 4 ajustes inevitables |

Backup previo a la carga total NCF: `production_20260907_104708`.
Backup previo limpieza QA: `pre_qa_cleanup_operational_20260907_100627` (`pg_restore -l` = 33990).

## ¿Piñaria / Dominion / Blue Elite no mandaron NCF?

**Sí lo mandaron.** Está en `Plantilla_PENDIENTES` hoja `02_Secuencias_NCF` (34 filas).
No estaba en el Levantamiento (`FISCAL_ROWS = 0`).

Hoy las 34 filas están en Odoo `state=active`. No queda ningún tipo de la planilla inactivo.

## Limpieza QA (prod)

Cancelados: 22 pagos, 48 asientos, 11 SO, 10 OC.
Archivados: 13 partners DX TEST, 3 productos DX-TEST-*, user `dx.test.security@justech.do`.
Quants Existencias DX-TEST-STK = 0. Quedan contrapartidas en ubicación virtual `Inventory adjustment` (rastro del ajuste).
`qa_posted_moves = 0` · `qa_active_partners = 0` · `qa_active_users = 0`

Apertura intacta: 27 facturas / AR 27240211.80 / 0150=294754.56 / Rempart 110=267250.52 / PDFs 26 / QWeb 58 / MAIL=0 / ECF=False / DGII_SENT=0.

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
