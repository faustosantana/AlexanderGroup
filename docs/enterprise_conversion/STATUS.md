# Conversión Community → Enterprise — estado

**Fecha:** 2026-08-30  
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

## Canal temporal de transferencia — CERRADO

```
CLOSE_TRANSFER_CHANNEL = YES
TRANSFER_CHANNEL_CLOSED = YES
TEMP_TRANSFER_USER_REMOVED = YES
TEMP_TRANSFER_AUTHORIZED_KEY_REMOVED = YES
TEMP_TRANSFER_ACCESS_CLOSED = YES
TEMP_TRANSFER_SSH = PASS
ADDITIONAL_SOURCE_ARTIFACT_REQUIRED = NO
```

`id doralex-core-transfer` falla. Home `/home/doralex-core-transfer` eliminado.
`/opt/doralex/imports/core-incoming/` vacío (700 root). `sshd_config` no tocado.

**Conservado:**

- `/opt/doralex/imports/doralex_core_export_19.0.20260324.tar.zst`
- `/opt/doralex/imports/doralex_runtime_export_19.0-e-20260324.tar.zst`
- `/opt/doralex/runtime-source/19.0-e-20260324/`

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

## Backup pre-stack Justech

```
FULL_CUSTOM_STACK_BACKUP = PASS
  /opt/doralex/backups/enterprise-staging/pre_full_justech_custom_stack_20260829_185151
  /opt/doralex/backups/enterprise-staging/enterprise-staging_20260829_185151
```

## Custom Justech — paridad de código instalado (staging 127.0.0.1:8269)

Fuente: inventarios del export + `docs/stack_audit/justgroup_reference.json`
+ e-CF/nómina del cupo custom Justgroup. No lista manual como SoT.

```
TOTAL_CUSTOM_SOURCE = 49
TOTAL_CUSTOM_INSTALLED_JUSTGROUP = 44
TOTAL_CUSTOM_INSTALLED_DORALEX = 50
CUSTOM_SOURCE_INSTALLED = 44
CUSTOM_DORALEX_INSTALLED = 50
CUSTOM_COMMON_MISSING = 0
CUSTOM_COMMON_VERSION_MISMATCH = 0
CUSTOM_DIFFERENT_FUNCTIONAL = 2
DORALEX_ONLY_CUSTOM = 5
CUSTOM_CODE_SYNC = PASS
CUSTOM_DISCOVERED = 52
```

`DORALEX_ONLY_CUSTOM`: cinco `justech_alexander_*` (prioridad Doralex; no
sobrescritos). `justech_alexander_reports` = 19.0.3.8.5.

`CUSTOM_DIFFERENT_FUNCTIONAL = 2` (copia Doralex, no Justgroup):

| MODULE | PATH | REASON |
|---|---|---|
| `justech_l10n_do_treasury` | `views/menu_accounting_navigation.xml` | En DB fresca, dos `<record active=False>` sin `name` creaban menús huérfanos (`NotNullViolation`). Se eliminaron; en Justgroup esos xmlid ya existían. |
| `justech_ecf_admin` | `views/ecf_api_inbound_views.xml` | Etiqueta `API keys` → `Claves API` (i18n Doralex). |

Ningún módulo Justgroup se excluyó por comodidad. `justech_dgcp_bridge` y
`justech_managed_services` quedaron instalados.

```
FISCAL_ENGINE_INSTALLED = YES
ACCOUNTING_CUSTOM_INSTALLED = YES
MARGIN_CONTROL_INSTALLED = YES
APPROVAL_FLOW_INSTALLED = YES
AUDIT_INSTALLED = YES
WARRANTY_INSTALLED = YES
TRACEABILITY_INSTALLED = YES
VENDOR_BILL_CONTROL_INSTALLED = YES
```

```
WAVE_J1 = PASS
WAVE_J2 = PASS
WAVE_J3 = PASS
WAVE_J4 = PASS
WAVE_J5 = PASS
WAVE_J6 = PASS
WAVE_J7 = PASS
WAVE_J8 = PASS
```

J3b requirió `-u account` (no `-u all`) para alinear vistas Community nightly
con core 20260324 (`is_exact_move_duplicate`). J7d requirió `pyqrcode` +
`xmltodict` en la imagen `doralex-odoo-enterprise:19.0.20260324` (nunca
`odoo:19`). Firma e-CF: `signxml==3.2.2` (compatible cryptography 41). No se
envió nada a DGII. No se consumieron secuencias NCF reales.

## Baseline y personalizaciones Doralex

