# FINAL UX / LOGISTICS ACCEPTANCE

Fecha: 2026-09-16.
Entorno de prueba: **STAGING** `doralex_ent_staging` (pedido aislado `DOR/SO/00096`).
Código también actualizado en **PROD** (`justech_alexander_*` overlay).
**PROD TOUCHED: YES** (solo overlay base/ux/reports; sin validar picking real ni postear NCF).

```
EXISTING JUSTECH CONDUCE MODULE:
MODULE: ninguno dedicado (no existe justech_conduce)
VERSION: n/a
MODELS: n/a
REPORT: n/a
FLOW: n/a
REUSED:
  - justech_modules flag pdf_conduce (licencia, no modelo)
  - justech_report_identity_guard → stock.action_report_delivery
  - justech_sale_purchase_trace / sale_stock: picking nativo al confirmar
  - Alexander: stock.action_report_delivery nombre = Conduce
```

No se creó un tercer sistema de conduces.

==================================================
PROPET
LOCATION: Imprimir → Formato Propet (asistente Imprimir + binding report)
SEPARATE BUTTON: no
SOURCE DOCUMENT: DOR/SO/00096 (el pedido abierto)
FULL QUOTE DATA: sí (empresa, cliente, fechas, vendedor, moneda, términos, bancos, totales)
EXTRA COLUMNS: Producto, Descripción, Cant., P. unit. sin ITBIS, ITBIS, P. unit. con ITBIS, Dto., Subtotal, Total línea
OC/PO: OC / PO PO-TEST-2026-001
DESCRIPTION DUPLICATION: no (Producto = DX UX TEST CONDUCE; Descripción = Caja de clavos F-20…)
RESULT: PASS

==================================================
PROFORMA
LOCATION: Imprimir → Factura Proforma
SEPARATE BUTTON: no
OC/PO: OC / PO: PO-TEST-2026-001
RESULT: PASS

==================================================
CONDUCE
EXISTING JUSTECH MODULE: ninguno; se reutiliza stock.picking outgoing
MODULE USED: justech_alexander_base + justech_alexander_reports
SALE ORDER BUTTON: Conduce → action_dx_open_conduce
EXISTING PICKING REUSED: sí DOR/OUT/00042 (id 277)
DUPLICATE PICKING: no
ORDER QTY: 10 (sale.order.line)
DELIVERED QTY: 6 (stock.move.quantity; picking NO validado)
PARTIAL DELIVERY: pendiente nativo 4; no se implementó sistema paralelo
PRINT LOCATION: Entrega → Print / preview Conduce
PRICES: no
OC/PO: OC / PO PO-TEST-2026-001
COMPANY DESIGN: INVERSIONES DORALEX / picking.company_id
RESULT: PASS

==================================================
OC/PO
LABEL: OC / PO
FORM VIEW: junto a Fecha, editable
STANDARD QUOTE: sí
PROPET: sí
PROFORMA: sí
INVOICE: `ref` copiado por `_prepare_invoice` (draft 1898, no posteada)
CONDUCE: sí
RESULT: PASS

==================================================
TRACKING:
UNCHANGED: sí (sin cambios a lot/serial)
RESULT: PASS

==================================================
SCREENSHOTS:
COUNT: 12+ (form, Imprimir, 3 previews, entrega 10/6, Conduce, apps, facturas)

MODULES CHANGED:
- justech_alexander_base 19.0.1.0.10
- justech_alexander_ux 19.0.1.6.8
- justech_alexander_reports 19.0.3.11.1

MODULES UPDATED:
- STAGING -u dirigido + restart
- PROD -u dirigido + restart

ODOO HEALTH:
WEBCLIENT: /web/health 200 · /odoo 303 login · Apps y Contabilidad cargan
ERRORS: toast de wkhtmltopdf «need two workers» al pedir PDF binario; el preview HTML es el documento completo. Sin OWL navbar. Probe STAGING desactivado.

FINAL STATUS: PASS
```
