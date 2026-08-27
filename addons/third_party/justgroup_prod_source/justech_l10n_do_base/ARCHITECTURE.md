# Arquitectura — justech_l10n_do_base

## Propósito

Capa fundacional del **Estándar Fiscal Justech** para República Dominicana. Centraliza
validaciones puras, servicios reutilizables y configuración por empresa.

## Capas

| Capa | Ubicación | Responsabilidad |
|------|-----------|-----------------|
| **Validators** | `validators/` | Reglas puras sin BD (RNC, NCF, clave duplicado v2.0) |
| **Services** | `services/` | AbstractModels Odoo que orquestan validators |
| **Providers** | `providers/` | Lectura de tipos documentales y config |
| **Adapters** | `adapters/` | Puentes externos (DGII API, e-CF) — Sprint 2+ |
| **Models** | `models/` | Persistencia Odoo; delegación mínima |

## Servicios registrados

| Modelo técnico | Rol |
|----------------|-----|
| `justech.do.fiscal.validator.service` | RNC/NCF, claves fiscales |
| `justech.do.fiscal.config.service` | Fiscal habilitado, ir.config_parameter |
| `justech.do.document.type.provider` | Tipos NCF, prefijos, parse |

## Diagrama

Ver `diagrams/architecture.mmd` y `diagrams/dependencies.mmd`.

## Principios

1. **Validators puros** — testeables sin instancia Odoo.
2. **Una sola fuente de verdad** — ningún módulo downstream reimplementa RNC/NCF.
3. **Sin hardcode** — validado por `tools/fiscal_no_hardcode_check.py`.
4. **Compatibilidad** — extensiones vía herencia, no parches al core.

## Dependencias Odoo

```
account, contacts, l10n_do
```

## Consumidores

- `justech_l10n_do_ncf`
- `justech_l10n_do_dashboard`
- `justech_l10n_do_reports` (futuro: adapters)
- `justech_l10n_do_payments` (futuro)
