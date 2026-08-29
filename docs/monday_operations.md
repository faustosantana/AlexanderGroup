# Operación del lunes (DEV listo; PROD no desplegado)

## Compañía activa

Seleccionar la empresa **del documento** antes de crear.  
Si el usuario tiene Blue Elite activa y abre un documento Doralex, el PDF/NCF/correo deben seguir a Doralex. Si algo mezcla identidad: **no enviar**.

## Cotización

Ventas → Pedido → Nuevo. Cliente real (no `DX QA` en producción).  
Enviar con plantilla de la compañía. Verificar From `administracion@dominio`.

## Factura + NCF

Facturación → Factura. Tipo de comprobante (B01/B02/…) según el cliente.  
Publicar. El NCF lo asigna el motor.  
Si falta rango activo o el diario no tiene Motor NCF: **no forzar NCF a mano**.

En DEV los rangos `B0199…` son QA. En PROD no existen hasta cargarlos.

## Pago y recibo

Registrar pago desde la factura (pago / registrar).  
Imprimir recibo (A5). Anticipo sin factura aplicada debe decir **PAGO NO APLICADO / ANTICIPO**.

## Nota de crédito

Desde la factura → nota de crédito (flujo core).  
Requiere permiso de NC fiscal / Recuperación Contable. Hoy el usuario operativo **no lo tiene**.  
Verificar NCF B04 y NCF afectado.

## Compra

Compras → RFQ / PO. El PDF no es factura.  
Factura de proveedor: NCF del proveedor (documento recibido), no consumir rango de ventas.

## Qué no hacer

- No facturar en PROD hasta cargar rangos autorizados.
- No reutilizar NCF.
- No resetear secuencias DGII.
- No usar clientes `DX QA`.
- No inventar términos, website, sello, QR o e-CF.
- No desplegar este módulo a PROD sin autorización.
