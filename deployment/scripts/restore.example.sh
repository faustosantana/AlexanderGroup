#!/usr/bin/env bash
# ==============================================================================
# restore.example.sh — Alexander Group (Odoo 19)
# EJEMPLO / PLANTILLA. NO APROBADO PARA PRODUCCIÓN. No ejecutar en Fase 0.
#
# Restaura una base de datos y filestore desde un respaldo generado por
# backup.example.sh. Operación DESTRUCTIVA: valida siempre el destino.
# ==============================================================================
set -euo pipefail

: "${ODOO_DB_NAME:?Define ODOO_DB_NAME}"
: "${ODOO_DB_USER:?Define ODOO_DB_USER}"
: "${ODOO_DB_HOST:?Define ODOO_DB_HOST}"

BACKUP_DIR="${1:-}"
if [[ -z "${BACKUP_DIR}" ]]; then
  echo "Uso: $0 <ruta_del_respaldo>"
  exit 2
fi

echo "[restore] Script de EJEMPLO. Operación destructiva: revisar antes de usar."
echo "[restore] Respaldo origen: ${BACKUP_DIR}"

# --- Restauración de base de datos (deshabilitado) ---
# PGPASSWORD="${ODOO_DB_PASSWORD}" pg_restore \
#   -h "${ODOO_DB_HOST}" -U "${ODOO_DB_USER}" -d "${ODOO_DB_NAME}" --clean \
#   "${BACKUP_DIR}/db.dump"

# --- Restauración del filestore (deshabilitado) ---
# tar -xzf "${BACKUP_DIR}/filestore.tar.gz" -C /var/lib/odoo/filestore/

echo "[restore] (deshabilitado) Descomentar tras validar entorno y destino."
