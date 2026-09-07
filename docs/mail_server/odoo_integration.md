# Integración Odoo — no aplicada

`ODOO_SMTP_READY = NO`
`ODOO_IMAP_READY = NO`
`ODOO_PASSWORD_RESET_EMAIL = NOT_TESTED`

Regla: no cambiar logins, `ir.mail_server`, IMAP ni Graph en prod
hasta `MAIL_SERVER_QA = PASS` en el VPS de correo.

## Mapeo actual (prod, 2026-09-07)

| ODOO_USER_ID | CURRENT_LOGIN | NEW_LOGIN propuesto | MAILBOX | COMPANY | STATUS |
|---|---|---|---|---|---|
| 5 | inversionesdoralex@gmail.com | alexander@erp.doralexgroup.cloud | sí | 6 empresas (default Doralex) | PROPUESTO — no aplicado |
| 2 | admin | no cambiar | no | 6 empresas (default Blue Elite) | implementación |
| 8 | fausto@justech.do | no cambiar | no | 6 + compañía técnica | implementación Justech |

Alexander sigue **un solo** `res.users`. No duplicar por empresa.

Cuando el correo exista:

1. Backup de prod.
2. Actualizar el usuario 5 (`login` + `email`) al mailbox nuevo. No crear otro user.
3. SMTP Odoo: 587 STARTTLS autenticado hacia `mail.erp.doralexgroup.cloud`.
   Cuenta técnica `odoo-system@erp.doralexgroup.cloud` solo si hace falta
   (hoy `ir.mail_server = 0`; From oficial sigue `administracion@` de cada
   dominio corporativo M365).
4. Password reset: probar **solo en staging**.
5. IMAP 993: no conectar buzones departamentales hasta validar loops.

## From corporativo vs login ERP

| Uso | Dirección |
|---|---|
| Login Odoo (fase 1) | `@erp.doralexgroup.cloud` |
| From fiscal / documentos | `administracion@` dominio de cada empresa (M365, no tocar) |
| Alias departamento ERP | `ventas@erp…` etc. — routing, no login compartido |

No mezclar catchall M365 con fetchmail de Mailcow.

## Mailgate

No implementar Odoo mailgate. Primero SMTP + (si hay caso) IMAP.