```
QWEB_BEFORE = 58
QWEB_AFTER = 58
QWEB_HASH_MISMATCH_UNEXPECTED = 0
REPORTS_PRESERVED = YES
justech_alexander_reports = 19.0.3.8.5
ALEXANDER_REPORTS_ACTION = PRESERVE_DORALEX
DORALEX_MAIL_CONFIG_PRESERVED = YES
DORALEX_CONFIG_PRESERVED = YES
DORALEX_COMPANIES_PRESERVED = YES
DORALEX_USERS_PRESERVED = YES
DORALEX_SYSTEM_PARAMETERS_PRESERVED = YES
DORALEX_ACCOUNTING_CONFIG_PRESERVED = YES
DORALEX_FISCAL_CONFIG_PRESERVED = YES
MAIL_SAFE_MODE = YES
```

SMTP staging: `neutralization - disable emails` / `invalid:1025`.
`web.base.url` = `https://enterprise.doralexgroup.cloud`.
`mail.catchall.domain` = `doralexgroup.cloud`.
Usuarios = 8, compañías = 7 (nombres Doralex). Parámetros nuevos solo de
módulos instalados.

## Imagen y staging (127.0.0.1:8269)

```
DORALEX_RUNTIME_IMAGE = doralex-odoo-enterprise:19.0.20260324
WEB_ENTERPRISE_INSTALLED = YES
ODOO_VERSION = 19.0+e-20260324
ODOO_EDITION = Enterprise
STAGING_LOGIN = PASS
STAGING_HEALTH = PASS
ENTERPRISE_UI = PASS
SPANISH_UI = PASS
PUBLIC_LOGIN_SPANISH = PASS
PDF_QUOTATION = PASS
PDF_SALE_ORDER = PASS
PDF_INVOICE = PASS
```

PDFs Alexander: cotización BLUE ELITE, pedido/factura INVERSIONES DORALEX,
ITBIS, NCF pendiente (sin consumir secuencia). Layout/header/footer Doralex.

Login público: «Iniciar sesión» / «Contraseña». Website `default_lang_id` =
`es_DO`. Admin y `dx.test.security@justech.do` en `es_DO`.

Prod/Dev siguen en `odoo:19`. El tag `odoo:19` no se retocó.

```
DORALEX_SUBSCRIPTION_ACTIVATION = PENDING
JUSTGROUP_DATA_COPIED = NO
JUSTGROUP_SUBSCRIPTION_COPIED = NO
JUSTGROUP_PROD_TOUCHED = NO
DORALEX_PROD_TOUCHED = NO
CUTOVER_ALLOWED = NO
```

## QA funcional final pre-cutover (solo staging)

```
FINAL_QA_BACKUP = PASS
APP_LAUNCHER_QA = PASS
FISCAL_UI = PASS
NCF_ENGINE = PASS
ECF_ENGINE = PASS
DGII_OUTBOUND = DISABLED/SAFE
ACCOUNTING_QA = PASS
SALES_QA = PASS
PURCHASE_QA = PASS
TRACEABILITY_QA = PASS
MARGIN_CONTROL_QA = PASS
CXP_QA = PASS
APPROVAL_QA = PASS
WARRANTY_QA = PASS
AUDIT_QA = PASS
VENDOR_BILL_CONTROL_QA = PASS
DGCP_BRIDGE_QA = PASS
MANAGED_SERVICES_QA = PASS
ENTERPRISE_APPS_QA = FAIL
REPORT_QA = PASS
MAIL_QA = PASS
SPANISH_UI_FINAL = PASS
SECURITY_QA = PASS
MULTICOMPANY_QA = PASS
QWEB_BEFORE = 58
QWEB_AFTER = 58
QWEB_HASH_MISMATCH_UNEXPECTED = 0
REPORTS_PRESERVED = YES
CRITICAL_ERRORS = 0
HIGH_ERRORS = 0
READY_FOR_CUTOVER_REVIEW = NO
DORALEX_SUBSCRIPTION_ACTIVATION = PENDING
DORALEX_PROD_TOUCHED = NO
CUTOVER_ALLOWED = NO
```

`ENTERPRISE_APPS_QA = FAIL`: no se instalaron a ciegas `documents`, `sign`,
`planning`, `sale_renting`, `web_studio`. Helpdesk y Suscripciones sí abren.

Caso margen UI: `DOR/SO/00013` venta 400 / costo 240 / margen 160 (40%)
vinculado a `DOR/OC/00012`. Aprobación: `DOR/SO/00015` Aprobada.
Auditoría: logs de `res.partner.phone` con usuario/fecha/valor anterior-nuevo.
NCF no consumido. DGII no enviado. SMTP neutralizado.

Evidencia: `docs/enterprise_conversion/evidence/wave4_justech_custom_stack_20260829.txt`
Evidencia QA: `docs/enterprise_conversion/evidence/wave5_final_functional_qa_20260830.txt`
