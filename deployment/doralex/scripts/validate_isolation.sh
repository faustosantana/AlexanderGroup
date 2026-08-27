#!/usr/bin/env bash
# Doralex — valida el AISLAMIENTO entre Produccion y Dev y la exposición de red.
# ==============================================================================
# Comprueba (sección 18 del bootstrap):
#   - redes Docker separadas (doralex_prod_net vs doralex_dev_net)
#   - volúmenes separados (db y filestore por entorno)
#   - contenedores separados
#   - PostgreSQL NO publicado (ningún contenedor mapea 5432 a host)
#   - Odoo publicado SOLO en 127.0.0.1
# Imprime PASS/FAIL global.
# ==============================================================================
set -uo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "${SCRIPT_DIR}/lib.sh"

require_cmd docker
fail=0
ok()   { log "PASS  $*"; }
bad()  { err  "FAIL  $*"; fail=1; }

# 1) Redes separadas.
if docker network ls --format '{{.Name}}' | grep -qx doralex_prod_net &&
   docker network ls --format '{{.Name}}' | grep -qx doralex_dev_net; then
  ok "Redes separadas: doralex_prod_net y doralex_dev_net"
else
  bad "Faltan redes separadas doralex_prod_net / doralex_dev_net"
fi

# 2) Volúmenes separados.
for v in doralex_prod_db_data doralex_prod_odoo_data doralex_dev_db_data doralex_dev_odoo_data; do
  if docker volume ls --format '{{.Name}}' | grep -qx "$v"; then
    ok "Volumen presente: $v"
  else
    bad "Falta volumen: $v"
  fi
done

# 3) Contenedores separados.
for c in doralex-production-db doralex-production-odoo doralex-dev-db doralex-dev-odoo; do
  if docker ps -a --format '{{.Names}}' | grep -qx "$c"; then
    ok "Contenedor presente: $c"
  else
    bad "Falta contenedor: $c"
  fi
done

# 4) PostgreSQL NO expuesto (ningún puerto 5432 publicado a host).
if docker ps --format '{{.Names}} {{.Ports}}' | grep -E '(^|[^0-9])5432->' >/dev/null 2>&1; then
  bad "Algún contenedor publica 5432 al host (PostgreSQL expuesto)"
else
  ok "PostgreSQL no expuesto a host"
fi

# 5) Odoo solo en loopback (127.0.0.1).
if docker ps --format '{{.Ports}}' | grep -E '0\.0\.0\.0:(8069|8072|8169|8172)->' >/dev/null 2>&1; then
  bad "Odoo publicado en 0.0.0.0 (debe ser solo 127.0.0.1)"
else
  ok "Odoo publicado solo en loopback (o no publicado a 0.0.0.0)"
fi

# 6) Ningún volumen de Produccion montado por contenedores de Dev.
if docker inspect doralex-dev-odoo doralex-dev-db >/dev/null 2>&1; then
  if docker inspect doralex-dev-odoo doralex-dev-db 2>/dev/null | grep -q 'doralex_prod_'; then
    bad "Un contenedor de Dev referencia un volumen de Produccion"
  else
    ok "Dev no monta volúmenes de Produccion"
  fi
fi

if [ "$fail" -eq 0 ]; then
  log "ISOLATION: PASS"
  exit 0
else
  err "ISOLATION: FAIL"
  exit 1
fi
