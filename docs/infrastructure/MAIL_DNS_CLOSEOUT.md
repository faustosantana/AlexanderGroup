# Cierre DNS de correo — 6 dominios Doralex

Fecha de auditoría: 2026-08-28. Tenant `doralex.onmicrosoft.com`.
**PROD Odoo / Doralex PROD no se tocaron.**

## Resultado

```text
MX = 2/6
SPF = 2/6
DKIM = 0/6
DMARC = 4/6
MAIL_FLOW_TEST = 2/6
READY_FOR_MAIL_PRODUCTION = NO
```

`MAIL_FLOW_TEST` cuenta inbound público enrutable por MX. Graph interno
(send/receive + From alias + isolation) está en **6/6**. EOP acepta RCPT 250
hacia los 6 `administracion@` si se conecta directo a
`*.mail.protection.outlook.com`; internet no llega a 4 dominios porque no hay MX
Outlook publicado.

## Proveedor DNS (live NS)

| Dominio | Nameservers | DNS host |
| ------- | ----------- | -------- |
| `pinariagroup.com` | `ns1–4.bdm.microsoftonline.com` | Microsoft 365 FullRedelegation |
| `rempartgroup.com` | `ns1–4.bdm.microsoftonline.com` | Microsoft 365 FullRedelegation |
| `inversionesdoralex.com` | `ns75/76.domaincontrol.com` | GoDaddy |
| `dominion-business.com` | `ns71/72.domaincontrol.com` | GoDaddy |
| `elmayuma.com` | `ns39/40.domaincontrol.com` | GoDaddy |
| `blueelite.net` | `ns17/18.domaincontrol.com` | GoDaddy |

No hay API GoDaddy, zona Azure DNS, ni suscripción Azure. Graph
`serviceConfigurationRecords` es solo lectura. `Set-DkimSigningConfig -Enabled`
falla con `CnameMissing` hasta publicar los CNAME. El editor DNS de Microsoft
365 Admin Center no aceptó escritura con token de `az`. Piñaria/Rempart MX+SPF
Outlook **no se modificaron**.

Acción hecha en tenant (no DNS): `PATCH` Graph `supportedServices` += `Email` en
los 4 dominios GoDaddy. Eso desbloqueó EOP `451 4.4.4 … no mail-enabled
subscriptions` → `250 Recipient OK`. `IsDehydrated=True` (upgrade org en curso);
`Enable-OrganizationCustomization` aún no aplica.

## Live vs requerido

MX Exchange Online (Graph):

| Dominio | MX requerido |
| ------- | ------------ |
| inversionesdoralex.com | `0 inversionesdoralex-com.mail.protection.outlook.com` |
| pinariagroup.com | `0 pinariagroup-com.mail.protection.outlook.com` (ya live) |
| dominion-business.com | `0 dominionbusiness-com02b.mail.protection.outlook.com` |
| elmayuma.com | `0 elmayuma-com.mail.protection.outlook.com` |
| rempartgroup.com | `0 rempartgroup-com.mail.protection.outlook.com` (ya live) |
| blueelite.net | `0 blueelite-net.mail.protection.outlook.com` |

SPF Microsoft: `v=spf1 include:spf.protection.outlook.com -all` (un solo `v=spf1`).
DKIM Exchange: `Enabled=False`, `Status=CnameMissing` en los 6.
DMARC: 4 dominios GoDaddy ya tienen `p=quarantine` (rua GoDaddy). Piñaria y
Rempart no tienen `_dmarc`.

## Plan DMARC (después de alinear SPF+DKIM)

1. Publicar DKIM y verificar `Enabled=true`.
2. Dejar `p=none` (Piñaria/Rempart) o el `p=quarantine` ya existente (GoDaddy)
   y revisar `rua` 7–14 días.
3. Subir a `p=quarantine` donde aún esté `none`.
4. Solo entonces `p=reject`. No saltar a reject sin alineación.

## Registros pendientes (copiar/pegar)

TTL 3600. Host `@` = apex. No crear un segundo TXT `v=spf1`. En
`dominion-business.com` el SPF se **edita** (combinado) y los MX GoDaddy se
**eliminan** para no partir el correo.

