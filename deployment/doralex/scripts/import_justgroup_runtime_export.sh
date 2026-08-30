#!/usr/bin/env bash
# Extrae y audita el export Justgroup en un directorio aislado.
# No toca Prod. No instala módulos. No extrae sobre /usr/lib/odoo.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "${SCRIPT_DIR}/lib.sh"

EXPECTED_SHA256="${EXPECTED_SHA256:-d406ccfd73225db88b83dfd07def618b2c48e1b1aeaebcc5877f76fa26b4cb86}"
ARCHIVE="${DORALEX_BASE}/imports/doralex_runtime_export_19.0-e-20260324.tar.zst"
ROOT="${DORALEX_BASE}/runtime-source/19.0-e-20260324"

[ -f "$ARCHIVE" ] || die "Falta ${ARCHIVE}. Ejecute transfer_justgroup_runtime_export.sh"
actual="$(sha256sum "$ARCHIVE" | awk '{print $1}')"
printf 'EXPORT_SHA256_ACTUAL = %s\n' "$actual"
[ "$actual" = "$EXPECTED_SHA256" ] || die "EXPORT_SHA256_MATCH = NO. STOP."
log "EXPORT_SHA256_MATCH = YES"

require_cmd zstd
mkdir -p "$ROOT"
# Extraer en aislado (no sobre core/custom vivos).
zstd -dc "$ARCHIVE" | tar -x -C "$ROOT" --no-same-owner
# Si el tar trae un directorio raíz extra, aplanar un nivel si hace falta.
if [ ! -d "${ROOT}/enterprise" ]; then
  inner="$(find "$ROOT" -mindepth 1 -maxdepth 2 -type d -name enterprise | head -1 || true)"
  if [ -n "$inner" ]; then
    base="$(dirname "$inner")"
    log "Aplanando desde ${base}"
    shopt -s dotglob
    mv "${base}"/* "$ROOT"/ 2>/dev/null || true
    shopt -u dotglob
  fi
fi

for must in enterprise custom-addons; do
  [ -d "${ROOT}/${must}" ] || die "Export incompleto: falta ${must}/"
done

# Auditoría de secretos / dumps / filestore / suscripción.
python3 - <<PY
from pathlib import Path
root = Path("${ROOT}")
forbidden = []
skip_names = {".git"}
needles = (
    "subscription-code", "enterprise-code", "database.enterprise-code",
    "BEGIN OPENSSH PRIVATE KEY", "BEGIN RSA PRIVATE KEY", "BEGIN PRIVATE KEY",
    "aws-secret", "smtp-pass", "smtp-password",
)
suffix_bad = {".env", ".dump", ".sql", ".pem", ".key", ".p12", ".pfx"}
for p in root.rglob("*"):
    if not p.is_file():
        continue
    rel = str(p.relative_to(root))
    name = p.name.lower()
    if name in {".env"} or p.suffix.lower() in suffix_bad or "filestore" in rel.lower():
        # metadatos de inventario no son dumps
        if p.suffix.lower() in {".dump", ".sql"} or "filestore" in rel.lower() or name == ".env":
            forbidden.append(rel)
            continue
    if p.stat().st_size > 2_000_000:
        continue
    try:
        text = p.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        continue
    low = text.lower().replace("_", "-")
    for n in needles:
        if n.lower() in low:
            forbidden.append(rel + ":" + n)
            break
print("EXPORT_SECRETS_FOUND", len(forbidden))
for h in forbidden[:20]:
    print("HIT", h)
db = any("dump" in str(p).lower() or p.suffix.lower()==".sql" for p in root.rglob("*") if p.is_file())
fs = any("filestore" in str(p).relative_to(root).lower() for p in root.rglob("*"))
sub = any("subscription" in str(p).name.lower() and p.suffix.lower() in {".txt",".env",""} for p in root.rglob("*") if p.is_file())
print(f"EXPORT_DATABASE_FOUND = {'YES' if db else 'NO'}")
print(f"EXPORT_FILESTORE_FOUND = {'YES' if fs else 'NO'}")
print(f"EXPORT_SUBSCRIPTION_FOUND = {'YES' if sub else 'NO'}")
if forbidden:
    raise SystemExit("STOP: secreto o artefacto prohibido en el export")
PY

# Conteos Enterprise
python3 - <<PY
from pathlib import Path
import ast
ent = Path("${ROOT}/enterprise")
dirs = [p for p in ent.iterdir() if p.is_dir() and not p.name.startswith(".")]
mans = list(ent.glob("*/__manifest__.py"))
installable = non = 0
for man in mans:
    try:
        data = ast.literal_eval(man.read_text(encoding="utf-8"))
    except Exception:
        continue
    if data.get("installable", True):
        installable += 1
    else:
        non += 1
print(f"ENTERPRISE_DIRECTORIES = {len(dirs)}")
print(f"ENTERPRISE_MANIFESTS = {len(mans)}")
print(f"ENTERPRISE_INSTALLABLE = {installable}")
print(f"ENTERPRISE_NON_INSTALLABLE = {non}")
for name in ("web_enterprise","account_accountant","documents","sign","helpdesk","sale_subscription","sale_renting","planning","web_studio"):
    print(f"KEYMOD {name} = {'YES' if (ent/name/'__manifest__.py').is_file() else 'NO'}")
cust = Path("${ROOT}/custom-addons")
cmans = list(cust.glob("*/__manifest__.py")) + list(cust.glob("*/*/__manifest__.py"))
print(f"CUSTOM_MANIFESTS = {len(cmans)}")
PY

if [ -f "${ROOT}/README_RUNTIME.txt" ]; then
  log "README_RUNTIME.txt presente"
  head -40 "${ROOT}/README_RUNTIME.txt" || true
fi
ls -la "$ROOT" | head
log "Extract+audit OK en ${ROOT}"
