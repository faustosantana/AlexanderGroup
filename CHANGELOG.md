# Changelog

Todos los cambios notables de este proyecto se documentan en este archivo.
El formato sigue, de forma aproximada, [Keep a Changelog](https://keepachangelog.com/es-ES/1.0.0/).

## Unreleased

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
