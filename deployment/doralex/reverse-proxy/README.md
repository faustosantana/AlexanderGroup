# Reverse proxy (Nginx de host) — Doralex

Termina TLS y enruta por dominio hacia cada entorno Odoo, que **solo** escucha en
loopback:

| Dominio (previsto)          | Entorno     | Upstream (loopback)   |
| --------------------------- | ----------- | --------------------- |
| `erp.doralexgroup.com`      | Produccion  | `127.0.0.1:8069/8072` |
| `dev.doralexgroup.com`      | Dev         | `127.0.0.1:8169/8172` |

## Por qué proxy de host (y no un contenedor compartido)

El proxy habla con cada Odoo por `127.0.0.1`, por lo que **no** se conecta a las
redes Docker de Produccion ni de Dev. Así se preserva el aislamiento total entre
entornos (redes/volúmenes/DB separados).

## Estado: `PENDING_DNS`

No hay DNS confirmado para `*.doralexgroup.com`. **No** se emiten certificados ni
se activa el bloque `443` hasta que los dominios resuelvan a la IP del servidor.
Ver [`../../../docs/infrastructure/DNS_AND_SSL.md`](../../../docs/infrastructure/DNS_AND_SSL.md).

## Instalación (post-auditoría, en el servidor)

1. Copiar `*.conf.example` → `/etc/nginx/sites-available/<dominio>.conf` (quitar `.example`).
2. Habilitar: `ln -s /etc/nginx/sites-available/<dominio>.conf /etc/nginx/sites-enabled/`.
3. `nginx -t && systemctl reload nginx` (solo bloque `80` mientras `PENDING_DNS`).
4. Cuando el DNS resuelva: emitir certificado con certbot y descomentar el bloque `443`.

```bash
# Ejemplo (ejecutar SOLO cuando el DNS resuelva):
certbot certonly --webroot -w /var/www/certbot -d erp.doralexgroup.com
certbot certonly --webroot -w /var/www/certbot -d dev.doralexgroup.com
```

## Seguridad

- Los certificados (`*.pem`, `*.key`, `*.crt`) **nunca** se commitean (`.gitignore`).
- PostgreSQL no se expone; el proxy solo alcanza Odoo por loopback.
