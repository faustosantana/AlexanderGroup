# DNS y PTR — acción del usuario

`DNS_USER_ACTION_REQUIRED = YES`
`PTR_USER_ACTION_REQUIRED = YES`

No se cambiaron MX corporativos. `erp.doralexgroup.cloud` no tiene registros hoy.
NS de `doralexgroup.cloud`: `artemis.dns-parking.com` / `hermes.dns-parking.com` (Hostinger).

`MAIL_VPS_IPV4` = IPv4 del **VPS de correo** (aún no existe). No usar
`2.25.121.111` hasta que Mailcow viva ahí.

TTL sugerido: 300 mientras se prueba; 3600 después.

## Registros a crear (cuando exista la IP de correo)

| TYPE | HOST | VALUE | PRIORITY | TTL | PURPOSE |
|---|---|---|---|---|---|
| A | mail.erp | MAIL_VPS_IPV4 | | 300 | host SMTP/IMAP/UI |
| AAAA | mail.erp | MAIL_VPS_IPV6 o omitir | | 300 | solo si hay IPv6 en el VPS correo |
| MX | erp | mail.erp.doralexgroup.cloud | 10 | 300 | buzones @erp.doralexgroup.cloud |
| TXT | erp | v=spf1 mx a:mail.erp.doralexgroup.cloud -all | | 300 | SPF único |
| TXT | dkim._domainkey.erp | *(valor DKIM que genere Mailcow; no inventar)* | | 300 | DKIM |
| TXT | _dmarc.erp | v=DMARC1; p=none; rua=mailto:postmaster@erp.doralexgroup.cloud; fo=1 | | 300 | DMARC inicial |
| CNAME | autodiscover.erp | mail.erp.doralexgroup.cloud | | 300 | clientes IMAP |
| CNAME | autoconfig.erp | mail.erp.doralexgroup.cloud | | 300 | clientes IMAP |

No crear un segundo TXT SPF en `erp`.

No tocar:

| HOST | QUÉ HAY HOY | ACCIÓN |
|---|---|---|
| inversionesdoralex.com MX | Outlook | no cambiar |
| pinariagroup.com MX | Outlook | no cambiar |
| dominion-business.com MX | Outlook | no cambiar |
| elmayuma.com MX | Outlook | no cambiar |
| rempartgroup.com MX | Outlook | no cambiar |
| blueelite.net MX | Outlook | no cambiar |
| doralexgroup.cloud A | 2.25.121.111 | no cambiar |
| doralexgroup.cloud MX | 10 doralexgroup.cloud. | no cambiar |

## PTR (panel Hostinger del VPS de correo)

```
PUBLIC_IP = MAIL_VPS_IPV4
CURRENT_PTR (VPS Odoo 2.25.121.111) = srv1935521.hstgr.cloud.
REQUIRED_PTR = mail.erp.doralexgroup.cloud
PROVIDER_ACTION_REQUIRED = YES
```

Debe quedar:

- `MAIL_VPS_IPV4` PTR → `mail.erp.doralexgroup.cloud`
- `mail.erp.doralexgroup.cloud` A → `MAIL_VPS_IPV4`

## DKIM

`DKIM_SELECTOR`, `DKIM_DNS_HOST`, `DKIM_DNS_VALUE` se rellenan **después**
de instalar Mailcow en el VPS de correo. No se inventa la clave.
No se publica la private key.

## SPF / DMARC

`SPF_STATUS` = MISSING hasta el TXT.
DMARC inicial `p=none`. Subir a `quarantine` a los 7–14 días de alineación;
`reject` solo cuando SPF+DKIM+PTR estén verdes en correo externo.
