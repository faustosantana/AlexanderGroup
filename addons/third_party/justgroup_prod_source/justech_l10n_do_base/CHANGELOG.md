# Changelog — justech_l10n_do_base

## [19.0.1.27.1] — 2026-07-24 — HOTFIX e-CF proveedor 14 dígitos en FDP

### Fixed
- `NCF_RE` / `_normalize_ncf` aceptan secuencias 7–12 (totales 10–15) para
  e-NCF de proveedor con longitud 14 (ej. `E3100000106285`) además del e-CF
  DGII de 13 y el NCF clásico de 11.
- `fiscal_ncf_display` deja de quedar vacío en facturas recibidas publicadas
  cuando el NCF está almacenado en `l10n_latam_document_number`.

### Unchanged
- No reescribe datos fiscales; solo lectura/normalización de display.

## [19.0.1.27.0] — 2026-07-17 — P0.1 Fuente de verdad NCF

### Changed
- `is_dual_write_enabled`: default **OFF** si no hay flag (antes ON).
- Helper `get_ncf_source_of_truth`: emisión=Justech, recibido=LATAM, lectura=FDP.

### Unchanged
- FDP solo lectura; umbrales de alerta; baseline de alertas NCF (otro módulo).

## [19.0.1.26.0] — 2026-07-16 — Umbrales de alerta NCF por empresa

### Added
- `justech_do_ncf_alert_threshold_preventive` (default 20).
- `justech_do_ncf_alert_threshold_critical` (default 5).
- `justech_do_ncf_alert_expiry_days` (default 15).

### Changed
- `justech_do_ncf_alert_days` queda como legado (oculto en formulario).

## [19.0.1.25.2] — 2026-07-16 — Consistencia tipo ↔ prefijo NCF

### Added
- `get_selected_document_type_prefix`, `get_ncf_prefix`,
  `check_type_ncf_prefix_consistency` en Fiscal Data Provider (solo lectura).
- Permite bloquear publicación/exportación cuando el tipo seleccionado no
  coincide con el prefijo del NCF almacenado, sin reescribir el NCF.


## [19.0.1.25.0] — 2026-07-14 — Catálogo tipos de costos y gastos (606)

### Added
- Modelo `justech.do.dgii.expense.type` (códigos DGII 01–11) administrable.
- Menú Configuración → Localización Dominicana → Compras → Tipos de costos y gastos.
- ACL: lectura operativa; escritura Settings / Administrador Fiscal.

### Unchanged
- El valor operativo se guarda en la factura; no se impone como regla del proveedor.

## [19.0.1.24.0] — 2026-07-14 — Prefijos recibidos Compras + nombres B11/B13

### Added
- `PURCHASE_RECEIVED_DOC_PREFIXES` (B01–B04, B14–B16, E31–E47) para dominio LATAM
  de documentos recibidos en Compras.
- `PURCHASE_DOC_FULL_NAMES` para display `B11/B13/B17 — nombre funcional`.

### Changed
- Nombres catálogo B11/B13 alineados a DGII (Proveedor Informal / Gastos Menores).
- `display_name` usa guión tipográfico `—`.

## [19.0.1.23.0] — 2026-07-14 — Catálogo fiscal compartido multiempresa

### Fixed
- Tipos de comprobante DGII (`justech.do.fiscal.document.type`) pasan a catálogo
  compartido (`company_id` vacío). Evita AccessError al resolver B01/B02/B14/B15
  cuando el usuario opera en Omni/Just Office/PlugSafe con switcher sin JUSTECH.
- Lectura ACL para `sales_team.group_sale_salesman` (solo lectura).
- Constraint `unique(prefix)` alineada al catálogo global.

### Unchanged
- Rangos NCF, secuencias y consumo siguen aislados por empresa.

## [19.0.1.22.0] — 2026-07-14 — Configuración fiscal histórica

### Added
- Estados de configuración fiscal: Confirmado por histórico / Validado por padrón /
  Pendiente — cliente nuevo / Requiere revisión / No aplica.