| DOMINIO | TIPO | NOMBRE/HOST | VALOR | TTL |
| ------- | ---- | ----------- | ----- | --- |
| pinariagroup.com | CNAME | selector1._domainkey | selector1-pinariagroup-com._domainkey.doralex.w-v1.dkim.mail.microsoft | 3600 |
| pinariagroup.com | CNAME | selector2._domainkey | selector2-pinariagroup-com._domainkey.doralex.w-v1.dkim.mail.microsoft | 3600 |
| pinariagroup.com | TXT | _dmarc | v=DMARC1; p=none; rua=mailto:administracion@pinariagroup.com; fo=1 | 3600 |
| rempartgroup.com | CNAME | selector1._domainkey | selector1-rempartgroup-com._domainkey.doralex.r-v1.dkim.mail.microsoft | 3600 |
| rempartgroup.com | CNAME | selector2._domainkey | selector2-rempartgroup-com._domainkey.doralex.r-v1.dkim.mail.microsoft | 3600 |
| rempartgroup.com | TXT | _dmarc | v=DMARC1; p=none; rua=mailto:administracion@rempartgroup.com; fo=1 | 3600 |
| inversionesdoralex.com | MX | @ | 0 inversionesdoralex-com.mail.protection.outlook.com | 3600 |
| inversionesdoralex.com | TXT | @ | v=spf1 include:spf.protection.outlook.com -all | 3600 |
| inversionesdoralex.com | CNAME | autodiscover | autodiscover.outlook.com | 3600 |
| inversionesdoralex.com | CNAME | selector1._domainkey | selector1-inversionesdoralex-com._domainkey.doralex.a-v1.dkim.mail.microsoft | 3600 |
| inversionesdoralex.com | CNAME | selector2._domainkey | selector2-inversionesdoralex-com._domainkey.doralex.a-v1.dkim.mail.microsoft | 3600 |
| dominion-business.com | MX | @ | 0 smtp.secureserver.net | ELIMINAR |
| dominion-business.com | MX | @ | 10 mailstore1.secureserver.net | ELIMINAR |
| dominion-business.com | MX | @ | 0 dominionbusiness-com02b.mail.protection.outlook.com | 3600 |
| dominion-business.com | TXT | @ | v=spf1 include:spf.protection.outlook.com include:spf.em.secureserver.net -all | 3600 |
| dominion-business.com | CNAME | autodiscover | autodiscover.outlook.com | 3600 |
| dominion-business.com | CNAME | selector1._domainkey | selector1-dominionbusiness-com02b._domainkey.doralex.q-v1.dkim.mail.microsoft | 3600 |
| dominion-business.com | CNAME | selector2._domainkey | selector2-dominionbusiness-com02b._domainkey.doralex.q-v1.dkim.mail.microsoft | 3600 |
| elmayuma.com | MX | @ | 0 elmayuma-com.mail.protection.outlook.com | 3600 |
| elmayuma.com | TXT | @ | v=spf1 include:spf.protection.outlook.com -all | 3600 |
| elmayuma.com | CNAME | autodiscover | autodiscover.outlook.com | 3600 |
| elmayuma.com | CNAME | selector1._domainkey | selector1-elmayuma-com._domainkey.doralex.e-v1.dkim.mail.microsoft | 3600 |
| elmayuma.com | CNAME | selector2._domainkey | selector2-elmayuma-com._domainkey.doralex.e-v1.dkim.mail.microsoft | 3600 |
| blueelite.net | MX | @ | 0 blueelite-net.mail.protection.outlook.com | 3600 |
| blueelite.net | TXT | @ | v=spf1 include:spf.protection.outlook.com -all | 3600 |
| blueelite.net | CNAME | autodiscover | autodiscover.outlook.com | 3600 |
| blueelite.net | CNAME | selector1._domainkey | selector1-blueelite-net._domainkey.doralex.w-v1.dkim.mail.microsoft | 3600 |
| blueelite.net | CNAME | selector2._domainkey | selector2-blueelite-net._domainkey.doralex.w-v1.dkim.mail.microsoft | 3600 |

Después de publicar: `Set-DkimSigningConfig -Identity <dominio> -Enabled $true`.
Mantener el TXT `MS=ms42350016` en `inversionesdoralex.com` (no es SPF).
No tocar registros A de parking GoDaddy.
