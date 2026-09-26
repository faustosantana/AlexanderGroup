#!/usr/bin/env bash
# Restore the latest PROD backup into an isolated temp DB on staging-db.
# Never touches doralex_prod or doralex_ent_staging data.
set -euo pipefail
SRC=/opt/odoo-backups/pre_fix_multicompany_tax_access_20260926_133358
DB=doralex_restore_golive_20260926
DUMP="$SRC/db/doralex_prod.dump"
FS="$SRC/filestore/odoo_data.tar"
START=$(date +%s)
echo "RESTORE_START $(date -u +%FT%TZ)"
echo "SRC=$SRC DB=$DB"
test -f "$DUMP"
test -f "$FS"
echo "DUMP_BYTES=$(stat -c%s "$DUMP")"
echo "FS_BYTES=$(stat -c%s "$FS")"
echo "ADDONS_BYTES=$(stat -c%s "$SRC/custom-addons/custom-addons.tar")"
echo "CONF_BYTES=$(stat -c%s "$SRC/config/odoo.conf")"
docker cp "$DUMP" doralex-enterprise-staging-db:/tmp/${DB}.dump
TOC=$(docker exec doralex-enterprise-staging-db pg_restore -l /tmp/${DB}.dump | wc -l)
echo "TOC=$TOC"
docker exec doralex-enterprise-staging-db bash -lc \
  "dropdb -U doralex_ent_staging --if-exists $DB && createdb -U doralex_ent_staging $DB"
set +e
docker exec doralex-enterprise-staging-db pg_restore \
  -U doralex_ent_staging -d "$DB" --no-owner --role=doralex_ent_staging \
  /tmp/${DB}.dump
RC=$?
set -e
echo "PG_RESTORE_RC=$RC"
docker exec doralex-enterprise-staging-db rm -f /tmp/${DB}.dump
docker exec doralex-enterprise-staging-db bash -lc \
  "psql -U doralex_ent_staging -d $DB -c \"SELECT count(*) AS tables FROM information_schema.tables WHERE table_schema='public';\" -c \"SELECT count(*) AS companies FROM res_company;\" -c \"SELECT count(*) AS products FROM product_template;\" -c \"SELECT count(*) AS posted FROM account_move WHERE state='posted';\""
# Isolated filestore — never replace staging/prod filestore dirs
docker exec doralex-enterprise-staging-odoo bash -lc \
  "rm -rf /var/lib/odoo/filestore/$DB /tmp/${DB}_unpack && mkdir -p /tmp/${DB}_unpack"
docker cp "$FS" doralex-enterprise-staging-odoo:/tmp/${DB}_filestore.tar
docker exec doralex-enterprise-staging-odoo bash -lc \
  "tar -C /tmp/${DB}_unpack -xf /tmp/${DB}_filestore.tar && mkdir -p /var/lib/odoo/filestore && \
   if [ -d /tmp/${DB}_unpack/doralex_prod ]; then mv /tmp/${DB}_unpack/doralex_prod /var/lib/odoo/filestore/$DB; \
   elif [ -d /tmp/${DB}_unpack/filestore/doralex_prod ]; then mv /tmp/${DB}_unpack/filestore/doralex_prod /var/lib/odoo/filestore/$DB; \
   elif [ -d /tmp/${DB}_unpack/./filestore/doralex_prod ]; then mv /tmp/${DB}_unpack/filestore/doralex_prod /var/lib/odoo/filestore/$DB; \
   elif [ -d /tmp/${DB}_unpack/odoo/filestore/doralex_prod ]; then mv /tmp/${DB}_unpack/odoo/filestore/doralex_prod /var/lib/odoo/filestore/$DB; \
   else echo UNPACK_LAYOUT; find /tmp/${DB}_unpack -maxdepth 3 -type d; exit 1; fi && \
   echo FILESTORE_FILES=\$(find /var/lib/odoo/filestore/$DB -type f | wc -l) && \
   rm -rf /tmp/${DB}_unpack /tmp/${DB}_filestore.tar"
END=$(date +%s)
echo "RESTORE_LOAD_SECONDS=$((END-START))"
echo "RESTORE_LOAD_OK"
