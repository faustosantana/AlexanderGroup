# Alexander Group / Doralex — Precheck READ-ONLY

Fecha: 2026-09-16.
Alcance: inventario técnico y diagnóstico de los 17 hallazgos de la reunión
de entrenamiento. **Sin escrituras en PROD. Sin cambios de datos en esta
fase.** Fuente viva: STAGING (`doralex_ent_staging`) vía `ssh doralex-server`.
DEV (`doralex_dev`) se confirma como entorno hermano; el stack operativo
Enterprise vive en STAGING.

PROD no se consultó en escritura ni se modificó. `PROD TOUCHED: NO`.

## 1. Entornos

| | STAGING (trabajo) | DEV | PROD (intacto) |
| --- | --- | --- | --- |
| Contenedor | `doralex-enterprise-staging-odoo` | `doralex-dev-odoo` | `doralex-production-odoo` |
| Base | `doralex_ent_staging` | `doralex_dev` | `doralex_prod` |
| Estado | healthy (8 días) | healthy (2 semanas) | healthy (8 días) — **no tocar** |
| Dominio | staging interno | `dev.doralexgroup.cloud` | `doralexgroup.cloud` |

## 2. Plataforma (STAGING, leído en vivo)

| Dato | Valor |
| --- | --- |
| Odoo | **19.0+e-20260324** (Enterprise, `19.0-20260324`) |
| Edición | Enterprise (`+e`, addons `/usr/lib/odoo/enterprise`) |
| PostgreSQL | **16.15** (Debian 16.15-1.pgdg13+2) |
| Módulos instalados | 372 |
| Idiomas activos | `es_DO`, `en_US` |

### addons_path efectivo (contenedor STAGING)

1. `/usr/lib/python3/dist-packages/odoo/addons` — Community
2. `/var/lib/odoo/addons/19.0`
3. `/mnt/custom-addons` — overlay Justech + Alexander
4. `/usr/lib/odoo/enterprise` — Enterprise
5. `/usr/lib/odoo/custom-addons`
6. `/usr/lib/python3/dist-packages/addons`

DEV documentado: `/mnt/enterprise,/mnt/custom-addons`.

## 3. Empresas (multiempresa)

| ID | Nombre | RNC | Moneda | Correo |
| --- | --- | --- | --- | --- |
| 8 | BLUE ELITE, S.R.L. | 133371261 | DOP | administracion@blueelite.net |
| 9 | COMERCIALIZADORA DE ALIMENTOS PIÑARIA, S.R.L. | 132271068 | DOP | administracion@pinariagroup.com |
| 10 | DOMINION BUSINESS,S.R.L. | 132721502 | DOP | administracion@dominion-business.com |
| 11 | INVERSIONES DORALEX,S.RL. | 132220112 | DOP | administracion@inversionesdoralex.com |
| 12 | INVERSIONES EL MAYUMA, S.R.L. | 132710152 | DOP | administracion@elmayuma.com |
| 13 | REMPART GROUP S.R.L. | 132769155 | DOP | administracion@rempartgroup.com |
| 1 | Plantilla técnica (no operativa) | — | USD | — |

Nunca asumir `company_id=1` como empresa operativa.

## 4. Qué es nativo / custom / configuración

| Capa | Ejemplos |
| --- | --- |
| Nativo Community | `sale`, `purchase`, `stock`, `crm`, `mail`, `account` |
| Nativo Enterprise | `account_accountant`, `approvals`, `sale_enterprise`, `l10n_do`, `l10n_do_reports`, `microsoft_outlook` |
| Localización Indexa / DO | `l10n_do_accounting`, `l10n_do_ecf_connector` |
| Custom Justech (vendor) | `justech_l10n_do_*`, `justech_approval_flow`, `justech_sale_purchase_trace`, `justech_accounting_recovery`, `justech_l10n_do_payments_withholding` 19.0.1.7.2 |
| Overlay Alexander (este repo) | `justech_alexander_{base,admin,ux,reports,website,microsoft_mail}` |
| Configuración | impuestos, etapas CRM, cron padrón (inactivo), SMTP neutralizado en staging, firmas de usuario |

Módulos **congelados en PROD** (no se tocan aquí ni se despliegan):
`justech_l10n_do_payments_withholding` 19.0.1.7.2,
`multi_invoice_manual_payment_prod`,
`justech_purchase_sale_margin_control`,
`justech_sale_purchase_trace`.

## 5. Módulos por área (instalados en STAGING)

