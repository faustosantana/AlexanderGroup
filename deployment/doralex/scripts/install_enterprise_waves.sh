#!/usr/bin/env bash
# Instala olas de módulos en enterprise-staging. Nunca -u all. Nunca Prod.
#
# Uso: CONFIRM=yes bash install_enterprise_waves.sh <3|4|5|7>
#   3 = apps Enterprise funcionales
#   4 = Community faltantes del UX Justgroup
#   5 = custom Justech aplicables (ya vendorizados)
#   7 = idiomas es_DO + es_ES
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "${SCRIPT_DIR}/lib.sh"

[ "${CONFIRM:-no}" = "yes" ] || die "Aborta: exporte CONFIRM=yes."
WAVE="${1:-}"
load_env enterprise-staging

wave3="web_studio,account_accountant,approvals,documents,helpdesk,planning,sale_subscription,sale_renting,sign,stock_barcode,industry_fsm,timesheet_grid,knowledge,marketing_automation"
wave4="project,hr,hr_holidays,hr_timesheet,maintenance,repair,survey,event,mass_mailing,im_livechat,base_automation"
wave5="justech_approval_flow,justech_purchase_sale_margin_control,justech_sale_purchase_trace,justech_vendor_bill_po_control,multi_invoice_manual_payment_prod,justech_sale_terms_guard,justech_quotation_client_dedup,justech_admin_center,justech_l10n_do_adel_freeze"

install_list() {
  local mods="$1"
  log "Instalando (targeted): ${mods}"
  docker exec -u 100:101 doralex-enterprise-staging-odoo bash -c \
    'python3 /usr/bin/odoo -d '"${POSTGRES_DB}"' --db_host="$HOST" --db_user="$USER" --db_password="$PASSWORD" --addons-path=/mnt/enterprise,/mnt/custom-addons -i '"${mods}"' --stop-after-init --without-demo=all --no-http'
  dc enterprise-staging up -d
}

case "$WAVE" in
  3) install_list "$wave3" ;;
  4) install_list "$wave4" ;;
  5)
    err "Wave 5 requiere montar addons/vendor (VENDOR_ADDONS_SRC) y revisar hardcodes."
    die "No ejecutar a ciegas: adaptar justech_* a identidad Doralex primero."
    ;;
  7)
    log "Cargando idiomas es_DO,es_ES y aplicando a usuarios internos..."
    docker exec -u 100:101 doralex-enterprise-staging-odoo bash -c \
      'python3 /usr/bin/odoo -d '"${POSTGRES_DB}"' --db_host="$HOST" --db_user="$USER" --db_password="$PASSWORD" --load-language=es_DO,es_ES --stop-after-init --no-http'
    docker exec -i doralex-enterprise-staging-db \
      psql -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" \
      -c "UPDATE res_lang SET active=true WHERE code IN ('es_DO','es_ES'); UPDATE res_users SET lang='es_DO' WHERE share=false AND active=true;"
    dc enterprise-staging up -d
    ;;
  *) die "Ola inválida: ${WAVE}. Use 3, 4, 5 o 7." ;;
esac

bash "${SCRIPT_DIR}/healthcheck.sh" enterprise-staging
log "WAVE ${WAVE} COMPLETA en staging."
