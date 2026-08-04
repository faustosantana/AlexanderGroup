# deployment/docker/

Archivos Docker de **ejemplo**. No construir ni levantar nada en Fase 0.

| Archivo                        | Propósito                                             |
| ------------------------------ | ----------------------------------------------------- |
| `Dockerfile.example`           | Imagen de Odoo 19 de referencia (por confirmar).      |
| `docker-compose.example.yml`   | Stack de referencia: Odoo + PostgreSQL + volúmenes.   |

## Advertencias

- **No aprobado para producción.**
- Requiere completar variables (`config/env.example` → `.env`).
- Requiere definir estrategia de backups.
- Requiere validar la versión exacta de Odoo 19.
- Requiere confirmar si se usa Enterprise (licencia).
- Requiere confirmar el servidor definitivo.

## Uso previsto (Fase 3, NO ahora)

```bash
# Copiar y renombrar los ejemplos, completar variables y revisar:
cp deployment/docker/docker-compose.example.yml deployment/docker/docker-compose.yml
cp config/env.example .env
# Editar .env y config/odoo.conf con valores reales gestionados fuera de Git.
```
