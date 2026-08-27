# ROLE_MAPPING — capa UX → res.groups

Fuente de verdad: `res.groups`. La UI solo sincroniza estos XMLIDs.

## Categorías de responsabilidad

| Categoría UX | Roles (tarjetas) | Grupos |
|---|---|---|
| Comercial | Usuario propios / Usuario todos / Administrador | `sales_team.group_sale_salesman` → `group_sale_salesman_all_leads` → `group_sale_manager` |
| Compras | Usuario / Administrador | `purchase.group_purchase_user` → `purchase.group_purchase_manager` |
| Inventario | Usuario / Administrador | `stock.group_stock_user` → `stock.group_stock_manager` |
| Finanzas | Facturación / Contable / Administrador | `account.group_account_invoice` → `account.group_account_user` → `account.group_account_manager` |
| Contabilidad | Solo lectura / Operativo / Administrador | `account.group_account_readonly` → `account.group_account_user` → `account.group_account_manager` |
| Fiscal | Usuario / Responsable / Administrador | `justech_l10n_do_base.group_justech_do_fiscal_user` → `...fiscal_manager` → `justech_fiscal_admin.group_justech_fiscal_admin_manager` |
| e-CF | Lectura / Operador / Responsable / Administrador | `group_ecf_readonly` → `operator` → `responsible` → `admin` |
| Garantías | Usuario / Responsable | `justech_warranty.group_warranty_user` → `group_warranty_manager` |
| Recursos Humanos | Encargado / Administrador | `hr.group_hr_user` → `hr.group_hr_manager` |
| CRM | (flag leads) | `crm.group_use_lead` (+ ventas) |
| Administración Justech | Usuario consola / Administrador | `justech_admin_center.group_justech_admin_center_user` → `...manager` |

## Permisos operativos (acciones) → grupos

| Acción UX | Grupo |
|---|---|
| Registrar/aplicar cobros-pagos | `account.group_account_invoice` |
| Conciliar / desconciliar | `account.group_account_user` |
| Aprobar/eliminar pagos (nivel admin) | `account.group_account_manager` |
| Validar bancos | `account.group_validate_bank_account` |
| Crear/confirmar ventas | `sales_team.group_sale_salesman` (+ niveles) |
| Descuentos en línea | `sale.group_discount_per_so_line` |
| Nota de crédito fiscal | `l10n_do_accounting.group_l10n_do_fiscal_credit_note` |
| Cancelar factura fiscal | `l10n_do_accounting.group_l10n_do_fiscal_invoice_cancel` |
| Compras usuario/admin | `purchase.group_purchase_user` / `manager` |
| Documentos recibidos/emitidos | fiscal_user / fiscal_manager |
| Anular NCF | `justech_l10n_do_base.group_justech_do_fiscal_manager` |
| Reportes 606/607/608 | `justech_l10n_do_base.group_justech_do_fiscal_user` |
| Rangos / tipos / DGII admin | `justech_fiscal_admin.group_justech_fiscal_admin_manager` |
| e-CF administrar | `justech_ecf_core.group_ecf_admin` |
| Garantías crear/editar | `justech_warranty.group_warranty_user` |
| Garantías aprobar/admin | `justech_warranty.group_warranty_manager` |
| Inventario movimientos | `stock.group_stock_user` / `manager` |

## Reglas

1. No se crean grupos nuevos en esta capa.
2. No se tocan ACL ni Record Rules.
3. La sincronización solo agrega/quita grupos del catálogo gestionado.
4. Grupos no gestionados (Marketing, Sitio Web, etc.) quedan intactos y solo visibles en Permisos Avanzados.
