#!/usr/bin/env bash
# Clona github.com/odoo/enterprise (rama 19.0) hacia enterprise-staging.
# NO escribe en /opt/doralex/enterprise (Prod Community monta ese path).
# NO copia addons Enterprise de Justgroup.
#
# Credencial (una de):
#   ODOO_ENTERPRISE_GITHUB_TOKEN
#   /opt/doralex/secrets/odoo_enterprise/github_token
#   GIT_ASKPASS / SSH a github.com con acceso al repo privado
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "${SCRIPT_DIR}/lib.sh"

DEST="${DORALEX_BASE}/enterprise-staging/enterprise-addons"
SHARED="${DORALEX_BASE}/enterprise"
BRANCH="${ODOO_ENTERPRISE_BRANCH:-19.0}"
TOKEN_FILE="${DORALEX_BASE}/secrets/odoo_enterprise/github_token"

if [ -d "${SHARED}" ] && [ ! -f "${SHARED}/ENTERPRISE_SOURCE_PENDING" ]; then
  log "AVISO: ${SHARED} ya tiene contenido; este script no lo modifica."
fi

mkdir -p "${DORALEX_BASE}/enterprise-staging"
TOKEN="${ODOO_ENTERPRISE_GITHUB_TOKEN:-}"
if [ -z "$TOKEN" ] && [ -f "$TOKEN_FILE" ]; then
  TOKEN="$(tr -d '[:space:]' < "$TOKEN_FILE")"
fi

if [ -z "$TOKEN" ]; then
  err "ENTERPRISE_SOURCE = MISSING"
  err "La suscripción no entrega el código sola: hace falta acceso al repo privado"
  err "github.com/odoo/enterprise (cuenta GitHub vinculada en odoo.com)."
  err "Coloque la credencial de lectura del repo privado en:"
  err "  variable de entorno ODOO_ENTERPRISE_GITHUB_TOKEN"
  err "  o el archivo ${TOKEN_FILE}"
  exit 2
fi

TMP="$(mktemp -d)"
cleanup() { rm -rf "$TMP"; }
trap cleanup EXIT

log "Clonando odoo/enterprise@${BRANCH} (depth=1)..."
GIT_TERMINAL_PROMPT=0 git clone --depth 1 --branch "$BRANCH" \
  "https://x-access-token:${TOKEN}@github.com/odoo/enterprise.git" \
  "${TMP}/enterprise"

[ -f "${TMP}/enterprise/web_enterprise/__manifest__.py" ] || \
  die "El clon no contiene web_enterprise. ¿rama incorrecta?"

rsync -a --delete \
  --exclude '.git' \
  "${TMP}/enterprise/" "${DEST}/"
# Quitar el marcador pending si el árbol es real.
rm -f "${DEST}/ENTERPRISE_SOURCE_PENDING"
log "Enterprise addons en ${DEST} (web_enterprise presente)."
log "Prod /opt/doralex/enterprise NO fue modificado."
