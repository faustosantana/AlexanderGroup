# 13 — Correo

```
MAIL_SENT = 0
ir.mail_server = 0
mail.mail sent/outgoing since 2026-09-04 = 0
```

| COMPANY | ODOO EMAIL | EXCEL EMAIL | CATCHALL |
|---|---|---|---|
| DORALEX | administracion@inversionesdoralex.com | inversionesdoralex@gmail.com | catchall@inversionesdoralex.com |
| PIÑARIA | administracion@pinariagroup.com | piñariascomercializadora@gmail.com | catchall@pinariagroup.com |
| DOMINION | administracion@dominion-business.com | dominionsrl@hotmail.com | catchall@dominion-business.com |
| EL MAYUMA | administracion@elmayuma.com | inversioneselmayuma@gmail.com | catchall@elmayuma.com |
| REMPART | administracion@rempartgroup.com | rempartsrl@hotmail.com | catchall@rempartgroup.com |
| BLUE ELITE | administracion@blueelite.net | bluelitesrl@hotmail.com | catchall@blueelite.net |

No se sobrescribió el correo Odoo con el personal del Excel.

Identidad de documentos (SO staging): cada empresa usa su `administracion@…` y su RNC/banco. Rempart no sale con firma Doralex.

Falta SMTP real → envío outbound `MISSING`. No se configuró a ciegas. No se enviaron correos de QA.

Cron `Digest Emails` existe; no hay mail sent desde la apertura.
