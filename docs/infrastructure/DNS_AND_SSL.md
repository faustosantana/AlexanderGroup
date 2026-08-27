# DNS y SSL — Doralex

## Estado: `PENDING_DNS`

No se asume DNS final ni se inventan registros. Los dominios previstos son:

| Entorno    | Dominio previsto         | Destino (loopback)   |
| ---------- | ------------------------ | -------------------- |
| Produccion | `erp.doralexgroup.com`   | `127.0.0.1:8069`     |
| Dev        | `dev.doralexgroup.com`   | `127.0.0.1:8169`     |

## Registros DNS a crear (cuando se confirme el dominio)

```text
erp.doralexgroup.com.   A   2.25.121.111
dev.doralexgroup.com.   A   2.25.121.111
```

> **Pendiente de confirmar:** titularidad/gestión del dominio `doralexgroup.com`,
> proveedor DNS y TTL. Hasta entonces, el reverse proxy solo sirve el bloque `:80`
> (para el challenge ACME) y **no** se emiten certificados.

## SSL (Let's Encrypt / certbot)

Una vez que cada dominio resuelva a `2.25.121.111`:

```bash
certbot certonly --webroot -w /var/www/certbot -d erp.doralexgroup.com
certbot certonly --webroot -w /var/www/certbot -d dev.doralexgroup.com
# luego descomentar el bloque 443 en los .conf del reverse proxy y recargar nginx
```

- Renovación automática vía timer de certbot.
- Certificados y llaves **nunca** se commitean (`.gitignore`: `*.pem`, `*.key`, `*.crt`).

## Verificación

```bash
dig +short erp.doralexgroup.com     # debe devolver 2.25.121.111
curl -I https://erp.doralexgroup.com
```
