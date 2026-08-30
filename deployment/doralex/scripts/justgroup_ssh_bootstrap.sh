#!/usr/bin/env bash
# Configura SSH de SOLO LECTURA a Justgroup (31.97.6.178).
# Lee la llave desde la variable de entorno (nunca en Git, nunca se imprime).
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "${SCRIPT_DIR}/lib.sh"

KEY="${HOME}/.ssh/justgroup_vps_ed25519"
CONFIG="${HOME}/.ssh/config"
HOST_IP="31.97.6.178"

if [ -z "${JUSTGROUP_SSH_PRIVATE_KEY:-}" ]; then
  err "Falta JUSTGROUP_SSH_PRIVATE_KEY."
  err "Es el mismo acceso de solo lectura usado el 2026-08-27 (ssh justgroup-vps)."
  exit 3
fi

mkdir -p "${HOME}/.ssh"
chmod 700 "${HOME}/.ssh"
umask 077
printf '%s\n' "${JUSTGROUP_SSH_PRIVATE_KEY}" > "$KEY"
chmod 600 "$KEY"
touch "$CONFIG"
chmod 600 "$CONFIG"
if ! grep -qE '^Host[[:space:]]+justgroup-vps$' "$CONFIG"; then
  cat >> "$CONFIG" <<EOF

Host justgroup-vps
    HostName ${HOST_IP}
    User root
    Port 22
    IdentityFile ${KEY}
    IdentitiesOnly yes
    StrictHostKeyChecking accept-new
EOF
fi

ssh -o BatchMode=yes -o ConnectTimeout=12 justgroup-vps \
  'echo READONLY_OK-$(hostname); systemctl is-active odoo || true'
log "Justgroup SSH de solo lectura: PASS"
