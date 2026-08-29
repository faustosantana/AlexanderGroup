# Conversión Community → Enterprise — estado

**Fecha:** 2026-08-29  
**Cutover:** `CUTOVER_ALLOWED = NO`  
**Estrategia vigente:** runtime Enterprise desde Justgroup/Justech (**solo lectura**).  
El `.deb` Doralex no bloquea: Odoo aún no habilita ese contrato para descarga.

```
ENTERPRISE_PACKAGE_ROUTE = JUSTGROUP_RUNTIME_COPY
GITHUB_BLOCKER = REMOVE
DORALEX_SUBSCRIPTION_ACTIVATION = PENDING
JUSTECH_DATA_COPIED = NO
JUSTECH_SUBSCRIPTION_COPIED = NO
JUSTECH_PROD_TOUCHED = NO
DORALEX_PROD_TOUCHED = NO
CUTOVER_ALLOWED = NO
```

## Fase 1 — source (HTTP vivo)

| Sitio | IP | `server_version` | Edición |
| --- | --- | --- | --- |
| justgroup.app | 31.97.6.178 | `19.0+e-20260324` | Enterprise |
| erp.justech.do | 207.244.242.58 | `19.0+e-20260324` | Enterprise |
| doralexgroup.cloud | 2.25.121.111 | `19.0-20260817` | Community |
| staging 127.0.0.1:8269 | mismo host Doralex | Community `odoo:19` | Community |

Misma versión/edición pública Justgroup ↔ erp.justech.do. **Hosts distintos.**  
Inventario SSH 2026-08-27 (solo lectura) está en **justgroup.app** (`/usr/lib/odoo/enterprise`, 360 módulos).  
`erp.justech.do:22` está abierto, pero este agente **no tiene llave**.

```
ENTERPRISE_SOURCE_SELECTED = justgroup.app
SOURCE_ODOO_VERSION = 19.0+e-20260324
SOURCE_ODOO_EDITION = Enterprise
SOURCE_RUNTIME_TYPE = host + addons /usr/lib/odoo/enterprise (no Docker en la auditoría 2026-08-27)
SOURCE_IMAGE_DIGEST = N/A
SOURCE_ENTERPRISE_PATH = /usr/lib/odoo/enterprise
```

## Fase 8 — QWeb Doralex (antes de cambiar staging)

```
QWEB_BEFORE = 58
justech_alexander_reports = 19.0.3.8.5
```

Inventario + hashes: `docs/enterprise_conversion/evidence/qweb_doralex_before_20260829.json`  
Copia en servidor: `/opt/doralex/backups/enterprise-staging/qweb_doralex_20260829_140443.*`

## Bloqueo actual (no es el .deb)

```
ENTERPRISE_RUNTIME_COPIED = NO
WEB_ENTERPRISE_INSTALLED = NO
WHAT_IS_MISSING = JUSTGROUP_SSH_PRIVATE_KEY
```

Este entorno tiene SSH a Doralex, no a Justgroup (`justgroup_vps_ed25519` ausente; `Permission denied` a 31.97.6.178).  
Scripts listos (solo lectura / rsync addons):

- `justgroup_ssh_bootstrap.sh`
- `audit_justgroup_readonly.sh`
- `copy_justgroup_enterprise_runtime.sh` → `/opt/doralex/enterprise-addons/19/`
- `inventory_staging_qweb.sh`

No se copia DB, filestore, correos, clientes ni el código de suscripción Justech.

## Waves

| Wave | Estado |
| --- | --- |
| 0 Backup / 1 Staging | PASS |
| QWeb inventory | PASS 58 |
| Runtime Enterprise copy | **espera llave SSH Justgroup** |
| `-i web_enterprise` | pendiente copia |
| 3–8 módulos / español / QA | pendiente |
| Cutover | **NO** |
