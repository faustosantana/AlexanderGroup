#!/usr/bin/env bash
# Doralex — verifica un backup existente: archivos presentes, tamaño>0 y checksum.
# Uso:  bash verify_backup.sh /opt/doralex/backups/production/production_YYYYmmdd_HHMMSS
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "${SCRIPT_DIR}/lib.sh"

require_cmd sha256sum
DIR="${1:-}"
[ -n "$DIR" ] || die "Uso: verify_backup.sh <directorio_de_backup>"
[ -d "$DIR" ] || die "No existe el directorio: ${DIR}"

REQUIRED=(db.dump filestore.tar.gz docker-compose.yml SHA256SUMS MANIFEST)
status=0

for f in "${REQUIRED[@]}"; do
  if [ ! -f "${DIR}/${f}" ]; then
    err "Falta artefacto requerido: ${f}"; status=1; continue
  fi
  if [ ! -s "${DIR}/${f}" ]; then
    err "Artefacto vacío (tamaño 0): ${f}"; status=1
  fi
done

# db.dump debe superar un tamaño mínimo razonable (un dump válido no es trivial).
if [ -f "${DIR}/db.dump" ]; then
  size=$(stat -c '%s' "${DIR}/db.dump")
  if [ "$size" -lt 1024 ]; then
    err "db.dump sospechosamente pequeño (${size} bytes)"; status=1
  fi
fi

# Verificación de checksums.
if [ -f "${DIR}/SHA256SUMS" ]; then
  if ( cd "$DIR" && sha256sum -c SHA256SUMS >/dev/null 2>&1 ); then
    log "Checksums OK"
  else
    err "Fallo de verificación de checksums (SHA256SUMS)"; status=1
  fi
fi

if [ "$status" -eq 0 ]; then
  log "BACKUP VALIDO: ${DIR}"
else
  err "BACKUP INVALIDO: ${DIR}"
fi
exit "$status"
