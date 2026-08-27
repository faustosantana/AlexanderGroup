# Validación de aislamiento y salud — Doralex

Checklist previo a declarar **PASS** (sección 18 del bootstrap). Se automatiza con
`scripts/validate_isolation.sh` y `scripts/healthcheck.sh` (requieren el servidor
con Docker).

| # | Criterio | Cómo se verifica | Estado |
| - | -------- | ---------------- | ------ |
| 1 | Produccion y Dev aislados | `validate_isolation.sh` (redes/volúmenes/contenedores) | PENDING_DEPLOY |
| 2 | DBs separadas | usuarios/DB `doralex_prod` vs `doralex_dev` | PENDING_DEPLOY |
| 3 | Filestores separados | volúmenes `*_odoo_data` por entorno | PENDING_DEPLOY |
| 4 | Redes separadas | `doralex_prod_net` vs `doralex_dev_net` | PENDING_DEPLOY |
| 5 | PostgreSQL no público | ningún `5432->` publicado | PENDING_DEPLOY |
| 6 | Odoo HTTP saludable | `healthcheck.sh` (`/web/health`) | PENDING_DEPLOY |
| 7 | Sobrevive reinicio | `restart: unless-stopped` + reboot de prueba | PENDING_DEPLOY |
| 8 | Backups ejecutables y verificados | `backup.sh` + `verify_backup.sh` | PENDING_DEPLOY |
| 9 | Git limpio | `git status` sin cambios sin commitear | **PASS (repo)** |
| 10 | Secretos fuera del repo | `.env`/`odoo.conf` gitignored; validador de secretos | **PASS (repo)** |

> Los ítems marcados `PENDING_DEPLOY` solo pueden ejecutarse en el servidor tras
> la auditoría y el despliegue. Los ítems de repositorio (9, 10) ya están en verde.

## Evidencia esperada al desplegar

```bash
bash scripts/validate_isolation.sh   # -> "ISOLATION: PASS"
bash scripts/healthcheck.sh production
bash scripts/healthcheck.sh dev
docker ps --format '{{.Names}}\t{{.Ports}}'   # Odoo solo 127.0.0.1, sin 5432
```
