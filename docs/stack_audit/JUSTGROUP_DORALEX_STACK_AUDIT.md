# Auditoría Justgroup → Doralex (stack funcional)

**Fecha:** 2026-08-29  
**Corte:** inventario obligatorio. **Sin cutover. Sin upgrade in-place. Justgroup no se tocó.**

```
DORALEX_CLONE_STATUS            = REJECTED
JUSTGROUP_SOURCE_OF_TRUTH       = YES
JUSTGROUP_PROD_WRITE_ALLOWED    = NO
JUSTGROUP_PRODUCTION_TOUCHED    = NO
DORALEX_REPORTS_MUST_BE_PRESERVED = YES
DORALEX_REPORTS_PRESERVED       = YES
TRANSACTION_COPY_ALLOWED        = NO
JUSTGROUP_TRANSACTIONS_COPIED   = NO
SPANISH_ONLY_UI                 = FAIL (solo en_US)
CUTOVER_ALLOWED                 = NO
AUDIT_REQUIRED                  = DONE (esta entrega)
```

Comparador: `python3 tools/justgroup_doralex_stack_compare.py`  
(opcional `--live` para revalidar `common.version` público).

---

## Entregable corto (10 puntos)

### 1. Versión real de Odoo en Justgroup

`19.0+e-20260324` — **Enterprise** (`server_version_info[5] = "e"`).

Fuente viva 2026-08-29 (JSON-RPC público, sin login):

- `https://justgroup.app`
- `https://erp.justech.do` (misma build)

Inventario SSH 2026-08-27 (solo lectura): DB `justech`, PostgreSQL **16.15**, 360 módulos, addons `community + enterprise + /usr/lib/odoo/custom-addons`.

### 2. Versión real de Odoo en Doralex

`19.0-20260817` — **Community** (edition vacía). Imagen Docker `odoo:19`.

- PROD `https://doralexgroup.cloud` y DEV `https://dev.doralexgroup.cloud` = misma build.
- Python **3.12.3**, PostgreSQL **16.15**, wkhtmltopdf **0.12.6.1** (patched qt).
- `addons_path = /mnt/enterprise,/mnt/custom-addons`
- `/opt/doralex/enterprise` vacío (`ENTERPRISE_SOURCE_PENDING=TRUE`).

Misma **serie** (19.0). **No** es la misma edición ni el mismo build operativo.

### 3. Cantidad de módulos instalados

| Sitio | Instalados | Notas |
| --- | ---: | --- |
| Justgroup | **360** | Community 173 / Enterprise 142 / Justech custom 41 (auditoría SSH 2026-08-27) |
| Doralex PROD | **106** | Shell `ir.module.module` 2026-08-29 |

Lista Justgroup **completa** de 360 nombres: **no viva hoy**. Falta `~/.ssh/justgroup_vps_ed25519` en este agente (`Permission denied`). El conteo 360 y el desglose sí están verificados en la auditoría SSH previa.

### 4. Módulos faltantes (Doralex vs Justgroup)

**Enterprise (UX Justgroup; en Doralex `uninstallable` o ausentes de la imagen Community):**

`account_accountant`, `approvals`, `documents`, `helpdesk`, `industry_fsm`, `planning`, `sale_renting`, `sale_subscription`, `sign`, `stock_barcode`, `timesheet_grid`, `web_studio`, `knowledge`, `marketing_automation`.

Eso explica Documentos, Firma, Soporte, Suscripciones, Alquiler, Planeación, Servicio externo, Aprobaciones nativas, Contabilidad completa vs “Invoicing”.

**Community presentes en Justgroup / no instalados en Doralex PROD:**

`project`, `hr`, `hr_holidays`, `hr_timesheet`, `maintenance`, `repair`, `survey`, `event`, `mass_mailing`, `im_livechat`, `base_automation`, `fleet`, `mrp`, `board`.

**Custom Justech instalados en Justgroup y ausentes en Doralex:**

`justech_approval_flow`, `justech_purchase_sale_margin_control`, `justech_sale_purchase_trace`, `justech_vendor_bill_po_control`, `multi_invoice_manual_payment_prod`, `justech_sale_terms_guard`, `justech_quotation_client_dedup`, `justech_admin_center`, `justech_l10n_do_adel_freeze`, `justech_security_ux`, `justech_mail_outgoing_policy`, `justech_recurring_fee`, más e-CF / payroll / `studio_hotfix` y el resto del cupo de 41.

**Custom con dependencia Enterprise (no instalables hoy):**

`justech_l10n_do_payments_withholding`, `justech_l10n_do_reports`, `justech_l10n_do_treasury`.

### 5. Módulos con versiones distintas

En el subconjunto **custom que sí está instalado en ambos**, las versiones coinciden (`justech_l10n_do_ncf` 19.0.2.31.0, `justech_l10n_do_base` 19.0.1.27.1, `justech_warranty` 19.0.1.9.1, etc.).

El mismatch crítico no es de parche custom: es **Community 19.0-20260817 vs Enterprise 19.0+e-20260324**.

### 6. Módulos custom faltantes

Ver §4. En PROD hay **14** `justech_*` instalados (incluidos 5 `justech_alexander_*` de identidad Doralex). Justgroup tiene **41** custom Justech. Código de varios faltantes ya está en `addons/vendor/odoo-custom-addons/` pero **no** está instalado (freeze previo + falta de Enterprise).

