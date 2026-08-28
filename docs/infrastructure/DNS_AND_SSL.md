# DNS y SSL — Doralex

## Dominios definitivos

| Entorno    | Dominio                     | Destino (loopback)   |
| ---------- | --------------------------- | -------------------- |
| Produccion | `doralexgroup.cloud`        | `127.0.0.1:8069`     |
| Produccion | `www.doralexgroup.cloud`    | 301 → `doralexgroup.cloud` |
| Dev        | `dev.doralexgroup.cloud`    | `127.0.0.1:8169`     |

## Estado: `DNS_REQUIRED` / `PENDING_DNS`

No se emiten certificados ni se activa `443` hasta verificar resolución real.
Registros DNS a crear (apuntando al servidor `2.25.121.111`):

```text
doralexgroup.cloud.       A      2.25.121.111
dev.doralexgroup.cloud.   A      2.25.121.111
www.doralexgroup.cloud.   A      2.25.121.111      ; (o CNAME -> doralexgroup.cloud.)
```

> `www` puede ser `A` a la misma IP o `CNAME` a `doralexgroup.cloud`. El reverse
> proxy redirige `www` → canónico con 301.

## Verificación de DNS (antes de emitir SSL)

```bash
dig +short doralexgroup.cloud        # debe devolver 2.25.121.111
dig +short dev.doralexgroup.cloud    # debe devolver 2.25.121.111
dig +short www.doralexgroup.cloud
```

Si **no** resuelven aún, el estado permanece `DNS_REQUIRED` y **no** se emiten
certificados (no crear certificados falsos).

### Estado dev (2026-08-27): `PASS` (DNS + SSL)

- `dev.doralexgroup.cloud` → `2.25.121.111` (registro `A` creado en Hostinger).
- **SSL emitido** con Let's Encrypt (`certbot --nginx -d dev.doralexgroup.cloud --redirect`):
  CN `dev.doralexgroup.cloud`, exp. **2026-11-25**, cadena válida (`ssl_verify_result=0`).
- `https://dev.doralexgroup.cloud/web/health` → **200**; HTTP→HTTPS **301** (sin loops);
  `X-Forwarded-Proto`/`X-Forwarded-For`/`Host` y `/websocket` (`:8172`) configurados;
  renovación automática vía `certbot.timer`.

## SSL (Let's Encrypt / certbot)

Cuando cada dominio resuelva a `2.25.121.111`:

```bash
certbot certonly --webroot -w /var/www/certbot -d doralexgroup.cloud -d www.doralexgroup.cloud
certbot certonly --webroot -w /var/www/certbot -d dev.doralexgroup.cloud
# luego descomentar el bloque 443 en los .conf y recargar nginx
```

- Renovación automática vía timer de certbot; `certbot renew --dry-run` para probar.
- HTTP redirige a HTTPS (301) una vez activo el bloque `443`.
- Certificados y llaves **nunca** se commitean (`*.pem`, `*.key`, `*.crt`).

## Verificación final

```bash
curl -I http://doralexgroup.cloud        # 301 -> https
curl -I https://doralexgroup.cloud       # 200 (Odoo)
curl -I https://www.doralexgroup.cloud   # 301 -> https://doralexgroup.cloud
```
