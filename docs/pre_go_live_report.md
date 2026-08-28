# Pre-go-live report — Doralex DEV

2026-08-28. Trabajo solo en DEV. **PRODUCTION_DEPLOYED = NO.**

## 1. Resumen ejecutivo

El motor fiscal Justech asigna NCF QA reales (formato B01/B02/B04, banda `99xxxxxx`) en las 6 empresas. Se postearon facturas, notas de crédito desde el wizard, pagos y un estado de cuenta que ahora cuadra. Los reportes V2.3 renderizan con identidad por `company_id`. **No está listo para facturar el lunes en producción**: faltan rangos DGII reales, permisos del usuario operativo, términos, tasa USD y aprobación humana de diseño.

`MONDAY_OPERATIONAL_READY = NO`  
`READY_TO_DEPLOY_PRODUCTION = NO`  
`PROD_UNTOUCHED = YES` (container start `2026-08-27T20:12:21.681221743Z`)

## 2. Blockers críticos

1. Rangos NCF de producción no cargados (esperado hasta autorización).
2. Usuario `inversionesdoralex@gmail.com` sin grupos fiscales / NC.
3. Términos comerciales y websites vacíos 6/6 (no inventados).
4. Sin tasa USD configurada.
5. Diseño V2.3 sin aprobación humana.

## 3. Acciones lunes (si se opera solo DEV)

Usar rangos QA conscientemente. No enviar PDF QA a clientes reales.  
Si el objetivo es PROD el lunes: **no facturar** hasta cerrar la lista humana.

## 4. Master data pendiente

Website, `dx_report_terms`, confirmación de titular bancario (registros = nombres personales; PDF = razón social), e-CF.

## 5–9. Readiness

Ver `docs/go_live_checklist.md`, `docs/fiscal_qa.md`, `docs/report_qa.md`, `docs/mail_qa.md`, `docs/multicompany_qa.md`.

## 10. Deploy PROD (plan, no ejecutar)

1. Backup PROD verificado.  
2. Deploy módulo + `-u justech_alexander_reports` (y dependencias si aplica).  
3. Cargar datos de compañía ya existentes (no clonar QA).  
4. Cargar rangos NCF autorizados.  
5. Smoke controlado.  
6. Rollback: restore del backup; no “reset NCF”.

Ventana: fuera de horario de facturación DGII.  
Después: monitorear cola de correo, primer NCF, primer pago.
