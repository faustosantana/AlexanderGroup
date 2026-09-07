#!/usr/bin/env bash
# Ejecuta un script Graph en el servidor. No imprime secretos.
set -euo pipefail
SCRIPT="${1:?script name inside tools/alexander_m365_users}"
ROOT="$(cd "$(dirname "$0")" && pwd)"
REMOTE_DIR="/tmp/alexander_m365_users"
scp -q -r "$ROOT" "doralex-server:${REMOTE_DIR}.new"
ssh doralex-server "rm -rf ${REMOTE_DIR} && mv ${REMOTE_DIR}.new ${REMOTE_DIR}"
ssh doralex-server "cd ${REMOTE_DIR} && DX_MS_GRAPH_DIR=/opt/doralex/secrets/microsoft python3 ${SCRIPT}"
