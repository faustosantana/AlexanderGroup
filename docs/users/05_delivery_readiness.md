# Auditoría de entrega — 7 septiembre 2026 (PROD)

Corte read-only. Impresiones sobre documentos **ya existentes**, con
SAVEPOINT + rollback. Facturas posteadas y adjuntos no cambiaron
(27 / 434 antes y después).

## Veredicto

`DELIVERY_READY = YES`

Se puede entregar hoy. No se escribió nada en producción.

## Tu usuario (Justech)

| Campo | Valor |
|---|---|
| LOGIN | fausto@justech.do |
| USER_ID | 8 |
| ACTIVE | YES |
| CAN_ENTER | YES |
| Settings | YES |
| Empresas | 1 + 8–13 (default Doralex) |
| Último login | 2026-08-30 |

No se tocó ni se reseteó tu contraseña. Entra a
https://doralexgroup.cloud con `fausto@justech.do` y la clave que ya usas.

## Equipo (Odoo login XML-RPC)

6/6 PASS: Luis 13, Janny 14, Elianny 15, Leopordo 16, Alexander 5,
Geilin 17. Todos activos, compañías 8–13, default 11. Operadores sin
Settings ni facturación. Geilin factura, sin Settings. Alexander admin
funcional. Un solo uid 5. Login gmail viejo = 0.

## Microsoft 365

6/6 `AccountEnabled=TRUE`, `O365_BUSINESS_PREMIUM`, SMTP = UPN,
`ForceChangePasswordNextSignIn=TRUE`, sin roles admin.
`admin@` / `alex@` onmicrosoft no se tocaron.
`mailboxSettings` sigue 403 (permiso de la app); el buzón se valida por
`mail` + `SMTP:` primario.

## Impresiones (existentes, sin crear)

| Tipo | Documento | Resultado |
|---|---|---|
| Factura cliente | INV/2026/00021 (B1300000016) Doralex | PASS |
| Cotización | BLU/SO/00004 Blue Elite | PASS |
| Orden de compra | PIN/OC/00005 Piñaria | PASS |
| Entrega | DOR/OUT/00012 Doralex | PASS |
| Recibo de pago | — | SKIP (no hay payment posteado) |

La factura de apertura ya traía `SOURCE_DOCUMENT_STATUS=MISSING_PDF`
(dato histórico). No se alteró.

## Baseline

- Facturas cliente posteadas ops = 27
- NCF B1500000150 / B1500000110 / B1300000016 presentes y posted
- `__system__` intacto
- HTTP `/web/login` = 200, `/web/health` = 200

## No bloquean la entrega

- `ODOO_RESET_MAIL_READY = NO` (sin `ir.mail_server`)
- Licencia Standard es temporal; Alexander la cambia cuando venza
- Recibo de pago: no hay uno real que imprimir (no se inventó)
