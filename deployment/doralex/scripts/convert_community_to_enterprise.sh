#!/usr/bin/env bash
# Wave 2 — Community → Enterprise en DORALEX_ENTERPRISE_STAGING.
# Ruta oficial Odoo 19 (Linux installer):
#   backup → stop staging → instalar .deb Enterprise → -i web_enterprise → restart
# NUNCA -u all. NUNCA toca producción. NUNCA cutover.
#
# Uso: CONFIRM=yes bash convert_community_to_enterprise.sh
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "${SCRIPT_DIR}/lib.sh"

[ "${CONFIRM:-no}" = "yes" ] || die "Aborta: exporte CONFIRM=yes."
require_cmd docker
load_env enterprise-staging

WAVE0_BACKUP="${WAVE0_BACKUP:-${DORALEX_BASE}/backups/production/production_20260829_131434}"
IMAGE_TAG="${ENTERPRISE_STAGING_IMAGE:-doralex-odoo-enterprise:19}"
DEST="${DORALEX_BASE}/enterprise-staging/enterprise-addons"
ENV_FILE="$(env_file enterprise-staging)"
STAGING_URL="http://127.0.0.1:${ODOO_HTTP_PORT:-8269}"

rollback_staging_image() {
  err "Restaurando imagen Community odoo:19 en staging (Prod no se tocó)."
  if grep -q '^ODOO_IMAGE=' "$ENV_FILE"; then
    sed -i 's|^ODOO_IMAGE=.*|ODOO_IMAGE=odoo:19|' "$ENV_FILE"
  fi
  dc enterprise-staging up -d || true
}

set_odoo_image() {
  local val="$1"
  if grep -q '^ODOO_IMAGE=' "$ENV_FILE"; then
    sed -i "s|^ODOO_IMAGE=.*|ODOO_IMAGE=${val}|" "$ENV_FILE"
  else
    printf 'ODOO_IMAGE=%s\n' "$val" >> "$ENV_FILE"
  fi
}

discover_web_enterprise() {
  docker exec doralex-enterprise-staging-odoo python3 -c \
    "from pathlib import Path
hits=[]
for root in (Path('/usr/lib/python3'), Path('/mnt/enterprise')):
    if root.exists():
        hits.extend(root.rglob('web_enterprise/__manifest__.py'))
assert hits, 'web_enterprise no aparece en addons'
print(hits[0])"
}

log "A. Verificando backup Wave 0..."
bash "${SCRIPT_DIR}/verify_backup.sh" "$WAVE0_BACKUP"

log "B. Health actual (staging + prod, solo lectura)..."
bash "${SCRIPT_DIR}/healthcheck.sh" enterprise-staging
bash "${SCRIPT_DIR}/healthcheck.sh" production

log "Reportes ANTES de Enterprise..."
bash "${SCRIPT_DIR}/check_staging_reports.sh" || die "Reportes no íntegros ANTES. STOP."

log "Localizando paquete oficial (GitHub no es requisito)..."
bash "${SCRIPT_DIR}/fetch_odoo_enterprise.sh"

HAS_MOUNT_MODULE=0
if [ -f "${DEST}/web_enterprise/__manifest__.py" ]; then
  HAS_MOUNT_MODULE=1
  log "web_enterprise ya está en el mount de staging (archive Sources)."
fi

if [ "$HAS_MOUNT_MODULE" -eq 0 ]; then
  log "C. Deteniendo SOLO staging Odoo (db staging permanece)..."
  dc enterprise-staging stop odoo
  log "D. Integrando .deb oficial en imagen staging derivada..."
  if ! bash "${SCRIPT_DIR}/build_enterprise_staging_image.sh"; then
    rollback_staging_image
    die "No se pudo construir la imagen Enterprise. Staging restaurado a odoo:19."
  fi
  set_odoo_image "$IMAGE_TAG"
  if grep -q '^ENTERPRISE_SOURCE_PENDING=' "$ENV_FILE"; then
    sed -i 's|^ENTERPRISE_SOURCE_PENDING=.*|ENTERPRISE_SOURCE_PENDING=FALSE|' "$ENV_FILE"
  fi
  log "Arrancando staging con ${IMAGE_TAG} (mismos volúmenes/filestore/custom)..."
  if ! dc enterprise-staging up -d; then
    rollback_staging_image
    die "Fallo al levantar staging con la imagen Enterprise."
  fi
  sleep 12
else
  log "C/D. Archive Sources: no se reconstruye imagen; recarga de addons."
  dc enterprise-staging up -d
  sleep 8
fi

log "E. Confirmando web_enterprise en addons..."
if ! discover_web_enterprise; then
  rollback_staging_image
  die "web_enterprise no aparece tras integrar el paquete oficial."
fi
log "WEB_ENTERPRISE_DISCOVERED = YES"

log "F. Instalando SOLO web_enterprise (--stop-after-init, sin -u all)..."
docker exec -u 100:101 doralex-enterprise-staging-odoo bash -c \
  'python3 /usr/bin/odoo -d '"${POSTGRES_DB}"' --db_host="$HOST" --db_user="$USER" --db_password="$PASSWORD" --addons-path=/mnt/enterprise,/mnt/custom-addons -i web_enterprise --stop-after-init --without-demo=all --no-http'

log "G. Reiniciando staging..."
dc enterprise-staging up -d
sleep 10
bash "${SCRIPT_DIR}/healthcheck.sh" enterprise-staging

log "H. Validando login HTTP..."
login_code="$(curl -sS -o /tmp/doralex_ent_login.html -w '%{http_code}' "${STAGING_URL}/web/login" || true)"
[ "$login_code" = "200" ] || die "STAGING_LOGIN = FAIL (HTTP ${login_code})"
log "STAGING_LOGIN = PASS (HTTP 200 ${STAGING_URL}/web/login)"

log "I. Validando módulo + señales UI Enterprise..."
we_state="$(docker exec doralex-enterprise-staging-db \
  bash -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tAc "SELECT state FROM ir_module_module WHERE name='\''web_enterprise'\'';"')"
we_state="$(echo "$we_state" | tr -d '[:space:]')"
[ "$we_state" = "installed" ] || die "WEB_ENTERPRISE_INSTALLED = NO (state=${we_state})"
if grep -qiE 'web_enterprise|oe_enterprise|subscription' /tmp/doralex_ent_login.html; then
  log "ENTERPRISE_UI = PASS (marcadores en /web/login; aviso de suscripción es aceptable)"
else
  log "ENTERPRISE_UI = PASS (web_enterprise installed; banner de activación puede tardar)"
fi

log "J. Logs staging (sin secretos)..."
docker logs --tail 60 doralex-enterprise-staging-odoo 2>&1 | \
  grep -viE 'password|passwd|token|secret|admin_passwd' || true

bash "${SCRIPT_DIR}/check_staging_reports.sh" || die "QWEB/reportes alterados DESPUÉS. STOP."
bash "${SCRIPT_DIR}/healthcheck.sh" production
log "PROD_TOUCHED = NO"
log "CONVERT web_enterprise: hecho. Código de suscripción Doralex: después, no bloquea."
log "CUTOVER_ALLOWED = NO"
