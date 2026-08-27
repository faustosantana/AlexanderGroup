# Referencia técnica de Justgroup (erp.justech.do)

> **PENDING_AUDIT.** Plantilla. Se completa auditando **técnicamente** la
> instalación estable de Justgroup, **sin copiar datos comerciales** ni la base de
> datos. El objetivo es **reutilizar la arquitectura probada** y fijar en Doralex
> una release compatible. **No inventar** valores.

## Cómo obtener los datos (solo lectura, con autorización)

Ejecutar en el servidor de Justgroup (o revisar su config/despliegue) sin alterar
nada. Registrar aquí los valores reales.

## Release de Odoo (Fase 5)

| Clave | Valor | Notas |
| ----- | ----- | ----- |
| `ODOO_MAJOR` | `19` | Confirmar |
| `ODOO_BUILD` | _pendiente_ | build/fecha exacta |
| `COMMUNITY_REVISION` | _pendiente_ | commit/tag community |
| `ENTERPRISE_REVISION` | _pendiente_ | commit/tag enterprise (misma rama) |
| Método de instalación | _pendiente_ | Docker / paquetes / fuente |

## Arquitectura y configuración

| Aspecto | Justgroup (real) | Notas para Doralex |
| ------- | ---------------- | ------------------ |
| Community/core path | _pendiente_ | |
| Enterprise addons path | _pendiente_ | mapear a `/mnt/enterprise` |
| Custom addons path | _pendiente_ | mapear a `/mnt/custom-addons` |
| `odoo.conf` (opciones) | _pendiente_ | workers, limits, proxy_mode |
| workers | _pendiente_ | |
| cron threads | _pendiente_ | |
| gevent/websocket | _pendiente_ | puerto longpolling |
| PostgreSQL (versión) | _pendiente_ | fijar misma mayor |
| Reverse proxy | _pendiente_ | nginx/traefik/apache |
| Motor PDF (`wkhtmltopdf`) | _pendiente_ | fijar misma versión |
| Dependencias Python | _pendiente_ | requirements extra |
| Dependencias del sistema | _pendiente_ | paquetes apt |
| Estructura multiempresa | _pendiente_ | |
| Mail (SMTP/IMAP) | _pendiente_ | |
| Filestore | _pendiente_ | ubicación/volumen |
| Backups | _pendiente_ | método y frecuencia |
| Service management | _pendiente_ | systemd/compose |
| Logging | _pendiente_ | rutas/rotación |

## Inventario de módulos

Se detalla en [`JUSTGROUP_MODULE_INVENTORY.md`](JUSTGROUP_MODULE_INVENTORY.md).

## Conclusiones para Doralex

_Pendiente._ Fijar release exacta, `addons_path`, versión de PostgreSQL, motor PDF
y lista de módulos custom reutilizables (con licencia/propiedad verificada).
