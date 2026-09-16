# ALEXANDERGROUP / DORALEX — FINAL VISUAL & FUNCTIONAL ACCEPTANCE

Fecha: 2026-09-16. Entorno: **PRODUCCIÓN** `doralexgroup.cloud`.
Criterio: VISIBLE + USABLE + CORRECTO + ROLE-APPROPRIATE + BROWSER.

---

H01 ITBIS16:
UI: Impuestos 16% ITBIS SALE (y purchase) visibles en Contabilidad → Impuestos por compañía. Nombre `16% ITBIS`.
BROWSER: lista filtrada DOR — PASS.
STATUS: **PASS** (selector en línea de cotización no se abrió para no editar documentos reales).

H02 DESCRIPTIONS:
UI: Formato Propet separa Producto vs Descripción y elimina repetición del nombre.
BROWSER: PDF DOR/SO/00013 sin nombre duplicado.
STATUS: **PASS**

H03 PROPET:
NAME: **Formato Propet** (ya no Formulario). Título PDF FORMATO PROPET.
SALE REPORT: botón de cabecera + PDF cotización.
INVOICE REPORT: botón + PDF en factura draft (sin NCF).
FIELDS: empresa/logo/RNC, cliente, OC/PO, fechas, vendedor, líneas con/sin ITBIS, dto, totales, bancos, términos.
BROWSER: DOR/SO/00013 y BLU/SO/00004.
STATUS: **PASS**

H04 SALES COLUMNS:
Ventas (sin grupo Compras): sin Comprado/Pend. compra/Pend. recibir; pestaña y smart button Abastecimiento ocultos.
STATUS: **PASS**

H05 TRACKING:
QUANTITY: Odoo 19 muestra `Track Inventory` + método **By Quantity** (= sin lote/serie). Visible en DX-TEST-STK.
LOT / SERIAL: dropdown completo requiere escritura de producto; no se ejecutó recepción/entrega real en PROD.
STATUS: **PARTIAL**

H06 CRM ES:
Nuevo / Calificado / Propuesta / Ganado. Sin etapas en inglés.
STATUS: **PASS**

H07 DRAFT CANCEL:
Botón **Cancelar** en factura draft. Cancela a Cancelled. Sin mensaje de recuperación contable. Sin NCF.
STATUS: **PASS**

H08 PROFORMA:
Botón **Proforma**. PDF FACTURA PROFORMA + badge. Sin asiento/NCF.
STATUS: **PASS**

H09 DGII:
OFF: ICP vacío, cron inactivo, botón Validar oculto.
STATUS: **PASS**

H10 RECOVERY:
DRAFT: cancel permitido a facturación.
POSTED: botones recovery siguen restringidos al grupo Recuperación Contable.
STATUS: **PASS**

H11 APPROVAL:
OFF compañías 8–13. Menú solo histórico.
STATUS: **PASS**

H12 CUSTOMER PO:
VISIBLE: `Número de Orden de Compra del Cliente` junto al cliente. Valor PO-CLIENTE-2026-001.
SALE / REPORT: sí en Formato Propet.
INVOICE: campo `ref` relabel; `_prepare_invoice` copia OC si falta.
SEARCH: filtro lista/búsqueda.
STATUS: **PASS**

H13 WITHHOLDINGS:
UI: `display_name` humano (RET ISR — …). `Cómo se calcula` en ficha (técnico 20% presunto → RD$3,000; ITBIS 30 sobre ITBIS).
CALC: verificado en ficha ORM.
RECEIPT: QWeb con bruto/ISR/ITBIS/otras/neto. Pagos UAT existentes están canceled; no se postearon nuevos.
Menú Administrar retenciones sigue exigiendo **Role / Administrator** en la action window vendor (no se otorga admin de sistema).
STATUS: **PARTIAL**

H14 DELIVERY NOTE:
VISIBLE ACTION: botón **Conduce** en pedido y en entrega (nombre del report = Conduce).
DESIGN: logo/empresa, pedido, solicitada/entregada, sin precios.
COMPANY: DOR y botón presente en BLU.
STATUS: **PASS**

H15 EMAIL:
Composer: From / Reply-To `administracion@inversionesdoralex.com`. Sin enviar.
STATUS: **PASS**

H16 SIGNATURE:
Bloque de firma del usuario en composer. Firma HTML de empresa inyectada por documento. No se envió correo real.
STATUS: **PASS** (preview; no envío)

H17 HOME/NAVBAR:
Sin t-on-click custom. Inicio nativo + title Inicio. Apps, switch empresa, navbar OK.
STATUS: **PASS**

LOGIN:
Formulario visible, logout vuelve al login. user_switch anónimo sigue sin montar; no bloquea.
STATUS: **PASS**

SCREENSHOTS:
COUNT: 16+ (botones, PDFs Propet/Proforma/Conduce, OC/PO, CRM, tracking, Cancelar, ITBIS 16, login, email).

MODULES CHANGED:
justech_alexander_base 19.0.1.0.9
justech_alexander_ux 19.0.1.6.6
justech_alexander_reports 19.0.3.10.2
justech_alexander_microsoft_mail 19.0.1.0.6

MODULES UPDATED:
los cuatro anteriores, `-u` dirigido. Sin `-u all`. Frozen intactos.

PROD HEALTH:
ODOO: doralex-production-odoo healthy
DB: doralex_prod
WEBCLIENT: /odoo carga

FAILED ITEMS:
- H05 LOT/SERIAL: no se hizo recepción/entrega de prueba en PROD.
- H13: catálogo admin UI bloqueado por Role/Administrator de la action vendor; cálculo/nombres sí existen.

REMAINING BLOCKERS:
Abrir Administrar retenciones exige Role/Administrator (seguridad nativa de ir.actions.act_window). Usar wizard de pago CxP para seleccionar reglas (nombres humanos). No otorgar admin de sistema al rol operativo.

FINAL STATUS: **PARTIAL**
