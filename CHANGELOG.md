# Changelog

Todos los cambios notables de este proyecto se documentan en este archivo.
El formato sigue, de forma aproximada, [Keep a Changelog](https://keepachangelog.com/es-ES/1.0.0/).

## Unreleased

### Added
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
