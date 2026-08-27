#!/usr/bin/env bash
# Doralex — RESTORE desde un backup (OPERACION DESTRUCTIVA).
# ==============================================================================
# Sobrescribe la base de datos y el filestore del entorno indicado. Requiere
# confirmación explícita (CONFIRM=yes) para evitar accidentes.
#
# Uso:
#   CONFIRM=yes bash restore.sh dev /opt/doralex/backups/dev/dev_YYYYmmdd_HHMMSS
#
# Por seguridad, NO se permite restaurar sobre 'production' sin, además,
# ALLOW_PROD=yes (doble barrera).
# ==============================================================================
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "${SCRIPT_DIR}/lib.sh"

ENV_NAME="$(require_env_name "${1:-}")"
BACKUP_DIR="${2:-}"
[ -n "$BACKUP_DIR" ] || die "Uso: CONFIRM=yes restore.sh <production|dev> <dir_backup>"
[ "${CONFIRM:-no}" = "yes" ] || die "Aborta: exporte CONFIRM=yes para confirmar."
if [ "$ENV_NAME" = "production" ] && [ "${ALLOW_PROD:-no}" != "yes" ]; then
  die "Restaurar Produccion requiere además ALLOW_PROD=yes."
fi

require_cmd docker
bash "${SCRIPT_DIR}/verify_backup.sh" "$BACKUP_DIR" || die "Backup inválido, no se restaura."
load_env "$ENV_NAME"
: "${POSTGRES_DB:?}"; : "${POSTGRES_USER:?}"

DB_CT="$(db_container "$ENV_NAME")"
ODOO_CT="$(odoo_container "$ENV_NAME")"

log "Deteniendo Odoo (${ODOO_CT}) para restaurar de forma consistente..."
docker stop "$ODOO_CT" >/dev/null

log "Restaurando base de datos ${POSTGRES_DB}..."
docker exec -i "$DB_CT" pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists \
  < "${BACKUP_DIR}/db.dump"

log "Restaurando filestore..."
docker exec -i "$ODOO_CT" sh -c 'rm -rf /var/lib/odoo/filestore && tar xzf - -C /var/lib/odoo' \
  < "${BACKUP_DIR}/filestore.tar.gz" || err "No se pudo restaurar filestore (revisar)."

log "Reiniciando Odoo..."
docker start "$ODOO_CT" >/dev/null
log "RESTORE COMPLETO para ${ENV_NAME}. Verifique salud con healthcheck.sh."
