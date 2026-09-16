# Informe DEV — Hallazgos reunión Doralex

Fecha: 2026-09-16.
Entorno de trabajo: STAGING `doralex_ent_staging` / código en
`justech_alexander_*`. **PROD no se tocó.**

## 1. Resumen ejecutivo

El inventario READ-ONLY confirma Odoo **19.0 Enterprise (20260324)** con
localización dominicana y overlay Alexander. Varios hallazgos son
**configuración o nativo no activado**, no bugs de core. Se versionaron
correcciones solo en módulos `justech_alexander_*`. No se editaron módulos
congelados ni el vendor. No hay cambios contables históricos ni NCF.

## 2. Estado de los 17 hallazgos

| ID | Estado | Causa raíz |
| --- | --- | --- |
| 01 ITBIS 16% | CORREGIDO (STAGING) | Existía 16% solo en compras. Creado 16% **venta** por empresa (ids 461–466), clon del 18% venta. No asignado a productos. |
| 02 Descripciones | CORREGIDO (código) | `sale.order.line.name` no estaba aislado al cambiar `product_id`. No hay override Justech que mezcle líneas; se refuerza por producto. |
| 03 Formulario Propet | CORREGIDO | No existía reporte extra. Nuevo print opcional con importes nativos. |
| 04 Columnas cotización | CORREGIDO | `justech_sale_purchase_trace` las muestra a ventas. Overlay las limita a compras. |
| 05 Rastrear inventario | CORREGIDO / CONFIGURACIÓN | `tracking` nativo exige `stock.group_production_lot`. Overlay lo muestra si `is_storable`. |
| 06 CRM español | CORREGIDO (STAGING + código) | Etapas/equipos demo en inglés; renombrados a Nuevo/Calificado/Propuesta/Ganado y Ventas/… |
| 07/10 Cancelar / recovery | REQUIERE DECISIÓN | Grupo Recuperación Contable **sin usuarios**. SoD bloquea también borradores. |
| 08 Proforma | CORREGIDO | Nativo `sale.action_report_pro_forma_invoice` existía, grupo vacío, título EN. |
| 09 Padrón DGII | BLOQUEADO / CONFIGURACIÓN | Cron inactivo, **0 filas**, sin config. No se descarga DGII. |
| 11 Aprobaciones | DOCUMENTADO | Fingerprint invalida si cambia partner/líneas/precio/tax. Sin cambio de flujo. |
| 12 OC/PO cliente | CORREGIDO | Reutilizado `client_order_ref`. |
| 13 Retenciones / recibo | CORREGIDO (lectura) | Recibo nativo ya lista facturas; se añaden retenciones/neto si existen. |
| 14 Conduces | CORREGIDO | Delivery Slip nativo; título **CONDUCE** + branding por `company_id`. |
| 15 Correo | CONFIGURACIÓN | STAGING SMTP neutralizado; 16 mails en exception. Sin bridge nuevo. |
| 16 Firmas | CORREGIDO | Firma de usuario global; ahora firma = usuario + HTML de la empresa del documento. |
| 17 Dashboard | CORREGIDO | Hamburguesa → Home Menu nativo, etiqueta «Inicio». Sin URL de dominio. |

## 3. Archivos / módulos modificados

Módulos: `justech_alexander_base` 19.0.1.0.6, `justech_alexander_reports` 19.0.3.9.0,
`justech_alexander_ux` 19.0.1.5.0, `justech_alexander_microsoft_mail` 19.0.1.0.5.

Configuraciones propuestas (STAGING): crear impuesto venta 16%; renombrar etapas CRM;
activar lote/serie o usar overlay; **no** asignar recovery/proforma sin decisión.

Permisos: **ningún usuario promovido a Admin**. Columnas de traza quedan con
`purchase.group_purchase_user`. Recovery group sigue vacío.

## 4. Matriz permisos (H07/H10) — actual vs propuesta

| Rol | A Borrador cancelar/borrar | B Publicada cancelar/revertir | C Restablecer a borrador | D Recuperación contable |
| --- | --- | --- | --- | --- |
| Vendedor | NO | NO | NO | NO |
| Facturación (`group_account_invoice`) | HOY NO / propuesto SÍ | NO | NO | NO |
| Contador (`group_account_user`) | HOY NO / propuesto SÍ | NO salvo grupo fiscal | HOY NO | NO |
| Gerente contable (`group_account_manager`) | HOY NO | Fiscal + recovery | HOY NO | HOY NO (grupo vacío) |
| Recuperación Contable | SÍ | SÍ | SÍ | SÍ |
| Administrador | no usar como solución | no usar como solución | no usar como solución | no usar como solución |

Propuesta de mínimo privilegio (requiere autorización):

1. Asignar `justech_accounting_recovery.group_accounting_recovery` a 1–2
   gerentes contables (p. ej. Alexander Piña, Fausto), no a vendedores.
