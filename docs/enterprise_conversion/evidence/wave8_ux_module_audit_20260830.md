# Auditoría UX — módulos custom Doralex (staging)

Fecha: 2026-08-30.
Ámbito: `doralex_ent_staging` en `127.0.0.1:8269`.
Producción: no tocada.

## Resumen

| Métrica | Antes | Después |
|---|---|---|
| CUSTOM_APPLICATION_TRUE | 8 | 5 |
| CUSTOM_ROOT_MENUS | 7 | 6 |
| DGII_ROOT_APP | YES | NO |
| INSTALLED_MODULES | 371 | 372 (+`justech_alexander_ux`) |
| UNINSTALL_COUNT | — | 0 |
| QWEB justech_alexander% | 58 | 58 |
| HASH_MISMATCH | — | 0 |

Apps custom visibles después:

- Administración Doralex
- Aprobaciones
- Costos y Márgenes
- Garantías
- Servicios Administrados

## Clasificación

Leyenda: A USER_APPLICATION · B FEATURE_MODULE · C TECHNICAL_DEPENDENCY · D SECURITY/GUARD · E REPORTING_ENGINE · F INTEGRATION · G LOCALIZATION/FISCAL_ENGINE · H UI/OVERLAY · I DORALEX_SPECIFIC

| technical_name | display_name (después) | version | installed | application_before | application_after | class | parent_functional_area | root_menu | visible_launcher | technical_only |
|---|---|---|---|---|---|---|---|---|---|---|
| justech_alexander_admin | Administración Doralex | 19.0.1.0.1 | yes | True | True | A / I | Administración | Administración Doralex | yes | no |
| justech_approval_flow | Aprobaciones | 19.0.1.3.8 | yes | True | True | A | Compras/Ventas | Aprobaciones | yes | no |
| justech_managed_services | Servicios Administrados | 19.0.2.1.3 | yes | True | True | A | Operaciones | Servicios Administrados | yes | no |
| justech_purchase_sale_margin_control | Costos y Márgenes | 19.0.8.29.38 | yes | True | True | A | Compras/Ventas | Costos y Márgenes | yes | no |
| justech_warranty | Garantías | 19.0.1.9.1 | yes | True | True | A | Ventas | Garantías | yes | no |
| justech_global_audit_log | Auditoría | 19.0.4.1.4 | yes | False | False | B | Auditoría | Auditoría de Cambios | yes (menú, no app) | no |
| justech_alexander_website | Sitio web institucional | 19.0.1.0.8 | yes | True | False | H / I | Sitio web | (usa Sitio web) | no | no |
| justech_fiscal_admin | Administración Fiscal | 19.0.1.10.0 | yes | True | False | G | Fiscal | legacy inactivo | no | no |
| l10n_do_ecf_connector | Conector e-CF DGII | 19.0.4.0.0 | yes | True | False | F / G | Fiscal | DGII (hijo) | no | no |
| justech_alexander_base | Identidad Doralex | 19.0.1.0.4 | yes | False | False | I | Identidad | — | no | no |
| justech_alexander_reports | Diseño de reportes Doralex | 19.0.3.8.5 | yes | False | False | E / I | Reportes | — | no | no |
| justech_alexander_microsoft_mail | Correo Microsoft | 19.0.1.0.4 | yes | False | False | F / I | Correo | — | no | no |
| justech_alexander_ux | Experiencia Doralex (menús) | 19.0.1.0.1 | yes | — | False | H / I | UX | — | no | yes |
| justech_core | Utilidades internas | 19.0.1.0.0 | yes | False | False | C | Plataforma | — | no | yes |
| justech_modules | Registro de módulos | 19.0.1.8.7 | yes | False | False | C | Plataforma | — | no | yes |
| justech_admin_center | Centro de administración técnica | 19.0.2.12.1 | yes | False | False | C | Ajustes | Administración técnica | no | yes |
| justech_security_ux | Permisos y seguridad | 19.0.4.1.9 | yes | False | False | D | Seguridad | — | no | yes |
| justech_mail_outgoing_policy | Política de correo saliente | 19.0.1.2.0 | yes | False | False | D | Correo | — | no | yes |
| justech_report_identity_guard | Identidad de reportes | 19.0.1.0.0 | yes | False | False | D | Reportes | — | no | yes |
| justech_sale_terms_guard | Términos de venta por compañía | 19.0.1.0.0 | yes | False | False | D | Ventas | — | no | yes |
| justech_quotation_client_dedup | Evitar clientes duplicados en cotización | 19.0.1.0.0 | yes | False | False | D | Ventas | — | no | yes |
| justech_l10n_do_adel_freeze | Candado de motor fiscal | 19.0.1.0.0 | yes | False | False | D / G | Fiscal | — | no | yes |
| justech_l10n_do_base | Base fiscal dominicana | 19.0.1.27.1 | yes | False | False | G | Fiscal | Fiscal Dominicana | no | no |
| justech_l10n_do_ncf | NCF | 19.0.2.31.0 | yes | False | False | G | Fiscal | NCF | no | no |
| justech_ecf_core | e-CF | 19.0.1.2.1 | yes | False | False | G | Fiscal | e-CF | no | no |
| justech_ecf_xml | e-CF XML | 19.0.1.0.0 | yes | False | False | G | Fiscal | — | no | yes |
| justech_ecf_signature | e-CF firma | 19.0.1.1.0 | yes | False | False | G | Fiscal | — | no | yes |
| justech_ecf_queue | e-CF cola | 19.0.1.0.0 | yes | False | False | G | Fiscal | — | no | yes |
| justech_ecf_dgii | e-CF DGII | 19.0.1.0.0 | yes | False | False | F / G | Fiscal | — | no | yes |
| justech_ecf_admin | Administración e-CF | 19.0.1.3.0 | yes | False | False | G | Fiscal | bajo e-CF | no | no |
| l10n_do_ecf_connector_receptor | Recepción e-CF proveedor | 19.0.1.0.0 | yes | False | False | F | Fiscal | — | no | no |
| justech_l10n_do_reports | Reportes fiscales | 19.0.1.24.8 | yes | False | False | E / G | Fiscal | Reportes fiscales | no | no |
| justech_l10n_do_payments_withholding | Pagos y retenciones | 19.0.1.7.2 | yes | False | False | G | Fiscal | bajo Reportes fiscales | no | no |
| justech_l10n_do_treasury | Tesorería | 19.0.1.6.7 | yes | False | False | B | Contabilidad | Pagos (Contabilidad) | no | no |
| justech_accounting_recovery | Recuperación contable | 19.0.1.4.0 | yes | False | False | B | Contabilidad | — | no | no |
| justech_l10n_do_hr_payroll | Nómina | 19.0.1.38.0 | yes | False | False | B | RRHH | Nómina bajo RRHH | no | no |
| justech_l10n_do_hr_payroll_account | Nómina — contabilidad | 19.0.1.9.0 | yes | False | False | B | RRHH | bajo RRHH | no | no |
| justech_l10n_do_hr_payroll_attendance | Nómina — asistencia | 19.0.1.15.0 | yes | False | False | B | RRHH | bajo RRHH | no | no |
| justech_l10n_do_hr_payroll_bank | Nómina — pagos bancarios | 19.0.1.8.0 | yes | False | False | B | RRHH | bajo RRHH | no | no |
| justech_l10n_do_hr_payroll_holidays | Nómina — ausencias | 19.0.1.15.0 | yes | False | False | B | RRHH | bajo RRHH | no | no |
| justech_l10n_do_hr_payroll_reports | Nómina — TSS/DGII | 19.0.1.4.0 | yes | False | False | E / B | RRHH | bajo RRHH | no | no |
| justech_l10n_do_hr_payroll_subsidies | Nómina — subsidios | 19.0.1.14.0 | yes | False | False | B | RRHH | bajo RRHH | no | no |
| justech_dgcp_bridge | Puente DGCP | 19.0.1.3.1 | yes | False | False | F | Integraciones | — | no | yes |
| justech_sale_purchase_trace | Trazabilidad ventas/compras | 19.0.1.2.11 | yes | False | False | B | Compras/Ventas | — | no | no |
| justech_vendor_bill_po_control | Control de facturas proveedor / OC | 19.0.3.6.2 | yes | False | False | B | Compras | — | no | no |
| justech_recurring_fee | Fees recurrentes | 19.0.1.2.0 | yes | False | False | B | Servicios | — | no | no |
| studio_hotfix | Corrección Studio | 19.0.1.0.2 | yes | False | False | C | Studio | — | no | yes |
| l10n_do_accounting | Contabilidad fiscal (Rep. Dominicana) | 19.0.1.0.1 | yes | False | False | G | Fiscal (histórico Adel) | — | no | yes |
| multi_invoice_manual_payment_prod | Pago manual de varias facturas | 19.0.1.5.4 | yes | False | False | B | Contabilidad | — | no | no |
| bi_convert_purchase_from_sales | Crear compra desde venta | 19.0.0.0 | yes | False | False | B | Compras | — | no | no |

