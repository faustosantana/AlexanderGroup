# Backup

## Snapshot pre-decisión (VPS Odoo)

`PRE_MAIL_SERVER_BACKUP = PASS`

Ruta en servidor:

`/opt/doralex/backups/infrastructure/pre_mail_server_20260907_155122`

Incluye: nginx, docker-compose.yml (sin `.env`), ufw, iptables, nombres
Let's Encrypt, unidades systemd, snapshot DNS/PTR. Permisos `go-rwx`.

No se copió `.env` ni contraseñas a Git.

## Cuando Mailcow viva en VPS propio

Backup local validado + destino externo (otro disco/object storage).

Incluir: volúmenes mailbox, MariaDB Mailcow, Redis/config, DKIM **privado**
solo en el almacén de secretos (`/opt/.../secrets`, no Git).

Riesgo de backup solo en el mismo disco: pérdida total si muere el VPS.
Documentar y copiar fuera.

Odoo ya tiene `backup.sh` on-demand en `/opt/doralex`; no hay cron de backup
(HIGH previo, no de esta fase).
