# Odoo — usuarios operativos (sin duplicar Alexander)

## Auditoría previa

| PERSON | EXISTING_USER_ID | EXISTING_LOGIN | ACTION |
|---|---|---|---|
| Luis Joel Aquino Casado | — | — | CREATE |
| Janny Chantal Montero | — | — | CREATE |
| Elianny Nicole Sanchez Javier | — | — | CREATE |
| Leopordo Jimenez | — | — | CREATE |
| Alexander Pina Aquino | 5 / partner 18 | inversionesdoralex@gmail.com | UPDATE |
| Geilin Rosario Suero | — | — | CREATE |

Alexander confirmado: **Alexander Piña Aquino**, compañías 8–13, default 11
(INVERSIONES DORALEX,S.RL.). No se creó un segundo `res.users`.
`__system__` (id 1) no se tocó.

`ir.mail_server = 0` → `ODOO_RESET_MAIL_READY = NO`. No bloquea la
creación.

## Perfiles (least privilege)

Operadores (Luis, Janny, Elianny, Leopordo):

- Sales: All Documents
- Purchase: User
- Inventory: User
- Contact Creation
- Margin ventas + compras
- Trace compras
- **No** Invoicing publish, **no** Accounting Admin, **no** Settings,
  **no** fiscal manager, **no** autoaprobación

Geilin: lo anterior + `account.group_account_invoice` + Usuario Fiscal.
No Accounting Admin, no Settings, no fiscal manager.

Alexander: se **añaden** Settings, Access Rights, Sales/Purchase/Accounting/
Inventory admin, Responsable Fiscal, Aprobador Justech, margin admin y
trace admin. Se mantienen compañías 8–13 y default Doralex. No es
superuser. No recibe `group_self_approve`.

## QA staging (documentos en SAVEPOINT, rollback)

- Cotización crear/editar/confirmar: PASS (6)
- OC crear/editar/confirmar: PASS (sin AccessError; 3 confirmaciones
  limpias; otras 3 vieron un FK de harness tras rollback, no ACL)
- Geilin: factura borrador OK; publicar bloqueado por validación RNC del
  partner QA (no AccessError, no NCF consumido)
- No-invoice: "You don't have the access rights to post an invoice."
- Settings: AccessError al crear usuarios
- `FOREIGN_MOVES_VISIBLE = 0`
- Apertura staging intacta
- No email, no e-CF, no DGII

Purchase User en Odoo 19 tiene ACL de create sobre `account.move` (facturas
de proveedor). Los operadores **no pueden publicar** factura de cliente.

## Producción

| PERSON | ODOO_USER_ID | PARTNER_ID | LOGIN_QA |
|---|---|---|---|
| Luis | 13 | 89 | PASS |
| Janny | 14 | 90 | PASS |
| Elianny | 15 | 91 | PASS |
| Leopordo | 16 | 92 | PASS |
| Geilin | 17 | 93 | PASS |
| Alexander | 5 | 18 | PASS |

`posted_out_invoices_ops = 27` (apertura intacta). NCF B1500000150 /
B1500000110 / B1300000016 sin cambio. `__system__` no tocado.
`alexander_login_rows = 1`.

## Login

Los 6 usuarios validan XML-RPC con la contraseña temporal de Odoo.
Alexander no tenía acceso Odoo previo (implementación nueva): se le asignó
la misma temporal. Debe cambiarla después del primer acceso. El login
`alexander.pina@inversionesdoralex.com` queda en el uid 5 (no se duplicó).
