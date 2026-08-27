# Reporte de implementación — 19.0.3.0.0

Módulo: `justech_purchase_sale_margin_control`
Versión: **19.0.3.0.0** (extiende 19.0.2.0.0; no elimina funcionalidad existente)

## Requerimiento 1 — Múltiples órdenes de compra en una operación

| Pieza | Implementación |
|---|---|
| Asistente | `wizard/add_purchase_wizard.py`: `purchase.sale.add.purchase.wizard` + `purchase.sale.add.purchase.wizard.line` |
| Vistas | `wizard/add_purchase_wizard_views.xml` |
| Contexto | `transaction_id`, `sale_order_id` (crea/encuentra operación) o `customer_invoice_id` (crea/encuentra operación) |
| Auto-carga | `_onchange_purchase_order_ids` reconstruye `line_ids` desde `purchase.order.line` (sin tipeo manual) |
| Disponibilidad | `qty_available` = cantidad de la línea de OC menos lo ya asignado como línea estimada (`purchase.sale.margin.transaction.line.purchase_order_line_id`) en **otras** operaciones |
| Validaciones | compañía, OC cancelada, sobre-asignación (`qty_to_assign > disponible`) |
| Resultado | Líneas `purchase.sale.margin.transaction.line` (`data_origin=estimated`, `line_type=cost`) prorateadas por cantidad; asignación de costo sugerida (`purchase.sale.cost.allocation`, `state=suggested`) cuando hay una venta única identificable; facturas de proveedor ya generadas por las OC se adjuntan a `vendor_bill_ids`; `message_post` de auditoría |
| Botones | `purchase.sale.margin.transaction.action_add_purchase_orders` / `action_recompute_costs`; `sale.order.action_add_purchase_orders`; `account.move.action_add_purchase_orders` (solo facturas de cliente) |
| Modelo extendido | `models/margin_transaction_line.py`: se agregan `purchase_order_line_id` y `quantity` (campos nuevos, no rompen nada existente) |

## Requerimiento 2 — Auxiliar de Cuentas por Pagar por operación

| Pieza | Implementación |
|---|---|
| Modelo | `models/payable_auxiliary.py`: `purchase.sale.payable.auxiliary` (1 registro por factura de proveedor, control operativo, nunca contable) |
| Asistente de relación | `wizard/relate_sale_wizard.py`: `purchase.sale.relate.sale.wizard` (N:N con operaciones / OV / facturas de cliente) |
| Auto-creación | `account.move._ensure_payable_auxiliary()`, llamado desde `action_post()` solo para `in_invoice`/`in_refund`; nunca altera montos contables |
| Botones en factura de proveedor | "Ver auxiliar CxP", "Relacionar ventas", "Clasificar costos" |
| Estado operativo | `operational_state` (pendiente de relación → relación parcial → relación completa → facturado a cliente → pendiente de cobro → pendiente de pago a proveedor → pagada parcial/pagada → cerrada manualmente) |
| Menús | "Auxiliar de Cuentas por Pagar" con vistas filtradas: Pendientes de relación, Pendientes de facturar, Pendientes de pago, Pagadas, Cerradas, Diferencias, Sin venta relacionada |
| KPIs del tablero | `models/margin_board.py`: `purchases_recovered_amount/count`, `purchases_pending_recovery(_count)`, `purchases_pending_payment_count`, `purchases_without_sale_aux_count`, `cost_recovery_percent`, `committed_vendor_flow`, con botones de drill-down a `purchase.sale.payable.auxiliary` |
| Reporte XLSX | `report/payable_auxiliary_xlsx.py` (mismo patrón que `report/cost_vs_sale_xlsx.py`), columnas en español |
| Seguridad | ACL en `security/ir.model.access.csv`; reglas multi-compañía en `security/margin_security.xml` (mismos grupos/`privilege_id` existentes) |
| Cron | `data/ir_cron.xml`: refresco diario opcional (`active=False` por defecto) vía `purchase.sale.payable.auxiliary.cron_refresh_all()` |

## Pruebas

`tests/test_margin_enhancement_3.py` cubre: múltiples OC (operación/OV/factura), auto-carga sin tipeo manual, asignación parcial y disponibilidad remanente, bloqueo de sobre-asignación, bloqueo multi-compañía, bloqueo de OC cancelada, bloqueo de reutilización de una línea ya agotada, factura de proveedor relacionada con múltiples ventas, una venta relacionada con múltiples facturas de proveedor, recuperación de costo parcial/total, transiciones de estado operativo, KPIs del tablero y restricciones multi-compañía. Las pruebas existentes (`test_margin_control.py`, `test_margin_transaction_2.py`) no se modifican y siguen funcionando sin cambios.

## Notas de diseño

- **Nunca se duplica el costo**: al agregar una OC vía el asistente, la escritura de `purchase_order_ids` usa `skip_line_sync=True` para evitar que el sincronizador genérico (`_sync_lines_from_documents`) cree una línea de "OC completa" además de la línea prorateada por cantidad que crea el asistente.
- **NCF con fallback seguro**: `ncf_number` intenta `l10n_do_fiscal_number`, luego `l10n_latam_document_number` (nombre real usado en `justech_l10n_do_ncf`), luego `ref`, siempre con `getattr` defensivo para no romper instalaciones sin esos campos.
- **Auxiliar CxP es 100% operativo**: nunca escribe `amount_residual`, `payment_state` ni ningún asiento; esos campos son `related` de solo lectura hacia `account.move`.
