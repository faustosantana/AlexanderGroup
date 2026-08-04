#!/usr/bin/env bash
# ==============================================================================
# backup.example.sh — Alexander Group (Odoo 19)
# EJEMPLO / PLANTILLA. NO APROBADO PARA PRODUCCIÓN. No ejecutar en Fase 0.
#
# Respalda la base de datos PostgreSQL y el filestore de Odoo.
# Requiere variables definidas fuera de Git (ver config/env.example -> .env).
# NUNCA hardcodear credenciales aquí.
# ==============================================================================
set -euo pipefail

# --- Parámetros (completar mediante entorno; sin valores por defecto sensibles) ---
: "${ODOO_DB_NAME:?Define ODOO_DB_NAME}"
: "${ODOO_DB_USER:?Define ODOO_DB_USER}"
: "${ODOO_DB_HOST:?Define ODOO_DB_HOST}"
: "${BACKUP_PATH:?Define BACKUP_PATH}"
FILESTORE_PATH="${FILESTORE_PATH:-/var/lib/odoo/filestore/${ODOO_DB_NAME}}"

TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
DEST="${BACKUP_PATH%/}/${ODOO_DB_NAME}_${TIMESTAMP}"

echo "[backup] Este es un script de EJEMPLO. Revisar antes de usar."
echo "[backup] Destino: ${DEST}"

# mkdir -p "${DEST}"

# --- Volcado de base de datos ---
# La contraseña debe proveerse por PGPASSWORD o ~/.pgpass, NUNCA en el script.
# PGPASSWORD="${ODOO_DB_PASSWORD}" pg_dump \
#   -h "${ODOO_DB_HOST}" -U "${ODOO_DB_USER}" -Fc "${ODOO_DB_NAME}" \
#   -f "${DEST}/db.dump"

# --- Copia del filestore ---
# tar -czf "${DEST}/filestore.tar.gz" -C "$(dirname "${FILESTORE_PATH}")" \
#   "$(basename "${FILESTORE_PATH}")"

echo "[backup] (deshabilitado) Descomentar los comandos tras validar el entorno."
