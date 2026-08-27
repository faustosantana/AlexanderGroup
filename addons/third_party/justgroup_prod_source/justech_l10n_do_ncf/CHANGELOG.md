## [19.0.2.30.0] — 2026-07-28 — Dashboard Fiscal (solo lectura)

- TransientModel `justech.do.fiscal.dashboard` con KPIs sobre regularización existente.
- Menú Contabilidad → Auditoría Fiscal → Dashboard Fiscal.
- Agrupación por `original_fiscal_period`; Ver 608 abre wizard sin presentar.
- Auditoría histórica mismatch void_date (sin backfill).

# Changelog — Estándar Fiscal Justech (cierre)

## [19.0.2.29.0] — 2026-07-28 — Regularización 608 período original + 607/IT-1 + actividad

### Changed
- Modelo `justech.do.fiscal.regularization` con período fiscal original (no fecha de cancelación).
- Post-cancelación directa: línea 608 automática, detección 607, IT-1 a validar, actividad al responsable configurable (Florangel).
- Badge fiscal: «Anulado» hasta presentar 608; «Anulado (608)» solo tras reportado.
- Config compañía: `justech_do_fiscal_regularization_user_id`.

### Reports companion
- `justech_l10n_do_reports` 19.0.1.24.6: exportador 608 filtra por `608_reporting_period` / período original; incluye `state=cancel`.

## [19.0.2.16.0] — 2026-07-20 — HOTFIX 2026.1.1 visualización NCF + mensajes

### Root cause
- Emisión Justech con dual-write OFF deja `justech_do_ncf` lleno y `l10n_latam_document_number` vacío.
- La lista de facturas (l10n_do_accounting) mostraba solo el campo LATAM → columna vacía pese a NCF correcto.

### Fixed
- Tree ventas/compras/NC: columna «Número de documento» usa `fiscal_ncf_display` (FDP / SoT Justech→LATAM).
- IntegrityError de unicidad NCF se traduce a UserError funcional (sin texto PostgreSQL).
- Servicio central `justech.do.fiscal.error.service`.
- Mensajes de duplicado vía duplicate.service alineados al tono funcional.

### Unchanged
- Datos históricos / NCF almacenados / dual-write OFF / Company First Mail / alertas baseline.

## [19.0.2.15.0] — 2026-07-17 — P0.1 Fuente canónica NCF + gate prefijo

### BREAKING CHANGES
Ninguno en datos históricos.

### Changed
- Gate de publicación: tipo seleccionado debe coincidir con prefijo del NCF (ventas y compras).
- Dual-write Justech→LATAM desactivado vía flag (módulo fiscal_admin).

### Unchanged
- Baseline alertas NCF (`19.0.2.14.0` / commit `aaea7f5…`).
- Unicidad v2.0; rangos; adel_freeze.

## [19.0.2.14.0] — 2026-07-16 — Alertas NCF internas consolidadas (sin correo) — BASELINE v1

**Congelamiento oficial.** Commit protegido: `aaea7f5f4730a038f005a3e6010354f9da64963a`  
Tag: `ncf-alerts-baseline-v1` — ver `docs/releases/NCF_ALERTS_BASELINE_v1.md`

### BREAKING CHANGES
Ninguno.

### NEW FEATURES
- Alertas internas consolidadas.
- Eliminación completa de correos NCF (flujo de alertas).
- Una actividad por empresa.
- Consolidación automática.
- Cierre automático.
- HTML limpio (Markup, sin etiquetas crudas visibles).

### FIXES
- Eliminado spam de actividades.
- Eliminado HTML crudo.
- Eliminadas actividades duplicadas.

### Changed
- Una sola `mail.activity` consolidada por empresa (no por rango ni por usuario).
- Eliminado `message_post` con destinatarios en el flujo de alertas (sin correo).
- Nota HTML con `Markup` (sin etiquetas visibles como texto).
- Etiqueta del modelo: «Rango autorizado de NCF»; acción «Ver rangos NCF».
- Actividades legacy por rango se cierran con nota de consolidación.

### Unchanged
- Cálculo de disponibles/estado; secuencias; multiempresa; Producción.

## [19.0.2.13.0] — 2026-07-16 — Estado y alertas multiempresa de rangos NCF

