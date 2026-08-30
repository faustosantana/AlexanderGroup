#!/usr/bin/env bash
# Doralex — cutover Community → Enterprise en PRODUCCIÓN.
# NO restaura la DB de staging. NO -u all / -i all. NO toca Justgroup.
# Uso en el servidor: bash cutover_prod_enterprise.sh backup|inventory|...
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "${SCRIPT_DIR}/lib.sh"

require_cmd docker
require_cmd sha256sum
require_cmd nginx

PROD_DIR="$(env_dir production)"
STG_DIR="$(env_dir enterprise-staging)"
TS="${CUTOVER_TS:-$(date +%Y%m%d_%H%M%S)}"
BACKUP_ROOT="${DORALEX_BASE}/backups/production/pre_enterprise_cutover_${TS}"
MAINT_DIR="/var/www/doralex-maintenance"
NGINX_CONF="/etc/nginx/sites-enabled/doralex.conf"
IMAGE="doralex-odoo-enterprise:19.0.20260324"
PROD_DB_CT="doralex-production-db"
PROD_ODOO_CT="doralex-production-odoo"

log_file() { printf '%s' "${BACKUP_ROOT}/cutover.log"; }

cutover_log() {
  mkdir -p "${BACKUP_ROOT}"
  local line
  line="$(printf '[%s] %s' "$(date -u +'%Y-%m-%dT%H:%M:%SZ')" "$*")"
  printf '%s\n' "$line" | tee -a "$(log_file)"
}

enable_maintenance() {
  mkdir -p "${MAINT_DIR}"
  cat > "${MAINT_DIR}/index.html" <<'HTML'
<!DOCTYPE html>
<html lang="es">
<head><meta charset="utf-8"><title>Mantenimiento — Doralex</title></head>
<body style="font-family:sans-serif;text-align:center;padding:4rem">
<h1>Doralex Group</h1>
<p>Estamos realizando una actualización controlada.</p>
<p>El servicio volverá en breve.</p>
</body>
</html>
HTML
  cp -a "${MAINT_DIR}/index.html" "${MAINT_DIR}/cutover-maintenance.html"
  touch "${MAINT_DIR}/CUTOVER_ON"
  cutover_log "MAINTENANCE_ON"
}

disable_maintenance() {
  rm -f "${MAINT_DIR}/CUTOVER_ON"
  cutover_log "MAINTENANCE_OFF"
}

inventory_sql() {
  local dest="$1"
  mkdir -p "${dest}"
  docker exec "${PROD_DB_CT}" psql -U doralex_prod -d doralex_prod -c \
    "COPY (SELECT name, state, latest_version, license FROM ir_module_module ORDER BY name) TO STDOUT WITH CSV HEADER" \
    > "${dest}/modules.csv"
  docker exec "${PROD_DB_CT}" psql -U doralex_prod -d doralex_prod -c \
    "COPY (SELECT id, key, type, name FROM ir_ui_view WHERE type='qweb' AND COALESCE(key,'') LIKE 'justech_alexander_%' ORDER BY key) TO STDOUT WITH CSV HEADER" \
    > "${dest}/qweb.csv"
  docker exec "${PROD_DB_CT}" psql -U doralex_prod -d doralex_prod -c \
    "COPY (SELECT id, report_name, name::text FROM ir_act_report_xml ORDER BY id) TO STDOUT WITH CSV HEADER" \
    > "${dest}/reports.csv"
  docker exec "${PROD_DB_CT}" psql -U doralex_prod -d doralex_prod -c \
    "COPY (SELECT id, name, smtp_host FROM ir_mail_server ORDER BY id) TO STDOUT WITH CSV HEADER" \
    > "${dest}/mail_servers.csv"
  docker exec "${PROD_DB_CT}" psql -U doralex_prod -d doralex_prod -c \
    "COPY (SELECT key FROM ir_config_parameter ORDER BY key) TO STDOUT WITH CSV HEADER" \
    > "${dest}/system_parameter_keys.csv"
  docker exec "${PROD_DB_CT}" psql -U doralex_prod -d doralex_prod -c \
    "COPY (SELECT id, name, email FROM res_company ORDER BY id) TO STDOUT WITH CSV HEADER" \
    > "${dest}/companies.csv"
  docker exec "${PROD_DB_CT}" psql -U doralex_prod -d doralex_prod -c \
    "COPY (SELECT id, login, active FROM res_users ORDER BY id) TO STDOUT WITH CSV HEADER" \
    > "${dest}/users.csv"
  docker exec "${PROD_DB_CT}" psql -U doralex_prod -d doralex_prod -c \
    "COPY (SELECT id, url, website_indexed FROM website_page ORDER BY id) TO STDOUT WITH CSV HEADER" \
    > "${dest}/website_pages.csv"
  docker exec "${PROD_DB_CT}" psql -U doralex_prod -d doralex_prod -c \
    "COPY (SELECT id, name::text, url FROM website_menu ORDER BY id) TO STDOUT WITH CSV HEADER" \
    > "${dest}/website_menus.csv"
  docker exec "${PROD_DB_CT}" psql -U doralex_prod -d doralex_prod -tAc \
    "SELECT COUNT(*) FROM ir_ui_view WHERE type='qweb' AND COALESCE(key,'') LIKE 'justech_alexander_%'" \
    > "${dest}/qweb_count.txt"
}

