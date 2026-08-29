# Compras / CxP QA

## Flujo 6/6

RFQ `DX TEST RFQ/PO {CCC}` (PDF SOLICITUD / OC) → confirm PO → recepción → vendor bill recibida → pago.

Vendor NCF LATAM `B01992xxxxx` + `justech_do_expense_type_id` código 09 (requerido para 606).

## bi_convert_purchase_from_sales

Wizard `create.purchaseorder` desde cotización DOR: creó OC (`DOR/OC/00004` y posteriores draft por re-runs). PASS. Traza = `origin` del SO, no el módulo de margen.

## Varias PO por venta

Sin `justech_purchase_sale_margin_control`. NOT_IMPLEMENTED.

## Vendor bill PO control

NOT_INSTALLED.
