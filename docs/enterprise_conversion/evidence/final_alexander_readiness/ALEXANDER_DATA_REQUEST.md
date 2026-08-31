# Paquete definitivo de solicitud de datos a Alexander

**No cargar todavía.** Staging ya está en
`READY_FOR_ALEXANDER_DATA_LOAD = YES`. Esta lista es lo que hay que pedir
antes de diseñar la carga real.

`ALEXANDER_CONFIRMATION_REQUIRED = YES` en tesorería (cuentas outstanding).

## 1. Empresas y legal

Por cada empresa operativa (6 DO + decisión sobre plantilla US):

- Razón social oficial (DGII) y nombre comercial
- RNC y confirmación de que coincide con padrón
- Dirección fiscal, teléfono, correo oficial
- Actividad económica / código
- ¿La plantilla USD (company 1) debe quedar inactiva / sin fiscal DO?

## 2. NCF / DGII

Por empresa DO, **solo lo que vayan a usar**:

- Tipos autorizados reales (no asumir B02/B11/B13/B17)
- Número de autorización DGII
- Prefijo, rango inicio/fin, próximo a usar, vigencia
- ¿Emiten B02, B11, B13, B15, B16, B17?
- Secuencias B04
- ¿e-CF en el día 1? (hoy switch operativo vacío / OFF)
- Primer período 606/607/608 a declarar en el sistema

Hoy en staging los rangos emitidos activos son **solo B01 y B04**.

## 3. Bancos y tesorería (plantilla por cuenta real)

Completar una fila por cada cuenta bancaria real:

| Campo | Valor Alexander |
|---|---|
| Empresa | |
| Banco | |
| Número de cuenta | |
| Moneda | |
| Tipo de cuenta (corriente / ahorro / caja) | |
| Cuenta contable banco | |
| Cuenta transitoria de cobros (Outstanding Receipts) | |
| Cuenta transitoria de pagos (Outstanding Payments) | |
| Métodos de pago permitidos | |
| Forma de pago DGII (01/02/03/…) | |
| Diario Odoo a usar | |

### Propuesta QA vista en staging (NO definitiva)

El plan ya tiene estas cuentas. En QA se asignaron a las líneas de método
del diario banco para que Odoo 19 cree el asiento **sin** `force_payment_move`.
El contador debe confirmar o sustituir:

| Empresa | Diario QA | Cobros (propuesta) | Pagos (propuesta) |
|---|---|---|---|
| Plantilla técnica | Bank | 101403 Outstanding Receipts | 101404 Outstanding Payments |
| BLUE ELITE | Bank | 11010203 Outstanding Receipts | 11010204 Outstanding Payments |
| PIÑARIA | Bank | 11010203 Outstanding Receipts | 11010204 Outstanding Payments |
| DOMINION | Bank | 11010203 Outstanding Receipts | 11010204 Outstanding Payments |
| INVERSIONES DORALEX | Bank | 11010203 Outstanding Receipts | 11010204 Outstanding Payments |
| EL MAYUMA | Bank | 11010203 Outstanding Receipts | 11010204 Outstanding Payments |
| REMPART | Bank | 11010203 Outstanding Receipts | 11010204 Outstanding Payments |

`ALEXANDER_CONFIRMATION_REQUIRED = YES`

No crear otras cuentas outstanding sin esa confirmación.

También pedir: chequeras, cajas, formas DGII reales (01 efectivo, 02 cheque,
03 transferencia, etc.).

## 4. Plan contable y diarios

- Confirmación del plan (CxC 11030201, ventas 41010100, ITBIS, etc.)
- Diarios venta / compra / banco / caja / misceláneos
- Cuentas de gasto 606 (códigos 01–11)
- ¿OC obligatoria en facturas de proveedor? (hoy `vendor_bill_po_policy = disabled`)

## 5. Impuestos

- ITBIS 18% bienes / servicios / importaciones activos
- Exentos / propina / restaurante si aplican
- Retenciones ISR / ITBIS: catálogo, tasas, cuentas, vigencia.
  **Hoy 0 configs.** Sin esto 623 y withholding en pagos siguen N/A.

## 6. Clientes y proveedores

Plantilla mínima:

- Tipo (empresa / persona)
- RNC o cédula
- Nombre oficial DGII
- Dirección, correo **real** (no `DXQA*`)
- Condición de pago
- Tipo de comprobante default (B01 vs B02) **después** de validar RNC
- Proveedores: NCF recibido (B01/B14/…) vs B11/B13/B17 emitido por Alexander

## 7. Productos / tarifas

- Lista, precio, costo, impuestos, cuentas
- ¿Inventario real o servicio/consumo?

## 8. Saldos de apertura

Si entran con historia:

- Trial balance por empresa a fecha de corte
- CxC / CxP abiertas: socio, NCF, fechas, residual, moneda
- Anticipos / créditos no aplicados
- ¿Migran NCF históricos al 607/608 o solo saldos?

## 9. Usuarios y aprobaciones

- Usuarios, correos, roles
- ¿Sigue `justech_approval_flow` para publicar?
- Quién anula NCF (608)

## 10. Correo y documentos

- SMTP / Microsoft 365
- Logos y textos legales (QWeb Alexander = 58, no tocar)
- Cuentas bancarias que deben verse en factura/recibo

## 11. Márgenes y traza (si día 1)

- ¿Toda venta lleva OC?
- Costos adicionales
- Usuarios del módulo

El motor ya validó 1 venta ↔ varias OC (carga de líneas al seleccionar OC).

## 12. Lo que NO pedir / no hacer todavía

- Datos de e-CF productivos, certificados, envío a DGII
- Dump Justgroup
- Carga de partners/productos reales
- Limpieza de `DXQA-MASS-20260831` (solo identificación)

Cuando entreguen 1–8 **y** confirmen el §3 outstanding, se diseña la carga.
No antes.
