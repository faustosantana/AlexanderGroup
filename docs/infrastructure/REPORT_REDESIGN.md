# Rediseño de reportes A4 — Doralex DEV

Fecha: 2026-08-28. Solo **DEV**. **PROD no se tocó** (container start `2026-08-27T20:12:21.681221743Z`).

```
REPORT_DESIGN_V1 = REJECTED
DORALEX_DESIGN_V2_CHECKPOINT = PENDING
REPORT_SUITE_COMPLETE = NO
PROD_UNTOUCHED = YES
READY_FOR_REPORTS_PRODUCTION = NO
```

Los scores 8.8–9.3 de V1 son **inválidos**. PDF_RENDER=PASS no implica DESIGN=PASS.

## Arquitectura V2

Separación:

- A. Motor de datos / multiempresa (`document.company_id`, NCF, bancos, logos, `administracion@`)
- B. Componentes visuales (`reports/components.xml`)
- C. Tema por empresa (paleta extraída del logo)
- D. Composición por tipo de documento

Módulo `justech_alexander_reports` **19.0.3.0.0**.

Paperformat compacto: `margin_top=32`, `header_spacing=28`, `margin_bottom=16`, L/R=12.

La composición V2 se inyecta en `div.page`; el esqueleto Odoo se oculta (no se borra) para no romper herencias (`payment_communication`, l10n_do, warranty).

## Checkpoint Doralex (solo estos 4)

1. Cotización
2. Factura
3. Recibo
4. Estado de cuenta

No se rediseñaron todavía los 47 reportes ni las otras 5 empresas.

## Paletas derivadas de logos reales

| Empresa | primary | secondary | accent | neutral |
| --- | --- | --- | --- | --- |
| Doralex | `#E86A12` | `#1A1A1A` | `#E86A12` | `#5C5C5C` |
| Piñaria | `#C41E3A` | `#2E7D32` | `#C41E3A` | `#5C5C5C` |
| Dominion | `#2AA8A4` | `#F08A3C` | `#F08A3C` | `#5C5C5C` |
| El Mayuma | `#2EC4B6` | `#111111` | `#2EC4B6` | `#5C5C5C` |
| Rempart | `#1A1A1A` | `#3D7AB5` | `#3D7AB5` | `#5C5C5C` |
| Blue Elite | `#0A3D91` | `#00AEEF` | `#00AEEF` | `#5C5C5C` |

## COMPANY_DATA_MISSING

- website 6/6
- `dx_report_terms` / `invoice_terms` 6/6
- NCF: rangos no configurados; facturas/recibos en borrador

No inventados. Bancos Banreservas sí existen.

## WHAT_WAS_WRONG_V1

Header 46 mm, layout técnico de Odoo, título “Borrador”, tablas pequeñas, totales flotando, recibo y estado casi vacíos, scores autoasignados.

## WHAT_CHANGED_V2

Header 20–30 mm con logo + empresa + título/número. Título comercial (FACTURA, no Borrador). Tabla a ancho completo. Totales junto a la tabla. Recibo con monto protagonista y ANTICIPO explícito. Estado con KPIs + aging. V2.1: vendedor no-OdooBot, método en español, monto en letras.

Galería BEFORE/AFTER: [`docs/report_previews/index.html`](../report_previews/index.html)