### Fixed
- Disponibles / % consumido ya no se fuerzan a 0 / 100 % solo por `state=depleted`.
- Al ampliar `sequence_end`, se recalcula estado (Agotado→Activo si hay cupo),
  se preserva `next_sequence` y se registra chatter.

### Added
- Fórmula única: autorizado / consumidos / disponibles / %.
- Prioridad de estado: Cerrado > Vencido > Agotado > Activo > Borrador.
- Alertas `mail.activity` + mensaje por compañía (preventivo/crítico/agotado/
  próximo a vencer/vencido), idempotentes por ciclo del rango.
- Cron diario `Justech NCF: alertas de rangos (multiempresa)`.
- Umbrales opcionales por rango; herencia de umbrales de compañía.
- Campo `flow_kind` (Ventas / Compras Emitidos).

### Unchanged
- No consume NCF; no crea rangos ficticios; no toca Producción;
  Compras Recibidos fuera de esta lógica.

## [19.0.2.12.3] — 2026-07-16 — Bloqueo tipo≠NCF en compras recibidas

### Added
- Al publicar documento recibido: el prefijo del NCF del proveedor debe
  coincidir con el tipo de comprobante seleccionado (E31≠B01… bloqueado).
- Mensaje claro con tipo, prefijo encontrado y NCF digitado.
- No aplica a B11/B13/B17 emitidos (Motor Fiscal Justech).

### Unchanged
- No reescribe NCF; no cambia tipo; no consume secuencia; Producción.

## [19.0.2.12.2] — 2026-07-16 — NCF del proveedor visible + sin Sugerencia

### Fixed
- `l10n_latam_document_number` («NCF del proveedor») visible y editable en
  facturas de proveedor con Tipo de registro = Documento recibido.
- Vista Justech `priority=200` supera Studio (160), que ocultaba el NCF cuando
  `l10n_latam_use_documents=False`.
- Campo requerido en borrador recibido; reutiliza el campo histórico (606).
- Duplicidad compras v2.0 también considera `l10n_latam_document_number`
  (NCF recibido histórico), no solo `justech_do_ncf`.

### Removed (UI only)
- Línea «Sugerencia» / «Sugerido por histórico…» del formulario de compras.
- Autocompletado de `justech_do_expense_type_id` en onchange y `create`.

### Unchanged
- Campo/modelo de costos y gastos; histórico; emisiones B11/B13/B17;
  secuencias/rangos; 606/607/608/609/623; Producción.

## [19.0.2.12.1] — 2026-07-14 — Hotfix void NCF sin Hellenia

### Fixed
- Wizard 100% en `justech_l10n_do_ncf` (catálogo 608 del move + «Otro» UX).
- Aviso claro si la factura tiene pagos/parcial; no toca pagos ni conciliaciones.
- `button_cancel` oculto también con NCF anulado; herencia Justech solo.
- `button_draft` no reactiva ni reutiliza NCF anulado ni borra traza 608.
- Sin dependencia de `hellenia_ux` para el flujo.

### Unchanged
- Producción; secuencias; asientos históricos; 606/607/609/623 lógica.

## [19.0.2.12.0] — 2026-07-14 — Wizard anulación NCF + Cancelar asiento

### Added
- Wizard modal `justech.do.ncf.void.wizard`: motivo 608, observación (obligatoria si Otro), ayuda 608.
- Botón «Anular NCF» abre el wizard (`action_open_void_ncf_wizard`).

### Fixed
- Motivo inaccesible: ya no exige campo oculto en el form.
- `button_cancel` (Cancelar asiento): invisible fuera de `draft` (corrige fórmula rota de `l10n_do_accounting`).
- Anulación idempotente con mensaje claro; chatter legible; no cancela el asiento contable.

### Unchanged
- Secuencias/rangos; no auto nota de crédito; 606/607/609/623 sin cambios de lógica.

## [19.0.2.11.1] — 2026-07-14 — Hotfix Cotización de referencia (PO)

### Fixed
- Cotización de referencia: enlace inequívoco vía `sale_line_id` o `origin→sale.order` (bi_convert).
- Smart button si hay múltiples cotizaciones origen.
- `partner_ref` ya no recibe el nombre de cotización desde bi_convert.
- Migración: limpia `partner_ref` solo si `partner_ref == origin == sale.order.name` (misma empresa).

