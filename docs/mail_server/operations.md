# Operación — estado actual y siguiente paso

## Qué está funcionando hoy (sin Mailcow)

- Odoo prod / staging / dev + Postgres: arriba, healthy.
- Nginx 80/443: `doralexgroup.cloud`, `www`, `dev`, `enterprise.doralexgroup.cloud`.
- Outbound TCP 25 desde este VPS: **sí** llega a Gmail y Outlook.
- Correo corporativo de las 6 empresas: Microsoft 365 (no tocado).
- `ir.mail_server` Odoo prod: 0. No se configuró SMTP.

## Qué no se hizo

- No se clonó ni levantó Mailcow.
- No se abrieron 25/587/465/993 en UFW.
- No se reinició Odoo, Nginx, Docker ni Postgres.
- No se cambiaron MX corporativos ni logins.

## Siguiente paso (acción tuya)

1. Contratar VPS KVM 8 GiB / 2–4 vCPU / 50+ GiB, IPv4 propia, PTR editable,
   puerto 25 libre (Hostinger u otro que no bloquee SMTP).
2. Enviar la IPv4 nueva.
3. Crear los DNS de `docs/mail_server/dns_records.md`.
4. En Hostinger: PTR de esa IP → `mail.erp.doralexgroup.cloud`.
5. Autorizar instalación de Mailcow **en ese VPS**, no en el de Odoo.

## Monitoreo (cuando exista)

`docker compose ps` en `/opt/mailcow-dockerized`, cola Postfix, disco,
vencimiento ACME. No se instaló stack extra de monitoring.

## Logs

N/A: no hay contenedores Mailcow. En el VPS Odoo no se buscaron errores
de Postfix/Dovecot porque no existen en el host.
