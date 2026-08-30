#!/usr/bin/env bash
# Clona la base Community de PRODUCCIÓN a enterprise-staging.
# No detiene ni modifica el stack de doralexgroup.cloud.
#
# Uso (en el servidor):
#   CONFIRM=yes bash clone_prod_to_enterprise_staging.sh \
#     /opt/doralex/backups/production/production_YYYYmmdd_HHMMSS
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "${SCRIPT_DIR}/lib.sh"

[ "${CONFIRM:-no}" = "yes" ] || die "Aborta: exporte CONFIRM=yes."
BACKUP_DIR="${1:-}"
[ -n "$BACKUP_DIR" ] || die "Uso: CONFIRM=yes $0 <dir_backup_production>"
bash "${SCRIPT_DIR}/verify_backup.sh" "$BACKUP_DIR" || die "Backup inválido."

require_cmd docker
require_cmd openssl
require_cmd rsync
require_cmd envsubst

STAGING_DIR="${DORALEX_BASE}/enterprise-staging"
REPO_STAGING="${DORALEX_BASE}/repository/deployment/doralex/enterprise-staging"
if [ ! -f "${REPO_STAGING}/docker-compose.yml" ]; then
  REPO_STAGING="$(cd "${SCRIPT_DIR}/../enterprise-staging" && pwd)"
fi
[ -f "${REPO_STAGING}/docker-compose.yml" ] || die "No encuentro plantilla enterprise-staging."

PROD_DIR="$(env_dir production)"
[ -d "${PROD_DIR}/custom-addons" ] || die "Falta custom-addons de producción."

log "Preparando ${STAGING_DIR} (no se toca production)..."
mkdir -p "${STAGING_DIR}/config" "${STAGING_DIR}/logs" \
  "${STAGING_DIR}/enterprise-addons" "${STAGING_DIR}/custom-addons"
if [ ! -f "${STAGING_DIR}/enterprise-addons/ENTERPRISE_SOURCE_PENDING" ]; then
  printf '%s\n' "ENTERPRISE_SOURCE_PENDING=TRUE" \
    > "${STAGING_DIR}/enterprise-addons/ENTERPRISE_SOURCE_PENDING"
fi

cp "${REPO_STAGING}/docker-compose.yml" "${STAGING_DIR}/docker-compose.yml"
cp "${REPO_STAGING}/config/odoo.conf.example" "${STAGING_DIR}/config/odoo.conf.example"

if [ ! -f "${STAGING_DIR}/.env" ]; then
  umask 077
  cat > "${STAGING_DIR}/.env" <<EOF
ODOO_ENVIRONMENT=enterprise-staging
POSTGRES_DB=doralex_ent_staging
POSTGRES_USER=doralex_ent_staging
POSTGRES_PASSWORD=$(openssl rand -hex 24)
ODOO_IMAGE=odoo:19
ODOO_ADMIN_PASSWD=$(openssl rand -hex 24)
ODOO_DBFILTER=^doralex_ent_staging\$
ODOO_HTTP_PORT=8269
ODOO_LONGPOLLING_PORT=8272
ENTERPRISE_SRC=./enterprise-addons
CUSTOM_ADDONS_SRC=./custom-addons
ENTERPRISE_SOURCE_PENDING=TRUE
ODOO_BASE_URL=https://enterprise.doralexgroup.cloud
EOF
  chmod 600 "${STAGING_DIR}/.env"
  log "Creado .env de staging (permisos 600)."
fi

log "Copiando custom-addons de producción (incluye justech_alexander_reports)..."
rsync -a --delete "${PROD_DIR}/custom-addons/" "${STAGING_DIR}/custom-addons/"

# Render odoo.conf usando el .env de staging.
load_env enterprise-staging
: "${ODOO_ADMIN_PASSWD:?}"
: "${ODOO_DBFILTER:?}"
umask 077
envsubst '${ODOO_ADMIN_PASSWD} ${ODOO_DBFILTER}' \
  < "${STAGING_DIR}/config/odoo.conf.example" \
  > "${STAGING_DIR}/config/odoo.conf"
