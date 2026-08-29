#!/usr/bin/env bash
# Construye doralex-odoo-enterprise:19.0.20260324 a partir del export + core Justgroup.
# No incluye DB, filestore, secretos ni código de suscripción.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "${SCRIPT_DIR}/lib.sh"

ROOT="${DORALEX_BASE}/runtime-source/19.0-e-20260324"
IMAGE="${ENTERPRISE_RUNTIME_IMAGE:-doralex-odoo-enterprise:19.0.20260324}"
CTX="$(mktemp -d)"
cleanup() { rm -rf "$CTX"; }
trap cleanup EXIT

[ -d "${ROOT}/enterprise/web_enterprise" ] || \
  die "Falta enterprise/web_enterprise en ${ROOT}. Extraiga el export primero."

# Core: 1) .deb en metadata  2) rsync Justgroup  3) STOP (no nightly distinta, no odoo:19 latest).
CORE_DEB="$(find "${ROOT}/core-metadata" -name 'odoo_19.0.20260324*.deb' 2>/dev/null | head -1 || true)"
if [ -z "$CORE_DEB" ] && ssh -o BatchMode=yes -o ConnectTimeout=10 justgroup-vps 'true' 2>/dev/null; then
  log "Buscando .deb o árbol core 19.0.20260324 en Justgroup (solo lectura)..."
  remote_deb="$(ssh justgroup-vps 'ls /var/cache/apt/archives/odoo_19.0.20260324*.deb 2>/dev/null | head -1' || true)"
  if [ -n "$remote_deb" ]; then
    mkdir -p "${ROOT}/core-metadata"
    rsync -a "justgroup-vps:${remote_deb}" "${ROOT}/core-metadata/"
    CORE_DEB="$(find "${ROOT}/core-metadata" -name 'odoo_19.0.20260324*.deb' | head -1)"
  fi
fi

if [ -z "$CORE_DEB" ]; then
  die "CORE 19.0.20260324 no está en el export ni en Justgroup. No usaré odoo:19 latest ni otra nightly."
fi

log "Core .deb oficial/infra: $(basename "$CORE_DEB")"
cp "$CORE_DEB" "${CTX}/odoo-core.deb"
# Enterprise + custom (sin reportes Doralex).
mkdir -p "${CTX}/enterprise" "${CTX}/justgroup-custom"
rsync -a --exclude '.git' "${ROOT}/enterprise/" "${CTX}/enterprise/"
rsync -a --exclude '.git' --exclude 'justech_alexander_reports/' \
  "${ROOT}/custom-addons/" "${CTX}/justgroup-custom/"

cat > "${CTX}/Dockerfile" <<'DOCKER'
FROM ubuntu:24.04
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
      python3 python3-pip python3-wheel python3-setuptools \
      python3-venv ca-certificates curl \
      wkhtmltopdf fonts-dejavu-core fonts-liberation \
      libpq5 libxml2 libxslt1.1 libsasl2-2 libldap-2.4-2 || \
    apt-get install -y --no-install-recommends \
      python3 python3-pip ca-certificates curl wkhtmltopdf fonts-dejavu-core \
      libpq5 libxml2 libxslt1.1 libsasl2-2 libldap2
COPY odoo-core.deb /tmp/odoo-core.deb
RUN apt-get update && apt-get install -y --no-install-recommends /tmp/odoo-core.deb \
    || dpkg -i --force-downgrade /tmp/odoo-core.deb \
    && apt-get -y -f install --no-install-recommends \
    && rm -f /tmp/odoo-core.deb && rm -rf /var/lib/apt/lists/*
COPY enterprise /usr/lib/odoo/enterprise
COPY justgroup-custom /usr/lib/odoo/custom-addons
RUN python3 -c "from pathlib import Path; assert (Path('/usr/lib/odoo/enterprise')/'web_enterprise'/'__manifest__.py').is_file()"
USER odoo
DOCKER

require_cmd docker
docker build -t "$IMAGE" "$CTX"
docker tag "$IMAGE" doralex-odoo-enterprise:19.0.20260324
log "DORALEX_RUNTIME_IMAGE = ${IMAGE}"
docker run --rm --user 0 "$IMAGE" dpkg-query -W odoo
