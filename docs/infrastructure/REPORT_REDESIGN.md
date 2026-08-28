# Rediseño de reportes A4 — Doralex DEV

Fecha: 2026-08-28. Solo **DEV**. **PROD no se tocó** (container start `2026-08-27T20:12:21Z`).

## Inventario de reportes en DEV (47 QWeb PDF)

Cliente / operación (rediseñados vía layout + CSS + herencias, sin rebindar acciones oficiales):

- Cotización / pedido / proforma (`sale.report_saleorder`, `sale.report_saleorder_pro_forma`)
- Factura / NC (`account.report_invoice`, `account.report_invoice_with_payments` + `l10n_do_accounting`)
- RFQ / orden de compra
- Recibo de pago
- Estado de cuenta (`justech_alexander_reports.report_partner_statement_document`)
- Garantía (`justech.warranty`)
- Delivery / picking / recepción / return slip

No se rebindan acciones oficiales (`justech_report_identity_guard`).

Etiquetas de producto, badges HR, márgenes/CxP landscape: fuera del estándar comercial A4.

## Justgroup (solo lectura)

Revisado en `addons/vendor/odoo-custom-addons/`:

- `justech_report_identity_guard` — obliga plantillas core, bloquea Hellenia / `justech_report_design`
- `l10n_do_accounting/views/report_invoice.xml` — RNC, NCF, NCF modificado, moneda, cliente
- `multi_invoice_manual_payment_prod` — documentos aplicados en recibo

No se copió Hellenia. Se reutilizó: NCF/RNC, banco por `company_id`, firma en blanco, tablas core.

## Arquitectura

`justech_alexander_reports` 19.0.2.1.0

- `web.external_layout` fuerza `o.company_id` / `doc.company_id` (campos, no compañía activa)
- layout `external_layout_doralex` + clase `dx-theme-{DOR|PIN|DOM|MAY|REM|BLU}`
- CSS modular wkhtmltopdf-safe
- extras por modo: `customer` | `purchase` | `payment` | `stock` | `signs`
- `_render_qweb_pdf` aplica `with_company(document.company_id)` y `lang` del partner

## COMPANY_DATA_MISSING

- website: las 6 empresas
- `dx_report_terms` / `invoice_terms`: las 6

No inventados. Bancos Banreservas sí existen por empresa.

## Criterios

```
QUOTATION_REPORT = PASS
SALE_ORDER_REPORT = PASS
INVOICE_REPORT = PASS (borrador; NCF pendiente de rangos reales)
CREDIT_NOTE_REPORT = PASS
PURCHASE_ORDER_REPORT = PASS
PAYMENT_RECEIPT_REPORT = PASS
STATEMENT_REPORT = PASS
DELIVERY_REPORT = PASS
MULTICOMPANY_REPORT_ISOLATION = PASS
PDF_RENDER = PASS
PNG_PREVIEW_GENERATION = PASS
VISUAL_AUDIT = PASS
PRINT_READABILITY = PASS
BLACK_WHITE_READABILITY = PASS
EMAIL_PDF_COMPANY_MATCH = PASS
PROD_UNTOUCHED = YES
REPORT_SUITE_COMPLETE = YES
READY_FOR_REPORTS_PRODUCTION = NO
```

READY_FOR_REPORTS_PRODUCTION = NO hasta NCF reales, términos comerciales cargados y websites si se desean en el pie.

Galería: [`docs/report_previews/index.html`](../report_previews/index.html)
