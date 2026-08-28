# Doralex DEV — Website, organización, admin y reportes

> Fecha: 2026-08-28. Solo **DEV**. PROD intacto. Sin editar vendor.

## Módulos overlay (`addons/alexander/`)

| Módulo | Función |
| ------ | ------- |
| `justech_alexander_base` | Códigos DOR/PIN/DOM/MAY/REM/BLU, ficha pública, nomenclatura de almacenes/diarios/secuencias, campos legales internos |
| `justech_alexander_website` | Home institucional en `https://dev.doralexgroup.cloud/` — ERP en `/web` |
| `justech_alexander_admin` | Menú Administración Doralex; auth vía clave Justech (hash/env/`ir.config_parameter`/archivo) |
| `justech_alexander_reports` | Layout A4 único por `company_id` + vista previa sin NCF |

## Convención

| Código | Marca pública | Almacén |
| ------ | ------------- | ------- |
| DOR | Doralex | Almacén Principal |
| PIN | Piñaria | Almacén Principal |
| DOM | Dominion | Almacén Principal |
| MAY | El Mayuma | Almacén Principal |
| REM | Rempart | Almacén Principal |
| BLU | Blue Elite | Almacén Principal |

No se alteran RNC, impuestos, posiciones fiscales ni rangos NCF.

## Website (público)

Muestra: nombre comercial, logo, sector, descripción breve.
No muestra: RNC, bancos, saldos, representantes, cédulas, usuarios, datos fiscales.

Los logos se sirven en `/doralex/logo/<CODE>` (público, solo compañías publicadas).
No se usa `/web/image/res.company/<id>/logo` para visitantes anónimos, porque el
aislamiento multiempresa de Odoo devolvía un placeholder en 5 de 6 compañías.

El header/footer de Odoo Website (teléfono `+1 555…` y `yourcompany.example.com`)
se sustituyen por contacto de la compañía del website (DOR).

## Estado DEV 2026-08-28

| Indicador | Resultado |
| --------- | --------- |
| DORALEX_WEBSITE | PASS (DEV). PROD no se tocó |
| PUBLIC_COMPANY_PRESENTATION | PASS |
| CONFIDENTIAL_DATA_EXPOSURE | 0 |
| WAREHOUSE_ORGANIZATION | PASS |
| MULTICOMPANY_ORGANIZATION | PASS |
| MODULE_ADMIN_CENTER | PASS |
| MODULE_ADMIN_AUTH | PASS |
| REPORT_BASE_LAYOUT | PASS |
| QUOTATION_LAYOUT | PASS |
| SALE_ORDER_LAYOUT | PASS |
| INVOICE_LAYOUT | PASS |
| PURCHASE_ORDER_LAYOUT | PASS |
| DELIVERY_LAYOUT | PASS |
| PAYMENT_RECEIPT_LAYOUT | PASS |
| WARRANTY_LAYOUT | PASS |
| REPORT_PREVIEW | PASS |
| MULTICOMPANY_REPORT_IDENTITY | PASS |
| DORALEX_DEV_RUNTIME_ERRORS | 0 |

Pendiente fuera de este alcance: rangos NCF reales, roles de usuario por empresa, promoción del website a PROD.

## Auth admin

Reutiliza `justech.admin.access.service`. Complementa con:

- `ir.config_parameter` `doralex.admin_key_hash`
- env `DORALEX_ADMIN_KEY_HASH` / `JUSTECH_ADMIN_KEY_HASH`
- archivo `/opt/doralex/dev/secrets/doralex_admin_key.hash`

La clave nunca va a Git, logs ni UI.

## Reportes

`web.external_layout` → `justech_alexander_reports.external_layout_doralex` según compañía.
Acciones oficiales de impresión no se rebindan (respeta `justech_report_identity_guard`).
Preview: Administración Doralex → Diseñador / Vista previa.
