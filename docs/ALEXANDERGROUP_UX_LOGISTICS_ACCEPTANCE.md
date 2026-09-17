# FINAL UX / LOGISTICS ACCEPTANCE

Fecha: 2026-09-17.
Entorno de prueba: **PROD** `doralex_prod` (túnel 127.0.0.1:18069).
**PROD TOUCHED: YES** (overlay `justech_alexander_reports` 19.0.3.11.4 + `-u` dirigido; sin `-u all`; frozen intactos).

```
PROPET MENU NAME: Formato Propet (solo Imprimir)
PROPET HEADER BUTTON: no
QUOTE PDF TITLE: PEDIDO DE VENTA (MAY/SO/00007 está confirmado; draft PIN/SO/00007 = COTIZACIÓN)
QUOTE PDF NUMBER: MAY/SO/00007
INVOICE PDF TITLE: FACTURA
INVOICE PDF NUMBER: Pendiente (draft 143 sin secuencia; posted INV/2026/00021 = FACTURA)
PROFORMA PDF TITLE: FACTURA PROFORMA
OC/PO: OC / PO (visible; MAY/SO/00007 = PO-CLIENTE-2026-001)

CONDUCE BUTTON: sí (abre picking; no imprime)
OLD ACTION 1853: no existe
PICKING OPEN: sí DOR/OUT/00015 (también MAY/OUT/00003)
CONDUCE PRINT: sí desde la entrega
ORDER QTY: 5
DELIVERED QTY: 5
PRICES SHOWN: no

MODULES CHANGED:
- justech_alexander_base 19.0.1.0.11 (sin cambio en este paso)
- justech_alexander_ux 19.0.1.6.8 (sin cambio)
- justech_alexander_reports 19.0.3.11.4

PROD HEALTH: doralex-production-odoo healthy; frozen 19.0.1.7.2 / 19.0.1.5.4 / 19.0.8.29.38 / 19.0.1.2.11

FINAL STATUS: PASS
```
