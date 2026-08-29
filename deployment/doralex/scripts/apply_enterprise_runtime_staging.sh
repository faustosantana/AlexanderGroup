#!/usr/bin/env bash
# Aplica la imagen Enterprise 19.0.20260324 a staging y instala SOLO web_enterprise.
# Nunca -u all. Nunca Prod.
# Uso: CONFIRM=yes bash apply_enterprise_runtime_staging.sh
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "${SCRIPT_DIR}/lib.sh"

[ "${CONFIRM:-no}" = "yes" ] || die "Aborta: exporte CONFIRM=yes."
load_env enterprise-staging
IMAGE="${ENTERPRISE_RUNTIME_IMAGE:-doralex-odoo-enterprise:19.0.20260324}"
ROOT="${DORALEX_BASE}/runtime-source/19.0-e-20260324"
ENVF="$(env_file enterprise-staging)"
CONF="$(env_dir enterprise-staging)/config/odoo.conf"

docker image inspect "$IMAGE" >/dev/null 2>&1 || die "Falta imagen ${IMAGE}"
[ -d "${ROOT}/enterprise/web_enterprise" ] || die "Falta árbol enterprise extraído."

bash "${SCRIPT_DIR}/check_staging_reports.sh"
QWEB_OUT_DIR="${DORALEX_BASE}/backups/staging/pre_runtime_import/qweb" \
  bash "${SCRIPT_DIR}/inventory_staging_qweb.sh"

# addons_path: Doralex custom primero (reportes), luego Enterprise, luego custom Justgroup.
if [ -f "$CONF" ]; then
  if grep -q '^addons_path' "$CONF"; then
    sed -i 's|^addons_path.*|addons_path = /mnt/custom-addons,/usr/lib/odoo/enterprise,/usr/lib/odoo/custom-addons|' "$CONF"
  else
    printf '\naddons_path = /mnt/custom-addons,/usr/lib/odoo/enterprise,/usr/lib/odoo/custom-addons\n' >> "$CONF"
  fi
fi
if grep -q '^ODOO_IMAGE=' "$ENVF"; then
  sed -i "s|^ODOO_IMAGE=.*|ODOO_IMAGE=${IMAGE}|" "$ENVF"
else
  printf 'ODOO_IMAGE=%s\n' "$IMAGE" >> "$ENVF"
fi

log "Arranque staging con runtime nuevo (sin -i)..."
dc enterprise-staging up -d
sleep 15
if ! bash "${SCRIPT_DIR}/healthcheck.sh" enterprise-staging; then
  die "STAGING_BOOT_ENTERPRISE_RUNTIME = FAIL"
fi
log "STAGING_BOOT_ENTERPRISE_RUNTIME = PASS"

# Descubrimiento
docker exec doralex-enterprise-staging-odoo python3 - <<'PY'
from pathlib import Path
print("WEB_ENTERPRISE_DISCOVERED =", (Path("/usr/lib/odoo/enterprise")/"web_enterprise"/"__manifest__.py").is_file())
print("ENTERPRISE_DISCOVERED_COUNT =", sum(1 for p in Path("/usr/lib/odoo/enterprise").glob("*/__manifest__.py")))
print("CUSTOM_DISCOVERED_COUNT =", sum(1 for p in Path("/usr/lib/odoo/custom-addons").rglob("__manifest__.py")))
PY

log "Instalando SOLO web_enterprise..."
docker exec -u 100:101 doralex-enterprise-staging-odoo bash -c \
  'python3 /usr/bin/odoo -d '"${POSTGRES_DB}"' --db_host="$HOST" --db_user="$USER" --db_password="$PASSWORD" --addons-path=/mnt/custom-addons,/usr/lib/odoo/enterprise,/usr/lib/odoo/custom-addons -i web_enterprise --stop-after-init --without-demo=all --no-http'

dc enterprise-staging up -d
sleep 12
bash "${SCRIPT_DIR}/healthcheck.sh" enterprise-staging
bash "${SCRIPT_DIR}/check_staging_reports.sh"
QWEB_OUT_DIR="${DORALEX_BASE}/backups/staging/post_web_enterprise/qweb" \
  mkdir -p "${DORALEX_BASE}/backups/staging/post_web_enterprise/qweb"
QWEB_OUT_DIR="${DORALEX_BASE}/backups/staging/post_web_enterprise/qweb" \
  bash "${SCRIPT_DIR}/inventory_staging_qweb.sh"

we_state="$(docker exec doralex-enterprise-staging-db \
  bash -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tAc "SELECT state FROM ir_module_module WHERE name='\''web_enterprise'\'';"')"
we_state="$(echo "$we_state" | tr -d '[:space:]')"
[ "$we_state" = "installed" ] || die "WEB_ENTERPRISE_INSTALLED = NO"
log "WEB_ENTERPRISE_INSTALLED = YES"
log "DORALEX_SUBSCRIPTION_ACTIVATION = PENDING"
log "JUSTGROUP_DATA_COPIED = NO"
log "CUTOVER_ALLOWED = NO"
bash "${SCRIPT_DIR}/healthcheck.sh" production
log "DORALEX_PROD_TOUCHED = NO"
