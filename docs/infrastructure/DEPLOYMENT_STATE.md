# Estado del despliegue — Doralex (Odoo 19)

> Fecha: 2026-08-27. Servidor `2.25.121.111` (`America/Santo_Domingo`).
> Odoo 18 preinstalado **eliminado** (ver `PREEXISTING_ODOO18_BACKUP.md`).
> Odoo 19 **desplegado**, Prod + Dev aislados, enterprise-ready.

## Plataforma

| Componente | Versión / valor |
| ---------- | --------------- |
| Odoo | **19.0-20260817** (imagen `odoo:19`) |
| PostgreSQL | **16.15** (imagen `postgres:16`) |
| Reverse proxy | Nginx (host) + certbot |
| Docker / Compose | 29.7.2 / v5.5.0 |

> `ODOO_MAJOR=19`, `ODOO_BUILD=19.0-20260817`. `COMMUNITY_REVISION` /
> `ENTERPRISE_REVISION`: pendientes de la auditoría de Justgroup (Fase 18).

## Entornos (aislados)

| | Produccion | Dev |
| --- | --- | --- |
| Contenedores | `doralex-production-{db,odoo}` | `doralex-dev-{db,odoo}` |
| DB | `doralex_prod` (base instalada, sin demo) | `doralex_dev` (base instalada) |
| Red | `doralex_prod_net` | `doralex_dev_net` |
| Volúmenes | `doralex_prod_{db,odoo}_data` | `doralex_dev_{db,odoo}_data` |
| Odoo (loopback) | `127.0.0.1:8069/8072` | `127.0.0.1:8169/8172` |
| Estado | **healthy** (`/web/health` 200) | **healthy** (`/web/health` 200) |
| Dominio | `https://doralexgroup.cloud` | `https://dev.doralexgroup.cloud` (DNS pendiente) |

`addons_path` (contenedor): `/mnt/enterprise,/mnt/custom-addons` (final).
`/opt/doralex/enterprise` existe vacío → `ENTERPRISE_SOURCE_PENDING=TRUE`.

## Aislamiento (validado)

`scripts/validate_isolation.sh` → **ISOLATION: PASS**. Cross-environment shared
volumes = **0**. PostgreSQL **no publicado**.

## Seguridad / exposición (verificada externamente)

| Puerto | Estado externo |
| ------ | -------------- |
| 22, 80, 443 | ABIERTOS |
| 5432, 8069, 8072, 8169, 8172 | CERRADOS/filtrados |

- `ufw` activo (solo 22/80/443). `fail2ban` activo (jail `sshd`).
- Odoo publicado solo en loopback; Nginx termina TLS.

## DNS / SSL

| Dominio | DNS | SSL |
| ------- | --- | --- |
| `doralexgroup.cloud` | → `2.25.121.111` ✅ | Let's Encrypt ✅ (exp. 2026-11-25) |
| `www.doralexgroup.cloud` | → `2.25.121.111` ✅ | ✅ (301 → canónico) |
| `dev.doralexgroup.cloud` | **NXDOMAIN** ❌ | **DNS_REQUIRED** (sin certificado) |

HTTP→HTTPS (301) y `www`→canónico (301) verificados. Renovación automática certbot.

## Backups

`scripts/backup.sh` ejecutado y **verificado** (SHA256) para Prod y Dev
(`/opt/doralex/backups/{production,dev}/…`): `db.dump`, `filestore.tar.gz`,
`odoo.conf`, `docker-compose.yml`, `env.backup`, `MANIFEST`, `SHA256SUMS`.

## Pendientes

- `DNS_REQUIRED`: crear `A dev.doralexgroup.cloud → 2.25.121.111` para emitir su SSL.
- `ENTERPRISE_SOURCE_PENDING`: colocar addons Enterprise legítimos en
  `/opt/doralex/enterprise` cuando llegue la licencia (sin reconstruir).
- Auditoría técnica de Justgroup (Fase 18) para fijar revisiones y módulos.
- **No** se ha cargado Alexander Group (empresas, catálogo, NCF, usuarios).
