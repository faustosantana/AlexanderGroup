# Matriz módulo → niveles → grupos

Fuente: `models/modules_registry.py` · solo xmlids reales.

| Módulo | Nivel UI | xmlids |
|---|---|---|
| Ventas | Sin acceso | — |
| Ventas | Usuario propios | `sales_team.group_sale_salesman` |
| Ventas | Usuario todos | `sales_team.group_sale_salesman_all_leads` |
| Ventas | Administrador | `sales_team.group_sale_manager` |
| Ventas / cap | Descuentos | `sale.group_discount_per_so_line` |
| Ventas / cap | NC fiscal | `l10n_do_accounting.group_l10n_do_fiscal_credit_note` |
| Ventas / cap | Cancelar fiscal | `l10n_do_accounting.group_l10n_do_fiscal_invoice_cancel` |
| Compras | Usuario / Admin | `purchase.group_purchase_user` / `purchase.group_purchase_manager` |
| Inventario | Usuario / Admin | `stock.group_stock_user` / `stock.group_stock_manager` |
| Inventario / cap | Lotes | `stock.group_production_lot` |
| Contabilidad | Facturación | `account.group_account_invoice` |
| Contabilidad | Contabilidad | `account.group_account_user` |
| Contabilidad | Administrador | `account.group_account_manager` |
| Fiscal DO | Usuario / Responsable / Admin | `justech_* fiscal` groups |
| Pagos | Facturación+pagos | `account.group_account_invoice` (sin segregación fina) |
| Pagos | Banco | `account.group_validate_bank_account` |
| Retenciones | Catálogo | `justech_l10n_do_payments_withholding.group_justech_withholding_catalog_admin` |
| e-CF | readonly→admin + auditor | `justech_ecf_core.group_ecf_*` |
| Garantías | user / manager | `justech_warranty.group_warranty_*` |
| Fees | user / manager | `justech_recurring_fee.group_recurring_fee_*` |
| CRM | Leads flag | `crm.group_use_lead` |
| RRHH | Encargado / Admin | `hr.group_hr_user` / `hr.group_hr_manager` |
| Admin Justech | user / manager | `justech_admin_center.group_*` |
