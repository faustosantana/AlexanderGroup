#!/usr/bin/env bash
# Instala web_enterprise en enterprise-staging. NO usa -u all.
# NO toca producción.
#
# Uso: CONFIRM=yes bash convert_community_to_enterprise.sh
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "${SCRIPT_DIR}/lib.sh"

[ "${CONFIRM:-no}" = "yes" ] || die "Aborta: exporte CONFIRM=yes."
require_cmd docker
load_env enterprise-staging

DEST="${DORALEX_BASE}/enterprise-staging/enterprise-addons"
[ -f "${DEST}/web_enterprise/__manifest__.py" ] || \
  die "Falta web_enterprise en ${DEST}. Ejecute fetch_odoo_enterprise.sh."

log "Reiniciando Odoo staging para recargar addons Enterprise..."
dc enterprise-staging up -d
sleep 5

log "Instalando SOLO web_enterprise (--stop-after-init, sin -u all)..."
docker exec -u 100:101 doralex-enterprise-staging-odoo bash -c \
  'python3 /usr/bin/odoo -d '"${POSTGRES_DB}"' --db_host="$HOST" --db_user="$USER" --db_password="$PASSWORD" --addons-path=/mnt/enterprise,/mnt/custom-addons -i web_enterprise --stop-after-init --without-demo=all --no-http'

log "Arrancando de nuevo el servicio..."
dc enterprise-staging up -d
sleep 8
bash "${SCRIPT_DIR}/healthcheck.sh" enterprise-staging
log "CONVERT web_enterprise: hecho. Active el código de suscripción Doralex en Ajustes."
