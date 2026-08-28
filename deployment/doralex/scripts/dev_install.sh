#!/usr/bin/env bash
# Doralex DEV — instalación/upgrade DIRIGIDO por módulo (nunca -u all).
# Instala/actualiza cada módulo por separado (rollback por módulo) y reporta
# OK/FAIL con el error real (leído del logfile de Odoo, no de stdout).
#
# Uso:
#   dev_install.sh -i mod1 mod2 ...     # instalar
#   dev_install.sh -u mod1 mod2 ...     # actualizar
set -uo pipefail

BASE="${DORALEX_BASE:-/opt/doralex}"
ENVN="dev"
DIR="${BASE}/${ENVN}"
LOG="${DIR}/logs/odoo.log"
PROJ="doralex-${ENVN}"

mode="${1:-}"; shift || true
case "$mode" in -i|-u) : ;; *) echo "Uso: dev_install.sh -i|-u <modulos...>"; exit 2;; esac
[ "$#" -ge 1 ] || { echo "Sin módulos"; exit 2; }

cd "$DIR" || exit 2
docker stop "doralex-${ENVN}-odoo" >/dev/null 2>&1 || true

dc_run() {
  docker compose --project-name "$PROJ" --env-file .env -f docker-compose.yml \
    run --rm --no-deps odoo \
    odoo -d "doralex_${ENVN}" "$1" "$2" --stop-after-init --without-demo=all \
    >/dev/null 2>&1
}
state() {
  docker exec "doralex-${ENVN}-db" psql -U "doralex_${ENVN}" -d "doralex_${ENVN}" \
    -tAc "SELECT state FROM ir_module_module WHERE name='$1'" 2>/dev/null
}

rc_all=0
for m in "$@"; do
  : > "$LOG" 2>/dev/null || true
  dc_run "$mode" "$m"
  st="$(state "$m")"
  if [ "$st" = "installed" ]; then
    echo "OK   ${mode} ${m}"
  else
    err="$(grep -iE 'ERROR|CRITICAL|KeyError|Traceback|ParseError|ValidationError|does not exist|External ID|Unmet|No module' "$LOG" 2>/dev/null | grep -viE 'docutils|ERROR/3|werkzeug|/web/health' | tail -1)"
    echo "FAIL ${mode} ${m} (state=${st:-none}) :: ${err}"
    rc_all=1
  fi
done

docker compose --project-name "$PROJ" --env-file .env -f docker-compose.yml up -d >/dev/null 2>&1
exit "$rc_all"
