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
  "${DORALEX_BASE}/repository"
  "${DORALEX_BASE}/odoo"
  "${DORALEX_BASE}/enterprise"
  "${DORALEX_BASE}/custom-addons"
  "${DORALEX_BASE}/production"
  "${DORALEX_BASE}/production/config"
  "${DORALEX_BASE}/production/custom-addons"
  "${DORALEX_BASE}/production/logs"
  "${DORALEX_BASE}/dev"
  "${DORALEX_BASE}/dev/config"
  "${DORALEX_BASE}/dev/custom-addons"
  "${DORALEX_BASE}/dev/logs"
  "${DORALEX_BASE}/backups"
  "${DORALEX_BASE}/backups/production"
  "${DORALEX_BASE}/backups/dev"
  "${DORALEX_BASE}/scripts"
  "${DORALEX_BASE}/logs"
)

for d in "${dirs[@]}"; do
  mkdir -p "$d"
  log "OK  $d"
done

# El directorio Enterprise existe desde el inicio (addons_path final). Debe ser
# TRAVERSABLE (755) por el usuario del contenedor Odoo; de lo contrario Odoo no
# resuelve el addons_path (queda vacío). Permanece VACIO hasta la licencia.
chmod 755 "${DORALEX_BASE}/enterprise"

# Los directorios de addons deben ser legibles por el usuario del contenedor.
chmod 755 "${DORALEX_BASE}/custom-addons" \
          "${DORALEX_BASE}/production/custom-addons" \
          "${DORALEX_BASE}/dev/custom-addons"

# Los logs deben ser escribibles por el usuario 'odoo' del contenedor
# (imagen oficial: uid 100, gid 101). Configurable con ODOO_UID/ODOO_GID.
_ouid="${ODOO_UID:-100}"; _ogid="${ODOO_GID:-101}"
chown "${_ouid}:${_ogid}" "${DORALEX_BASE}/production/logs" \
                          "${DORALEX_BASE}/dev/logs" 2>/dev/null || true
chmod 775 "${DORALEX_BASE}/production/logs" "${DORALEX_BASE}/dev/logs"

if [ ! -f "${DORALEX_BASE}/enterprise/ENTERPRISE_SOURCE_PENDING" ]; then
  {
    echo "ENTERPRISE_SOURCE_PENDING=TRUE"
    echo "# Coloque aquí los addons Enterprise SOLO desde la fuente legítima autorizada."
    echo "# No descargar Enterprise desde repositorios de terceros."
  } > "${DORALEX_BASE}/enterprise/ENTERPRISE_SOURCE_PENDING"
fi

log "Estructura creada (enterprise-ready)."
log "Enterprise: ${DORALEX_BASE}/enterprise (vacío, ENTERPRISE_SOURCE_PENDING=TRUE)."
log "Recuerde: .env reales y odoo.conf renderizados NO se versionan."
