# Report QA — V4 editorial

Módulo `justech_alexander_reports` **19.0.3.3.0**. DEV only. PROD no tocado.

## Estado de este ciclo

| Clave | Valor |
| --- | --- |
| VISUAL_V4 | PENDING |
| DORALEX_DESIGN | PENDING |
| PINARIA_DESIGN | PENDING |
| DOMINION_DESIGN | PENDING |
| MAYUMA_DESIGN | PENDING |
| REMPART_DESIGN | PENDING |
| BLUEELITE_DESIGN | PENDING |
| LOGO_ASSET_OK_DOR | PASS |
| LOGO_ASSET_OK_PIN | PASS |
| LOGO_ASSET_OK_DOM | PASS (PNG oficial en `res.company.logo`, header blanco, sin placa) |
| LOGO_ASSET_OK_MAY | PASS (PNG oficial recortado, header blanco, sin placa) |
| LOGO_ASSET_OK_REM | PASS |
| LOGO_ASSET_OK_BLU | PASS |
| SIGNATURE_POSITION | PASS técnico (spacer 48px). Checkpoint humano. |
| EMAIL_PDF_MATCH | 0/6 NOT_TESTED este ciclo |
| NCF_QA_ENGINE | PASS |
| MULTICOMPANY_FISCAL_ISOLATION | PASS (ciclo previo) |
| PROD_UNTOUCHED | YES (`StartedAt` 2026-08-27T20:12:21.681221743Z) |
| REPORT_SUITE_COMPLETE | NO |
| MONDAY_OPERATIONAL_READY | NO |
| USD | BLOCKED_BY_CONFIGURATION (sin `res.currency.rate`) |

## Qué cambió en V4 (solo visual)

Menos bordes. Metadata apilada (label / valor). Tabla con header de marca +
líneas horizontales. Totales abiertos. Firmas sin rectángulo. Footer con
hairline. Headers sin cajas ni placas negras.

No se tocó motor fiscal, NCF, `company_id`, email, bancos ni lógica contable.

## PNG

[`docs/report_previews/v4/`](report_previews/v4/) y comparativos en
[`report_previews/v4_overview/`](report_previews/v4_overview/).