### Custom Alexander / Justech (extracto)

`justech_alexander_base` 19.0.1.0.5, `justech_alexander_admin` 19.0.1.0.1,
`justech_alexander_ux` 19.0.1.4.0, `justech_alexander_reports` 19.0.3.8.5,
`justech_alexander_microsoft_mail` 19.0.1.0.4, `justech_alexander_website` 19.0.1.0.8,
`justech_approval_flow` 19.0.1.3.8, `justech_accounting_recovery` 19.0.1.4.0,
`justech_sale_purchase_trace` 19.0.1.2.11, `justech_purchase_sale_margin_control` 19.0.8.29.39,
`justech_l10n_do_base` 19.0.1.27.1, `justech_l10n_do_ncf` 19.0.2.31.0,
`justech_l10n_do_payments_withholding` 19.0.1.7.2, `justech_l10n_do_reports` 19.0.1.24.8,
`justech_global_audit_log` 19.0.4.1.4, `justech_security_ux` 19.0.4.1.9.

### Fiscal / DO

`l10n_do` 19.0.2.0, `l10n_do_accounting` 19.0.1.0.1, `l10n_do_reports`,
`l10n_do_ecf_connector` 19.0.4.0.0, `justech_ecf_*`, `justech_fiscal_admin`.

### Ventas / compras / inventario / CRM / correo / website

Nativos + Enterprise (`sale_management`, `sale_stock`, `purchase`, `stock`,
`crm`, `mail`, `microsoft_outlook`, `website`). Aprobaciones nativas
`approvals` + custom `justech_approval_flow`.

## 6. Usuarios internos activos (STAGING)

| Login | Empresa activa | Notas de grupos |
| --- | --- | --- |
| `admin` | Blue Elite | Administrador amplio (contabilidad, aprobaciones, márgenes, traza) |
| `alexander.pina@…` | Doralex | Facturación + gerente contable + aprobador + márgenes |
| `fausto@justech.do` | Doralex | Gerente contable, fiscal, ventas, compras, inventario |
| `geilin.rosario@…` | Doralex | Facturación + ventas/compras/stock + márgenes |
| `elianny.sanchez@…`, `janny.montero@…`, `leopordo.jimenez@…`, `luis.aquino@…` | Doralex | Vendedor + compras + stock + márgenes (sin facturación) |
| `dx.test.security@justech.do` | Blue Elite | Solo `sales_team.group_sale_salesman_all_leads` |

Grupo `justech_accounting_recovery.group_accounting_recovery` existe y en STAGING
**no tiene ningún usuario**. Por eso el mensaje de recuperación aparece para
todos (incluido el flujo de cancelar/restablecer).
`sale.group_proforma_sales` existe y **tampoco tiene usuarios** (el print
nativo de proforma no se ofrece).

## 7. Diagnóstico por hallazgo (READ-ONLY)

### H01 — ITBIS 16 %

- Existe **16% ITBIS** en las 6 empresas operativas, pero solo como
  `type_tax_use=purchase` (compras).
- **No hay impuesto de venta 16%** en ninguna empresa operativa.
- Venta activa por empresa: 18% ITBIS, ITBIS Exempt, 10% Propina, 18% Restaurant, -5% ISR Gov.
- ~1607 productos por empresa usan **18% ITBIS** de venta.
- Precio no incluido (`price_include=False`).
- Localización: `l10n_do` + `l10n_do_accounting` + `justech_l10n_do_*`.
- **Causa raíz:** el 16% de la localización se cargó para compras, no para ventas.
- **Acción STAGING (post-precheck):** creados impuestos de venta «16% ITBIS»
  (ids 461–466) clonando el 18% de venta de cada empresa. Precio no incluido.
  No asignados a productos. No se tocaron facturas históricas.

### H02 — Descripciones de productos

- Campos nativos: `product.template.description_sale`, `sale.order.line.name`.
- No hay inherit Justech que escriba `sale.order.line.name`.
- Muestras recientes (líneas QA) coinciden producto ↔ `name`.
- `description_sale` es campo traducido JSON (Odoo 19); un cruce SQL ingenuo no aplica.
- **Hipótesis:** mezcla visual al cambiar producto en líneas OWL, o `description_sale` vacío / idioma `en_US` vs `es_DO`. No es un parche de PDF.
- **Acción:** aislar `name` por línea (producto propio; no reutilizar la de otra línea) + prueba de regresión. No reescribir líneas históricas.

