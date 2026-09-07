# Arquitectura prevista — correo Alexander (erp)

Fecha: 2026-09-07. **Mailcow no se instaló en el VPS de Odoo.**

## Por qué no en este VPS

Mailcow oficial: **6 GiB RAM + 1 GiB swap** solo para el stack de correo.
Este host (`2.25.121.111`, Hostinger KVM, 2 CPU, 7.8 GiB, **0 swap**) ya corre:

- Odoo prod + Postgres prod (~2.1 GiB)
- Odoo staging + Postgres staging (~0.8 GiB)
- Odoo dev + Postgres dev (~0.7 GiB)
- Docker/nginx/sistema

Quedan ~3.4 GiB. Instalar Mailcow aquí deja a Odoo expuesto a OOM.
`MAILCOW_RESOURCE_STATUS = FAIL`.

## Diseño correcto

```
Internet
   |
   | 25/465/587/993  +  80/443 (solo mail UI)
   v
VPS CORREO (nuevo)  mail.erp.doralexgroup.cloud
   Mailcow dockerized
   dominio: erp.doralexgroup.cloud
   |
   | SMTP 587 STARTTLS (cuando Odoo SMTP esté listo)
   v
VPS ODOO (actual)   doralexgroup.cloud / enterprise / dev
   Nginx 80/443
   Odoo prod/staging/dev
```

No se toca:

- MX de `inversionesdoralex.com`, `pinariagroup.com`, `dominion-business.com`,
  `elmayuma.com`, `rempartgroup.com`, `blueelite.net` (Microsoft 365).
- Website `doralexgroup.cloud`.
- Contenedores Odoo/Postgres.
- Hostname `mail.erp.doralexgroup.cloud` está libre (0 registros DNS).

## Hostname

| Campo | Valor |
|---|---|
| MAIL_DOMAIN | `erp.doralexgroup.cloud` |
| MAIL_HOSTNAME | `mail.erp.doralexgroup.cloud` |
| CURRENT_DNS | vacío |
| CURRENT_MX | vacío en `erp.` |
| CURRENT_PTR (IP Odoo) | `srv1935521.hstgr.cloud.` |

`doralexgroup.cloud` ya tiene MX hacia sí mismo (web). No se cambia.
El correo de login Odoo vive en el **subdominio** `erp.`.

## Si más adelante se insiste en el VPS actual

Solo con autorización explícita y aceptando riesgo:

1. Añadir 4 GiB swap.
2. Apagar **dev** (y preferible staging) mientras Mailcow corre.
3. `SKIP_CLAMD=y` y `SKIP_FTS=y`.
4. Bind HTTP/HTTPS Mailcow a `127.0.0.1:8080/8443` y proxy por Nginx.
5. Aun así queda **por debajo** del mínimo oficial de 6+1 GiB.

No se recomienda.
