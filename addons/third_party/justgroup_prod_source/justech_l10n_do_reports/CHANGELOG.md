# Changelog — justech_l10n_do_reports

## 19.0.1.24.7 — 2026-07-28 — Menú Dashboard Fiscal bajo Auditoría Fiscal

- Menú Dashboard Fiscal + Centro de Regularización (orden 1–2).
- Renombre Reportes 607/608; sin cambio de exportadores.


## 19.0.1.24.6 — 2026-07-28 — 608: período fiscal original

### Changed
- Exportador 608: período por `justech_do_608_reporting_period` / `original_fiscal_period` / `invoice_date`.
- No filtrar por fecha de anulación/cancelación interna.
- Dominio incluye asientos `cancel` voided (cancelación directa).

## 19.0.1.24.5 — 2026-07-16 — 606: inconsistencia tipo≠NCF

### Added
- Validación defensiva en exportador 606: si el tipo seleccionado no coincide
  con el prefijo del NCF almacenado → incompleto / no exportable.
- Mensaje: «Inconsistencia fiscal: el tipo E31 no coincide con el NCF …».
- El exportador no modifica ni reconstruye el NCF.

## 19.0.1.24.2 — 2026-07-13

### Fixed
- 623: catálogo Gobierno global + legado `RET5%`; elegibilidad sin exigir conciliación bancaria.
- Carga de período vacía con mensaje accionable (empresa/fechas/causas).
- Chatter de revisión fiscal: HTML vía `Markup` (sin tags crudos).

## 19.0.1.24.0 — 2026-07-11

- ACL de lectura para `justech.do.dgii.period` (AbstractModel) — evita AccessError al invocar utilidades de período DGII.
- Menús de Auditoría Fiscal restringidos a grupos del Centro Fiscal.

## 19.0.1.20.0 — 2026-07-10

- Estabilización menú Auditoría Fiscal: 14 opciones bajo Contabilidad, nombres DGII exactos.
- Corrección Odoo 19: `group_ids` en menús Pendientes y Centro Fiscal.
- Clasificación fiscal desactivada en menú de auditoría.
