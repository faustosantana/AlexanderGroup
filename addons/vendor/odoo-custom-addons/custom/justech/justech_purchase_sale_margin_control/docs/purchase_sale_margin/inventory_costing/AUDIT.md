# Auditoría de valoración de inventario — DEV (justech_dev)

Fecha: 2026-08-11  
Entorno: https://erp.justech.do · DB `justech_dev` · servicio `odoo-dev`  
Módulo: `justech_purchase_sale_margin_control` 19.0.8.11.0

## Hallazgos DEV

| Concepto | Valor detectado |
|---|---|
| Categorías producto | 21 |
| `property_cost_method` | **standard** (todas las categorías muestreadas) |
| `property_valuation` | **periodic** (todas) |
| Tabla `stock_valuation_layer` | **No existe** en esta BD (valoración no perpetua / sin capa SVL activa) |
| `stock.move` | Disponible (sale_stock / purchase_stock) |
| Lotes/series | No requisito UAT inicial |

## Implicación para el margen

No se puede asumir SVL en todas las compañías.

Orden de resolución del costo de inventario consumido:

1. `stock.valuation.layer` ligado al `stock.move` de salida/devolución (si el modelo/tablas existen).
2. `stock.move.value` / `stock_value` si está poblado.
3. `stock.move.price_unit × qty`.
4. `product.standard_price × qty` (caso típico DEV: standard + periodic).

## Regla de negocio

- Margen de una venta = costo de las **cantidades entregadas** (salidas done), no el total de la factura/OC de compra a inventario.
- Factura proveedor de la compra a stock → **CxP / contabilidad**.
- Consumo de inventario → **costo de venta / margen** (`cost_source = inventory`).
- Prohibido sumar factura completa + valoración de salida (doble conteo).

## Estados de compra a inventario (sin venta)

| Estado | Significado |
|---|---|
| Inventario disponible | Recibido, sin consumo en ventas |
| Inventario parcialmente consumido | Parte vendida/entregada |
| Inventario consumido | Sin saldo pendiente de consumo |

Estas compras **no** se clasifican como “compra problemática sin venta” en el margen comercial.

## Devoluciones

Si existe movimiento de devolución del cliente ligado a `sale_line_id`, el costo de inventario se ajusta (resta) según la misma fuente de valoración real.
