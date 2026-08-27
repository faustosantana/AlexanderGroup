# Doralex DEV — Configuración de las 6 empresas

> Fecha: 2026-08-27. Solo **Doralex DEV**. PROD intacto. **No** se cargaron datos
> reales/históricos. **No** hay datos oficiales de levantamiento en el proyecto
> (`docs/03_COMPANY_MATRIX.md` sigue en "Pendiente"), por lo que los datos de negocio
> quedan como **placeholder/PENDING** sin inventar nada.

## Búsqueda de datos oficiales (previa)

Se buscó en el repo (Excel/CSV/JSON/docs) razones sociales, RNC, direcciones,
correos, catálogo y rangos NCF: **no existen** en el proyecto. Se procedió con la
**estructura técnica** y placeholders, marcando lo faltante.

## Empresas (estructura creada, persistida)

6 compañías (ids 28–33), aisladas, con:

| Aspecto | Valor |
| ------- | ----- |
| Nombre | `Doralex Empresa 1..6 [PENDIENTE RAZON SOCIAL/RNC]` (placeholder) |
| Moneda | **DOP** |
| País | **DO** (República Dominicana) |
| Timezone (partner) | `America/Santo_Domingo` |
| Plan de cuentas | **`do`** — 289 cuentas por empresa |
| Impuestos | **37** por empresa (ITBIS + retenciones RD) |
| Diarios | **8** por empresa (venta, compra, banco, **caja**, + varios) |
| Almacén | **1** por empresa (+ ubicaciones + operation types) |
| Posiciones fiscales | 11 por empresa · Términos de pago: 10 |

Aislamiento verificado: cada empresa tiene su propio set de cuentas/diarios/
impuestos/almacén; sin contaminación cruzada.

## Módulos custom activos (aplican a todas las compañías)

`l10n_do_accounting`, `justech_l10n_do_base`, `justech_l10n_do_ncf`,
`justech_fiscal_admin`, `justech_accounting_recovery`, `justech_vendor_bill_po_control`,
`justech_l10n_do_adel_freeze`, `justech_purchase_sale_margin_control`,
`justech_sale_purchase_trace`, `bi_convert_purchase_from_sales`,
`justech_approval_flow`, `justech_warranty` (Wave A/B, 19 instalados).

## NCF (estructura, sin numeración real)

23 `l10n_latam.document.type` + 11 `justech.do.fiscal.document.type` disponibles.
**`justech.do.ncf.range = 0`** → `PENDING_REAL_DGII_SEQUENCE`: no se crean rangos
oficiales ni se emiten comprobantes reales hasta disponer de la numeración DGII.

## Config params Doralex (sin editar vendor)

Vía `ir.config_parameter`: `web.base.url` y `justech.approval.public.base.url` →
`https://dev.doralexgroup.cloud`; `mail.catchall.domain` → `doralexgroup.cloud`.
Guards de identidad de reportes/términos de venta: habilitados.

## Usuarios/roles

Grupos estándar por función presentes (ventas, compras, contabilidad, inventario,
RRHH, gerencia) y capacidad multiempresa validada (`allowed_company_ids`,
company switching). **No se inventaron usuarios/empleados**: la creación de usuarios
reales queda pendiente del **listado oficial**. `USERS_ROLES_CONFIG = PARTIAL`.

## Pruebas (0 FAIL / 0 ERROR / 0 CRITICAL)

- **Aislamiento funcional 36/36** (por empresa: cliente, proveedor, producto, venta,
  compra, factura cliente, factura proveedor, almacén, diario), datos revertidos.
- golden **9/9**, six-company **6/6**, repo **15/15**, runtime errors **0**.
- `DXTEST leftover = 0` (sin datos persistentes de prueba).

Evidencia: [`evidence/dev_6companies.txt`](evidence/dev_6companies.txt).

## Datos PENDIENTES (requieren archivos oficiales de levantamiento)

Razón social, nombre comercial, **RNC**, dirección, teléfono, correo, logo por
empresa; **rangos NCF DGII**; catálogo de cuentas **ampliado**; usuarios reales;
configuración fiscal final por empresa (régimen, retenciones específicas).

## Estado

`DORALEX_6_COMPANIES_CREATED = PASS` · `MULTICOMPANY_CONFIG = PASS` ·
`ACCOUNTING_RD_CONFIG = PASS` (estándar; ampliado pendiente) ·
`NCF_CONFIG = PENDING_REAL_RANGES` · `WAREHOUSE_CONFIG = PASS` ·
`SALES_PURCHASE_CONFIG = PASS` · `USERS_ROLES_CONFIG = PARTIAL` ·
`DORALEX_CONFIG_PARAMS = PASS` · `COMPANY_ISOLATION_TEST = 36/36` ·
`DORALEX_DEV_RUNTIME_ERRORS = 0`. `READY_FOR_MASTER_DATA_LOAD = YES` (estructura
lista) · `READY_FOR_FULL_DORALEX_DATA_LOAD = NO` (faltan datos oficiales + Enterprise).
