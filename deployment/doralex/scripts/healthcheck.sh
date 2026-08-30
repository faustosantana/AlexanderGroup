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
PORT="${ODOO_HTTP_PORT:-}"
if [ -z "$PORT" ]; then
  case "$ENV_NAME" in
    production) PORT=8069 ;;
    enterprise-staging) PORT=8269 ;;
    *) PORT=8169 ;;
  esac
fi
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
health_url="http://127.0.0.1:${PORT}/web/health"
if curl -fsS "$health_url" >/dev/null 2>&1 ||
   python3 -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('${health_url}', timeout=5).getcode()==200 else 1)" 2>/dev/null; then
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
