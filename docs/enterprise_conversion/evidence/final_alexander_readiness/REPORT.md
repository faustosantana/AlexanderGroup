# Cierre CONDITIONAL_PASS — readiness Alexander (staging)

Fecha: 2026-08-31
Entorno: **solo staging** `127.0.0.1:8269` / DB `doralex_ent_staging`
Tag previo (conservado): `DXQA-MASS-20260831`
Tag de esta fase: `DXQA-FINAL-20260831`
`PROD_TOUCHED_BY_FINAL_QA = NO`

No se envió e-CF. No se envió correo real. No se migraron rangos NCF.
No se ejecutó `03_cleanup_identify.py` como DELETE.

## 1. Backup

`FINAL_READINESS_BACKUP = PASS`

`/opt/doralex/backups/enterprise-staging/pre_final_alexander_readiness_20260831_124228`

Artefactos: `db.dump`, `filestore.tar.gz`, `custom-addons.tar.gz`, `config.tar.gz`,
compose, `odoo.conf`, SHA256 verificados, inventario QWeb/outstanding/NCF.

## 2. Recibo multi-factura

Módulo: `multi_invoice_manual_payment_prod` **19.0.1.5.5**
`justech_alexander_reports` **19.0.3.8.5** no se tocó.

Un `account.payment` → un PDF. Encabezado (empresa, logo, RNC, recibo, fecha,
socio, RNC/Cédula, moneda, método, banco/caja, referencia, monto) + tabla
(FACTURA/NCF/fechas/original/saldo antes/aplicado/saldo resultante) + pie
(TOTAL RECIBIDO/APLICADO/SALDO NO APLICADO/forma/referencia/observaciones).

Evidencia nativa (sin `force_payment_move`):

| Caso | Archivo |
|---|---|
| 1 pago → 2 facturas | `C1_receipt_multi2.pdf` |
| 1 pago → 3 facturas | `C1_receipt_multi3.pdf` |
| 1 pago → 4 facturas | `C1_receipt_multi4.pdf` |
| 1 pago → 5 facturas | `C1_receipt_multi5.pdf` + `C11_existing_407.pdf` |
| Parcial multi | `C11_receipt_partial_multi.pdf` |
| Proveedor 3 bills | `C11_vendor_receipt_multi3.pdf` |

`MULTI_INVOICE_SINGLE_RECEIPT = PASS`
`MULTI_INVOICE_RECEIPT_PDF = PASS`
`VENDOR_MULTI_INVOICE_RECEIPT_QA = PASS`
`PAYMENT_RECEIPT_BALANCE_RECONCILIATION = PASS`

Empresas DO 8–13: nativo 2/3/4 + parcial + vendor 3. El grupo de 5 se
re-renderizó desde pagos masivos existentes (p. ej. pago 407) y se ejecutó
nativo de 5 en la plantilla (company 1). No se inventaron facturas extra
para forzar un 5 en cada DO (B01 restante 6–8).

## 3. Outstanding / flujo nativo

Cuentas **ya existían** en el plan (no se crearon):

| Empresa | Receipts | Payments |
|---|---|---|
| 1 Plantilla | 101403 Outstanding Receipts | 101404 Outstanding Payments |
| 8–13 DO | 11010203 Outstanding Receipts | 11010204 Outstanding Payments |

Se asignaron a las líneas de método de los diarios banco **solo en staging QA**.

`ALEXANDER_CONFIRMATION_REQUIRED = YES` — no son definitivas sin el contador.

`OUTSTANDING_CONFIG_QA = PASS`
`NATIVE_PAYMENT_FLOW_QA = PASS`
`force_payment_move` **no** se usó en esta fase.

## 4. Márgenes / multi-PO / CxP

6 empresas operativas DO. Por empresa: A 1SO/1PO, B 1SO/2PO, C PO
parcialmente facturada, D bill parcialmente pagada, E venta+compra pagadas.
Wizard API `purchase.sale.add.purchase.wizard`: al seleccionar las OC carga
líneas (`wizard_lines_loaded` = 1 o 2). Márgenes estimados/reales no nulos.

UI operativa (staging, company 11, `DOR/SO/00040`): **Gestionar compras** →
**Vincular compra existente**. OWL 19 no persistía el onchange One2many;
`justech_purchase_sale_margin_control` **19.0.8.29.39** recarga líneas en
`write()`/`create()` al elegir la OC y deja **Cargar artículos** visible.
Verificación shell: `DOR/OC/00035` y `DOR/OC/00036` cargan 1 línea cada una
(qty_available=1, qty_needed=2). QWeb Alexander sigue en 58.

