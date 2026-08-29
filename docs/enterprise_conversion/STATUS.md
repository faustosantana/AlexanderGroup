# Conversión Community → Enterprise — estado

**Fecha:** 2026-08-29  
**Cutover:** `CUTOVER_ALLOWED = NO`

```
ENTERPRISE_PACKAGE_ROUTE = JUSTGROUP_RUNTIME_COPY
ENTERPRISE_SOURCE_SELECTED = justgroup.app
SOURCE_ODOO_VERSION = 19.0-20260324
SOURCE_ODOO_EDITION = Enterprise
GITHUB_BLOCKER = REMOVE
JUSTECH_SUBSCRIPTION_COPIED = NO
DORALEX_SUBSCRIPTION_ACTIVATION = PENDING
JUSTGROUP_DATA_COPIED = NO
JUSTGROUP_SUBSCRIPTION_COPIED = NO
JUSTGROUP_PROD_TOUCHED = NO
DORALEX_PROD_TOUCHED = NO
CUTOVER_ALLOWED = NO
```

## Hecho en Doralex (sin el archivo todavía)

```
QWEB_BEFORE = 58
QWEB_BASELINE_HASH = PASS
STAGING_PRE_RUNTIME_BACKUP = PASS
  /opt/doralex/backups/enterprise-staging/enterprise-staging_20260829_142222
DORALEX_CORE_VERSION_BEFORE = 19.0.20260817 (Community, imagen odoo:19)
PYTHON_VERSION_ACTUAL = 3.12.3
OS_VERSION_ACTUAL = Ubuntu 24.04.4 LTS
WKHTMLTOPDF_VERSION_ACTUAL = 0.12.6.1 patched qt
STAGING_HEALTH = PASS
PROD_HEALTH = PASS
```

No se montó Enterprise 20260324 sobre el core 20260817.

## Transfer del export

```
EXPORT_TRANSFER = FAIL
EXPORT_SHA256_MATCH = (no calculado: archivo ausente)
WHAT_IS_MISSING = SSH justgroup-vps (justgroup_vps_ed25519 / JUSTGROUP_SSH_PRIVATE_KEY)
SOURCE = justgroup.app:/root/doralex_runtime_export_19.0-e-20260324.tar.zst
EXPECTED_SHA256 = d406ccfd73225db88b83dfd07def618b2c48e1b1aeaebcc5877f76fa26b4cb86
DEST = /opt/doralex/imports/doralex_runtime_export_19.0-e-20260324.tar.zst
```

Scripts listos: `transfer_justgroup_runtime_export.sh` → `import_justgroup_runtime_export.sh` →
`build_doralex_enterprise_image.sh` → `apply_enterprise_runtime_staging.sh`
(`-i web_enterprise` únicamente).

Nightly `odoo_19.0.20260324_all.deb` = 404; el core exacto debe salir de Justgroup
(`.deb` en cache o metadata del export). No se usó `odoo:19` latest.
