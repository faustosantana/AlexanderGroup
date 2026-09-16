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

## 2. Estado de los 17 hallazgos (reclasificado tras UAT STAGING)

Un hallazgo solo es **IMPLEMENTADO Y VALIDADO** si se probó en Odoo STAGING.
Detalle y evidencia: `docs/ALEXANDERGROUP_STAGING_UAT.md`.

| ID | Estado | Causa raíz / UAT |
| --- | --- | --- |
| 01 ITBIS 16% | IMPLEMENTADO Y VALIDADO | 461–466 venta 16%. Tags 18%→16%. Factura persistida 1 000/160/1 160. No masivo a productos. |
| 02 Descripciones | IMPLEMENTADO Y VALIDADO | Aislado a `product_id`. UAT 3 líneas sin cruce. |
| 03 Formulario Propet | IMPLEMENTADO Y VALIDADO | Print extra. Identidades 18/16/exento/dto OK. Estándar intacto. |
| 04 Columnas cotización | IMPLEMENTADO PENDIENTE UAT | Overlay + `column_invisible` nativo/traza. No hay usuario solo Ventas. |
| 05 Rastrear inventario | IMPLEMENTADO Y VALIDADO | **Sin** override de `groups`. Setting nativo + flujo lote/serie persistido. |
| 06 CRM español | IMPLEMENTADO Y VALIDADO | Nuevo/Calificado/Propuesta/Ganado. Sin etapas demo EN. |
| 07/10 Cancelar / recovery | REQUIERE DECISIÓN | Recovery pisa **borradores**. Grupo vacío. Propuesta mínima no implementada. |
| 08 Proforma | IMPLEMENTADO Y VALIDADO | Sin asiento/NCF. `group_ids` limpios; no hace falta el grupo nativo. |
| 09 Padrón DGII | BLOQUEADO | 0 filas, cron OFF, 0 config. Sin descarga. |
| 11 Aprobaciones | IMPLEMENTADO PENDIENTE UAT | Fingerprint no cubre nota/término/desc. Post-confirm no invalida. Sin cambio de código. |
| 12 OC/PO cliente | IMPLEMENTADO Y VALIDADO | `client_order_ref` PO-TEST-001 en SO/búsqueda/PDF. |
| 13 Retenciones / recibo | IMPLEMENTADO PENDIENTE UAT | Pago 3 facturas VALIDADO. Retención BLOQUEADA (catálogo 0). |
| 14 Conduces | IMPLEMENTADO Y VALIDADO | 2 compañías, CONDUCE, sin branding cruzado. |
| 15 Correo | CONFIGURACIÓN | 16 exception = SMTP `invalid` + Graph sin credenciales. |
| 16 Firmas | IMPLEMENTADO Y VALIDADO | `document.company_id` ≠ `env.company`. From/firma A≠B. |
| 17 Dashboard | IMPLEMENTADO Y VALIDADO | Inicio / Home Menu nativo. Sin dominio hardcodeado. |

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
- `tracking` queda nativo (`stock.group_production_lot`). No se evade el
  grupo. El setting Lots & Serial Numbers se activó en STAGING.
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

## STATUS DEV + STAGING UAT

- PRECHECK: HECHO (`docs/ALEXANDERGROUP_PRECHECK.md`)
- STAGING UAT: HECHO (`docs/ALEXANDERGROUP_STAGING_UAT.md`)
- HALLAZGOS IMPLEMENTADO Y VALIDADO: 01, 02, 03, 05, 06, 08, 12, 14, 16, 17
- HALLAZGOS IMPLEMENTADO PENDIENTE UAT: 04 (sin usuario solo-ventas), 11 (fingerprint post-confirm), 13 (retención)
- HALLAZGOS REQUIERE DECISIÓN: 07/10 recovery vs borrador
- HALLAZGOS BLOQUEADO / CONFIGURACIÓN: 09 padrón, 15 SMTP
- MODULE UPDATE STAGING: 19.0.1.0.6 / 19.0.3.9.0 / 19.0.1.5.0 / 19.0.1.0.5
- STAGING BACKUP: `/opt/doralex/backups/enterprise-staging/pre_alexander_staging_uat_20260916_183140`
- TESTS: estructurales + UAT Odoo STAGING
- REGRESIONES: primer `-u` falló por `context` en `ir.actions.report`; corregido
- MULTIEMPRESA: compose/firma/conduce por `document.company_id`
- CONTABILIDAD UAT: ITBIS 16 + pago triple persistidos en STAGING (no históricos reales de negocio)
- DGII: padrón 0; no descargado
- EMAIL: SMTP/Graph STAGING inválidos
- ROLLBACK: dump validado; restore destructivo no ejecutado
- PROD TOUCHED: NO
- READY FOR PROD: NO