2. Decidir si el borrador (A) se libera para Facturación sin recovery
   (exige overlay sobre `justech_accounting_recovery`; no implementado).

## 5. H11 — comportamiento actual (sin cambio)

1. Crear: vendedor.
2. Modificar: vendedor en `draft`/`sent`.
3. Aprobar: `justech_approval_flow.group_approver` / manager; admin bypass.
4–6. Cambio material → fingerprint distinto → solicitud **Invalidada** →
   reaprobación (o bypass).
7. Disparan: partner, moneda, producto, qty, precio, descuento, impuestos, totales.
   **No** dispara: solo `name` de línea.
8–10. Snapshot HTML, chatter, request, usuario y fecha de bypass.

## 6. H09 — padrón DGII

| Dato | Valor |
| --- | --- |
| Fuente | `justech.do.rnc.padron` / `justech.do.rnc.padron.auto.service` |
| Fecha | no hay filas |
| Frecuencia | cron 1 hora, **inactive** |
| Si DGII no responde | no hay config; la UI queda en pending/not_found |
| PROD | no descargar ni reemplazar |

## 7. Pruebas ejecutadas

- `python3 -m pytest tests/test_training_findings.py tests/test_alexander_modules.py tests/test_alexander_reports.py tests/test_alexander_microsoft_mail.py -q`
- Inventario y hallazgos READ-ONLY en STAGING (impuestos, reportes, etapas, padrón=0, recovery vacío).
- Identidades Propet (18%, descuento, exento) en `propet_math.py`.

Pruebas de UI / PDF / SMTP real / pago con retención **pendientes de upgrade
de módulos en STAGING** (código en repo; no desplegado a contenedor).

## 8. Riesgos y regresiones

- Upgrade de `justech_alexander_ux` hereda vistas de traza: si el xpath de
  columnas no existe en otra base, fallaría el `-u`. STAGING sí tiene traza.
- Mostrar `tracking` sin grupo lote permite configurar serie a más usuarios
  (intencional). El inventario lote sigue exigiendo operaciones stock.
- Crear 16% venta no asigna productos: hay que elegir artículos.
- SMTP STAGING sigue neutralizado: no probar correo real ahí.

Regresiones encontradas en código: ninguna en pytest estructural.

## 9. Rollback

```text
git revert <commits de este PR>
# o bajar versiones:
# justech_alexander_base 19.0.1.0.5
# justech_alexander_reports 19.0.3.8.5
# justech_alexander_ux 19.0.1.4.0
# justech_alexander_microsoft_mail 19.0.1.0.4
```

Impuesto 16% venta creado en STAGING: archivar (`active=False`), no borrar
si ya se usó en borradores. Etapas CRM: revertir nombres New/Qualified/…

## 10. PROD (no ejecutar)

READY FOR PROD: **NO**.

Cambios propuestos para PROD (tras UAT STAGING y autorización):

1. Upgrade overlay Alexander (versiones de este PR).
2. Crear 16% ITBIS **venta** por empresa (clon 18% venta).
3. Activar print Propet / Proforma (nativo).
4. Decisión recovery + padrón (importación controlada, no en caliente).

Indisponibilidad estimada: recarga de workers 1–3 minutos. Sin `-u all`.

Comandos de deploy (solo cuando se autorice; **no ejecutados**):

```bash
# backup
ssh doralex-server '… dump doralex_prod …'
# sync addons Alexander únicamente
# docker exec doralex-production-odoo odoo -d doralex_prod -u \
#   justech_alexander_base,justech_alexander_reports,justech_alexander_ux,justech_alexander_microsoft_mail \
#   --stop-after-init --no-http
```

Backup requerido: dump DB + filestore + `odoo.conf` de PROD.
Post-deploy: imprimir cotización estándar y Propet; verificar logos por
empresa; no fuga de firmas; ITBIS 16% solo en productos asignados;
padrón no tocar; NCF intactos.

## STATUS DEV

- PRECHECK: HECHO (`docs/ALEXANDERGROUP_PRECHECK.md`)
- HALLAZGOS CORREGIDOS: 01 (STAGING), 02, 03, 04, 05 (vista), 06 (STAGING+código), 08, 12, 13 (recibo), 14, 16, 17
- HALLAZGOS PENDIENTES: 07/10 (decisión), 09 (padrón vacío), 11 (solo doc), 15 (SMTP staging)
- TESTS: estructurales + identidades Propet
- REGRESIONES: ninguna en pytest
- MULTIEMPRESA: compose/firma/reportes siguen `document.company_id`
- CONTABILIDAD: sin asientos históricos
- DGII: padrón 0; no descargado
- EMAIL: firma por empresa en código; SMTP STAGING inválido
- ROLLBACK: revertir PR / bajar versiones overlay
- PROD TOUCHED: NO
- READY FOR PROD: NO