`TOTAL_CUSTOM_MODULES = 49` (+ overlay = 50 filas; 49 preexistentes + ux).

## Application=True: ¿merecía ser app?

| módulo | antes | decisión | motivo |
|---|---|---|---|
| justech_alexander_admin | True | KEEP | Área operativa de administración Doralex |
| justech_approval_flow | True | KEEP | Bandeja de aprobaciones independiente |
| justech_managed_services | True | KEEP | Operación de servicios administrados |
| justech_purchase_sale_margin_control | True | KEEP | Área de costos y márgenes |
| justech_warranty | True | KEEP | Ciclo de garantías / RMA |
| justech_alexander_website | True | FALSE | Overlay/theme del Sitio web |
| justech_fiscal_admin | True | FALSE | Consola fiscal; menú legacy inactivo; vive en Fiscal |
| l10n_do_ecf_connector | True | FALSE | Cliente DGII; no es área de trabajo propia |

## Propuesta CURRENT → PROPOSED (apps / roots)

| CURRENT_APP | TECHNICAL_MODULE | CURRENT_ROOT_MENU | PROPOSED_VISIBLE_APP | PROPOSED_PARENT | APPLICATION_BEFORE | APPLICATION_AFTER | USER_IMPACT | RISK |
|---|---|---|---|---|---|---|---|---|
| Administración Doralex | justech_alexander_admin | Administración Doralex | Administración Doralex | (raíz) | True | True | ninguno | bajo |
| Aprobaciones | justech_approval_flow | Aprobaciones | Aprobaciones | (raíz) | True | True | nombre más corto | bajo |
| Servicios Administrados | justech_managed_services | Servicios Administrados | Servicios Administrados | (raíz) | True | True | ninguno | bajo |
| Costos y Márgenes | justech_purchase_sale_margin_control | Costos y Márgenes | Costos y Márgenes | (raíz) | True | True | ninguno | bajo |
| Justech Garantías | justech_warranty | Justech Garantías | Garantías | (raíz) | True | True | tile sin Justech | bajo |
| Doralex Website Institucional | justech_alexander_website | — | (ninguna) | Sitio web | True | False | desaparece del catálogo Apps | bajo |
| Justech Fiscal Administration Center | justech_fiscal_admin | Centro Fiscal (legacy, inactivo) | (ninguna) | Contabilidad → Fiscal | True | False | no era usable como app | bajo |
| DGII | l10n_do_ecf_connector | DGII (raíz) | (ninguna) | Contabilidad → Fiscal Dominicana → DGII | True | False | tile DGII desaparece; menú se conserva | medio (menú movido) |
| Auditoría Fiscal | justech_l10n_do_reports | Auditoría Fiscal bajo Contabilidad | (ninguna) | Fiscal Dominicana → Reportes fiscales | False | False | un clic más dentro de Fiscal | bajo |
| e-CF | justech_ecf_core | e-CF bajo Facturación Community | (ninguna) | Fiscal Dominicana → e-CF | False | False | deja Invoicing inactivo | medio (menú movido) |
| Nómina * | justech_l10n_do_hr_payroll* | ya bajo RRHH | (ninguna) | RRHH → Nómina / … | False | False | ya estaba integrado | nulo |

