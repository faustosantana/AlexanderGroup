# Doralex — DEV

Stack aislado de Desarrollo (`/opt/doralex/dev/`). **Primer entorno operativo.**

> Aquí se instalará posteriormente Alexander Group (6 empresas, catálogo de
> cuentas, localización RD, bancos, usuarios, oficinas, módulos), **después** de
> completar el bootstrap de infraestructura. Ahora NO se carga nada de eso.

## Puesta en marcha (en el servidor, tras auditoría)

```bash
cd /opt/doralex/dev
cp .env.example .env          # completar POSTGRES_PASSWORD y ODOO_ADMIN_PASSWD
bash /opt/doralex/scripts/render_config.sh dev
docker compose --project-name doralex-dev --env-file .env -f docker-compose.yml up -d
bash /opt/doralex/scripts/healthcheck.sh dev
```

## Diferencias con Produccion

- Puertos loopback **distintos**: `127.0.0.1:8169` (+ `8172`).
- `list_db = True` y `dbfilter = ^doralex_dev.*$` para permitir bases de prueba.
- Red/volúmenes/DB completamente separados de Produccion.
- Odoo Studio podrá usarse aquí para prototipar (la lógica crítica y los PDF QWeb
  se versionan en Git; ver docs de arquitectura).
