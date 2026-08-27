# Doralex — PRODUCCION

Stack aislado de Produccion (`/opt/doralex/production/`).

> No desarrollar aquí. Produccion solo recibe releases controlados desde `main`
> tras UAT en Dev y backup previo. Ver el runbook de despliegue.

## Puesta en marcha (en el servidor, tras auditoría)

```bash
cd /opt/doralex/production
cp .env.example .env          # completar POSTGRES_PASSWORD y ODOO_ADMIN_PASSWD (fuertes)
bash /opt/doralex/scripts/render_config.sh production
docker compose --project-name doralex-production --env-file .env -f docker-compose.yml up -d
bash /opt/doralex/scripts/healthcheck.sh production
```

## Características

- PostgreSQL **no** expuesto (sin `ports`).
- Odoo publicado **solo** en `127.0.0.1:8069` (+ `8072` longpolling).
- `list_db = False`, `dbfilter = ^doralex_prod$`.
- Estado inicial deseado: instalado, **vacío/base controlada**, saludable, **sin**
  configuración final de Alexander (empresas, NCF, catálogo, usuarios).

## Archivos

| Archivo | Descripción |
| ------- | ----------- |
| `docker-compose.yml` | Stack Prod (db + odoo), redes/volúmenes propios. |
| `.env.example` | Plantilla de variables (copiar a `.env`, no versionar). |
| `config/odoo.conf.example` | Plantilla de odoo.conf (renderizar, no versionar el resultado). |