### H03 — Formulario Propet

- No existe reporte extra. El estándar es `sale.action_report_saleorder` (PDF Quote), heredado por `justech_alexander_reports`.
- Campos nativos Odoo 19 en línea: `price_reduce_taxexcl`, `price_reduce_taxinc`, `price_tax`, `price_subtotal`, `price_total`.
- **Acción:** nuevo `ir.actions.report` opcional, no default.

### H04 — Columnas de compra en cotización

- **Causa raíz:** `justech_sale_purchase_trace` → `views/sale_order_views.xml` añade Comprado / Pend. compra / Pend. recibir / Abastecimiento (`optional="show"`) a todos los que ven el form de venta.
- El módulo está congelado en PROD. **No se edita.**
- **Acción:** vista heredada en `justech_alexander_ux` con `groups` de compras/traza. Los campos del modelo permanecen.

### H05 — Rastrear inventario

- Odoo 19: `type` es `consu`/`service`/`combo`; el almacenable es `is_storable` (True en productos de prueba, `tracking=none`).
- No hay vista custom Alexander que oculte `product.template.tracking`.
- **Causa raíz confirmada en STAGING:** `stock.view_template_property_form` muestra
  `tracking` con `groups="stock.group_production_lot"` e `invisible="not is_storable"`.
  Sin el ajuste nativo «Números de lote y serie», las opciones no cargan.
- **Acción:** quitar el `groups` en overlay (el campo sigue en el modelo) **o**
  activar el ajuste nativo. No inventar un flujo paralelo.

### H06 — CRM en inglés

- Etapas globales: `New`, `Qualified`, `Proposition`, `Won` (datos demo / core).
- Equipos: `Sales`, `Point of Sale`, `Website`.
- Overlay actual solo traduce menú Leads → Iniciativas (`spanish_ui.py`).
- **Causa raíz:** nombres de registros, no fallos de traducción de clientes.
- **Acción STAGING:** New→Nuevo, Qualified→Calificado, Proposition→Propuesta,
  Won→Ganado; equipo Sales→Ventas. No se tocaron oportunidades ni partners.

### H07 / H10 — Cancelar / restablecer / recuperación

- Mensaje «Debe pertenecer al grupo Recuperación Contable»: `justech_accounting_recovery` SoD.
- `button_cancel`, `button_draft`, `unlink` de `account.move` exigen ese grupo **también en borrador**.
- Distinción nativa/custom:
  - A) Borrador cancelar/borrar: nativo `account.group_account_invoice`; **hoy bloqueado** por recovery.
  - B) Publicada cancelar/revertir: `l10n_do_accounting.group_l10n_do_fiscal_invoice_cancel` + recovery / `justech_l10n_do_ncf.group_justech_reverse_invoice`.
  - C) Restablecer a borrador: recovery.
  - D) Recuperación contable: recovery.
- **No se da Admin.** Matriz mínima en el informe DEV. Cambio de SoD = **REQUIERE DECISIÓN**.

### H08 — Factura Proforma

- **Ya existe nativo:** `sale.action_report_pro_forma_invoice` / `sale.report_saleorder_pro_forma` («PRO-FORMA Invoice»).
- No crea asiento, no consume NCF (imprime `sale.order`).
- Grupo `sale.group_proforma_sales`.
- El inherit Doralex del QWeb de cotización también aplica; el título actual diría COTIZACIÓN si no se distingue el contexto proforma.
- **Acción:** reutilizar nativo, etiquetar «Factura Proforma», no default, identidad PROFORMA. No crear factura borrador.

### H09 — Padrón DGII

- Módulo: `justech_l10n_do_base`. Modelos: `justech.do.rnc.padron*`.
- Cron `Justech: actualizar padrón DGII` — **`active=False`** (data `noupdate`, cada 1 hora). `nextcall` 2026-08-29.
- Tabla `justech.do.rnc.padron`: **0 registros**. No hay `justech.do.rnc.padron.config`.
- **No se descarga ni se reemplaza nada en PROD.**
- **Causa raíz:** cron apagado + padrón vacío + sin configuración. La búsqueda por RNC no puede validar contra DGII.

### H11 — Aprobaciones de cotización (solo documentar)

Implementado en `justech_approval_flow` (no se cambia en esta fase):