## Nueva jerarquía fiscal

```
Contabilidad
  └─ Fiscal Dominicana
       ├─ Centro de regularización fiscal
       ├─ Documentos pendientes de regularización
       ├─ NCF
       ├─ Compras
       ├─ e-CF
       │    ├─ Recepciones
       │    └─ Claves API
       ├─ DGII
       └─ Reportes fiscales   (antes: Auditoría Fiscal, hermano de Contabilidad)
            ├─ Dashboard Fiscal
            ├─ 606 / 607 / 608 / 609 / 623
            ├─ Consumo NCF / Anulados
            ├─ Administrar Retenciones
            └─ Centro de Administración Fiscal
Contabilidad
  └─ Pagos                    (tesorería operativa; se deja aquí a propósito)
```

Nómina (sin cambio de parent):

```
RRHH
  ├─ Nómina
  ├─ Tiempo y Ausencias
  ├─ Finanzas / Pagos bancarios
  ├─ Cumplimiento (TSS/DGII)
  └─ Configuración (contabilidad de nómina, subsidios, bancos)
```

## Redundancias (solo reporte; no fusionar)

| MODULE_A | MODULE_B | OVERLAP | DEPENDENTS | DATA_MODELS | MIGRATION_RISK | RECOMMENDATION |
|---|---|---|---|---|---|---|
| justech_ecf_* (core/xml/signature/queue/dgii/admin) | l10n_do_ecf_connector (+receptor) | dos stacks e-CF (Justech + NETVUX) | fiscal, invoices | justech_ecf_document vs ecf_document | alto | no fusionar; UX ya los junta bajo Fiscal → e-CF / DGII |
| justech_l10n_do_ncf | l10n_do_accounting (Adel) | dos motores NCF; freeze ya bloquea Adel | facturación | justech_do_ncf_range vs Adel sequences | alto | no fusionar; `adel_freeze` se queda técnico |
| justech_fiscal_admin | justech_l10n_do_reports (Centro de Administración Fiscal) | consola fiscal duplicada en menú | fiscal users | flags / health vs audit center | medio | no fusionar; menú legacy fiscal_admin ya inactivo |
| justech_approval_flow | approvals (Enterprise) | dos bandejas «Aprobaciones» | compras/ventas | justech_approval_request vs approval.request | alto | no fusionar; Justech es el flujo OC/SO/factura |
| justech_admin_center | justech_alexander_admin | dos consolas de administración | settings | productos Justech vs dashboard Doralex | medio | no fusionar; admin_center queda en Ajustes |
| justech_global_audit_log | justech_admin_center audit | logs de cambio | — | justech_audit_log vs justech_admin_audit_log | medio | no fusionar |

## Qué queda como app / qué pasa a técnico

Apps (5): Administración Doralex, Aprobaciones, Costos y Márgenes, Garantías, Servicios Administrados.

Technical/feature (resto): motor fiscal, e-CF piezas, guards, reporting, website overlay, nómina addons, integraciones, core/modules.

## No hecho (fase posterior)

- No se desinstaló nada.
- No se renombraron technical names.
- No se tocó producción.
- No se fusionó código e-CF / NCF / approvals.
- Tesorería «Pagos» sigue bajo Contabilidad (uso diario CxC/CxP), no se enterró en Fiscal.
