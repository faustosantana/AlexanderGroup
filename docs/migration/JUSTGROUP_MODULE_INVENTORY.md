# Inventario y clasificación de módulos (Justgroup → Doralex)

> Fecha: 2026-08-27. **Estado del audit real de Justgroup: `JUSTGROUP_ACCESS_REQUIRED`.**
>
> `erp.justech.do` resuelve a `207.244.242.58`, pero **no se dispone de credenciales**
> (SSH ni admin Odoo) para auditar su instalación. Por regla, **no** se copia su base
> de datos ni datos comerciales, y no se inventa el contenido de su instancia. La
> matriz de abajo se completa con: (a) módulos **estándar** ya instalados y validados
> en Doralex DEV, y (b) módulos **custom Justech conocidos** por su nombre/versión
> (referencias operativas), marcados como pendientes de acceso para auditar/copiar.

## Cómo completar el audit real (cuando haya acceso)

Necesito **una** de estas vías (solo lectura, sin tocar su producción):
- Acceso SSH a `207.244.242.58` (usuario + llave/clave), o
- Credenciales de administrador de Odoo (XML-RPC/UI) de `erp.justech.do`, o
- Un export del listado de módulos (`ir.module.module`) y de `custom-addons`.

Con eso ejecuto la auditoría técnica (ver `JUSTGROUP_TECHNICAL_REFERENCE.md`) y
completo versiones exactas, dependencias, cron, QWeb, Studio, seguridad, etc.

## Clasificación (valores de ACTION)

`REQUIRED` · `OPTIONAL` · `NOT_APPLICABLE` · `REQUIRES_ADAPTATION` ·
`BLOCKED_BY_ENTERPRISE_SOURCE`

## A) Módulos estándar (baseline Doralex DEV — instalados)

| MODULE | SOURCE | ENTERPRISE_REQUIRED | APPLIES_TO_DORALEX | ACTION | REASON |
| ------ | ------ | ------------------- | ------------------ | ------ | ------ |
| base, web, mail | Community | No | Sí | REQUIRED | Núcleo (ya instalado) |
| contacts | Community | No | Sí | REQUIRED | Maestros de contactos |
| crm | Community | No | Sí | REQUIRED | Gestión comercial |
| sale_management | Community | No | Sí | REQUIRED | Ventas |
| purchase | Community | No | Sí | REQUIRED | Compras |
| stock | Community | No | Sí | REQUIRED | Inventario |
| account | Community | No | Sí | REQUIRED | Contabilidad/Facturación |
| l10n_do | Community | No | Sí | REQUIRED | Localización RD (chart/impuestos) |
| hr, hr_holidays | Community | No | Sí | REQUIRED | RRHH base |
| calendar | Community | No | Sí | REQUIRED | Agenda |
| account_accountant | Enterprise | **Sí** | Sí | BLOCKED_BY_ENTERPRISE_SOURCE | Contabilidad full (licencia) |
| web_studio | Enterprise | **Sí** | Sí (Dev) | BLOCKED_BY_ENTERPRISE_SOURCE | Prototipado (licencia) |
| documents, sign | Enterprise | **Sí** | Por evaluar | BLOCKED_BY_ENTERPRISE_SOURCE | Licencia |

## B) Módulos custom Justech conocidos (pendientes de acceso a Justgroup)

> Datos tomados de referencias operativas (nombres/versiones). **No** auditados ni
> copiados: requieren acceso a la fuente y revisión de hardcodes antes de reutilizar.

| MODULE | VERSION | CUSTOM | APPLIES_TO_DORALEX | ACTION | REASON |
| ------ | ------: | ------ | ------------------ | ------ | ------ |
| justech_l10n_do_payments_withholding | 19.0.1.7.2 | Sí | Probable (RD) | REQUIRES_ADAPTATION | Retenciones RD; auditar hardcodes/compañía; requiere fuente |
| multi_invoice_manual_payment_prod | 19.0.1.5.4 | Sí | Por evaluar | REQUIRES_ADAPTATION | Pago manual multi-factura; revisar acoplamiento |
| justech_purchase_sale_margin_control | 19.0.8.29.38 | Sí | Opcional | OPTIONAL | Control de margen; útil pero no crítico |
| justech_sale_purchase_trace | 19.0.1.2.9 | Sí | Opcional | OPTIONAL | Trazabilidad venta/compra |
| _(otros justech_* / OCA / terceros)_ | — | — | — | JUSTGROUP_ACCESS_REQUIRED | Se completará tras la auditoría |

> Ninguno de estos se ha copiado a `custom-addons` todavía (falta fuente legítima
> y auditoría de hardcodes). Al obtenerlos: escanear con
> `tools/scan_module_hygiene.py`, adaptar multiempresa, instalar **primero en DEV**.

## Resumen (estado actual)

| Categoría | Conteo |
| --------- | -----: |
| Estándar Community REQUIRED (instalados en DEV) | 11 (+deps: 90 total) |
| Enterprise BLOCKED_BY_ENTERPRISE_SOURCE | ≥4 (studio/documents/sign/accountant) |
| Custom Justech conocidos (pendientes) | 4 (por auditar/adaptar) |
| Copiados a AlexanderGroup | **0** (pendiente de acceso) |
| Datos comerciales de Justgroup copiados | **0** |
