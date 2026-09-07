# Microsoft 365 / Entra — usuarios Alexander

Autenticación: Microsoft Graph con certificado de aplicación ya existente
en el servidor (`/opt/doralex/secrets/microsoft`). No se usó MSOnline ni
AzureAD legacy. No se guardaron tokens ni passwords en Git.

## Dominio

`DOMAIN_VERIFIED = YES` para `inversionesdoralex.com`.

También verificados en el tenant: pinariagroup.com, rempartgroup.com,
blueelite, dominion-business.com, elmayuma.com y el default
`doralex.onmicrosoft.com`.

Los UPN finales son `@inversionesdoralex.com`. No se creó ningún UPN
`.onmicrosoft.com` como login de negocio.

## SKUs reales (Get-MgSubscribedSku equivalente)

| SKU_PART_NUMBER | SKU_ID | PREPAID | CONSUMED | AVAILABLE | Exchange |
|---|---|---|---|---|---|
| O365_BUSINESS_PREMIUM | f245ecc8-75af-4f8e-b61f-27d8114de5f3 | 25 | 6 | 19 | EXCHANGE_S_STANDARD + Office/Teams |
| O365_BUSINESS | cdd28e44-67e3-425e-be4c-737fab2899d3 | 1 | 1 | 0 | EXCHANGE_S_FOUNDATION (sin buzón real) |
| O365DOMAINSTANDARD | 6a62c9a4-21f1-4b50-bdbb-9281101d307a | 2 | 0 | 2 | no |

`EXCHANGEDESKLESS` (Exchange Online Kiosk) **no está en el tenant**.
Por instrucción posterior se asignó la Standard actual del tenant
(`O365_BUSINESS_PREMIUM` / Microsoft 365 Business Standard) a los 6 UPN
nuevos. Cuando venza esa prueba se cambiará a Kiosk u otra. No se quitó
la licencia `O365_BUSINESS` de `alex@doralex.onmicrosoft.com`.

## Cuentas que no se tocaron

| UPN | Nota |
|---|---|
| admin@doralex.onmicrosoft.com | Global Administrator — password no reseteado |
| alex@doralex.onmicrosoft.com | Alexander Piña, O365_BUSINESS, sin buzón — no reseteado |

## Usuarios creados

Seis cuentas nuevas, `AccountEnabled = TRUE`, `UsageLocation = DO`,
cambio de credencial en el primer inicio (TRUE), `ADMIN_ROLES = NONE`.

| DISPLAY_NAME | UPN | LICENSE | MAILBOX | PRIMARY_SMTP |
|---|---|---|---|---|
| Luis Joel Aquino Casado | luis.aquino@inversionesdoralex.com | none | NOT_CREATED | none |
| Janny Chantal Montero | janny.montero@inversionesdoralex.com | none | NOT_CREATED | none |
| Elianny Nicole Sanchez Javier | elianny.sanchez@inversionesdoralex.com | none | NOT_CREATED | none |
| Leopordo Jimenez | leopordo.jimenez@inversionesdoralex.com | none | NOT_CREATED | none |
| Alexander Pina Aquino | alexander.pina@inversionesdoralex.com | none | NOT_CREATED | none |
| Geilin Rosario Suero | geilin.rosario@inversionesdoralex.com | none | NOT_CREATED | none |

No se activó SMTP AUTH. No se cambió la configuración global de Exchange.
No se desactivó MFA ni Security Defaults. No se asignaron roles admin M365.

## Siguiente paso Microsoft

Comprar 6× Exchange Online Kiosk (o autorizar por escrito otro SKU de
solo correo) y asignarlo. Hasta entonces `MAILBOXES_READY = 0`.
