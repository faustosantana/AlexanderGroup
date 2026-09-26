#!/usr/bin/env bash
# Host-side backup inventory. Prints paths and sizes. No secrets.
set -euo pipefail
echo "=== HOST ==="
hostname
uname -a
echo "=== DISK ==="
df -h / /opt /var 2>/dev/null | sed -n '1,10p'
echo "=== MEM ==="
free -h
echo "=== CPU ==="
nproc
echo "=== DOCKER ==="
docker ps --format '{{.Names}} {{.Status}} {{.Image}}'
echo "=== BACKUPS /opt/odoo-backups ==="
ls -lah /opt/odoo-backups 2>/dev/null | head -40
echo "=== BACKUPS enterprise-staging ==="
ls -lah /opt/doralex/backups/enterprise-staging 2>/dev/null | tail -20
echo "=== LATEST PROD BACKUP CONTENTS ==="
LATEST=$(ls -1dt /opt/odoo-backups/pre_* 2>/dev/null | head -1 || true)
echo "LATEST=$LATEST"
if [ -n "${LATEST:-}" ]; then
  find "$LATEST" -maxdepth 3 -type f -printf '%p %s\n' | head -40
  if [ -f "$LATEST/db/pg_restore.list" ]; then
    echo "PG_RESTORE_LIST_LINES=$(wc -l < "$LATEST/db/pg_restore.list")"
  fi
fi
echo "=== CRON BACKUP ==="
ls -lah /etc/cron.d /etc/cron.daily 2>/dev/null | head
grep -R --line-number -E 'pg_dump|backup|odoo-backups' /etc/cron.d /opt/doralex 2>/dev/null | grep -v Binary | head -40 || true
echo "=== FILESTORE VOLUME ==="
docker inspect doralex-production-odoo --format '{{range .Mounts}}{{.Source}} -> {{.Destination}}{{println}}{{end}}'
echo "DONE_HOST"
