# Cierre DNS de correo — 6 dominios Doralex

Fecha: 2026-08-28. Tenant `doralex.onmicrosoft.com`.
**PROD Odoo / Doralex PROD no se tocaron.**

## Resultado

```text
GODADDY_API_ACCESS = PASS
GODADDY_DOMAINS = 4/4
MX = 6/6
SPF = 6/6
AUTODISCOVER = 6/6
DKIM = 4/6
DMARC = 4/6
EXCHANGE_DKIM_ENABLED = 4/6
MAIL_FLOW_TEST = 6/6
ODOO_OUTGOING_MAIL = PASS
ODOO_INCOMING_MAIL = PASS
MULTICOMPANY_MAIL_ISOLATION = PASS
READY_FOR_MAIL_PRODUCTION = NO
```

Bloqueo restante: Piñaria y Rempart usan DNS de Microsoft 365 (`ns*.bdm.microsoftonline.com`).
No están en la cuenta GoDaddy. No hay API de escritura para CNAME DKIM ni `_dmarc`.
MX/SPF/autodiscover Outlook de esos dos **no se tocaron**.

## Proveedor DNS

| Dominio | Nameservers | Host | Mail DNS |
| ------- | ----------- | ---- | -------- |
| pinariagroup.com | Microsoft FullRedelegation | Microsoft | MX/SPF/autodiscover OK; DKIM/DMARC pendiente |
| rempartgroup.com | Microsoft FullRedelegation | Microsoft | MX/SPF/autodiscover OK; DKIM/DMARC pendiente |
| inversionesdoralex.com | GoDaddy | GoDaddy API | MX/SPF/autodiscover/DKIM/DMARC PASS; DKIM EXO Valid |
| dominion-business.com | GoDaddy | GoDaddy API | igual; MX GoDaddy reemplazado por Outlook |
| elmayuma.com | GoDaddy | GoDaddy API | PASS |
| blueelite.net | GoDaddy | GoDaddy API | PASS |

## Cambios GoDaddy (correo únicamente)

Creados: MX Outlook, SPF Outlook, autodiscover, selector1/selector2 DKIM en los 4 dominios
(excepto SPF de Dominion, que se **reemplazó**).

Modificados: `dominion-business.com` SPF
`v=spf1 include:spf.em.secureserver.net ?all` → `v=spf1 include:spf.protection.outlook.com -all`.

Eliminados: MX `smtp.secureserver.net` y `mailstore1.secureserver.net` en Dominion
(v3 DELETE 409 `sable_mx`; v1 PUT MX `@` Outlook-only sí los quitó).

Conservados: nameservers, A de parking/WebsiteBuilder, `www`, Intune CNAME,
`_domainconnect`, TXT `MS=ms42350016`, DMARC `p=quarantine` de GoDaddy,
CNAME de Email Marketing en Dominion (`bounces.cloud.em`, `sable.cloud._domainkey`).

DKIM Exchange `Enabled=True Status=Valid`: inversionesdoralex, dominion-business,
elmayuma, blueelite.

## Plan DMARC (después de DKIM Piñaria/Rempart)

1. Publicar CNAME DKIM + `_dmarc p=none` en Microsoft DNS.
2. `Set-DkimSigningConfig -Enabled $true`.
3. Revisar `rua` 7–14 días; luego quarantine; después reject.
