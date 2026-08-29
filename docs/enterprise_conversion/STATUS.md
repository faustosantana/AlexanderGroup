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

```
TEMP_TRANSFER_SSH = PASS
TEMP_TRANSFER_USER_REMOVED = YES
TEMP_TRANSFER_KEY_REMOVED = YES
TEMP_TRANSFER_ACCESS_CLOSED = YES
```

Usuario `doralex-transfer` eliminado (`id` falla). Home y `authorized_keys`
borrados. `sshd_config` no se modificó ni se reinició sshd.

## Export recibido

```
EXPORT_TRANSFER = PASS
EXPORT_FINAL_PATH = /opt/doralex/imports/doralex_runtime_export_19.0-e-20260324.tar.zst
EXPORT_FINAL_SIZE = 54534193
EXPORT_FINAL_SHA256 = d406ccfd73225db88b83dfd07def618b2c48e1b1aeaebcc5877f76fa26b4cb86
EXPORT_FINAL_HASH_MATCH = YES
EXPORT_OWNER = root:root
EXPORT_MODE = 600
```

No se volvió a copiar desde Justgroup. El archivo no se sirve por HTTP.

## Baseline (antes de extraer; sin cambios)

```
STAGING_PRE_RUNTIME_BACKUP = PASS
  /opt/doralex/backups/enterprise-staging/enterprise-staging_20260829_142222
QWEB_BEFORE = 58
QWEB_BASELINE_HASH = PASS
REPORTS_PRESERVED = YES
justech_alexander_reports = 19.0.3.8.5
DORALEX_CONFIG_PRESERVED = YES
DORALEX_MAIL_CONFIG_PRESERVED = YES
MAIL_SAFE_MODE = YES
```

Staging: `ir_mail_server` solo `neutralization - disable emails` (`invalid:1025`).
`fetchmail` activo = 0. `web.base.url` = `https://enterprise.doralexgroup.cloud`.
`mail.catchall.domain` sigue `doralexgroup.cloud`. Cron activo = 1 (autovacuum).
`addons_path` staging intacto. Contenedores Prod/Dev/staging healthy; no restart.

## Extracto aislado

```
EXPORT_EXTRACTED = YES
RUNTIME_SOURCE_PATH = /opt/doralex/runtime-source/19.0-e-20260324
```

Presente: `enterprise/`, `custom-addons/`, `core-metadata/`, `inventories/`,
`README_RUNTIME.txt`. No se extrajo sobre `/usr/lib/odoo`, `/usr/lib/python3`,
`/opt/doralex/custom-addons` ni `/opt/doralex/production`.

```
ENTERPRISE_DIRECTORIES = 747
ENTERPRISE_MANIFESTS = 746
ENTERPRISE_INSTALLABLE = 746
ENTERPRISE_NON_INSTALLABLE = 0
CUSTOM_DIRECTORIES = 44
CUSTOM_MANIFESTS = 45
```

El directorio extra de Enterprise sin manifiesto es `l10n_it_xml_export`.
El manifiesto extra de custom es anidado: `justech_dgcp_bridge/justech_dgcp_bridge/`.
Hay `web_enterprise` en el árbol; **no se instaló**.

## Secretos

```
EXPORT_SECRETS_FOUND = none
EXPORT_DATABASE_FOUND = NO
EXPORT_FILESTORE_FOUND = NO
EXPORT_SUBSCRIPTION_FOUND = NO
```

No hay `.pem` / `.key` / `.p12` / `.pfx` / `.env` / `odoo.conf` / dumps /
filestore. Quedan fixtures **upstream** de Odoo Enterprise (no secretos Justgroup
ni Doralex; no se borraron):

- 14 `.crt` públicos demo/test (`l10n_ar_edi`, `l10n_co_dian`)
- 2 plantillas CAF de test `l10n_cl_edi*` (`caf_file_template.xml`) con
  marcador PEM de prueba (empresa demo chilena 2019, no producción)

## Custom addons (solo comparación)

Tabla: `docs/enterprise_conversion/evidence/custom_addons_compare_20260829.tsv`

```
MATCH = 6
DIFFERENT = 5
MISSING (en source, no en Doralex) = 33
DORALEX_ONLY = 5
```

```
ALEXANDER_REPORTS_SOURCE_PRESENT = NO
ALEXANDER_REPORTS_SOURCE_VERSION =
ALEXANDER_REPORTS_DORALEX_VERSION = 19.0.3.8.5
ALEXANDER_REPORTS_ACTION = PRESERVE_DORALEX
```

`justech_alexander_*` no viene en el export. No se copió ni se sobrescribió nada.

## Core — no alineado; no construir imagen

```
DORALEX_CORE_VERSION = 19.0.20260817
SOURCE_CORE_VERSION = 19.0.20260324
CORE_VERSION_MATCH = NO
CORE_ALIGNMENT_PLAN = WAIT_EXACT_CORE_PACKAGE
CORE_ARTIFACT_MISSING = odoo_19.0.20260324_all.deb
```

El export trae **solo metadata** del core (`dpkg` Version `19.0.20260324`,
`odoo_release` `19.0-20260324`, lista de 669 addons, tamaño 1.4G). No incluye
el árbol `/usr/lib/python3/dist-packages/odoo` ni `/usr/bin/odoo` ni un `.deb`.
En Doralex no hay cache apt con ese paquete. El nightly de esa fecha ya fue 404.

No se puede reconstruir el core exacto con lo ya recibido. Falta **uno** de:

1. `odoo_19.0.20260324_all.deb` (paquete Debian exacto de Justgroup / cache), o
2. segundo export **solo core**: `/usr/lib/python3/dist-packages/odoo` +
   `/usr/bin/odoo` + `dpkg -L odoo`.

No usar `odoo:19` latest ni `19.0.20260817` como base final.
**No se construyó la imagen Enterprise. No se instaló `web_enterprise`.**

## Prohibido hasta autorización

No instalar módulos. No cambiar DB/filestore/SMTP/QWeb/params. No tocar
`doralexgroup.cloud`. `CUTOVER_ALLOWED = NO`.
