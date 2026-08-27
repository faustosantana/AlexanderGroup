# Doralex DEV — Wave A/B instaladas desde el snapshot vendorizado

> Fecha: 2026-08-27. Fuente: `addons/vendor/odoo-custom-addons/` (snapshot del SoT
> `faustosantana/odoo-custom-addons`, canónico `12458c0`, tag `doralex-wave-ab-2026-08-27`).
> **No** se editó el código vendorizado. PROD intacto. Sin datos de Justech.

## Sincronización

- `DORALEX_VENDOR_SNAPSHOT = PASS`: 20 módulos completos (12 Wave A + 8 Wave B),
  0 archivos `data/` faltantes, 0 basura `._*`. Copiados a `/opt/doralex/dev/custom-addons`
  (flat) con permisos legibles por el contenedor. `addons_path` de DEV resuelve
  `/mnt/custom-addons`. Backup previo: `dev_20260827_183205` (verificado).

## WAVE A — `WAVE_A_INSTALL = PASS` (12/12)

`bi_convert_purchase_from_sales`, `justech_approval_flow`, `justech_core`,
`justech_global_audit_log`, `justech_purchase_sale_margin_control`,
`justech_quotation_client_dedup`, `justech_report_identity_guard`,
`justech_sale_purchase_trace`, `justech_sale_terms_guard`, `justech_warranty`,
`l10n_do_accounting`, `multi_invoice_manual_payment_prod` → **installed**.

## WAVE B — clasificación e instalación

`WAVE_B_CLASSIFICATION = PASS`:

| Módulo | Clasificación | Resultado |
| ------ | ------------- | --------- |
| `justech_modules` | INSTALLABLE_AS_IS (infra: provee `justech.license.service`, requerido por los `post_init` hooks del ecosistema justech_*) | installed |
| `justech_l10n_do_base` | INSTALLABLE_AS_IS (localización RD base) | installed |
| `justech_l10n_do_ncf` | INSTALLABLE_AS_IS (stack NCF) | installed |
| `justech_vendor_bill_po_control` | INSTALLABLE_AS_IS | installed |
| `justech_l10n_do_adel_freeze` | INSTALLABLE_AS_IS | installed |
| `justech_fiscal_admin` | INSTALLABLE_AS_IS (ajustes fiscales) | installed |
| `justech_accounting_recovery` | INSTALLABLE_AS_IS | installed (previo) |
| `justech_admin_center` | **NOT_APPLICABLE_TO_DORALEX** (consola admin/licencias SaaS de Justech; sin valor de negocio para Doralex) | no instalado |

`WAVE_B_INSTALL = PARTIAL` por diseño: **7/8 instalados**; `admin_center` descartado
como NOT_APPLICABLE.

## WAVE C — `ENTERPRISE_BLOCKED = 11`

Payroll RD (×7), `justech_l10n_do_payments_withholding`, `justech_l10n_do_reports`,
`justech_l10n_do_treasury`, `studio_hotfix`. **No** vendorizados, **no** instalados.
Requieren licencia Enterprise legítima de Doralex.

## Hallazgo técnico (dependencia oculta)

Varios `justech_*` usan un `post_init_hook` (`register_from_manifest_hook`) que
requiere el modelo `justech.license.service` (de `justech_modules`), **no** declarado
en `depends`. Se resolvió instalando `justech_modules` primero (infra). Cambio
recomendado para el **SoT**: declarar `justech_modules` como dependencia explícita
de los módulos que usan el hook (no se edita el vendor aquí).

## Adaptaciones / hardcodes

No se editó el código vendorizado (política: overlay/patch/config fuera del vendor).
Los módulos instalaron **as-is** en DEV (base vacía, sin datos Justech). Hardcodes
de tipo dominio/email/URL detectados por `scan_module_hygiene.py` son **parámetros
de configuración** (system params) que se fijarán con valores de Doralex en la carga
de datos; **no** son literales de credencial (secrets scan = 0). Documentados para
parametrizar/llevar al SoT. `HARDCODES_CORRECTED = 0` (por política de no editar vendor).

## Tests (0 FAIL / 0 ERROR / 0 CRITICAL)

- repo tests: **15/15**
- golden env: **9/9** (multiempresa, ventas, compras, factura, inventario, CRM)
- six-company: **6/6** (aislamiento, diario/secuencia/almacén por compañía)
- runtime errors DEV: **0**; `dev /web/health` = 200 (healthy)

Evidencia: [`evidence/dev_wave_ab_final.txt`](evidence/dev_wave_ab_final.txt).

## Estado

`WAVE_A_INSTALL = PASS` · `WAVE_B_CLASSIFICATION = PASS` · `WAVE_B_INSTALL = PARTIAL`
(7/8; 1 NOT_APPLICABLE) · `ENTERPRISE_BLOCKED = 11` · `MULTICOMPANY_SCAN = PASS` ·
`DORALEX_DEV_RUNTIME_ERRORS = 0`. PROD intacto; sin cargar datos reales.
