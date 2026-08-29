#!/usr/bin/env bash
# Construye la imagen staging derivada a partir del .deb oficial Enterprise 19.
# No toca Prod. No etiqueta como odoo:19.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "${SCRIPT_DIR}/lib.sh"

require_cmd docker
require_cmd python3

SECRET_DIR="${DORALEX_BASE}/secrets/odoo_enterprise"
ARCHIVE_DIR="${SECRET_DIR}/archive"
IMAGE_TAG="${ENTERPRISE_STAGING_IMAGE:-doralex-odoo-enterprise:19}"
DOCKERFILE=""
for candidate in \
  "${SCRIPT_DIR}/../enterprise-staging/Dockerfile.enterprise" \
  "${DORALEX_BASE}/enterprise-staging/Dockerfile.enterprise" \
  "/workspace/deployment/doralex/enterprise-staging/Dockerfile.enterprise"; do
  if [ -f "$candidate" ]; then
    DOCKERFILE="$candidate"
    break
  fi
done
[ -n "$DOCKERFILE" ] || die "Falta Dockerfile.enterprise"

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
[ -n "$FINDER" ] || die "Falta tools/enterprise_source.py"

deb="$(python3 -c "from pathlib import Path; import sys; sys.path.insert(0, '${FINDER%/*}'); from enterprise_source import find_official_enterprise_deb; print(find_official_enterprise_deb(Path('${ARCHIVE_DIR}')))")"

log "ENTERPRISE_PACKAGE_SOURCE = OFFICIAL"
log "Construyendo ${IMAGE_TAG} desde el .deb oficial (nombre omitido)."

ctx="$(mktemp -d)"
cp "$DOCKERFILE" "${ctx}/Dockerfile"
cp "$deb" "${ctx}/odoo-enterprise.deb"
if ! docker build -t "$IMAGE_TAG" "$ctx"; then
  rm -rf "$ctx"
  die "Fallo al construir la imagen staging derivada."
fi
rm -rf "$ctx"

docker run --rm --user 0 "$IMAGE_TAG" python3 -c \
  "from pathlib import Path; hits=list(Path('/usr/lib/python3').rglob('web_enterprise/__manifest__.py')); \
assert hits, 'web_enterprise no está en la imagen'; print(hits[0])"

log "WEB_ENTERPRISE_DISCOVERED = YES (imagen ${IMAGE_TAG})"
printf '%s\n' "$IMAGE_TAG"
