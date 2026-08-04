#!/usr/bin/env bash
# ==============================================================================
# deploy.example.sh — Alexander Group (Odoo 19)
# EJEMPLO / PLANTILLA. NO APROBADO PARA PRODUCCIÓN. No ejecutar en Fase 0.
#
# Referencia de un flujo de despliegue basado en contenedores.
# NO se conecta a ningún servidor real en esta fase.
# ==============================================================================
set -euo pipefail

COMPOSE_FILE="${COMPOSE_FILE:-deployment/docker/docker-compose.yml}"

echo "[deploy] Script de EJEMPLO. Requiere servidor definitivo y variables completas."

# Prerrequisitos (validar manualmente antes de habilitar):
#   - Servidor y credenciales confirmados.
#   - .env completado a partir de config/env.example.
#   - Estrategia de backups probada.
#   - Versión de Odoo 19 validada (Community/Enterprise confirmado).

# --- Ejemplo de pasos (deshabilitados) ---
# git pull --ff-only origin main
# docker compose -f "${COMPOSE_FILE}" pull
# docker compose -f "${COMPOSE_FILE}" up -d
# docker compose -f "${COMPOSE_FILE}" ps

echo "[deploy] (deshabilitado) Descomentar tras aprobar la infraestructura (Fase 3)."
