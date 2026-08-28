# Documentación funcional — Justech Garantías

## Objetivo
Controlar las garantías de los productos vendidos y gestionar los reclamos (RMA)
asociados, con vigencia automática y trazabilidad.

## Flujo principal
1. En la ficha del producto se define **Meses de garantía**.
2. Al **validar una factura de cliente**, por cada línea con un producto que tenga
   meses de garantía se genera una garantía:
   - Productos sin serie → garantía **Activa**.
   - Productos con seguimiento por serie → garantía en **Borrador** (hay que asignar
     el número de serie y luego **Activar**).
3. La **fecha de vencimiento** se calcula como `fecha de inicio + meses`.
4. Un proceso diario marca como **Vencidas** las garantías activas cuyo vencimiento
   ya pasó.

## Reclamos (RMA)
- Desde la garantía se registran reclamos con descripción del problema.
- Flujo: `Borrador → Enviado → En proceso → Resuelto / Rechazado`.
- Al **resolver** un reclamo, la garantía activa pasa a estado **Reclamada**.

## Estados de la garantía
| Estado | Significado |
|--------|-------------|
| Borrador | Creada, pendiente de activar (p. ej. falta asignar serie). |
| Activa | Vigente. |
| Vencida | Expiró la vigencia. |
| Reclamada | Tiene un reclamo resuelto. |
| Anulada | Invalidada manualmente. |

## Permisos
- **Usuario de Garantías**: gestiona garantías y reclamos.
- **Responsable de Garantías**: además puede eliminar registros.
