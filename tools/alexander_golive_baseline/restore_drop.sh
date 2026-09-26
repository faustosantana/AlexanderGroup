#!/usr/bin/env bash
# Drop the isolated restore copy. Never touches prod/staging DBs.
set -euo pipefail
DB=doralex_restore_golive_20260926
echo "DROP_START $DB"
docker exec doralex-enterprise-staging-db bash -lc \
  "dropdb -U doralex_ent_staging --if-exists $DB"
docker exec doralex-enterprise-staging-odoo bash -lc \
  "rm -rf /var/lib/odoo/filestore/$DB"
echo "DROP_OK $DB"
