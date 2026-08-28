# Remitente único por empresa — `administracion@`

Fecha: 2026-08-28. Solo **DEV**. **PROD no se tocó.**

## De dónde salía Gmail

El wizard de cotización mostraba Gmail **antes** de enviar porque:

1. `res.users.email` del usuario operativo = `inversionesdoralex@gmail.com`.
2. Plantilla `Sales: Send Quotation` (`mail.template` id 25) tiene
   `email_from = {{ object.user_id.email_formatted or object.company_id.email_formatted or user.email_formatted }}`.
3. `mail.compose.message._compute_authorship` renderiza esa expresión y pone
   From = Gmail del vendedor (`object.user_id`).
4. Si no hay plantilla, el mismo compute usa `env.user.email_formatted` (Gmail).
5. Graph no intervenía en el **wizard**; solo al enviar. Por eso el usuario veía Gmail.

No venía del servidor SMTP (no hay `ir.mail_server` SMTP). Graph usa el mailbox
`administracion@` de la empresa del **From ya resuelto**.

## Regla única (saliente)

Fuente de verdad: `document.company_id` → `company._dx_outgoing_address()`:

`company.email` / `dx_mail_mailbox` / `dx_mail_alias_admin`
si pertenecen al dominio de esa company y **no** son
`ventas@`, `compras@`, `info@`, `facturacion@`, `contabilidad@`.

Resultado: `administracion@<dominio de esa company>`.

Aplica a compositor, `mail.mail.send`, factura, chatter (`_message_compute_author`)
y Reply-To (`_notify_get_reply_to`). La compañía **activa** del usuario no cuenta.

## Reply-To

Reply-To = el mismo `administracion@`.

Odoo core usaría `catchall@alias_domain` para threading. Aquí **no**: el cron de
entrada lee el user mailbox `administracion@` (Graph). `catchall@` no es un buzón
licenciado. Respuestas a `administracion@` llegan al mismo mailbox de esa empresa
y no cruzan a otra.

## Alias domain Blue Elite

La plantilla técnica (company 1) heredaba `alias_domain = blueelite.net`.
Se deja vacío. Las 6 empresas operativas tienen cada una su `mail.alias.domain`.

Los aliases `ventas@` etc. siguen existiendo **solo para entrada** (CRM / buzones
funcionales). No se usan como From.

## Prueba DEV (`DX-PRIM-20260828T202237`)

Wizard real + envío Graph. Cross-company: Blue Elite activa, documento de las otras 5.

Graph SentItems: quote/invoice/po 6/6 From `administracion@` propio.
Cross BLU→REM = `administracion@rempartgroup.com`.
