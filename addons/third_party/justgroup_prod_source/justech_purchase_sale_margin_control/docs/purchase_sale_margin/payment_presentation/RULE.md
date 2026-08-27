# Regla de presentación — estados de pago (reporte)

Versión: 19.0.8.11.0  
Alcance: solo etiquetas del PDF/XLSX. **No modifica** `account.move.payment_state`.

## Proveedor (factura)

Si `amount_residual == 0` → mostrar **PAGADA**, aunque el `payment_state` técnico sea `in_payment`.

Si `amount_residual > 0`:

| payment_state | Etiqueta |
|---|---|
| not_paid | PENDIENTE |
| partial | PARCIAL |
| in_payment | EN PROCESO |
| paid | PAGADA |

## Cliente (factura)

Misma lógica de residual: si residual 0 → **Cobrada**.

## Inventario

| kind | Etiqueta Estado/Saldo |
|---|---|
| inventory (salida consumida) | CONSUMIDO |
| inventory_purchase (OC stock sin venta) | INVENTARIO DISPONIBLE / PARCIALMENTE CONSUMIDO / CONSUMIDO |
| po sin factura | SIN FACTURA |
