# Ventas / CRM QA

## Flujo 6/6

Cotización `DX TEST COTIZACION {CCC}` → confirm → entrega → factura B01 → PDF → pago parcial → pago total → NC B04 → estado de cuenta.

Cliente exclusivo `DX TEST CLIENTE {CCC}` (RNC 10199xxxx). Productos `DX-TEST-EQP`, `DX-TEST-SVC` (dto 10%), `DX-TEST-STK`.

Factura TEST enviada solo a `fausto@justech.do` con subject `[DX TEST][NO FISCAL REAL][NO ENVIAR DGII]`. FROM `administracion@` del dominio de la empresa. 6/6.

## Estado de cuenta

PDF `justech_alexander_reports.action_report_partner_statement` 6/6. Casos: factura vencida + NC + pagos + (DOR) anticipo.

## CRM

Lead `DX TEST LEAD DOR` → opportunity (`convert_opportunity` con partner record). PASS.

## Términos / dedup

Módulos no instalados. Términos de compañía siguen EMPTY (no inventados).
