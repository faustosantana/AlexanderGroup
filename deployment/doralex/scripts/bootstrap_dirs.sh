#!/usr/bin/env bash
# Doralex — crea la estructura de directorios AISLADA en el servidor.
# NO instala software ni levanta contenedores. Solo crea carpetas con permisos.
#
# Uso (en el servidor):  sudo bash bootstrap_dirs.sh
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "${SCRIPT_DIR}/lib.sh"

log "Base: ${DORALEX_BASE}"
umask 077

dirs=(
  "${DORALEX_BASE}"
  "${DORALEX_BASE}/production"
  "${DORALEX_BASE}/production/config"
  "${DORALEX_BASE}/production/addons"
  "${DORALEX_BASE}/dev"
  "${DORALEX_BASE}/dev/config"
  "${DORALEX_BASE}/dev/addons"
  "${DORALEX_BASE}/backups"
  "${DORALEX_BASE}/backups/production"
  "${DORALEX_BASE}/backups/dev"
  "${DORALEX_BASE}/scripts"
  "${DORALEX_BASE}/repository"
)

for d in "${dirs[@]}"; do
  mkdir -p "$d"
  log "OK  $d"
done

log "Estructura creada. Recuerde: los .env reales y odoo.conf renderizados NO se versionan."
