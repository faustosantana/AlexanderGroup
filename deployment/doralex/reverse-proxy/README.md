# Reverse proxy (Nginx de host) — Doralex

Termina TLS y enruta por dominio hacia cada entorno Odoo, que **solo** escucha en
loopback:

| Dominio (definitivo)          | Entorno     | Upstream (loopback)   |
| ----------------------------- | ----------- | --------------------- |
| `doralexgroup.cloud`          | Produccion  | `127.0.0.1:8069/8072` |
| `www.doralexgroup.cloud`      | → redirect  | 301 → `doralexgroup.cloud` |
| `dev.doralexgroup.cloud`      | Dev         | `127.0.0.1:8169/8172` |

## Por qué proxy de host (y no un contenedor compartido)

El proxy habla con cada Odoo por `127.0.0.1`, por lo que **no** se conecta a las
redes Docker de Produccion ni de Dev. Así se preserva el aislamiento total.

## Estado: `PENDING_DNS`

No hay DNS confirmado para `*.doralexgroup.cloud`. **No** se emiten certificados ni
se activa el bloque `443` hasta que los dominios resuelvan a `2.25.121.111`.
Ver [`../../../docs/infrastructure/DNS_AND_SSL.md`](../../../docs/infrastructure/DNS_AND_SSL.md).

## Instalación (post-auditoría, en el servidor)

1. Copiar `*.conf.example` → `/etc/nginx/sites-available/<dominio>.conf` (quitar `.example`).
2. Habilitar: `ln -s /etc/nginx/sites-available/<dominio>.conf /etc/nginx/sites-enabled/`.
3. `nginx -t && systemctl reload nginx` (solo bloque `80` mientras `PENDING_DNS`).
4. Cuando el DNS resuelva: emitir certificados con certbot y descomentar `443`.

```bash
# Ejecutar SOLO cuando el DNS resuelva a 2.25.121.111:
certbot certonly --webroot -w /var/www/certbot -d doralexgroup.cloud -d www.doralexgroup.cloud
certbot certonly --webroot -w /var/www/certbot -d dev.doralexgroup.cloud
```

## Seguridad

- Un solo reverse proxy (no instalar dos).
- Certificados (`*.pem`, `*.key`, `*.crt`) **nunca** se commitean (`.gitignore`).
- PostgreSQL no se expone; el proxy solo alcanza Odoo por loopback.
