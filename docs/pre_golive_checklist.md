# Checklist preproducción — Alexander Group

Estado: **suite documental y correo desplegados en PROD**.  
`READY_TO_DEPLOY_PRODUCTION = YES` (ejecutado 2026-08-29).  
`FISCAL_POSTING_READY = NO` — faltan rangos NCF reales.

## Hecho en PROD

- [x] Backup PROD verificado (`production_20260829_104748`)
- [x] Secret scan del código a desplegar
- [x] Código + módulos target (sin `-u all`, sin módulos congelados)
- [x] Reportes V5.3 6 identidades
- [x] Multiempresa por `document.company_id`
- [x] Graph / From `administracion@` 6/6
- [x] DNS MX/SPF/DKIM/DMARC 6/6 (sin cambios)
- [x] Permisos usuario operacional (no admin global)
- [x] Motor fiscal instalado; 0 rangos
- [x] Guardia de posteo sin rango NCF
- [x] Factura borrador muestra Pendiente de NCF
- [x] Websites vacíos ocultos
- [x] Smoke post-deploy
- [x] Rollback documentado (comandos listos; no ejecutado)

## Pendiente humano (bloquea solo facturación fiscal)

- [ ] Rangos NCF reales DGII por empresa/tipo
- [ ] Secuencias y vencimientos reales
- [ ] Tasa USD si aplica
- [ ] Términos legales definitivos
- [ ] Primera factura / NC / pago controlados en PROD

## Congelados (no instalados en este deploy)

payments/withholding, multi invoice, margin control, sale-purchase trace.
