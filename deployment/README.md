# deployment/

Artefactos de despliegue **de ejemplo únicamente**. Nada de esta carpeta está
aprobado para producción ni debe ejecutarse en esta fase.

> ⚠️ En **Fase 0** no se descargan imágenes, no se levantan contenedores y no se
> realizan conexiones a servidores.

## Contenido

| Subcarpeta | Descripción                                                       |
| ---------- | ----------------------------------------------------------------- |
| `docker/`  | `Dockerfile.example` y `docker-compose.example.yml` de referencia.|
| `nginx/`   | `odoo.conf.example` (proxy inverso) de referencia.                |
| `scripts/` | `backup`, `deploy`, `restore` de ejemplo (`*.example.sh`).        |

## Requisitos previos antes de usar cualquier cosa aquí (Fase 3)

- Servidor definitivo confirmado.
- Versión exacta de Odoo 19 y confirmación de Enterprise/Community.
- Variables completadas a partir de `config/env.example`.
- Estrategia de backups definida ([`docs/09_BACKUP_AND_ROLLBACK.md`](../docs/09_BACKUP_AND_ROLLBACK.md)).
- DNS, SSL y credenciales gestionadas fuera de Git.

Ver [`docs/08_DEPLOYMENT_STRATEGY.md`](../docs/08_DEPLOYMENT_STRATEGY.md).