### Unchanged
- Fiscal, NCF, secuencias, facturas, pagos, GL.

## [19.0.2.11.0] — 2026-07-14 — RC-FISCAL-UX-FINAL (Centro + columnas)

### Changed
- Filtro superior Tipo de Flujo (dropdown Todos / Ventas / Compras Emitidos / Compras Recibidos).
- Tarjetas KPI unificadas: Tipos / Activos / Pendientes / Sin rango.
- Columnas por flujo según UX operativa; `last_used` en Ventas y Compras Emitidos (lectura).
- Menú raíz: Fiscal República Dominicana (sin menús nuevos).

### Unchanged
- Sin inventar rangos; sin consumo NCF; DGII/histórico intactos.

## [19.0.2.10.0] — 2026-07-14 — Centro único Rangos (filtros de flujo)

### Added
- `justech.do.fiscal.range.center` + líneas unificadas:
  Todos / Ventas / Compras Emitidos / Compras Recibidos.
- KPIs superiores; ficha de detalle; columna Consume secuencia / Origen / Flujo.

### Changed
- Menú **Rangos** = Centro de Administración Fiscal (Localización Dominicana).
- Menús satélite de documentos Compras desactivados (sin duplicar).

### Unchanged
- Sin rangos ficticios; sin consumo de NCF; histórico intacto.

## [19.0.2.9.0] — 2026-07-14 — UX admin Compras + costos/gastos editables

### Added
- `justech_do_expense_type_id` editable en borrador (factura proveedor).
- Sugerencia histórica no bloqueante (`justech_do_expense_type_manual`).
- Administración: documentos recibidos LATAM; emisión B11/B13/B17; rangos Compras.
- Menú Localización Dominicana → Compras.
- Post-migrate: enlace `l10n_do_expense_type` → catálogo Justech.

### Changed
- Emisión compras: botón «Administrar rango»; nombres/ayudas operativas.

### Fixed
- El “Tipo de costos y gastos” deja de ser solo un display readonly.

## [19.0.2.8.0] — 2026-07-14 — Compras: recibidos LATAM vs emisión B11/B13/B17

### Added
- Campo `justech_do_purchase_registration_mode` en facturas de proveedor
  (`received` | `issued`).
- Modelo `justech.do.purchase.emission.config`: configuración por empresa de
  B11/B13/B17 sin inventar rangos; `emission_enabled` solo con rango activo.
- UX Compras: selector de tipo de registro; LATAM dominio recepción B+E;
  emisión Justech limitada a `is_purchase_document`.
- Post-migrate idempotente: 12 configs (4 empresas × 3 tipos) + modo `received`
  en históricos nulos.
- Tests `test_purchase_registration_mode`.

### Changed
- Assignment: documentos recibidos no consumen rangos/secuencias Justech;
  emisión sin rango bloquea con mensaje nominativo (código + nombre).
- Nombres display B11/B13/B17 con código + nombre funcional completo.

### Unchanged
- Continuidad JUSTECH B11@11 / B13@213; sin rangos ficticios; Ventas intactas.

## [19.0.2.7.0] — 2026-07-14 — Hotfix moneda DOP + vigencia NCF

### Fixed
- Oculta `account.document_tax_totals_company_currency_template` (“Impuestos DOP”)
  en facturas multicurrency; el PDF solo muestra totales en moneda del documento.
- “Válida hasta:” usa `justech_do_ncf_range_id.date_to` si `l10n_do_ncf_expiration_date`
  está vacío; oculta la etiqueta cuando no hay fecha.

### Docs
- `docs/REPORT_HOTFIX_CURRENCY_NCF_VALIDITY.md`

## [19.0.2.6.2] — 2026-07-14 — Hotfix reportes (gate DO por compañía)

### Fixed
- `is_l10n_do_invoice` usa compañía DO (`l10n_do_country_code`), no el flag latam del diario.
  Cubre borradores sin NCF; no aplica a empresas no dominicanas.

## [19.0.2.6.1] — 2026-07-14 — Hotfix reportes (Studio fingerprint)

