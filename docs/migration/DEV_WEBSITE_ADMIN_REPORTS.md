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
