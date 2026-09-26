#!/usr/bin/env bash
# PROD backup before NCF B15 write. Validates pg_restore -l. Does not restore.
set -euo pipefail
STAMP="${1:-$(date +%Y%m%d_%H%M%S)}"
NAME="pre_ncf_b15_sequence_update_${STAMP}"
ssh doralex-server bash -s -- "$NAME" <<'EOS'
set -euo pipefail
NAME="$1"
ROOT="/opt/odoo-backups/${NAME}"
mkdir -p "$ROOT"/{db,filestore,custom-addons,config}
docker exec -u postgres doralex-production-db bash -lc \
  'pg_dump -U doralex_prod -d doralex_prod -Fc -f /var/lib/postgresql/doralex_prod.dump'
docker cp doralex-production-db:/var/lib/postgresql/doralex_prod.dump "$ROOT/db/doralex_prod.dump"
docker exec -u postgres doralex-production-db pg_restore -l /var/lib/postgresql/doralex_prod.dump \
  > "$ROOT/db/pg_restore.list"
docker exec -u postgres doralex-production-db rm -f /var/lib/postgresql/doralex_prod.dump
test -s "$ROOT/db/pg_restore.list"
test -s "$ROOT/db/doralex_prod.dump"
# filestore + addons + config as real files
if [ -d /opt/doralex/production/custom-addons ]; then
  tar -C /opt/doralex/production -cf "$ROOT/custom-addons/custom-addons.tar" custom-addons
fi
if [ -f /opt/doralex/production/config/odoo.conf ]; then
  cp -a /opt/doralex/production/config/odoo.conf "$ROOT/config/odoo.conf"
fi
docker exec doralex-production-odoo bash -lc \
  'tar -C /var/lib/odoo -cf /tmp/odoo_data_ncf.tar filestore/doralex_prod'
docker cp doralex-production-odoo:/tmp/odoo_data_ncf.tar "$ROOT/filestore/odoo_data.tar"
docker exec doralex-production-odoo rm -f /tmp/odoo_data_ncf.tar
test -s "$ROOT/filestore/odoo_data.tar"
test -s "$ROOT/custom-addons/custom-addons.tar"
test -s "$ROOT/config/odoo.conf"
echo "PRE_NCF_UPDATE_BACKUP=PASS"
echo "ROOT=$ROOT"
echo "DUMP_BYTES=$(stat -c%s "$ROOT/db/doralex_prod.dump")"
echo "TOC=$(wc -l < "$ROOT/db/pg_restore.list")"
ls -lah "$ROOT"/db "$ROOT"/filestore "$ROOT"/custom-addons "$ROOT"/config
EOS
