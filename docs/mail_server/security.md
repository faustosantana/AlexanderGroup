# Seguridad — gate y pendientes

## Hecho

- No se expuso panel Mailcow (no hay).
- No se usaron credenciales default (no hay).
- Contraseñas de buzones: no generadas; no van a Git/chat.
- UFW host Odoo sigue deny-incoming excepto 22/80/443.
- Open relay: no aplicable (nada escucha 25).

## Pendiente en el VPS de correo

- Admin Mailcow: cambiar default + 2FA.
- Fail2ban nativo de Mailcow; no instalar un segundo fail2ban en el host
  que pelee con Docker.
- Rspamd + DNSBL con política inicial suave.
- Validar `OPEN_RELAY = NO` con un cliente no autenticado a un tercero.
- Reputación: PTR coherente + HELO = `mail.erp.doralexgroup.cloud`.
- IP `2.25.121.111` (VPS Odoo): Spamcop/Barracuda/SORBS sin listing.
  Spamhaus public query devolvió `127.255.255.254` (respuesta de política
  de resolver, no un hit de lista).

## Docker + firewall

UFW no filtra publicaciones Docker por sí solo. En el VPS correo:
reglas `DOCKER-USER` / nft compatibles; no deshabilitar UFW a ciegas.

## TLS

Certificado `mail.erp.doralexgroup.cloud` por ACME en el VPS correo
(80/443 libres ahí). No quitar validación TLS.