### 7. Dónde están los reportes Doralex

Tres copias, ninguna es Justgroup:

1. **Git:** `addons/alexander/justech_alexander_reports` (V5.3 / `19.0.3.8.5`) — XML de layout, headers 6 empresas, inherits de cotización/factura/OC/picking, paperformat, estados de cuenta, garantías.
2. **PROD DB:** 58 vistas QWeb `justech_alexander_*` + 48 `ir.actions.report` + paperformats (xml_id del módulo; no Studio).
3. **Disco PROD:** `/opt/doralex/production/custom-addons/justech_alexander_reports/`.

No hay vistas Studio (`web_studio` = uninstallable, `studio_views = 0`).

### 8. ¿Los reportes están seguros?

**Sí, para no destruirlos.** No se reinstaló Odoo ni se tocó el módulo.

Backup fresco (solo lectura + dump):

`/opt/doralex/backups/production/production_20260829_120319`

- `db.dump` sha256 `cfaa2bb21c899235ff7fa32a54577eeacdb938a8a3752be0c4ceedec1d146d73`
- `filestore.tar.gz` sha256 `549e1257b1000a245fb05c26eeef64aa9d854ab4cf2940e8fa5fcbce3be58245`
- `custom-addons.tar.gz` + `doralex_reports_xml/` + nginx

Backup 360 previo: `production_20260829_112927`.

**Riesgo residual:** un upgrade/reinstall a ciegas del core o `-u all` puede reescribir QWeb. Por eso **no** se hace cutover aquí.

### 9. Estrategia recomendada

**Rebuild paralelo (`DORALEX_NEW` / staging). No upgrade destructivo in-place.**

1. Contratar **licencia Enterprise propia de Doralex** (no copiar addons Enterprise de Justgroup).
2. Levantar instancia staging con build **19.0+e** alineada a Justgroup (`19.0+e-20260324` o la misma revisión oficial que se fije).
3. Instalar el catálogo extraído de Justgroup (export vivo `ir.module.module` cuando exista SSH/export).
4. Reaplicar identidad Doralex: 6 empresas, Graph mail, `justech_alexander_reports`, NCF Doralex.
5. Español `es_DO` (y/o `es_ES` + términos RD).
6. Datos Doralex limpios (sin transacciones Justgroup). Limpiar QA `DX TEST` en un paso aparte.
7. QA del comparador = todos PASS → cutover DNS/proxy.

Instalar solo Community extra (`hr`, `project`, …) **no** cumple el objetivo: la UI Enterprise y ~142 módulos seguirían faltando.

### 10. Riesgos

| Riesgo | Severidad | Mitigación |
| --- | --- | --- |
| Sin fuente Enterprise legítima | **BLOCKER** | `ENTERPRISE_SOURCE_PENDING`. Copiar el árbol de Justgroup viola licencia. |
| Upgrade Community → Enterprise sobre la misma DB | **CRITICAL** | Puede romper QWeb/filestore. Staging primero. |
| Lista Justgroup 360 no reexportada hoy | **HIGH** | Pedir llave SSH solo lectura o CSV de `ir.module.module`. |
| QA `DX TEST` + rangos NCF TEST aún en PROD | **HIGH** | No son Justgroup; limpiar en un run autorizado, no en este cutover. |
| Personalizaciones Studio de Justgroup | **MED** | Studio no se copió (correcto). Recrear en código, no clonar DB. |
| Custom Justech con hardcodes de dominio/email | **MED** | Adaptar a Doralex; no copiar RNC/bancos/secuencias Justech. |
| Módulos frozen en justgroup.app | **MED** | No instalar/actualizar esos cuatro en Justgroup. En Doralex, instalar **réplicas** adaptadas cuando el staging lo permita. |
| UI en inglés | **MED** | Causa actual: único idioma `en_US`. No parchear core; instalar i18n. |

---

## Por qué se ve “otra generación”

No es Odoo 18. Es **Odoo 19 Community** (build 17 ago) frente a **Odoo 19 Enterprise** (build 24 mar). El app switcher Community no incluye Documentos, Firma, Helpdesk, Suscripciones, Alquiler, Planeación, Contabilidad completa ni Studio. Los menús salen en inglés porque **no hay idioma español instalado**.

Aplicaciones instaladas hoy en Doralex PROD: Invoicing, Calendar, Contacts, CRM, Discuss, Purchase, Sales, Inventory, Website, Administración Doralex, Fiscal Admin, Garantías.

---

## Qué se replicó / qué no

| Debe replicarse | Estado |
| --- | --- |
| Código / arquitectura / fiscal Community | Parcial (motor NCF + reportes Doralex) |
| Catálogo Enterprise | **BLOQUEADO** |
| Identidad Doralex (logo, RNC, bancos, Graph) | Conservar; no sustituir por Justech |
| Transacciones Justgroup | **No copiadas** (correcto) |
| Justgroup PROD | **No escrito** |

---

## Condiciones para continuar (después de este inventario)

No se ejecuta corrección de stack en PROD en este turno.

Para desbloquear staging:

1. Suscripción + fuente Enterprise 19 de **Doralex**.
2. Export read-only de módulos Justgroup (SSH o CSV).
3. Confirmación de levantar `DORALEX_NEW` (no reciclar el contenedor actual).

Hasta entonces: `CUTOVER_ALLOWED = NO`.