1. Crear: vendedor (`sales_team.group_sale_salesman*`).
2. Modificar: mismo, mientras `draft`/`sent`.
3. Aprobar: `justech_approval_flow.group_approver` / manager; admin puede bypass.
4. Si una cotización aprobada se modifica en campos materiales, el fingerprint cambia y la solicitud pasa a **Invalidada**.
5. Sí pierde aprobación.
6. Debe aprobarse de nuevo (o confirmar con bypass de admin).
7. Disparan reaprobación: partner, moneda, líneas, qty, precio, descuento, impuestos, totales.
8. Auditoría: snapshot HTML + chatter + `justech.approval.request`.
9–10. Usuario/fecha en request y tracking.

`name` de línea **no** está en el fingerprint (solo producto/qty/precio/desc/tax).

### H12 — OC / PO del cliente

- Campo nativo `sale.order.client_order_ref` ya existe.
- El compose Doralex ya lo pasa como `client_ref` (etiqueta «Referencia»).
- **Acción:** reutilizar nativo; etiqueta «OC / PO del cliente»; visible en form, búsqueda y PDF. No copiar a otros campos.

### H13 — Retenciones y recibo

- `justech_l10n_do_payments_withholding` 19.0.1.7.2 (congelado).
- Campos en `account.payment`: `justech_withholding_line_ids`, `justech_withholding_total`, `justech_net_transfer`, `justech_applied_invoice_ids`, `justech_application_line_ids`.
- Recibo nativo `account.action_report_payment_receipt` ya listado por `justech_alexander_reports` (varias facturas + saldos).
- SMTP/staging no impide probar el PDF.
- **Acción:** incluir retenciones/neto en el compose del recibo (lectura). No asientos paralelos. No editar el módulo congelado.

### H14 — Conduces

- Flujo nativo: `stock.picking` + Delivery Slip / Picking, ya con branding por empresa (`_dx_picking_compose`).
- Título actual de salida: **ENTREGA**. Preview lo llama «Conduce / Delivery Slip».
- **Acción:** titular **CONDUCE** en entregas, logo/RNC/dirección de `company_id` del picking. No sistema paralelo.

### H15 — Correo

- STAGING: `ir.mail_server` = «neutralization - disable emails» / host `invalid` (intencional).
- `mail.catchall.domain` = `doralexgroup.cloud`. Sin fetchmail.
- 16 `mail.mail` en `exception`.
- 77 aliases. Overlay Microsoft: From = `administracion@` del dominio de la **empresa del documento**.
- **Acción:** no crear bridge. Hacer visibles los fallos (ya en `mail.mail`). Firmas → H16. No probar SMTP real contra PROD.

### H16 — Firmas por empresa

- `res.users.signature` es global (solo el nombre en `<div>`).
- No hay firma por empresa activa.
- **Causa raíz:** firma nativa de usuario, no aislada por `company_id` / `allowed_company_ids`.
- **Acción:** HTML de firma en `res.company` + composer usa la empresa del documento. Usuario multiempresa no filtra logo/teléfono ajeno.

### H17 — Navegación al dashboard

- Control: `justech_alexander_ux/static/src/navbar/navbar.xml` sobre `o_menu_toggle`.
- Se eliminó marca de app; el clic hace `this.hm.toggle(true)` (Home Menu Enterprise).
- No hay URL hardcodeada a doralexgroup.cloud.
- **Causa probable:** el usuario espera «Inicio» y el control no está etiquetado / `this.hm` frágil.
- **Acción:** mismo Home Menu nativo, `title` «Inicio», servicio `home_menu` si `this.hm` falta. Sin dominio hardcodeado.

## 8. Principios de implementación (post-precheck)

- Solo módulos `justech_alexander_*` (identificables, rollback = revertir versión).
- No editar vendor ni módulos congelados.
- No SQL sobre asientos, NCF, saldos, facturas publicadas.
- STAGING primero; PROD requiere autorización expresa.
- Preferir nativo (proforma, `client_order_ref`, delivery slip, impuestos `account.tax`).

## 9. Rollback de esta fase de diagnóstico

No hubo escrituras. Rollback = no aplicar el PR de hallazgos.

Scripts usados (solo lectura):

- `tools/alexander_training_findings/inventory_readonly.py`
- `tools/alexander_training_findings/findings_readonly.py`
- `tools/alexander_training_findings/run_readonly.sh staging|dev`

## 10. Evidencia

Inventario STAGING: generado 2026-09-16 contra `doralex_ent_staging`.
Odoo `19.0+e-20260324`, 372 módulos, 6 empresas operativas + plantilla.