- Reconstrucción del comprobante por defecto desde facturas publicadas (por empresa).
- Acción «Confirmar desde histórico» sin tocar documentos ni consumir NCF.

### Changed
- Clientes históricos consistentes ya no se degradan a «Pendiente de validar».
- `justech_do_get_default_sale_document_type(company=)` usa histórico confirmado.

## [19.0.1.21.0] — 2026-07-11 — Gate Final Producción v1.0

### Changed
- Versión de release certificada tras Gate Final (Datos/Operación/Seguridad/Infra/Go-Live) en `erp.justech.do` / `justech_dev`.
- Evidencia: `evidence/gate-final-produccion-v1/GO_LIVE_CERTIFICATION.md`.

## [19.0.1.20.0] — 2026-07-11 — Padrón DGII Enterprise

### Fixed
- Lock concurrente con `pg_advisory_lock` + `FOR UPDATE NOWAIT`.
- Si la importación falla tras mutar, restaura automáticamente el snapshot vigente.
- Rollback ACL alineado a Administrador Fiscal / Settings.
- `run_hour` aplicado al programar `next_run_at` y como ventana del cron.
- Cron horario sincronizado con `auto_update_enabled` (activo/inactivo).

### Added
- Adjunto del archivo fuente en historial para reintento real (`source=retry`).
- Acción «Reintentar con este archivo» y servicio `retry_last_failed`.
- Campo `cron_active` en configuración; guía restore/reimportación en status.

## [19.0.1.19.0] — 2026-07-11 — Contactos: cédula + padrón

### Fixed
- Validación DGII también para personas con cédula (11 dígitos), no solo RNC empresa (9).
- Visibilidad del bloque «Validar con DGII» para tipo persona/cédula.
- Integridad de padrón: logs `running` huérfanos ya no marcan el padrón como «a medias».

### Changed
- `_compute_justech_do_rnc_valid` y `action_justech_validate_rnc` alineados a longitudes 9/11.

## [19.0.1.15.0] — 2026-07-11 — Administración padrón DGII

### Added
- Historial de importaciones (`justech.do.rnc.padron.import.log`).
- Configuración de actualización automática (`justech.do.rnc.padron.config`).
- Servicios de importación por lotes, integridad, snapshot/rollback y descarga DGII.
- Cron de actualización automática (frecuencia configurable, default 45 días).
- Administración del padrón restringida a `base.group_system`.

## [19.0.1.14.0] — 2026-07-11 — Contactos RNC + padrón DGII

### Added
- Modelo `justech.do.rnc.padron` y wizard de importación TXT/CSV (formato DGII oficial).
- Validación RNC en formulario de contactos con Resultado y Fuente separados.
- Autocompletado de razón social cuando Nombre está vacío.
- Control de RNC duplicado (contacto existente + abrir).

### Changed
- Vista `res.partner`: bloques Identificación fiscal, Configuración fiscal y Relación comercial a ancho completo.
- Importador alineado al layout oficial `DGII_RNC.TXT`.

### Operational
- Padrón DGII cargado en `justech_dev` (fuente `dgii_txt`).

## [19.0.1.6.0] — 2026-07-09 — Fase 3A Sprint 1

### Added
- Capa `validators/` (RNC, NCF, contexto fiscal v2.0 duplicados).
- Capa `services/` (`fiscal.validator`, `fiscal.config`, `document.type.provider`).
- Placeholders `providers/` y `adapters/` para extensiones futuras.
- Pruebas `test_fiscal_validators.py` (Odoo) + runner standalone en `tools/`.
- Documentación técnica: ARCHITECTURE, MIGRATION, ROADMAP, diagramas.

### Changed
- `res.partner` delega validación RNC al servicio fiscal (sin cambio funcional).
- `fiscal.document.type.parse_ncf` delega a validador puro.

### Unchanged (compatibilidad)
- Datos maestros NCF, vistas, permisos y reglas de negocio existentes.
