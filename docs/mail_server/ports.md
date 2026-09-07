# Puertos — inventario 2026-09-07 (VPS Odoo, sin Mailcow)

Inventario `ss -tulpn`. No se detuvo nada.

| Puerto | Estado en VPS Odoo | Proceso | Uso futuro Mailcow |
|---|---|---|---|
| 22 | LISTEN 0.0.0.0 / :: | sshd | SSH (ya abierto UFW) |
| 25 | FREE | — | SMTP inbound (abrir en VPS correo + UFW) |
| 80 | LISTEN 0.0.0.0 | nginx | ACME / web Odoo. Mailcow **no** debe tomarlo aquí |
| 110 | FREE | — | POP: no exponer |
| 143 | FREE | — | IMAP STARTTLS opcional |
| 443 | LISTEN 0.0.0.0 | nginx | HTTPS Odoo/web. Mailcow **no** debe tomarlo aquí |
| 465 | FREE | — | SMTPS |
| 587 | FREE | — | Submission STARTTLS (Odoo SMTP) |
| 993 | FREE | — | IMAPS |
| 995 | FREE | — | POP: no exponer |
| 4190 | FREE | — | ManageSieve |
| 8069 | 127.0.0.1 | docker-proxy prod Odoo | no tocar |
| 8072 | 127.0.0.1 | docker-proxy prod longpolling | no tocar |
| 8169/8172 | 127.0.0.1 | docker-proxy dev | no tocar |
| 8269/8272 | 127.0.0.1 | docker-proxy staging | no tocar |
| 8080 | FREE | — | candidato HTTP_BIND Mailcow si se colocalizara |
| 8443 | FREE | — | candidato HTTPS_BIND Mailcow si se colocalizara |

UFW actual: deny incoming; allow 22/80/443 only.
Docker publica Odoo solo en loopback. Postgres no está en el host.

En el **VPS de correo** (cuando exista):

| Puerto | Exponer |
|---|---|
| 25 | sí |
| 465 | sí |
| 587 | sí |
| 993 | sí |
| 80/443 | sí (UI Mailcow + ACME) |
| 143 | opcional STARTTLS |
| 110/995 | no |
| 4190 | sí si se usa Sieve |
