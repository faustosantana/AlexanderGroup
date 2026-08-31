# Changelog

Todos los cambios notables de este proyecto se documentan en este archivo.
El formato sigue, de forma aproximada, [Keep a Changelog](https://keepachangelog.com/es-ES/1.0.0/).

## Unreleased

### Changed
- Recibo multi-factura (`multi_invoice_manual_payment_prod` 19.0.1.5.5): un
  solo PDF por `account.payment` con tabla completa (NCF, saldos, pie). No
  modifica `justech_alexander_reports` (QWeb 58). Solo staging Doralex.

### Added
- Staging Doralex: canal temporal `doralex-core-transfer` cerrado e instalación
  del stack custom Justech (fiscal, NCF, e-CF, tesorería, márgenes, aprobaciones,
  auditoría, garantías, guards, nómina RD). Overlay `justech_alexander_*` y QWeb
  58 intactos. Cutover y Prod siguen bloqueados.
- Auditoría del export Justgroup en Doralex (extracto aislado, QWeb 58,
  custom-addons comparado, core 19.0.20260324 pendiente). Usuario SSH
  temporal de transferencia cerrado. Cutover sigue bloqueado.
- Conversión Community → Enterprise en staging aislado
  (`deployment/doralex/enterprise-staging/`, scripts de clon/fetch/convert).
  Cutover a producción bloqueado.
- Auditoría Justgroup vs Doralex (stack): manifiestos, comparador
  `tools/justgroup_doralex_stack_compare.py` y backup de preservación de
  reportes. Cutover bloqueado hasta Enterprise propia.

### Changed
- Correo saliente Doralex: un solo From por empresa (`administracion@` de
  `document.company_id`). Los aliases funcionales no se usan como remitente.

### Added
- Estructura inicial del repositorio.
- Documentación base.
- Plantillas de configuración.
- Validadores de seguridad.
- Estrategia inicial de implementación.
- Bootstrap de infraestructura Doralex (Odoo 19): stacks Docker Compose aislados
  de Produccion y Dev (`deployment/doralex/`), reverse proxy Nginx + plantillas
  SSL, y scripts de auditoría, render de config, backups verificables, restore,
  healthcheck y validación de aislamiento.
- Documentación de infraestructura (`docs/infrastructure/`): arquitectura,
  plantilla de auditoría de servidor, runbook de despliegue, validación de
  aislamiento, DNS/SSL (PENDING_DNS), endurecimiento de seguridad, estrategia de
  backups y estado de Odoo 19 Enterprise (BLOCKED, pendiente de licencia).
- Plantilla de inventario para migración de módulos Justgroup
  (`docs/migration/JUSTGROUP_MODULE_INVENTORY.md`).

### Changed
- Infraestructura Doralex **enterprise-ready** desde el inicio: `addons_path` final
  `/mnt/enterprise,/mnt/custom-addons`, montaje del dir Enterprise (vacío,
  `ENTERPRISE_SOURCE_PENDING=TRUE`), workers/gevent y logging productivos.
- Dominios definitivos migrados a `.cloud`: `doralexgroup.cloud` (Prod),
  `dev.doralexgroup.cloud` (Dev), `www.doralexgroup.cloud` (→ canónico).
- `bootstrap_dirs.sh` crea la estructura final (`odoo/`, `enterprise/`,
  `custom-addons/`, `logs/` y por entorno).
- Acceso al servidor por **llave SSH** vía `setup_ssh_local.sh` (máquina del
  usuario) y `cloud_ssh_bootstrap.sh` (Cloud Agent, Secret `DORALEX_SSH_PRIVATE_KEY`).
- Nuevos documentos: `STUDIO_AND_REPORTS.md` y `JUSTGROUP_TECHNICAL_REFERENCE.md`.
