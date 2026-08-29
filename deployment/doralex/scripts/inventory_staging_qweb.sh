#!/usr/bin/env bash
# Inventario de QWeb Doralex en enterprise-staging. No toca Prod.
# Uso: bash inventory_staging_qweb.sh
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "${SCRIPT_DIR}/lib.sh"

load_env enterprise-staging
OUT="${DORALEX_BASE}/backups/enterprise-staging"
mkdir -p "${OUT}/qweb_xml"
STAMP="$(date +%Y%m%d_%H%M%S)"
TSV="${OUT}/qweb_doralex_${STAMP}.tsv"
JSON="${OUT}/qweb_doralex_${STAMP}.json"

docker exec -i doralex-enterprise-staging-db \
  psql -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" -v ON_ERROR_STOP=1 \
  -c "\\copy (
    SELECT v.id,
           COALESCE(d.module, '') AS module,
           COALESCE(d.name, '') AS xml_name,
           v.key,
           v.name,
           COALESCE(v.model, '') AS model,
           v.type,
           COALESCE(v.inherit_id::text, '') AS inherit_id,
           v.priority,
           v.active,
           md5(COALESCE(v.arch_db::text, '')) AS arch_md5
    FROM ir_ui_view v
    LEFT JOIN ir_model_data d ON d.model = 'ir.ui.view' AND d.res_id = v.id
    WHERE v.key LIKE 'justech_alexander%'
    ORDER BY v.key
  ) TO STDOUT WITH CSV HEADER" > "$TSV"

python3 - <<PY
import csv, json
from pathlib import Path
src = Path("${TSV}")
rows = list(csv.DictReader(src.open(encoding="utf-8")))
Path("${JSON}").write_text(json.dumps({"count": len(rows), "views": rows}, indent=2) + "\n", encoding="utf-8")
print(f"QWEB_BEFORE = {len(rows)}")
PY

# Export arch_db of each view (report XML only; no transactional data).
docker exec -i doralex-enterprise-staging-db \
  psql -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" -v ON_ERROR_STOP=1 -At \
  -c "SELECT v.id || E'\\t' || v.key || E'\\t' || md5(COALESCE(v.arch_db::text, ''))
      FROM ir_ui_view v WHERE v.key LIKE 'justech_alexander%' ORDER BY v.key" \
  > "${OUT}/qweb_arch_${STAMP}.oneline.tsv"

log "QWeb inventory: ${TSV}"
log "QWeb json: ${JSON}"
log "QWeb arch backup: ${OUT}/qweb_arch_${STAMP}.oneline.tsv"
