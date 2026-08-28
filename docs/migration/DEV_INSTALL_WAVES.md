# Doralex DEV — Instalación por olas (WAVE A/B/C)

> Actualizado: 2026-08-27. Fuente: **vendored snapshot**
> `addons/vendor/odoo-custom-addons/` regenerado desde
> `faustosantana/odoo-custom-addons` (SoT). Target: **Doralex DEV** only.
> PROD **no** tocado. Sin `-u all`. Sin datos reales de Justech/Doralex.

## Delivery (Cloud Agent)

Cursor Cloud no puede leer el repo privado canónico. Consume únicamente:

```
addons/vendor/odoo-custom-addons/
```

Regenerar (máquina local con acceso a ambos repos):

```bash
bash tools/sync_odoo_custom_addons_vendor.sh
```

Provenance: `ORIGIN_REF.json` + `WAVES.json`.

## WAVE A — Community-safe (código listo para DEV)

| Módulo |
|--------|
| `bi_convert_purchase_from_sales` |
| `justech_approval_flow` |
| `justech_core` |
| `justech_global_audit_log` |
| `justech_purchase_sale_margin_control` |
| `justech_quotation_client_dedup` |
| `justech_report_identity_guard` |
| `justech_sale_purchase_trace` |
| `justech_sale_terms_guard` |
| `justech_warranty` |
| `l10n_do_accounting` |
| `multi_invoice_manual_payment_prod` |

`WAVE_A_READY = YES` (código completo en vendor; instalación dirigida en DEV pendiente de operador).

## WAVE B — Requiere adaptación fiscal/config (código vendorizado)

| Módulo | Nota |
|--------|------|
| `justech_accounting_recovery` | Adaptar a compañías Doralex |
| `justech_admin_center` | Plataforma admin; adaptar secretos vía env |
| `justech_fiscal_admin` | Fiscal DO — adaptar |
| `justech_l10n_do_adel_freeze` | Freeze fiscal |
| `justech_l10n_do_base` | Base l10n DO |
| `justech_l10n_do_ncf` | NCF |
| `justech_modules` | Catálogo módulos Justech |
| `justech_vendor_bill_po_control` | Vendor bill ↔ PO |

`WAVE_B_READY = PARTIAL` (código presente; no instalar en masa sin adaptar compañías/fiscal).

## WAVE C — Enterprise-blocked (solo en canónico)

`justech_l10n_do_payments_withholding`, `justech_l10n_do_reports`,
`justech_l10n_do_treasury`, payroll suite (`justech_l10n_do_hr_payroll*`),
`studio_hotfix`.

`ENTERPRISE_BLOCKED = 11` — no vendorizados en AlexanderGroup.

## NOT_APPLICABLE

DGCP / ECF / managed_services / mail policy / recurring_fee / `justech_security_ux`
(depende ECF). Permanecen en canónico; no Wave A/B.

## addons_path (DEV)

```
/mnt/enterprise,/mnt/custom-addons,/mnt/vendor/custom/justech,/mnt/vendor/third_party
```

## Reglas

Sin `-u all`; instalación dirigida; Justgroup PROD y Doralex PROD intactos;
sin carga de datos reales todavía → `READY_FOR_FULL_DORALEX_DATA_LOAD = NO`.
