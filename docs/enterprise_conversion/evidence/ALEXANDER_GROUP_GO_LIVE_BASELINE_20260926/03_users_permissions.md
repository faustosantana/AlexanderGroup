# 03 — Users / permissions

| USER | LOGIN | ACTIVE | DEFAULT | ALLOWED | SALES | PURCHASE | INVOICING | ACCOUNTING_ADMIN | ODOO_ADMIN | APPROVER | STATUS |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Alexander Pina Aquino | alexander.pina@inversionesdoralex.com | yes | 11 | 8-13 | yes | yes | yes | yes | yes | yes | PASS functional admin |
| Luis Joel Aquino Casado | luis.aquino@inversionesdoralex.com | yes | 11 | 8-13 | yes | yes | no | no | no | no | PASS operator |
| Janny Chantal Montero | janny.montero@inversionesdoralex.com | yes | 11 | 8-13 | yes | yes | no | no | no | no | PASS operator |
| Elianny Nicole Sanchez Javier | elianny.sanchez@inversionesdoralex.com | yes | 11 | 8-13 | yes | yes | no | no | no | no | PASS operator |
| Leopordo Jimenez | leopordo.jimenez@inversionesdoralex.com | yes | 11 | 8-13 | yes | yes | no | no | no | no | PASS operator |
| Geilin Rosario Suero | geilin.rosario@inversionesdoralex.com | yes | 11 | 8-13 | yes | yes | yes | no | no | no | PASS invoicing |
| Fausto Santana | fausto@justech.do | yes | 11 | 1,8-13 | mgr | mgr | no | yes | yes | admin | implementer (expected) |

Self-approval group empty. Operators AccessError on `res.users` create and on invoice post (Janny/Leopordo explicit: "You don't have the access rights to post an invoice.").
