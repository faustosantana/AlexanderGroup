#!/usr/bin/env bash
# Regenerate addons/vendor/odoo-custom-addons from canonical SoT.
# Requires local clone access to faustosantana/odoo-custom-addons (not Cloud Agent).
set -euo pipefail
AG_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CANONICAL_PATH="${CANONICAL_PATH:-$AG_ROOT/../odoo-custom-addons}"
VENDOR_DIR="$AG_ROOT/addons/vendor/odoo-custom-addons"

if [[ ! -d "$CANONICAL_PATH/.git" ]]; then
  echo "ERROR: canonical clone not found at $CANONICAL_PATH" >&2
  echo "Set CANONICAL_PATH to your local odoo-custom-addons checkout." >&2
  exit 2
fi

git -C "$CANONICAL_PATH" fetch origin --tags --quiet || true
git -C "$CANONICAL_PATH" checkout main --quiet
git -C "$CANONICAL_PATH" pull --ff-only origin main --quiet || true

bash "$CANONICAL_PATH/tools/export_vendor_snapshot.sh" "$VENDOR_DIR"

# stamp sync metadata into AlexanderGroup
python3 - <<PY
import json
from pathlib import Path
from datetime import datetime, timezone
vendor=Path("$VENDOR_DIR")
ref=json.loads((vendor/"ORIGIN_REF.json").read_text())
ref["synced_at"]=datetime.now(timezone.utc).isoformat()
ref["synced_into"]="AlexanderGroup/addons/vendor/odoo-custom-addons"
(vendor/"ORIGIN_REF.json").write_text(json.dumps(ref, indent=2)+"\n")
print("VENDOR_SYNC_OK commit={canonical_commit} modules={n}".format(
  canonical_commit=ref["canonical_commit"][:12], n=len(ref["modules"])))
PY
