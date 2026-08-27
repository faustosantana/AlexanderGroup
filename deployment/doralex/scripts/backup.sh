#!/usr/bin/env bash
# Doralex — BACKUP verificable por entorno (DB + filestore + config + addons + metadata).
# ==============================================================================
# Un backup NO se considera válido solo porque el comando terminó: al final se
# valida existencia, tamaño (>0) y checksum (SHA256) de cada artefacto.
#
# Uso (en el servidor, con Docker levantado):
#   bash backup.sh production
#   bash backup.sh dev
# ==============================================================================
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "${SCRIPT_DIR}/lib.sh"

ENV_NAME="$(require_env_name "${1:-}")"
require_cmd docker
require_cmd sha256sum
load_env "$ENV_NAME"

: "${POSTGRES_DB:?}"; : "${POSTGRES_USER:?}"

TS="$(date +%Y%m%d_%H%M%S)"
DEST="$(backup_root "$ENV_NAME")/${ENV_NAME}_${TS}"
DB_CT="$(db_container "$ENV_NAME")"
ODOO_CT="$(odoo_container "$ENV_NAME")"

umask 077
mkdir -p "$DEST"
log "Backup ${ENV_NAME} -> ${DEST}"

# 1) Base de datos (formato custom, comprimido).
log "Volcando base de datos ${POSTGRES_DB}..."
docker exec "$DB_CT" pg_dump -U "$POSTGRES_USER" -Fc "$POSTGRES_DB" > "${DEST}/db.dump"

# 2) Filestore de Odoo.
log "Copiando filestore..."
docker exec "$ODOO_CT" sh -c 'cd /var/lib/odoo && tar czf - filestore 2>/dev/null || true' \
  > "${DEST}/filestore.tar.gz"

# 3) Config renderizada (odoo.conf) y addons custom.
if [ -f "$(env_dir "$ENV_NAME")/config/odoo.conf" ]; then
  cp "$(env_dir "$ENV_NAME")/config/odoo.conf" "${DEST}/odoo.conf"
fi
if [ -d "$(env_dir "$ENV_NAME")/addons" ]; then
  tar czf "${DEST}/addons.tar.gz" -C "$(env_dir "$ENV_NAME")" addons
fi

# 4) Metadata de compose/env (el .env se guarda con permisos 600 para DR).
cp "$(compose_file "$ENV_NAME")" "${DEST}/docker-compose.yml"
if [ -f "$(env_file "$ENV_NAME")" ]; then
  cp "$(env_file "$ENV_NAME")" "${DEST}/env.backup"
  chmod 600 "${DEST}/env.backup"
fi

# 5) Checksums y manifiesto.
( cd "$DEST" && sha256sum ./* > SHA256SUMS )
{
  echo "environment=${ENV_NAME}"
  echo "timestamp=${TS}"
  echo "db=${POSTGRES_DB}"
  echo "created_at=$(date -u +'%Y-%m-%dT%H:%M:%SZ')"
} > "${DEST}/MANIFEST"

# 6) Validación inmediata (tamaño + checksum).
log "Validando backup recién creado..."
bash "${SCRIPT_DIR}/verify_backup.sh" "$DEST"

log "Backup COMPLETO y VERIFICADO: ${DEST}"
