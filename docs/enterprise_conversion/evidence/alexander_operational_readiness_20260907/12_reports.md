# 12 — Reportes

```
QWEB_BEFORE = 58
QWEB_AFTER = 58
REPORTS_PRESERVED = YES
```

Módulo `justech_alexander_reports` = 19.0.3.8.5 (no se actualizó).

## PDFs QA staging (12)

SO + OC × 6 empresas, tag `DXQA-OPREADY-20260907`. `MAIL_SENT = 0`.

Inspección visual primera página SO:

| COMPANY | LEGAL NAME | RNC FOOTER | EMAIL | BANK | LOGO HEADER | VERDICT |
|---|---|---|---|---|---|---|
| DORALEX | INVERSIONES DORALEX,S.RL. | 1-32-22011-2 | administracion@inversionesdoralex.com | 9604436830 | presente/débil | IDENTITY_PASS |
| PIÑARIA | COMERCIALIZADORA DE ALIMENTOS PIÑARIA, S.R.L. | 1-32-27106-8 | administracion@pinariagroup.com | 9604097492 | no claro en crop | IDENTITY_PASS / LOGO_WEAK |
| DOMINION | DOMINION BUSINESS,S.R.L. | (header email/tel) | administracion@dominion-business.com | 9605588726 | no claro en crop | IDENTITY_PASS / LOGO_WEAK |
| EL MAYUMA | INVERSIONES EL MAYUMA, S.R.L. | 1-32-71015-2 | administracion@elmayuma.com | 9605543104 | no claro en crop | IDENTITY_PASS / LOGO_WEAK |
| REMPART | REMPART GROUP S.R.L. | 1-32-76915-5 | administracion@rempartgroup.com | 9608739498 | no claro en crop | IDENTITY_PASS / LOGO_WEAK |
| BLUE ELITE | BLUE ELITE, S.R.L. | 1-33-37126-1 | administracion@blueelite.net | 9608670542 | mancha gris | IDENTITY_PASS / LOGO_WEAK |

Las 6 identidades **no** están unificadas. ITBIS 18%, totales 118.00, firmas Elaborado/Aprobado, paginación 1/1.

Layout dual EN+ES es el QWeb Alexander existente; no se rediseñó.

`company.logo = True` en las 6 (binario en Odoo). El render del header SO no muestra el logo con la misma fuerza en todas. No se tocó QWeb para “arreglarlo” (riesgo de perder los 58).

Factura/NCF/conduce: no se generó PDF de factura posteada (consumiría NCF). OC renderizadas (12 PDFs en staging `/tmp/op_ready_reports`).
