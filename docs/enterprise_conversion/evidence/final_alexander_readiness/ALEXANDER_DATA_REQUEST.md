# Solicitud final a Alexander — solo lo que falta

**No cargar todavía.**  
**No repetir** lo que ya está en
`Levantamiento_Basico_Odoo_Alexander_Group.xlsx` y ya está (o se puede
mapear) en Doralex.

Auditoría: `ALEXANDER_EXCEL_VS_ODOO_AUDIT.md`.  
`FISCAL_ROWS_IN_SOURCE_EXCEL = 0` → NCF **no** vino en ese archivo.

`PROD_TOUCHED = NO`

---

## No volver a pedir

Razón social, RNC, dirección fiscal, actividad, teléfono, representante,
cédula, moneda, fecha de inicio, BANRESERVAS, número de cuenta, tipo
(corriente/ahorros), titular, cédula del titular, oficina principal.

Esos 6+6+6 registros **ya los entregaron**.

Correos Gmail/Hotmail del Excel vs `administracion@…` de Odoo: no
reescribir; solo marcar en §2 cuál queda oficial.

---

## 1. NCF / DGII reales

El Excel fiscal está **vacío**. Lo que hay en staging (B01/B04 series
`9910xxxx`) es **QA**, creado el 2026-08-29 por el sistema. No usar eso
en producción.

Por empresa DO, **solo los tipos que vayan a emitir**:

| Empresa | Tipo (B01/B02/B04/B11/B13/B14/B15/B16/B17/…) | Autorización DGII | Desde | Hasta | Próximo | Vence | ¿e-CF? |
|---|---|---|---|---|---|---|---|
| INVERSIONES DORALEX | | | | | | | |
| PIÑARIA | | | | | | | |
| DOMINION | | | | | | | |
| EL MAYUMA | | | | | | | |
| REMPART | | | | | | | |
| BLUE ELITE | | | | | | | |

También:

- ¿e-CF el día 1? (hoy el switch operativo está vacío / OFF)
- Primer período 606/607/608 a declarar en el sistema
- 609/623: no inventar. 623 solo si hay retenciones del Estado.

---

## 2. Tesorería que el Excel no trae

Ya tenemos banco, número, tipo y titular. Falta lo **contable**:

| Empresa | Diario ya creado | Cuenta GL banco (confirmar) | Outstanding cobros | Outstanding pagos | Formas DGII (01/02/03/…) | ¿Caja / chequera extra? |
|---|---|---|---|---|---|---|
| DORALEX | Banco Banreservas · DOR | | | | | |
| PIÑARIA | Banco Banreservas · PIN | | | | | |
| DOMINION | Banco Banreservas · DOM | | | | | |
| EL MAYUMA | Banco Banreservas · MAY | | | | | |
| REMPART | Banco Banreservas · REM | | | | | |
| BLUE ELITE | Banco Banreservas · BLU | | | | | |

Propuesta QA (no definitiva): cobros `Outstanding Receipts` / pagos
`Outstanding Payments` del plan.  
`ALEXANDER_CONFIRMATION_REQUIRED = YES` — no crear otras cuentas sin el
contador.

Balances del Excel (no pedir el monto otra vez):

- Doralex 5,000,000 · Piñaria 2,450,000 · Dominion 1,500,000 ·
  Mayuma 3,000,000 · Rempart 4,600,000 · Blue Elite 1,250,000
- Fecha escrita `05//08/2026` — **¿5 ago o 8 may 2026?**
- ¿Autorizan el asiento de apertura con esos montos?

Correo oficial por empresa (marcar uno; ya los tenemos ambos):

| Empresa | Excel | Odoo UX | ¿Cuál usar? |
|---|---|---|---|
| DORALEX | inversionesdoralex@gmail.com | administracion@inversionesdoralex.com | |
| PIÑARIA | piñariascomercializadora@gmail.com | administracion@pinariagroup.com | |
| DOMINION | dominionsrl@hotmail.com | administracion@dominion-business.com | |
| EL MAYUMA | inversioneselmayuma@gmail.com | administracion@elmayuma.com | |
| REMPART | rempartsrl@hotmail.com | administracion@rempartgroup.com | |
| BLUE ELITE | bluelitesrl@hotmail.com | administracion@blueelite.net | |

---

## 3. Plan, impuestos, retenciones

- Visto bueno del plan ya instalado (l10n_do). No reenviar el catálogo.
- ¿OC obligatoria en factura de proveedor? Hoy `disabled`.
- Retenciones ISR/ITBIS: catálogo **solo si las usan**. Hoy 0 configs;
  623 = N/A hasta que existan.

---

## 4. Maestros reales (cero en Odoo hoy)

Staging solo tiene DXQA / DX TEST. Eso **no** es Alexander.

Plantilla mínima:

**Clientes / proveedores:** tipo, RNC o cédula, nombre DGII, dirección,
correo real, condición de pago, comprobante default (después de validar
RNC). Proveedor: NCF recibido vs B11/B13/B17 emitido.

**Productos / servicios:** nombre, precio, costo, impuesto, ¿stock o
consumo?

No enviar partners de prueba.

---

## 5. Saldos e historia (si aplican)

Marcar sí/no. Si no migran historia, no hace falta el detalle.

- Trial balance de corte por empresa  
- CxC / CxP abiertas (socio, NCF, fechas, residual)  
- Anticipos / créditos no aplicados  
- Inventario real (el Excel no trajo almacenes extra; la oficina ya está)  
- Activos fijos  
- ¿NCF históricos al 607/608 o solo saldos?

---

## 6. Personas y plantilla USD

- Alexander Piña Aquino **ya es 1 usuario** con las 6 empresas
  (`inversionesdoralex@gmail.com`). No crear 6 usuarios.
- Falta: rol/grupos (el Excel dejó cargo/nivel vacíos) y si hay **otras
  personas**.
- ¿Quién anula NCF (608)? ¿Sigue el flujo de aprobación para publicar?
- Compañía 1 `Plantilla técnica (no operativa)` USD/US: **KEEP** por
  ahora. ¿La dejan inactiva / sin fiscal DO?

---

## 7. Fuera de esta solicitud

- Re-pedir RNC, direcciones, bancos, números de cuenta  
- Certificados e-CF / envío DGII  
- Dump Justgroup  
- Cargar maestros ahora  
- Borrar `DXQA-MASS-20260831` (solo identificar)

Cuando respondan §§1–6 se diseña la carga. No antes.
