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

`ir.mail_server = 0` → `ODOO_PASSWORD_RESET_READY = NO`. No bloquea la
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

## Login

Los 5 usuarios nuevos validaron XML-RPC en staging. Alexander conserva su
contraseña Odoo anterior (no se interrumpió su acceso). El login nuevo
`alexander.pina@inversionesdoralex.com` queda en el mismo uid 5.
