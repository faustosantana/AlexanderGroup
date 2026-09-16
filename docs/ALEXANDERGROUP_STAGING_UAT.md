# Alexander Group — UAT STAGING (fase 2)

Fecha: 2026-09-16.
Entorno: **solo STAGING** `doralex_ent_staging` /
`doralex-enterprise-staging-odoo`. **PROD TOUCHED: NO.**

## 1. Precheck y backup (antes del `-u`)

| Dato | Valor |
| --- | --- |
| Host | `Doralexgroup` vía `ssh doralex-server` |
| Contenedor | `doralex-enterprise-staging-odoo` healthy |
| DB | `doralex_ent_staging` (PostgreSQL 16.15) |
| Bind addons | `/opt/doralex/enterprise-staging/custom-addons` → `/mnt/custom-addons` (ro) |
| Filestore | 754 archivos / 40 956 582 bytes, `doralex_ent_staging` |
| Git rama | `cursor/doralex-training-findings-86c5` |
| PROD | `doralex-production-odoo` running — no escrito |

### Versiones **antes** del overlay

| Módulo | Host / instalado |
| --- | --- |
| `justech_alexander_base` | 19.0.1.0.5 |
| `justech_alexander_reports` | 19.0.3.8.5 |
| `justech_alexander_ux` | 19.0.1.4.0 |
| `justech_alexander_microsoft_mail` | 19.0.1.0.4 |

### Backup

`/opt/doralex/backups/enterprise-staging/pre_alexander_staging_uat_20260916_183140`

- `db/doralex_ent_staging.dump` 20 MB, TOC 33 983 (`pg_restore -l` OK)
- `filestore/filestore.tar.gz` 20 MB
- `modules_before/alexander_overlay_before.tar.gz`
- `ROLLBACK.txt` (pasos exactos, solo STAGING)

## 2. Overlay (nunca `-u all`)

Primer `-u` falló: `ir.actions.report` en Odoo 19 **no tiene** campo
`context` (`propet_proforma.xml`). Se detuvo, se corrigió, se reintentó.

Segundo `-u` (log
`/opt/doralex/enterprise-staging/logs/alexander_overlay_u_20260916_183641.log`):

- EXIT 0
- Sin ParseError / ERROR / WARNING Alexander
- Cargó XML de los 4 módulos (incluido `propet_proforma.xml` y
  `sale_order_views.xml`)
- Restart **solo** `doralex-enterprise-staging-odoo` → healthy
- PROD intacto

### Versiones **después**

| Módulo | Instalado |
| --- | --- |
| `justech_alexander_base` | 19.0.1.0.6 |
| `justech_alexander_reports` | 19.0.3.9.0 |
| `justech_alexander_ux` | 19.0.1.5.0 |
| `justech_alexander_microsoft_mail` | 19.0.1.0.5 |

## 3. Rollback exacto

Ver `ROLLBACK.txt` del backup. Resumen:

1. Restaurar tarball de los 4 módulos (versiones 1.0.5 / 3.8.5 / 1.4.0 / 1.0.4).
2. `docker stop doralex-enterprise-staging-odoo`.
3. `dropdb`/`createdb` **solo** `doralex_ent_staging` + `pg_restore`.
4. Restaurar filestore STAGING.
5. `docker start doralex-enterprise-staging-odoo`.

Nunca `doralex-production-*` ni `doralex_prod`.

`ROLLBACK TESTED: NO` (restore destructivo no ejecutado; TOC + checksum sí).

## 4. Checklist UAT (ejecutado en Odoo STAGING)

Criterio: **IMPLEMENTADO Y VALIDADO** solo con prueba funcional en STAGING.

