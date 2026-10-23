#!/usr/bin/env bash
# Directed -u justech_alexander_reports. Never -u all. Never vendor trees.
set -euo pipefail
TARGET="${1:?staging|production}"
case "$TARGET" in
  staging)
    CT=doralex-enterprise-staging-odoo
    DB=doralex_ent_staging
    HOST_ADDONS=/opt/doralex/enterprise-staging/custom-addons
    ;;
  production)
    CT=doralex-production-odoo
    DB=doralex_prod
    HOST_ADDONS=/opt/doralex/production/custom-addons
    ;;
  *) echo "target must be staging or production" >&2; exit 2 ;;
esac
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SRC="$ROOT/addons/alexander/justech_alexander_reports"
ssh doralex-server "test -d ${HOST_ADDONS}/justech_alexander_reports"
tar -C "$SRC" -cf - \
  __manifest__.py \
  hooks.py \
  models/__init__.py \
  models/datefmt.py \
  models/report_compose.py \
  models/res_company.py \
  models/res_partner.py \
  models/preview.py \
  models/ir_actions_report.py \
  reports/warranty_report.xml \
  | ssh doralex-server "tar -C ${HOST_ADDONS}/justech_alexander_reports -xf -"
ssh doralex-server "docker exec -u 100:101 ${CT} bash -lc \
  'python3 /usr/bin/odoo -d ${DB} --db_host=\"\$HOST\" --db_user=\"\$USER\" --db_password=\"\$PASSWORD\" \
   -u justech_alexander_reports --stop-after-init --no-http'"
ssh doralex-server "docker restart ${CT}"
echo "OVERLAY_U=${TARGET}=PASS"
