# 08 — Estrategia de Despliegue

> **Fase 0:** solo se documenta y se dejan ejemplos en `deployment/`. No se
> despliega nada ni se conecta a servidores.

## Principios

- Despliegue reproducible basado en contenedores (Docker).
- Configuración por variables de entorno (ver `config/env.example`).
- Secretos **fuera de Git** (gestor de secretos del servidor, por definir).
- Proxy inverso con TLS (Nginx) delante de Odoo.

## Ambientes objetivo

DEV → TEST → PROD. Ver [`14_ENVIRONMENT_MATRIX.md`](14_ENVIRONMENT_MATRIX.md).

## Prerrequisitos antes de desplegar (Fase 3)

- [ ] Servidor definitivo confirmado (CPU/RAM/disco).
- [ ] Dominios y DNS.
- [ ] Certificados TLS (fuera de Git).
- [ ] Versión exacta de Odoo 19 validada.
- [ ] Confirmar Community vs. Enterprise (licencia).
- [ ] Variables completas (`.env`).
- [ ] Estrategia de backups probada ([`09_BACKUP_AND_ROLLBACK.md`](09_BACKUP_AND_ROLLBACK.md)).
- [ ] Monitoreo básico.

## Flujo de despliegue previsto (referencia)

1. Construir/actualizar imagen (ver `deployment/docker/`).
2. Aplicar configuración y variables.
3. Levantar servicios (`db`, `odoo`, `nginx`).
4. Verificar salud y logs.
5. Respaldo posterior y validación funcional.

Scripts de referencia (deshabilitados): `deployment/scripts/*.example.sh`.

## Reglas

- Ningún componente de `deployment/` está aprobado para producción en Fase 0.
- No descargar imágenes ni levantar contenedores todavía.