| ID | Prueba | Resultado | Evidencia |
| --- | --- | --- | --- |
| H01 | Impuestos 461–466 + cotización/pedido/factura 1 000 → 160 / 1 160 | **PASS** | `DOR/SO/00079`, `INV/2026/00067` NCF `B0100000054`; AML 41010100 1000 / 21030102 160 / 11030201 1160. Tags copiadas `*.18%` → corregidas a `base.16%`/`tax.16%`. Productos reales no reasignados. Empresa 8 **sin rango B01 activo**; post en empresa 11. NC wizard no cerrada. |
| H02 | 3 líneas, reorder/qty, desc. manual B, cambio de producto | **PASS** | `BLU/SO/00038`. Descripciones no se cruzan. Qty no pisa manual. Cambio de producto sí refresca. |
| H03 | Formulario Propet 18/16/exento/dto/qty>1 vs tax engine | **PASS** | PDF `h03_propet.pdf`. Identidades OK. Estándar **no** es Propet (`h03_std.pdf`). |
| H04 | Columnas traza solo compras; no romper trace | **PASS*** | Vista overlay 5535 con `purchase.group_purchase_user`. Traza 19.0.1.2.11 intacta. **No existe usuario solo Ventas.** `column_invisible=1` también viene de traza/márgenes. |
| H05 | Lots nativo + recepción/entrega lote y serie | **PASS** | Se **retiró** el inherit que limpiaba `groups`. Setting Lots & Serial Numbers = implied en Internal User. Persistido: lote `DXUAT-LOT-P1`, serie `DXUAT-SER-P1`. |
| H06 | Etapas ES; no traducir técnicos | **PASS** | Visible: Nuevo / Calificado / Propuesta / Ganado. Sin New/Qualified/Proposition/Won. |
| H07 | Matriz borrador vs recovery | **PASS** (diagnóstico) | Usuario facturación **sin** recovery: `button_cancel`/`unlink` de **borrador** → AccessError. Grupo vacío. No se asignaron usuarios. No se cambió seguridad. |
| H08 | Proforma sin asiento/NCF | **PASS** | `h08_proforma.pdf`. 0 `account.move` nuevos. Grupo nativo vacío; Alexander limpia `group_ids` del reporte. |
| H09 | Padrón — solo diagnóstico | **BLOCKED** | 0 filas, cron OFF, 0 config. Sin descarga. |
| H11 | Aprobación + 8 mutaciones | **PASS** (doc) | Tras aprobar, SO queda `sale`. Fingerprint cambia en qty/precio/dto/tax/partner; **no invalida** si `state` no es draft/sent. `name`, término y nota no están en el fingerprint. Código **no** modificado. |
| H12 | `client_order_ref` = PO-TEST-001 | **PASS** | Conservado, buscable, en PDF Propet. |
| H13 | 1 pago → 3 facturas + recibo | **PASS** | `INV/2026/00068–00070` residual 0; pago `PBNK1/2026/00081` 7 080; recibo lista las 3. Retención **BLOCKED** (catálogo 0). |
| H14 | Conduce 2 compañías | **PASS** | `BLU/OUT/00026`, `PIN/OUT/00023` (sesión) / PDFs `h14_r3_*.pdf`. Título CONDUCE, logo/empresa correctos, sin branding cruzado. RNC no siempre literal en HTML. |
| H15 | 16 mails exception | **PASS** | SMTP `invalid:1025` + Graph «credenciales no disponibles». No es bug del overlay. Sin envío real. Sin copiar secretos. |
| H16 | Firma por `document.company_id` | **PASS** | Mismo usuario: Blue Elite vs Piñaria → from/reply-to/firma distintos. Odoo 19 no tiene `signature` en composer; se usa HTML de empresa. |
| H17 | Hamburguesa Inicio, sin dominio | **PASS** | `navbar.xml`: Inicio + `homeMenu.toggle(true)` + `this.hm`. Sin URL hardcodeada. |

\*H04 no pudo impersonar un usuario **solo** Ventas porque no hay ninguno.

## 5. H01 — auditoría 461–466

Comparados con el ITBIS **venta 18%** de la **misma** empresa.

| Campo | 16% venta | 18% venta misma empresa |
| --- | --- | --- |
| `company_id` | 8–13 (461–466) | coincide |
| `amount` | 16 | 18 |
| `amount_type` | percent | percent |
| `type_tax_use` | sale | sale |
| `price_include` | False | False |
| `tax_group_id` | ITBIS | ITBIS |
| `tax_exigibility` | on_invoice | on_invoice |
| `country_id` | DO | DO |
| cuentas tax line | ITBIS on Sale of Goods (21030102 en DOR) | misma familia |
| tags (antes UAT) | **base.18% / tax.18%** (copia) | 18% |
| tags (después UAT) | **base.16% / tax.16%** | 18% |

No se copió un impuesto de **compra**. Sí se clonó el de **venta 18%**.
Las tags 18% en un 16% no eran conceptualmente correctas; se corrigieron
en STAGING. No se asignó el 16% a productos reales.

Asiento persistido (`INV/2026/00067`, empresa 11, DOP):

| Cuenta | Debe | Haber |
| --- | --- | --- |
| 11030201 CxC | 1 160 |  |
| 41010100 Ventas |  | 1 000 |
| 21030102 ITBIS ventas |  | 160 |

## 6. H05 — seguridad nativa de lotes

- `stock.group_production_lot` = «Manage Lots / Serial Numbers».
- Es el switch de Inventario > Configuración «Lots & Serial Numbers»
  (`group_stock_production_lot` implied en Internal User).
- Mostrar `tracking` **sin** ese grupo evadiría el gate nativo y puede
  terminar en AccessError al crear `stock.lot`.
- Overlay custom **eliminado**. Se activó el setting nativo en STAGING.

Quién debe usarlo: almacén / calidad, no vendedores genéricos.

## 7. H07 — matriz cancelar vs recovery

Módulo: `justech_accounting_recovery` 19.0.1.4.0.
`button_cancel` / `button_draft` / `unlink` exigen
`group_accounting_recovery` si el recordset no está vacío. **No**
distingue borrador vs publicado.

| Documento | Estado | Acción | Grupo nativo | Grupo custom | Observado |
| --- | --- | --- | --- | --- | --- |
| Factura | borrador | Cancelar | account invoice | Recuperación Contable | **bloqueado** sin recovery |
| Factura | borrador | Eliminar | account invoice | Recuperación Contable | **bloqueado** |
| Factura | publicada | Cancelar/draft | — | Recuperación Contable | no probado (grupo vacío) |
| Factura | publicada | Revertir | reverse invoice **o** recovery | recovery | no asignado |
| Pago | cualquiera | unlink | — | Recuperación Contable | no asignado |

