#!/usr/bin/env bash
# READ-ONLY PROD host inventory. Never writes. Never docker restart. Never -u.
set -euo pipefail
echo "=== HOST ==="
hostname
uname -a
echo "=== CONTAINERS ==="
docker ps --format '{{.Names}} {{.Status}} {{.Image}} {{.ID}}' | sed -n '1,20p'
echo "=== PROD ODOO INSPECT ==="
docker inspect doralex-production-odoo --format 'Name={{.Name}} Image={{.Config.Image}} Started={{.State.StartedAt}} Status={{.State.Status}}'
echo "=== PROD MOUNTS ==="
docker inspect doralex-production-odoo --format '{{range .Mounts}}{{.Type}} {{.Source}} -> {{.Destination}} {{.Mode}}{{println}}{{end}}'
echo "=== PROD ENV (no secrets) ==="
docker exec doralex-production-odoo bash -lc 'echo HOST=$HOST USER=$USER; grep -E "^(db_name|addons_path|http_port|without_demo|logfile)=" /etc/odoo/odoo.conf | sed "s/password=.*/password=REDACTED/"'
echo "=== ODOO VERSION ==="
docker exec doralex-production-odoo bash -lc 'python3 /usr/bin/odoo --version; cat /usr/lib/python3/dist-packages/odoo/release.py | head -20'
echo "=== POSTGRES ==="
docker exec doralex-production-db bash -lc 'psql -U doralex_prod -d doralex_prod -c "SELECT current_database(), inet_server_addr(), version();"'
echo "=== FILESTORE SIZE ==="
docker exec doralex-production-odoo bash -lc 'du -sh /var/lib/odoo/filestore 2>/dev/null; du -sh /var/lib/odoo/filestore/doralex_prod 2>/dev/null; ls /var/lib/odoo/filestore | head'
echo "=== ADDONS ALEXANDER ON HOST ==="
for p in /opt/doralex/production/custom-addons /opt/doralex/custom-addons /opt/odoo/custom-addons; do
  if [ -d "$p/justech_alexander_base" ]; then
    echo "FOUND $p"
    python3 - <<PY
import ast, pathlib
root = pathlib.Path("$p")
for name in ("justech_alexander_base","justech_alexander_ux","justech_alexander_reports"):
    man = root / name / "__manifest__.py"
    if man.exists():
        data = ast.literal_eval(man.read_text())
        print("MANIFEST", name, data.get("version"))
PY
  fi
done
echo "=== GIT CANDIDATES ==="
for p in /opt/doralex/repository /opt/doralex/production /opt/doralex /opt/odoo /opt/doralex/production/custom-addons; do
  if [ -d "$p/.git" ]; then
    echo "GIT $p"
    git -C "$p" rev-parse --abbrev-ref HEAD
    git -C "$p" rev-parse HEAD
    git -C "$p" status -sb
    git -C "$p" log -1 --oneline
  fi
done
echo "=== BACKUP ROOTS ==="
ls -ld /opt/doralex/backups /opt/doralex/backups/production /opt/doralex/backups/prod /opt/odoo-backups 2>/dev/null || true
ls /opt/doralex/backups/production 2>/dev/null | tail
ls /opt/odoo-backups 2>/dev/null | tail
echo "=== SCRIPTS ==="
ls -l /opt/doralex/scripts/backup.sh /opt/doralex/scripts/verify_backup.sh /opt/doralex/scripts/restore.sh 2>/dev/null || true
echo "=== FROZEN MODULES ON HOST ==="
for name in justech_l10n_do_payments_withholding justech_purchase_sale_margin_control justech_sale_purchase_trace multi_invoice_manual_payment_prod; do
  find /opt/doralex /usr/lib/odoo -maxdepth 5 -type f -name __manifest__.py 2>/dev/null | grep -F "/$name/" | head -3
done
echo "=== PRECHECK DONE ==="