### Fixed
- Fingerprint Studio alineado al arch real (`information_block`, `name='address'`).

## [19.0.2.6.0] — 2026-07-14 — Hotfix reportes (Studio address + gate DO)

### Fixed
- Desactiva de forma idempotente la vista Studio destructiva
  `web_studio.report_editor_customization_diff.view._web.address_layout`
  (fingerprint + inherit `web.address_layout`) para restaurar address/information_block.
- Restaura `is_l10n_do_invoice` vía herencia QWeb Justech cuando el documento DO
  tiene evidencia fiscal (`l10n_latam_*` o Motor Justech), sin forzar latam en diarios.

### Docs
- `docs/REPORT_HOTFIX_IS_L10N_DO_INVOICE.md`

## [19.0.2.5.0] — 2026-07-14 — Resolución fiscal histórica

### Changed
- Orden de resolución en factura: default persistido → histórico por empresa →
  padrón/sugerencia → regla inequívoca (sin RNC→B01 ciego).
- Onchange de partner recalcula el tipo (no hereda del cliente anterior).
- Post bloquea clientes nuevos / revisión sin comprobante con mensaje claro.

## [19.0.2.4.1] — 2026-07-13

### Fixed
- RPC_ERROR del Centro Fiscal: placeholders `_()` mixtos nombrados/`%.1f` en diagnóstico de rangos NCF.
- Defensas ante `name`/`remaining_count`/`pct_used` nulos en mensajes de stock bajo.

## [19.0.2.4.0] — 2026-07-13

### Added
- Migración controlada legacy Adel → Motor Fiscal Justech (`justech.do.ncf.migration.*`) con previsualización obligatoria.
- Reconciliación post-sync de numeración (`justech.do.ncf.reconcile.*`) — solo avanza, nunca retrocede.
- Auditoría de migración (`justech.do.ncf.migration.log`).
- Menú Motor Fiscal NCF: migración, reconciliación y auditoría.

### Changed
- Asignación en ventas auto-asignables: ya no publica en silencio sin NCF (exige diario `justech_do_use_ncf` o NCF manual / rango activo).
- Dual-write LatAm solo refleja NCF generado por Justech.

### Notes
- Secuencias Adel permanecen como histórico; `get_fiscal_number` bloqueado si Justech fiscal está activo.
- Tras sync de transacciones desde Prod: ejecutar reconciliación; no copiar rangos/`ir.sequence` de Prod.

## [19.0.2.3.1] — 2026-07-10

### Changed
- Campo `justech_do_document_type_id` oculto en formulario de cotización/pedido (`invisible="1"`).
- La herencia interna hacia la factura (`_prepare_invoice`) se mantiene intacta.
- El tipo de comprobante fiscal sigue visible en facturas (cliente/proveedor, NC/ND).

## [19.0.2.2.4] — 2026-07-10

### Fixed
- Lectura fiscal en formularios vía campos display seguros (`fiscal_*_display`) y Fiscal Data Provider.
- Estado histórico Adel: **Histórico compatible** (nunca «Incompleto» cuando hay NCF válido).
- NCF histórico visible en facturas de venta/compra sin backfill ni escritura.

### Added
- Regla permanente Cursor: auditoría de herencia XML antes de tocar vistas/menús.
- UAT de cierre (shell + visual) en `justech_dev`.

## [19.0.2.0.0] — 2026-07-10

### Added
- `justech_l10n_do_payments_withholding`: motor pagos con retenciones (wizard único).
- `justech_fiscal_admin`: Centro de Administración Fiscal + feature flags runtime.
- Menú **Auditoría Fiscal** consolidado (606–623, NCF, retenciones, centro fiscal).

### Fixed
- RPC `action_justech_open_fiscal_admin_center` en Ajustes → Fiscal Justech.
- Dependencia circular `justech_fiscal_admin` ↔ `justech_l10n_do_reports`.
- Pantalla facturas restaurada (pestaña compacta Comprobante Fiscal).
- Feature flags conectados: `ncf_motor`, `ncf_dual_write`, `duplicate_blocking`, `payments_withholding`.

### Scripts
- `fiscal-closure-run.sh`, `fiscal-standard-cleanup.py`, `fiscal-clean-install-lab.sh`.
