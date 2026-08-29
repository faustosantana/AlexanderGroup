#!/usr/bin/env bash
# Copia SOLO el árbol de addons Enterprise desde Justgroup (solo lectura).
# NO copia DB, filestore, correos, clientes, ni códigos de suscripción.
# NO escribe en /opt/doralex/enterprise (Prod Community lo monta).
# Destino: /opt/doralex/enterprise-addons/19/
#
# Uso: CONFIRM=yes bash copy_justgroup_enterprise_runtime.sh
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "${SCRIPT_DIR}/lib.sh"

[ "${CONFIRM:-no}" = "yes" ] || die "Aborta: exporte CONFIRM=yes."
require_cmd rsync
require_cmd ssh
require_cmd sha256sum

DEST="${DORALEX_BASE}/enterprise-addons/19"
INV="${DORALEX_BASE}/enterprise-addons/19.inventory"
SRC_HOST="justgroup-vps"
# Ruta conocida por auditoría 2026-08-27; se revalida en remoto.
REMOTE_CANDIDATES="/usr/lib/odoo/enterprise /opt/odoo/enterprise"

ssh -o BatchMode=yes -o ConnectTimeout=12 "$SRC_HOST" 'true' \
  || die "Sin SSH justgroup-vps. Configure JUSTGROUP_SSH_PRIVATE_KEY."

REMOTE=""
for cand in $REMOTE_CANDIDATES; do
  if ssh -o BatchMode=yes "$SRC_HOST" "test -f ${cand}/web_enterprise/__manifest__.py"; then
    REMOTE="$cand"
    break
  fi
done
[ -n "$REMOTE" ] || die "No se localizó web_enterprise en Justgroup (solo lectura)."

log "SOURCE_ENTERPRISE_PATH=${REMOTE} (remoto, solo rsync)"
mkdir -p "$DEST"
# Copia inmutable: no --delete sobre un destino que aún no existe; sí después.
rsync -a --info=stats2 \
  --exclude '.git/' \
  --exclude '*.pyc' \
  --exclude '__pycache__/' \
  --exclude 'filestore/' \
  --exclude '*.dump' \
  "${SRC_HOST}:${REMOTE}/" "${DEST}/"

[ -f "${DEST}/web_enterprise/__manifest__.py" ] || \
  die "Copia incompleta: falta web_enterprise."

# Inventario (nombres + hash de manifiestos; no secretos).
: > "${INV}.tsv"
while IFS= read -r man; do
  mod="$(basename "$(dirname "$man")")"
  sum="$(sha256sum "$man" | awk '{print $1}')"
  printf '%s\t%s\t%s\n' "$mod" "$sum" "$man" >> "${INV}.tsv"
done < <(find "$DEST" -mindepth 2 -maxdepth 2 -name __manifest__.py | sort)
wc -l < "${INV}.tsv" | awk '{print "ENTERPRISE_MODULES_COPIED="$1}'
sha256sum "${INV}.tsv" | awk '{print "INVENTORY_SHA256="$1}'

# Apuntar staging al árbol copiado (solo .env de staging).
ENVF="$(env_file enterprise-staging)"
if [ -f "$ENVF" ]; then
  if grep -q '^ENTERPRISE_SRC=' "$ENVF"; then
    sed -i "s|^ENTERPRISE_SRC=.*|ENTERPRISE_SRC=${DEST}|" "$ENVF"
  else
    printf 'ENTERPRISE_SRC=%s\n' "$DEST" >> "$ENVF"
  fi
  if grep -q '^ENTERPRISE_SOURCE_PENDING=' "$ENVF"; then
    sed -i 's|^ENTERPRISE_SOURCE_PENDING=.*|ENTERPRISE_SOURCE_PENDING=FALSE|' "$ENVF"
  fi
fi
log "ENTERPRISE_RUNTIME_COPIED = YES"
log "Destino ${DEST}. Prod /opt/doralex/enterprise NO modificado."
log "JUSTECH_SUBSCRIPTION_COPIED = NO"
log "JUSTECH_DATA_COPIED = NO"
