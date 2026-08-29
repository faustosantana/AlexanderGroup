#!/usr/bin/env bash
# Construye doralex-odoo-enterprise:19.0.20260324 desde el core extraído + Enterprise.
# No incluye DB, filestore, secretos ni código de suscripción.
# No etiqueta como odoo:19. No usa odoo:19 latest como core final (solo OS/entrypoint).
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "${SCRIPT_DIR}/lib.sh"

CORE_ROOT="${DORALEX_BASE}/core-source/19.0.20260324"
RUNTIME_ROOT="${DORALEX_BASE}/runtime-source/19.0-e-20260324"
IMAGE="${ENTERPRISE_RUNTIME_IMAGE:-doralex-odoo-enterprise:19.0.20260324}"
CTX="${DORALEX_BASE}/image-build/19.0.20260324"

[ -f "${CORE_ROOT}/core/usr_lib_python_odoo/release.py" ] || \
  die "Falta el árbol core en ${CORE_ROOT}. Extraiga doralex_core_export primero."
[ -d "${RUNTIME_ROOT}/enterprise/web_enterprise" ] || \
  die "Falta enterprise/web_enterprise en ${RUNTIME_ROOT}."
grep -q "20260324" "${CORE_ROOT}/core/usr_lib_python_odoo/release.py" || \
  die "CORE 19.0.20260324 no está en el extracto. No usaré odoo:19 latest ni otra nightly."

require_cmd docker
mkdir -p "${CTX}/justgroup-custom"
rm -rf "${CTX}/odoo-core" "${CTX}/enterprise" "${CTX}/odoo"
# Hardlinks: no duplicar 1.4G+ en disco.
cp -al "${CORE_ROOT}/core/usr_lib_python_odoo" "${CTX}/odoo-core"
cp -al "${CORE_ROOT}/bin/odoo" "${CTX}/odoo"
cp -al "${RUNTIME_ROOT}/enterprise" "${CTX}/enterprise"
rsync -a --delete --exclude '.git' --exclude 'justech_alexander_reports/' \
  --exclude 'justech_alexander_admin/' --exclude 'justech_alexander_base/' \
  --exclude 'justech_alexander_microsoft_mail/' --exclude 'justech_alexander_website/' \
  "${RUNTIME_ROOT}/custom-addons/" "${CTX}/justgroup-custom/"

cat > "${CTX}/Dockerfile" <<'DOCKER'
# Bootstrap OS/user/entrypoint/wkhtmltopdf from odoo:19, then REPLACE the core.
# Running core must be 19.0.20260324, not 19.0.20260817.
FROM odoo:19
USER root
RUN rm -rf /usr/lib/python3/dist-packages/odoo
COPY odoo-core /usr/lib/python3/dist-packages/odoo
COPY odoo /usr/bin/odoo
COPY enterprise /usr/lib/odoo/enterprise
COPY justgroup-custom /usr/lib/odoo/custom-addons
RUN chmod 755 /usr/bin/odoo \
 && python3 -m pip install --break-system-packages --no-cache-dir \
      pyqrcode xmltodict simplejson pycountry "signxml==3.2.2" \
 && python3 -c "import odoo.release; assert odoo.release.version=='19.0-20260324', odoo.release.version" \
 && python3 -c "import pyqrcode, xmltodict, simplejson, pycountry, signxml" \
 && test -f /usr/lib/odoo/enterprise/web_enterprise/__manifest__.py \
 && ! ls -d /usr/lib/odoo/custom-addons/justech_alexander_* >/dev/null 2>&1
USER odoo
DOCKER

log "Building ${IMAGE} (core tree 19.0.20260324 + Enterprise; no Justgroup DB/filestore/conf)"
docker build -t "$IMAGE" "$CTX"
# Never retag odoo:19.
log "DORALEX_RUNTIME_IMAGE = ${IMAGE}"
docker run --rm --user 0 "$IMAGE" python3 -c "import odoo.release; print(odoo.release.version)"