chown "${ODOO_UID:-101}:${ODOO_GID:-101}" "${STAGING_DIR}/config/odoo.conf" 2>/dev/null || true
chmod 640 "${STAGING_DIR}/config/odoo.conf"

log "Levantando stack staging (red/volúmenes propios)..."
dc enterprise-staging up -d

log "Esperando DB healthy..."
for _ in $(seq 1 30); do
  if docker inspect --format '{{.State.Health.Status}}' doralex-enterprise-staging-db 2>/dev/null | grep -qx healthy; then
    break
  fi
  sleep 2
done

log "Deteniendo Odoo staging para restaurar..."
docker stop doralex-enterprise-staging-odoo >/dev/null

log "Restaurando dump de producción en doralex_ent_staging (--no-owner)..."
set +e
docker exec -i doralex-enterprise-staging-db \
  pg_restore -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" \
  --no-owner --role="${POSTGRES_USER}" --clean --if-exists \
  < "${BACKUP_DIR}/db.dump"
restore_rc=$?
set -e
log "pg_restore exit=${restore_rc} (1 suele ser avisos de --clean; se valida por conteo)."
mod_count="$(docker exec doralex-enterprise-staging-db \
  psql -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" -tAc \
  "SELECT COUNT(*) FROM ir_module_module WHERE state='installed';" | tr -d '[:space:]')"
log "Módulos instalados en el clon: ${mod_count}"
[ "${mod_count:-0}" -ge 50 ] || die "Restore incompleto (ir_module_module=${mod_count})."

log "Restaurando filestore (rename doralex_prod → doralex_ent_staging)..."
docker run --rm --user 0 \
  -v doralex_ent_staging_odoo_data:/var/lib/odoo \
  -v "${BACKUP_DIR}:/backup:ro" \
  "${ODOO_IMAGE:-odoo:19}" \
  sh -c 'mkdir -p /var/lib/odoo && tar xzf /backup/filestore.tar.gz -C /var/lib/odoo && if [ -d /var/lib/odoo/filestore/doralex_prod ]; then rm -rf /var/lib/odoo/filestore/doralex_ent_staging; mv /var/lib/odoo/filestore/doralex_prod /var/lib/odoo/filestore/doralex_ent_staging; fi; chown -R 101:101 /var/lib/odoo/filestore || true'

log "Neutralizando correo/cron (SQL nativo; no enviar mail de Prod)..."
docker exec -i doralex-enterprise-staging-db \
  psql -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" <<'SQL'
UPDATE ir_mail_server SET active = false;
INSERT INTO ir_mail_server (name, smtp_port, smtp_host, smtp_encryption, active, smtp_authentication)
SELECT 'neutralization - disable emails', 1025, 'invalid', 'none', true, 'login'
WHERE NOT EXISTS (SELECT 1 FROM ir_mail_server WHERE name = 'neutralization - disable emails');
UPDATE ir_cron SET active = false
 WHERE id NOT IN (
   SELECT res_id FROM ir_model_data WHERE model = 'ir.cron' AND name = 'autovacuum_job'
 );
UPDATE ir_config_parameter
   SET value = 'https://enterprise.doralexgroup.cloud'
 WHERE key = 'web.base.url';
SQL

log "Arrancando Odoo staging..."
docker start doralex-enterprise-staging-odoo >/dev/null
log "Esperando /web/health en 127.0.0.1:8269..."
for _ in $(seq 1 40); do
  if curl -fsS "http://127.0.0.1:8269/web/health" >/dev/null 2>&1; then
    log "Staging HTTP healthy."
    break
  fi
  sleep 3
done
for _ in $(seq 1 20); do
  if docker inspect --format '{{.State.Health.Status}}' doralex-enterprise-staging-odoo 2>/dev/null | grep -qx healthy; then
    break
  fi
  sleep 3
done
bash "${SCRIPT_DIR}/healthcheck.sh" enterprise-staging
log "CLONE STAGING COMPLETO. Prod no fue detenido ni modificado."
