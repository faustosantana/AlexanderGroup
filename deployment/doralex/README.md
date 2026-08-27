# deployment/doralex/ — Bootstrap de infraestructura (Odoo 19)

Fuente de verdad **versionada** de la infraestructura de Doralex / Alexander Group.
Los artefactos se despliegan en el servidor nuevo bajo `/opt/doralex/`.

> Estado actual: **infraestructura diseñada y versionada**. Aún **no** desplegada
> (requiere auditoría por SSH primero). No hay datos de Alexander Group todavía.

## Mapa repo → servidor

| En el repo                                   | En el servidor                         |
| -------------------------------------------- | -------------------------------------- |
| `production/`                                | `/opt/doralex/production/`             |
| `dev/`                                        | `/opt/doralex/dev/`                    |
| `reverse-proxy/`                              | `/etc/nginx/sites-available/` (host)   |
| `scripts/`                                    | `/opt/doralex/scripts/`                |
| (este repo)                                   | `/opt/doralex/repository/`             |
| —                                             | `/opt/doralex/enterprise/` (vacío, licencia) |
| —                                             | `/opt/doralex/custom-addons/`          |
| —                                             | `/opt/doralex/odoo/` (ref. de versión) |
| —                                             | `/opt/doralex/backups/{production,dev}`|

## Aislamiento Produccion ↔ Dev

| Recurso            | Produccion              | Dev                    |
| ------------------ | ----------------------- | ---------------------- |
| Proyecto compose   | `doralex-production`    | `doralex-dev`          |
| Red Docker         | `doralex_prod_net`      | `doralex_dev_net`      |
| Volumen DB         | `doralex_prod_db_data`  | `doralex_dev_db_data`  |
| Volumen filestore  | `doralex_prod_odoo_data`| `doralex_dev_odoo_data`|
| DB / usuario       | `doralex_prod`          | `doralex_dev`          |
| Password DB        | propio (`.env`)         | propio (`.env`)        |
| Odoo (loopback)    | `127.0.0.1:8069/8072`   | `127.0.0.1:8169/8172`  |
| PostgreSQL         | **no publicado**        | **no publicado**       |
| Dominio definitivo | `doralexgroup.cloud`    | `dev.doralexgroup.cloud` |

**Regla dura:** nunca montar volúmenes de Produccion en Dev. `scripts/validate_isolation.sh`
lo verifica.

## Secretos

- Cada entorno tiene su `.env` (a partir de `.env.example`), **fuera de Git**.
- `config/odoo.conf` se **renderiza** desde `config/odoo.conf.example` con
  `scripts/render_config.sh` y queda **fuera de Git** (contiene el master password).

## Documentación

- Arquitectura: [`../../docs/infrastructure/ARCHITECTURE.md`](../../docs/infrastructure/ARCHITECTURE.md)
- Runbook de despliegue: [`../../docs/infrastructure/DEPLOYMENT_RUNBOOK.md`](../../docs/infrastructure/DEPLOYMENT_RUNBOOK.md)
- Validación de aislamiento: [`../../docs/infrastructure/ISOLATION_VALIDATION.md`](../../docs/infrastructure/ISOLATION_VALIDATION.md)
- DNS y SSL: [`../../docs/infrastructure/DNS_AND_SSL.md`](../../docs/infrastructure/DNS_AND_SSL.md)
- Backups: [`../../docs/infrastructure/BACKUP_STRATEGY.md`](../../docs/infrastructure/BACKUP_STRATEGY.md)
- Enterprise: [`../../docs/infrastructure/ENTERPRISE_READINESS.md`](../../docs/infrastructure/ENTERPRISE_READINESS.md)
