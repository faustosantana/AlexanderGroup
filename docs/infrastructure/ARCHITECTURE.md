# Arquitectura de infraestructura — Doralex / Alexander Group

Odoo 19 sobre Docker Compose, con **Produccion** y **Dev** totalmente aislados en
un mismo servidor, detrás de un reverse proxy con TLS.

## Diagrama lógico

```text
                         Internet
                            │
                   ┌────────┴─────────┐
                   │  Nginx (host)     │  TLS / Let's Encrypt
                   │  reverse proxy    │  (PENDING_DNS)
                   └───┬───────────┬───┘
        erp.doralexgroup.com   dev.doralexgroup.com
                   │               │
        127.0.0.1:8069        127.0.0.1:8169     (solo loopback)
                   │               │
        ┌──────────┴───┐   ┌───────┴──────┐
        │ PROD odoo    │   │ DEV odoo     │
        │ doralex_prod │   │ doralex_dev  │   redes Docker separadas
        │   _net       │   │   _net       │
        │   │          │   │   │          │
        │ PROD db      │   │ DEV db       │   PostgreSQL NO expuesto
        │ (vol prod)   │   │ (vol dev)    │   volúmenes separados
        └──────────────┘   └──────────────┘
```

## Principios de aislamiento

- **Un stack compose por entorno** (`doralex-production`, `doralex-dev`).
- **Red, volúmenes, base de datos, usuario y password independientes** por entorno.
- **Filestore independiente** (volumen `*_odoo_data` por entorno).
- **Nunca** montar volúmenes de Produccion en Dev.
- **Puertos internos/publicados distintos** y **solo** en `127.0.0.1`.
- **PostgreSQL nunca se publica** al exterior (sin `ports`).

## Puertos (loopback)

| Entorno    | HTTP           | Longpolling     |
| ---------- | -------------- | --------------- |
| Produccion | `127.0.0.1:8069` | `127.0.0.1:8072` |
| Dev        | `127.0.0.1:8169` | `127.0.0.1:8172` |

## Rutas en el servidor

```text
/opt/doralex/
├── production/   (docker-compose.yml, .env, config/, addons/)
├── dev/          (docker-compose.yml, .env, config/, addons/)
├── backups/      (production/ , dev/)
├── scripts/      (audit, backup, restore, healthcheck, isolation, ...)
└── repository/   (checkout del repo Git, fuente de verdad)
```

## Reverse proxy y TLS

Nginx de **host** termina TLS y enruta por dominio hacia el Odoo correspondiente
por `127.0.0.1`. Al comunicarse por loopback, el proxy **no** se une a las redes
Docker de los entornos, preservando el aislamiento. Certificados con certbot
(Let's Encrypt) una vez el DNS resuelva. Ver [`DNS_AND_SSL.md`](DNS_AND_SSL.md).

## Configuración de Odoo

- `config/odoo.conf` se **renderiza** desde `*.example` con `render_config.sh`
  (inyecta `admin_passwd` y `dbfilter` desde `.env`) y **no** se versiona.
- Conexión a DB por variables de entorno del contenedor (`HOST/USER/PASSWORD/PORT`).
- `proxy_mode = True`; `list_db = False` en Produccion.

## Studio / PDF / código

- Odoo Studio se permitirá en **Dev** para prototipar (formularios, listas,
  kanban, campos, pestañas).
- La lógica crítica y las personalizaciones importantes deben terminar
  **versionadas en Git**.
- Los PDF críticos se hacen con **QWeb/XML/CSS** versionados (no dependencia
  exclusiva de Studio). Ver [`../15_ACCEPTANCE_CRITERIA.md`](../15_ACCEPTANCE_CRITERIA.md).

## Enterprise

Objetivo: Odoo 19 **Enterprise**. Requiere imagen/addons Enterprise con licencia
legítima. Estado actual: **BLOCKED** hasta contar con fuente/credenciales. Ver
[`ENTERPRISE_READINESS.md`](ENTERPRISE_READINESS.md).
