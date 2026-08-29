# Checklist preproducción — Alexander Group

Estado: **DEV cercano a go-live de reportes**.  
`READY_TO_DEPLOY_PRODUCTION = BLOCKED_BY_CONFIGURATION`.  
**No desplegar a PROD en este ciclo.**

## Ya listo en DEV

- [x] Seis identidades V5.2/V5.3 en cotización
- [x] Factura borrador / posteada / nota de crédito con NCF del motor QA
- [x] RFQ, OC, recibo aplicado, recibo anticipo, estado de cuenta, entrega, recepción
- [x] Aislamiento de logo, RNC, banco, email y NCF por `document.company_id`
- [x] Multipágina: firmas solo al final, footer Página X/Y
- [x] Español en títulos comerciales
- [x] Sin NCF inventado en borrador
- [x] PROD no tocado

## Falta decisión / dato humano (bloquea PROD)

1. **NCF producción** — cargar rangos reales solo con aprobación explícita. Hoy solo rangos QA DEV.
2. **Correo saliente** — no hay `ir.mail_server` en DEV. FROM debe ser `administracion@dominio` por empresa. `EMAIL_PDF_MATCH` no se puede cerrar a 6/6 sin eso.
3. **Tasa USD** — 0 registros en `res.currency.rate`. No inventar. Operar en DOP hasta configurar.
4. **Términos legales PROD** — los textos actuales son QA de DEV. Revisar y cargar términos finales por empresa.
5. **Website** — si no existe, el PDF lo oculta. No inventar URL.
6. **Roles** — usuario operacional debe cotizar / vender / facturar / NC / pagos / compras / imprimir **sin** admin global. Pendiente sign-off humano del mapa de grupos.
7. **Congelados PROD** — no upgrade/hotfix de payments/withholding, multi invoice, margin control, sale-purchase trace.

## Go-live (cuando lo autorice un humano)

1. Backup PROD verificado.
2. Cargar NCF reales **después** de aprobación.
3. Configurar correo y probar 1 cotización + 1 factura por empresa (meta `EMAIL_PDF_MATCH = 6/6`).
4. Cargar tasa USD si van a facturar en USD.
5. Sustituir términos QA por legales.
6. Desplegar **solo** el módulo de reportes acordado; no tocar módulos congelados.
7. Smoke print A4 100% y un recibo A5.
8. Dejar `READY_TO_DEPLOY_PRODUCTION = YES` únicamente cuando 1–7 estén cerrados.
