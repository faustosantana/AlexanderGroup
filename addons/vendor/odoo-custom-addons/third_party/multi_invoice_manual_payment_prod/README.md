# Multi Invoice Manual Payment - Odoo 19

## 19.0.1.5.5
- Recibo único (cliente y proveedor): encabezado con empresa/RNC/recibo/fecha/
  socio/moneda/método/banco/referencia/monto; tabla FACTURA, NCF, fechas,
  monto original, saldo antes, aplicado, saldo resultante; pie con totales.
- Un `account.payment` sigue generando un solo PDF aunque cubra 2–N facturas.
- No toca `justech_alexander_reports` (QWeb Alexander permanece en 58).

## 19.0.1.5.4
- Default `group_payment=True` on standard Register Payment (except physical checks).
- Reactivate Contabilidad → Pago de Múltiples Facturas menu.
- Wizard: monto transferencia, diferencia, aviso duplicado, aviso cheque, ref en pago.
- Recibo: lista de documentos aplicados bajo el pago único.

## 19.0.1.5.3
La moneda del pago se toma del diario seleccionado.
El wizard lista facturas de distintas monedas y convierte cada monto a la moneda del pago.
