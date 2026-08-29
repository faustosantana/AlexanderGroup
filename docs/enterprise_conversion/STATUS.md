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

## Acceso temporal de transferencia

Usuario anterior `doralex-transfer` (export runtime) permanece cerrado:

```
TEMP_TRANSFER_SSH = PASS
TEMP_TRANSFER_USER_REMOVED = YES
TEMP_TRANSFER_KEY_REMOVED = YES
TEMP_TRANSFER_ACCESS_CLOSED = YES
```

Canal **core** (`doralex-core-transfer`) sigue activo a propósito:

```
CLOSE_TRANSFER_CHANNEL = NO
TRANSFER_CHANNEL_CAN_CLOSE = YES
ADDITIONAL_SOURCE_ARTIFACT_REQUIRED = NO
```

No eliminar usuario ni clave hasta `CLOSE_TRANSFER_CHANNEL = YES`.

## Export runtime (Enterprise + custom)

```
EXPORT_TRANSFER = PASS
EXPORT_FINAL_PATH = /opt/doralex/imports/doralex_runtime_export_19.0-e-20260324.tar.zst
EXPORT_FINAL_SIZE = 54534193
EXPORT_FINAL_SHA256 = d406ccfd73225db88b83dfd07def618b2c48e1b1aeaebcc5877f76fa26b4cb86
EXPORT_FINAL_HASH_MATCH = YES
EXPORT_OWNER = root:root
EXPORT_MODE = 600
```

## Core exacto 19.0.20260324

El plan `WAIT_EXACT_CORE_PACKAGE` / `odoo_19.0.20260324_all.deb` se resolvió
con el export de árbol (no un `.deb` nightly).

```
CORE_FINAL_PATH = /opt/doralex/imports/doralex_core_export_19.0.20260324.tar.zst
CORE_FINAL_SIZE = 222257350
CORE_FINAL_SHA256 = d6b1e36d113a26c4adad2731d7b422fa1c1eefebc7f82bbe14486f8c178ae36a
CORE_FINAL_HASH_MATCH = YES
CORE_TREE_FOUND = YES
ODOO_BINARY_FOUND = YES
DPKG_METADATA_FOUND = YES
RUNTIME_DEPENDENCIES_FOUND = YES
CORE_EXTRACTED_VERSION = 19.0.20260324
CORE_VERSION_MATCH = YES
CORE_SECRETS_FOUND = none
CORE_DATABASE_FOUND = NO
CORE_FILESTORE_FOUND = NO
CORE_SUBSCRIPTION_FOUND = NO
```

Extracto aislado: `/opt/doralex/core-source/19.0.20260324/` (no sobre `/usr`).

## Baseline y personalizaciones

```
STAGING_PRE_RUNTIME_BACKUP = PASS
  /opt/doralex/backups/enterprise-staging/enterprise-staging_20260829_142222
QWEB_BEFORE = 58
QWEB_AFTER = 58
QWEB_BASELINE_HASH = PASS
QWEB_HASH_MISMATCH_UNEXPECTED = 0
REPORTS_PRESERVED = YES
justech_alexander_reports = 19.0.3.8.5
ALEXANDER_REPORTS_ACTION = PRESERVE_DORALEX
DORALEX_CONFIG_PRESERVED = YES
DORALEX_MAIL_CONFIG_PRESERVED = YES
DORALEX_COMPANIES_PRESERVED = YES
DORALEX_USERS_PRESERVED = YES
DORALEX_SYSTEM_PARAMETERS_PRESERVED = YES
MAIL_SAFE_MODE = YES
```

## Imagen y staging (127.0.0.1:8269)

```
DORALEX_RUNTIME_IMAGE = doralex-odoo-enterprise:19.0.20260324
ENTERPRISE_RUNTIME_BOOT = PASS
PRE_WEB_ENTERPRISE_DB_PRESERVATION = PASS
WEB_ENTERPRISE_DISCOVERED = YES
WEB_ENTERPRISE_INSTALLED = YES
ODOO_VERSION = 19.0+e-20260324
ODOO_EDITION = Enterprise
STAGING_LOGIN = PASS
STAGING_HEALTH = PASS
SPANISH_UI = PASS
PDF_QUOTATION = PASS
PDF_SALE_ORDER = PASS
PDF_INVOICE = PASS
```

`-i web_enterprise` se hace con addons **slim** (solo `web_enterprise`).
La ruta Enterprise completa auto-instala un grafo de ~129 módulos.

Prod/Dev siguen en `odoo:19`. El tag `odoo:19` no se retocó.

## Custom (sin instalar los 33 missing)

```
CUSTOM_MATCH = 6
CUSTOM_DIFFERENT = 5
CUSTOM_MISSING = 33
DORALEX_ONLY_CUSTOM = 5
SOURCE_MODULE_COUNT = 44
DORALEX_MODULE_COUNT = 16
MODULES_MISSING = 33
MODULE_VERSION_MISMATCH = 0
```

Tabla: `docs/enterprise_conversion/evidence/custom_addons_compare_20260829.tsv`  
Evidencia de esta ola: `docs/enterprise_conversion/evidence/wave3_core_runtime_20260829.txt`

## Prohibido hasta autorización

No cutover. No tocar `doralexgroup.cloud`. No cerrar el canal core.
No instalar los 33 custom missing en esta ola.
`CUTOVER_ALLOWED = NO`.
