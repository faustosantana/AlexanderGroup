# Changelog — justech_l10n_do_payments_withholding

## 19.0.1.6.11 — 2026-07-28 (UX configuración retenciones)

### Changed (UI only)
- Formulario de catálogo: sección «Cuenta contable para esta empresa» con Empresa,
  Estado (badge), Cuenta (una línea) y Naturaleza (Activo/Pasivo/…).
- Advertencias como banners Odoo; se ocultan al corregir el estado.
- Tabla por empresa: Empresa / Estado / Cuenta / Naturaleza / Vigencia.
- Botones «Configurar cuenta» / «Editar configuración» (navegación UI).
- Campos técnicos (tipo Odoo, código separado, checkbox activa, warning Char)
  ocultos en la vista principal; permanecen en el modelo.

### Notes
- Sin cambios de lógica, resolución, validaciones, permisos ni datos.
- Despliegue controlado a Producción desde 19.0.1.6.10.

## 19.0.1.6.10 — 2026-07-28 (DEV — Fase 3 fix + PROD harden UAT)

### Fixed
- `compute_withholding_amount`: prorratea siempre contra `amount_total` cuando hay
  `applied_amount` (excepto `base_type=applied_amount`). Evita sobre-retención en el
  último pago parcial que cubría el residual completo.

### Changed
- Specs `UAT-RET-*` excluidos del sync de producción (solo tests / context explícito).
- Post-migrate 19.0.1.6.10: quarantine UAT + configs pendientes inactivas.

### Notes
- Producción: upgrade controlado desde 19.0.1.6.7. Sin remediación histórica.

## 19.0.1.6.9 — 2026-07-28 (DEV — Fase 2 integración wizard)

### Changed
- Wizards de pago (`justech.payment.partner.wizard`, `account.payment.register`)
  resuelven cuenta **solo** vía `_get_withholding_account` / `resolve_for_payment`.
- Selector de retenciones: únicamente activas, configuradas, vigentes y compatibles.
- Preview en tiempo real: empresa, cuenta, código, naturaleza, %, estado, vigencia.
- Validación fail-closed antes de postear; bloqueo de diarios RET01/RET02 en pagos nuevos con catálogo.
- Asiento de pago re-resuelve cuenta con el servicio único en `_prepare_move_withholding_lines`.
- `get_account_for_company` bloqueado bajo contexto `justech_payment_withholding`.

### Added
- Tests `justech_withholding_phase2` (parciales, ISR/ITBIS, multiempresa, multimoneda, cancelación).

### Notes
- Solo DEV. Sin migraciones de datos. Sin archivar RET*. Sin tocar PROD ni históricos.

## 19.0.1.6.8 — 2026-07-28 (DEV — Fase 1 base contable)

### Added
- Modelo `justech.do.withholding.company.config` (cuenta por empresa, estados, chatter).
- Servicio único `_get_withholding_account` (fail-closed, sin fallback a banco/diario).
- Bootstrap automático de configs para todas las empresas (+ empresas nuevas).
- UI: sección CONFIGURACIÓN CONTABLE POR EMPRESA + cuenta efectiva.
- Asistente «Configurar cuentas de retenciones».
- Validación anti-liquidez / anti-banco / anti-otra empresa / archivadas.
- Advertencia legado RET01/RET02 en formulario de pago (sin cambiar asientos).
- Tests `justech_withholding_phase1`.
- Contrato JAIOS documentado (sin LLM).

### Notes
- Solo DEV. No remedia históricos. No archiva RET*. No despliega Producción.
- Flujo de pagos con retención (wizard) aún no usa el servicio nuevo (Fase 2).

## 19.0.1.6.7 — 2026-07-28 (Producción)

### Changed — Mejora UX - Facturas relacionadas en Pagos
- Navegación mejorada; apertura directa de factura, contacto y pago.
- Visualización de NCF/e-CF.
- Balance pendiente desde residual contable.
- Limpieza de información técnica (Detalle NCF, Estado fiscal, DGII).
- Mejora de usabilidad para Contabilidad y Tesorería.
- Modal «Detalle por factura» operativo.

### Notes
- Desplegado en Producción 2026-07-28.
- Incluido en el producto estándar / futuras instalaciones.

## 19.0.1.6.6 — 2026-07-27

### Added (UX only — DEV)
- Sección **Facturas relacionadas** enriquecida: factura (enlace), NCF/e-CF, contacto,
  total, aplicado, saldo, estado de pago, estado fiscal, detalle NCF y botones Abrir.
- Sync de líneas de detalle al publicar pago y botón «Actualizar detalle».
- Fallback lista (no chips) si aún no hay líneas de aplicación.
- Tests `justech_payment_related_invoices_ux`.

### Notes
- No altera conciliación, asientos, montos de pago ni lógica fiscal.
- Producción: **no desplegado** en este cambio (esperar validación funcional).

## 19.0.1.6.2 — 2026-07-15

### Fixed
- ACL operativa: `account.group_account_invoice` puede `read/create/unlink` en
  `justech.payment.application.line` (requerido por el wizard al sincronizar
  aplicación pago↔factura). Sin `write` (el flujo solo crea/reemplaza líneas).
- No eleva a Contabilidad/Administrador; ACL manager CRUD intacta.

## 19.0.1.6.1 — 2026-07-13

### Fixed
- Catálogo de retenciones global (`company_id` vacío) + override por empresa; ACL Administrador de Retenciones.
- Legado `RET5%` alineado a 623 (código DGII / affects_623) sin recalcular asientos.
- Retenciones navegables en pago y factura; stamp 623 reconoce códigos Gobierno.

## 19.0.1.5.0 — 2026-07-10

### Changed
- Flujo único operativo: el botón de factura `Registrar pago` abre `justech.payment.partner.wizard`.
- Prefill de partner/facturas al abrir desde `account.move`.
- Acciones/menús de `multi.invoice.manual.payment.wizard` sin binding UI (módulo conservado por histórico).

### Notes
- Default fiscal del cliente vacío → **P2 mejora UX futura** (la factura resuelve tipo/NCF; no es bloqueo).

## 19.0.1.3.1 — 2026-07-10

- Estabilización wizard unificado cobro/pago (banco, método, retenciones).
- Eliminación menú duplicado Administrar Retenciones.
- Scripts de diagnóstico y limpieza de pago de prueba.
