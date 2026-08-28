# Multi Invoice Manual Payment - Odoo 19

## 19.0.1.5.4
- Default `group_payment=True` on standard Register Payment (except physical checks).
- Reactivate Contabilidad → Pago de Múltiples Facturas menu.
- Wizard: monto transferencia, diferencia, aviso duplicado, aviso cheque, ref en pago.
- Recibo: lista de documentos aplicados bajo el pago único.

## 19.0.1.5.3
La moneda del pago se toma del diario seleccionado.
El wizard lista facturas de distintas monedas y convierte cada monto a la moneda del pago.
