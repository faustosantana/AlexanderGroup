# Estrategia de backups — Doralex

Backups **verificables** desde el inicio, separados por entorno.

## Qué se respalda (por entorno)

- Base de datos PostgreSQL (`pg_dump -Fc`).
- Filestore de Odoo (`/var/lib/odoo/filestore`).
- Config renderizada (`odoo.conf`).
- Addons custom versionados.
- Metadata de compose/env (`docker-compose.yml`, `.env` con permisos `600`).

## Dónde

```text
/opt/doralex/backups/production/production_YYYYmmdd_HHMMSS/
/opt/doralex/backups/dev/dev_YYYYmmdd_HHMMSS/
```

> Nunca se guardan backups dentro del repo Git (`.gitignore`: `backups/`,
> `*.dump`, `*.sql`, `*.tar.gz`).

## Validez (regla dura)

Un backup **no** es válido solo porque el comando terminó. `backup.sh` genera y
`verify_backup.sh` valida:

- Presencia de todos los artefactos requeridos.
- Tamaño `> 0` (y `db.dump` por encima de un mínimo razonable).
- **Checksum SHA256** (`SHA256SUMS`) verificado.

```bash
bash scripts/backup.sh production            # crea + verifica
bash scripts/verify_backup.sh <dir_backup>   # revalida cuando se quiera
```

## Restauración

`restore.sh` es **destructivo** y exige confirmación:

```bash
CONFIRM=yes bash scripts/restore.sh dev <dir_backup>
CONFIRM=yes ALLOW_PROD=yes bash scripts/restore.sh production <dir_backup>
```

Antes de restaurar, `restore.sh` vuelve a validar el backup con `verify_backup.sh`.

## Recomendaciones

- Programar `backup.sh` por cron (p. ej. diario) por entorno.
- Copia **offsite cifrada** de los backups de Produccion.
- Probar la restauración periódicamente en Dev (backup de Prod → restore en Dev
  **solo** si se anonimiza; nunca montar volúmenes de Prod en Dev).
