#!/usr/bin/env bash
# Restore the nominated STAGING backup into a TEMP database only.
# Never touches doralex_ent_staging or doralex_prod.
set -euo pipefail
SRC=/opt/doralex/backups/enterprise-staging/pre_alexander_staging_uat_20260916_183140
DB=doralex_restore_test_20260916
DUMP="$SRC/db/doralex_ent_staging.dump"
FS="$SRC/filestore/filestore.tar.gz"
START=$(date +%s)
echo "RESTORE_START $(date -u +%FT%TZ)"
echo "SRC=$SRC"
test -f "$DUMP"
test -f "$FS"
docker cp "$DUMP" doralex-enterprise-staging-db:/tmp/${DB}.dump
docker exec doralex-enterprise-staging-db pg_restore -l /tmp/${DB}.dump | wc -l | awk '{print "TOC",$1}'
docker exec doralex-enterprise-staging-db bash -lc \
  "dropdb -U doralex_ent_staging --if-exists $DB && createdb -U doralex_ent_staging $DB"
docker exec doralex-enterprise-staging-db pg_restore \
  -U doralex_ent_staging -d "$DB" --no-owner --role=doralex_ent_staging \
  /tmp/${DB}.dump
docker exec doralex-enterprise-staging-db rm -f /tmp/${DB}.dump
docker exec doralex-enterprise-staging-db bash -lc \
  "psql -U doralex_ent_staging -d $DB -c 'SELECT count(*) AS tables FROM information_schema.tables;'"
# Temp filestore next to staging, never replacing doralex_ent_staging.
docker exec doralex-enterprise-staging-odoo bash -lc \
  "rm -rf /var/lib/odoo/filestore/$DB && mkdir -p /tmp/${DB}_fs && rm -rf /tmp/${DB}_fs"
docker cp "$FS" doralex-enterprise-staging-odoo:/tmp/${DB}_filestore.tar.gz
docker exec doralex-enterprise-staging-odoo bash -lc \
  "mkdir -p /tmp/${DB}_unpack && tar -C /tmp/${DB}_unpack -xzf /tmp/${DB}_filestore.tar.gz && mkdir -p /var/lib/odoo/filestore && if [ -d /tmp/${DB}_unpack/doralex_ent_staging ]; then mv /tmp/${DB}_unpack/doralex_ent_staging /var/lib/odoo/filestore/$DB; elif [ -d /tmp/${DB}_unpack/filestore/doralex_ent_staging ]; then mv /tmp/${DB}_unpack/filestore/doralex_ent_staging /var/lib/odoo/filestore/$DB; else ls -la /tmp/${DB}_unpack; exit 1; fi && find /var/lib/odoo/filestore/$DB -type f | wc -l && rm -rf /tmp/${DB}_unpack /tmp/${DB}_filestore.tar.gz"
END=$(date +%s)
echo "RESTORE_LOAD_SECONDS=$((END-START))"
echo "RESTORE_LOAD_OK"
