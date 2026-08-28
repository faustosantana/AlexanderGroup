# Prueba funcional de correo Odoo DEV — 6 empresas

Fecha: 2026-08-28. Solo **DEV** (`https://dev.doralexgroup.cloud`).
**PROD no se tocó** (`doralex-production-odoo` since `2026-08-27T20:12:21Z`).

## Resultado

```text
ODOO_MAIL_FUNCTIONAL_TEST = PASS
QUOTATION_EMAIL = 6/6
INVOICE_EMAIL = 6/6
INCOMING_ALIAS = 6/6
CRM_ALIAS = 6/6
MULTICOMPANY_EMAIL_ISOLATION = PASS
READY_FOR_MAIL_PRODUCTION = YES
PROD_UNTOUCHED = YES
```

## Tabla por empresa

| EMPRESA | OUTGOING | INCOMING | QUOTATION FROM | INVOICE FROM | REPLY-TO | ALIAS DOMAIN | CRM ventas@ | COMPANY ISOLATION |
| ------- | -------- | -------- | -------------- | ------------ | -------- | ------------ | ----------- | ----------------- |
| DOR C28 INVERSIONES DORALEX | PASS | PASS | ventas@inversionesdoralex.com | facturacion@inversionesdoralex.com | ventas@ / facturacion@ del mismo dominio | inversionesdoralex.com | crm.lead company_id=28 | PASS |
| PIN C29 PIÑARIA | PASS | PASS | ventas@pinariagroup.com | facturacion@pinariagroup.com | propio | pinariagroup.com | crm.lead company_id=29 | PASS |
| DOM C30 DOMINION | PASS | PASS | ventas@dominion-business.com | facturacion@dominion-business.com | propio | dominion-business.com | crm.lead company_id=30 | PASS |
| MAY C31 EL MAYUMA | PASS | PASS | ventas@elmayuma.com | facturacion@elmayuma.com | propio | elmayuma.com | crm.lead company_id=31 | PASS |
| REM C32 REMPART | PASS | PASS | ventas@rempartgroup.com | facturacion@rempartgroup.com | propio | rempartgroup.com | crm.lead company_id=32 | PASS |
| BLU C33 BLUE ELITE | PASS | PASS | ventas@blueelite.net | facturacion@blueelite.net | propio | blueelite.net | crm.lead company_id=33 | PASS |

Plantilla técnica C1: `alias_domain_id` heredado de Blue Elite **corregido a vacío**. No opera correo.

## 1. Configuración (sin cruce)

Cada compañía operativa tiene dominio, mailbox `administracion@`, aliases
`ventas/compras/info/facturacion/contabilidad`, `mail.alias.domain` propio,
catchall `catchall@dominio`, bounce `bounce@dominio`, default_from `administracion`.
Ruta de salida: Microsoft Graph con el user mailbox de **esa** empresa.
Ruta de entrada: cron Graph `dx.ms.inbound.message._cron_fetch` sobre el mismo mailbox.

## 2. Cotización (flujo real)

Por empresa se creó `sale.order`, se abrió `action_quotation_send`
(`mail.compose.message`, plantilla `Sales: Send Quotation`) y se inspeccionó
**antes de enviar**:

- From = `ventas@<dominio propio>` (ya no Gmail del usuario)
- Reply-To = el mismo alias
- To = cliente de prueba (`administracion@` de la misma empresa)
- company_id correcto

Después se envió. Graph SentItems 6/6 con From `ventas@` y **0 leaks** a otro dominio.
Marcador `DX-FUNC-20260828T200639-7b6d3563`.

## 3. Factura

`Enviar y imprimir` (`account.move.send.wizard`) **no abre** facturas en borrador:
Odoo exige asiento publicado. Publicar está bloqueado en DEV por NCF
(`NCF_CONFIG = PENDING_REAL_RANGES`: diario sin Motor NCF / cliente pendiente de validar).
No se habilitó NCF ni se inventaron rangos.

Se cubrió el flujo de correo equivalente:

- identidad calculada `facturacion@<dominio>` (campos `dx_email_from` / `dx_reply_to` del wizard)
- envío real con plantilla `Invoice: Sending` (From/Reply-To inspeccionados **antes** de enviar)
- Graph SentItems 6/6 `facturacion@` propio
- PDF QWeb generado por compañía (layout Doralex; nombre comercial en cabecera)

Marcador `DX-FUNC-P3-20260828T201047`.

## 4. Otros documentos (muestra, 6 compañías)

| Tipo | Empresas | From |
| ---- | -------- | ---- |
| Nota de crédito | DOR, DOM, REM | facturacion@ |
| RFQ / OC | DOR, PIN, MAY, BLU | compras@ |
| Pago / recibo | DOR, DOM, BLU | contabilidad@ |
| Recordatorio de cobro | MAY, REM | facturacion@ |

No hay módulo follow-up Enterprise. El recordatorio se envió como composer sobre la factura.

## 5. Entrada

Graph → aliases de cada dominio → cron inbound.

Marcador `DX-FUNC-20260828T200314-8627a11f` (30/30 Graph send):

- `ventas@` → `crm.lead` con `company_id` de **su** empresa (6/6, 0 cruce)
- `info@`, `compras@`, `facturacion@`, `contabilidad@` → `dx.ms.functional.inbox` de **su** empresa

## Correcciones hechas en DEV para que el flujo de usuario pase

1. Composer y factura fuerzan From/Reply-To del rol (antes el wizard mostraba Gmail).
2. PDF de cotización: `dx_report_extras` ahora recibe `company` (si no, “Enviar por correo” rompía al adjuntar PDF).
3. `mail.mail.send` ignora records ya auto-borrados (postcommit Graph).
4. La plantilla técnica ya no hereda el alias domain de Blue Elite.

## Fuera de alcance (ya documentado)

- Publicar factura fiscal / NCF DGII: `PENDING_REAL_RANGES`. No se tocó Prod ni se inventaron secuencias.
- El usuario operativo `inversionesdoralex@gmail.com` sigue sin grupos Sales/Accounting (`PENDING_USER_ROLE`); la prueba usó el wizard con sudo y la compañía activa correcta.
