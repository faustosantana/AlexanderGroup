#!/usr/bin/env bash
# Copia (no mueve) el export de runtime Justgroup → Doralex.
# Justgroup es solo lectura. No borra el source.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "${SCRIPT_DIR}/lib.sh"

EXPECTED_SHA256="${EXPECTED_SHA256:-d406ccfd73225db88b83dfd07def618b2c48e1b1aeaebcc5877f76fa26b4cb86}"
SRC_FILE="${JUSTGROUP_EXPORT:-/root/doralex_runtime_export_19.0-e-20260324.tar.zst}"
DEST_DIR="${DORALEX_BASE}/imports"
DEST_FILE="${DEST_DIR}/doralex_runtime_export_19.0-e-20260324.tar.zst"

require_cmd ssh
require_cmd sha256sum
ssh -o BatchMode=yes -o ConnectTimeout=15 justgroup-vps "test -f '${SRC_FILE}'" \
  || die "No hay SSH justgroup-vps o falta ${SRC_FILE}."

mkdir -p "$DEST_DIR"
chmod 700 "$DEST_DIR"
log "Copiando export (rsync, source intacto)..."
rsync -a --info=progress2 "justgroup-vps:${SRC_FILE}" "$DEST_FILE"
# Si este script corre en el Cloud Agent, el dest local no es el servidor Doralex.
# Segundo salto: si DORALEX_PUSH=yes, scp al servidor.
if [ "${DORALEX_PUSH:-yes}" = "yes" ] && [ "$(hostname)" != "Doralexgroup" ]; then
  ssh doralex-server "mkdir -p '${DEST_DIR}' && chmod 700 '${DEST_DIR}'"
  rsync -a --info=progress2 "$DEST_FILE" "doralex-server:${DEST_FILE}"
  actual="$(ssh doralex-server "sha256sum '${DEST_FILE}'" | awk '{print $1}')"
else
  actual="$(sha256sum "$DEST_FILE" | awk '{print $1}')"
fi

printf 'EXPORT_SHA256_ACTUAL = %s\n' "$actual"
if [ "$actual" != "$EXPECTED_SHA256" ]; then
  err "EXPORT_SHA256_MATCH = NO"
  err "EXPORT_TRANSFER = FAIL"
  die "STOP: hash distinto. No extraer."
fi
log "EXPORT_TRANSFER = PASS"
log "EXPORT_SHA256_MATCH = YES"
