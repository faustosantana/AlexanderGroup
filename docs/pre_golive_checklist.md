# Checklist preproducción — Alexander Group

Estado: **suite documental DEV cerrada en E2E**.  
`READY_TO_DEPLOY_PRODUCTION = BLOCKED_BY_CONFIGURATION`.  
**No desplegar a PROD en este ciclo.**

## Ya listo en DEV

- [x] Seis identidades V5.2/V5.3 en cotización (microajustes revisados en PNG)
- [x] Factura borrador / posteada / NC con NCF del motor QA (flujo real)
- [x] RFQ ≠ OC, recibo aplicado, recibo anticipo, estado, entrega, recepción
- [x] Saldo a favor = `RD$ 500.00` (no total negativo)
- [x] Header compacto en continuación (página 2+)
- [x] Firmas solo última página; totales solo al final
- [x] Aislamiento logo/RNC/banco/email/NCF por `document.company_id`
- [x] Cruce fiscal: Blue Elite activa + factura Rempart → NCF Rempart
- [x] EMAIL_PDF_MATCH = 6/6 (Graph Sent Items, FROM administración + PDF)
- [x] PDF de factura adjunto en plantilla EDI
- [x] PROD no tocado
- [x] Backup DEV antes de datos QA masivos

## Falta decisión / dato humano (bloquea PROD)

- [ ] Rangos NCF reales de producción (hoy solo QA DEV; no cargar DGII PROD)
- [ ] Tasa USD (`res.currency.rate` = 0)
- [ ] Términos legales definitivos por empresa
- [ ] Websites (si no hay, el PDF los oculta)
- [ ] Permisos usuario operacional (hoy no puede ni imprimir SO)
- [ ] Bancos confirmados por tesorería (hoy Banreservas QA)
- [ ] Primera factura controlada en PROD
- [ ] Primera NC controlada en PROD
- [ ] Primer pago controlado en PROD
- [ ] Primer email controlado en PROD
- [ ] Smoke test PROD post-deploy
- [ ] Backup PROD verificado
- [ ] Plan de deploy (solo reportes; no módulos congelados)
- [ ] Plan de rollback

## Congelados PROD (no tocar)

payments/withholding, multi invoice, margin control, sale-purchase trace.

## Go-live (solo con autorización humana)

1. Backup PROD.
2. Cargar NCF reales **después** de aprobación.
3. Confirmar correo Graph en PROD (FROM `administracion@`).
4. Tasa USD si van a facturar en USD.
5. Sustituir términos QA por legales.
6. Desplegar **solo** reportes acordados.
7. Smoke print A4 + recibo A5 + 1 email.
8. Marcar `READY_TO_DEPLOY_PRODUCTION = YES` únicamente entonces.
