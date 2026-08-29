#!/usr/bin/env bash
# Ruta PRIMARIA: paquete oficial Odoo 19 Enterprise (cuenta Doralex en odoo.com).
#   1) .deb Ubuntu/Debian  → validar (la imagen derivada lo instala)
#   2) ZIP/tarball Sources → extraer web_enterprise a enterprise-staging
# GitHub odoo/enterprise es OPCIONAL y secundario. No es requisito.
# NO escribe en /opt/doralex/enterprise (Prod Community monta ese path).
# NO copia addons Enterprise de Justgroup.
# Nunca imprime credenciales ni el nombre del archivo depositado.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "${SCRIPT_DIR}/lib.sh"

DEST="${DORALEX_BASE}/enterprise-staging/enterprise-addons"
SHARED="${DORALEX_BASE}/enterprise"
BRANCH="${ODOO_ENTERPRISE_BRANCH:-19.0}"
SECRET_DIR="${DORALEX_BASE}/secrets/odoo_enterprise"
TOKEN_FILE="${SECRET_DIR}/github_token"
ARCHIVE_DIR="${SECRET_DIR}/archive"
FINDER=""
for candidate in \
  "${SCRIPT_DIR}/../../../tools/enterprise_source.py" \
  "${DORALEX_BASE}/tools/enterprise_source.py" \
  "${SCRIPT_DIR}/enterprise_source.py" \
  "/opt/doralex/repository/tools/enterprise_source.py" \
  "/workspace/tools/enterprise_source.py"; do
  if [ -f "$candidate" ]; then
    FINDER="$candidate"
    break
  fi
done
[ -n "$FINDER" ] || FINDER="${SCRIPT_DIR}/../../../tools/enterprise_source.py"

print_official_drop_instructions() {
  err "ENTERPRISE_PACKAGE_SOURCE = OFFICIAL"
  err "ENTERPRISE_PACKAGE_INSTALLED = NO"
  err "GITHUB_BLOCKER = REMOVE"
  err "Descargue el instalador oficial (sesión de la suscripción Doralex):"
  err "  https://www.odoo.com/page/download"
  err "  Odoo 19  →  Ubuntu • Debian  →  Enterprise  →  Download"
  err "Archivo esperado: odoo_19.0+e.*_all.deb"
  err "NO Community. NO nightly. NO Windows. NO RPM."
  err "Colóquelo en: ${ARCHIVE_DIR}/"
  err "Justgroup no se usa como fuente. Prod no se toca."
}

if [ -d "${SHARED}" ] && [ ! -f "${SHARED}/ENTERPRISE_SOURCE_PENDING" ]; then
  log "AVISO: ${SHARED} ya tiene contenido; este script no lo modifica."
fi

mkdir -p "${DEST}" "${SECRET_DIR}" "${ARCHIVE_DIR}"
chmod 700 "${SECRET_DIR}" "${ARCHIVE_DIR}" 2>/dev/null || true

install_from_tree() {
  local src="$1"
  [ -f "${src}/web_enterprise/__manifest__.py" ] || \
    die "El árbol no contiene web_enterprise: ${src}"
  rsync -a --delete --exclude '.git' --exclude 'ENTERPRISE_SOURCE_PENDING' \
    "${src}/" "${DEST}/"
  rm -f "${DEST}/ENTERPRISE_SOURCE_PENDING"
  log "Enterprise addons en ${DEST} (web_enterprise presente)."
  log "Prod ${SHARED} NO fue modificado."
}

try_deb() {
  local deb
  deb="$(python3 -c "from pathlib import Path; import sys; sys.path.insert(0, '${FINDER%/*}'); from enterprise_source import find_official_enterprise_deb; print(find_official_enterprise_deb(Path('${ARCHIVE_DIR}')))" 2>/dev/null || true)"
  [ -n "$deb" ] || return 1
  command -v dpkg-deb >/dev/null 2>&1 || die "dpkg-deb no está disponible para validar el .deb."
  local tmp
  tmp="$(mktemp -d)"
  log "Validando .deb oficial Enterprise 19 (nombre omitido)."
  if ! dpkg-deb -x "$deb" "$tmp"; then
    rm -rf "$tmp"
    die "El archivo .deb no se pudo extraer. ¿Es el instalador oficial Ubuntu/Debian?"
  fi
  python3 -c "from pathlib import Path; import sys; sys.path.insert(0, '${FINDER%/*}'); from enterprise_source import find_enterprise_addons_root; print(find_enterprise_addons_root(Path('${tmp}')))" >/dev/null
  rm -rf "$tmp"
  log "ENTERPRISE_PACKAGE_SOURCE = OFFICIAL"
  log "WEB_ENTERPRISE_DISCOVERED = YES (dentro del .deb)"
  return 0
}

try_archive() {
  local archive
  archive="$(find "$ARCHIVE_DIR" -maxdepth 1 -type f \
    \( -name '*.zip' -o -name '*.tar.gz' -o -name '*.tgz' -o -name '*.tar' \) \
    | head -1 || true)"
  [ -n "$archive" ] || return 1
  local tmp
  tmp="$(mktemp -d)"
  log "Intentando archive oficial Sources (nombre omitido)."
  case "$archive" in
    *.zip) unzip -q "$archive" -d "$tmp" ;;
    *.tar.gz|*.tgz) tar xzf "$archive" -C "$tmp" ;;
    *.tar) tar xf "$archive" -C "$tmp" ;;
    *) die "Formato de archive no soportado" ;;
  esac
  local root
  root="$(python3 -c "from pathlib import Path; import sys; sys.path.insert(0, '${FINDER%/*}'); from enterprise_source import find_enterprise_addons_root; print(find_enterprise_addons_root(Path('${tmp}')))")"
  install_from_tree "$root"
  rm -rf "$tmp"
  return 0
}

try_git() {
  local token="${ODOO_ENTERPRISE_GITHUB_TOKEN:-}"
  if [ -z "$token" ] && [ -f "$TOKEN_FILE" ]; then
    token="$(tr -d '[:space:]' < "$TOKEN_FILE")"
  fi
  [ -n "$token" ] || return 1
  local tmp
  tmp="$(mktemp -d)"
  log "Vía secundaria git 19.0 (credencial presente, no se imprime)."
  if ! GIT_TERMINAL_PROMPT=0 git clone --depth 1 --branch "$BRANCH" \
      "https://x-access-token:${token}@github.com/odoo/enterprise.git" \
      "${tmp}/enterprise" >/dev/null 2>"${tmp}/git.err"; then
    rm -rf "$tmp"
    return 1
  fi
  install_from_tree "${tmp}/enterprise"
  rm -rf "$tmp"
  return 0
}

if try_deb; then
  log "ENTERPRISE_SOURCE = PASS (paquete .deb oficial)"
  exit 0
fi
if try_archive; then
  log "ENTERPRISE_SOURCE = PASS (archive oficial)"
  exit 0
fi
if try_git; then
  log "ENTERPRISE_SOURCE = PASS (git 19.0, vía secundaria)"
  exit 0
fi

err "ENTERPRISE_SOURCE = PENDING_OFFICIAL_PACKAGE"
print_official_drop_instructions
exit 2
