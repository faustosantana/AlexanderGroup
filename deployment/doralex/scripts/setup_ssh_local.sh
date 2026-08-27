#!/usr/bin/env bash
# Doralex — configuración de SSH por LLAVE desde TU computadora (Fase 1 y 2).
# ==============================================================================
# Ejecutar en TU máquina local (no en el servidor ni en el repo del servidor).
# Crea una llave DEDICADA para Doralex, la instala en el servidor y configura
# alias en ~/.ssh/config. La contraseña root se pide UNA vez (interactivo) y
# NO se guarda ni se imprime.
#
# Uso:
#   bash setup_ssh_local.sh
# ==============================================================================
set -euo pipefail

HOST_IP="2.25.121.111"
KEY="${HOME}/.ssh/doralex_ed25519"
CONFIG="${HOME}/.ssh/config"

mkdir -p "${HOME}/.ssh"; chmod 700 "${HOME}/.ssh"

# 1) Crear llave dedicada si no existe (sin sobrescribir otras).
if [ -f "$KEY" ]; then
  echo "[ssh] Llave existente: $KEY (no se sobrescribe)."
else
  echo "[ssh] Generando llave dedicada ed25519..."
  ssh-keygen -t ed25519 -f "$KEY" -C "doralex-$(date +%Y%m%d)" -N ""
fi
chmod 600 "$KEY"; chmod 644 "${KEY}.pub"

# 2) Instalar SOLO la clave pública en root@servidor (pide password una vez).
echo "[ssh] Instalando la clave pública en root@${HOST_IP} (se pedirá la contraseña root UNA vez)..."
if command -v ssh-copy-id >/dev/null 2>&1; then
  ssh-copy-id -i "${KEY}.pub" "root@${HOST_IP}"
else
  # Alternativa portable sin ssh-copy-id.
  ssh "root@${HOST_IP}" 'umask 077; mkdir -p ~/.ssh && cat >> ~/.ssh/authorized_keys' < "${KEY}.pub"
fi

# 3) Alias en ~/.ssh/config (root y, más adelante, doralexadmin).
touch "$CONFIG"; chmod 600 "$CONFIG"
add_block() {
  local name="$1" user="$2"
  if grep -qE "^Host[[:space:]]+${name}\$" "$CONFIG"; then
    echo "[ssh] Alias '${name}' ya existe en ${CONFIG} (no se duplica)."
    return
  fi
  {
    echo ""
    echo "Host ${name}"
    echo "    HostName ${HOST_IP}"
    echo "    User ${user}"
    echo "    IdentityFile ${KEY}"
    echo "    IdentitiesOnly yes"
    echo "    ServerAliveInterval 60"
    echo "    ServerAliveCountMax 3"
  } >> "$CONFIG"
  echo "[ssh] Alias '${name}' agregado."
}
add_block "doralex-server" "root"
add_block "doralex" "doralexadmin"   # se usará tras crear el usuario admin (Fase 2)

# 4) Validar acceso por llave (root).
echo "[ssh] Validando 'ssh doralex-server' (debe entrar sin password)..."
if ssh -o BatchMode=yes -o ConnectTimeout=10 doralex-server 'echo OK-$(hostname)'; then
  echo "[ssh] PASS: acceso por llave funcionando."
else
  echo "[ssh] FALLO: revise la instalación de la clave. NO desactive password aún." >&2
  exit 1
fi

cat <<'NOTE'

[siguiente] Para que el Cloud Agent de Cursor también pueda conectarse:
  - Agregue el CONTENIDO de la llave PRIVADA (~/.ssh/doralex_ed25519) como
    "Secret" en Cursor con el nombre: DORALEX_SSH_PRIVATE_KEY
  - El agente la usará vía scripts/cloud_ssh_bootstrap.sh (no se imprime ni se
    versiona). NUNCA pegue la contraseña root; solo la llave privada.
NOTE
