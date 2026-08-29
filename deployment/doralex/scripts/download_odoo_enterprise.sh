#!/usr/bin/env bash
# Descarga el .deb oficial Odoo 19 Enterprise (Ubuntu/Debian) desde odoo.com.
# Flujo real: POST /download/check_subscription → GET /thanks/download?platform_version=deb_19e
# Código de contrato: env ODOO_ENTERPRISE_SUBSCRIPTION_CODE o archivo
#   /opt/doralex/secrets/odoo_enterprise/subscription_code  (chmod 600)
# Nunca imprime el código. Nunca toca Prod. Nunca usa nightly/Community.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "${SCRIPT_DIR}/lib.sh"

SECRET_DIR="${DORALEX_BASE}/secrets/odoo_enterprise"
ARCHIVE_DIR="${SECRET_DIR}/archive"
CODE_FILE="${SECRET_DIR}/subscription_code"
FINDER_DIR=""
for candidate in \
  "${SCRIPT_DIR}/../../../tools" \
  "${DORALEX_BASE}/tools" \
  "/opt/doralex/repository/tools" \
  "/workspace/tools"; do
  if [ -f "${candidate}/enterprise_download.py" ]; then
    FINDER_DIR="$candidate"
    break
  fi
done
[ -n "$FINDER_DIR" ] || die "Falta tools/enterprise_download.py"

mkdir -p "$ARCHIVE_DIR"
chmod 700 "$SECRET_DIR" "$ARCHIVE_DIR" 2>/dev/null || true

read_code() {
  if [ -n "${ODOO_ENTERPRISE_SUBSCRIPTION_CODE:-}" ]; then
    printf '%s' "$ODOO_ENTERPRISE_SUBSCRIPTION_CODE"
    return 0
  fi
  if [ -f "$CODE_FILE" ]; then
    tr -d '[:space:]' < "$CODE_FILE"
    return 0
  fi
  return 1
}

validate_deb() {
  local deb="$1"
  [ -s "$deb" ] || die "El archivo descargado está vacío."
  local kind
  kind="$(file -b "$deb" || true)"
  case "$kind" in
    *Debian*|*ar\ archive*|*deb*) ;;
    *) die "file(1) no reconoce un .deb: ${kind}" ;;
  esac
  command -v dpkg-deb >/dev/null 2>&1 || die "dpkg-deb no está disponible."
  dpkg-deb --info "$deb" >/dev/null
  python3 -c "from pathlib import Path; import sys; sys.path.insert(0, '${FINDER_DIR}'); from enterprise_source import is_official_enterprise_package_name, find_enterprise_addons_root; \
p=Path('${deb}'); assert is_official_enterprise_package_name(p.name), p.name"
  local tmp
  tmp="$(mktemp -d)"
  dpkg-deb -x "$deb" "$tmp"
  python3 -c "from pathlib import Path; import sys; sys.path.insert(0, '${FINDER_DIR}'); from enterprise_source import find_enterprise_addons_root; find_enterprise_addons_root(Path('${tmp}'))"
  rm -rf "$tmp"
  sha256sum "$deb" | awk '{print $1}'
}

export PYTHONPATH="${FINDER_DIR}/..:${FINDER_DIR}:${PYTHONPATH:-}"
export PY_FINDER_DIR="$FINDER_DIR"
export CODE_FILE ARCHIVE_DIR

has_code=0
if read_code >/dev/null; then
  has_code=1
fi
if [ "$has_code" -eq 0 ]; then
  log "Sin código de contrato en env/archivo; sondando endpoints oficiales..."
  python3 - <<PY
import sys
sys.path.insert(0, "${FINDER_DIR}/..")
sys.path.insert(0, "${FINDER_DIR}")
try:
    from tools.enterprise_download import probe_without_code
except ImportError:
    from enterprise_download import probe_without_code
p = probe_without_code()
print("AUTOMATIC_DOWNLOAD = BLOCKED")
print("BLOCKED_BY = SUBSCRIPTION_CODE")
print(f"HTTP_STATUS = {p.http_status}")
print(f"FINAL_URL = {p.final_url}")
print(f"AUTH_REQUIRED = {p.auth_required}")
print(f"SUBSCRIPTION_REQUIRED = {p.subscription_required}")
print(f"DOWNLOAD_ENDPOINT = {p.download_endpoint}")
print(f"REASON = {p.reason}")
print(f"THANKS_BODY = {p.body_kind}")
PY
  err "WHAT_IS_MISSING = código de suscripción Enterprise Doralex (contrato M...)"
  err "Colóquelo (chmod 600, una línea) en: ${CODE_FILE}"
  err "No hace falta subir el .deb. Este script lo baja de odoo.com."
  exit 2
fi

log "Llamando check_subscription + thanks/download (platform=deb_19e). Código omitido."
set +e
dest="$(CODE_FILE="$CODE_FILE" ARCHIVE_DIR="$ARCHIVE_DIR" python3 - <<'PY'
import os, sys
from pathlib import Path
sys.path.insert(0, os.environ.get("PY_FINDER_DIR", "."))
sys.path.insert(0, str(Path(os.environ.get("PY_FINDER_DIR", ".")).parent))
try:
    from tools.enterprise_download import download_official_deb, EnterpriseDownloadError
except ImportError:
    from enterprise_download import download_official_deb, EnterpriseDownloadError
code = (os.environ.get("ODOO_ENTERPRISE_SUBSCRIPTION_CODE") or "").strip()
if not code:
    code = Path(os.environ["CODE_FILE"]).read_text(encoding="utf-8").strip()
try:
    path = download_official_deb(code, Path(os.environ["ARCHIVE_DIR"]))
except EnterpriseDownloadError as exc:
    print(exc, file=sys.stderr)
    sys.exit(3)
print(path)
PY
)"
rc=$?
set -e
if [ "$rc" -ne 0 ]; then
  err "AUTOMATIC_DOWNLOAD = BLOCKED"
  err "BLOCKED_BY = CONTRACT_REJECTED_OR_HTML"
  err "DOWNLOAD_ENDPOINT = https://www.odoo.com/download/check_subscription"
  exit 3
fi

digest="$(validate_deb "$dest")"
log "ENTERPRISE_DEB_FOUND = YES"
log "ENTERPRISE_DEB_VALID = YES"
log "ENTERPRISE_DEB_OFFICIAL = YES"
log "ENTERPRISE_PACKAGE_SOURCE = OFFICIAL"
log "sha256=${digest}"
