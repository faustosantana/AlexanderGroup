# Información exacta a pedir a Alexander (antes de carga real)

No cargar todavía. Esto es el paquete mínimo para go-live contable/fiscal.

## 1. Empresas y legal

Por cada empresa operativa (hoy 6 DO + plantilla US):

- Razón social oficial (DGII) y nombre comercial
- RNC y confirmación de que coincide con padrón
- Dirección fiscal, teléfono, correo oficial
- Actividad económica / código
- ¿La plantilla USD (company 1) debe quedar inactiva / sin `justech_do_fiscal_enabled`?

## 2. NCF / DGII

Por empresa DO, **solo lo que vayan a usar**:

- Tipos autorizados reales (no asumir B02/B11/B13/B17)
- Número de autorización DGII
- Prefijo, rango inicio/fin, próximo a usar, vigencia (`date_from` / `date_to`)
- ¿Emiten B02 consumo? ¿B11 informal? ¿B13 gastos menores? ¿B15 gubernamental? ¿B16 exportación? ¿B17 exterior?
- Secuencias de notas de crédito B04
- Política: ¿e-CF se usará? (hoy switch operativo vacío / OFF)
- Período de primera declaración 606/607/608 que deben generar en el sistema

## 3. Bancos y tesorería

Por empresa:

- Bancos, cuentas, moneda, número de cuenta
- Diario banco Odoo a usar
- Cuentas contables de **Outstanding Receipts** y **Outstanding Payments** (hoy no están en las líneas de método; el pago Odoo 19 no crea asiento sin ellas)
- Formas de pago DGII (01 efectivo, 02 cheque, 03 transferencia, etc.) que usan de verdad
- Chequeras / transferencias / cajas

## 4. Plan contable y diarios

- Confirmación de que el plan actual (cuentas 11030201 CxC, 41010100 ventas, ITBIS, etc.) es el definitivo
- Diarios de venta / compra / banco / caja / misceláneos
- Cuentas de gasto 606 (códigos 01–11): cuál usan por tipo de compra
- ¿Requieren OC obligatoria en facturas de proveedor? (hoy `vendor_bill_po_policy = disabled`)

## 5. Impuestos

- ITBIS 18% bienes / servicios / importaciones: qué impuestos Odoo deben quedar activos
- Exentos / propina / restaurante si aplican
- Retenciones ISR / ITBIS: catálogo, tasas, cuentas, vigencia. **Hoy 0 configs.** Sin esto no hay 623 ni withholding en pagos.

## 6. Clientes y proveedores (carga)

Plantilla mínima por partner:

- Tipo (empresa / persona)
- RNC o cédula
- Nombre oficial DGII
- Dirección, correo **real** (no usar los DXQA)
- Condición de pago
- Cuenta analítica / vendedor si aplica
- Tipo de comprobante default (B01 vs B02) **después** de validar RNC
- Para proveedores: si facturan con NCF recibido (B01/B14/…) o si Alexander emite B11/B13/B17

No reutilizar partners `DXQA*` ni `DX TEST*`.

## 7. Productos / tarifas

- Lista de productos/servicios a cargar
- Precio, costo, impuesto venta/compra
- Cuentas de ingreso/gasto
- ¿Inventario real o solo servicio/consumo?

## 8. Saldos de apertura

Si van a entrar con historia:

- Trial balance por empresa a fecha de corte
- CxC abierta: factura, socio, NCF, fecha, vencimiento, residual, moneda
- CxP abierta: igual + NCF del proveedor + tipo 606
- Anticipos / créditos no aplicados
- ¿Migran NCF históricos al 607/608 o solo saldos?

## 9. Usuarios y aprobaciones

- Usuarios, correos, roles (contable, facturación, tesorería, gerente fiscal)
- ¿Sigue el flujo `justech_approval_flow` para publicar facturas?
- Quién anula NCF (608)

## 10. Correo y documentos

- Servidor SMTP / Microsoft 365 a usar (hoy hay un mail server en staging; no enviar a terceros)
- Logos, pie de factura, cuentas bancarias que deben verse en QWeb Alexander (58 plantillas)
- Textos legales de factura / cotización / recibo

## 11. Márgenes y traza (si lo usarán el día 1)

- ¿Toda venta lleva OC de compra?
- Costos adicionales a capturar
- Usuarios del módulo de márgenes

## 12. Lo que NO pedir todavía

- Datos de e-CF productivos
- Certificados digitales
- Envío a DGII
- Dump de producción Justgroup
- Limpieza de `DXQA-MASS-20260831` (primero autorizar el script de identificación)

Cuando entreguen 1–8, se puede diseñar la carga. No antes.
