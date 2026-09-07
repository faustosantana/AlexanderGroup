# Buzones — propuesta. Creados: 0

No se inventó personal. No se crearon cuentas.

## Usuarios Odoo reales

| PERSON | ODOO_CURRENT_LOGIN | PROPOSED_EMAIL_LOGIN | COMPANY | ROLE | MAILBOX_REQUIRED | ALIAS_ONLY |
|---|---|---|---|---|---|---|
| Alexander Piña Aquino | inversionesdoralex@gmail.com | alexander@erp.doralexgroup.cloud | 6 (multiempresa) | Operación | YES | NO |
| Administrator | admin | — | 6 | Settings (impl.) | NO | — |
| Fausto Santana | fausto@justech.do | — | 6 + técnica | Settings Justech | NO | — |

Usuario QA `dx.test.security@justech.do` está inactivo. Sin mailbox.

## Departamentales (cuando Mailcow exista)

No usar como login compartido de Odoo.

| EMAIL | TIPO | DESTINO INICIAL |
|---|---|---|
| ventas@erp.doralexgroup.cloud | alias o buzón 500 MB | alexander@ |
| compras@erp.doralexgroup.cloud | alias o buzón 500 MB | alexander@ |
| contabilidad@erp.doralexgroup.cloud | alias o buzón 500 MB | alexander@ |
| facturacion@erp.doralexgroup.cloud | alias o buzón 500 MB | alexander@ |
| almacen@erp.doralexgroup.cloud | alias o buzón 500 MB | alexander@ |
| soporte@erp.doralexgroup.cloud | alias o buzón 500 MB | alexander@ |
| postmaster@erp.doralexgroup.cloud | alias | alexander@ |
| abuse@erp.doralexgroup.cloud | alias | alexander@ |
| odoo-system@erp.doralexgroup.cloud | buzón técnico 500 MB | solo SMTP Odoo, si se crea |

Cuotas: 500 MB – 2 GB. Sin ilimitado.

Cuentas `ventas01@` / `compras01@` etc. **solo** cuando existan personas reales.

`MAILBOXES_CREATED = 0`
`ALIASES_CREATED = 0`
