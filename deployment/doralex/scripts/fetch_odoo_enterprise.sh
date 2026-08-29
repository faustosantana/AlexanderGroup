#!/usr/bin/env bash
# Obtiene addons Odoo Enterprise 19 por vía oficial:
#   A) git clone github.com/odoo/enterprise @ 19.0
#   B) archive/ZIP oficial depositado en secrets (cuenta/suscripción Doralex)
# NO escribe en /opt/doralex/enterprise (Prod Community monta ese path).
# NO copia addons Enterprise de Justgroup.
# Nunca imprime credenciales.
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
  "/opt/doralex/repository/tools/enterprise_source.py" \
  "/workspace/tools/enterprise_source.py"; do
  if [ -f "$candidate" ]; then
    FINDER="$candidate"
    break
  fi
done
[ -n "$FINDER" ] || FINDER="${SCRIPT_DIR}/../../../tools/enterprise_source.py"

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

try_git() {
  local token="${ODOO_ENTERPRISE_GITHUB_TOKEN:-}"
  if [ -z "$token" ] && [ -f "$TOKEN_FILE" ]; then
    token="$(tr -d '[:space:]' < "$TOKEN_FILE")"
  fi
  [ -n "$token" ] || return 1
  local tmp
  tmp="$(mktemp -d)"
  log "Intentando vía A: git 19.0 (credencial presente, no se imprime)."
  if ! GIT_TERMINAL_PROMPT=0 git clone --depth 1 --branch "$BRANCH" \
      "https://x-access-token:${token}@github.com/odoo/enterprise.git" \
      "${tmp}/enterprise" >/dev/null 2>"${tmp}/git.err"; then
    err "GitHub odoo/enterprise rechazó la credencial (vía A)."
    rm -rf "$tmp"
    return 1
  fi
  install_from_tree "${tmp}/enterprise"
  rm -rf "$tmp"
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
  log "Intentando vía B: archive oficial (nombre omitido en logs)."
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

if try_git; then
  log "ENTERPRISE_SOURCE = PASS (git 19.0)"
  exit 0
fi
if try_archive; then
  log "ENTERPRISE_SOURCE = PASS (archive oficial)"
  exit 0
fi

err "ENTERPRISE_SOURCE = PENDING_OFFICIAL_PACKAGE"
err "Vía A: coloque la credencial de lectura de github.com/odoo/enterprise"
err "  en ${TOKEN_FILE} (chmod 600). Cuenta GitHub vinculada en odoo.com."
err "Vía B: descargue el ZIP/tarball Enterprise 19 desde odoo.com"
err "  (login de la suscripción Doralex o enlace del correo de compra)"
err "  y déjelo en ${ARCHIVE_DIR}/"
err "Justgroup no se usa como fuente. Prod no se toca."
exit 2
