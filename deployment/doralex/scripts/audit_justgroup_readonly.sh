#!/usr/bin/env bash
# Auditoría SOLO LECTURA de Justgroup / erp.justech.do runtime.
# PROHIBIDO: -i, -u, restart, install, edit config, tocar DB.
# Uso: bash audit_justgroup_readonly.sh
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "${SCRIPT_DIR}/lib.sh"

require_cmd ssh
ssh -o BatchMode=yes -o ConnectTimeout=12 justgroup-vps 'bash -s' <<'EOS'
set -euo pipefail
echo "HOSTNAME=$(hostname)"
echo "OS=$(. /etc/os-release && echo $PRETTY_NAME)"
echo "KERNEL=$(uname -r)"
command -v python3 >/dev/null && python3 -c 'import sys; print("PYTHON="+sys.version.split()[0])'
psql --version 2>/dev/null | head -1 || true
(command -v wkhtmltopdf >/dev/null && wkhtmltopdf --version) || true
echo "ODOO_UNIT=$(systemctl is-active odoo 2>/dev/null || echo none)"
echo "DOCKER=$(command -v docker >/dev/null && docker ps --format '{{.Names}} {{.Image}}' || echo no-docker)"
# odoo.conf paths only (no admin_passwd)
if [ -f /etc/odoo/odoo.conf ]; then
  echo "CONF=/etc/odoo/odoo.conf"
  grep -E '^(addons_path|data_dir|logfile|workers|http_port|db_name|db_user)=' /etc/odoo/odoo.conf || true
fi
echo "ENTERPRISE_CANDIDATES"
for p in /usr/lib/odoo/enterprise /opt/odoo/enterprise /usr/lib/python3/dist-packages/odoo/addons; do
  if [ -d "$p" ]; then
    echo "DIR $p"
    for m in web_enterprise account_accountant documents sign helpdesk sale_subscription sale_renting planning web_studio; do
      if [ -f "$p/$m/__manifest__.py" ]; then
        ver=$(grep -E "version" "$p/$m/__manifest__.py" | head -1)
        echo "MOD $m PATH=$p/$m $ver"
      fi
    done
  fi
done
find /usr/lib/odoo /opt/odoo /usr/lib/python3 -type d -name web_enterprise 2>/dev/null | head
echo "DPKG_ODOO"
dpkg -l odoo 2>/dev/null | tail -1 || echo no-odoo-dpkg
echo "CUSTOM=/usr/lib/odoo/custom-addons"
ls /usr/lib/odoo/custom-addons 2>/dev/null | wc -l
EOS
