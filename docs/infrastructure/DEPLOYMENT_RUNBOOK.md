# Runbook de despliegue — Doralex

Flujo **obligatorio**. Produccion nunca es fuente de experimentación.

```text
LOCAL/CURSOR → GIT → DEV → TESTS → VALIDACION → BACKUP PRODUCCION → DEPLOY CONTROLADO
```

## 0. Acceso SSH por llave (una vez)

- En tu máquina: `bash deployment/doralex/scripts/setup_ssh_local.sh`.
- (Para el Cloud Agent) agregar Secret `DORALEX_SSH_PRIVATE_KEY` y ejecutar
  `bash deployment/doralex/scripts/cloud_ssh_bootstrap.sh`.
- No desactivar la autenticación por contraseña hasta confirmar la llave.

## 0.1 Pre-requisito: auditoría del servidor

Completar [`SERVER_AUDIT.md`](SERVER_AUDIT.md) con `audit_server.sh` (solo lectura)
**antes** de instalar o modificar nada. Verificar que no exista una instalación
previa que se pudiera destruir.

## 1. Bootstrap del servidor (una vez)

```bash
sudo bash /opt/doralex/scripts/bootstrap_dirs.sh      # crea /opt/doralex/** (enterprise-ready)
# instalar paquetes base + Docker Engine + Docker Compose si faltan (ver Fase 7)
# clonar el repo en /opt/doralex/repository
# el dir /opt/doralex/enterprise queda vacío (ENTERPRISE_SOURCE_PENDING=TRUE)
```

## 2. Preparar un entorno (Dev primero)

```bash
cd /opt/doralex/dev
cp .env.example .env                       # completar secretos fuertes
bash /opt/doralex/scripts/render_config.sh dev
docker compose --project-name doralex-dev --env-file .env -f docker-compose.yml up -d
bash /opt/doralex/scripts/healthcheck.sh dev
bash /opt/doralex/scripts/validate_isolation.sh
```

## 3. Ciclo de cambios (nunca directo en Produccion)

1. Rama `feature/*` desde `development` en local/Cursor.
2. Commit + push → PR hacia `development`.
3. Deploy en **Dev**; correr **tests** y **UAT**.
4. Validación funcional y de aislamiento (PASS).
5. Merge `development` → `main` mediante PR (release controlado).

## 4. Deploy a Produccion (controlado)

```bash
# 4.1 BACKUP OBLIGATORIO ANTES DE TOCAR PRODUCCION
bash /opt/doralex/scripts/backup.sh production      # crea y VERIFICA el backup

# 4.2 Traer el release aprobado (tag/commit de main) al servidor
cd /opt/doralex/repository && git fetch --all && git checkout <tag-o-commit-de-main>

# 4.3 Aplicar
cd /opt/doralex/production
bash /opt/doralex/scripts/render_config.sh production
docker compose --project-name doralex-production --env-file .env -f docker-compose.yml up -d

# 4.4 Verificar
bash /opt/doralex/scripts/healthcheck.sh production
```

## 5. Rollback

1. `docker compose ... down` del servicio afectado.
2. `CONFIRM=yes ALLOW_PROD=yes bash restore.sh production <backup_valido>`.
3. `healthcheck.sh production`.
4. Registrar el incidente.

## Reglas

- **No** commits funcionales directos a `main`.
- **No** cargar datos de Alexander en Produccion hasta cerrar infraestructura + Dev.
- Todo deploy a Produccion va precedido de **backup verificado**.
