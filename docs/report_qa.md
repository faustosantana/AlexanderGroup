# Report QA — V3.2

Módulo `justech_alexander_reports` **19.0.3.2.0**. DEV only. PROD no tocado.

## Estado de este ciclo

| Clave | Valor |
| --- | --- |
| DORALEX_DESIGN | PENDING (hay PNG) |
| PINARIA_DESIGN | PENDING (hay PNG) |
| DOMINION_DESIGN | PENDING (hay PNG) |
| MAYUMA_DESIGN | PENDING (hay PNG) |
| REMPART_DESIGN | PENDING (hay PNG) |
| BLUEELITE_DESIGN | PENDING (hay PNG) |
| SIGNATURE_POSITION | PASS técnico en 1 línea / A5 (spacer en bloques 48px). Checkpoint humano. |
| EMAIL_PDF_MATCH | 0/6 NOT_TESTED este ciclo |
| PURCHASE_FLOW | 6/6 PDF render (OC existentes) |
| DELIVERY_FLOW | 6/6 PDF render (albaranes existentes) |
| NCF_QA_ENGINE | PASS |
| MULTICOMPANY_FISCAL_ISOLATION | PASS (ciclo previo; NCF por empresa en estas facturas) |
| PROD_UNTOUCHED | YES (`StartedAt` 2026-08-27T20:12:21.681221743Z) |
| REPORT_SUITE_COMPLETE | NO |
| MONDAY_OPERATIONAL_READY | NO |
| USD | BLOCKED_BY_CONFIGURATION (sin `res.currency.rate`) |

## Firmas

wkhtmltopdf 0.12.6 Qt4 ignora `min-height`, `position` peligroso, GIF 1×1 y bordes transparentes.  
El spacer es una pila de `div` de 48px (`nbsp` + `min-height`) calculada por número de líneas: 1–8 sí, 15+ colapsa.

Etiquetas: cotización Elaborado/Aceptado por el cliente · factura Elaborado/Recibido conforme (operativo, no requisito fiscal) · NC Preparado/Aprobado · OC Solicitado/Aprobado · entrega Entregado/Recibido · recibo Recibido/Entregado · estado **sin** firma.

## Footer

`{marca} · RNC · email · teléfono · web?` + `Página X / Y`. Sin país duplicado.

## Paleta

Ver [`report_brand_colors.md`](report_brand_colors.md).

## PNG

[`docs/report_previews/v32/`](report_previews/v32/) y overviews en [`report_previews/v32_overview/`](report_previews/v32_overview/).
