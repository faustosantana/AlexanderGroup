# FINAL UX / LOGISTICS ACCEPTANCE

Fecha: 2026-09-16
Rama: `cursor/doralex-ux-logistics-86c5`

## EXISTING JUSTECH CONDUCE MODULE

```
EXISTING JUSTECH CONDUCE MODULE:
MODULE: ninguno dedicado (`justech_conduce` no existe)
VERSION: n/a
MODELS: n/a
REPORT: n/a
FLOW: n/a
REUSED:
  - justech_modules licencia `pdf_conduce` (flag, no modelo)
  - justech_report_identity_guard protege `stock.action_report_delivery`
  - justech_sale_purchase_trace: Delivery nativo al confirmar
  - Alexander overlay: `stock.action_report_delivery` nombre = Conduce
  - Odoo nativo: sale.order → stock.picking outgoing
```

No se creó un tercer sistema de conduces.

## Código (pre-browser)

PROPET
LOCATION: Imprimir → Formato Propet (`ir.actions.report` binding)
SEPARATE BUTTON: eliminado
SOURCE DOCUMENT: el `sale.order` / `account.move` desde el que se imprime
FULL QUOTE DATA: compose nativo + columnas fiscales
EXTRA COLUMNS: producto, desc, cant, P. unit. sin ITBIS, ITBIS, P. unit. con ITBIS, dto, subtotal, total
OC/PO: label corto, solo si hay valor
DESCRIPTION DUPLICATION: `propet_display_texts` (solo presentación)
RESULT: CODE READY — pendiente prueba de navegador

PROFORMA
LOCATION: Imprimir → Factura Proforma
SEPARATE BUTTON: eliminado
OC/PO: mismo campo `client_order_ref`
RESULT: CODE READY — pendiente prueba de navegador

CONDUCE
EXISTING JUSTECH MODULE: ninguno; se reutiliza picking nativo + reporte Alexander
MODULE USED: `justech_alexander_base` + `justech_alexander_reports`
SALE ORDER BUTTON: `Crear Conduce` / `Conduce` → `action_dx_open_conduce`
EXISTING PICKING REUSED: sí (filtra outgoing no cancelados)
DUPLICATE PICKING: no; solo `_action_launch_stock_rule` nativo si falta
ORDER QTY: `sale.order.line.product_uom_qty`
DELIVERED QTY: `stock.move.quantity`
PARTIAL DELIVERY: backorder nativo de Odoo
PRINT LOCATION: Entrega → Imprimir → Conduce
PRICES: no en plantilla de picking
OC/PO: desde `sale_id.client_order_ref` si tiene valor
COMPANY DESIGN: `picking.company_id` vía `_render_qweb_pdf`
RESULT: CODE READY — pendiente prueba de navegador

OC/PO
LABEL: OC / PO
FORM VIEW: junto a Cliente (`client_order_ref`)
STANDARD QUOTE / PROPET / PROFORMA / INVOICE / CONDUCE: sí si tiene valor
RESULT: CODE READY — pendiente prueba de navegador

TRACKING:
UNCHANGED: sí (sin cambios a lot/serial UI)
RESULT: PASS (no tocado)

SCREENSHOTS:
COUNT: 0 (pendiente navegador)

MODULES CHANGED:
- justech_alexander_base 19.0.1.0.10
- justech_alexander_ux 19.0.1.6.7
- justech_alexander_reports 19.0.3.11.0

MODULES UPDATED: pendiente `-u` dirigido

ODOO HEALTH: pendiente
WEBCLIENT: pendiente
ERRORS: pendiente

FINAL STATUS: PARTIAL (código + pytest 214; falta browser en instancia)
