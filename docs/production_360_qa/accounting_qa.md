# Contabilidad QA

## Flujos

Por empresa (DOR PIN DOM MAY REM BLU):

- Factura cliente B01 TEST posteada, journal `INV` / Ventas, `justech_do_use_ncf=True`
- ITBIS 18% en líneas de producto/servicio; descuento 10% en servicio
- Asiento posted; residual 0 tras pago parcial + pago total
- NC B04 via `account.move.reversal` **solo** con grupo Recuperación Contable
- Factura vencida (fecha 2026-06-01 / venc. 2026-06-15) abierta
- Anticipo DOR RD$ 75 no aplicado
- Vendor bill recibida (LATAM B01 + tipo gasto 09) + pago

## Recovery

`can_recover_accounting_document`: admin True, operacional False.  
`check_accounting_recovery` **no** exceptúa Administrador: sin el grupo, `refund_moves` lanza AccessError. QA otorgó el grupo a `__system__` para poder emitir NC. No se asignó al usuario operacional.

## CxP

6 `in_invoice` TEST posted. Residual 0 (pagadas). Listado por proveedor/compañía no vacío.

## Pagos multi-factura

`multi_invoice_manual_payment_prod` NOT_INSTALLED. Pagos nativos 1:1 PASS.
