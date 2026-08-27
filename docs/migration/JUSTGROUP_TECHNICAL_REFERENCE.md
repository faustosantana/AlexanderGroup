# Referencia técnica de Justgroup (erp.justech.do)

> **PENDING_AUDIT.** Plantilla. Se completa auditando **técnicamente** la
> instalación estable de Justgroup, **sin copiar datos comerciales** ni la base de
> datos. El objetivo es **reutilizar la arquitectura probada** y fijar en Doralex
> una release compatible. **No inventar** valores.

## Estado: `JUSTGROUP_AUDIT = PARTIAL`

Auditoría **de solo lectura** realizada sobre la instancia real (sin autenticar,
sin modificar nada), vía el endpoint público JSON-RPC `common.version` de
`erp.justech.do`:

| Clave | Valor (verificado) |
| ----- | ------------------ |
| `server_version` | **`19.0+e-20260324`** |
| `server_version_info` | `[19, 0, 0, "final", 0, "e"]` |
| `server_serie` | `19.0` |
| Edición | **Enterprise** (sufijo `+e` / `"e"`) |

`ODOO_MAJOR=19`, `ODOO_BUILD=19.0+e-20260324`, Edición=**Enterprise**.

Otros datos read-only (sin login): DB manager **deshabilitado** (`/web/database/list`
→ Access Denied, buena práctica), módulo **Website** instalado (login "Soporte
Justech"), reverse proxy `openresty`. Evidencia:
[`evidence/justgroup_readonly_audit.txt`](evidence/justgroup_readonly_audit.txt).

### Lo que falta (requiere credenciales que NO existen en el entorno)

El **inventario de módulos** (`ir.module.module`), modelos/campos custom, cron,
QWeb, Studio, seguridad, etc. requiere autenticación (admin Odoo, SSH al servidor
de Justgroup, o un export). **Búsqueda de accesos existentes realizada** (sin
resultado):

- Variables de entorno: sin credenciales Justgroup/Odoo.
- `~/.ssh/config` y llaves: solo Doralex (`2.25.121.111`).
- Archivos de credenciales (`.netrc`, `.pgpass`, `.odoorc`, etc.): ninguno.
- Remotos Git: solo `faustosantana/AlexanderGroup`.
- Repos GitHub accesibles: `faustosantana/justech` es **otra aplicación**
  (FastAPI/frontend, no Odoo) y `website-justech` es la web; **no** hay repo de
  addons Odoo de Justgroup accesible.

> Enterprise: Justgroup es Enterprise, pero **sus addons Enterprise no pueden
> copiarse a Doralex** (licenciamiento por instancia). Doralex requiere su propia
> suscripción → `BLOCKED_BY_ENTERPRISE_SOURCE` para Doralex.

Para completar el inventario, proveer acceso de solo lectura (admin Odoo de
`erp.justech.do`, o SSH a su servidor, o export de `ir.module.module` +
`custom-addons`) como Secret. Ver `JUSTGROUP_MODULE_INVENTORY.md`.

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