cmd_backup() {
  load_env production
  : "${POSTGRES_DB:?}"; : "${POSTGRES_USER:?}"
  mkdir -p "${BACKUP_ROOT}/inventories" "${BACKUP_ROOT}/nginx"
  cutover_log "CUTOVER_START_TIME=$(date -u +'%Y-%m-%dT%H:%M:%SZ')"
  cutover_log "BACKUP_ROOT=${BACKUP_ROOT}"
  inventory_sql "${BACKUP_ROOT}/inventories/before"
  cp -a "${NGINX_CONF}" "${BACKUP_ROOT}/nginx/doralex.conf"
  cp -a /etc/nginx/sites-enabled/enterprise.doralexgroup.cloud.conf \
    "${BACKUP_ROOT}/nginx/" 2>/dev/null || true
  tar czf "${BACKUP_ROOT}/production_tree.tar.gz" \
    -C /opt/doralex \
    --exclude=production/logs \
    --exclude='production/.env' \
    production
  if [ -f "${PROD_DIR}/.env" ]; then
    cp "${PROD_DIR}/.env" "${BACKUP_ROOT}/env.backup"
    chmod 600 "${BACKUP_ROOT}/env.backup"
  fi
  enable_maintenance
  if grep -q 'CUTOVER_ON' "${NGINX_CONF}"; then
    cutover_log "nginx already has maintenance hook"
  else
    python3 - <<'PY'
from pathlib import Path
p = Path("/etc/nginx/sites-enabled/doralex.conf")
text = p.read_text()
old = """    location / {
        proxy_pass http://127.0.0.1:8069;"""
new = """    error_page 503 /cutover-maintenance.html;
    location = /cutover-maintenance.html {
        root /var/www/doralex-maintenance;
        internal;
    }
    location / {
        if (-f /var/www/doralex-maintenance/CUTOVER_ON) {
            return 503;
        }
        proxy_pass http://127.0.0.1:8069;"""
if old not in text:
    raise SystemExit("nginx location / marker not found")
# Only first production server block occurrence
text = text.replace(old, new, 1)
p.write_text(text)
print("nginx maintenance hook inserted")
PY
  fi
  nginx -t
  nginx -s reload
  cutover_log "Stopping production Odoo (Postgres stays up)"
  dc production stop odoo
  cutover_log "Dumping production DB"
  docker exec "${PROD_DB_CT}" pg_dump -U "${POSTGRES_USER}" -Fc "${POSTGRES_DB}" \
    > "${BACKUP_ROOT}/db.dump"
  cutover_log "Archiving filestore"
  docker run --rm -v doralex_prod_odoo_data:/var/lib/odoo:ro alpine \
    sh -c 'cd /var/lib/odoo && tar czf - filestore' > "${BACKUP_ROOT}/filestore.tar.gz"
  cp "${PROD_DIR}/config/odoo.conf" "${BACKUP_ROOT}/odoo.conf"
  tar czf "${BACKUP_ROOT}/custom-addons.tar.gz" -C "${PROD_DIR}" custom-addons
  tar czf "${BACKUP_ROOT}/config.tar.gz" -C "${PROD_DIR}" config
  cp "${PROD_DIR}/docker-compose.yml" "${BACKUP_ROOT}/docker-compose.yml"
  docker inspect "${IMAGE}" --format '{{.Id}}' > "${BACKUP_ROOT}/enterprise_image.id"
  docker inspect doralex-production-odoo --format '{{.Config.Image}} {{.Image}}' \
    > "${BACKUP_ROOT}/old_odoo_image.txt" || true
  (
    cd "${BACKUP_ROOT}"
    sha256sum db.dump filestore.tar.gz odoo.conf custom-addons.tar.gz \
      config.tar.gz docker-compose.yml production_tree.tar.gz \
      enterprise_image.id > SHA256SUMS
  )
  {
    echo "environment=production"
    echo "timestamp=${TS}"
    echo "db=${POSTGRES_DB}"
    echo "created_at=$(date -u +'%Y-%m-%dT%H:%M:%SZ')"
    echo "purpose=pre_enterprise_cutover"
  } > "${BACKUP_ROOT}/MANIFEST"
  cutover_log "Verifying checksums"
  bash "${SCRIPT_DIR}/verify_backup.sh" "${BACKUP_ROOT}"
  cutover_log "Restore-test into throwaway database"
  docker cp "${BACKUP_ROOT}/db.dump" "${PROD_DB_CT}:/tmp/pre_cutover_restore.check.dump"
  docker exec "${PROD_DB_CT}" dropdb -U "${POSTGRES_USER}" --if-exists doralex_prod_restore_check
  docker exec "${PROD_DB_CT}" createdb -U "${POSTGRES_USER}" doralex_prod_restore_check
  docker exec "${PROD_DB_CT}" pg_restore -U "${POSTGRES_USER}" -d doralex_prod_restore_check \
    --no-owner --no-acl /tmp/pre_cutover_restore.check.dump
  docker exec "${PROD_DB_CT}" psql -U "${POSTGRES_USER}" -d doralex_prod_restore_check -tAc \
    "SELECT COUNT(*) FROM res_company" > "${BACKUP_ROOT}/restore_company_count.txt"
  docker exec "${PROD_DB_CT}" dropdb -U "${POSTGRES_USER}" doralex_prod_restore_check
  docker exec "${PROD_DB_CT}" rm -f /tmp/pre_cutover_restore.check.dump
  tar tzf "${BACKUP_ROOT}/filestore.tar.gz" >/dev/null
  cutover_log "PROD_PRE_CUTOVER_BACKUP = PASS"
  cutover_log "PROD_BACKUP_PATH = ${BACKUP_ROOT}"
}

case "${1:-}" in
  backup) cmd_backup ;;
  maintenance-on) enable_maintenance; nginx -s reload ;;
  maintenance-off) disable_maintenance; nginx -s reload ;;
  *) die "Uso: $0 backup|maintenance-on|maintenance-off" ;;
esac
