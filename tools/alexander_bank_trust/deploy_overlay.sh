#!/usr/bin/env bash
# Directed -u justech_alexander_base. Never -u all.
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
SRC="$ROOT/addons/alexander/justech_alexander_base"
ssh doralex-server "test -d ${HOST_ADDONS}/justech_alexander_base"
ssh doralex-server "mkdir -p ${HOST_ADDONS}/justech_alexander_base/migrations/19.0.1.0.21"
tar -C "$SRC" -cf - \
  models/res_partner_bank.py \
  models/account_move_bank_trust.py \
  models/__init__.py \
  hooks.py \
  __manifest__.py \
  migrations/19.0.1.0.21/end-trust_company_banks.py \
  | ssh doralex-server "tar -C ${HOST_ADDONS}/justech_alexander_base -xf -"
ssh doralex-server "docker exec -u 100:101 ${CT} bash -lc \
  'python3 /usr/bin/odoo -d ${DB} --db_host=\"\$HOST\" --db_user=\"\$USER\" --db_password=\"\$PASSWORD\" \
   -u justech_alexander_base --stop-after-init --no-http'"
ssh doralex-server "docker restart ${CT}"
echo "OVERLAY_U=${TARGET}=PASS"
