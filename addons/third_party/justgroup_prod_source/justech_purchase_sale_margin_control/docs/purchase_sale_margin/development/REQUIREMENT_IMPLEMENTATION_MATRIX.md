# Matriz de implementación de requerimientos — 19.0.2.0.0

Módulo: `justech_purchase_sale_margin_control`
Versión: **19.0.2.0.0** (redesign: `purchase.sale.margin.transaction` como registro financiero principal)

| # | Requerimiento | Implementación | Estado |
|---|---|---|---|
| 1 | Modelo principal `purchase.sale.margin.transaction` | `models/margin_transaction.py` (mail.thread/activity.mixin, secuencia `MTX/%(year)s/`, montos calculados desde `line_ids`) | ✅ |
| 2 | Modelo de líneas `purchase.sale.margin.transaction.line` | `models/margin_transaction_line.py` (sale/cost, origen contable/manual/estimado) | ✅ |
| 3 | Eliminar el `TransientModel` modal como dashboard principal | `models/margin_dashboard.py` y `views/dashboard_views.xml` eliminados; reemplazados por `purchase.sale.margin.board` (`target=current`, página completa) | ✅ |
| 4 | Contexto de compañía corregido | `company_id` en el board es opcional (no forzado); alcance = `self.env.companies` cuando está vacío; nunca compañías fuera de las permitidas (`_get_scope_companies`) | ✅ |
| 5 | Ventas sin costo no cuentan como margen confirmado | `sale_without_cost` + `margin_is_calculable` (False cuando no hay costo real); KPI `confirmed_real_margin` filtra por `margin_is_calculable=True` | ✅ |
| 6 | Mantener `cost.link` / `cost.allocation` / `margin.snapshot` / `reconciliation.rule` | Sin cambios de ruptura; `cost_allocation` extendido con `transaction_id` para sincronizar líneas | ✅ |
| 7 | Mantener servicios `trace_engine`, `margin_service`, `classification_service` | Sin cambios; siguen usados por `sale.order`/`purchase.order` y el snapshot histórico | ✅ |
| 8 | Mejorar asistentes allocate/prorate/backfill | `backfill_wizard.py` ahora detecta y crea operaciones (`detected`/`pending_review`, nunca aprobadas) y reporta ventas sin costo, compras sin venta, candidatos admin/inventario | ✅ |
| 9 | Nuevos asistentes de registro manual | `wizard/register_cost_wizard.py`, `wizard/register_sale_wizard.py`, `wizard/create_transaction_wizard.py` (no crean asientos contables) | ✅ |
| 10 | Vistas y menús rediseñados | `views/margin_transaction_views.xml`, `views/margin_board_views.xml`, `views/menus.xml` reescrito con la estructura solicitada | ✅ |
| 11 | Botones en `account.move` / `sale.order` / `purchase.order` | "Crear/vincular operación de margen" y "Ver operación" agregados a los tres modelos | ✅ |
| 12 | Reporte XLSX línea por relación en español | `report/cost_vs_sale_xlsx.py` reescrito sobre `purchase.sale.margin.transaction` con columnas en español | ✅ |
| 13 | Seguridad para modelos nuevos | ACL en `security/ir.model.access.csv`, reglas multi-compañía y de alcance en `security/margin_security.xml` (mismos grupos y `privilege_id` existentes) | ✅ |
| 14 | Pruebas ampliadas | `tests/test_margin_control.py` (sin romper) + `tests/test_margin_transaction_2.py` (nuevo, cobertura completa de la 2.0.0) | ✅ |
| 15 | Manifiesto 19.0.2.0.0 | `__manifest__.py` actualizado con la nueva versión y lista de datos | ✅ |

## Notas de diseño

- **Fuente única de verdad de montos**: todos los montos de una operación se calculan exclusivamente
  a partir de `line_ids` (líneas de venta/costo), que se sincronizan automáticamente desde los
  documentos relacionados (`sale_order_ids`, `purchase_order_ids`, facturas) y desde las
  asignaciones de costo existentes (`purchase.sale.cost.allocation.transaction_id`).
- **Base sin ITBIS**: se mantiene la regla de auditoría heredada de 1.x: los montos base nunca
  incluyen impuestos.
- **Nunca aprobar automáticamente**: tanto el backfill como la detección automática solo crean
  operaciones en estado `detected` o `pending_review`; la validación (Compras) y aprobación
  (Finanzas) son siempre pasos humanos explícitos.
