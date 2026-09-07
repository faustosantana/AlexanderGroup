# 14 — Backups

## Backup de esta fase

```
OPERATIONAL_READINESS_BACKUP = PASS
NAME = pre_alexander_operational_readiness_20260907_093742
PATH = /opt/doralex/backups/production/production_20260907_093742
```

Incluye: `db.dump`, `filestore.tar.gz`, `config.tar.gz`, `custom-addons.tar.gz`, `odoo.conf`, `docker-compose.yml`, `env.backup`, `MANIFEST`, `SHA256SUMS`.

```
db.dump SHA256 = 2390117899fac821d42170e03bd4b79ad37a69ed6de6003eb61d3e5a31d6639a
pg_restore -l = 33990
TOC Entries = 33979
Format = CUSTOM gzip
Dumped from PostgreSQL 16.15
dbname = doralex_prod
created_at = 2026-09-07T13:37:46Z
verify_backup.sh = BACKUP VALIDO
```

Restore: `restore.sh` exige `CONFIRM=yes` y `ALLOW_PROD=yes`. **No se restauró prod.** `RESTORE_VALIDATED = PARTIAL` (TOC + checksum; sin restore destructivo).

## Programado

No hay crontab root ni systemd timer que ejecute `backup.sh`.
`BACKUP_STRATEGY.md` recomienda cron diario; **no está instalado**.

Backups on-demand previos existen (`production_20260905_135703` cutover apertura, etc.). Retention = directorio local `/opt/doralex/backups/production`. Offsite: no evidenciado.

`BACKUP_READY = PARTIAL`
`HIGH`: producción con CxC real sin backup automático.
