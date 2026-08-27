# Changelog — justech_l10n_do_adel_freeze

## [19.0.1.0.0] — 2026-07-13

### Added
- Congelación de emisión Adel cuando `justech_do_fiscal_enabled` está activo.
- Bloqueo de `account.fiscal.sequence.get_fiscal_number` para empresas Justech.
- Limpieza de `l10n_do_fiscal_sequence_id` en post y journals sin LatAm docs.

### Notes
- Legacy permanece instalado solo para lectura histórica / compatibilidad FDP.
- Fuente activa de nuevas asignaciones: Motor Fiscal Justech.
