#!/usr/bin/env bash
# Directed -u justech_alexander_ux,justech_alexander_base. Never -u all.
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
ssh doralex-server "test -d ${HOST_ADDONS}/justech_alexander_ux"
ssh doralex-server "test -d ${HOST_ADDONS}/justech_alexander_base"
ssh doralex-server "mkdir -p ${HOST_ADDONS}/justech_alexander_ux/migrations/19.0.1.6.11"
tar -C "$ROOT/addons/alexander/justech_alexander_ux" -cf - \
  hooks.py \
  __manifest__.py \
  views/account_move_views.xml \
  views/sale_order_views.xml \
  views/menus.xml \
  migrations/19.0.1.6.11/end-hide_margin.py \
  | ssh doralex-server "tar -C ${HOST_ADDONS}/justech_alexander_ux -xf -"
tar -C "$ROOT/addons/alexander/justech_alexander_base" -cf - \
  models/account_move_draft.py \
  views/account_move_views.xml \
  __manifest__.py \
  | ssh doralex-server "tar -C ${HOST_ADDONS}/justech_alexander_base -xf -"
ssh doralex-server "docker exec -u 100:101 ${CT} bash -lc \
  'python3 /usr/bin/odoo -d ${DB} --db_host=\"\$HOST\" --db_user=\"\$USER\" --db_password=\"\$PASSWORD\" \
   -u justech_alexander_ux,justech_alexander_base --stop-after-init --no-http'"
ssh doralex-server "docker restart ${CT}"
echo "OVERLAY_U=${TARGET}=PASS"