**Por qué recovery pisa borradores:** SoD del módulo (mismas tres APIs).
No es overlay Alexander.

**Propuesta mínima (NO implementada):** overlay Alexander que permita
`button_cancel`/`unlink` solo si `state == 'draft'` y no hay asiento
publicado. Seguridad que se tocaría: `justech_accounting_recovery`
`account.move.button_cancel` / `unlink`. No añadir usuarios todavía.

## 8. H08 — «grupo proforma nativa vacío»

`sale.group_proforma_sales` oculta el print nativo Proforma. En STAGING
no tiene usuarios. Alexander **limpia `group_ids`** del reporte nativo
(además de etiqueta ES). No hace falta asignar el grupo. La plantilla
nativa ya hace `docs.with_context(proforma=True)` — no se usa campo
`context` (no existe en Odoo 19).

## 9. H11 — fingerprint

Cubre: partner, currency, product, qty, price, discount, taxes, totals.
**Omite:** `line.name`, `payment_term_id`, `note`, `client_order_ref`.

Tras `action_approve` el SO se **confirma**. `_justech_maybe_invalidate_approval`
solo invalida si `state in (draft, sent)`. Cambios materiales en pedido
confirmado **no** vuelven a aprobación.

| Campo | Permitió | Invalidó | Volvió a aprobación | FP cambió |
| --- | --- | --- | --- | --- |
| descripción | sí | no | no | no |
| cantidad | sí | no (ya sale) | no | sí |
| precio | sí | no | no | sí |
| descuento | sí | no | no | sí |
| impuesto | sí | no | no | sí |
| cliente | sí | no | no | sí |
| término de pago | sí | no | no | no |
| nota | sí | no | no | no |

Usuario de la prueba: `__system__` / admin STAGING. Código no cambiado.

## 10. H13 — pago y retenciones

Pago nativo (`multi.invoice.manual.payment.wizard`, **sin**
`force_payment_move`):

| Antes | Total | Residual | NCF |
| --- | --- | --- | --- |
| INV/2026/00068 | 1 180 | 1 180 | B0100000055 |
| INV/2026/00069 | 2 360 | 2 360 | B0100000056 |
| INV/2026/00070 | 3 540 | 3 540 | B0100000057 |

Un `account.payment` `PBNK1/2026/00081` / 7 080 DOP → residual 0 /
`in_payment`. Asiento: 11010203 Outstanding Receipts 7 080 / 11030201
CxC 7 080. Recibo lista las 3 facturas (`h13_recibo_persist.pdf`).

Retención: catálogo `justech.do.withholding.catalog` = **0**. No se inventó
catálogo fiscal. **BLOCKED.**

## 11. H09 — padrón (sin descarga)

| Dato | Valor |
| --- | --- |
| Módulo | `justech_l10n_do_base` |
| Modelo / tabla | `justech.do.rnc.padron` / `justech_do_rnc_padron` |
| Cron | id 31, `cron_auto_update()`, 1 h, **active=False** (noupdate) |
| Config | 0 |
| Filas | 0 |
| Fuente | servicio auto DGII del módulo (no ejecutado) |

Propuesta: crear config, dry-run, luego activar cron. **No autorizado.**

## 12. H15 / H16 correo

16 `mail.mail` exception. SMTP host `invalid`. Failure típica:
«Microsoft Mail / Credenciales Microsoft no disponibles». No es bug de
código. PROD deberá tener Graph/mailbox `administracion@` por
`company_id`. No se copiaron secretos.

Firmas: documento A → firma/from Blue Elite; documento B → Piñaria; se
resuelve `document.company_id`, no solo `env.company`.

## 13. Conteos

| | |
| --- | --- |
| UAT PASS | H01 H02 H03 H04* H05 H06 H07(diag) H08 H11(doc) H12 H13 H14 H15 H16 H17 |
| UAT FAIL | — (tras corrección overlay + persist) |
| UAT BLOCKED | H09 padrón; H13 retención (catálogo 0); H01 NC; H04 usuario solo-ventas |
| ITBIS 16 ACCOUNTING | SÍ (empresa 11) |
| TRACKING NATIVE SECURITY | SÍ (sin override groups) |
| DRAFT INVOICE CANCEL | bloqueado por recovery |
| RECOVERY GROUP | vacío, sin altas |
| PROFORMA | PASS, grupo nativo innecesario |
| DGII | no descargado |
| APPROVAL FLOW | fingerprint incompleto post-confirm |
| MULTI-INVOICE PAYMENT | PASS |
| WITHHOLDING | BLOCKED |
| EMAIL | SMTP/Graph inválidos, no código |
| MULTICOMPANY | firmas/from/conduce OK |
| ROLLBACK TESTED | NO (dump validado) |
| PROD TOUCHED | NO |
| READY FOR PROD | **NO** |
