#!/usr/bin/env bash
# Doralex — healthcheck de un entorno (contenedores + HTTP de Odoo en loopback).
# Uso:  bash healthcheck.sh production   |   bash healthcheck.sh dev
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "${SCRIPT_DIR}/lib.sh"

ENV_NAME="$(require_env_name "${1:-}")"
require_cmd docker
load_env "$ENV_NAME"

DB_CT="$(db_container "$ENV_NAME")"
ODOO_CT="$(odoo_container "$ENV_NAME")"
PORT="${ODOO_HTTP_PORT:-$([ "$ENV_NAME" = production ] && echo 8069 || echo 8169)}"
status=0

check_health() {
  local ct="$1" state
  state="$(docker inspect --format '{{.State.Health.Status}}' "$ct" 2>/dev/null || echo 'missing')"
  if [ "$state" = "healthy" ]; then
    log "OK  ${ct}: healthy"
  else
    err "${ct}: estado='${state}'"; status=1
  fi
}

check_health "$DB_CT"
check_health "$ODOO_CT"

log "Probando HTTP de Odoo en 127.0.0.1:${PORT} ..."
if curl -fsS "http://127.0.0.1:${PORT}/web/health" >/dev/null 2>&1; then
  log "OK  HTTP /web/health responde"
else
  err "HTTP /web/health no responde en 127.0.0.1:${PORT}"; status=1
fi

if [ "$status" -eq 0 ]; then
  log "HEALTHCHECK PASS (${ENV_NAME})"
else
  err "HEALTHCHECK FAIL (${ENV_NAME})"
fi
exit "$status"
