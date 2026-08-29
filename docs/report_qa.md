# Report QA — V5.3 suite documental

Módulo `justech_alexander_reports` **19.0.3.7.1**. Solo DEV. PROD no tocado.

`VISUAL_V4 = REJECTED`. `VISUAL_V5 = SUPERSEDED`. `VISUAL_V5_1 = SUPERSEDED`.
`VISUAL_V5_2 = APPROVED_AS_DESIGN_BASE`. `VISUAL_V5_3 = FINAL_POLISH`.

## Scorecard de este ciclo

| Clave | Valor |
| --- | --- |
| VISUAL_V5_3 | PASS |
| QUOTATION_REPORT | PASS |
| INVOICE_REPORT | PASS |
| CREDIT_NOTE_REPORT | PASS |
| RFQ_REPORT | PASS |
| PURCHASE_ORDER_REPORT | PASS |
| PAYMENT_RECEIPT_REPORT | PASS (A5; monto visible; anticipo explícito) |
| STATEMENT_REPORT | PASS (SALDO A FAVOR, no RD$ negativo) |
| DELIVERY_REPORT | PASS |
| RECEIPT_REPORT | PASS (recepción: Esperada / Recibida) |
| EMAIL_PDF_MATCH | 0/6 BLOCKED_BY_CONFIGURATION (0 `ir.mail_server` en DEV) |
| MULTICOMPANY_REPORT_ISOLATION | PASS (`document.company_id`; cruz PIN→DOR sigue Doralex) |
| MULTICOMPANY_FISCAL_ISOLATION | PASS (NCF B01/B04 por empresa, rangos QA) |
| NCF_QA_ENGINE | PASS (NCF reales al postear; borrador = Pendiente de NCF) |
| MULTIPAGE_RENDER | PASS (40 líneas = 3 páginas; thead; footer X/Y) |
| SIGNATURE_LAST_PAGE | PASS (solo página 3/3) |
| PRINT_READABILITY | PASS técnico A4 100% / A5 recibo; B/N no impreso en este ciclo |
| REPORT_SUITE_COMPLETE | YES (suite operativa renderizada; email y USD pendientes de config) |
| READY_TO_DEPLOY_PRODUCTION | BLOCKED_BY_CONFIGURATION |
| PROD_UNTOUCHED | YES (`StartedAt` 2026-08-27T20:12:21.681221743Z) |
| USD_RATE_CONFIGURATION | BLOCKED (0 tasas `res.currency.rate` para USD) |

## Microajustes V5.3 (cotización)

- Doralex: vendedor a ancho completo. `ALEXANDER PIÑA AQUINO` en una línea.
- Piñaria: TOTAL rojo más compacto, mismo bloque que Subtotal/ITBIS.
- Dominion: líneas de firma ~37% (antes 30%).
- El Mayuma / Rempart: alineación y line-height, sin rediseño.
- Blue Elite: TOTAL apilado (`Total` / `RD$ 642,451.00`). No `TotalRD$`.

## Extensión de identidad

Misma familia visual (header, tabla, totales, firmas). Composición propia:

- Factura: NCF protagonista. Borrador = BORRADOR + Pendiente de NCF. Sin NCF inventado.
- NC: flujo real de reversión. NCF B04 + NCF afectado + total acreditado.
- RFQ ≠ OC (títulos distintos). Firmas Solicitado / Aprobado.
- Recibo A5: monto + letras; aplicado vs `PAGO NO APLICADO / ANTICIPO`.
- Estado: KPIs + movimientos + aging. Créditos visibles.
- Entrega / recepción: composición operativa.

## Fiscal QA (rangos DEV, no PROD)

| Empresa | Factura B01 | NC B04 |
| --- | --- | --- |
| DOR | B0199000005 | B0499000123 (afecta B0199000005) |
| PIN | B0199001001 | B0499001121 |
| DOM | B0199002001 | B0499002121 |
| MAY | B0199003001 | B0499003121 |
| REM | B0199004001 | B0499004121 |
| BLU | B0199005001 | B0499005121 |

## Bloqueos humanos (no inventados)

1. Rangos NCF de **producción** — no cargar sin aprobación explícita.
2. Servidor de correo saliente por empresa (`administracion@…`).
3. Tasa USD.
4. Términos comerciales legales de PROD (hoy solo textos QA de DEV).
5. Website por empresa: si falta, se oculta; no se inventa.

PNG/PDF: [`docs/report_previews/v53/`](report_previews/v53/). Checklist: [`docs/pre_golive_checklist.md`](pre_golive_checklist.md).
