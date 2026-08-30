#!/usr/bin/env bash
# Doralex — biblioteca común para scripts de infraestructura.
# Se importa con:  source "$(dirname "$0")/lib.sh"
# No contiene secretos. No ejecuta nada por sí sola.

set -euo pipefail

DORALEX_BASE="${DORALEX_BASE:-/opt/doralex}"

log()  { printf '[%s] %s\n' "$(date +'%Y-%m-%dT%H:%M:%S%z')" "$*"; }
err()  { printf '[%s] ERROR: %s\n' "$(date +'%Y-%m-%dT%H:%M:%S%z')" "$*" >&2; }
die()  { err "$*"; exit 1; }

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || die "Comando requerido no encontrado: $1"
}

# Valida y normaliza el nombre de entorno.
require_env_name() {
  local env="${1:-}"
  case "$env" in
    production|dev|enterprise-staging) printf '%s' "$env" ;;
    *) die "Entorno inválido: '${env}'. Use 'production', 'dev' o 'enterprise-staging'." ;;
  esac
}

env_dir() { printf '%s/%s' "$DORALEX_BASE" "$(require_env_name "$1")"; }
backup_root() { printf '%s/backups/%s' "$DORALEX_BASE" "$(require_env_name "$1")"; }
compose_file() { printf '%s/docker-compose.yml' "$(env_dir "$1")"; }
env_file() { printf '%s/.env' "$(env_dir "$1")"; }

# Carga variables desde el .env del entorno sin imprimir valores.
load_env() {
  local ef
  ef="$(env_file "$1")"
  [ -f "$ef" ] || die "No existe el archivo de entorno: ${ef}"
  set -a
  # shellcheck disable=SC1090
  . "$ef"
  set +a
}

# Ejecuta docker compose para el entorno indicado.
dc() {
  local env="$1"; shift
  require_cmd docker
  docker compose \
    --project-name "doralex-${env}" \
    --env-file "$(env_file "$env")" \
    -f "$(compose_file "$env")" \
    "$@"
}

db_container() { printf 'doralex-%s-db' "$(require_env_name "$1")"; }
odoo_container() { printf 'doralex-%s-odoo' "$(require_env_name "$1")"; }
