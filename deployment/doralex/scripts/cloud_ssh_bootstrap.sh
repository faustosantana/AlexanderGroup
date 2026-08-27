#!/usr/bin/env bash
# Doralex — configura SSH para el Cloud Agent a partir de un Secret de Cursor.
# ==============================================================================
# Lee la llave privada desde la variable de entorno DORALEX_SSH_PRIVATE_KEY
# (definida como Secret en Cursor, inyectada como env var; NUNCA en Git ni en
# logs) y prepara ~/.ssh para poder usar `ssh doralex-server`.
#
# Requisitos previos (los realiza el usuario en su máquina, una vez):
#   1. Instalar la clave PÚBLICA correspondiente en root@2.25.121.111.
#   2. Agregar la clave PRIVADA como Secret DORALEX_SSH_PRIVATE_KEY.
#
# Uso (en el Cloud Agent):
#   bash cloud_ssh_bootstrap.sh && ssh doralex-server 'hostname'
# ==============================================================================
set -euo pipefail

HOST_IP="2.25.121.111"
KEY="${HOME}/.ssh/doralex_ed25519"
CONFIG="${HOME}/.ssh/config"

if [ -z "${DORALEX_SSH_PRIVATE_KEY:-}" ]; then
  echo "ERROR: falta el Secret DORALEX_SSH_PRIVATE_KEY (llave privada)." >&2
  echo "El usuario debe agregarlo en Cursor > Secrets. No se imprime su valor." >&2
  exit 3
fi

mkdir -p "${HOME}/.ssh"; chmod 700 "${HOME}/.ssh"
umask 077
# Escribir la llave sin imprimirla.
printf '%s\n' "${DORALEX_SSH_PRIVATE_KEY}" > "$KEY"
chmod 600 "$KEY"

touch "$CONFIG"; chmod 600 "$CONFIG"
if ! grep -qE '^Host[[:space:]]+doralex-server$' "$CONFIG"; then
  {
    echo ""
    echo "Host doralex-server"
    echo "    HostName ${HOST_IP}"
    echo "    User root"
    echo "    IdentityFile ${KEY}"
    echo "    IdentitiesOnly yes"
    echo "    StrictHostKeyChecking accept-new"
    echo "    ServerAliveInterval 60"
    echo "    ServerAliveCountMax 3"
  } >> "$CONFIG"
fi

echo "[cloud-ssh] Configurado. Probando conexión (BatchMode)..."
if ssh -o BatchMode=yes -o ConnectTimeout=10 doralex-server 'echo OK-$(hostname)'; then
  echo "[cloud-ssh] PASS: el Cloud Agent puede conectarse por llave."
else
  echo "[cloud-ssh] FALLO: verifique que la clave pública esté instalada en el servidor." >&2
  exit 1
fi
