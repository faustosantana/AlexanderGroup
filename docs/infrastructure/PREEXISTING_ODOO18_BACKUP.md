# Odoo 18 preinstalado — Backup y eliminación

> Fecha: 2026-08-27. Servidor `2.25.121.111`. Acción autorizada por el usuario:
> **eliminar** el Odoo 18 preinstalado (plantilla del proveedor) e instalar Odoo 19.

## Qué había (instalación preconfigurada del proveedor)

Stack Docker `odoo-aeju` + `traefik` (Hostinger), enrutado solo al host por defecto
`odoo-aeju.srv1935521.hstgr.cloud` (no a nuestros dominios):

| Contenedor | Imagen | Rol |
| ---------- | ------ | --- |
| `odoo-aeju-odoo-1` | `odoo:18` | Odoo 18 (expuesto en `:32768`) |
| `odoo-aeju-db-1` | `postgres:17-alpine` | Base de datos |
| `traefik-traefik-1` | `traefik:latest` | Reverse proxy `:80/:443` |

Compose en `/docker/odoo-aeju` y `/docker/traefik`.

## Verificación de que era seguro borrar

- Única base de datos: `postgres` (por defecto). **Ninguna base Odoo creada**
  (`ir_module_module` inexistente → Odoo nunca inicializado).
- Filestore `/var/lib/odoo` = 16K (vacío). Sin custom addons.
- **0 sesiones activas**; sin dominios productivos propios; sin datos comerciales.
- Conclusión: instalación **preconfigurada/vacía** → seguro eliminar.

## Backup de seguridad (antes de borrar)

Guardado en `/opt/doralex/backups/preexisting-odoo18/` (fuera de Git), con
`SHA256SUMS`:

- `docker-compose.yml` de `odoo-aeju` y `traefik` (copias de `/docker/**`).
- `inspect_*.json` de los 3 contenedores.
- `odoo.conf` del contenedor Odoo 18.
- `dbdump_postgres.dump` (pg_dump de la base `postgres`).
- Listados `docker_ps/images/volumes/networks`, `db_names`, `db_probe`,
  `pg_activity`, `filestore_addons`.

> No se preservaron datos comerciales porque **no existían** (instalación vacía).

## Eliminación (ODOO18_REMOVAL_PASS = YES)

Ejecutado `docker compose down -v` en ambos proyectos + limpieza:

- Contenedores `odoo-aeju-*` y `traefik-*`: **eliminados**.
- Volúmenes `odoo-aeju_*`, `traefik*letsencrypt`: **eliminados**.
- Red `odoo-aeju_default`: **eliminada**.
- Imágenes `odoo:18`, `traefik:latest`, `postgres:17-alpine`: **eliminadas**.
- Directorios `/docker/odoo-aeju`, `/docker/traefik`, `/docker`: **eliminados**.

Validación post-eliminación:

| Check | Resultado |
| ----- | --------- |
| Contenedores legacy | 0 |
| Volúmenes legacy | 0 |
| Imágenes legacy | 0 |
| Procesos Odoo 18 | 0 |
| Puertos `80/443/32768/8069/8072` | LIBRES (antes de instalar Odoo 19) |

`ODOO18_REMOVAL_PASS = YES`.
