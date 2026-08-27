#!/usr/bin/env bash
# Doralex — renderiza config/odoo.conf desde odoo.conf.example usando el .env.
# Sustituye ${VARIABLES} con los valores del entorno. El archivo resultante
# (config/odoo.conf) contiene el master password y por eso NO se versiona.
#
# Uso:  bash render_config.sh production   |   bash render_config.sh dev
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "${SCRIPT_DIR}/lib.sh"

require_cmd envsubst
ENV_NAME="$(require_env_name "${1:-}")"
DIR="$(env_dir "$ENV_NAME")"
TEMPLATE="${DIR}/config/odoo.conf.example"
TARGET="${DIR}/config/odoo.conf"

[ -f "$TEMPLATE" ] || die "No existe la plantilla: ${TEMPLATE}"
load_env "$ENV_NAME"

: "${ODOO_ADMIN_PASSWD:?Defina ODOO_ADMIN_PASSWD en .env}"
: "${ODOO_DBFILTER:?Defina ODOO_DBFILTER en .env}"

umask 077
# Comillas simples intencionales: envsubst recibe la lista LITERAL de variables
# a sustituir (así no toca otros ${...} del archivo).
# shellcheck disable=SC2016
envsubst '${ODOO_ADMIN_PASSWD} ${ODOO_DBFILTER}' < "$TEMPLATE" > "$TARGET"
chmod 600 "$TARGET"
log "Renderizado ${TARGET} (permisos 600). No lo commitees."