`MARGIN_QA_MASS = PASS`
`MULTI_PO_RELATION_QA = PASS`
`MARGIN_CXP_INTEGRATION_QA = PASS`

## 5. Trazabilidad

SO→factura (`sale_line_ids`), SO→PO (`origin` + `sale_line_id`), SO→multi PO,
PO→bill (`purchase_line_id`), invoice↔bills, pagos conciliados.
0 enlaces cross-company. Relación manual confirmada no se sobrescribe.
Prioridad instalada: `purchase_line → procurement → origin → product_qty_company
→ ref → analytic → heuristic` (+ `invoice_rel` / `sale_line_id` en documentos).

`TRACEABILITY_QA_MASS = PASS`
`TRACE_PRIORITY_QA = PASS`

## 6. Auditoría

Política QA temporal. Writes en `res.partner`, `sale.order`, `purchase.order`,
`account.move`, `account.payment` con before/after, usuario, datetime, company.
0 reglas TransientModel. Política restaurada.

Wizards fiscales: `justech.do.ncf.reconcile.wizard` abierto; público DENIED;
**sin** migrar rangos ni consumir NCF.

`AUDIT_LOG_MASS_QA = PASS`

## 7. DGII final

Regen 606/607 (202608) y 608 (202606, anulaciones QA). Company 11: 606=53,
607=55, 608=2. Formas de pago leídas del módulo (`payment_method_code` en
línea). 609/623 siguen N/A (sin B17 / sin retenciones Estado).

`DGII_606_FINAL = PASS`
`DGII_607_FINAL = PASS`
`DGII_608_FINAL = PASS`
`DGII_609_FINAL = NOT_APPLICABLE`
`DGII_623_FINAL = NOT_APPLICABLE`

## 8. Integridad / reportes

`AR_BALANCE_MATCH = YES`
`AP_BALANCE_MATCH = YES`
`UNBALANCED_MOVES = 0`
`MULTICOMPANY_ISOLATION = PASS`
`QWEB_BEFORE = 58`
`QWEB_AFTER = 58`
`QWEB_HASH_MISMATCH_UNEXPECTED = 0`
`REPORTS_PRESERVED = YES`

## 9. Errores

`CRITICAL_ERRORS = 0`
`HIGH_ERRORS = 0`
`MEDIUM_ERRORS = 1` (asignación QA de outstanding pendiente de confirmación
del contador; `ALEXANDER_CONFIRMATION_REQUIRED = YES`)
`LOW_ERRORS = 1` (wkhtmltopdf avisa ConnectionRefused al resolver assets
del layout; el PDF se genera igual)

## 10. Keys finales

```
FINAL_READINESS_BACKUP = PASS
MULTI_INVOICE_SINGLE_RECEIPT = PASS
MULTI_INVOICE_RECEIPT_PDF = PASS
VENDOR_MULTI_INVOICE_RECEIPT_QA = PASS
PAYMENT_RECEIPT_BALANCE_RECONCILIATION = PASS
OUTSTANDING_CONFIG_QA = PASS
NATIVE_PAYMENT_FLOW_QA = PASS
MARGIN_QA_MASS = PASS
MULTI_PO_RELATION_QA = PASS
MARGIN_CXP_INTEGRATION_QA = PASS
TRACEABILITY_QA_MASS = PASS
TRACE_PRIORITY_QA = PASS
AUDIT_LOG_MASS_QA = PASS
DGII_606_FINAL = PASS
DGII_607_FINAL = PASS
DGII_608_FINAL = PASS
DGII_609_FINAL = NOT_APPLICABLE
DGII_623_FINAL = NOT_APPLICABLE
AR_BALANCE_MATCH = YES
AP_BALANCE_MATCH = YES
UNBALANCED_MOVES = 0
MULTICOMPANY_ISOLATION = PASS
QWEB_BEFORE = 58
QWEB_AFTER = 58
QWEB_HASH_MISMATCH_UNEXPECTED = 0
REPORTS_PRESERVED = YES
CRITICAL_ERRORS = 0
HIGH_ERRORS = 0
MEDIUM_ERRORS = 1
LOW_ERRORS = 1
PROD_TOUCHED_BY_FINAL_QA = NO
FINAL_ACCOUNTING_FISCAL_QA = PASS
READY_FOR_ALEXANDER_DATA_LOAD = YES
```

**No cargar datos reales todavía.** Pedir el paquete en `ALEXANDER_DATA_REQUEST.md`.
